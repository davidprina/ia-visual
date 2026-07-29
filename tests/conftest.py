"""Fixtures de la suite: ruta hostil, motor SQLite, reloj determinista y video sintético.

**DIS-06 es una condición de todo el entorno de prueba, no un caso especial.** La raíz
con espacios y acentos se instala con una fixture de sesión `autouse=True` para que
ninguna prueba pueda correr fuera de ella. Si viviera sólo en una prueba aislada,
alguien la rompería por descuido en la Fase 5 y nadie se enteraría.

**La resolución de la base falla; nunca salta.** Un `pytest.skip` de alcance de sesión
haría que `uv run pytest -q -m "not lenta"` terminara con exit 0 sin ejecutar nada, y
que `scripts/compuerta.py` propagara ese 0 como compuerta verde. Es la forma más
silenciosa que tiene esta fase de mentirse. Por eso acá se levanta `pytest.UsageError`
y además `pytest_sessionfinish` falla cuando no se recolectó ninguna prueba.

**Por qué no se usa `tmp_path_factory`** (Pitfall 3): su base en Windows
(`C:\\Users\\<usuario>\\AppData\\Local\\Temp\\pytest-of-<usuario>\\pytest-N\\...`) más
`IA visual ñandú áéí\\evidencia fotográfica` queda pegada al límite de 170 caracteres
que impone MAX_PATH, y a menudo por encima. La raíz se ancla en una base corta y
controlada.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine

from porteria.infraestructura.runtime.reloj import RelojFijo

# --------------------------------------------------------------------------- #
# Constantes de la ruta hostil (DIS-06)
# --------------------------------------------------------------------------- #

#: Nombre del directorio raíz: espacios, eñe y tildes, todo junto y a propósito.
NOMBRE_RAIZ = "IA visual ñandú áéí"
SUBDIR_BASE_DE_DATOS = "base de datos"
SUBDIR_EVIDENCIA = "evidencia fotográfica"
SUBDIR_VIDEO = "video"

#: Pitfall 3: MAX_PATH está activo y el sufijo `AAAA/MM/DD/<64hex>.jpg` mide 89
#: caracteres, así que la raíz de evidencia no puede pasar de ~170.
LARGO_MAXIMO_RAIZ_EVIDENCIA = 170

#: Variable de entorno que fija la base de forma explícita. La integración continua
#: la define en `C:\\p` para no depender de la heurística de candidatos.
VARIABLE_BASE = "PORTERIA_RAIZ_PRUEBAS"

# Video sintético (Open Question 5 de la investigación: alcanza para medir el
# contrato de frescura). Se genera, no se versiona (D-59).
VIDEO_ANCHO = 320
VIDEO_ALTO = 240
VIDEO_FPS = 25
VIDEO_SEGUNDOS = 30


@dataclass(frozen=True)
class RutaHostil:
    """Las tres rutas que las pruebas necesitan, ya resueltas.

    Se exponen como atributos para que ninguna prueba posterior reconstruya rutas a
    mano y termine escribiendo fuera de la raíz hostil.
    """

    raiz: Path
    raiz_evidencia: Path
    ruta_db: Path


_raiz_hostil: RutaHostil | None = None


# --------------------------------------------------------------------------- #
# Resolución de la base
# --------------------------------------------------------------------------- #


def ruta_de_evidencia_bajo(base: Path) -> Path:
    """Devuelve dónde caería la raíz de evidencia si la base fuera `base`."""
    return Path(base) / NOMBRE_RAIZ / SUBDIR_EVIDENCIA


def candidatos_por_defecto() -> list[Path]:
    """Los candidatos de base, en orden de preferencia.

    1. La variable de entorno `PORTERIA_RAIZ_PRUEBAS`, si está definida.
    2. `<ancla de la unidad actual>p` — por ejemplo `C:\\p`.
    3. `%LOCALAPPDATA%\\pp` en Windows, o `~/.pp` en POSIX.
    """
    candidatos: list[Path] = []

    desde_entorno = os.environ.get(VARIABLE_BASE)
    if desde_entorno:
        candidatos.append(Path(desde_entorno))

    ancla = Path.cwd().anchor
    if ancla:
        candidatos.append(Path(ancla) / "p")

    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            candidatos.append(Path(local) / "pp")
    else:
        candidatos.append(Path.home() / ".pp")

    return candidatos


def resolver_base_de_pruebas(candidatos: Sequence[Path] | None = None) -> Path:
    """Elige la primera base creable cuya raíz de evidencia entre en MAX_PATH.

    Se extrae como función propia —y no se resuelve dentro de la fixture— para poder
    probarla con una base artificialmente larga y exigir que **levante** en vez de
    saltar.

    Raises:
        pytest.UsageError: si ningún candidato sirve. Nunca `pytest.skip`.
    """
    a_probar = list(candidatos) if candidatos is not None else candidatos_por_defecto()
    intentos: list[str] = []

    for candidata in a_probar:
        base = Path(candidata)
        largo = len(str(ruta_de_evidencia_bajo(base)))

        if largo > LARGO_MAXIMO_RAIZ_EVIDENCIA:
            intentos.append(
                f"«{base}»: la raíz de evidencia mediría {largo} caracteres y el "
                f"máximo es {LARGO_MAXIMO_RAIZ_EVIDENCIA}"
            )
            continue

        try:
            base.mkdir(parents=True, exist_ok=True)
            sonda = base / ".porteria-sonda-de-escritura"
            sonda.write_text("ñandú", encoding="utf-8")
            sonda.unlink()
        except OSError as error:
            intentos.append(f"«{base}»: no se pudo crear ni escribir ({error})")
            continue

        return base

    detalle = "\n".join(f"  - {intento}" for intento in intentos) or "  - (ninguno)"
    raise pytest.UsageError(
        "No hay ninguna base utilizable para la suite de pruebas.\n"
        f"La raíz de evidencia no puede superar los {LARGO_MAXIMO_RAIZ_EVIDENCIA} "
        "caracteres: MAX_PATH está activo en Windows y el sufijo "
        "AAAA/MM/DD/<64hex>.jpg ya mide 89.\n"
        f"Candidatos probados:\n{detalle}\n"
        f"Qué hacer: fijá una base corta con la variable de entorno {VARIABLE_BASE}, "
        "por ejemplo\n"
        f"  set {VARIABLE_BASE}=C:\\p"
    )


def exigir_pruebas_recolectadas(session) -> None:  # noqa: ANN001 - doble en las pruebas
    """Fuerza un exit status distinto de 0 si la sesión no recolectó ninguna prueba.

    `--exitfirst` no cubre este caso: el problema no es una prueba que falla sino que
    no hubo nada que ejecutar.
    """
    if session.testscollected != 0:
        return

    print(
        "\n"
        "No se recolectó ninguna prueba: la sesión no ejecutó nada.\n"
        "Esto NO es un éxito. Una compuerta que pasa porque no corrió nada es peor "
        "que ninguna compuerta,\n"
        "así que la sesión termina en rojo a propósito.\n"
        "Qué revisar: el filtro -k/-m que usaste, la ruta que le pasaste a pytest, y "
        "que `testpaths`\n"
        "de pyproject.toml siga apuntando a tests/."
    )
    session.exitstatus = 1


# --------------------------------------------------------------------------- #
# Hooks de sesión
# --------------------------------------------------------------------------- #


def pytest_sessionstart(session: pytest.Session) -> None:
    """Crea la raíz hostil antes de recolectar. Si no puede, revienta la sesión."""
    global _raiz_hostil

    base = resolver_base_de_pruebas()
    raiz = base / NOMBRE_RAIZ
    raiz_evidencia = raiz / SUBDIR_EVIDENCIA
    directorio_db = raiz / SUBDIR_BASE_DE_DATOS

    for directorio in (raiz_evidencia, directorio_db, raiz / SUBDIR_VIDEO):
        directorio.mkdir(parents=True, exist_ok=True)

    _raiz_hostil = RutaHostil(
        raiz=raiz,
        raiz_evidencia=raiz_evidencia,
        ruta_db=directorio_db / "porteria.sqlite3",
    )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Borra el subárbol de la sesión y exige que se haya recolectado algo."""
    global _raiz_hostil

    if _raiz_hostil is not None:
        shutil.rmtree(_raiz_hostil.raiz, ignore_errors=True)
        _raiz_hostil = None

    exigir_pruebas_recolectadas(session)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="session", autouse=True)
