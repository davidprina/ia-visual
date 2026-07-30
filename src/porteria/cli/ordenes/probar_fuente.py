"""Orden `probar-fuente`: apuntar la herramienta a un video y ver si la cañería está sana.

Es la primera orden del producto que hace algo observable: antes de este plan, un operador
no tenía forma de saber si una fuente entrega cuadros frescos sin abrir un depurador.
Después de este plan, corre una línea y lee en pantalla los fps efectivos contra los
declarados, cuántos cuadros se descartaron y cuál es la antigüedad mediana del cuadro que
recibe.

**Qué mirar en la salida, en orden de importancia:**

1. `frames descartados` en **0** con un consumidor a 5 Hz sobre una fuente a 25 fps es la
   señal de alarma, no la de todo bien: significa que los cuadros se están acumulando en
   algún lado y que la antigüedad crece sin que nadie la vea (Pitfall 7).
2. `antigüedad mediana` creciendo entre dos corridas de distinta duración es el mismo
   problema visto desde el otro lado.
3. `backend` vacío o distinto del esperado explica de entrada un archivo que no abre.

**D-49 a D-51:** orden y opciones en español y sin tildes en los nombres —`--archivo`,
`--segundos`, `--modo`, `--json`—, porque el teclado y el encoding de la consola del
cliente no están garantizados; tildes libres en la ayuda y en la salida. Legible por
personas por defecto, estructurada bajo bandera: un solo comando para los dos públicos, y
las pruebas no parsean texto libre.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Annotated

import typer

from porteria.aplicacion.puertos.salida.fuente_de_video import PerfilDeFlujo
from porteria.infraestructura.video.archivo import (
    FuenteDeArchivo,
    FuenteNoDisponible,
    Modo,
)

#: Frecuencia del consumidor de la sonda. Es la misma con la que se mide el Criterio de
#: Éxito 5, y es deliberadamente **más lenta que cualquier fuente**: un consumidor rápido
#: no descartaría nada y la orden no podría mostrar el dato que más importa.
HZ_DEL_CONSUMIDOR = 5.0

#: Código de salida cuando la fuente no se puede abrir. Distinto de 0 para que un script
#: de despliegue lo detecte, y distinto de 1 para separarlo de un fallo inesperado.
SALIDA_FUENTE_NO_DISPONIBLE = 2


def _formatear_ms(valor: object) -> str:
    """Milisegundos con un decimal, o un guion si todavía no hay medición."""
    if isinstance(valor, (int, float)):
        return f"{float(valor):.1f} ms"
    return "—"


def registrar(app: typer.Typer) -> None:
    """Registra la orden en la aplicación de consola."""

    # Las opciones se declaran con `Annotated` y no con un valor por defecto llamado, que
    # es el estilo de `version.py`: con tipos que no son inmutables —acá `Path` y el enum
    # `Modo`— la forma vieja es una llamada a función en el valor por defecto, que se
    # evalúa una sola vez al importar y es una fuente clásica de estado compartido. Es
    # además el idioma actual de Typer.
    @app.command("probar-fuente")
    def probar_fuente(
        archivo: Annotated[
            Path, typer.Option("--archivo", help="Ruta del archivo de video a probar.")
        ],
        segundos: Annotated[
            float,
            typer.Option(
                "--segundos", help="Cuánto tiempo consumir la fuente antes de informar."
            ),
        ] = 5.0,
        modo: Annotated[
            Modo,
            typer.Option(
                "--modo",
                help="tiempo-real respeta la cadencia del video; velocidad-maxima no espera.",
            ),
        ] = Modo.TIEMPO_REAL,
        estructurado: Annotated[
            bool,
            typer.Option("--json", help="Salida estructurada, para pruebas y herramientas."),
        ] = False,
    ) -> None:
        """Reproduce un archivo de video e informa si la fuente entrega cuadros frescos."""
        fuente = FuenteDeArchivo(archivo, modo=modo)

        try:
            fuente.abrir()
        except FuenteNoDisponible as error:
            # UI-05: lo que se imprime es el mensaje, no la excepción. Un traceback en la
            # consola de una planta sin área de sistemas no le sirve a nadie.
            typer.echo(str(error), err=True)
            raise typer.Exit(code=SALIDA_FUENTE_NO_DISPONIBLE) from None

        try:
            entregas = 0
            periodo_s = 1.0 / HZ_DEL_CONSUMIDOR
            limite_ns = time.perf_counter_ns() + int(segundos * 1_000_000_000)
            while time.perf_counter_ns() < limite_ns and fuente.esta_viva():
                if fuente.tomar_mas_reciente(PerfilDeFlujo.MONITOREO, timeout=periodo_s):
                    entregas += 1
                time.sleep(periodo_s)

            datos: dict[str, object] = dict(fuente.descripcion())
            datos.update(fuente.metricas())
            datos["entregas"] = entregas
            datos["segundos_pedidos"] = segundos
        finally:
            fuente.cerrar()

        if estructurado:
            typer.echo(json.dumps(datos, ensure_ascii=False, indent=2))
            return

        # La ruta completa sí va en la salida legible: la lee quien está sentado frente al
        # equipo. En la estructurada no, para no filtrar el árbol del cliente (T-01-02).
        typer.echo(f"Fuente             {fuente.ruta}")
        typer.echo(f"Backend            {datos['backend'] or '—'}")
        typer.echo(f"Resolución         {datos['resolucion']}")
        typer.echo(f"Códec              {datos['codec'] or '—'}")
        typer.echo(f"Modo               {datos['modo']}")
        typer.echo(f"Fps declarados     {datos['fps_declarados']}")
        typer.echo(f"Fps efectivos      {float(datos['fps_efectivos']):.2f}")  # type: ignore[arg-type]
        typer.echo(f"Frames publicados  {datos['frames_publicados']}")
        typer.echo(f"Frames descartados {datos['frames_descartados']}")
        typer.echo(f"Entregas al consumidor ({HZ_DEL_CONSUMIDOR:.0f} Hz)  {entregas}")
        typer.echo(f"Antigüedad mediana {_formatear_ms(datos['antiguedad_mediana_ms'])}")
        typer.echo(f"Antigüedad última  {_formatear_ms(datos['antiguedad_ultimo_ms'])}")

        if datos["frames_descartados"] == 0:
            typer.echo(
                "\nAtención: no se descartó ningún cuadro con un consumidor más lento "
                "que la fuente. Eso no es una buena señal: si nada se descarta, los "
                "cuadros se están acumulando en algún lado y la antigüedad va a crecer."
            )
