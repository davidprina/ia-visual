"""Invariantes declaradas por el plan 01-04: el almacén de evidencia y la cuarentena.

Dos grupos, y los dos cierran propiedades que ninguna prueba funcional puede sostener sola,
porque describen **cómo** está escrito el código y no sólo qué devuelve.

1. **La escritura de evidencia habla el idioma de Windows, no el de POSIX.** Las cuatro
   invariantes sobre `evidencia_fs.py` fijan el patrón medido en la plataforma de destino:
   temporal con `mkstemp` en el mismo directorio, `os.replace` y jamás `os.rename` —que
   sobre un archivo existente lanza `FileExistsError(17)`, o sea justo en el único caso que
   importa: reescribir evidencia con el mismo hash—, y el `fsync` del directorio padre
   **guardado tras `if os.name != "nt"`** en vez de silenciado con un `except`. Reproducido
   en esta máquina: `os.fsync` sobre un descriptor de directorio lanza
   `PermissionError(13)`. Una prueba funcional no distingue «el paso está guardado» de «el
   paso está envuelto en un `try/except OSError: pass`»: las dos pasan en verde en Windows,
   y la segunda deja de sincronizar en Linux sin que nadie se entere.

2. **El barrido de huérfanos mueve; nunca elimina.** Un archivo sin fila puede ser
   justamente la foto del camión del corte de luz (D-13). La invariante de ausencia sobre
   el módulo de cuarentena es lo que impide que alguien «limpie» la carpeta con un borrado
   directo el día que la cuarentena crezca. Es la mitigación verificable de T-01-18.

**Por qué son aserciones de pytest y no comandos de shell.** La plataforma de compuerta es
Windows únicamente (D-54) y el shell no garantiza `grep`. Varias de estas invariantes
definen propiedades de seguridad, y cuando el comando no existe «no se pudo verificar» se
lee como «pasó».

La prohibición de la dependencia `atomicwrites` en `pyproject.toml` ya la declara el plan
01-01 y no se duplica acá.
"""

from tests.arquitectura.invariantes import Invariante

INVARIANTES: tuple[Invariante, ...] = (
    # --- 1. La escritura atómica en el idioma de Windows (Patrón 2, Pitfalls 2 y 6) --- #
    Invariante(
        ruta="src/porteria/infraestructura/persistencia/evidencia_fs.py",
        modo="presente",
        patron=r"os\.replace",
        motivo=(
            "El renombrado final tiene que ser `os.replace`. Es la única forma de que "
            "escribir evidencia que ya existe con el mismo hash —el camino feliz del "
            "reintento— no falle en Windows. Medido en esta máquina: `os.replace` sobre un "
            "archivo existente deja el destino con el contenido nuevo; `os.rename` lanza "
            "FileExistsError(17)."
        ),
    ),
    Invariante(
        ruta="src/porteria/infraestructura/persistencia/evidencia_fs.py",
        modo="presente",
        patron=r"mkstemp",
        motivo=(
            "El temporal se crea con `tempfile.mkstemp` **en el mismo directorio de "
            "destino**: `os.replace` sólo puede ser atómico dentro del mismo volumen. Un "
            "temporal en la carpeta temporal del sistema —que suele estar en otra unidad— "
            "convierte el renombrado en una copia, y una copia interrumpida deja medio "
            "archivo en la ruta final. Escribir directo sobre el destino es peor todavía: "
            "un corte deja la evidencia truncada y con la huella ya persistida."
        ),
    ),
    Invariante(
        ruta="src/porteria/infraestructura/persistencia/evidencia_fs.py",
        modo="ausente",
        patron=r"os\.rename",
        motivo=(
            "`os.rename` sobre un archivo que ya existe lanza `FileExistsError(17)` en "
            "Windows —verificado, WinError 183— y tiene éxito en POSIX. O sea: el código "
            "pasa todas las pruebas en la máquina del desarrollador si es Linux y revienta "
            "en la portería el día que dos capturas dan bytes idénticos. Señal de alerta "
            "en producción: fallos de guardado que sólo aparecen con la cámara quieta."
        ),
    ),
    Invariante(
        ruta="src/porteria/infraestructura/persistencia/evidencia_fs.py",
        modo="presente",
        patron=r'if os\.name != "nt"',
        motivo=(
            "El `fsync` del directorio padre es el idioma POSIX de la escritura durable y "
            "en Windows es imposible: sobre un descriptor de directorio lanza "
            "`PermissionError(13)`, reproducido en esta máquina. El paso va **guardado** "
            "por plataforma, no borrado: el día que la aplicación corra sobre Linux ese "
            "`fsync` sí hace falta, y sin la guardia explícita nadie sabría si se ejecuta."
        ),
    ),
    Invariante(
        ruta="src/porteria/infraestructura/persistencia/evidencia_fs.py",
        modo="ausente",
        patron=r"except\s+(OSError|Exception|BaseException)[^\n]*:\s*(?:\r?\n\s*)+pass",
        motivo=(
            "Silenciar el `fsync` de directorio con un `except`/`pass` oculta el problema "
            "en vez de documentarlo (Pitfall 2), y de paso se traga cualquier otro error "
            "de entrada/salida que caiga en el mismo bloque: un disco lleno pasaría por "
            "escritura exitosa. La limpieza del temporal no coincide con este patrón "
            "porque **re-lanza**, que es exactamente la diferencia entre atender un error "
            "y taparlo."
        ),
    ),
)
