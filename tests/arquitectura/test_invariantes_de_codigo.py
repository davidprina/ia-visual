"""Comprueba las invariantes de código que cada plan de la fase declara.

Descubre **todos** los módulos de `tests/arquitectura/invariantes/` con
`pkgutil.iter_modules`, concatena sus tuplas `INVARIANTES` y parametriza una prueba por
entrada. Cada plan posterior agrega su propio `inv_01_0N.py` y nada más: así ningún plan
de la misma ola edita el archivo de otro.

Reemplaza todo criterio de aceptación basado en `grep`. Ver
`tests/arquitectura/invariantes/__init__.py` para el fundamento completo — en corto: la
plataforma de compuerta es Windows únicamente (D-54), `grep` no está garantizado, y
cuando el comando no existe «no se pudo verificar» se lee como «pasó».

Dos anti-vacuidades, porque una tabla de invariantes vacía pasaría siempre:
  1. Falla si el conjunto concatenado está vacío.
  2. Falla nombrando el archivo si una invariante declara una `ruta` que no existe —una
     entrada sin archivo significa que el plan que la declaró no creó el módulo.
"""

from __future__ import annotations

import importlib
import pkgutil
import re
from pathlib import Path

import pytest

from tests.arquitectura import invariantes as paquete_invariantes
from tests.arquitectura.invariantes import Invariante
from tests.arquitectura.lectura_de_codigo import normalizar_para_invariante

RAIZ_REPO = Path(__file__).resolve().parents[2]


def descubrir_invariantes() -> list[tuple[str, Invariante]]:
    """Concatena las invariantes de todos los módulos `inv_*` del paquete."""
    encontradas: list[tuple[str, Invariante]] = []

    for modulo in sorted(
        pkgutil.iter_modules(paquete_invariantes.__path__), key=lambda m: m.name
    ):
        if modulo.name.startswith("_"):
            continue

        cargado = importlib.import_module(f"{paquete_invariantes.__name__}.{modulo.name}")
        declaradas = getattr(cargado, "INVARIANTES", None)

        if declaradas is None:
            raise RuntimeError(
                f"El módulo de invariantes «{modulo.name}» no expone `INVARIANTES`. "
                "Cada `inv_01_0N.py` tiene que declarar una tupla `INVARIANTES` con las "
                "invariantes de su plan."
            )

        for invariante in declaradas:
            encontradas.append((f"{modulo.name}::{invariante.identificador()}", invariante))

    return encontradas


INVARIANTES_DESCUBIERTAS = descubrir_invariantes()


def verificar_invariante(invariante: Invariante, raiz: Path = RAIZ_REPO) -> None:
    """Comprueba una invariante. Levanta `AssertionError` con el motivo si no se cumple.

    Se extrae como función propia para que la propia maquinaria sea verificable: hay
    pruebas más abajo que la invocan con invariantes sintéticas y exigen que falle.
    """
    archivo = raiz / invariante.ruta

    assert archivo.is_file(), (
        f"La invariante declara el archivo «{invariante.ruta}», que no existe en el "
        "árbol. Una entrada sin archivo significa que el plan que la declaró no creó el "
        f"módulo.\nMotivo de la invariante: {invariante.motivo}"
    )

    texto = archivo.read_text(encoding="utf-8")
    if invariante.ignorar_comentarios:
        texto = normalizar_para_invariante(texto, archivo)
    if invariante.solo_primeras_lineas is not None:
        texto = "\n".join(texto.splitlines()[: invariante.solo_primeras_lineas])

    banderas = re.IGNORECASE if invariante.ignorar_mayusculas else 0
    coincidencia = re.search(invariante.patron, texto, banderas)

    if invariante.modo == "presente":
        assert coincidencia is not None, (
            f"«{invariante.ruta}» debería contener el patrón "
            f"`{invariante.patron}` y no lo contiene.\n{invariante.motivo}"
        )
        return

    if coincidencia is not None:
        numero_de_linea = texto[: coincidencia.start()].count("\n") + 1
        raise AssertionError(
            f"«{invariante.ruta}» contiene el patrón `{invariante.patron}` en la línea "
            f"{numero_de_linea} y no debería: {coincidencia.group(0)!r}\n"
            f"{invariante.motivo}"
        )


