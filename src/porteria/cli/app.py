"""Punto de entrada de la línea de comandos, en español (D-49, D-50, D-51)."""

import sys

# Pitfall 8: la consola de Windows es cp1252 y una CLI en español revienta con
# UnicodeEncodeError. Esto va ANTES de importar Typer, y es la única vía que
# sobrevive al empaquetado con PyInstaller sin depender del entorno del cliente.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

import importlib  # noqa: E402
import pkgutil  # noqa: E402

import typer  # noqa: E402
import typer.rich_utils as ru  # noqa: E402

import porteria.cli.ordenes  # noqa: E402

# D-50: la ayuda generada por Typer/Click viene en inglés. Estas constantes son
# de módulo y se pueden reemplazar; verificado que existen en typer 0.27.0.
ru.OPTIONS_PANEL_TITLE = "Opciones"
ru.COMMANDS_PANEL_TITLE = "Órdenes"
ru.ARGUMENTS_PANEL_TITLE = "Argumentos"
ru.ERRORS_PANEL_TITLE = "Error"
ru.ABORTED_TEXT = "Cancelado."
ru.REQUIRED_LONG_STRING = "[obligatorio]"
ru.DEFAULT_STRING = "por defecto: {}"

app = typer.Typer(add_completion=False, help="Herramienta de diagnóstico de portería.")


@app.callback()
def _principal() -> None:
    # Sin esta retrollamada, Typer colapsa la aplicación en su única orden cuando
    # sólo hay una registrada, y `porteria version` deja de existir como orden.
    # Declararla fija la forma de la consola: siempre un grupo de órdenes, tenga
    # una o veinte. Sin docstring a propósito: la ayuda sale de Typer(help=...).
    pass


_ordenes_registradas = False


def _registrar_ordenes() -> None:
    """Descubre los módulos de `porteria.cli.ordenes` y registra cada orden.

    Contrato de extensión: cada módulo de `cli/ordenes/` expone una función
    `registrar(app)`. Ningún plan posterior edita este archivo; agregar una orden
    es crear un módulo nuevo. Idempotente: registrar dos veces no duplica órdenes.
    """
    global _ordenes_registradas
    if _ordenes_registradas:
        return
    _ordenes_registradas = True

    for modulo in pkgutil.iter_modules(porteria.cli.ordenes.__path__):
        if modulo.name.startswith("_"):
            continue
        cargado = importlib.import_module(f"{porteria.cli.ordenes.__name__}.{modulo.name}")
        registrar = getattr(cargado, "registrar", None)
        if registrar is None:
            raise RuntimeError(
                f"El módulo de orden «{modulo.name}» no expone una función registrar(app). "
                "Revisá que el archivo defina «def registrar(app)» como pide el contrato "
                "de cli/ordenes/."
            )
        registrar(app)


_registrar_ordenes()


def main() -> None:
    """Arranca la línea de comandos."""
    _registrar_ordenes()
    app()


if __name__ == "__main__":
    main()