def ruta_hostil() -> RutaHostil:
    """La raíz con espacios y acentos bajo la que corre **toda** la suite (DIS-06)."""
    if _raiz_hostil is None:
        raise pytest.UsageError(
            "La raíz hostil no está resuelta: `pytest_sessionstart` de "
            "tests/conftest.py no corrió. Revisá que el conftest esté en tests/ y que "
            "no haya otro conftest sombreándolo."
        )
    return _raiz_hostil


@pytest.fixture
def motor_sqlite(ruta_hostil: RutaHostil) -> Engine:
    """Motor SQLAlchemy sobre la base bajo la ruta hostil.

    En este plan la fixture todavía no puede importar `crear_motor`, que llega en
    01-05. Se construye la URL con `URL.create` y no concatenando `"sqlite:///" + ruta`,
    que es el antipatrón que rompe con acentos.
    """
    # 01-05 reemplaza esta construcción por
    # porteria.infraestructura.persistencia.sqlite.motor.crear_motor
    motor = create_engine(URL.create("sqlite", database=str(ruta_hostil.ruta_db)))
    try:
        yield motor
    finally:
        motor.dispose()
        for sufijo in ("", "-wal", "-shm"):
            Path(f"{ruta_hostil.ruta_db}{sufijo}").unlink(missing_ok=True)


