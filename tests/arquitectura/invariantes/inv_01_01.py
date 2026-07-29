"""Invariantes declaradas por el plan 01-01.

Tres grupos, y cada uno cierra un modo de fallo concreto:

1. **`pyproject.toml` sin licencias contagiosas ni dependencias prohibidas.** Ultralytics
   y los YOLO derivados son AGPL-3.0 o GPL-3.0 y obligarían a publicar el código fuente
   de la aplicación entera; `PyQt6` es GPL-3.0 o licencia paga; `opencv-python` no
   headless embebe Qt5 y choca con el Qt6 de PySide6 en la Fase 2; `atomicwrites` está
   sin mantener desde 2022 y la escritura atómica se resuelve con la biblioteca
   estándar. `requests` y `httpx` cierran la decisión de transporte de esta fase: el
   plan 01-10 usa `urllib.request` de la stdlib, inyectado desde `composicion/`.

2. **El punto de entrada activa el modo UTF-8 antes de todo lo demás.** Sin eso la
   consola cp1252 de Windows revienta con `UnicodeEncodeError` en una CLI en español, y
   es un fallo de primer día en la herramienta de soporte remoto del producto.

3. **La compuerta de licencias usa lista blanca, no lista negra.** `--fail-on` compara
   cadenas y las cadenas varían: una dependencia GPL cuyo metadato diga
   "GNU General Public License v3 or later (GPLv3+)" pasa en verde contra una lista
   negra que decía "GPLv3". La lista blanca falla ante lo desconocido, que es lo que
   D-55 pide.
"""

from tests.arquitectura.invariantes import Invariante

