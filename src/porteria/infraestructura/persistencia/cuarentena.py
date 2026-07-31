"""Barrido de archivos huérfanos: este módulo **sólo mueve** archivos.

El destino de un archivo sin fila es la carpeta de cuarentena, con la fecha del barrido, y
desde ahí queda listado en el estado del sistema para que alguien lo mire. Nunca la
papelera (D-13).

**Por qué mover y no otra cosa.** El criterio que ordena toda la escritura de evidencia es
que *un archivo huérfano es basura recuperable y una fila huérfana es evidencia rota*
(D-12). De ahí sale el orden archivo-primero: primero el archivo, después la transacción.
La consecuencia buscada de ese orden es que un corte de energía deje archivos sin fila —y
un archivo sin fila puede ser justamente la foto del camión del corte de luz, que es
exactamente la que alguien va a pedir cuando vuelva la luz. Tratar ese archivo como basura
sería tirar el caso que el diseño entero está tratando de proteger.

Hay una invariante de código que verifica esta propiedad sobre el texto de este módulo, y
por eso el módulo tampoco **nombra** las funciones que no usa: el texto se busca tal cual,
y una prosa que las mencionara para explicar que no se usan invalidaría la invariante que
la explica.

**El barrido corre en segundo plano** para no demorar el arranque: puede haber miles de
archivos y el portero necesita el sistema en pantalla, no una barra de progreso.
`barrer_huerfanos` es síncrona y comprobable; `barrer_en_segundo_plano` es la que el plan
01-07 agenda al arrancar.

**Recibe las rutas conocidas como parámetro y no consulta la base.** Así se prueba sin
persistencia, y el orden de responsabilidades queda a la vista: quién sabe qué filas hay es
el repositorio, no el sistema de archivos.
"""

from __future__ import annotations

import datetime as dt
import os
import threading
from collections.abc import Iterable
from pathlib import Path
from typing import Final, NamedTuple

from porteria.dominio.comun.tiempo import FechaLocal
from porteria.infraestructura.persistencia.evidencia_fs import (
    EXTENSION_DE_EVIDENCIA,
    PREFIJO_TEMPORAL,
    SUFIJO_TEMPORAL,
    ruta_para_el_sistema,
)

__all__ = [
    "NOMBRE_DE_LA_CUARENTENA",
    "ArchivoEnCuarentena",
    "barrer_en_segundo_plano",
    "barrer_huerfanos",
]

#: Carpeta de primer nivel bajo la raíz de evidencia. Queda fuera del barrido: si se
#: barriera a sí misma, cada arranque hundiría un nivel más los archivos ya apartados.
NOMBRE_DE_LA_CUARENTENA: Final = "cuarentena"

#: Cuántos nombres alternativos se prueban antes de darse por vencido con una colisión.
_INTENTOS_DE_NOMBRE: Final = 1000


class ArchivoEnCuarentena(NamedTuple):
    """Qué se apartó, adónde fue y cuánto ocupa.

    Las dos rutas son **relativas a la raíz de evidencia** y con `/`, por la misma razón
    que la ruta de la evidencia lo es (D-06): esto va al estado del sistema y a la salida
    `--json` de la línea de comandos, y una ruta absoluta ahí filtra la estructura de
    directorios del equipo del cliente.
    """

    ruta_original: str
    ruta_en_cuarentena: str
    bytes_ocupados: int


def _es_candidato(nombre: str) -> bool:
    """Dice si el archivo es evidencia o un temporal de una escritura interrumpida."""
    if nombre.endswith(EXTENSION_DE_EVIDENCIA):
        return True
    return nombre.startswith(PREFIJO_TEMPORAL) and nombre.endswith(SUFIJO_TEMPORAL)


def _texto_de_la_fecha(fecha_local: FechaLocal | dt.date | None) -> str:
    """`AAAA-MM-DD` del barrido. Se puede fijar para que las pruebas no dependan del día."""
    if fecha_local is None:
        return dt.date.today().isoformat()
    if isinstance(fecha_local, FechaLocal):
        return fecha_local.texto
    return fecha_local.isoformat()


