"""Criterio de Éxito 5: la antigüedad del cuadro no crece con el tiempo de operación.

**Lo que se mide es la pendiente, no un valor.** Un máximo alto puede ser un pico legítimo
—una ráfaga de disco, el antivirus del puesto—; una pendiente positiva sostenida es el
fallo. Con una cola ilimitada se midieron **+806,6 ms por cada segundo** de operación
hasta 16 s de atraso; con el slot de capacidad 1 la antigüedad **baja**, de 25,8 a 13,9 ms
de mediana.

**Los tres criterios se afirman a la vez** y ninguno alcanza solo:

1. `pendiente(antigüedad ~ t) < 5 ms/s`. El umbral tiene dos órdenes de magnitud de margen
   contra los 806 ms/s del antipatrón, así que no es frágil ante variaciones de máquina.
2. `mediana(2.ª mitad) <= mediana(1.ª mitad) × 1,5`. Existe porque la pendiente sola podría
   promediar un tramo bueno con uno malo.
3. `frames_descartados > 0`. Existe porque si nada se descarta con un consumidor más lento
   que la fuente, la latencia se está acumulando en otro lado — es la métrica que delata
   el problema (Pitfall 7).

**Dos pruebas del mismo comportamiento, y no es duplicación** (D-53). `test_frescura_acotada`
corre 60 s, no lleva marcador y **bloquea la fusión**: la investigación verificó que 20 s ya
separan las dos arquitecturas por un factor de 800, así que 60 dan margen de sobra.
`test_frescura_sostenida_diez_minutos` corre 600 s, va marcada `lenta` y satisface el
criterio literal del roadmap en la tanda programada. Una compuerta lenta es una compuerta
que se termina salteando.

**No se falsifica el tiempo en ninguna de las dos.** El fenómeno que se mide *es* la
acumulación de buffers reales en el decodificador de FFmpeg: con el tiempo falsificado el
fenómeno desaparece y la prueba pasa siempre sin verificar nada. La aceleración legítima es
acortar la ventana, no mentir sobre el reloj. Hay una invariante de código que lo sostiene.

La evaluación de los tres criterios vive en `evaluar_frescura` y no dentro de cada prueba,
para que las dos pruebas de la prueba de `test_frescura_anti_vacuidad.py` puedan invocarla
sobre datos del antipatrón y exigir que **falle**. Si cada prueba reimplementara el juicio,
las anti-vacuidad no demostrarían nada sobre este juicio.
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

from porteria.aplicacion.puertos.salida.fuente_de_video import PerfilDeFlujo
from porteria.infraestructura.runtime.reloj import RelojDelProceso
from porteria.infraestructura.video.archivo import FuenteDeArchivo, Modo
from porteria.infraestructura.video.slot_ultimo_valor import PuntoDeEncuentro

#: Criterio 1. Dos órdenes de magnitud de margen contra los 806 ms/s del antipatrón.
UMBRAL_PENDIENTE_MS_POR_S = 5.0

#: Criterio 2. La mediana de la segunda mitad no puede ser 1,5 veces la de la primera.
FACTOR_ENTRE_MEDIANAS = 1.5

#: Frecuencia del consumidor. Más lenta que cualquier fuente a propósito: con un consumidor
#: rápido no habría descartes y el criterio 3 no podría distinguir nada.
HZ_DEL_CONSUMIDOR = 5.0

#: Piso de muestras para que la regresión signifique algo. A 5 Hz, 20 muestras son 4 s.
#: Evaluar una pendiente sobre menos que eso es leer ruido y llamarlo medición.
MINIMO_DE_MUESTRAS = 20

SEGUNDOS_COMPUERTA = 60.0
SEGUNDOS_TANDA_PROGRAMADA = 600.0

NS_POR_S = 1_000_000_000


@dataclass(frozen=True, slots=True)
class Muestra:
    """Una entrega: cuándo ocurrió desde el arranque, y qué antigüedad traía el cuadro."""

    segundo: float
    antiguedad_ms: float


@dataclass(frozen=True)
class ResultadoDeFrescura:
    """El juicio sobre una corrida, con los números que lo justifican.

    Guarda los tres valores medidos y no sólo el veredicto: quien lea el fallo en la salida
    de integración continua tiene que poder saber **cuál** de los tres criterios cayó y por
    cuánto, sin volver a correr nada.
    """

    pendiente_ms_por_s: float
    mediana_primera_mitad_ms: float
    mediana_segunda_mitad_ms: float
    frames_descartados: int
    muestras: int

    @property
    def cumple_pendiente(self) -> bool:
        return self.pendiente_ms_por_s < UMBRAL_PENDIENTE_MS_POR_S

    @property
    def cumple_medianas(self) -> bool:
        return self.mediana_segunda_mitad_ms <= (
            self.mediana_primera_mitad_ms * FACTOR_ENTRE_MEDIANAS
        )

    @property
    def cumple_descartes(self) -> bool:
        return self.frames_descartados > 0

    @property
    def aprueba(self) -> bool:
        """Los tres criterios a la vez. Ninguno alcanza solo."""
        return self.cumple_pendiente and self.cumple_medianas and self.cumple_descartes

    def mensaje(self) -> str:
        """El informe en español, con el detalle de cada criterio y su umbral."""
        def marca(cumple: bool) -> str:
            return "CUMPLE" if cumple else "FALLA "

        return (
            f"Frescura sobre {self.muestras} entregas:\n"
            f"  [{marca(self.cumple_pendiente)}] Criterio 1 · pendiente medida "
            f"{self.pendiente_ms_por_s:+.3f} ms/s (umbral < "
            f"{UMBRAL_PENDIENTE_MS_POR_S} ms/s)\n"
            f"  [{marca(self.cumple_medianas)}] Criterio 2 · mediana 1.ª mitad "
            f"{self.mediana_primera_mitad_ms:.1f} ms · 2.ª mitad "
            f"{self.mediana_segunda_mitad_ms:.1f} ms (tope "
            f"{self.mediana_primera_mitad_ms * FACTOR_ENTRE_MEDIANAS:.1f} ms)\n"
            f"  [{marca(self.cumple_descartes)}] Criterio 3 · frames descartados "
            f"{self.frames_descartados} (tiene que ser > 0 con consumidor lento)"
        )


def evaluar_frescura(
    muestras: list[Muestra], frames_descartados: int
) -> ResultadoDeFrescura:
    """Aplica los tres criterios a una corrida. Es el único juicio de este archivo.

    Raises:
        ValueError: si hay menos de `MINIMO_DE_MUESTRAS`. Una regresión sobre cuatro
            puntos no distingue una tendencia de un par de picos, y devolver "aprueba"
            sobre esos datos sería la peor forma de pasar en verde: sin haber medido.
    """
    if len(muestras) < MINIMO_DE_MUESTRAS:
        raise ValueError(
            f"Se recolectaron {len(muestras)} muestras y hacen falta al menos "
            f"{MINIMO_DE_MUESTRAS} para que la pendiente signifique algo. Qué revisar: "
            "que la fuente esté entregando cuadros y que la ventana de medición no sea "
            "demasiado corta."
        )

    segundos = [muestra.segundo for muestra in muestras]
    antiguedades = [muestra.antiguedad_ms for muestra in muestras]
    mitad = len(muestras) // 2

    return ResultadoDeFrescura(
        pendiente_ms_por_s=statistics.linear_regression(segundos, antiguedades).slope,
        mediana_primera_mitad_ms=statistics.median(antiguedades[:mitad]),
        mediana_segunda_mitad_ms=statistics.median(antiguedades[mitad:]),
        frames_descartados=frames_descartados,
        muestras=len(muestras),
    )


def medir_frescura(
    ruta_del_video: Path,
    segundos: float,
    destino: PuntoDeEncuentro | None = None,
) -> tuple[list[Muestra], int]:
    """Reproduce el video en tiempo real con un consumidor a 5 Hz y registra las entregas.

    El eje de tiempos sale de `RelojDelProceso`, que es el reloj del producto: medir la
    frescura con un cronómetro distinto del que sella los cuadros sería comparar dos
    escalas y llamar antigüedad a la diferencia entre relojes.

    `destino` existe para que la prueba de la prueba pueda montar el antipatrón. En las
    dos pruebas de este archivo va en `None`, es decir el slot del contrato.
    """
    reloj = RelojDelProceso()
    fuente = FuenteDeArchivo(
        ruta_del_video, modo=Modo.TIEMPO_REAL, repetir=True, destino=destino
    )
    periodo_s = 1.0 / HZ_DEL_CONSUMIDOR
    muestras: list[Muestra] = []

    fuente.abrir()
    try:
        inicio_ns = reloj.instante()
        limite_ns = inicio_ns + int(segundos * NS_POR_S)
        while reloj.instante() < limite_ns:
            cuadro = fuente.tomar_mas_reciente(PerfilDeFlujo.MONITOREO, timeout=periodo_s)
            if cuadro is not None:
                antiguedad = fuente.metricas()["antiguedad_ultimo_ms"]
                muestras.append(
                    Muestra(
                        segundo=(reloj.instante() - inicio_ns) / NS_POR_S,
                        antiguedad_ms=float(antiguedad),  # type: ignore[arg-type]
                    )
                )
            time.sleep(periodo_s)
        descartados = int(fuente.metricas()["frames_descartados"])  # type: ignore[call-overload]
    finally:
        fuente.cerrar()

    return muestras, descartados


def test_frescura_acotada(video_sintetico: Path) -> None:
    """Sesenta segundos, sin marcador: **esta prueba bloquea la fusión**.

    Es la versión corta del Criterio de Éxito 5. La de diez minutos satisface el criterio
    literal del roadmap pero vive en la tanda programada, porque una compuerta que tarda
    diez minutos es una compuerta que alguien va a saltear (D-53).
    """
    muestras, descartados = medir_frescura(video_sintetico, SEGUNDOS_COMPUERTA)
    resultado = evaluar_frescura(muestras, descartados)

    assert resultado.aprueba, (
        "La frescura del cuadro no se sostiene con un consumidor más lento que la "
        "fuente.\n" + resultado.mensaje()
    )


@pytest.mark.lenta
def test_frescura_sostenida_diez_minutos(video_sintetico: Path) -> None:
    """Diez minutos: el criterio literal del roadmap, en la tanda programada (D-53).

    Su falla abre un asunto y no traba la fusión. Es la misma medición que la de 60 s con
    la ventana estirada: el fenómeno no cambia, lo que cambia es cuánta evidencia se junta.
    """
    muestras, descartados = medir_frescura(video_sintetico, SEGUNDOS_TANDA_PROGRAMADA)
    resultado = evaluar_frescura(muestras, descartados)

    assert resultado.aprueba, (
        "La frescura del cuadro no se sostiene en diez minutos de operación continua.\n"
        + resultado.mensaje()
    )
