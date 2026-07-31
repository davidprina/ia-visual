"""Bitácora técnica: eventos estructurados a archivo rotativo, con nivel configurable.

Es NUC-06 y nada más que NUC-06. Lo que se escribe acá es **diagnóstico**: sirve para
entender por qué una cámara dejó de entregar cuadros, se le sube el nivel de detalle
cuando hay que depurar, se comprime y se manda por correo a soporte, y se borra sin
consecuencias cuando ya no hace falta. Rota por tamaño y conserva una cantidad acotada de
respaldos, así que el archivo más viejo desaparece por diseño.

**Este módulo no es la vía por la que se registra un hecho auditable.** Los hechos que
sostienen la cadena de custodia van por la vía del dominio a la tabla encadenada por hash,
que sólo agrega y nunca rota. Son dos destinos con dos disciplinas opuestas y **sin una
línea de código en común**, y esa separación está fijada como invariante de código en
`tests/arquitectura/invariantes/inv_01_06.py` (D-11, T-01-23).

Por qué importa que sean dos y no una con un parámetro: si fueran la misma, subir el nivel
de detalle para perseguir un problema de red inundaría de ruido la evidencia legal, y la
rotación por tamaño —que acá es una virtud— borraría eslabones de la cadena. El parámetro
que las uniría es exactamente el antipatrón que el catálogo de pitfalls marca como señal de
alerta, y por eso el módulo no puede ni nombrar al otro.

**Las tres decisiones de implementación:**

1. **`structlog` sobre el `logging` de la stdlib.** La rotación la da
   `logging.handlers.RotatingFileHandler` sin agregar una dependencia; lo que aporta
   `structlog` es el contexto acumulado por hilo (`bind`), que es lo único que vuelve
   legible una bitácora de N fuentes de video concurrentes cuando llegue la Fase 2.
2. **Toda la cadena de procesadores corre una sola vez, antes de cualquier handler.** Los
   handlers sólo eligen cómo se ve el resultado —JSON por línea en el archivo, formato
   para personas en la consola—. Es lo que garantiza que el redactor de secretos
   (`redaccion.py`) no pueda ser esquivado por un destino que se agregue después.
3. **El archivo se abre con `encoding="utf-8"` explícito.** La codificación por defecto de
   Windows es cp1252 (Pitfall 8) y una bitácora en español con eñes y tildes se corrompe o
   revienta con `UnicodeEncodeError`. Es la misma razón por la que el punto de entrada de
   la consola hace `reconfigure`.

La ubicación por defecto se resuelve con `platformdirs` bajo el identificador técnico
`porteria` (D-36) y no cableando `%APPDATA%`: es lo que hace que Linux y macOS funcionen
cuando lleguen, sin un `if sys.platform`. *(Riesgo asumido de D-36: si el nombre comercial
cambia antes de la Fase 11, la carpeta hay que renombrarla en instalaciones ya
desplegadas.)*
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import platformdirs
import structlog

from porteria.infraestructura.runtime.redaccion import redactar

__all__ = [
    "BYTES_MAXIMOS_POR_DEFECTO",
    "IDENTIFICADOR_TECNICO",
    "NIVEL_POR_DEFECTO",
    "NOMBRE_ARCHIVO",
    "RESPALDOS_POR_DEFECTO",
    "cerrar_bitacora",
    "configurar_bitacora",
    "directorio_de_bitacora_por_defecto",
    "obtener_bitacora",
    "procesadores_compartidos",
]

#: Identificador técnico neutro de D-36. El nombre comercial se define antes de la Fase 11.
IDENTIFICADOR_TECNICO = "porteria"

#: Nombre del archivo activo. Los respaldos son `porteria.log.1` … `porteria.log.N`.
NOMBRE_ARCHIVO = "porteria.log"

#: Nivel por defecto. Se cambia por configuración (capa 2, clave `nivel_bitacora`), nunca
#: editando código: es literalmente lo que pide NUC-06.
NIVEL_POR_DEFECTO = "INFO"

#: 5 MiB por archivo. Con `RESPALDOS_POR_DEFECTO` da un techo de 30 MiB: suficiente para
#: reconstruir varios días de operación y despreciable frente al disco de la evidencia.
BYTES_MAXIMOS_POR_DEFECTO = 5 * 1024 * 1024

#: Respaldos conservados. El techo total es `(respaldos + 1) * bytes_maximos`, y que exista
#: un techo es el control de T-01-24: el diagnóstico no puede llenar el disco donde vive la
#: evidencia y dejar al sistema sin poder registrar capturas.
RESPALDOS_POR_DEFECTO = 5

#: Los handlers que este módulo instaló en el logger raíz. Se guardan para poder sacarlos:
#: en Windows un archivo abierto no se puede borrar ni mover, así que dejar handlers
#: colgados rompe la rotación y la limpieza. Nunca se toca ningún handler ajeno.
_handlers_instalados: list[logging.Handler] = []


def directorio_de_bitacora_por_defecto() -> Path:
    """Dónde van los archivos si nadie configuró otra cosa.

    Se expone como función propia para que el composition root del plan 01-07 la use tal
    cual en vez de reconstruir la ruta, que es como aparecen dos ubicaciones distintas
    para el mismo archivo y nadie encuentra el que busca.
    """
    return Path(platformdirs.user_log_dir(IDENTIFICADOR_TECNICO, appauthor=False))


def _serializar(objeto: Any, **argumentos: Any) -> str:
    """Vuelca a JSON sin escapar los no-ASCII: una `ñ` se escribe `ñ`, no `\\u00f1`.

    `default` cae en `str` para que un valor no serializable —un `Path`, un enum— se
    escriba en vez de tumbar la emisión del evento. Una bitácora que revienta al registrar
    un problema es peor que no tenerla.
    """
    argumentos.setdefault("default", str)
    return json.dumps(objeto, ensure_ascii=False, **argumentos)


def procesadores_compartidos() -> list[Callable[..., Any]]:
    """La cadena que corre **una sola vez**, antes de que el evento llegue a un handler.

    El orden importa y es el siguiente: contexto por hilo, filtro por nivel, nivel, nombre
    del emisor, marca temporal ISO-8601 en UTC, información de excepción y, al final, el
    redactor de secretos. Que el redactor sea el último de la cadena compartida —y no algo
    que cada handler aplique por su cuenta— es lo que hace imposible que un destino nuevo
    vea un valor en claro por haberse olvidado de enchufarlo.
    """
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        # Último eslabón compartido, y a propósito el último: lo que salga de acá ya no
        # tiene credenciales, y cualquier destino que se agregue después las hereda
        # redactadas sin tener que acordarse de nada.
        redactar,
    ]


def _formateador(renderizador: Any) -> logging.Formatter:
    """Envuelve un renderizador para que un handler de la stdlib pueda usarlo."""
    return structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderizador,
        ],
    )


def _numero_de_nivel(nivel: str | int) -> int:
    """Traduce el nivel configurado a su número, o explica qué valores son válidos."""
    if isinstance(nivel, int):
        return nivel

    conocidos = logging.getLevelNamesMapping()
    numero = conocidos.get(str(nivel).strip().upper())
    if numero is None:
        raise ValueError(
            f"«{nivel}» no es un nivel de detalle válido para la bitácora. Los valores "
            "aceptados son: DEBUG, INFO, WARNING, ERROR, CRITICAL."
        )
    return numero


def cerrar_bitacora() -> None:
    """Saca del logger raíz los handlers que instaló este módulo y cierra sus archivos.

    Idempotente. Es lo que permite reconfigurar en caliente —cambiar el nivel sin
    reiniciar— y lo que hace que en Windows el archivo quede libre para rotar o borrar.
    """
    raiz = logging.getLogger()
    while _handlers_instalados:
        manejador = _handlers_instalados.pop()
        raiz.removeHandler(manejador)
        try:
            manejador.close()
        except OSError:  # pragma: no cover - cerrar dos veces no debe tumbar nada
            pass


def configurar_bitacora(
    ruta_directorio: Path | str | None = None,
    nivel: str | int = NIVEL_POR_DEFECTO,
    bytes_maximos: int = BYTES_MAXIMOS_POR_DEFECTO,
    respaldos: int = RESPALDOS_POR_DEFECTO,
) -> Path:
    """Deja la bitácora técnica lista y devuelve la ruta del archivo activo.

    Args:
        ruta_directorio: Dónde escribir. Si es `None`, se usa el directorio por defecto.
        nivel: Nivel mínimo que llega al archivo y a la consola. Viene de la configuración.
        bytes_maximos: Tamaño a partir del cual el archivo activo rota.
        respaldos: Cuántos archivos rotados se conservan.

    Llamarla dos veces **reemplaza** la configuración anterior en vez de sumarse a ella: si
    se acumularan handlers, cada línea aparecería duplicada y los archivos de la
    configuración vieja quedarían abiertos.
    """
    directorio = (
        Path(ruta_directorio)
        if ruta_directorio is not None
        else directorio_de_bitacora_por_defecto()
    )
    directorio.mkdir(parents=True, exist_ok=True)
    archivo = directorio / NOMBRE_ARCHIVO
    numero = _numero_de_nivel(nivel)

    cerrar_bitacora()

    a_archivo = logging.handlers.RotatingFileHandler(
        archivo,
        maxBytes=bytes_maximos,
        backupCount=respaldos,
        encoding="utf-8",
    )
    a_archivo.setFormatter(_formateador(structlog.processors.JSONRenderer(serializer=_serializar)))

    # Segundo destino, con formato pensado para una persona sentada frente al equipo.
    # `colors=False` porque la consola del cliente no está garantizada y los códigos de
    # escape sin intérprete son ruido ilegible.
    a_consola = logging.StreamHandler(stream=sys.stderr)
    a_consola.setFormatter(_formateador(structlog.dev.ConsoleRenderer(colors=False)))

    raiz = logging.getLogger()
    for manejador in (a_archivo, a_consola):
        manejador.setLevel(numero)
        raiz.addHandler(manejador)
        _handlers_instalados.append(manejador)
    raiz.setLevel(numero)

    structlog.configure(
        processors=[
            *procesadores_compartidos(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        # Sin caché: si se cacheara, cambiar el nivel en caliente no tendría efecto sobre
        # los emisores ya creados y la configuración mentiría.
        cache_logger_on_first_use=False,
    )

    return archivo


def obtener_bitacora(nombre: str | None = None) -> Any:
    """Devuelve el emisor de eventos del módulo que la pide.

    El uso previsto es `obtener_bitacora(__name__).bind(camara="lateral")`: lo que se liga
    con `bind` viaja con cada evento posterior de ese emisor, y es lo que permite leer una
    corrida con varias fuentes concurrentes sin ir cruzando líneas a mano.
    """
    return structlog.get_logger(nombre)
