"""Dos versiones que no son la misma, y la negativa a abrir una base del futuro (D-35).

**La versión del producto y la del esquema se mueven por separado.** Si fueran el mismo
número, cada release obligaría a una migración y cada migración obligaría a un release. El
producto se versiona por lo que le cambió al usuario; el esquema, por lo que le cambió a la
base. Las dos se persisten en cada captura y en cada ítem de evidencia, porque dentro de
veinte años la pregunta de auditoría va a ser «qué versión escribió esta fila».

**Abrir una base más nueva que la aplicación está prohibido, y no es paranoia.** Ocurre en
campo con una secuencia banal: el cliente actualiza, la base migra, más tarde alguien
reinstala desde el instalador viejo que quedó guardado en una carpeta compartida. Esa
aplicación vieja no conoce las columnas que la migración agregó; si abre igual, escribe
filas incompletas sobre evidencia buena y la corrupción es silenciosa y acumulativa. Negarse
a abrir con un mensaje que nombra las dos versiones convierte una pérdida de datos en un
llamado a soporte.

**Por qué la versión de esquema es el identificador de revisión de Alembic.** Podría ser un
número aparte, pero entonces habría dos verdades sobre el mismo hecho y nada que impidiera
que se contradijeran. Con el identificador de la revisión cabeza, la única forma de subir la
versión de esquema es agregar una migración — que es exactamente lo que la versión significa.
"""

from __future__ import annotations

from enum import StrEnum
from importlib import metadata
from typing import Final

__all__ = [
    "VERSION_APP",
    "VERSION_ESQUEMA",
    "BaseMasNuevaQueLaAplicacion",
    "Veredicto",
    "comprobar",
]

#: La revisión cabeza de Alembic que esta aplicación conoce. Sube cuando se agrega una
#: migración, y sólo entonces.
VERSION_ESQUEMA: Final = "0002"


def _version_instalada() -> str:
    """La versión del producto, o un texto explícito si corre sin instalar."""
    try:
        return metadata.version("porteria")
    except metadata.PackageNotFoundError:  # pragma: no cover - sólo sin instalar
        return "no instalada"


#: La versión del producto (D-35). Se lee del paquete instalado y no se escribe a mano en
#: dos lugares: un número duplicado se desincroniza en la primera release apurada.
VERSION_APP: Final = _version_instalada()


class Veredicto(StrEnum):
    """Qué corresponde hacer con la base que se encontró."""

    #: La base es más vieja: hay migraciones pendientes que aplicar.
    MIGRAR = "MIGRAR"
    #: La base y la aplicación hablan el mismo esquema.
    COMPATIBLE = "COMPATIBLE"


class BaseMasNuevaQueLaAplicacion(RuntimeError):
    """La base la migró una versión posterior. Abrirla corrompería la evidencia."""


def _como_numero(version: str, cual: str) -> int:
    """Convierte un identificador de revisión a entero para poder ordenarlo."""
    try:
        return int(version)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"«{version}» no es una versión de esquema válida ({cual}). Las versiones de "
            "esquema son el identificador numérico de la revisión de Alembic, con ceros a "
            "la izquierda, por ejemplo 0002.\n"
            "Qué revisar: si el valor salió de la tabla `alembic_version` de una base "
            "ajena, esa base no es de este producto."
        ) from error


def comprobar(version_base: str, version_app: str = VERSION_ESQUEMA) -> Veredicto:
    """Decide si la base se puede abrir, hay que migrarla, o hay que negarse.

    Args:
        version_base: La versión de esquema que trae la base que se encontró.
        version_app: La versión de esquema que **esta aplicación** conoce. Por defecto,
            `VERSION_ESQUEMA`. Se admite pasarla para poder probar los tres caminos sin
            fabricar bases de versiones inventadas.

    Returns:
        `Veredicto.MIGRAR` si la base es más vieja, `Veredicto.COMPATIBLE` si coinciden.

    Raises:
        BaseMasNuevaQueLaAplicacion: si la base es más nueva. El mensaje nombra las dos
            versiones porque quien lo lee está en una planta sin área de sistemas y lo que
            necesita saber es qué versión del producto instalar (UI-05).
    """
    de_la_base = _como_numero(version_base, "la de la base")
    de_la_app = _como_numero(version_app, "la de la aplicación")

    if de_la_base > de_la_app:
        raise BaseMasNuevaQueLaAplicacion(
            f"La base de datos está en la versión de esquema {version_base} y esta "
            f"aplicación conoce hasta la {version_app}. No se abre a propósito: una versión "
            "vieja no conoce las columnas que agregó la migración y escribiría filas "
            "incompletas sobre evidencia que hoy está bien.\n"
            "Qué hacer: instalar una versión del producto igual o posterior a la que migró "
            "esta base. Suele pasar al reinstalar desde un instalador guardado. La "
            "evidencia está intacta; sólo hace falta abrirla con la versión correcta."
        )

    if de_la_base < de_la_app:
        return Veredicto.MIGRAR

    return Veredicto.COMPATIBLE
