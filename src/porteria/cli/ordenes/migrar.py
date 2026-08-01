"""Orden `migrar`: lleva la base del cliente a la versión de esquema de esta aplicación.

El flujo es siempre el mismo y el orden importa: **comprobar la versión → respaldar →
migrar → comprobar la integridad → informar**. Cada paso está antes del siguiente por una
razón operativa concreta:

* comprobar primero evita el peor caso de D-35, que es una aplicación vieja escribiendo
  sobre una base que migró una versión posterior;
* respaldar antes de tocar nada es la red de D-34: la prueba de preservación evita que una
  migración rota llegue al cliente, y la copia es lo que queda por si igual llega;
* comprobar la integridad después es obligatorio porque durante el bloque batch las llaves
  foráneas están apagadas y SQLite no valida nada mientras corre.

**No localiza `alembic.ini`.** El producto se distribuye congelado y ese archivo no viaja en
el paquete instalado; la configuración se arma en memoria apuntando al directorio de
migraciones que sí viaja dentro de `porteria`. Depender del archivo haría que la orden
funcionara en la máquina de desarrollo y fallara en la del cliente, que es el peor lugar
para descubrirlo.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from alembic import command
from alembic.config import Config

from porteria.infraestructura.persistencia import migraciones
from porteria.infraestructura.persistencia.sqlite.motor import crear_motor
from porteria.infraestructura.persistencia.sqlite.respaldo import (
    ResultadoDeRespaldo,
    respaldar,
)
from porteria.infraestructura.persistencia.sqlite.version_esquema import (
    VERSION_APP,
    VERSION_ESQUEMA,
    BaseMasNuevaQueLaAplicacion,
    Veredicto,
    comprobar,
)

#: Código de salida de los errores que el operador puede resolver. Igual que el de la
#: orden `configurar`: 2 es «lo que pediste no se puede hacer y acá está por qué».
SALIDA_ERROR_DE_USO = 2

#: La opción se evalúa una sola vez, al importar, y no en cada invocación. Es el mismo
#: patrón que el plan 01-02 adoptó ante este aviso: un valor por defecto que es una llamada
#: se reevalúa por invocación y es una fuente clásica de estado compartido.
OPCION_BASE_DE_DATOS = typer.Option(
    None, "--base-de-datos", help="Ruta de la base. Por defecto, la del archivo de arranque."
)


def construir_config(ruta_db: Path) -> Config:
    """Arma la configuración de Alembic en memoria, sin depender de `alembic.ini`."""
    config = Config()
    config.set_main_option("script_location", str(Path(migraciones.__file__).parent))
    config.attributes["ruta_db"] = ruta_db
    return config


def version_de_la_base(ruta_db: Path) -> str | None:
    """La revisión en la que está la base, o `None` si nunca se migró.

    Se lee con el motor de la aplicación y no con el de migraciones: es una lectura, y no
    hay ninguna razón para hacerla con las llaves foráneas apagadas.
    """
    if not ruta_db.is_file():
        return None

    motor = crear_motor(ruta_db)
    try:
        with motor.connect() as conexion:
            existe = conexion.exec_driver_sql(
                "SELECT count(*) FROM sqlite_master "
                "WHERE type='table' AND name='alembic_version'"
            ).scalar()
            if not existe:
                return None
            return conexion.exec_driver_sql("SELECT version_num FROM alembic_version").scalar()
    finally:
        # En Windows, una conexión viva impide mover o borrar la base — incluida la
        # restauración del respaldo, que es justo lo que hace falta si esto sale mal.
        motor.dispose()


def _resolver_ruta(base_de_datos: Path | None) -> Path:
    """La ruta explícita si vino, y si no la del archivo de arranque de la capa 1."""
    if base_de_datos is not None:
        return base_de_datos

    from porteria.infraestructura.configuracion.arranque import (
        cargar_configuracion_de_arranque,
    )

    return Path(cargar_configuracion_de_arranque().ruta_base_datos)


def registrar(app: typer.Typer) -> None:
    """Registra la orden en la aplicación de consola."""

    @app.command("migrar")
    def migrar(
        hasta: str = typer.Option(
            "head", "--hasta", help="Revisión objetivo. Por defecto, la última."
        ),
        sin_respaldo: bool = typer.Option(
            False,
            "--sin-respaldo",
            help="Saltea la copia previa. Por defecto SIEMPRE se hace una.",
        ),
        base_de_datos: Path | None = OPCION_BASE_DE_DATOS,
        estructurado: bool = typer.Option(
            False, "--json", help="Salida estructurada, para pruebas y herramientas."
        ),
    ) -> None:
        """Aplica las migraciones pendientes, con copia previa y comprobación final."""
        try:
            ruta_db = _resolver_ruta(base_de_datos)
        except FileNotFoundError as error:
            typer.echo(str(error), err=True)
            raise typer.Exit(SALIDA_ERROR_DE_USO) from error

        version_previa = version_de_la_base(ruta_db)

        # --- 1. La versión, antes de tocar nada (D-35) ------------------------ #
        if version_previa is not None:
            try:
                veredicto = comprobar(version_previa, VERSION_ESQUEMA)
            except BaseMasNuevaQueLaAplicacion as error:
                typer.echo(str(error), err=True)
                raise typer.Exit(SALIDA_ERROR_DE_USO) from error

            if veredicto is Veredicto.COMPATIBLE and hasta == "head":
                _informar_sin_cambios(ruta_db, version_previa, estructurado)
                return

        # --- 2. La copia previa (D-34) ---------------------------------------- #
        copia: ResultadoDeRespaldo | None = None
        motivo_sin_copia: str | None = None

        if sin_respaldo:
            motivo_sin_copia = "se pidió explícitamente con --sin-respaldo"
        elif not ruta_db.is_file():
            motivo_sin_copia = "la base todavía no existe, así que no hay nada que perder"
        else:
            copia = respaldar(ruta_db)

        # --- 3. La migración, con la comprobación de integridad adentro ------- #
        try:
            command.upgrade(construir_config(ruta_db), hasta)
        except Exception as error:  # noqa: BLE001 - se traduce a mensaje de operador
            typer.echo(
                f"La migración falló y la base quedó sin terminar de actualizar.\n{error}\n"
                + (
                    f"La copia previa está en «{copia.ruta}»: restaurarla deja la base "
                    "exactamente como estaba antes de intentar migrar."
                    if copia is not None
                    else "No se hizo copia previa, así que no hay punto de retorno."
                ),
                err=True,
            )
            raise typer.Exit(SALIDA_ERROR_DE_USO) from error

        _informar_resultado(
            ruta_db, version_previa, version_de_la_base(ruta_db), copia, motivo_sin_copia,
            estructurado,
        )


def _informar_sin_cambios(ruta_db: Path, version: str, estructurado: bool) -> None:
    datos = {
        "resultado": "sin_cambios",
        "base_de_datos": str(ruta_db),
        "version_esquema_previa": version,
        "version_esquema_actual": version,
        "version_app": VERSION_APP,
        "revision_aplicada": None,
        "respaldo": None,
        "integridad": "no se comprobó: no se ejecutó ninguna migración",
    }
    if estructurado:
        typer.echo(json.dumps(datos, ensure_ascii=False, indent=2))
        return

    typer.echo(f"La base «{ruta_db}» ya está en la versión de esquema {version}.")
    typer.echo("No hay migraciones pendientes.")


def _informar_resultado(
    ruta_db: Path,
    version_previa: str | None,
    version_actual: str | None,
    copia: ResultadoDeRespaldo | None,
    motivo_sin_copia: str | None,
    estructurado: bool,
) -> None:
    datos = {
        "resultado": "migrada",
        "base_de_datos": str(ruta_db),
        "version_esquema_previa": version_previa,
        "version_esquema_actual": version_actual,
        "version_app": VERSION_APP,
        "revision_aplicada": version_actual,
        "respaldo": (
            {
                "ruta": str(copia.ruta),
                "bytes": copia.bytes_de_la_copia,
                "copias_conservadas": copia.copias_conservadas,
                "bytes_del_conjunto": copia.bytes_del_conjunto,
            }
            if copia is not None
            else None
        ),
        "motivo_sin_respaldo": motivo_sin_copia,
        # `env.py` falla la migración si alguna no queda limpia, así que llegar acá
        # significa que las dos pasaron.
        "integridad": "foreign_key_check y integrity_check limpios",
    }

    if estructurado:
        typer.echo(json.dumps(datos, ensure_ascii=False, indent=2))
        return

    desde = version_previa or "sin migrar"
    typer.echo(f"Base de datos    {ruta_db}")
    typer.echo(f"Esquema          {desde} → {version_actual}")
    typer.echo("Integridad       foreign_key_check y integrity_check limpios")

    if copia is not None:
        typer.echo(f"Copia previa     {copia.ruta}")
        typer.echo(
            f"                 {copia.bytes_de_la_copia} bytes · "
            f"{copia.copias_conservadas} copias conservadas, "
            f"{copia.bytes_del_conjunto} bytes en total"
        )
    else:
        typer.echo(f"Copia previa     no se hizo: {motivo_sin_copia}")