def _nombre_libre(directorio: Path, nombre: str) -> Path:
    """Encuentra un nombre que no esté ocupado en la carpeta de destino.

    Dos huérfanos distintos pueden llamarse igual —el mismo contenido guardado en dos
    fechas distintas produce el mismo nombre, porque el nombre es el hash—, y apartar el
    segundo encima del primero haría desaparecer al primero por la puerta de atrás. Que
    este módulo no elimine nada de forma directa no serviría de mucho si lo eliminara así.
    """
    candidato = directorio / nombre
    if not os.path.exists(ruta_para_el_sistema(candidato)):
        return candidato

    raiz_del_nombre = Path(nombre).stem
    extension = Path(nombre).suffix
    for numero in range(1, _INTENTOS_DE_NOMBRE):
        candidato = directorio / f"{raiz_del_nombre}-{numero}{extension}"
        if not os.path.exists(ruta_para_el_sistema(candidato)):
            return candidato

    raise FileExistsError(
        f"No se encontró un nombre libre para «{nombre}» en la cuarentena «{directorio}» "
        f"después de {_INTENTOS_DE_NOMBRE} intentos.\n"
        "Qué revisar: la carpeta de cuarentena tiene una cantidad anormal de copias del "
        "mismo archivo, lo que sugiere que el barrido está corriendo en un bucle."
    )


def barrer_huerfanos(
    raiz: Path | str,
    rutas_conocidas: Iterable[str],
    *,
    fecha_local: FechaLocal | dt.date | None = None,
) -> list[ArchivoEnCuarentena]:
    """Aparta a la cuarentena todo archivo de evidencia que no tenga fila.

    Args:
        raiz: Raíz de evidencia.
        rutas_conocidas: Las `ruta_relativa` que sí figuran en la base. Las aporta el
            repositorio; este módulo no consulta la base.
        fecha_local: Día que nombra la carpeta de cuarentena. Por defecto, hoy.

    Returns:
        Lo apartado, en tuplas `(ruta_original, ruta_en_cuarentena, bytes_ocupados)`. La
        lista vacía significa que no había ningún huérfano, que es el caso normal.
    """
    raiz_resuelta = Path(raiz).resolve()
    carpeta_de_cuarentena = raiz_resuelta / NOMBRE_DE_LA_CUARENTENA
    destino_del_dia = carpeta_de_cuarentena / _texto_de_la_fecha(fecha_local)

    conocidas = {str(ruta).replace("\\", "/") for ruta in rutas_conocidas}
    apartados: list[ArchivoEnCuarentena] = []

    for archivo in sorted(raiz_resuelta.rglob("*")):
        if carpeta_de_cuarentena in archivo.parents or not archivo.is_file():
            continue
        if not _es_candidato(archivo.name):
            continue

        relativa = archivo.relative_to(raiz_resuelta).as_posix()
        if relativa in conocidas:
            continue

        bytes_ocupados = archivo.stat().st_size
        os.makedirs(ruta_para_el_sistema(destino_del_dia), exist_ok=True)
        destino = _nombre_libre(destino_del_dia, archivo.name)

        # `os.replace` por el mismo motivo que en la escritura de evidencia: es lo único
        # que se comporta igual en las dos plataformas, y acá además el origen y el
        # destino están siempre en el mismo volumen porque los dos cuelgan de la raíz.
        os.replace(ruta_para_el_sistema(archivo), ruta_para_el_sistema(destino))

        apartados.append(
            ArchivoEnCuarentena(
                ruta_original=relativa,
                ruta_en_cuarentena=destino.relative_to(raiz_resuelta).as_posix(),
                bytes_ocupados=bytes_ocupados,
            )
        )

    return apartados


def barrer_en_segundo_plano(
    raiz: Path | str,
    rutas_conocidas: Iterable[str],
    *,
    fecha_local: FechaLocal | dt.date | None = None,
) -> threading.Thread:
    """Arranca el barrido en un hilo demonio y devuelve el hilo, ya en marcha (D-13).

    Demonio a propósito: cerrar la aplicación es lo que el portero hace al terminar el
    turno, y un barrido a medio camino no puede impedírselo. Lo que quede sin apartar se
    aparta en el arranque siguiente, porque el criterio no depende de cuándo se corra.

    Las rutas conocidas se materializan **antes** de arrancar el hilo: si se leyeran desde
    adentro, el barrido estaría consultando la base en paralelo con el arranque, que es
    justo el momento que se quiere dejar libre.
    """
    congeladas = set(rutas_conocidas)

    hilo = threading.Thread(
        target=barrer_huerfanos,
        args=(raiz, congeladas),
        kwargs={"fecha_local": fecha_local},
        name="barrido-de-huerfanos",
        daemon=True,
    )
    hilo.start()
    return hilo
