"""El caso adverso: sin él, la prueba de migración es un espejo del código de migración.

**Por qué esto existe.** `test_migracion_preserva_datos` afirma que `comparar_volcados`
devuelve una lista vacía. Una comparación rota —que devolviera siempre vacío, que comparara
el esquema contra sí mismo, o que se saltara las tablas que cambiaron— haría pasar esa
prueba en verde para siempre, incluida una migración que borra media base. La única forma de
saber que la comparación mide algo es **mostrarla fallando** ante una pérdida real.

Las tres pérdidas que se ejercitan acá son las tres formas en que una migración destruye
datos en la práctica: soltar una columna poblada, cambiar un valor existente y perder filas.
Todas usan **la misma función** `comparar_volcados` que usa el caso feliz; si usaran una
copia propia, esta prueba no diría nada sobre aquélla.
"""

from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from porteria.infraestructura.persistencia.sqlite.modelos import CONVENCION
from porteria.infraestructura.persistencia.sqlite.motor import crear_motor
from tests.migracion.conftest import comparar_volcados, volcar


def _volcar(ruta_db: Path) -> dict:
    motor = crear_motor(ruta_db)
    try:
        return volcar(motor)
    finally:
        motor.dispose()


def test_una_migracion_que_suelta_una_columna_poblada_se_detecta(base_en_0001: Path) -> None:
    """Una revisión de mentira que hace `drop_column` sobre una columna con datos."""
    antes = _volcar(base_en_0001)
    assert any(
        fila["peso_teorico_kg"] is not None for fila in antes["articulo"]
    ), "La siembra no dejó ningún peso cargado: la pérdida no sería observable."

    # El motor de migración, igual que el real: con las llaves encendidas el batch ni
    # siquiera llegaría a soltar la columna y la prueba pasaría por el motivo equivocado.
    motor = crear_motor(base_en_0001, para_migracion=True)
    try:
        with motor.begin() as conexion:
            operaciones = Operations(MigrationContext.configure(conexion))
            with operaciones.batch_alter_table("articulo", naming_convention=CONVENCION) as lote:
                lote.drop_column("peso_teorico_kg")
    finally:
        motor.dispose()

    diferencias = comparar_volcados(antes, _volcar(base_en_0001))

    assert diferencias, (
        "La comparación NO detectó que se soltó una columna poblada. Es el fallo más grave "
        "posible de esta suite: significa que la prueba de preservación pasa en verde ante "
        "una migración que destruye datos."
    )
    assert any("peso_teorico_kg" in diferencia for diferencia in diferencias), (
        f"Se detectó una diferencia pero no la de la columna soltada: {diferencias}"
    )


def test_cambiar_el_valor_de_una_sola_celda_se_detecta(base_en_0001: Path) -> None:
    """La comparación es valor por valor, no un conteo de filas."""
    antes = _volcar(base_en_0001)

    motor = crear_motor(base_en_0001)
    try:
        with motor.begin() as conexion:
            conexion.exec_driver_sql(
                "UPDATE articulo SET peso_teorico_kg = 99.0 WHERE codigo = 'A-1'"
            )
    finally:
        motor.dispose()

    diferencias = comparar_volcados(antes, _volcar(base_en_0001))

    assert diferencias, (
        "Cambió una celda y la comparación no lo vio. Contar filas habría dado igual antes "
        "y después: por eso contar no alcanza."
    )
    assert any("peso_teorico_kg" in diferencia for diferencia in diferencias), (
        f"Diferencias detectadas, pero ninguna nombra la columna alterada: {diferencias}"
    )


def test_perder_filas_se_detecta(base_en_0001: Path) -> None:
    antes = _volcar(base_en_0001)

    motor = crear_motor(base_en_0001)
    try:
        with motor.begin() as conexion:
            conexion.exec_driver_sql("DELETE FROM viaje_remito WHERE remito_id = 'r-2'")
    finally:
        motor.dispose()

    diferencias = comparar_volcados(antes, _volcar(base_en_0001))

    assert any("viaje_remito" in diferencia for diferencia in diferencias), (
        f"Se borraron las filas del remito compartido y no se detectó: {diferencias}"
    )


def test_agregar_una_columna_no_cuenta_como_perdida(base_en_0001: Path) -> None:
    """La contraprueba del criterio: si agregar contara, el caso feliz nunca podría pasar.

    Es lo que distingue una comparación útil de una que sólo exige que nada cambie: una
    migración **tiene** que cambiar el esquema; lo que no puede es perder lo que había.
    """
    antes = _volcar(base_en_0001)

    motor = crear_motor(base_en_0001, para_migracion=True)
    try:
        with motor.begin() as conexion:
            operaciones = Operations(MigrationContext.configure(conexion))
            operaciones.add_column(
                "articulo", sa.Column("columna_nueva", sa.String(10), nullable=True)
            )
    finally:
        motor.dispose()

    assert comparar_volcados(antes, _volcar(base_en_0001)) == [], (
        "Agregar una columna nullable se contó como pérdida de datos. Con ese criterio, "
        "ninguna migración podría pasar nunca la prueba de preservación."
    )
