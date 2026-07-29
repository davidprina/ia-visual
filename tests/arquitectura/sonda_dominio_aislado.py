"""Sonda de aislamiento del dominio: importa todo dominio/ y delata a los prohibidos.

Es un **script**, no una prueba. Se ejecuta con un intérprete donde ninguno de los
paquetes prohibidos está instalado:

    uv run --python 3.12 --isolated --no-project python tests/arquitectura/sonda_dominio_aislado.py

Ahí, un import prohibido revienta con `ModuleNotFoundError` antes de llegar a la
comprobación final —y ése es exactamente el resultado que se busca—. La comprobación
sobre `sys.modules` cubre el caso residual de un módulo prohibido que sí exista en el
entorno mínimo.

Responde una pregunta que la compuerta estática de `import-linter` no responde:
*¿el dominio realmente arranca sin esos paquetes?* Las dos juntas cubren NUC-01.

**Por qué se auto-resuelve `src/`.** Con `--no-project` el paquete `porteria` no está
instalado. Sin insertar `src/` en `sys.path`, `import porteria.dominio` fallaría con
`ModuleNotFoundError` y la sonda mediría otra cosa: la ausencia del proyecto, no la
limpieza del dominio. Resolverlo acá adentro es lo que permite que **el mismo comando
literal** funcione a mano, desde pytest y desde `scripts/compuerta.py`, sin que nadie
tenga que definir `PYTHONPATH`.

**Por qué la salida es ASCII.** Este script corre en un entorno mínimo cuya consola
puede ser cp1252, y no puede activar el modo UTF-8 porque el comando es literal y fijo.
Un acento en la salida arriesgaría un `UnicodeEncodeError` que se leería como un fallo
del dominio. La prosa acentuada vive en este docstring, que nunca se imprime.
"""

import os
import sys

# Primera sentencia ejecutable, antes de cualquier import del proyecto.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

import importlib  # noqa: E402
import pkgutil  # noqa: E402

#: Coincide con `forbidden_modules` del contrato `dominio_limpio` de pyproject.toml.
#: Si una lista cambia, la otra tiene que cambiar con ella.
PROHIBIDOS = frozenset(
    {
        "cv2",
        "onnxruntime",
        "PySide6",
        "av",
        "numpy",
        "sqlalchemy",
        "alembic",
        "typer",
        "click",
        "structlog",
        "argon2",
        "pydantic",
    }
)


def main() -> int:
    """Importa el dominio completo y devuelve 1 si algun prohibido quedo cargado."""
    import porteria.dominio as dominio

    importados = [dominio.__name__]
    for encontrado in pkgutil.walk_packages(dominio.__path__, dominio.__name__ + "."):
        importlib.import_module(encontrado.name)
        importados.append(encontrado.name)

    cargados = sorted(PROHIBIDOS & set(sys.modules))

    print("Sonda de aislamiento del dominio")
    print(f"modulos importados: {len(importados)}")
    for nombre in importados:
        print(f"  - {nombre}")
    print(f"prohibidos cargados: {', '.join(cargados) if cargados else 'ninguno'}")

    if cargados:
        print("")
        print("El dominio cargo dependencias que le estan prohibidas.")
        print("Que revisar: los imports de los modulos listados arriba.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
