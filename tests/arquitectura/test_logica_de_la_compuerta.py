"""Prueba la lógica de decisión de `scripts/compuerta.py` sin ejecutar la compuerta.

**Por qué no se invoca el script completo.** El paso 1 de la compuerta es
`uv run pytest -q -m "not lenta"`, que recolecta esta misma suite. Una prueba que
ejecutara `scripts/compuerta.py` se llamaría a sí misma sin fondo. Así que acá se
ejercita la lógica —el conteo de pruebas reportadas, el trato del código 5, la
propagación del peor resultado y que ningún paso se saltee— con el ejecutor de
subprocesos sustituido por un doble.

El comportamiento de punta a punta se verifica a mano al ejecutar el plan (los tres
sabotajes que declaran sus criterios de aceptación) y en integración continua, donde la
compuerta corre de verdad.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

RAIZ_REPO = Path(__file__).resolve().parents[2]
RUTA_COMPUERTA = RAIZ_REPO / "scripts" / "compuerta.py"
NOMBRE_MODULO = "porteria_scripts_compuerta"


def _cargar_compuerta() -> ModuleType:
    """Importa `scripts/compuerta.py`, que no vive en un paquete."""
    especificacion = importlib.util.spec_from_file_location(NOMBRE_MODULO, RUTA_COMPUERTA)
    assert especificacion is not None and especificacion.loader is not None, (
        f"No se pudo preparar la importación de «{RUTA_COMPUERTA}»."
    )
    modulo = importlib.util.module_from_spec(especificacion)
    # Registrarlo antes de ejecutarlo no es opcional: `dataclasses` resuelve el módulo
    # de la clase por `sys.modules[cls.__module__]` y sin esto revienta al definir `Paso`.
    sys.modules[NOMBRE_MODULO] = modulo
    especificacion.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def compuerta() -> ModuleType:
    return _cargar_compuerta()


# --------------------------------------------------------------------------- #
# Conteo de pruebas reportadas
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "resumen, esperado",
    [
        pytest.param("32 passed in 3.10s", 32, id="solo-passed"),
        pytest.param("12 passed, 1 xfailed in 2.85s", 13, id="passed-y-xfailed"),
        pytest.param("2 failed, 30 passed in 4.00s", 32, id="failed-y-passed"),
        pytest.param("1 error in 0.50s", 1, id="error"),
        pytest.param("no tests ran in 0.01s", 0, id="ninguna"),
        pytest.param("3 deselected in 0.02s", 0, id="deselected-no-cuenta"),
        pytest.param("", 0, id="salida-vacia"),
    ],
)
def test_cuenta_las_pruebas_que_el_resumen_reporta(
    compuerta: ModuleType, resumen: str, esperado: int
) -> None:
    assert compuerta._pruebas_reportadas(resumen) == esperado


# --------------------------------------------------------------------------- #
# El paso 1 no confía en el código de salida de pytest
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "codigo, salida, motivo",
    [
        pytest.param(5, "no tests ran in 0.01s", "codigo-5-de-pytest", id="codigo-5"),
        pytest.param(0, "no tests ran in 0.01s", "cero-recolectadas", id="exit-0-sin-pruebas"),
        pytest.param(0, "", "salida-sin-resumen", id="exit-0-sin-resumen"),
    ],
)
def test_una_corrida_sin_pruebas_deja_el_paso_1_en_rojo(
    compuerta: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    codigo: int,
    salida: str,
    motivo: str,
) -> None:
    monkeypatch.setattr(compuerta, "_ejecutar", lambda comando: (codigo, salida))

    paso = compuerta.paso_1_pruebas()

    assert paso.codigo != 0, (
        f"El paso 1 quedó en verde con cero pruebas ejecutadas ({motivo}). Es el fallo "
        "silencioso que la compuerta existe para cerrar."
    )
    assert paso.notas, "El paso no explicó por qué falló: en CI nadie sabría qué revisar."


def test_una_corrida_con_pruebas_deja_el_paso_1_en_verde(
    compuerta: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anti-vacuidad: el paso 1 no puede fallar siempre."""
    monkeypatch.setattr(
        compuerta, "_ejecutar", lambda comando: (0, "12 passed, 1 xfailed in 2.85s")
    )

    paso = compuerta.paso_1_pruebas()

    assert paso.codigo == 0, f"El paso 1 falló con 13 pruebas ejecutadas: {paso.notas}"
    assert any("13" in nota for nota in paso.notas), (
        f"El paso no informó cuántas pruebas corrieron. Notas: {paso.notas}"
    )


# --------------------------------------------------------------------------- #
# El paso 3 exige que la sonda haya importado algo
# --------------------------------------------------------------------------- #


def test_una_sonda_que_no_importo_nada_deja_el_paso_3_en_rojo(
    compuerta: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        compuerta, "_ejecutar", lambda comando: (0, "modulos importados: 0\n")
    )

    paso = compuerta.paso_3_sonda()

    assert paso.codigo != 0, (
        "La sonda declaró 0 módulos importados y el paso quedó en verde: la compuerta "
        "estaría pasando sin ejercitar nada."
    )


