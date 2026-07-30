"""Métricas por fuente, en memoria y sin una sola escritura en el camino crítico (D-17).

**La definición operativa de antigüedad, que se fija acá porque es lo que después se
persiste y se reporta:**

> `antiguedad_ms = (instante_de_entrega − instante_de_captura) / 1e6`
>
> donde `instante_de_captura` es el `perf_counter_ns()` tomado inmediatamente después de
> que el decodificador devuelve el cuadro, e `instante_de_entrega` es el
> `perf_counter_ns()` del momento en que el consumidor lo recibe.

**No es el PTS del contenedor.** El PTS mide tiempo de reproducción, no tiempo real
transcurrido: con un consumidor lento seguiría avanzando prolijo mientras la antigüedad
real crece sin techo. Medir con el PTS es tener un instrumento que no puede detectar el
único fallo que importa.

**Por qué este objeto envuelve el punto de encuentro en vez de recibir avisos.** Si la
fuente tuviera que llamar a `slot.publicar(...)` y además a `metricas.registrar(...)`,
alcanzaría con que un camino olvidara el segundo aviso para que las métricas mintieran —y
mentirían hacia abajo, mostrando todo sano. Envolviendo el punto de encuentro hay un solo
lugar por donde pasan los cuadros y las métricas no pueden divergir de los hechos.

**Los contadores no se duplican.** `frames_descartados` y `frames_publicados` se leen del
punto de encuentro, que es donde ocurre el descarte. Acá se agrega sólo lo que se **deriva**
de los cuadros: la antigüedad, su mediana y los fps efectivos.

**El límite aceptado (T-01-16).** Estas métricas viven en memoria y se pierden al cerrar el
proceso. El muestreo periódico a la base para diagnóstico retrospectivo está diferido
fuera de v1 a propósito: escribir en el camino crítico de la captura es peor que no tener
el histórico.
"""

from __future__ import annotations

import statistics
import threading
import time
from collections import deque
from typing import Final

from porteria.aplicacion.puertos.salida.fuente_de_video import FrameSellado
from porteria.infraestructura.video.slot_ultimo_valor import PuntoDeEncuentro

__all__ = [
    "CLAVES_DE_METRICAS",
    "MetricasDeFuente",
    "RegistroDeMetricas",
]

#: Cuántos cuadros recientes entran en la ventana deslizante. Acotada a propósito: un
#: acumulador que crece con el tiempo de ejecución es una fuga de memoria en un puesto que
#: corre todo el turno. 120 cuadros son ~5 s a 25 fps, suficiente para que los fps
#: efectivos y la mediana de antigüedad reaccionen rápido sin promediar el turno entero.
VENTANA_POR_DEFECTO: Final = 120

NS_POR_MS: Final = 1_000_000
NS_POR_S: Final = 1_000_000_000

#: Las claves del volcado, declaradas en un solo lugar. La orden `porteria metricas`, el
#: panel de estado de la Fase 2 y las pruebas leen de acá y no de una lista propia.
CLAVES_DE_METRICAS: Final = (
    "frames_publicados",
    "frames_descartados",
    "frames_consumidos",
    "ocupado",
    "antiguedad_ultimo_ms",
    "antiguedad_mediana_ms",
    "fps_efectivos",
    "reconexiones",
)

#: Claves que salen del punto de encuentro, con su valor por defecto si no las informa.
_CONTADORES: Final = {
    "frames_publicados": 0,
    "frames_descartados": 0,
    "frames_consumidos": 0,
    "ocupado": False,
}


