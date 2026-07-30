"""`Lapida`: el hueco con explicación que deja una purga manual (D-10).

**El sistema nunca borra evidencia por sí solo.** Existe una purga manual por antigüedad, y
cuando se ejecuta deja una lápida: hash, motivo, autor e instante. Los cuatro son
obligatorios y ninguno tiene valor por defecto, porque el punto entero de la lápida es que
**todo hueco tenga explicación**. Una lápida sin motivo o sin autor sería un agujero mudo,
que es indistinguible de un borrado encubierto — y en un producto de auditoría esa
distinción es todo.

Además la lápida es lo que mantiene la bitácora encadenada consistente: el registro de la
purga entra en la cadena como cualquier otro hecho, así que la ausencia del archivo queda
sellada con la misma garantía que su presencia.

**Alcance de esta fase:** el 01-02 fija el esquema del valor y la invariante de no borrado
automático. La herramienta operable de purga se difiere a su fase (D-10).
"""

from __future__ import annotations

from dataclasses import dataclass

from porteria.dominio.comun.identificadores import UsuarioId
from porteria.dominio.comun.tiempo import InstanteUtc
from porteria.dominio.evidencia.huella import HuellaDeIntegridad

__all__ = ["Lapida"]


@dataclass(frozen=True, slots=True)
class Lapida:
    """Lo que queda en lugar de un archivo de evidencia purgado.

    Attributes:
        sha256: La huella de lo que estuvo ahí. Sobrevive al archivo: es lo que permite
            afirmar después *qué* se purgó, no sólo que algo se purgó.
        motivo: Por qué se purgó, en español y legible por una persona.
        autor: Quién lo decidió. Nunca el sistema (D-10).
        ocurrido_en: Cuándo.
    """

    sha256: HuellaDeIntegridad
    motivo: str
    autor: UsuarioId
    ocurrido_en: InstanteUtc

    def __post_init__(self) -> None:
        if not self.motivo.strip():
            raise ValueError(
                "La lápida no puede quedar sin motivo. D-10 exige que todo hueco en la "
                "evidencia tenga explicación: una lápida sin motivo es indistinguible de "
                "un borrado encubierto."
            )
        if not str(self.autor).strip():
            raise ValueError(
                "La lápida no puede quedar sin autor. El sistema nunca borra evidencia "
                "por sí solo, así que toda purga tiene un responsable con nombre."
            )
