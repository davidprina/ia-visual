"""Identificadores del dominio: opacos para el sistema, legibles para las personas.

D-29 fija **doble identificador**:

* uno **opaco y único universal** para uso interno, que no colisiona si mañana hay un
  segundo puesto de portería o si se importa evidencia de otra instalación;
* uno **legible por año** del estilo `2026-001842`, para que el portero y
  Administración puedan referenciar una captura o un viaje por teléfono.

Los opacos se declaran con `typing.NewType` sobre `str` y no como alias. La diferencia
importa: un alias haría que `ViajeId` y `CapturaId` fueran el mismo tipo y pasar uno
donde va el otro sería legal. Con `NewType`, el verificador de tipos lo marca antes de
que la evidencia quede persistida contra el viaje equivocado — y en tiempo de ejecución
sigue siendo texto, que es lo que se guarda.

Cero dependencias externas, como todo `dominio/` (NUC-01).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, NewType

__all__ = [
    "CamaraId",
    "CapturaId",
    "ItemDeEvidenciaId",
    "NumeroLegible",
    "RemitoId",
    "UsuarioId",
    "ViajeId",
]

#: Identificador opaco de una captura de control.
CapturaId = NewType("CapturaId", str)

#: Identificador opaco de una cámara configurada.
CamaraId = NewType("CamaraId", str)

#: Identificador opaco de un viaje.
ViajeId = NewType("ViajeId", str)

#: Identificador opaco de un remito.
RemitoId = NewType("RemitoId", str)

#: Identificador opaco de un ítem de evidencia (una foto).
ItemDeEvidenciaId = NewType("ItemDeEvidenciaId", str)

#: Identificador opaco de un usuario del sistema.
UsuarioId = NewType("UsuarioId", str)


#: `AAAA-NNNNNN`: cuatro dígitos de año, guion, seis dígitos de secuencia.
PATRON_NUMERO_LEGIBLE: Final = re.compile(r"^\d{4}-\d{6}$")

#: Ancho de la secuencia. Seis dígitos alcanzan para 999 999 eventos por año, muy por
#: encima de lo que produce una portería, y el ancho fijo mantiene el orden
#: lexicográfico igual al numérico dentro de un mismo año.
ANCHO_DE_SECUENCIA: Final = 6


@dataclass(frozen=True, slots=True)
class NumeroLegible:
    """El identificador que una persona puede dictar por teléfono (D-29).

    Se valida en la construcción y no en el borde de entrada: un número mal formado que
    llegue a la base es un dato que después nadie puede buscar, y el borde de entrada
    son varios (la CLI, la futura interfaz, una importación).
    """

    texto: str

    def __post_init__(self) -> None:
        if not PATRON_NUMERO_LEGIBLE.match(self.texto):
            raise ValueError(
                f"«{self.texto}» no es un número legible válido. El formato es "
                "AAAA-NNNNNN: cuatro dígitos de año, un guion y seis dígitos de "
                "secuencia, por ejemplo 2026-001842. Los seis dígitos van completos con "
                "ceros a la izquierda."
            )

    @classmethod
    def de(cls, anio: int, secuencia: int) -> NumeroLegible:
        """Arma el número a partir del año y la secuencia, rellenando con ceros."""
        return cls(f"{anio:04d}-{secuencia:0{ANCHO_DE_SECUENCIA}d}")

    @property
    def anio(self) -> int:
        """El año del número, que es el que reinicia la secuencia."""
        return int(self.texto[:4])

    @property
    def secuencia(self) -> int:
        """La secuencia dentro del año, sin los ceros de relleno."""
        return int(self.texto[5:])

    def __str__(self) -> str:
        return self.texto
