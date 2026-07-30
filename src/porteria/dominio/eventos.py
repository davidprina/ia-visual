"""`EventoDeDominio`: los agregados **acumulan** hechos, no los publican.

La diferencia es la que hace posible el outbox de D-12. Si un agregado publicara sus
eventos al ocurrir, la publicación pasaría fuera de la transacción que confirma la fila
de evidencia y el manifiesto — y entonces existirían eventos de capturas que no se
guardaron, o capturas guardadas cuyo evento se perdió. Acumulándolos, el caso de uso los
recoge y los persiste en el outbox **dentro de la misma transacción**: o está todo o no
está nada.

Cada evento lleva los dos relojes (Patrón 7): `ocurrido_en` es el sello de calendario que
se lee y se audita, e `instante_monotono_ns` es el que sirve para medir deltas contra
otros hechos de la misma corrida.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from porteria.dominio.comun.tiempo import InstanteUtc

__all__ = ["EventoDeDominio"]


@dataclass(frozen=True, slots=True)
class EventoDeDominio:
    """Un hecho ya ocurrido, inmutable y con sus dos sellos de tiempo.

    Attributes:
        nombre: Identificador del hecho en minúsculas y con puntos, por ejemplo
            `evidencia.agregada`. Es lo que después discrimina el consumidor del outbox.
        ocurrido_en: Sello UTC persistible.
        instante_monotono_ns: `perf_counter_ns` crudo del momento del hecho.
        datos: Detalle del hecho, siempre texto contra texto para que serializarlo al
            outbox no requiera decidir nada. Se copia y se congela en la construcción:
            un evento que se puede editar después de acumulado es un evento que miente.
    """

    nombre: str
    ocurrido_en: InstanteUtc
    instante_monotono_ns: int
    datos: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.nombre:
            raise ValueError(
                "El nombre del evento de dominio no puede estar vacío: es lo que el "
                "consumidor del outbox usa para saber qué hacer con el hecho."
            )
        object.__setattr__(self, "datos", MappingProxyType(dict(self.datos)))