def test_una_sonda_muda_deja_el_paso_3_en_rojo(
    compuerta: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Si la sonda no informa cuánto importó, no se puede distinguir limpio de vacío."""
    monkeypatch.setattr(compuerta, "_ejecutar", lambda comando: (0, "todo bien\n"))

    assert compuerta.paso_3_sonda().codigo != 0


# --------------------------------------------------------------------------- #
# Los cuatro pasos corren siempre, y gana el peor
# --------------------------------------------------------------------------- #


def test_los_cuatro_pasos_corren_aunque_el_primero_falle(
    compuerta: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    ejecutados: list[int] = []

    def _falso(numero: int, codigo: int):
        def constructor() -> object:
            ejecutados.append(numero)
            return compuerta.Paso(numero, f"paso {numero}", ["falso"], codigo=codigo)

        return constructor

    monkeypatch.setattr(compuerta, "paso_1_pruebas", _falso(1, 1))
    monkeypatch.setattr(compuerta, "paso_2_contratos", _falso(2, 0))
    monkeypatch.setattr(compuerta, "paso_3_sonda", _falso(3, 0))
    monkeypatch.setattr(compuerta, "paso_4_licencias", _falso(4, 0))

    codigo = compuerta.main([])

    assert ejecutados == [1, 2, 3, 4], (
        "La compuerta cortó al primer fallo. Tiene que correr los cuatro pasos para que "
        f"un solo empujón muestre todos los problemas. Pasos ejecutados: {ejecutados}"
    )
    assert codigo == 1, f"La compuerta devolvió {codigo} con el paso 1 en rojo."


def test_la_compuerta_devuelve_el_peor_codigo_de_los_cuatro(
    compuerta: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    codigos = {1: 0, 2: 1, 3: 7, 4: 2}

    for numero, codigo in codigos.items():
        nombre = {
            1: "paso_1_pruebas",
            2: "paso_2_contratos",
            3: "paso_3_sonda",
            4: "paso_4_licencias",
        }[numero]
        monkeypatch.setattr(
            compuerta,
            nombre,
            lambda numero=numero, codigo=codigo: compuerta.Paso(
                numero, f"paso {numero}", ["falso"], codigo=codigo
            ),
        )

    assert compuerta.main([]) == 7, "La compuerta no propagó el peor código de salida."


def test_la_compuerta_en_verde_devuelve_cero(
    compuerta: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anti-vacuidad: no puede devolver siempre algo distinto de 0."""
    for numero, nombre in enumerate(
        ("paso_1_pruebas", "paso_2_contratos", "paso_3_sonda", "paso_4_licencias"), start=1
    ):
        monkeypatch.setattr(
            compuerta,
            nombre,
            lambda numero=numero: compuerta.Paso(numero, f"paso {numero}", ["falso"], codigo=0),
        )

    assert compuerta.main([]) == 0


def test_la_bandera_json_emite_el_resultado_estructurado(
    compuerta: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """D-51: legible por personas por defecto, estructurado bajo bandera."""
    import json

    for numero, nombre in enumerate(
        ("paso_1_pruebas", "paso_2_contratos", "paso_3_sonda", "paso_4_licencias"), start=1
    ):
        monkeypatch.setattr(
            compuerta,
            nombre,
            lambda numero=numero: compuerta.Paso(numero, f"paso {numero}", ["falso"], codigo=0),
        )

    compuerta.main(["--json"])
    salida = capsys.readouterr().out

    comienzo = salida.index("{")
    datos = json.loads(salida[comienzo:])

    assert datos["resultado"] == "verde"
    assert datos["codigo"] == 0
    assert [paso["numero"] for paso in datos["pasos"]] == [1, 2, 3, 4]


# --------------------------------------------------------------------------- #
# La lista blanca de licencias
# --------------------------------------------------------------------------- #


def test_la_lista_blanca_de_licencias_no_admite_nada_contagioso(
    compuerta: ModuleType,
) -> None:
    prohibidas = ("GPL", "AGPL", "LGPL", "SSPL", "UNKNOWN")

    for permitida in compuerta.LICENCIAS_PERMITIDAS:
        for prohibida in prohibidas:
            assert prohibida not in permitida.upper(), (
                f"La lista blanca admite «{permitida}», que contiene «{prohibida}». "
                "D-55 exige fallar ante licencias contagiosas o no identificables."
            )


def test_la_lista_blanca_no_esta_vacia(compuerta: ModuleType) -> None:
    """Una lista blanca vacía haría fallar todo, y alguien la desactivaría entera."""
    assert len(compuerta.LICENCIAS_PERMITIDAS) >= 10, (
        "La lista blanca quedó demasiado corta: revisá que cubra las variantes de cadena "
        "del inventario transitivo real."
    )
