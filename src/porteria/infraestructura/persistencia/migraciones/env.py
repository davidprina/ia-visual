"""El entorno de Alembic: motor dedicado, bloques batch y comprobación obligatoria al final.

**El motor de migraciones es otro motor, con las llaves foráneas apagadas.**
`batch_alter_table` reescribe la tabla entera —crear nueva, copiar, soltar la vieja,
renombrar— y con las llaves encendidas el paso de soltar falla en cuanto exista una fila que
referencie la tabla que se reescribe. Reproducido en esta máquina:
`IntegrityError: (sqlite3.IntegrityError) FOREIGN KEY constraint failed`. Por qué las dos
alternativas obvias se descartaron está documentado en `sqlite/motor.py`, con lo que
midieron de verdad.

**`PRAGMA foreign_key_check` e `integrity_check` al terminar no son opcionales.** Con las
llaves apagadas durante el batch, SQLite no valida **nada**: una referencia que quedó
colgando no produce ningún error mientras la migración corre. El final es el único momento en
que se puede detectar, y por eso acá la migración **falla** si alguno de los dos no queda
limpio. Sin esta comprobación, el modo de fallo es una base que migró "bien", abre bien, y
tiene evidencia apuntando a capturas que ya no existen — que es justo lo que un producto de
auditoría no puede permitirse. Es la mitad del Criterio de Éxito 6.

**La ruta de la base no está versionada.** Se resuelve en tiempo de ejecución, en este orden:
el atributo `ruta_db` que pasa quien invoca de forma programática (la orden `migrar` y las
pruebas), la opción `-x ruta_db=…` de la línea de comandos de Alembic, o el archivo de
arranque de la capa 1 (D-30).
"""

from __future__ import annotations

from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy.engine import URL

from porteria.infraestructura.persistencia.sqlite.integridad import comprobar_integridad
from porteria.infraestructura.persistencia.sqlite.modelos import Base
from porteria.infraestructura.persistencia.sqlite.motor import crear_motor

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

#: Lo que `alembic revision --autogenerate` compara contra la base.
target_metadata = Base.metadata


def _resolver_ruta_db() -> Path:
    """De dónde sale la base a migrar, sin que la ruta viva en un archivo versionado."""
    desde_atributo = config.attributes.get("ruta_db")
    if desde_atributo is not None:
        return Path(desde_atributo)

    desde_linea_de_comandos = context.get_x_argument(as_dictionary=True).get("ruta_db")
    if desde_linea_de_comandos:
        return Path(desde_linea_de_comandos)

    # Import diferido: el archivo de arranque sólo hace falta en el producto real, y
    # exigirlo acá haría que las pruebas y la orden `migrar` dependieran de que exista.
    from porteria.infraestructura.configuracion.arranque import (
        cargar_configuracion_de_arranque,
    )

    return Path(cargar_configuracion_de_arranque().ruta_base_datos)


def ejecutar_migraciones_sin_conexion() -> None:
    """Modo sin conexión: emite el SQL en vez de aplicarlo.

    Sirve para que un cliente con políticas estrictas pueda revisar lo que se va a ejecutar
    antes de ejecutarlo. No corre las comprobaciones de integridad porque no hay base contra
    la cual correrlas.
    """
    context.configure(
        # `URL.create` y no concatenación: la ruta puede tener espacios y acentos (DIS-06).
        url=URL.create("sqlite", database=str(_resolver_ruta_db())),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def ejecutar_migraciones_con_conexion() -> None:
    """El camino normal: motor dedicado, batch, y comprobación obligatoria al terminar."""
    ruta_db = _resolver_ruta_db()
    motor = crear_motor(ruta_db, para_migracion=True)

    try:
        with motor.connect() as conexion:
            context.configure(
                connection=conexion,
                target_metadata=target_metadata,
                # Sin esto, `alembic revision --autogenerate` produce ALTER que SQLite no
                # soporta y la migración generada no corre en el cliente.
                render_as_batch=True,
            )

            with context.begin_transaction():
                context.run_migrations()

            # Fuera de la transacción de la migración: comprobar dentro compararía contra
            # un estado que todavía se puede deshacer, y lo que interesa es lo que quedó.
            comprobar_integridad(conexion)
    finally:
        # En Windows, mientras el pool tenga una conexión abierta nadie puede mover ni
        # borrar la base — ni restaurar el respaldo, que es justo lo que hace falta si la
        # migración salió mal.
        motor.dispose()


if context.is_offline_mode():
    ejecutar_migraciones_sin_conexion()
else:
    ejecutar_migraciones_con_conexion()