class MetricasDeFuente:
    """Acumulador en memoria que envuelve el punto de encuentro y lo mide al pasar.

    Cumple `PuntoDeEncuentro`, así que la fuente publica y consume a través de él sin
    saber que está siendo medida.
    """

    def __init__(
        self, punto: PuntoDeEncuentro, ventana: int = VENTANA_POR_DEFECTO
    ) -> None:
        if ventana < 2:
            raise ValueError(
                f"La ventana de métricas tiene que ser de al menos 2 cuadros y se pidió "
                f"{ventana}: con un solo cuadro no hay intervalo del que derivar los fps "
                "efectivos."
            )
        self._punto = punto
        self._lock = threading.Lock()
        self._capturas_ns: deque[int] = deque(maxlen=ventana)
        self._antiguedades_ms: deque[float] = deque(maxlen=ventana)
        self._antiguedad_ultimo_ms: float | None = None
        self._reconexiones = 0

    # ------------------------------------------------- punto de encuentro medido #

    def publicar(self, frame: FrameSellado) -> None:
        """Publica el cuadro y anota su instante de captura para los fps efectivos."""
        self._punto.publicar(frame)
        with self._lock:
            self._capturas_ns.append(frame.instante_captura_ns)

    def tomar(self, timeout: float | None = None) -> FrameSellado | None:
        """Toma el cuadro más reciente y mide su antigüedad al entregarlo."""
        frame = self._punto.tomar(timeout)
        if frame is None:
            return None

        antiguedad_ms = (time.perf_counter_ns() - frame.instante_captura_ns) / NS_POR_MS
        with self._lock:
            self._antiguedad_ultimo_ms = antiguedad_ms
            self._antiguedades_ms.append(antiguedad_ms)
        return frame

    @property
    def metricas(self) -> dict[str, int | bool]:
        """Los contadores del punto de encuentro, tal como él los cuenta."""
        return self._punto.metricas

    # ------------------------------------------------------------------ derivados #

    def registrar_reconexion(self) -> None:
        """Suma una reconexión.

        En esta fase queda en 0: la fuente de archivo no reconecta, porque fin de archivo
        es un estado normal y no una caída. La Fase 2 lo puebla con el backoff exponencial
        de las cámaras IP, y el hueco existe desde hoy para que el volcado de métricas no
        cambie de forma cuando llegue.
        """
        with self._lock:
            self._reconexiones += 1

    def tamano_de_la_ventana(self) -> int:
        """Cuántas muestras hay guardadas. Es el techo de memoria, y se puede afirmar."""
        with self._lock:
            return max(len(self._capturas_ns), len(self._antiguedades_ms))

    def _fps_efectivos(self) -> float:
        """Cuadros por segundo derivados de los **sellos de captura** de la ventana.

        Se derivan del dato y no del reloj de quien pregunta: así el número es el mismo en
        cualquier equipo y una prueba puede afirmarlo con exactitud en vez de con una
        tolerancia amplia.
        """
        if len(self._capturas_ns) < 2:
            return 0.0
        transcurrido_ns = self._capturas_ns[-1] - self._capturas_ns[0]
        if transcurrido_ns <= 0:
            return 0.0
        return (len(self._capturas_ns) - 1) * NS_POR_S / transcurrido_ns

    def como_diccionario(self) -> dict[str, object]:
        """El volcado con las claves de `CLAVES_DE_METRICAS`, siempre las mismas.

        Los contadores se leen del punto de encuentro con un valor por defecto explícito:
        así el volcado tiene la misma forma aunque el punto de encuentro sea un doble de
        prueba que no informe alguno, y quien lo consuma no tiene que preguntarse si una
        clave ausente significa cero o significa que no se midió.
        """
        contadores = dict(self._punto.metricas)
        with self._lock:
            volcado: dict[str, object] = {
                clave: contadores.get(clave, defecto)
                for clave, defecto in _CONTADORES.items()
            }
            volcado["antiguedad_ultimo_ms"] = self._antiguedad_ultimo_ms
            volcado["antiguedad_mediana_ms"] = (
                statistics.median(self._antiguedades_ms) if self._antiguedades_ms else None
            )
            volcado["fps_efectivos"] = self._fps_efectivos()
            volcado["reconexiones"] = self._reconexiones
        return volcado


class RegistroDeMetricas:
    """Las fuentes vivas de **este** proceso, para que la consola pueda volcarlas.

    Es deliberadamente un registro en memoria y de proceso: `porteria metricas` en una
    consola nueva no ve las fuentes de otro proceso, y lo dice en vez de mostrar un cero
    que se leería como "todo bien". Un registro que mintiera hacia abajo sería peor que no
    tener la orden.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._fuentes: dict[str, MetricasDeFuente] = {}

    def registrar(self, nombre: str, metricas: MetricasDeFuente) -> None:
        """Anota una fuente viva bajo su nombre."""
        with self._lock:
            self._fuentes[nombre] = metricas

    def olvidar(self, nombre: str) -> None:
        """Saca una fuente del registro al cerrarla. No falla si ya no estaba."""
        with self._lock:
            self._fuentes.pop(nombre, None)

    def instantanea(self) -> dict[str, dict[str, object]]:
        """El volcado de todas las fuentes registradas, en el momento de preguntar."""
        with self._lock:
            fuentes = dict(self._fuentes)
        return {nombre: metricas.como_diccionario() for nombre, metricas in fuentes.items()}


#: El registro del proceso. Es estado global a propósito y con alcance acotado: la orden
#: `porteria metricas` no recibe la fuente por parámetro —no la tiene—, así que necesita un
#: lugar convenido donde mirar. Las pruebas construyen su propio `RegistroDeMetricas` y no
#: tocan éste, para no depender del orden de ejecución.
REGISTRO_DEL_PROCESO: Final = RegistroDeMetricas()
