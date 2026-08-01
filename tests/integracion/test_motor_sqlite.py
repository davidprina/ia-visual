"""El motor SQLite del producto: los cuatro PRAGMA, la ruta hostil y la versión de esquema.

**Los PRAGMA se leen, no se suponen.** `create_engine` no falla si el listener `connect`
nunca corre: simplemente la base queda en `journal_mode=delete` y `synchronous=NORMAL`, que
es la configuración con la que un corte de energía se lleva el último commit confirmado.
Una prueba que sólo construyera el motor pasaría en verde con el listener borrado. Por eso
acá se abre una conexión y se lee cada PRAGMA desde la base.

**`synchronous` se afirma en 2 y no en «FULL».** El PRAGMA de lectura devuelve el entero, y
2 es FULL. Afirmar contra el texto que se escribió sería afirmar contra el código propio.

**La ruta con espacios y acentos no es un caso de borde acá** (DIS-06): toda la suite corre
bajo la raíz hostil, así que los sidecar `-wal` y `-shm` de la prueba de abajo se crean
justamente donde el antipatrón de concatenar el prefijo de URL fallaría.
"""

from __future__ import annotations

import pytest
from sqlalchemy.engine import Engine

from porteria.infraestructura.persistencia.sqlite.motor import crear_motor
from porteria.infraestructura.persistencia.sqlite.version_esquema import (
    VERSION_APP,
    VERSION_ESQUEMA,
    BaseMasNuevaQueLaAplicacion,
    Veredicto,
    comprobar,
)
from tests.conftest import RutaHostil

#: Sin interpolación de cadenas: cada consulta es un literal. El PRAGMA no admite
#: parámetros ligados, así que la única defensa contra construir SQL por concatenación es
#: no tener nada que concatenar.
CONSULTAS_PRAGMA = {
    "journal_mode": "PRAGMA journal_mode",
    "synchronous": "PRAGMA synchronous",
    "foreign_keys": "PRAGMA foreign_keys",
    "busy_timeout": "PRAGMA busy_timeout",
}


def leer_pragmas(motor: Engine) -> dict[str, object]:
    """Lee los cuatro PRAGMA **desde la base**, con una conexión real."""
    with motor.connect() as conexion:
        return {
            nombre: conexion.exec_driver_sql(consulta).scalar()
            for nombre, consulta in CONSULTAS_PRAGMA.items()
        }


# --------------------------------------------------------------------------- #
# Los cuatro PRAGMA (D-14)
# --------------------------------------------------------------------------- #


def test_el_motor_de_la_aplicacion_arranca_con_los_cuatro_pragma(
    motor_sqlite: Engine,
) -> None:
    """WAL + FULL + llaves foráneas + espera ante base ocupada, leídos de la base."""
    leidos = leer_pragmas(motor_sqlite)

    assert leidos["journal_mode"] == "wal", (
        "El diario no quedó en WAL. Sin WAL no hay lectura concurrente con la escritura "
        f"y `synchronous=FULL` no significa lo mismo. Leído: {leidos['journal_mode']!r}"
    )
    assert leidos["synchronous"] == 2, (
        "`synchronous` tiene que ser 2 (FULL). Con 1 (NORMAL) SQLite garantiza integridad "
        "pero **no** durabilidad del último commit ante un corte de energía, que es "
        f"justamente lo que D-14 pide. Leído: {leidos['synchronous']!r}"
    )
    assert leidos["foreign_keys"] == 1, (
        "Las llaves foráneas están apagadas en el motor de la aplicación. Sin ellas, una "
        "fila de evidencia puede quedar apuntando a una captura que no existe y nadie se "
        "entera hasta la auditoría."
    )
    assert leidos["busy_timeout"] == 5000, (
        "Sin `busy_timeout`, una base tomada por otra conexión devuelve «database is "
        f"locked» al instante en vez de esperar. Leído: {leidos['busy_timeout']!r}"
    )


def test_el_motor_de_migracion_apaga_las_llaves_foraneas_y_nada_mas(
    ruta_hostil: RutaHostil,
) -> None:
    """`para_migracion=True` cambia **una** cosa: `batch_alter_table` necesita eso y sólo eso."""
    motor = crear_motor(ruta_hostil.ruta_db, para_migracion=True)
    try:
        leidos = leer_pragmas(motor)
    finally:
        motor.dispose()

    assert leidos["foreign_keys"] == 0, (
        "El motor de migración tiene las llaves foráneas encendidas. Con ellas, "
        "`batch_alter_table` falla con «FOREIGN KEY constraint failed [SQL: DROP TABLE "
        "remito]» en cuanto haya una fila que referencie la tabla que se reescribe."
    )
    assert leidos["journal_mode"] == "wal"
    assert leidos["synchronous"] == 2
    assert leidos["busy_timeout"] == 5000


