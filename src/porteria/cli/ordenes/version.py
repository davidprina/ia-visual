"""Orden `version`: informa qué versión de portería está instalada.

Es la orden mínima que ejercita el contrato de descubrimiento de `cli/app.py`
(un módulo por orden, con una función `registrar(app)`) y la primera respuesta
de soporte remoto: antes de diagnosticar nada hay que saber qué está corriendo.
"""

import json
import platform
import sys
from importlib import metadata

import typer


def registrar(app: typer.Typer) -> None:
    """Registra la orden en la aplicación de consola."""

    @app.command("version")
    def version(
        estructurado: bool = typer.Option(
            False, "--json", help="Salida estructurada, para pruebas y herramientas."
        ),
    ) -> None:
        """Muestra la versión instalada de portería y del intérprete."""
        try:
            instalada = metadata.version("porteria")
        except metadata.PackageNotFoundError:
            instalada = "no instalada"

        datos = {
            "producto": "porteria",
            "version": instalada,
            "python": platform.python_version(),
            "plataforma": platform.platform(),
            "ejecutable": sys.executable,
        }

        # D-51: legible por personas por defecto, estructurada bajo bandera.
        if estructurado:
            typer.echo(json.dumps(datos, ensure_ascii=False, indent=2))
            return

        typer.echo(f"Portería {datos['version']}")
        typer.echo(f"Python   {datos['python']}")
        typer.echo(f"Sistema  {datos['plataforma']}")