INVARIANTES: tuple[Invariante, ...] = (
    # --- 1. pyproject.toml: nada contagioso, nada prohibido --------------------- #
    Invariante(
        ruta="pyproject.toml",
        modo="ausente",
        patron=r"ultralytics",
        motivo=(
            "Ultralytics se publica bajo AGPL-3.0 o licencia Enterprise paga. La AGPL "
            "obliga a liberar el código fuente de la aplicación completa, no sólo del "
            "módulo de visión. Usar RF-DETR-Nano/Small (Apache-2.0) en su lugar."
        ),
        ignorar_mayusculas=True,
    ),
    Invariante(
        ruta="pyproject.toml",
        modo="ausente",
        patron=r"yolo",
        motivo=(
            "Todos los YOLO disponibles como paquete son AGPL-3.0 (Ultralytics v5/v8/"
            "v11/v12, v10), GPL-3.0 (WongKinYiu v7/v9) o traen pesos con licencia de "
            "investigación no comercial (YOLO-NAS). Usar RF-DETR o D-FINE (Apache-2.0)."
        ),
        ignorar_mayusculas=True,
    ),
    Invariante(
        ruta="pyproject.toml",
        modo="ausente",
        patron=r"PyQt6",
        motivo=(
            "PyQt6 es GPL-3.0 o licencia comercial Riverbank paga. El toolkit de la "
            "Fase 2 es PySide6-Essentials (LGPLv3), que permite producto cerrado con "
            "enlace dinámico."
        ),
    ),
    Invariante(
        ruta="pyproject.toml",
        modo="ausente",
        patron=r"opencv-python==",
        motivo=(
            "`opencv-python` no headless embebe su propio Qt5 y choca con el Qt6 de "
            "PySide6: es una causa clásica de crashes al inicio, difíciles de "
            "diagnosticar. La única variante admitida es `opencv-python-headless`."
        ),
    ),
    Invariante(
        ruta="pyproject.toml",
        modo="ausente",
        patron=r"atomicwrites",
        motivo=(
            "`atomicwrites` está sin mantener desde 2022 y su propio autor recomienda "
            "el patrón de biblioteca estándar que el plan 01-04 implementa: "
            "`tempfile.mkstemp` en el directorio destino, `flush`, `os.fsync(fd)` y "
            "`os.replace`."
        ),
    ),
    # `requests` y `httpx` se buscan como **declaración de dependencia**, no como
    # mención: el contrato `sin_conexion_cruda` del mismo `pyproject.toml` tiene que
    # nombrar a `requests` para poder prohibirlo, igual que un docstring tiene que
    # nombrar lo que explica. El patrón acepta la entrada de una línea del array
    # `dependencies` (`^\s*"requests…`) o un especificador de versión pegado al nombre,
    # y no la aparición dentro de una lista en línea como `forbidden_modules`.
    Invariante(
        ruta="pyproject.toml",
        modo="ausente",
        patron=r"(?m)^\s*\"requests|requests\s*(?:==|>=|<=|~=|!=|>|<)",
        motivo=(
            "El producto no agrega ninguna dependencia HTTP. Las consultas a PALJET y "
            "a la balanza (plan 01-10) son GET simples con autenticación básica y "
            "timeout, resueltas con `urllib.request` de la stdlib e inyectadas desde "
            "`porteria.composicion`. Agregar `requests` reabre el inventario de "
            "licencias y la auditoría de legitimidad de paquetes."
        ),
    ),
    Invariante(
        ruta="pyproject.toml",
        modo="ausente",
        patron=r"(?m)^\s*\"httpx|httpx\s*(?:==|>=|<=|~=|!=|>|<)",
        motivo=(
            "Igual que `requests`, y peor: `httpx` arrastra `httpcore`, `h11`, `anyio`, "
            "`sniffio`, `certifi` e `idna` — seis paquetes sin auditar que obligarían a "
            "un checkpoint humano de legitimidad y a reabrir la lista blanca de "
            "`pip-licenses`."
        ),
    ),
    # --- 2. El punto de entrada sobrevive a la consola cp1252 -------------------- #
    Invariante(
        ruta="src/porteria/cli/app.py",
        modo="presente",
        patron=r"reconfigure\(encoding=\"utf-8\"",
        motivo=(
            "El punto de entrada tiene que reconfigurar la salida a UTF-8 en sus "
            "primeras líneas, antes de importar Typer. `sys.stdout.encoding` es cp1252 "
            "por defecto en Windows y una CLI en español revienta con "
            "`UnicodeEncodeError`. Es la única vía que sobrevive al empaquetado con "
            "PyInstaller sin depender del entorno del cliente."
        ),
        solo_primeras_lineas=10,
    ),
    # --- 3. La compuerta de licencias falla ante lo desconocido ------------------ #
    Invariante(
        ruta="scripts/compuerta.py",
        modo="presente",
        patron=r"--allow-only",
        motivo=(
            "La compuerta de licencias tiene que usar `--allow-only` con lista blanca "
            "explícita. D-55 exige fallar ante una licencia contagiosa **o no "
            "identificable**, y sólo la lista blanca falla ante lo desconocido."
        ),
    ),
    Invariante(
        ruta="scripts/compuerta.py",
        modo="ausente",
        patron=r"--fail-on",
        motivo=(
            "`--fail-on` compara cadenas y las cadenas varían: en el inventario "
            "verificado convivieron `MIT`, `MIT License`, `MIT-0`, `MIT OR Apache-2.0`, "
            "`BSD License` y `BSD-3-Clause` — seis formas para dos licencias. Una "
            "dependencia GPL cuyo metadato diga «GNU General Public License v3 or later "
            "(GPLv3+)» pasaría en verde contra una lista negra que decía `GPLv3`."
        ),
    ),
    # --- 4. La compuerta corre sobre Windows y sólo sobre Windows (D-54) --------- #
    Invariante(
        ruta=".github/workflows/compuerta.yml",
        modo="presente",
        patron=r"windows-latest",
        motivo=(
            "La compuerta tiene que correr sobre Windows: rutas con espacios y acentos, "
            "nombres de usuario con eñe y el renombrado atómico se comportan distinto "
            "ahí, y el Criterio de Éxito 6 exige demostrarlo en la plataforma de destino."
        ),
    ),
    Invariante(
        ruta=".github/workflows/compuerta.yml",
        modo="ausente",
        patron=r"ubuntu-",
        motivo=(
            "D-54 fija Windows como única plataforma de compuerta. Agregar un runner de "
            "otra plataforma diluye la señal: un verde en Linux no dice nada sobre "
            "MAX_PATH, cp1252 ni el renombrado atómico de NTFS."
        ),
    ),
    Invariante(
        ruta=".github/workflows/compuerta.yml",
        modo="ausente",
        patron=r"macos-",
        motivo="Ídem: D-54 fija Windows como única plataforma de compuerta.",
    ),
    Invariante(
        ruta=".github/workflows/compuerta.yml",
        modo="presente",
        patron=r"schedule:",
        motivo=(
            "D-53 exige que las pruebas de larga duración corran en tanda programada y "
            "no traben la fusión. Sin el disparador `schedule`, o se pierden o se "
            "vuelven bloqueantes, y una compuerta lenta obligatoria se termina salteando."
        ),
    ),
    Invariante(
        ruta=".github/workflows/compuerta.yml",
        modo="presente",
        patron=r"-m lenta",
        motivo="La tanda programada tiene que ejecutar justamente las pruebas `lenta`.",
    ),
    Invariante(
        ruta=".github/workflows/compuerta.yml",
        modo="presente",
        patron=r"PORTERIA_RAIZ_PRUEBAS",
        motivo=(
            "En integración continua la base de la ruta hostil se fija de forma "
            "explícita, para no depender de la heurística de candidatos del `conftest` "
            "en un runner cuyo directorio de trabajo puede cambiar."
        ),
    ),
)