#: Doble del puerto `Reloj`, y **el mismo objeto que el producto expone** en
#: `porteria.infraestructura.runtime.reloj`. El plan 01-01 declaró acá una clase propia
#: porque el reloj todavía no existía; el 01-02 la reemplaza por un alias en vez de
#: mantener dos dobles en paralelo. Si fueran dos, el de las pruebas podría dejar de
#: cumplir el puerto sin que nada lo delate, y las pruebas de dominio estarían
#: verificando un contrato que la aplicación no usa.
RelojDeterminista = RelojFijo


@pytest.fixture
def reloj_determinista() -> RelojFijo:
    """Reloj controlado por la prueba: cero dependencia del reloj real."""
    return RelojFijo()


def _codec_mp4v() -> int:
    """Devuelve el fourcc de mp4v con la API que tenga esta versión de OpenCV."""
    fabrica = getattr(cv2, "VideoWriter_fourcc", None) or cv2.VideoWriter.fourcc
    return int(fabrica(*"mp4v"))


@pytest.fixture(scope="session")
def video_sintetico(ruta_hostil: RutaHostil) -> Path:
    """Genera un video de 320x240 a 25 fps y ~30 s bajo la ruta con acentos.

    Se genera y no se versiona (D-59). El contenido cambia en cada cuadro —una barra
    que se desplaza más el número de cuadro impreso— para que las pruebas de frescura
    de 01-03 puedan distinguir un cuadro nuevo de uno repetido.
    """
    destino = ruta_hostil.raiz / SUBDIR_VIDEO / "sintetico.mp4"
    if destino.exists():
        return destino

    escritor = cv2.VideoWriter(
        str(destino), _codec_mp4v(), VIDEO_FPS, (VIDEO_ANCHO, VIDEO_ALTO)
    )
    if not escritor.isOpened():
        raise pytest.UsageError(
            "OpenCV no pudo abrir el escritor de video para generar el video "
            f"sintético en «{destino}». Qué revisar: que el paquete instalado sea "
            "opencv-python-headless y que la ruta sea escribible."
        )

    try:
        for numero in range(VIDEO_FPS * VIDEO_SEGUNDOS):
            cuadro = np.zeros((VIDEO_ALTO, VIDEO_ANCHO, 3), dtype=np.uint8)
            izquierda = (numero * 4) % VIDEO_ANCHO
            cv2.rectangle(
                cuadro,
                (izquierda, 0),
                (min(izquierda + 40, VIDEO_ANCHO), VIDEO_ALTO),
                (0, 200, 255),
                -1,
            )
            cv2.putText(
                cuadro,
                f"{numero:05d}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2,
            )
            escritor.write(cuadro)
    finally:
        escritor.release()

    if not destino.exists() or destino.stat().st_size == 0:
        raise pytest.UsageError(
            f"El video sintético quedó vacío o no se escribió en «{destino}»."
        )
    return destino
