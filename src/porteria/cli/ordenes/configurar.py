"""Orden `configurar`: ver y cambiar los parámetros de operación, dejando rastro.

Es la superficie de la capa 2 de D-30 mientras no exista la interfaz gráfica, y sobrevive
después como herramienta de diagnóstico del producto vendido (D-49): «escribí esto y
leeme lo que sale» es la diferencia entre resolver por teléfono y viajar a la planta.

**Lo que esta orden hace y lo que deliberadamente no hace.** Muestra las siete claves de la
capa 2 con su valor vigente, quién lo cambió y cuándo, y permite cambiar una dejando el
rastro. **No lee ni escribe credenciales**: las de PALJET y la balanza viven en una tabla
aparte (plan 01-10), y el archivo de arranque de la capa 1 no tiene dónde ponerlas.

**Por qué `--listar` funciona incluso sin archivo de arranque.** Quien está instalando el
producto necesita ver qué claves existen justo en el momento en que todavía no configuró
nada. Fallar ahí sería lo peor de los dos mundos, así que se muestran los valores del
catálogo y se dice de dónde salen. Escribir, en cambio, sí exige la base: no hay dónde
dejar el rastro.

**D-49 a D-51:** orden y opciones en español y sin tildes en los nombres —`--listar`,
`--clave`, `--valor`, `--autor`, `--json`—, porque el teclado y la codificación de la
consola del cliente no están garantizados; tildes libres en la ayuda y en la salida.
Legible por personas por defecto, estructurada bajo bandera, y la estructurada **no lleva
rutas absolutas** (T-01-02): un volcado que se pega en un correo de soporte no tiene por
qué revelar el árbol de directorios del cliente.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import typer
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine
from sqlalchemy.exc import SQLAlchemyError

from porteria.aplicacion.puertos.salida.configuracion import ValorDeConfiguracion
from porteria.infraestructura.configuracion.arranque import (
    ArchivoDeArranqueIlegible,
    ConfiguracionDeArranqueAusente,
    RaizDeEvidenciaDemasiadoLarga,
    cargar_configuracion_de_arranque,
)
from porteria.infraestructura.configuracion.en_base import (
    CATALOGO,
    NOMBRE_DE_TIPO,
    AutorRequerido,
    ClaveDesconocida,
    ConfiguracionEnBase,
    catalogo_como_valores,
    convertir_desde_texto,
)
from porteria.infraestructura.runtime.reloj import RelojDelProceso

#: Código de salida ante entrada inválida o falta de configuración. Distinto de 0 para que
#: un script de despliegue lo detecte, y distinto de 1 para separarlo de un fallo
#: inesperado. Es el mismo criterio que usa `probar-fuente`.
SALIDA_ERROR_DE_USO = 2

NOTA_DEL_CATALOGO = (
    "Estos son los valores por defecto del producto: todavía no hay una base donde se "
    "haya guardado un cambio."
)

NOTA_DE_LA_BASE = (
    "Los valores salen de la base. Las claves sin autor nunca se cambiaron y muestran el "
    "valor por defecto del producto."
)


@dataclass(frozen=True, slots=True)
class _Entorno:
    """Lo que la orden necesita para trabajar, más por qué falta lo que falta.

    El `motor` viaja aparte de la `configuracion` porque hay que **soltarlo** al terminar:
    mientras el pool tenga una conexión abierta, Windows no deja borrar ni mover el archivo
    de la base, y una herramienta de diagnóstico que traba la base que diagnostica es un
    defecto y no un detalle.
    """

    configuracion: ConfiguracionEnBase | None
    motor: Engine | None
    ruta_base: Path | None
    motivo: str


def _abrir_configuracion() -> _Entorno:
    """Arma la configuración de la base, o explica por qué no se pudo.

    No crea la base si no existe: que `--listar` deje un archivo vacío tirado en el disco
    del cliente como efecto secundario de una consulta sería una sorpresa desagradable.

    El motor se construye acá de forma provisional. El dueño de `crear_motor` es el plan
    01-05 y quien lo arma y lo inyecta es el composition root del plan 01-07; cuando eso
    exista, esta función se reduce a pedirle la pieza ya construida.
    """
    try:
        arranque = cargar_configuracion_de_arranque()
    except (
        ConfiguracionDeArranqueAusente,
        ArchivoDeArranqueIlegible,
        RaizDeEvidenciaDemasiadoLarga,
    ) as error:
        return _Entorno(None, None, None, str(error))

    if not arranque.ruta_base_datos.is_file():
        return _Entorno(
            None,
            None,
            arranque.ruta_base_datos,
            f"La base «{arranque.ruta_base_datos}» todavía no existe. Qué hacer: corré el "
            "asistente de primer arranque para crearla.",
        )

    motor = create_engine(URL.create("sqlite", database=str(arranque.ruta_base_datos)))
    return _Entorno(
        ConfiguracionEnBase(motor, RelojDelProceso()),
        motor,
        arranque.ruta_base_datos,
        "",
    )


def _listado(
    configuracion: ConfiguracionEnBase | None,
) -> tuple[dict[str, ValorDeConfiguracion], str, str]:
    """Devuelve el listado, su origen y la nota que lo explica."""
    if configuracion is None:
        return catalogo_como_valores(), "catalogo", NOTA_DEL_CATALOGO

    try:
        return dict(configuracion.listar()), "base", NOTA_DE_LA_BASE
    except SQLAlchemyError:
        # La base existe pero todavía no tiene la tabla: es una instalación a medio
        # preparar, no un error del operador.
        return (
            catalogo_como_valores(),
            "catalogo",
            "La base existe pero todavía no tiene la tabla de configuración. "
            + NOTA_DEL_CATALOGO,
        )


def _como_diccionario(listado: dict[str, ValorDeConfiguracion]) -> dict[str, Any]:
    """La forma estructurada de una clave. Sin rutas: T-01-02."""
    return {
        nombre: {
            "valor": valor.valor,
            "por_defecto": CATALOGO[nombre].por_defecto,
            "tipo": NOMBRE_DE_TIPO.get(CATALOGO[nombre].tipo, CATALOGO[nombre].tipo.__name__),
            "cambiado_por": valor.cambiado_por,
            "cambiado_en_utc_iso": valor.cambiado_en_utc_iso,
            "es_valor_por_defecto": valor.es_valor_por_defecto,
            "ayuda": CATALOGO[nombre].ayuda,
        }
        for nombre, valor in listado.items()
    }


def _mostrar_legible(
    listado: dict[str, ValorDeConfiguracion],
    nota: str,
    ruta_base: Path | None,
    motivo: str,
) -> None:
    """La salida que lee quien está sentado frente al equipo: acá sí va la ruta."""
    typer.echo("Configuración de portería")
    if ruta_base is not None:
        typer.echo(f"Base de datos      {ruta_base}")
    typer.echo("")

    for nombre in sorted(listado):
        valor = listado[nombre]
        typer.echo(f"{nombre}")
        typer.echo(f"  Valor            {json.dumps(valor.valor, ensure_ascii=False)}")
        if valor.es_valor_por_defecto:
            typer.echo("  Cambiado por     — (nunca se cambió)")
        else:
            typer.echo(f"  Cambiado por     {valor.cambiado_por}")
            typer.echo(f"  Cambiado el      {valor.cambiado_en_utc_iso}")
        typer.echo(f"  Qué es           {CATALOGO[nombre].ayuda}")
        typer.echo("")

    typer.echo(nota)
    if motivo:
        typer.echo("")
        typer.echo(motivo)


def _fallar(mensaje: str) -> None:
    """Imprime el mensaje y termina con el código de uso indebido.

    UI-05: lo que se imprime es el mensaje, no la excepción. Un traceback en la consola de
    una planta sin área de sistemas no le sirve a nadie.
    """
    typer.echo(mensaje, err=True)
    raise typer.Exit(code=SALIDA_ERROR_DE_USO)


def _ejecutar(
    entorno: _Entorno,
    listar: bool,
    clave: str | None,
    valor: str | None,
    autor: str | None,
    estructurado: bool,
) -> None:
    """El cuerpo de la orden, separado para que el motor se suelte pase lo que pase."""
    configuracion = entorno.configuracion

    if listar and (clave is not None or valor is not None):
        _fallar(
            "No se puede listar y cambiar en la misma corrida: --listar muestra, "
            "--clave y --valor cambian. Corré una cosa y después la otra."
        )

    # Sin clave ni valor, la acción es mostrar. `--listar` lo hace explícito, pero no hace
    # falta para que la orden sea útil de entrada.
    if clave is None and valor is None:
        registros, origen, nota = _listado(configuracion)
        if estructurado:
            typer.echo(
                json.dumps(
                    {
                        "origen": origen,
                        "nota": nota,
                        "claves": _como_diccionario(registros),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return
        _mostrar_legible(registros, nota, entorno.ruta_base, entorno.motivo)
        return

    if clave is None or valor is None:
        _fallar(
            "Para cambiar un parámetro hacen falta las tres opciones: --clave, --valor y "
            "--autor. Para ver qué claves existen, corré:\n"
            "  porteria configurar --listar"
        )

    if not autor or not autor.strip():
        _fallar(
            "Falta --autor. Un cambio de configuración es un hecho auditable, no un "
            "ajuste anónimo: cada captura guarda cuál era la ventana vigente en su "
            "momento y hay que poder explicar por qué cambió.\n"
            f"  porteria configurar --clave {clave} --valor {valor} --autor «tu nombre»"
        )

    try:
        convertido = convertir_desde_texto(str(clave), str(valor))
    except ClaveDesconocida as error:
        # `KeyError` agrega comillas al convertirse a texto, así que se toma el argumento.
        _fallar(str(error.args[0]))
    except ValueError as error:
        _fallar(str(error))

    if configuracion is None:
        _fallar(
            "No se puede cambiar la configuración todavía: no hay base donde dejar el "
            f"rastro del cambio.\n{entorno.motivo}"
        )
        return

    try:
        configuracion.escribir(str(clave), convertido, autor=str(autor))
    except (AutorRequerido, ValueError) as error:
        _fallar(str(error))
    except SQLAlchemyError as error:
        _fallar(
            f"No se pudo guardar el cambio en la base: {error}\nQué revisar: que la base "
            "exista y que la aplicación tenga permiso de escritura sobre ella."
        )

    if estructurado:
        typer.echo(
            json.dumps(
                {"clave": clave, "valor": convertido, "cambiado_por": str(autor).strip()},
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    typer.echo(
        f"«{clave}» quedó en {json.dumps(convertido, ensure_ascii=False)}, cambiado por "
        f"{str(autor).strip()}."
    )


def registrar(app: typer.Typer) -> None:
    """Registra la orden en la aplicación de consola."""

    # Las opciones van con `Annotated` y no con un valor por defecto llamado: con tipos
    # que no son inmutables la forma vieja es una llamada a función en el valor por
    # defecto, que se evalúa una sola vez al importar. Es el mismo criterio que
    # `probar-fuente`.
    @app.command("configurar")
    def configurar(
        listar: Annotated[
            bool,
            typer.Option("--listar", help="Muestra las claves con su valor y su rastro."),
        ] = False,
        clave: Annotated[
            str | None, typer.Option("--clave", help="Clave a cambiar.")
        ] = None,
        valor: Annotated[
            str | None, typer.Option("--valor", help="Valor nuevo para la clave.")
        ] = None,
        autor: Annotated[
            str | None,
            typer.Option("--autor", help="Quién hace el cambio. Obligatorio al escribir."),
        ] = None,
        estructurado: Annotated[
            bool,
            typer.Option("--json", help="Salida estructurada, para pruebas y herramientas."),
        ] = False,
    ) -> None:
        """Muestra y cambia los parámetros de operación, dejando quién y cuándo."""
        entorno = _abrir_configuracion()
        try:
            _ejecutar(entorno, listar, clave, valor, autor, estructurado)
        finally:
            # Mientras el pool tenga una conexión abierta, Windows no deja borrar ni mover
            # el archivo de la base. Una herramienta de diagnóstico no puede dejar tomada
            # la base que diagnostica.
            if entorno.motor is not None:
                entorno.motor.dispose()
