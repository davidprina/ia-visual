"""La copia previa a cada migración, consistente con el diario de escritura anticipada.

**Copiar el archivo de la base como un archivo común está mal acá, y el error es
silencioso.** Con el diario en modo WAL —que es como arranca este producto (D-14)— las
transacciones confirmadas más recientes viven en el sidecar `-wal` y todavía no se
trasladaron al archivo principal. Una copia a nivel de sistema de archivos se lleva el
archivo principal y deja afuera esas transacciones: el resultado es una base que **abre
perfectamente** y a la que le faltan las últimas capturas. Nadie se entera hasta que hace
falta el respaldo, que es el peor momento posible para descubrirlo.

La API de copia de SQLite recorre las páginas por dentro del motor, así que incluye lo que
está en el WAL y produce una copia consistente aunque haya escritores. Hay una invariante de
código que exige que este módulo **no** nombre al módulo de utilidades de copia de archivos
de la biblioteca estándar: es la forma equivocada de resolver esto y es la que alguien va a
escribir por costumbre.

**Las copias se conservan acotadas y el conjunto informa cuánto ocupa** (D-34). Un respaldo
antes de cada migración es barato; una carpeta que crece sin techo en el disco donde vive la
evidencia no lo es. Que la orden pueda decir cuánto ocupan es lo que permite que alguien
decida bajarlas o moverlas antes de que el disco se llene.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

__all__ = ["ResultadoDeRespaldo", "copias_existentes", "respaldar"]

#: Cuántas copias se conservan por defecto. Suficiente para volver atrás de una migración
#: mala sin convertir la carpeta en un archivo histórico.
COPIAS_A_CONSERVAR = 5

#: Prefijo de los archivos de copia, para poder distinguirlos de la base y contarlos.
PREFIJO_DE_COPIA = "respaldo-"

#: Sufijo. Se conserva la extensión de SQLite para que la copia se pueda abrir con
#: cualquier herramienta sin renombrarla.
SUFIJO_DE_COPIA = ".sqlite3"


@dataclass(frozen=True, slots=True)
class ResultadoDeRespaldo:
    """Dónde quedó la copia y cuánto ocupa el conjunto conservado."""

    ruta: Path
    bytes_de_la_copia: int
    copias_conservadas: int
    bytes_del_conjunto: int


def _marca_de_tiempo() -> str:
    """`AAAAMMDD-HHMMSS` en UTC: ordena lexicográficamente igual que cronológicamente."""
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def copias_existentes(directorio: Path) -> list[Path]:
    """Las copias que hay en el directorio, de la más vieja a la más nueva."""
    if not directorio.is_dir():
        return []
    return sorted(directorio.glob(f"{PREFIJO_DE_COPIA}*{SUFIJO_DE_COPIA}"))


def respaldar(
    ruta_db: Path,
    ruta_backup: Path | None = None,
    *,
    conservar: int = COPIAS_A_CONSERVAR,
) -> ResultadoDeRespaldo:
    """Copia la base de forma consistente y poda las copias sobrantes.

    Args:
        ruta_db: La base a copiar. Tiene que existir: respaldar una base inexistente sería
            producir un archivo vacío y llamarlo respaldo.
        ruta_backup: Dónde dejar la copia. Si es `None`, se arma un nombre con marca de
            tiempo en un subdirectorio `respaldos/` al lado de la base.
        conservar: Cuántas copias dejar. Las más viejas se borran.

    Returns:
        Dónde quedó la copia y cuánto ocupa el conjunto, para que la orden `migrar` lo
        informe (D-34).

    Raises:
        FileNotFoundError: si la base no existe.
    """
    origen = Path(ruta_db)
    if not origen.is_file():
        raise FileNotFoundError(
            f"No hay ninguna base de datos en «{origen}», así que no hay nada que "
            "respaldar.\n"
            "Qué revisar: que la ruta de la base del archivo de arranque apunte a donde "
            "está la base real. Si el archivo todavía no existe porque es la primera "
            "migración, no hace falta respaldo."
        )

    if ruta_backup is None:
        destino = origen.parent / "respaldos" / (
            f"{PREFIJO_DE_COPIA}{_marca_de_tiempo()}{SUFIJO_DE_COPIA}"
        )
    else:
        destino = Path(ruta_backup)

    destino.parent.mkdir(parents=True, exist_ok=True)

    # La copia recorre las páginas por dentro del motor: incluye lo que vive en el `-wal`.
    conexion_origen = sqlite3.connect(origen)
    conexion_destino = sqlite3.connect(destino)
    try:
        with conexion_destino:
            conexion_origen.backup(conexion_destino)
    finally:
        conexion_destino.close()
        conexion_origen.close()

    conservadas = _podar(destino.parent, conservar)

    return ResultadoDeRespaldo(
        ruta=destino,
        bytes_de_la_copia=destino.stat().st_size,
        copias_conservadas=len(conservadas),
        bytes_del_conjunto=sum(copia.stat().st_size for copia in conservadas),
    )


def _podar(directorio: Path, conservar: int) -> list[Path]:
    """Borra las copias más viejas y devuelve las que quedaron.

    Sólo alcanza a archivos que este módulo creó —los que llevan su prefijo y su sufijo—.
    Es deliberado: una poda que barriera el directorio entero podría llevarse la base de un
    cliente que decidió guardar los respaldos junto a otra cosa.
    """
    copias = copias_existentes(directorio)
    if conservar <= 0 or len(copias) <= conservar:
        return copias

    for vieja in copias[: len(copias) - conservar]:
        vieja.unlink(missing_ok=True)

    return copias_existentes(directorio)
