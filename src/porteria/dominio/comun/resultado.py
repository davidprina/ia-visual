"""`Resultado[T]`: tres variantes para que el dominio pueda operar con datos ausentes.

El problema concreto que resuelve: el peso teórico de un remito puede no existir en
PALJET (D-31), la balanza puede no responder, y Geomov puede no estar disponible en
absoluto (D-45). Si la ausencia de un dato viaja como excepción, la regla de negocio
"cuando falta el peso teórico el veredicto es *peso teórico incompleto*" termina escrita
en un `except`, donde nadie la ve y nadie la prueba.

Las tres variantes, y por qué son exactamente tres:

* `Ok(valor)` — el dato está y es confiable.
* `NoDisponible(motivo, detalles)` — el dato **no está**, y el motivo es texto para una
  persona (UI-05) mientras los detalles alimentan los reportes. No hay valor: nadie puede
  confundirse y usar un cero.
* `Degradado(valor, motivo, antiguedad_ms)` — hay un valor, pero viejo o de segunda
  mano. La antigüedad viaja con él para que quien decide sepa cuánto vale.

Una cuarta variante obligaría a revisar cada `match` del sistema, así que la cantidad es
parte del contrato y hay una prueba que la fija.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

__all__ = [
    "VARIANTES",
    "Degradado",
    "NoDisponible",
    "Ok",
    "Resultado",
]


@dataclass(frozen=True, slots=True)
class Ok[T]:
    """El dato está y es confiable."""

    valor: T


@dataclass(frozen=True, slots=True)
class NoDisponible:
    """El dato no está. Sin valor, para que nadie pueda tratar la ausencia como cero.

    Attributes:
        motivo: Texto en español, legible por el portero, que dice qué falta y por qué.
        detalles: Los identificadores concretos que faltan — por ejemplo los códigos de
            artículo sin peso teórico. Es lo que consume el reporte de artículos sin peso
            maestro de la Fase 7, sin volver a parsear el motivo.
    """

    motivo: str
    detalles: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Degradado[T]:
    """Hay valor, pero viejo o de segunda mano; la antigüedad viaja con él.

    Attributes:
        valor: El dato utilizable.
        motivo: Por qué está degradado, en español.
        antiguedad_ms: Cuántos milisegundos hace que se obtuvo. Es lo que permite que la
            interfaz muestre "peso de hace 4 s" en vez de dar un número a secas.
    """

    valor: T
    motivo: str
    antiguedad_ms: float


type Resultado[T] = Ok[T] | NoDisponible | Degradado[T]

#: Las variantes, enumeradas para que una prueba pueda exigir que sean exactamente tres.
#: Se declara acá y no en la prueba porque es parte del contrato del módulo.
VARIANTES: Final = (Ok, NoDisponible, Degradado)
