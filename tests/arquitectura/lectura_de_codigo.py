"""Normaliza el texto de un archivo antes de buscarle una invariante.

El problema que resuelve, con un ejemplo real de este repositorio: `tests/conftest.py`
declara en su docstring **por qué no** usa `tmp_path_factory`. Una invariante que exija
"cero coincidencias de `tmp_path_factory`" falla contra esa prosa, aunque el código
cumpla. Si en cambio se busca sobre el texto crudo, la única salida es dejar de
explicar las decisiones —y las decisiones no explicadas se revierten.

La regla, entonces: **la prosa no cuenta como código.** Se descartan los comentarios y
los docstrings, y se conserva todo lo demás.

Lo que NO se descarta, y es deliberado: los literales de cadena que no son docstrings.
Varias invariantes de la fase buscan patrones que viven dentro de una cadena —por
ejemplo `reconfigure(encoding="utf-8"` en el punto de entrada de la consola—, así que
borrar todas las cadenas volvería inverificable justo lo que hay que verificar.

El blanqueo respeta la numeración de líneas: cada carácter descartado se reemplaza por
un espacio en su lugar. Eso es lo que permite que una invariante acotada a las primeras
N líneas siga midiendo las primeras N líneas del archivo real.
"""

from __future__ import annotations

import ast
import io
import tokenize
from pathlib import Path

#: Extensiones que se analizan como código Python.
EXTENSIONES_PYTHON = frozenset({".py", ".pyi"})


def sin_comentarios_de_linea(fuente: str) -> str:
    """Descarta las líneas que empiezan por `#`.

    Es la normalización de los archivos que no son Python (TOML, YAML, INI), donde el
    comentario de línea es la única forma de prosa.
    """
    return "\n".join(
        linea for linea in fuente.splitlines() if not linea.lstrip().startswith("#")
    )


def _rangos_de_docstring(fuente: str) -> list[tuple[int, int, int, int]]:
    """Ubica los docstrings de módulo, clase y función, con fila y columna."""
    try:
        arbol = ast.parse(fuente)
    except SyntaxError:
        return []

    con_docstring = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    rangos: list[tuple[int, int, int, int]] = []

    for nodo in ast.walk(arbol):
        if not isinstance(nodo, con_docstring):
            continue
        cuerpo = getattr(nodo, "body", [])
        if not cuerpo:
            continue
        primero = cuerpo[0]
        if (
            isinstance(primero, ast.Expr)
            and isinstance(primero.value, ast.Constant)
            and isinstance(primero.value.value, str)
            and primero.end_lineno is not None
            and primero.end_col_offset is not None
        ):
            rangos.append(
                (
                    primero.lineno,
                    primero.col_offset,
                    primero.end_lineno,
                    primero.end_col_offset,
                )
            )

    return rangos


def _rangos_de_comentario(fuente: str) -> list[tuple[int, int, int, int]]:
    """Ubica los comentarios `#`, incluidos los que van al final de una línea."""
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(fuente).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return []

    return [
        (token.start[0], token.start[1], token.end[0], token.end[1])
        for token in tokens
        if token.type == tokenize.COMMENT
    ]


def _blanquear(fuente: str, rangos: list[tuple[int, int, int, int]]) -> str:
    """Reemplaza por espacios los rangos indicados, conservando las líneas."""
    matriz = [list(linea) for linea in fuente.splitlines()]

    for fila_inicial, columna_inicial, fila_final, columna_final in rangos:
        for numero in range(fila_inicial, fila_final + 1):
            indice = numero - 1
            if not 0 <= indice < len(matriz):
                continue
            caracteres = matriz[indice]
            desde = columna_inicial if numero == fila_inicial else 0
            hasta = columna_final if numero == fila_final else len(caracteres)
            for posicion in range(desde, min(hasta, len(caracteres))):
                caracteres[posicion] = " "

    return "\n".join("".join(fila) for fila in matriz)


def codigo_sin_prosa(fuente: str) -> str:
    """Devuelve el código Python con comentarios y docstrings blanqueados."""
    rangos = _rangos_de_docstring(fuente) + _rangos_de_comentario(fuente)
    return _blanquear(fuente, rangos)


def normalizar_para_invariante(fuente: str, ruta: Path) -> str:
    """Normaliza según el tipo de archivo: Python por sintaxis, el resto por línea."""
    if Path(ruta).suffix.lower() in EXTENSIONES_PYTHON:
        return codigo_sin_prosa(fuente)
    return sin_comentarios_de_linea(fuente)
