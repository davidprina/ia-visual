"""Prueba de la prueba: sabotea la compuerta del dominio y exige que falle (T-01-11).

Una compuerta que nunca falló no está demostrada. Sin esta prueba, un contrato mal
escrito pasa siempre y nadie se entera: es la diferencia entre **tener** una compuerta y
**creer** que se tiene una.

Siembra en `dominio/` un módulo con `import cv2` y exige que `lint-imports` devuelva
exit 1 nombrando al módulo ofensor y al paquete prohibido. Usa las dos vías de evasión
más difíciles de las cuatro que la investigación verificó:

  1. **Import diferido dentro de una función** — invisible para cualquier comprobación
     que dependa de ejecutar el código.
  2. **Import bajo `if TYPE_CHECKING:`** — nunca se ejecuta en runtime, y es la razón
     por la que `pyproject.toml` **no** activa `exclude_type_checking_imports`.

El módulo sembrado se borra en un `finally`, y el `finally` verifica que se borró: un
fallo de esta prueba no puede dejar el árbol contaminado, porque un `import cv2` olvidado
en `dominio/` rompería todas las compuertas siguientes con una causa difícil de rastrear.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

RAIZ_REPO = Path(__file__).resolve().parents[2]

#: El módulo se siembra en `dominio/comun/`, la zona más interna del dominio.
MODULO_SABOTEADO = RAIZ_REPO / "src" / "porteria" / "dominio" / "comun" / "_sabotaje_temporal.py"
MODULO_ESPERADO_EN_LA_SALIDA = "porteria.dominio.comun._sabotaje_temporal"

COMANDO = ["uv", "run", "lint-imports", "--no-cache"]

#: Encabezado del módulo sembrado. Si alguien lo encuentra en el árbol, tiene que saber
#: en un segundo qué es y quién lo dejó ahí.
AVISO = (
    '"""Modulo temporal de sabotaje: lo crea y lo borra\n'
    'test_sabotaje_compuerta_dominio.py. Si aparece en un commit, es un error."""'
)

IMPORT_DIFERIDO_EN_FUNCION = f'''{AVISO}


def calcular():
    import cv2

    return cv2
'''

IMPORT_BAJO_TYPE_CHECKING = f'''{AVISO}

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import cv2


def anotada(imagen: "cv2.Mat") -> str:
    return str(imagen)
'''


@contextmanager
def _dominio_saboteado(fuente: str) -> Iterator[None]:
    """Siembra el módulo ofensor y garantiza que el árbol queda limpio al salir."""
    MODULO_SABOTEADO.write_text(fuente, encoding="utf-8")
    try:
        yield
    finally:
        MODULO_SABOTEADO.unlink(missing_ok=True)
        # Los .pyc del módulo sembrado también se van: grimp analiza el árbol de
        # archivos, y un resto en __pycache__ confundiría la próxima corrida.
        cache = MODULO_SABOTEADO.parent / "__pycache__"
        for compilado in cache.glob(f"{MODULO_SABOTEADO.stem}.*.pyc"):
            compilado.unlink(missing_ok=True)
        assert not MODULO_SABOTEADO.exists(), (
            f"El módulo de sabotaje «{MODULO_SABOTEADO}» quedó en el árbol. Borralo a "
            "mano antes de seguir: mientras exista, todas las compuertas de arquitectura "
            "van a fallar por este archivo y no por el código real."
        )


def _correr_lint_imports() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        COMANDO,
        cwd=RAIZ_REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=dict(os.environ),
        check=False,
    )


@pytest.mark.parametrize(
    "fuente",
    [
        pytest.param(IMPORT_DIFERIDO_EN_FUNCION, id="import-diferido-dentro-de-funcion"),
        pytest.param(IMPORT_BAJO_TYPE_CHECKING, id="import-bajo-TYPE_CHECKING"),
    ],
)
def test_un_import_prohibido_en_el_dominio_rompe_la_compuerta(fuente: str) -> None:
    with _dominio_saboteado(fuente):
        resultado = _correr_lint_imports()

    salida = f"--- stdout ---\n{resultado.stdout}\n--- stderr ---\n{resultado.stderr}"

    assert resultado.returncode == 1, (
        "Se sembró un `import cv2` en `dominio/` y `lint-imports` no falló. El contrato "
        "`dominio_limpio` no está atrapando esta vía de evasión: revisá que "
        "`include_external_packages = true`, que `allow_indirect_imports = false` y que "
        "`exclude_type_checking_imports` NO esté activado.\n"
        f"Código de salida: {resultado.returncode}\n{salida}"
    )
    assert MODULO_ESPERADO_EN_LA_SALIDA in resultado.stdout, (
        "`lint-imports` falló pero no nombró al módulo ofensor, así que en integración "
        "continua nadie sabría qué archivo revisar.\n"
        f"Se esperaba ver «{MODULO_ESPERADO_EN_LA_SALIDA}».\n{salida}"
    )
    assert "cv2" in resultado.stdout, (
        "`lint-imports` falló pero no nombró al paquete prohibido `cv2`.\n"
        f"{salida}"
    )


def test_sobre_el_arbol_limpio_la_compuerta_pasa() -> None:
    """Anti-vacuidad: la compuerta no puede fallar siempre, sólo cuando hay motivo.

    Sin esta prueba, un `lint-imports` roto —por ejemplo un `pyproject.toml` con un
    contrato mal formado— haría pasar las dos pruebas de sabotaje por el motivo
    equivocado, y la compuerta parecería más sana que nunca.
    """
    assert not MODULO_SABOTEADO.exists(), (
        f"El árbol no está limpio: existe «{MODULO_SABOTEADO}». Borralo antes de correr "
        "la suite."
    )

    resultado = _correr_lint_imports()
    salida = f"--- stdout ---\n{resultado.stdout}\n--- stderr ---\n{resultado.stderr}"

    assert resultado.returncode == 0, (
        f"`lint-imports` falla sobre el árbol limpio.\n{salida}"
    )
    assert "4 kept, 0 broken" in resultado.stdout, (
        "La salida no reporta los cuatro contratos en verde. Si son menos de cuatro, "
        f"alguien borró un contrato de `pyproject.toml`.\n{salida}"
    )
