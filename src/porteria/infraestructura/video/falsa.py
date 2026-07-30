"""Fuente falsa: el doble de prueba de NUC-04 **y** el motor del modo demostración (D-48).

Que sea la misma pieza para las dos cosas no es una economía de código, es lo que la
mantiene viva: un falso que se ejercita en cada corrida de pruebas no se pudre, y el día
que haya que mostrar el sistema sin cámaras, sin balanza y sin ERP ya está probado.

No abre ningún archivo y no importa OpenCV. Los cuadros se generan en memoria y son
**deterministas**: el mismo número de secuencia produce el mismo cuadro en cualquier
equipo, lo que permite que una prueba afirme *qué* cuadro recibió en vez de conformarse
con "recibí algo".
"""

from __future__ import annotations

import threading
import time
from collections.abc import Mapping
from typing import Final

import numpy as np

from porteria.aplicacion.puertos.salida.fuente_de_video import (
    FrameSellado,
    PerfilDeFlujo,
)
from porteria.infraestructura.video.metricas import MetricasDeFuente
from porteria.infraestructura.video.slot_ultimo_valor import SlotUltimoValor

__all__ = ["FuenteFalsa"]

ANCHO_POR_DEFECTO: Final = 64
ALTO_POR_DEFECTO: Final = 48
HZ_POR_DEFECTO: Final = 25.0

#: Base del código de color con que se marca el número de secuencia en el cuadro.
BASE: Final = 256


class FuenteFalsa:
    """Genera cuadros sintéticos deterministas a la frecuencia pedida.

    Args:
        hz: Cuadros por segundo que produce el hilo.
        ancho: Ancho del cuadro en píxeles.
        alto: Alto del cuadro en píxeles.
        cuadros: Cuántos cuadros produce antes de terminar. `None` = sin límite.
        nombre: Nombre con que se identifica en el volcado de métricas.
    """

    def __init__(
        self,
        hz: float = HZ_POR_DEFECTO,
        ancho: int = ANCHO_POR_DEFECTO,
        alto: int = ALTO_POR_DEFECTO,
        cuadros: int | None = None,
        nombre: str = "falsa",
    ) -> None:
        if hz <= 0:
            raise ValueError(
                f"La frecuencia de la fuente falsa tiene que ser mayor que cero y se "
                f"pidió {hz}."
            )
        self.nombre = nombre
        self._hz = hz
        self._ancho = ancho
        self._alto = alto
        self._cuadros = cuadros
        self._slot = SlotUltimoValor()
        self._metricas = MetricasDeFuente(self._slot)
        self._fin = threading.Event()
        self._hilo: threading.Thread | None = None
        self._viva = False

    # ------------------------------------------------------------ generación #

    @staticmethod
    def cuadro_de(
        secuencia: int, ancho: int = ANCHO_POR_DEFECTO, alto: int = ALTO_POR_DEFECTO
    ) -> np.ndarray:
        """El cuadro que corresponde a un número de secuencia. Siempre el mismo.

        El número se codifica en los tres canales en base 256, así que dos cuadros son
        distintos durante 16 777 216 secuencias consecutivas —unos siete días a 25 fps—.
        Además lleva una barra vertical que se desplaza, para que en el modo demostración
        se vea movimiento y no un color plano.
        """
        cuadro = np.zeros((alto, ancho, 3), dtype=np.uint8)
        cuadro[:, :, 0] = secuencia % BASE
        cuadro[:, :, 1] = (secuencia // BASE) % BASE
        cuadro[:, :, 2] = (secuencia // (BASE * BASE)) % BASE
        cuadro[:, secuencia % ancho, :] = 255
        return cuadro

    def _producir(self) -> None:
        """Publica cuadros a la frecuencia pedida hasta agotarlos o hasta que se cierre.

        Un hilo por fuente y aislado: si esto levantara, la excepción muere acá y la fuente
        pasa a no viva. Nunca puede tumbar a otra fuente ni al proceso.
        """
        periodo_ns = int(1_000_000_000 / self._hz)
        secuencia = 0
        try:
            arranque_ns = time.perf_counter_ns()
            while not self._fin.is_set():
                if self._cuadros is not None and secuencia >= self._cuadros:
                    break
                self._metricas.publicar(
                    FrameSellado(
                        datos=self.cuadro_de(secuencia, self._ancho, self._alto),
                        instante_captura_ns=time.perf_counter_ns(),
                        secuencia=secuencia,
                    )
                )
                secuencia += 1
                objetivo_ns = arranque_ns + secuencia * periodo_ns
                espera_s = (objetivo_ns - time.perf_counter_ns()) / 1_000_000_000
                if espera_s > 0:
                    self._fin.wait(espera_s)
        finally:
            self._viva = False

    # ---------------------------------------------------------------- puerto #

    def abrir(self) -> None:
        """Arranca el hilo generador. Idempotente."""
        if self._hilo is not None:
            return
        self._fin.clear()
        self._viva = True
        self._hilo = threading.Thread(
            target=self._producir, name=f"fuente-falsa-{self.nombre}", daemon=True
        )
        self._hilo.start()

    def cerrar(self) -> None:
        """Detiene el hilo. Idempotente: cerrar dos veces no falla."""
        self._fin.set()
        self._viva = False
        if self._hilo is not None:
            self._hilo.join(timeout=5.0)
            self._hilo = None

    def tomar_mas_reciente(
        self, perfil: PerfilDeFlujo, timeout: float | None = None
    ) -> FrameSellado | None:
        """Devuelve el cuadro más reciente.

        En esta fase el **perfil** no cambia el flujo: monitoreo y evidencia reciben el
        mismo cuadro, exactamente como la fuente de archivo. El parámetro se recibe desde
        el día uno para que la Fase 2 pueda devolver el sub-stream liviano al visor y el
        main-stream a la captura sin tocar a ningún llamador (D-15).
        """
        del perfil  # D-15: mismo flujo para los dos perfiles en la Fase 1.
        return self._metricas.tomar(timeout)

    def metricas(self) -> Mapping[str, object]:
        """El volcado en memoria de esta fuente (D-17)."""
        return self._metricas.como_diccionario()

    def esta_viva(self) -> bool:
        """`False` antes de abrir, después de cerrar y al agotar los cuadros pedidos."""
        return self._viva
