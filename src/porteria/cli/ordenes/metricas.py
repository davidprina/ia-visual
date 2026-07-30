"""Orden `metricas`: vuelca las métricas de las fuentes vivas de este proceso (D-17).

**El límite, dicho de frente en la propia salida.** Las métricas viven en memoria y se
pierden al cerrar el proceso: es la contrapartida aceptada de no escribir nada en el camino
crítico de la captura. Una consola nueva no ve las fuentes de otra, y por eso el volcado
vacío **explica por qué está vacío** en vez de mostrar una fila de ceros. Un cero que se lee
como "todo bien" cuando en realidad significa "no estoy mirando nada" es peor que no tener
la orden: es una herramienta de diagnóstico que miente hacia abajo.

El muestreo periódico a la base para diagnóstico retrospectivo está diferido fuera de v1
a propósito (T-01-16, riesgo aceptado).
"""

from __future__ import annotations

import json

import typer

from porteria.infraestructura.video.metricas import REGISTRO_DEL_PROCESO

#: Orden en que se muestran las columnas. `frames_descartados` va primero entre los
#: contadores porque es el número que delata el problema (Pitfall 7): en 0 con un
#: consumidor más lento que la fuente significa que la latencia se acumula en otro lado.
COLUMNAS = (
    ("frames_descartados", "Descartados"),
    ("frames_publicados", "Publicados"),
    ("frames_consumidos", "Consumidos"),
    ("fps_efectivos", "Fps efectivos"),
    ("antiguedad_mediana_ms", "Antigüedad mediana (ms)"),
    ("antiguedad_ultimo_ms", "Antigüedad última (ms)"),
    ("reconexiones", "Reconexiones"),
    ("ocupado", "Con cuadro disponible"),
)

NOTA_DE_ALCANCE = (
    "Las métricas viven en memoria y son de este proceso: una consola nueva no ve las "
    "fuentes abiertas por otra (D-17)."
)


def _formatear(valor: object) -> str:
    """Un valor listo para mostrar, con el guion como ausencia explícita."""
    if valor is None:
        return "—"
    if isinstance(valor, bool):
        return "sí" if valor else "no"
    if isinstance(valor, float):
        return f"{valor:.2f}"
    return str(valor)


def registrar(app: typer.Typer) -> None:
    """Registra la orden en la aplicación de consola."""

    @app.command("metricas")
    def metricas(
        estructurado: bool = typer.Option(
            False, "--json", help="Salida estructurada, para pruebas y herramientas."
        ),
    ) -> None:
        """Muestra las métricas de las fuentes de video abiertas en este proceso."""
        fuentes = REGISTRO_DEL_PROCESO.instantanea()

        if estructurado:
            typer.echo(
                json.dumps(
                    {"fuentes": fuentes, "nota": NOTA_DE_ALCANCE},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return

        if not fuentes:
            typer.echo("No hay ninguna fuente de video abierta en este proceso.")
            typer.echo(NOTA_DE_ALCANCE)
            typer.echo(
                "Para ver métricas de una fuente, corré:\n"
                "  porteria probar-fuente --archivo «ruta del video»"
            )
            return

        for nombre, volcado in sorted(fuentes.items()):
            typer.echo(f"Fuente «{nombre}»")
            for clave, etiqueta in COLUMNAS:
                typer.echo(f"  {etiqueta:<26}{_formatear(volcado.get(clave))}")
            typer.echo("")
        typer.echo(NOTA_DE_ALCANCE)
