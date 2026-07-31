"""Capa 2 de D-30: todo lo que no es una ruta de arranque vive en la base, con autoría.

Que estos parámetros vivan en la base y no en un archivo tiene tres consecuencias que el
archivo no puede dar: entran en la copia de seguridad junto con la evidencia que
condicionan, se editan desde la interfaz cuando llegue sin abrir un editor de texto, y
**cada cambio deja quién y cuándo**. Eso último es T-01-22 y es D-40: nadie ensancha la
ventana de aceptación —haciendo que capturas viejas pasen retroactivamente de estimadas a
sincronizadas— sin dejar rastro. Por eso `escribir` exige autor en la firma: olvidarlo es
un error de llamada, no una omisión silenciosa.

**El catálogo es una estructura consultable, no siete constantes sueltas.** El composition
root del plan 01-07 lo **recorre** para inyectar valores en el caso de uso de captura, y
tiene una prueba propia que exige que las siete claves existan con su tipo y su valor por
defecto. Un catálogo consultable es también lo que permite que `porteria configurar
--listar` muestre lo que hay sin repetir la lista en otro lado.

**El `Engine` se inyecta, no se construye acá.** En las pruebas de este plan apunta a un
esquema mínimo que crea la propia prueba; en el producto es el que arma el composition root
con el motor real del plan 01-05. La clase no cambia entre los dos casos: es la misma pieza
con distinto `Engine`. Ésa es la razón por la que este plan no depende del 01-05 y puede
ejecutarse en paralelo.

**Contrato con el esquema del plan 01-05.** Este módulo no es dueño de la tabla: la nombra
y espera las columnas de `COLUMNAS_REQUERIDAS`. Si el esquema real las nombra distinto, las
pruebas de este plan lo dicen antes que el cliente.

**Ninguna credencial pasa por acá.** Las de PALJET y la balanza van en una tabla aparte
(plan 01-10). Hay una prueba que afirma que ninguna clave del catálogo coincide con el
patrón de claves sensibles.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from porteria.aplicacion.puertos.salida.configuracion import ValorDeConfiguracion
from porteria.aplicacion.puertos.salida.reloj import Reloj

__all__ = [
    "CATALOGO",
    "COLUMNAS_REQUERIDAS",
    "NOMBRE_DE_LA_TABLA",
    "NOMBRE_DE_TIPO",
    "AutorRequerido",
    "ClaveDeConfiguracion",
    "ClaveDesconocida",
    "ConfiguracionEnBase",
    "catalogo_como_valores",
    "convertir_desde_texto",
]

#: La tabla de la capa 2. El esquema es del plan 01-05; acá sólo se la nombra.
NOMBRE_DE_LA_TABLA = "configuracion"

#: Las columnas que este adaptador espera encontrar. Es el contrato con el plan 01-05.
COLUMNAS_REQUERIDAS = ("clave", "valor", "cambiado_por", "cambiado_en_utc_iso")

#: Nombres de tipo en español, para que un mensaje de error diga «entero» y no «int».
#: Lo lee alguien en una planta sin área de sistemas (UI-05).
NOMBRE_DE_TIPO: Mapping[type, str] = MappingProxyType(
    {int: "entero", str: "texto", float: "número", dict: "mapa de clave y valor"}
)


class ClaveDesconocida(KeyError):
    """La clave pedida no está en el catálogo. El mensaje enumera las que sí están."""


class AutorRequerido(ValueError):
    """Se intentó cambiar la configuración sin decir quién. T-01-22."""


@dataclass(frozen=True, slots=True)
class ClaveDeConfiguracion:
    """Una clave de la capa 2: cómo se llama, qué tipo tiene, cuánto vale y qué significa.

    `ayuda` no es documentación decorativa: es lo que `porteria configurar --listar` le
    muestra al operador, y es donde vive la marca de «no validado» de la ventana de
    aceptación. Un número que nadie midió y que el producto presenta como un hecho es peor
    que no tener número, porque nadie lo vuelve a mirar.
    """

    nombre: str
    tipo: type
    por_defecto: Any
    ayuda: str


#: Las siete claves de la capa 2 que el composition root del plan 01-07 consume.
CATALOGO: Mapping[str, ClaveDeConfiguracion] = MappingProxyType(
    {
        clave.nombre: clave
        for clave in (
            ClaveDeConfiguracion(
                nombre="ventana_aceptacion_ms",
                tipo=int,
                por_defecto=150,
                ayuda=(
                    "Tolerancia, en milisegundos, dentro de la cual dos fotos de la misma "
                    "captura se consideran sincronizadas. ATENCIÓN: el valor por defecto "
                    "es no validado con el cliente ni medido en campo (D-39); medirlo con "
                    "las cámaras reales está agendado. Cada captura guarda cuál era la "
                    "ventana vigente en su momento, así que cambiarla no reinterpreta "
                    "evidencia ya tomada."
                ),
            ),
            ClaveDeConfiguracion(
                nombre="nivel_bitacora",
                tipo=str,
                por_defecto="INFO",
                ayuda=(
                    "Nivel de detalle de la bitácora técnica: DEBUG, INFO, WARNING, ERROR "
                    "o CRITICAL. Subirlo para diagnosticar no afecta al registro "
                    "encadenado de la base, que es otro destino."
                ),
            ),
            ClaveDeConfiguracion(
                nombre="bytes_maximos_bitacora",
                tipo=int,
                por_defecto=5 * 1024 * 1024,
                ayuda=(
                    "Tamaño en bytes a partir del cual el archivo de bitácora rota. Con "
                    "los respaldos, fija el techo de disco que puede ocupar el "
                    "diagnóstico."
                ),
            ),
            ClaveDeConfiguracion(
                nombre="respaldos_bitacora",
                tipo=int,
                por_defecto=5,
                ayuda=(
                    "Cuántos archivos de bitácora rotados se conservan. El techo total es "
                    "(respaldos + 1) por el tamaño máximo."
                ),
            ),
            ClaveDeConfiguracion(
                nombre="calidad_jpeg_por_camara",
                tipo=dict,
                por_defecto={"por_defecto": 88},
                ayuda=(
                    "Calidad de compresión JPEG por cámara, de 1 a 100 (D-01). La clave "
                    "«por_defecto» se aplica a toda cámara sin valor propio; la cámara de "
                    "patentes suele necesitar el máximo."
                ),
            ),
            ClaveDeConfiguracion(
                nombre="dias_retencion_payload_crudo",
                tipo=int,
                por_defecto=90,
                ayuda=(
                    "Días que se conserva el payload crudo de las consultas externas "
                    "(INT-05). Es una política separada de la de evidencia (D-46): un "
                    "payload de hace dos años ya no sirve, una foto sí."
                ),
            ),
            ClaveDeConfiguracion(
                nombre="copias_de_seguridad_a_conservar",
                tipo=int,
                por_defecto=5,
                ayuda=(
                    "Cuántas copias de seguridad previas a una migración se conservan "
                    "(D-34). La copia es la red por si una migración rota llega igual al "
                    "cliente."
                ),
            ),
        )
    }
)

# Sentencias con parámetros ligados: nunca se interpola un valor en el texto del SQL.
_LEER = text(f"SELECT valor FROM {NOMBRE_DE_LA_TABLA} WHERE clave = :clave")  # noqa: S608
_LISTAR = text(
    "SELECT clave, valor, cambiado_por, cambiado_en_utc_iso "  # noqa: S608
    f"FROM {NOMBRE_DE_LA_TABLA}"
)
_ESCRIBIR = text(
    f"INSERT INTO {NOMBRE_DE_LA_TABLA} "  # noqa: S608
    "(clave, valor, cambiado_por, cambiado_en_utc_iso) "
    "VALUES (:clave, :valor, :autor, :cuando) "
    "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor, "
    "cambiado_por = excluded.cambiado_por, "
    "cambiado_en_utc_iso = excluded.cambiado_en_utc_iso"
)


def _exigir_conocida(clave: str) -> ClaveDeConfiguracion:
    """Devuelve la declaración de la clave, o falla enumerando las que existen."""
    declarada = CATALOGO.get(clave)
    if declarada is None:
        disponibles = ", ".join(sorted(CATALOGO))
        raise ClaveDesconocida(
            f"«{clave}» no es una clave de configuración conocida. Las claves "
            f"disponibles son: {disponibles}."
        )
    return declarada


def _exigir_tipo(declarada: ClaveDeConfiguracion, valor: Any) -> Any:
    """Comprueba que el valor sea del tipo que la clave declara.

    Un `"doscientos"` guardado hoy en la ventana de aceptación es un fallo al arrancar
    dentro de seis meses, lejísimos de donde se originó.
    """
    if isinstance(valor, bool) or not isinstance(valor, declarada.tipo):
        esperado = NOMBRE_DE_TIPO.get(declarada.tipo, declarada.tipo.__name__)
        raise ValueError(
            f"«{declarada.nombre}» espera un valor de tipo {esperado} y se recibió "
            f"{valor!r}. Qué hacer: revisá el valor; la ayuda de la clave dice qué "
            f"significa.\n{declarada.ayuda}"
        )
    return valor


def convertir_desde_texto(clave: str, texto_del_valor: str) -> Any:
    """Convierte lo que llega por la línea de comandos al tipo que la clave declara.

    Vive acá y no en la orden de consola porque el dueño del tipo es el catálogo: si la
    conversión viviera en la consola, agregar una clave obligaría a tocar dos archivos y
    el segundo se olvidaría.
    """
    declarada = _exigir_conocida(clave)
    esperado = NOMBRE_DE_TIPO.get(declarada.tipo, declarada.tipo.__name__)

    if declarada.tipo is str:
        return texto_del_valor

    if declarada.tipo is int:
        try:
            return int(texto_del_valor.strip())
        except ValueError as error:
            raise ValueError(
                f"«{clave}» espera un valor de tipo {esperado} y se recibió "
                f"«{texto_del_valor}». Qué hacer: escribí sólo los dígitos, por ejemplo "
                f"{declarada.por_defecto}."
            ) from error

    try:
        interpretado = json.loads(texto_del_valor)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"«{clave}» espera un valor de tipo {esperado} escrito en JSON y se recibió "
            f"«{texto_del_valor}». Qué hacer: usá el formato "
            f"{json.dumps(declarada.por_defecto, ensure_ascii=False)}."
        ) from error

    return _exigir_tipo(declarada, interpretado)


def catalogo_como_valores(
    catalogo: Mapping[str, ClaveDeConfiguracion] = CATALOGO,
) -> dict[str, ValorDeConfiguracion]:
    """Los valores por defecto del catálogo, sin autor ni fecha porque nadie los cambió.

    Es lo que se muestra cuando todavía no hay base: quien está instalando el producto
    necesita ver qué claves existen justo en ese momento, y fallar ahí sería lo peor de
    los dos mundos.
    """
    return {
        nombre: ValorDeConfiguracion(clave=nombre, valor=declarada.por_defecto)
        for nombre, declarada in catalogo.items()
    }


class ConfiguracionEnBase:
    """Implementación del puerto `Configuracion` sobre la tabla `configuracion`.

    Args:
        motor: `Engine` **inyectado**. Este adaptador no lo construye: en las pruebas
            apunta a un esquema mínimo y en el producto al motor real del plan 01-05.
        reloj: el único origen de tiempo del sistema. El instante del cambio se deriva del
            ancla del reloj, no de una lectura suelta del reloj de pared.
    """

    def __init__(self, motor: Engine, reloj: Reloj) -> None:
        self._motor = motor
        self._reloj = reloj

    def leer(self, clave: str) -> Any:
        """Devuelve el valor vigente ya tipado, o el que declara el catálogo."""
        declarada = _exigir_conocida(clave)

        with self._motor.connect() as conexion:
            fila = conexion.execute(_LEER, {"clave": clave}).first()

        if fila is None:
            return declarada.por_defecto

        return _exigir_tipo(declarada, json.loads(fila[0]))

    def escribir(self, clave: str, valor: Any, autor: str) -> None:
        """Persiste el valor junto con quién lo cambió y cuándo.

        `autor` es obligatorio en la firma **y** no puede venir en blanco: un autor vacío
        sería un rastro que dice que alguien cambió algo sin decir quién, que es lo mismo
        que no tener rastro pero con apariencia de tenerlo.
        """
        declarada = _exigir_conocida(clave)
        _exigir_tipo(declarada, valor)

        if not autor or not autor.strip():
            raise AutorRequerido(
                f"No se puede cambiar «{clave}» sin decir quién lo hace. Un cambio de "
                "configuración es un hecho auditable, no un ajuste anónimo: cada captura "
                "guarda la ventana vigente en su momento y hay que poder explicar por qué "
                "cambió."
            )

        cuando = self._reloj.utc_de(self._reloj.instante())

        with self._motor.begin() as conexion:
            conexion.execute(
                _ESCRIBIR,
                {
                    "clave": clave,
                    "valor": json.dumps(valor, ensure_ascii=False),
                    "autor": autor.strip(),
                    "cuando": str(cuando),
                },
            )

    def listar(self) -> dict[str, ValorDeConfiguracion]:
        """Todas las claves del catálogo, tocadas o no, con su rastro.

        Se muestran también las que nadie cambió: un listado que sólo mostrara lo escrito
        dejaría al operador sin saber qué más se puede configurar.
        """
        listado = catalogo_como_valores()

        with self._motor.connect() as conexion:
            filas = conexion.execute(_LISTAR).all()

        for clave, valor, cambiado_por, cambiado_en in filas:
            declarada = CATALOGO.get(clave)
            if declarada is None:
                # Una clave que la base tiene y este catálogo no: es una versión más nueva
                # del producto que escribió acá, o una clave retirada. No se inventa nada.
                continue
            listado[clave] = ValorDeConfiguracion(
                clave=clave,
                valor=json.loads(valor),
                cambiado_por=cambiado_por,
                cambiado_en_utc_iso=cambiado_en,
            )

        return listado
