"""El motor SQLite del producto, con la configuración que hace durable a un commit.

**`synchronous=FULL` y no `NORMAL`.** D-14 pide durabilidad frente a un corte de energía, no
sólo integridad. En modo WAL, `FULL` hace un sync adicional del WAL después de cada commit y
ése es el que garantiza que un commit confirmado sobreviva al corte; con `NORMAL` la base
queda íntegra pero el último commit puede perderse. El costo en tiempo es irrelevante frente
a la escala de una captura —una foto por cámara, unas pocas veces por minuto— y la
alternativa es decirle al portero que la evidencia que el sistema le confirmó no está.

**`busy_timeout=5000`.** Sin él, una base tomada por otra conexión devuelve «database is
locked» al instante. Cinco segundos es más que suficiente para el único proceso escritor de
un puesto de portería y evita que un respaldo en curso haga fallar una captura.

**Cómo se arma la URL.** Se usa `URL.create`, que se ocupa de la ruta de Windows con
espacios y acentos. Concatenar a mano el prefijo de esquema de SQLite con la ruta es el
antipatrón que rompe justamente en la configuración que este producto tiene por diseño
(DIS-06): la ruta de la base la elige el cliente y puede contener espacios, acentos y
separadores. Hay una invariante de código que exige que ese prefijo literal no aparezca en
este archivo.

**`para_migracion=True`: el único motor con las llaves foráneas apagadas.**
`batch_alter_table` de Alembic reescribe la tabla —crear nueva, `INSERT…SELECT`, `DROP`,
`RENAME`— y con las llaves foráneas encendidas el `DROP` falla con
`IntegrityError: FOREIGN KEY constraint failed` en cuanto exista una fila que referencie la
tabla que se está reescribiendo. Las dos soluciones que parecen obvias **no funcionan**, y
esto se reprodujo en vivo:

* emitir el PRAGMA dentro de la transacción de la migración es un **no-op**: SQLite ignora
  el cambio de `foreign_keys` mientras hay una transacción abierta, así que la migración
  parece configurada y no lo está;
* emitirlo antes con `exec_driver_sql` rompe distinto: SQLAlchemy 2.0 hace *autobegin* al
  ejecutar, y la siguiente llamada a `begin()` levanta
  `InvalidRequestError: This connection has already initialized a SQLAlchemy Transaction()`.

Un motor aparte cuyo listener `connect` ya trae las llaves apagadas es limpio, no depende de
trucos de aislamiento, y deja explícito en el código que la migración corre bajo otras
reglas. Que sea un motor distinto es también la razón por la que la aplicación nunca puede
escribir sin validación referencial por accidente: no comparten objeto.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import URL, Engine, create_engine

__all__ = ["crear_motor"]

#: Los tres PRAGMA que los dos motores comparten, como literales.
#:
#: Nada se interpola acá y es deliberado: el PRAGMA no admite parámetros ligados, así que la
#: única forma de que este módulo no pueda construir SQL por concatenación es que no tenga
#: nada que concatenar (T-01-05). Los 5000 ms del `busy_timeout` están en el literal por esa
#: razón y no por descuido.
PRAGMAS_COMUNES = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=FULL",
    "PRAGMA busy_timeout=5000",
)

#: El PRAGMA que distingue al motor de la aplicación del de migraciones.
PRAGMA_LLAVES_ENCENDIDAS = "PRAGMA foreign_keys=ON"
PRAGMA_LLAVES_APAGADAS = "PRAGMA foreign_keys=OFF"


def crear_motor(ruta_db: Path, *, para_migracion: bool = False) -> Engine:
    """Devuelve el `Engine` del producto, ya configurado.

    Args:
        ruta_db: Dónde vive el archivo de la base. Puede tener espacios y acentos.
        para_migracion: `True` sólo para el motor que usa Alembic. Apaga las llaves
            foráneas, que es lo que `batch_alter_table` necesita para poder reescribir una
            tabla referenciada. Ningún otro camino del producto debe usarlo.

    Returns:
        Un `Engine` cuyo listener `connect` aplica los cuatro PRAGMA en **cada** conexión
        nueva del pool. Aplicarlos una sola vez al arrancar no alcanza: son estado por
        conexión, y el pool abre conexiones nuevas cuando le hace falta.
    """
    url = URL.create("sqlite", database=str(ruta_db))
    motor = create_engine(url)

    llaves = PRAGMA_LLAVES_APAGADAS if para_migracion else PRAGMA_LLAVES_ENCENDIDAS
    a_ejecutar = (*PRAGMAS_COMUNES, llaves)

    @event.listens_for(motor, "connect")
    def _aplicar_pragmas(conexion_dbapi, _registro) -> None:  # noqa: ANN001 - firma de SQLAlchemy
        cursor = conexion_dbapi.cursor()
        try:
            for sentencia in a_ejecutar:
                cursor.execute(sentencia)
        finally:
            cursor.close()

    return motor
