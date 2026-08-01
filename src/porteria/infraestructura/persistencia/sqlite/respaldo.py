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
    """`AAAAMMDD-HHMMSS-mmm` en UTC, con milisegundos.

    Los milisegundos no son precisión decorativa: son lo que hace que **ordenar los nombres
    alfabéticamente dé el mismo resultado que ordenarlos por antigüedad**, que es de lo que
    depende la poda para saber cuál es la copia más vieja. Con resolución de segundo hacía
    falta un sufijo de desempate, y un sufijo rompe justamente esa correspondencia:
    `respaldo-T-2` ordena *antes* que `respaldo-T` porque el guion precede al punto, así que
    la poda tomaba por más vieja a una copia más nueva.
    """
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")[:-3]


def _destino_libre(directorio: Path, marca: str) -> Path:
    """Un nombre que no pise una copia existente.

    Con milisegundos la colisión es casi imposible, pero «casi» no alcanza cuando lo que
    está en juego es el único punto de retorno de la base del cliente: si dos respaldos
    cayeran en el mismo milisegundo, el segundo sobrescribiría al primero y se perdería el
    estado anterior al intento que falló, que es exactamente el que hace falta.
    """
    directorio.mkdir(parents=True, exist_ok=True)

    candidato = directorio / f"{PREFIJO_DE_COPIA}{marca}{SUFIJO_DE_COPIA}"
    if not candidato.exists():
        return candidato

    for orden in range(2, 1000):
        # El desempate va con ancho fijo para no volver a romper el orden alfabético.
        candidato = directorio / f"{PREFIJO_DE_COPIA}{marca}{orden:03d}{SUFIJO_DE_COPIA}"
        if not candidato.exists():
            return candidato

    raise RuntimeError(  # pragma: no cover - mil copias en el mismo milisegundo
        f"Hay más de mil copias con la marca «{marca}» en «{directorio}». "
        "Algo está llamando a respaldar en un bucle."
    )


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
        destino = _destino_libre(origen.parent / "respaldos", _marca_de_tiempo())
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

    conservadas = _podar(destino.parent, conservar, proteger=destino)

    return ResultadoDeRespaldo(
        ruta=destino,
        bytes_de_la_copia=destino.stat().st_size,
        copias_conservadas=len(conservadas),
        bytes_del_conjunto=sum(copia.stat().st_size for copia in conservadas),
    )


def _podar(directorio: Path, conservar: int, *, proteger: Path | None = None) -> list[Path]:
    """Borra las copias más viejas y devuelve las que quedaron.

    Sólo alcanza a archivos que este módulo creó —los que llevan su prefijo y su sufijo—.
    Es deliberado: una poda que barriera el directorio entero podría llevarse la base de un
    cliente que decidió guardar los respaldos junto a otra cosa.

    `proteger` es la copia que se acaba de hacer y **nunca** se borra, pase lo que pase con
    el orden de los nombres. No es defensa en profundidad decorativa: sin ella, cualquier
    error futuro en la correspondencia entre orden alfabético y antigüedad haría que la
    orden `migrar` borrara el respaldo que acaba de tomar y después informara su ruta. El
    operador quedaría creyendo que tiene un punto de retorno que no existe, y se enteraría
    justo cuando fuera a usarlo.
    """
    copias = copias_existentes(directorio)
    if conservar <= 0 or len(copias) <= conservar:
        return copias

    intocable = proteger.resolve() if proteger is not None else None

    for vieja in copias[: len(copias) - conservar]:
        if intocable is not None and vieja.resolve() == intocable:
            continue
        vieja.unlink(missing_ok=True)

    return copias_existentes(directorio)
