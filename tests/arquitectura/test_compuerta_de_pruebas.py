"""La compuerta de la propia suite: que no pueda pasar en verde sin haber corrido.

Este archivo prueba a `tests/conftest.py`, no al producto. Existe porque el modo de
fallo más silencioso de toda la fase es una compuerta que termina con exit 0 **porque
no ejecutó nada**: un `pytest.skip` de alcance de sesión, o una recolección vacía, se
propagan como éxito a través de `scripts/compuerta.py` y nadie se entera.

Cubre las cuatro fixtures de ruta hostil (DIS-06) y las dos decisiones que las
sostienen: resolver la base **falla** en vez de saltar, y una sesión con cero pruebas
recolectadas **no puede** terminar en verde.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import cv2
import pytest
from sqlalchemy import text

from tests import conftest

RAIZ_REPO = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- #
# La resolución de la base falla en vez de saltar
# --------------------------------------------------------------------------- #


def test_una_base_demasiado_larga_levanta_en_vez_de_saltar(tmp_path: Path) -> None:
    """Con una base artificialmente larga la resolución tiene que reventar.

    Un `pytest.skip` acá dejaría la suite entera en exit 0 sin ejecutar una sola
    prueba. Fallar es la única opción honesta.
    """
    base_larga = tmp_path / ("d" * 120) / ("e" * 120)

    with pytest.raises(pytest.UsageError) as capturado:
        conftest.resolver_base_de_pruebas(candidatos=[base_larga])

    mensaje = str(capturado.value)
    largo_obtenido = len(str(conftest.ruta_de_evidencia_bajo(base_larga)))

    assert str(conftest.LARGO_MAXIMO_RAIZ_EVIDENCIA) in mensaje, (
        "El mensaje tiene que decir el máximo (170 caracteres) para que se entienda "
        f"qué revisar. Mensaje recibido:\n{mensaje}"
    )
    assert str(largo_obtenido) in mensaje, (
        f"El mensaje tiene que decir el largo obtenido ({largo_obtenido}), no sólo el "
        f"máximo. Mensaje recibido:\n{mensaje}"
    )
    assert conftest.VARIABLE_BASE in mensaje, (
        "El mensaje tiene que explicar cómo fijar la base con "
        f"{conftest.VARIABLE_BASE}. Mensaje recibido:\n{mensaje}"
    )


def test_la_resolucion_elige_el_primer_candidato_utilizable(tmp_path: Path) -> None:
    """Anti-vacuidad de la prueba anterior: con un candidato sano, resuelve."""
    base_larga = tmp_path / ("d" * 120) / ("e" * 120)
    base_corta = Path(Path.cwd().anchor) / "p"

    elegida = conftest.resolver_base_de_pruebas(candidatos=[base_larga, base_corta])

    assert elegida == base_corta, (
        f"Con un candidato largo y uno corto tiene que elegir el corto; eligió {elegida}."
    )


# --------------------------------------------------------------------------- #
# Cero pruebas recolectadas es un fallo, nunca un verde
# --------------------------------------------------------------------------- #


class _SesionFalsa:
    """Doble mínimo de `pytest.Session`: sólo lo que el hook mira."""

    def __init__(self, recolectadas: int, exitstatus: int) -> None:
        self.testscollected = recolectadas
        self.exitstatus = exitstatus


def test_cero_pruebas_recolectadas_fuerza_un_exit_status_distinto_de_cero() -> None:
    sesion = _SesionFalsa(recolectadas=0, exitstatus=0)

    conftest.exigir_pruebas_recolectadas(sesion)

    assert sesion.exitstatus != 0, (
        "Una sesión que no recolectó ninguna prueba terminó en verde. Es el fallo "
        "silencioso que esta compuerta existe para cerrar: revisá "
        "`exigir_pruebas_recolectadas` en tests/conftest.py."
    )


def test_una_sesion_con_pruebas_conserva_su_exit_status() -> None:
    """Anti-vacuidad: el hook no puede fallar siempre, sólo cuando no hubo nada."""
    sesion = _SesionFalsa(recolectadas=7, exitstatus=0)

    conftest.exigir_pruebas_recolectadas(sesion)

    assert sesion.exitstatus == 0, (
        "El hook alteró el exit status de una sesión que sí recolectó pruebas."
    )


def test_una_corrida_real_sin_pruebas_recolectadas_termina_en_rojo() -> None:
    """De punta a punta: `pytest -m marcador-inexistente` no puede dar exit 0.

    Se ejecuta en un proceso aparte con una base propia, para que el barrido de la
    sesión anidada no toque el subárbol de la sesión que está corriendo esta prueba.
    """
    base_anidada = Path(Path.cwd().anchor) / "p-anidada"
    entorno = dict(os.environ)
    entorno[conftest.VARIABLE_BASE] = str(base_anidada)

    resultado = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-m", "marcador-inexistente"],
        cwd=RAIZ_REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=entorno,
        check=False,
    )
    salida = resultado.stdout + resultado.stderr

    assert resultado.returncode != 0, (
        "Una corrida que no recolectó ninguna prueba terminó en verde.\n"
        f"Salida completa:\n{salida}"
    )
    assert "ninguna prueba" in salida, (
        "El exit code fue distinto de 0 pero el aviso de `pytest_sessionfinish` no "
        "aparece: puede estar fallando por otro motivo y no por la recolección vacía.\n"
        f"Salida completa:\n{salida}"
    )


# --------------------------------------------------------------------------- #
# Las cuatro fixtures de ruta hostil (DIS-06)
# --------------------------------------------------------------------------- #


def test_toda_la_suite_corre_bajo_una_ruta_con_espacios_y_acentos(ruta_hostil) -> None:
    raiz = str(ruta_hostil.raiz)

    assert " " in raiz, f"La raíz de pruebas no tiene espacios: {raiz}"
    assert "ñandú" in raiz, f"La raíz de pruebas no tiene acentos ni eñe: {raiz}"
    assert ruta_hostil.raiz_evidencia.is_dir(), (
        f"No existe el directorio de evidencia: {ruta_hostil.raiz_evidencia}"
    )
    assert ruta_hostil.ruta_db.parent.is_dir(), (
        f"No existe el directorio de la base: {ruta_hostil.ruta_db.parent}"
    )
    assert len(str(ruta_hostil.raiz_evidencia)) <= conftest.LARGO_MAXIMO_RAIZ_EVIDENCIA, (
        "La raíz de evidencia supera el máximo tolerado por MAX_PATH: "
        f"{len(str(ruta_hostil.raiz_evidencia))} caracteres."
    )


def test_el_motor_sqlite_abre_la_base_bajo_la_ruta_hostil(motor_sqlite, ruta_hostil) -> None:
    with motor_sqlite.connect() as conexion:
        assert conexion.execute(text("select 1")).scalar_one() == 1

    assert ruta_hostil.ruta_db.exists(), (
        f"La base no se creó donde se esperaba: {ruta_hostil.ruta_db}"
    )


def test_el_reloj_determinista_lo_controla_la_prueba(reloj_determinista) -> None:
    inicial = reloj_determinista.instante_ns()

    assert reloj_determinista.instante_ns() == inicial, (
        "El reloj determinista avanzó solo: alguna prueba de dominio va a ser inestable."
    )

    reloj_determinista.avanzar_ms(150)

    assert reloj_determinista.instante_ns() == inicial + 150_000_000, (
        "`avanzar_ms` no movió el reloj los milisegundos pedidos."
    )


def test_el_video_sintetico_se_abre_con_el_backend_ffmpeg(video_sintetico: Path) -> None:
    assert "ñandú" in str(video_sintetico), (
        f"El video sintético no se generó bajo la ruta con acentos: {video_sintetico}"
    )

    captura = cv2.VideoCapture(str(video_sintetico))
    try:
        assert captura.isOpened(), (
            f"cv2.VideoCapture no pudo abrir el video sintético: {video_sintetico}"
        )
        assert captura.getBackendName() == "FFMPEG", (
            "El video sintético no se abre con el backend FFMPEG sino con "
            f"{captura.getBackendName()!r}: las pruebas de frescura de 01-03 medirían "
            "otra cosa."
        )
        leido, cuadro = captura.read()
        assert leido and cuadro is not None, "El primer cuadro del video no se pudo leer."
        assert cuadro.shape[:2] == (240, 320), (
            f"El video sintético no mide 320x240 sino {cuadro.shape[1]}x{cuadro.shape[0]}."
        )
    finally:
        captura.release()


# --------------------------------------------------------------------------- #
# Anti-vacuidad de la suite de arquitectura (Pitfall 11)
# --------------------------------------------------------------------------- #


def test_el_conftest_no_puede_saltar_la_sesion() -> None:
    """`pytest.skip` en la resolución de la ruta convertiría la compuerta en un adorno."""
    fuente = (RAIZ_REPO / "tests" / "conftest.py").read_text(encoding="utf-8")
    codigo = "\n".join(
        linea for linea in fuente.splitlines() if not linea.lstrip().startswith("#")
    )

    assert not re.search(r"pytest\.skip\s*\(", codigo), (
        "tests/conftest.py llama a pytest.skip. Un skip de alcance de sesión hace que "
        "`pytest -q -m \"not lenta\"` termine con exit 0 sin ejecutar nada."
    )
    assert "tmp_path_factory" not in codigo, (
        "La raíz hostil se ancla en una base corta y controlada, no en "
        "`tmp_path_factory`: su base en Windows ya roza el límite de MAX_PATH."
    )
