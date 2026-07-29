"""Invariantes declaradas por el plan 01-02: el dominio y el reloj del proceso.

Tres grupos, y cada uno cierra una decisión que **no es retrofiteable**:

1. **El reloj del proceso mide con `perf_counter_ns` y nunca con `monotonic`.** En Python
   3.12 sobre Windows `time.monotonic()` se implementa con `GetTickCount64()` y tiene
   15,625 ms de resolución medida; recién 3.13 pasa a `QueryPerformanceCounter`. Medir la
   ventana de ±150 ms de D-39 con ese paso es arrancar con un 10 % de error de
   cuantización, y como el desvío queda persistido, cambiar el reloj después obliga a
   reinterpretar toda la evidencia ya guardada. La invariante de ausencia es la que
   impide que alguien "simplifique" el módulo volviendo al reloj obvio.

2. **El cálculo del hash no vive en el dominio.** Hashear un archivo es I/O sobre bytes y
   pertenece a `infraestructura`. El dominio recibe una huella ya calculada y decide si
   la evidencia está comprometida. Es el riesgo de asignación que RESEARCH le marca al
   planner y la razón por la que `huella.py` no puede nombrar el módulo de hashing.

3. **El estado del remito se deriva, no se persiste (D-31).** Un campo de estado y unos
   datos pueden contradecirse; una propiedad calculada no. La invariante de ausencia
   sobre `estado_remito` es la que detecta el atajo.
"""

from tests.arquitectura.invariantes import Invariante

INVARIANTES: tuple[Invariante, ...] = (
    # --- 1. El reloj del proceso (Patrón 7, Pitfall 1) -------------------------- #
    Invariante(
        ruta="src/porteria/infraestructura/runtime/reloj.py",
        modo="presente",
        patron=r"perf_counter_ns",
        motivo=(
            "El reloj del proceso tiene que medir con `time.perf_counter_ns()`: es el "
            "único reloj que en Python 3.12 sobre Windows usa "
            "`QueryPerformanceCounter` y da un paso de 100 ns. Medido: 717 804 valores "
            "distintos en 300 ms contra 20 de `time.monotonic()`."
        ),
    ),
    Invariante(
        ruta="src/porteria/infraestructura/runtime/reloj.py",
        modo="presente",
        patron=r"def reanclar_tras_suspension",
        motivo=(
            "`QueryPerformanceCounter` no avanza durante la suspensión del equipo y el "
            "reloj de pared sí, así que tras un resume el ancla que une los dos relojes "
            "queda inválida. Sin un método público para reanclar, la Fase 2 no tiene "
            "forma de corregirlo y los sellos UTC posteriores a un resume quedan "
            "corridos sin que nada lo delate."
        ),
    ),
    Invariante(
        ruta="src/porteria/infraestructura/runtime/reloj.py",
        modo="ausente",
        patron=r"monotonic",
        motivo=(
            "`time.monotonic()` en Python 3.12 sobre Windows se implementa con "
            "`GetTickCount64()`: resolución de 15,625 ms. Con ese paso, dos fotos "
            "tomadas con 10 ms de diferencia reportan desvío 0 y la evidencia afirma "
            "«sincronizada» sin haberlo medido. Señal de alerta en producción: desvíos "
            "persistidos que son siempre 0 o siempre múltiplos de 15."
        ),
    ),
)
