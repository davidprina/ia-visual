"""Pruebas de la prueba de CAP-04: que la evaluación de frescura falle cuando debe fallar.

Una prueba que sólo se ejercita contra el camino bueno no demuestra nada sobre sus propios
umbrales. Si alguien escribiera `UMBRAL_PENDIENTE_MS_POR_S = 100000`, `test_frescura_acotada`
seguiría en verde para siempre y el Criterio de Éxito 5 estaría reportado como cumplido sin
que nadie hubiera medido nada. Estas dos pruebas montan el fallo **a propósito** y exigen
que `evaluar_frescura` lo detecte.

**Las dos usan exactamente la misma función de evaluación que las pruebas reales.** Es la
razón por la que ese juicio se extrajo a `evaluar_frescura` en vez de escribirse dentro de
cada prueba: si acá se reimplementara el criterio, se estaría demostrando algo sobre una
copia y no sobre el código que efectivamente juzga la compuerta.

**El reparto de marcadores no es arbitrario.**
`test_cero_descartes_con_consumidor_lento_es_fallo` es instantáneo —inyecta datos, no
reproduce video— y queda **sin marcar** para proteger el criterio 3 en cada empujón.
`test_la_prueba_de_frescura_detecta_la_cola` necesita 20 segundos de reproducción real para
que la cola acumule, y su valor es **demostrativo**, no de regresión continua: va con
`lenta` a la tanda programada. D-53 es explícito en que una compuerta lenta es una
compuerta que se termina salteando, y el presupuesto de la suite rápida no soporta
60 s + 20 s + concurrencia + Argon2id.
"""

from __future__ import annotations

import threading
from collections import deque
from pathlib import Path

import pytest

from porteria.aplicacion.puertos.salida.fuente_de_video import FrameSellado
from tests.integracion.test_frescura import (
    Muestra,
    evaluar_frescura,
    medir_frescura,
)

#: Cuánto corre la demostración con la cola. Verificado: 20 s ya separan las dos
#: arquitecturas por un factor de 800.
SEGUNDOS_DE_LA_DEMOSTRACION = 20.0

#: Antigüedad de las muestras sintéticas del caso "cero descartes": plana y baja, para que
#: los criterios 1 y 2 **pasen** y el único que pueda hacer fallar la evaluación sea el 3.
ANTIGUEDAD_PLANA_MS = 20.0
MUESTRAS_SINTETICAS = 100


class ColaIlimitadaDeMentira:
    """El antipatrón, montado a propósito y viviendo **sólo** dentro de esta prueba.

    Hace las dos cosas que el contrato de frescura prohíbe: acumula sin techo y entrega el
    cuadro **más viejo**. Nunca descarta, así que su contador de descartes es un cero
    honesto — y ese cero es justamente la señal que el criterio 3 tiene que atrapar.

    No hereda de nada del producto ni se exporta: si esta clase apareciera en
    `src/porteria/`, sería el defecto en persona.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._nuevo = threading.Condition(self._lock)
        self._cola: deque[FrameSellado] = deque()
        self._publicados = 0
        self._consumidos = 0

    def publicar(self, frame: FrameSellado) -> None:
        with self._nuevo:
            self._cola.append(frame)
            self._publicados += 1
            self._nuevo.notify()

    def tomar(self, timeout: float | None = None) -> FrameSellado | None:
        with self._nuevo:
            if not self._cola:
                self._nuevo.wait(timeout)
            if not self._cola:
                return None
            self._consumidos += 1
            return self._cola.popleft()  # el MÁS VIEJO: acá nace el atraso

    @property
    def metricas(self) -> dict[str, int | bool]:
        with self._lock:
            return {
                "frames_publicados": self._publicados,
                "frames_descartados": 0,  # nunca descarta: acumula
                "frames_consumidos": self._consumidos,
                "ocupado": bool(self._cola),
            }


def test_cero_descartes_con_consumidor_lento_es_fallo() -> None:
    """El criterio 3, protegido en cada empujón: sin marcador porque es instantáneo.

    Las muestras que se inyectan tienen antigüedad **plana y baja**, así que los criterios
    1 y 2 pasan holgados. Lo único que puede hacer fallar la evaluación es el contador de
    descartes en cero, y eso es precisamente lo que se está verificando: que ese cero, con
    un consumidor más lento que la fuente, se lea como fallo y no como "no hubo nada que
    descartar".
    """
    muestras = [
        Muestra(segundo=numero * 0.2, antiguedad_ms=ANTIGUEDAD_PLANA_MS)
        for numero in range(MUESTRAS_SINTETICAS)
    ]

    con_descartes = evaluar_frescura(muestras, frames_descartados=137)
    sin_descartes = evaluar_frescura(muestras, frames_descartados=0)

    assert con_descartes.aprueba, (
        "Con los mismos datos y descartes > 0 la evaluación tendría que aprobar. Si no "
        "aprueba, el caso de abajo no demuestra nada sobre el criterio 3.\n"
        + con_descartes.mensaje()
    )
    assert not sin_descartes.aprueba, (
        "`frames_descartados == 0` con un consumidor más lento que la fuente pasó la "
        "evaluación. Ese cero no significa que todo esté bien: significa que nada se está "
        "descartando y que, por lo tanto, todo se está acumulando en otro lado "
        "(Pitfall 7).\n" + sin_descartes.mensaje()
    )
    assert sin_descartes.cumple_pendiente, "El caso tenía que fallar sólo por el criterio 3."
    assert sin_descartes.cumple_medianas, "El caso tenía que fallar sólo por el criterio 3."
    assert not sin_descartes.cumple_descartes


@pytest.mark.lenta
def test_la_prueba_de_frescura_detecta_la_cola(video_sintetico: Path) -> None:
    """Veinte segundos contra una cola ilimitada: la evaluación tiene que fallar.

    Es la demostración de que los umbrales de `evaluar_frescura` distinguen las dos
    arquitecturas sobre datos **reales** —vídeo real, hilos reales, buffers reales de
    FFmpeg— y no sólo sobre números inventados. Medido en la investigación con esta misma
    forma de antipatrón: la antigüedad mediana pasa de 4 152 ms en la primera mitad a
    12 218 ms en la segunda, con una pendiente de +806,6 ms/s y 406 cuadros de atraso al
    terminar.
    """
    muestras, descartados = medir_frescura(
        video_sintetico,
        SEGUNDOS_DE_LA_DEMOSTRACION,
        destino=ColaIlimitadaDeMentira(),
    )
    resultado = evaluar_frescura(muestras, descartados)

    assert not resultado.aprueba, (
        "La evaluación de frescura aprobó una cola ilimitada con un consumidor lento. "
        "Entonces no distingue las dos arquitecturas y `test_frescura_acotada` está "
        "pasando en verde sin verificar nada.\n" + resultado.mensaje()
    )
    assert resultado.frames_descartados == 0, (
        "El antipatrón no puede descartar: acumula. Si acá hay descartes, lo que se montó "
        "no es la cola ilimitada y la demostración no vale."
    )
    assert not resultado.cumple_pendiente, (
        "La cola no produjo pendiente positiva en 20 s. Revisá que el consumidor sea más "
        "lento que la fuente y que la cola entregue el cuadro más viejo.\n"
        + resultado.mensaje()
    )
