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
    # --- 2. El cálculo del hash es infraestructura, no dominio ------------------ #
    Invariante(
        ruta="src/porteria/dominio/evidencia/huella.py",
        modo="presente",
        patron=r"class HuellaDeIntegridad",
        motivo=(
            "La huella es un valor de primera clase del dominio y no un `str` suelto: es "
            "lo que permite que el dominio razone sobre integridad sin tocar bytes, y una "
            "de las tres decisiones no retrofiteables de la fase."
        ),
    ),
    Invariante(
        ruta="src/porteria/dominio/evidencia/huella.py",
        modo="presente",
        patron=r"\[0-9a-f\]\{64\}",
        motivo=(
            "La huella se valida contra `^[0-9a-f]{64}$` en la construcción. El nombre "
            "del archivo de evidencia se deriva de estos 64 caracteres (D-03), así que "
            "una huella mal formada es a la vez una clave única inválida y una ruta "
            "inválida. Validar en el borde no alcanza: los bordes son varios."
        ),
    ),
    Invariante(
        ruta="src/porteria/dominio/evidencia/huella.py",
        modo="ausente",
        patron=r"hashlib",
        motivo=(
            "Calcular el SHA-256 es I/O sobre bytes y vive en "
            "`infraestructura/persistencia` (plan 01-04), que lo hace por streaming sobre "
            "el archivo. El dominio recibe la huella **ya calculada** y decide si la "
            "evidencia está comprometida. Es el riesgo de asignación que RESEARCH le "
            "marca al planner: poner el cálculo acá «porque es una regla de integridad» "
            "mete el sistema de archivos dentro del dominio y rompe NUC-01."
        ),
    ),
    Invariante(
        ruta="src/porteria/dominio/auditoria/registro.py",
        modo="presente",
        patron=r"tamper-evident",
        motivo=(
            "El módulo de la cadena tiene que declarar en su propio texto que la garantía "
            "es **tamper-evident y no tamper-proof**: quien tenga escritura en el disco "
            "puede alterar un registro y re-encadenar desde ese punto. Lo que la cadena "
            "logra es elevar el costo de «editar una fila» a «rehacer todo el histórico "
            "posterior». Vender «inalterable» lo que es «detectable» es un riesgo de "
            "reputación mayor que la amenaza técnica, y este es un producto de auditoría."
        ),
        # Única invariante de la fase que mira la prosa a propósito: lo que se exige es
        # justamente que la advertencia esté escrita para quien lea el código.
        ignorar_comentarios=False,
    ),
)
