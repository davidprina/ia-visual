"""Invariantes declaradas por el plan 01-06: bitácora técnica y configuración en dos capas.

Dos grupos, y los dos cierran una decisión que no se sostiene con disciplina:

1. **La bitácora técnica y la bitácora de auditoría son dos módulos con dos destinos
   distintos, sin una línea de código compartida** (D-11, Pitfall 9, amenaza T-01-23). La
   invariante de ausencia sobre `runtime/bitacora.py` es la que hace estructural esa
   separación: mientras el módulo no pueda nombrar la auditoría, nadie puede agregarle un
   `es_auditoria=True` —la señal de alerta exacta del catálogo de pitfalls— por el que
   subir el nivel de detalle para depurar termine inundando la evidencia legal, o por el
   que rotar archivos borre parte de la cadena de custodia. Las dos invariantes de
   presencia fijan las dos propiedades que NUC-06 exige del archivo: que rote y que se
   abra en UTF-8.

2. **El valor por defecto de la ventana de aceptación está marcado como no validado en el
   código** (D-39). Un número que nadie midió y que el código presenta como si fuera un
   hecho es peor que no tener número: la marca vive donde se lee el valor, no sólo en un
   documento de planificación que nadie abre.

**Por qué son aserciones de pytest y no comandos de shell.** La plataforma de compuerta es
Windows únicamente (D-54) y el shell no garantiza `grep`. Éstas definen propiedades
estructurales del producto, y cuando el comando no existe «no se pudo verificar» se lee
como «pasó». Declaradas acá corren dentro del paso 1 de `scripts/compuerta.py` en
cualquier plataforma y quedan como regresión permanente.
"""

from tests.arquitectura.invariantes import Invariante

INVARIANTES: tuple[Invariante, ...] = (
    # --- 1. Dos bitácoras, dos destinos, cero código compartido (T-01-23) ------- #
    Invariante(
        ruta="src/porteria/infraestructura/runtime/bitacora.py",
        modo="ausente",
        patron=r"auditor[ií]a",
        ignorar_mayusculas=True,
        motivo=(
            "La bitácora técnica va a archivos rotativos, es borrable sin consecuencias y "
            "su nivel se sube para depurar; el registro encadenado por hash vive en la "
            "base, sólo agrega y sostiene la cadena de custodia. Que este módulo no pueda "
            "nombrar al otro es lo que hace imposible el antipatrón de un solo `logger` "
            "con un parámetro `es_auditoria=True`. Qué revisar: si necesitás registrar un "
            "hecho auditable, va por la vía del dominio a la tabla encadenada, no por acá."
        ),
    ),
    Invariante(
        ruta="src/porteria/infraestructura/runtime/bitacora.py",
        modo="presente",
        patron=r"RotatingFileHandler",
        motivo=(
            "NUC-06 exige rotación automática, y T-01-24 la convierte en un control de "
            "seguridad: sin techo de tamaño, la bitácora técnica puede llenar el disco "
            "donde vive la evidencia y dejar al sistema sin poder registrar capturas. "
            "`structlog` se apoya en el `logging` de la stdlib justamente para que la "
            "rotación la dé `logging.handlers.RotatingFileHandler` sin dependencia extra."
        ),
    ),
    Invariante(
        ruta="src/porteria/infraestructura/runtime/bitacora.py",
        modo="presente",
        patron=r'encoding="utf-8"',
        motivo=(
            "La codificación por defecto de Windows es cp1252 (Pitfall 8) y una bitácora "
            "en español con eñes y tildes se corrompe o revienta con "
            "`UnicodeEncodeError`. El archivo se abre en UTF-8 explícito, por la misma "
            "razón por la que el punto de entrada de la consola hace `reconfigure`."
        ),
    ),
    # --- 2. La ventana por defecto se declara no validada, en el código (D-39) -- #
    Invariante(
        ruta="src/porteria/infraestructura/configuracion/en_base.py",
        modo="presente",
        patron=r"150",
        motivo=(
            "D-39 fija ±150 ms como valor por defecto de la ventana de aceptación. Si el "
            "número desaparece del catálogo, el composition root del plan 01-07 se queda "
            "sin qué inyectar y cada captura pasaría a evaluarse contra un criterio "
            "distinto del que la fase declaró."
        ),
    ),
    Invariante(
        ruta="src/porteria/infraestructura/configuracion/en_base.py",
        modo="presente",
        patron=r"no validado",
        motivo=(
            "D-39 exige que el valor por defecto de la ventana esté marcado como **no "
            "validado** con el cliente ni medido en campo, y esa marca vive donde se lee "
            "el valor, no sólo en un documento de planificación. Un número que nadie "
            "midió y que el código presenta como si fuera un hecho es peor que no tener "
            "número: nadie lo vuelve a mirar. Qué revisar: la ayuda de la clave "
            "`ventana_aceptacion_ms` en el catálogo."
        ),
    ),
)