def test_los_dos_motores_se_diferencian_solo_en_las_llaves_foraneas(
    ruta_hostil: RutaHostil,
) -> None:
    """Anti-vacuidad de la prueba anterior: si `para_migracion` no hiciera nada, pasaría igual."""
    aplicacion = crear_motor(ruta_hostil.ruta_db)
    migracion = crear_motor(ruta_hostil.ruta_db, para_migracion=True)
    try:
        de_aplicacion = leer_pragmas(aplicacion)
        de_migracion = leer_pragmas(migracion)
    finally:
        aplicacion.dispose()
        migracion.dispose()

    diferencias = {
        nombre
        for nombre in CONSULTAS_PRAGMA
        if de_aplicacion[nombre] != de_migracion[nombre]
    }
    assert diferencias == {"foreign_keys"}, (
        "Los dos motores tienen que diferenciarse exactamente en `foreign_keys`. "
        f"Diferencias encontradas: {sorted(diferencias)}"
    )


# --------------------------------------------------------------------------- #
# La ruta con espacios y acentos (DIS-06)
# --------------------------------------------------------------------------- #


def test_la_base_y_sus_sidecar_viven_en_la_ruta_con_espacios_y_acentos(
    motor_sqlite: Engine, ruta_hostil: RutaHostil
) -> None:
    """Los `-wal` y `-shm` se crean junto a la base, en la ruta hostil.

    Se afirma **con la conexión abierta**: al cerrar la última, SQLite hace el checkpoint y
    borra los sidecar, así que una comprobación posterior no probaría nada.
    """
    assert " " in ruta_hostil.ruta_db.parts[-2], (
        "La prueba no está corriendo en una ruta con espacios."
    )
    assert any(caracter in str(ruta_hostil.ruta_db) for caracter in "ñáéí"), (
        "La prueba no está corriendo en una ruta con acentos, así que no ejercita DIS-06."
    )

    with motor_sqlite.connect() as conexion:
        conexion.exec_driver_sql("CREATE TABLE sonda (x INTEGER)")
        conexion.exec_driver_sql("INSERT INTO sonda VALUES (1)")
        conexion.commit()

        for sufijo in ("-wal", "-shm"):
            sidecar = ruta_hostil.ruta_db.with_name(ruta_hostil.ruta_db.name + sufijo)
            assert sidecar.exists(), (
                f"No apareció el sidecar «{sidecar.name}» junto a la base. Es la señal de "
                "que el modo WAL no está activo o de que la base se abrió en otra ruta."
            )

    assert ruta_hostil.ruta_db.exists()


# --------------------------------------------------------------------------- #
# Versión de esquema separada de la versión de producto (D-35)
# --------------------------------------------------------------------------- #


def test_una_base_mas_vieja_pide_migrar() -> None:
    assert comprobar("0001", "0002") is Veredicto.MIGRAR


def test_una_base_de_la_misma_version_es_compatible() -> None:
    assert comprobar("0002", "0002") is Veredicto.COMPATIBLE


def test_una_base_mas_nueva_se_niega_a_abrir_nombrando_las_dos_versiones() -> None:
    """El caso de campo: reinstalar desde un instalador guardado sobre datos ya migrados."""
    with pytest.raises(BaseMasNuevaQueLaAplicacion) as capturado:
        comprobar("0007", "0002")

    mensaje = str(capturado.value)
    assert "0007" in mensaje and "0002" in mensaje, (
        "El mensaje tiene que nombrar la versión de la base y la de la aplicación: sin los "
        f"dos números nadie sabe qué versión instalar. Mensaje:\n{mensaje}"
    )


def test_la_version_de_esquema_es_la_que_el_producto_declara_por_defecto() -> None:
    """Sin segundo argumento, se compara contra la versión que trae la aplicación."""
    assert comprobar(VERSION_ESQUEMA) is Veredicto.COMPATIBLE


def test_la_version_de_producto_y_la_de_esquema_son_datos_distintos() -> None:
    """D-35: la base se migra por su cuenta y el producto se versiona por la suya."""
    assert VERSION_APP != VERSION_ESQUEMA, (
        "Si la versión de producto y la de esquema fueran el mismo número, cada release "
        "obligaría a una migración y cada migración obligaría a un release."
    )
    assert VERSION_APP, "La versión de producto no puede quedar vacía."
