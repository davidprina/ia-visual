"""Slot de capacidad 1 con descarte del más viejo: el contrato de frescura (CAP-04).

**La medición que fuerza esta decisión** —20 s de reproducción en tiempo real, video de
320×240 a 25 fps, consumidor a 5 Hz:

| | Slot de capacidad 1 | Cola ilimitada (el antipatrón) |
|---|---|---|
| Antigüedad mediana, 1.ª mitad | 25,8 ms | 4 152,7 ms |
| Antigüedad mediana, 2.ª mitad | **13,9 ms** | 12 218,7 ms |
| Antigüedad máxima | 155,6 ms | 16 175,8 ms |
| Pendiente de crecimiento | ≈ 0 (baja) | **+806,6 ms por segundo** |
| Frames descartados | 403 de 503 (métrica) | 0 — se acumulan |
| Atraso al terminar | 0 | 406 cuadros |

Con el slot la antigüedad **no crece**: baja de 25,8 a 13,9 ms. Con la cola crece a razón
de 0,8 s por cada segundo de operación, hasta 16 segundos de atraso. Eso es el Pitfall 1
del catálogo —la foto no es del instante del botón, y la evidencia queda impugnable—
reproducido en laboratorio y con su mitigación demostrada.

**Por qué se escribe a mano.** Es el único caso de la tabla «Don't Hand-Roll» de la
investigación donde conviene: la semántica que el proyecto necesita no coincide con
ninguna estructura de la biblioteca estándar. `Queue(maxsize=1)` bloquea al productor en
`put()`, que es exactamente lo que no hay que hacer —frenar el decodificador llena el
buffer de red aguas arriba, donde ninguna métrica lo ve—; y `deque(maxlen=1)` no ofrece
espera bloqueante para el consumidor ni contador de descartes, así que habría que
envolverlo con un `Condition`: el mismo slot, con una estructura de más.

**El mismo contrato lo implementa después el adaptador PyAV de la Fase 2 sin cambios.**
Por eso la estructura vive acá, separada de la fuente que la usa: la fuente cambia, el
punto de encuentro no.
"""

from __future__ import annotations

import threading
from typing import Protocol

from porteria.aplicacion.puertos.salida.fuente_de_video import FrameSellado

__all__ = ["FrameSellado", "PuntoDeEncuentro", "SlotUltimoValor"]


class PuntoDeEncuentro(Protocol):
    """Dónde se encuentran el hilo que decodifica y el que consume.

    Existe como protocolo por una sola razón, y es de verificabilidad: la prueba de la
    prueba de CAP-04 necesita montar **el antipatrón a propósito** —una cola ilimitada en
    lugar del slot— y exigir que la evaluación de frescura falle. Sin este punto de
    inyección habría que duplicar el bucle de decodificación dentro de la prueba, y
    entonces la prueba no estaría midiendo el código del producto.

    El antipatrón vive en el módulo de prueba, nunca acá.
    """

    def publicar(self, frame: FrameSellado) -> None:
        """Deja disponible el cuadro. **Nunca bloquea al productor.**"""
        ...

    def tomar(self, timeout: float | None = None) -> FrameSellado | None:
        """Devuelve el cuadro más reciente y vacía el punto de encuentro."""
        ...

    @property
    def metricas(self) -> dict[str, int | bool]:
        """Los contadores que se cuentan donde ocurren los hechos."""
        ...


class SlotUltimoValor:
    """Capacidad 1, descarte del más viejo, contador de descartes.

    `__slots__` porque de esta clase hay una por cámara y sus atributos se tocan en cada
    cuadro: sin `__slots__` cada acceso pasa por el `__dict__` de la instancia.
    """

    __slots__ = ("_consumidos", "_descartados", "_item", "_lock", "_nuevo", "_publicados")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._nuevo = threading.Condition(self._lock)
        self._item: FrameSellado | None = None
        self._descartados = 0
        self._publicados = 0
        self._consumidos = 0

    def publicar(self, frame: FrameSellado) -> None:
        """Deja disponible el cuadro, descartando el anterior si nadie lo consumió.

        El único trabajo bajo el lock son tres enteros y una asignación, así que el
        productor lo suelta en microsegundos y **nunca** espera al consumidor. Que el
        descarte se cuente acá —en el mismo lugar donde ocurre— es lo que convierte
        `frames_descartados == 0` con consumidor lento en una señal confiable de que la
        latencia se está acumulando en otro lado (Pitfall 7).
        """
        with self._nuevo:
            if self._item is not None:
                self._descartados += 1
            self._item = frame
            self._publicados += 1
            self._nuevo.notify()

    def tomar(self, timeout: float | None = None) -> FrameSellado | None:
        """Devuelve el cuadro más reciente y vacía el slot; `None` si no llegó ninguno.

        Con el slot vacío **espera** hasta `timeout` en vez de girar en vacío: un
        consumidor que hace *busy-wait* le roba CPU al hilo que decodifica, que es el que
        no puede atrasarse.
        """
        with self._nuevo:
            if self._item is None:
                self._nuevo.wait(timeout)
            frame, self._item = self._item, None
            if frame is not None:
                self._consumidos += 1
            return frame

    @property
    def metricas(self) -> dict[str, int | bool]:
        """Los tres contadores propios del slot, más el estado de ocupación.

        `frames_consumidos` está acá y no sólo en la capa de métricas para que la
        identidad de conservación —`publicados == descartados + consumidos + ocupado`—
        sea comprobable con datos de una sola fuente. Si el consumo se contara afuera, un
        camino que tomara el cuadro sin avisar rompería la identidad sin que nada lo
        delate.
        """
        with self._lock:
            return {
                "frames_publicados": self._publicados,
                "frames_descartados": self._descartados,
                "frames_consumidos": self._consumidos,
                "ocupado": self._item is not None,
            }
