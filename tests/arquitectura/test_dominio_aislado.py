"""Compuerta de aislamiento del dominio en runtime (NUC-01, D-52).

Lanza `sonda_dominio_aislado.py` en un entorno donde ninguno de los paquetes prohibidos
está instalado. Es la segunda mitad del Criterio de Éxito 1: `import-linter` prueba que
nadie escribió el import; esto prueba que el dominio **arranca** sin esos paquetes.

El comando es literalmente el mismo que figura en el `must_have` del plan, en
`01-VALIDATION.md` y en el paso 3 de `scripts/compuerta.py`. Que sea el mismo no es
prolijidad: es la única forma de que las tres afirmaciones puedan ser verdaderas a la
vez. Por eso la sonda se auto-resuelve `src/` y acá **no se toca `PYTHONPATH`**.
"""

import os
import re
import subprocess
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parents[2]

COMANDO = [
    "uv",
    "run",
    "--python",
    "3.12",
    "--isolated",
    "--no-project",
    "python",
    "tests/arquitectura/sonda_dominio_aislado.py",
]


def _correr_la_sonda() -> subprocess.CompletedProcess[str]:
    """Ejecuta la sonda sin `PYTHONPATH`, desde la raíz del repositorio."""
    entorno = dict(os.environ)
    entorno.pop("PYTHONPATH", None)

    return subprocess.run(
        COMANDO,
        cwd=RAIZ_REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=entorno,
        check=False,
    )


def test_el_dominio_se_importa_entero_sin_las_dependencias_pesadas() -> None:
    resultado = _correr_la_sonda()
    salida = f"--- stdout ---\n{resultado.stdout}\n--- stderr ---\n{resultado.stderr}"

    assert resultado.returncode == 0, (
        "El dominio no se pudo importar en un entorno sin cv2, onnxruntime, PySide6, "
        "numpy, sqlalchemy, alembic, av, typer, click, structlog, argon2 ni pydantic.\n"
        "Qué revisar: el módulo que la salida nombra como ofensor. Si el fallo es un "
        "ModuleNotFoundError, ése es el import prohibido.\n"
        f"Comando: {' '.join(COMANDO)}\n{salida}"
    )


def test_la_sonda_declara_haber_importado_algo() -> None:
    """Anti-vacuidad (Pitfall 11): una sonda que no importó nada pasa siempre.

    Sin esta prueba, el día que `dominio/` se renombre o `walk_packages` deje de
    encontrar submódulos, la compuerta seguiría en verde sin ejercitar una sola línea.
    """
    resultado = _correr_la_sonda()
    salida = f"--- stdout ---\n{resultado.stdout}\n--- stderr ---\n{resultado.stderr}"

    encontrado = re.search(r"modulos importados: (\d+)", resultado.stdout)

    assert encontrado is not None, (
        "La sonda no informó cuántos módulos importó, así que no se puede distinguir "
        f"«el dominio está limpio» de «no se importó nada».\n{salida}"
    )
    assert int(encontrado.group(1)) >= 1, (
        "La sonda declaró haber importado 0 módulos: la compuerta estaría pasando en "
        f"verde sin ejercitar nada.\n{salida}"
    )
