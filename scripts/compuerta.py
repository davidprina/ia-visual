"""Compuerta de integración continua: cuatro pasos, un solo comando, el peor resultado.

    uv run python scripts/compuerta.py [--json]

Corre los cuatro pasos **siempre**, aunque el primero falle, para que un solo empujón
muestre todos los problemas en vez de obligar a cuatro vueltas. Sale con el peor código
de salida de los cuatro.

Sin dependencias fuera de la biblioteca estándar: la compuerta tiene que poder correr
antes y después de cualquier `uv sync`.

Los cuatro pasos
----------------
1. `pytest -q -m "not lenta"` — la compuerta rápida de D-53. Las pruebas `lenta` corren
   en tanda programada y no traban la fusión: una compuerta lenta es una compuerta que
   se termina salteando.
2. `lint-imports --no-cache` — los cuatro contratos de arquitectura. `--no-cache` porque
   un grafo cacheado puede ocultar una violación nueva.
3. La sonda de aislamiento del dominio en un entorno sin terceros (D-52).
4. El inventario de licencias de terceros (D-55).

Por qué el paso 1 no confía en su propio código de salida
---------------------------------------------------------
`pytest` devuelve 5 cuando no ejecutó ninguna prueba, y 5 es un número que un script
descuidado lee como "distinto de los que me importan" y deja pasar. Peor: un `skip` de
alcance de sesión produce exit **0** con cero pruebas ejecutadas. Por eso este paso hace
tres cosas: trata el 5 como fallo, cuenta las pruebas que el resumen reporta y exige que
sean más que cero. Es la misma comprobación que el `pytest_sessionfinish` de
`tests/conftest.py`, replicada acá a propósito, porque la compuerta no puede confiar en
que ese `conftest` se haya cargado.

Por qué el paso 4 usa lista blanca y no lista negra
---------------------------------------------------
`pip-licenses` compara cadenas, y las cadenas varían: en el inventario verificado
convivieron `MIT`, `MIT License`, `MIT-0`, `MIT OR Apache-2.0`, `BSD License` y
`BSD-3-Clause` — seis formas para dos licencias. Una lista negra (la opción `--fail-on`)
pasaría en verde ante una dependencia GPL cuyo metadato dijera "GNU General Public
License v3 or later (GPLv3+)" si la lista decía "GPLv3". D-55 exige fallar ante una
licencia contagiosa **o no identificable**, y sólo la lista blanca falla ante lo
desconocido. Se complementa con una comprobación propia que falla ante `UNKNOWN`.

El paquete `porteria` se excluye del inventario porque es código propio, no de terceros:
declarar la licencia del producto es una decisión comercial de la Fase 11, no una
dependencia a auditar.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

RAIZ_REPO = Path(__file__).resolve().parents[1]

#: Variantes de cadena de licencia aceptadas. Son las observadas en el cierre transitivo
#: completo del entorno de la fase. Ante cualquier cadena nueva la compuerta falla, y eso
#: es deliberado: obliga a mirar la licencia antes de aceptarla.
LICENCIAS_PERMITIDAS = (
    "MIT",
    "MIT License",
    "MIT-0",
    "MIT OR Apache-2.0",
    "MIT AND PSF-2.0",
    "BSD-3-Clause",
    "BSD-2-Clause",
    "BSD License",
    "Apache-2.0",
    "Apache Software License",
    "Apache-2.0 OR BSD-2-Clause",
    "ISC",
    "ISC License (ISCL)",
    "PSF-2.0",
    "BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0",
)

#: Código propio, no dependencia de terceros.
PAQUETES_IGNORADOS = ("porteria",)

COMANDO_PRUEBAS = ["uv", "run", "pytest", "-q", "-m", "not lenta"]
COMANDO_CONTRATOS = ["uv", "run", "lint-imports", "--no-cache"]
COMANDO_SONDA = [
    "uv",
    "run",
    "--python",
    "3.12",
    "--isolated",
    "--no-project",
    "python",
    "tests/arquitectura/sonda_dominio_aislado.py",
]
COMANDO_LICENCIAS = [
    "uv",
    "run",
    "pip-licenses",
    "--ignore-packages",
    *PAQUETES_IGNORADOS,
    "--allow-only",
    ";".join(LICENCIAS_PERMITIDAS),
]
COMANDO_LICENCIAS_JSON = [
    "uv",
    "run",
    "pip-licenses",
    "--ignore-packages",
    *PAQUETES_IGNORADOS,
    "--format=json",
]

#: Clases del resumen de pytest que cuentan como "algo se ejecutó". `deselected` queda
#: afuera a propósito: una prueba deseleccionada no corrió.
PATRON_RESUMEN = re.compile(
    r"(\d+)\s+(passed|failed|xfailed|xpassed|error|errors|skipped)\b"
)

ANCHO = 78


@dataclass
class Paso:
    """El resultado de un paso de la compuerta."""

    numero: int
    nombre: str
    comando: list[str]
    codigo: int = 0
    salida: str = ""
    notas: list[str] = field(default_factory=list)

    @property
    def paso(self) -> bool:
        return self.codigo == 0

    def como_diccionario(self) -> dict[str, object]:
        return {
            "numero": self.numero,
            "nombre": self.nombre,
            "comando": " ".join(self.comando),
            "codigo": self.codigo,
            "resultado": "verde" if self.paso else "rojo",
            "notas": list(self.notas),
        }


def _entorno_para_hijos() -> dict[str, str]:
    """Entorno de los subprocesos.

    Quita `PYTHONPATH` —la sonda del paso 3 tiene que auto-resolverse `src/`, y si acá se
    le regalara el camino la compuerta mediría otra cosa— y fuerza el modo UTF-8, para
    que la salida en español de los hijos no se rompa en una consola cp1252.
    """
    entorno = dict(os.environ)
    entorno.pop("PYTHONPATH", None)
    entorno["PYTHONUTF8"] = "1"
    return entorno


def _ejecutar(comando: list[str]) -> tuple[int, str]:
    proceso = subprocess.run(
        comando,
        cwd=RAIZ_REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_entorno_para_hijos(),
        check=False,
    )
    return proceso.returncode, proceso.stdout + proceso.stderr


def _pruebas_reportadas(salida: str) -> int:
    """Cuenta las pruebas que el resumen de pytest dice haber ejecutado."""
    return sum(int(cantidad) for cantidad, _ in PATRON_RESUMEN.findall(salida))


def paso_1_pruebas() -> Paso:
    resultado = Paso(1, "Pruebas rápidas (sin las marcadas «lenta»)", COMANDO_PRUEBAS)
    resultado.codigo, resultado.salida = _ejecutar(COMANDO_PRUEBAS)
    reportadas = _pruebas_reportadas(resultado.salida)

    if resultado.codigo == 5:
        resultado.notas.append(
            "pytest terminó con código 5: no ejecutó ninguna prueba. Se trata como "
            "fallo. Qué revisar: `testpaths` de pyproject.toml y el filtro -m."
        )
        resultado.codigo = 1
    elif reportadas == 0:
        resultado.notas.append(
            "El resumen de pytest no reporta ninguna prueba ejecutada. Una compuerta que "
            "pasa porque no corrió nada es peor que ninguna compuerta, así que se trata "
            "como fallo."
        )
        resultado.codigo = max(resultado.codigo, 1)
    else:
        resultado.notas.append(f"Pruebas ejecutadas: {reportadas}.")

    return resultado


def paso_2_contratos() -> Paso:
    resultado = Paso(2, "Contratos de arquitectura (import-linter)", COMANDO_CONTRATOS)
    resultado.codigo, resultado.salida = _ejecutar(COMANDO_CONTRATOS)
    if resultado.codigo != 0:
        resultado.notas.append(
            "Algún contrato se rompió. La salida nombra el módulo ofensor y el paquete "
            "prohibido."
        )
    return resultado


def paso_3_sonda() -> Paso:
    resultado = Paso(3, "Aislamiento del dominio en un entorno sin terceros", COMANDO_SONDA)
    resultado.codigo, resultado.salida = _ejecutar(COMANDO_SONDA)

    encontrado = re.search(r"modulos importados: (\d+)", resultado.salida)
    if encontrado is None:
        resultado.notas.append(
            "La sonda no informó cuántos módulos importó: no se puede distinguir «el "
            "dominio está limpio» de «no se importó nada»."
        )
        resultado.codigo = max(resultado.codigo, 1)
    elif int(encontrado.group(1)) == 0:
        resultado.notas.append(
            "La sonda importó 0 módulos: estaría pasando en verde sin ejercitar nada."
        )
        resultado.codigo = max(resultado.codigo, 1)
    else:
        resultado.notas.append(f"Módulos de dominio importados: {encontrado.group(1)}.")

    return resultado


def paso_4_licencias() -> Paso:
    resultado = Paso(4, "Inventario de licencias de terceros", COMANDO_LICENCIAS)
    resultado.codigo, resultado.salida = _ejecutar(COMANDO_LICENCIAS)
    if resultado.codigo != 0:
        resultado.notas.append(
            "Alguna dependencia declara una licencia que no está en la lista blanca. "
            "Mirala antes de agregarla: puede ser una variante de cadena de una licencia "
            "ya aceptada, o puede ser contagiosa."
        )

    codigo_json, salida_json = _ejecutar(COMANDO_LICENCIAS_JSON)
    if codigo_json != 0:
        resultado.notas.append(
            "No se pudo obtener el inventario en formato estructurado para revisar las "
            "licencias no identificables."
        )
        resultado.salida += f"\n{salida_json}"
        resultado.codigo = max(resultado.codigo, codigo_json)
        return resultado

    try:
        inventario = json.loads(salida_json)
    except json.JSONDecodeError as error:
        resultado.notas.append(f"El inventario estructurado no es JSON válido: {error}")
        resultado.codigo = max(resultado.codigo, 1)
        return resultado

    desconocidas = [
        f"{paquete.get('Name', '?')} {paquete.get('Version', '?')}"
        for paquete in inventario
        if str(paquete.get("License", "")).strip().upper() in {"", "UNKNOWN"}
    ]
    if desconocidas:
        resultado.notas.append(
            "Hay dependencias con licencia no identificable, y D-55 exige fallar ante "
            "eso igual que ante una licencia contagiosa: " + ", ".join(desconocidas)
        )
        resultado.codigo = max(resultado.codigo, 1)
    else:
        resultado.notas.append(
            f"Dependencias de terceros auditadas: {len(inventario)}. "
            "Ninguna con licencia no identificable."
        )

    return resultado


def _informar(paso: Paso) -> None:
    estado = "VERDE" if paso.paso else "ROJO"
    print("=" * ANCHO)
    print(f"Paso {paso.numero}/4 — {paso.nombre}  [{estado}]")
    print(f"  $ {' '.join(paso.comando)}")
    print("=" * ANCHO)
    for nota in paso.notas:
        print(f"  · {nota}")
    if not paso.paso:
        print("-" * ANCHO)
        print(paso.salida.rstrip())
        print("-" * ANCHO)
    print()


def main(argumentos: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(
        prog="compuerta",
        description="Corre las cuatro compuertas del proyecto y devuelve el peor resultado.",
    )
    analizador.add_argument(
        "--json",
        dest="estructurado",
        action="store_true",
        help="Emite además el resultado estructurado, para herramientas y pruebas.",
    )
    opciones = analizador.parse_args(argumentos)

    print()
    print("Compuerta de portería — cuatro pasos, ninguno se saltea".center(ANCHO))
    print()

    pasos = [paso_1_pruebas(), paso_2_contratos(), paso_3_sonda(), paso_4_licencias()]
    for paso in pasos:
        _informar(paso)

    peor = max(paso.codigo for paso in pasos)
    en_rojo = [paso.numero for paso in pasos if not paso.paso]

    print("=" * ANCHO)
    if en_rojo:
        numeros = ", ".join(str(numero) for numero in en_rojo)
        print(f"COMPUERTA EN ROJO — pasos con problemas: {numeros}. Código de salida: {peor}.")
        print("Los cuatro pasos corrieron: arriba está todo lo que hay que arreglar.")
    else:
        print("COMPUERTA EN VERDE — los cuatro pasos pasaron.")
    print("=" * ANCHO)

    if opciones.estructurado:
        print()
        print(
            json.dumps(
                {
                    "compuerta": "porteria",
                    "codigo": peor,
                    "resultado": "verde" if not en_rojo else "rojo",
                    "pasos": [paso.como_diccionario() for paso in pasos],
                },
                ensure_ascii=False,
                indent=2,
            )
        )

    return peor


if __name__ == "__main__":
    sys.exit(main())