# --------------------------------------------------------------------------- #
# Las invariantes declaradas por los planes
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "invariante",
    [
        pytest.param(entrada, id=identificador)
        for identificador, entrada in INVARIANTES_DESCUBIERTAS
    ],
)
def test_se_cumple_la_invariante_declarada(invariante: Invariante) -> None:
    verificar_invariante(invariante)


# --------------------------------------------------------------------------- #
# Anti-vacuidad de la propia maquinaria
# --------------------------------------------------------------------------- #


def test_la_tabla_de_invariantes_no_esta_vacia() -> None:
    """Una tabla vacía pasaría siempre y nadie se enteraría."""
    assert INVARIANTES_DESCUBIERTAS, (
        "No se descubrió ninguna invariante en tests/arquitectura/invariantes/. "
        "La compuerta estaría pasando en verde sin comprobar nada. Qué revisar: que los "
        "módulos se llamen `inv_01_0N.py`, que expongan `INVARIANTES` y que el paquete "
        "tenga su `__init__.py`."
    )


def test_se_descubren_las_invariantes_de_este_plan() -> None:
    """El descubrimiento tiene que ver el módulo de 01-01, no sólo «alguno»."""
    modulos = {identificador.split("::", 1)[0] for identificador, _ in INVARIANTES_DESCUBIERTAS}

    assert "inv_01_01" in modulos, (
        "`pkgutil.iter_modules` no encontró `inv_01_01`. Módulos descubiertos: "
        f"{sorted(modulos)}"
    )


def test_una_invariante_sobre_un_archivo_inexistente_falla_nombrandolo() -> None:
    """Si un plan declara una invariante y no crea el módulo, hay que verlo."""
    inventada = Invariante(
        ruta="src/porteria/dominio/comun/este_modulo_no_existe.py",
        modo="presente",
        patron=r"lo que sea",
        motivo="Invariante sintética de la prueba de la prueba.",
    )

    with pytest.raises(AssertionError) as capturado:
        verificar_invariante(inventada)

    assert inventada.ruta in str(capturado.value), (
        "El fallo no nombra el archivo faltante, así que no se puede saber qué plan "
        f"quedó a medias. Mensaje:\n{capturado.value}"
    )


def test_el_modo_ausente_detecta_una_coincidencia_real(tmp_path: Path) -> None:
    """Anti-vacuidad del modo `ausente`: tiene que fallar cuando el patrón está."""
    archivo = tmp_path / "sucio.py"
    archivo.write_text("import cv2\n", encoding="utf-8")
    inventada = Invariante(
        ruta="sucio.py",
        modo="ausente",
        patron=r"import cv2",
        motivo="Invariante sintética de la prueba de la prueba.",
    )

    with pytest.raises(AssertionError) as capturado:
        verificar_invariante(inventada, raiz=tmp_path)

    assert "línea 1" in str(capturado.value), (
        f"El fallo no indica la línea de la coincidencia. Mensaje:\n{capturado.value}"
    )


def test_la_prosa_no_invalida_una_invariante_de_ausencia(tmp_path: Path) -> None:
    """Un docstring que explica por qué algo no debe existir no puede hacerla fallar."""
    archivo = tmp_path / "explicado.py"
    archivo.write_text(
        '"""Este módulo nunca hace `import cv2`, y acá se explica por qué."""\n'
        "# Tampoco lo hace en un comentario: import cv2\n"
        "valor = 1\n",
        encoding="utf-8",
    )
    inventada = Invariante(
        ruta="explicado.py",
        modo="ausente",
        patron=r"import cv2",
        motivo="Invariante sintética de la prueba de la prueba.",
    )

    verificar_invariante(inventada, raiz=tmp_path)


def test_solo_primeras_lineas_acota_de_verdad(tmp_path: Path) -> None:
    """Una coincidencia más allá del corte no cuenta como presente."""
    archivo = tmp_path / "tardio.py"
    archivo.write_text("\n" * 20 + "marca = 1\n", encoding="utf-8")
    inventada = Invariante(
        ruta="tardio.py",
        modo="presente",
        patron=r"marca",
        motivo="Invariante sintética de la prueba de la prueba.",
        solo_primeras_lineas=10,
    )

    with pytest.raises(AssertionError):
        verificar_invariante(inventada, raiz=tmp_path)
