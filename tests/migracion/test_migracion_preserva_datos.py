"""La mitad «migración» del Criterio de Éxito 6: sembrar, respaldar, migrar y comparar.

El orden que la estrategia de validación fija, y que estas pruebas siguen literalmente:
**sembrar en la versión anterior con los casos feos → copia previa → migrar → comparar fila
por fila → `PRAGMA foreign_key_check` → `PRAGMA integrity_check`**.

**Contar filas no alcanza.** Una migración puede conservar la cantidad y arruinar el
contenido: un `INSERT…SELECT` con las columnas cambiadas de orden preserva el conteo y
mezcla los datos entre columnas. El cliente actualiza sobre años de evidencia y no hay
segunda oportunidad, así que la comparación es valor por valor.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from porteria.infraestructura.persistencia.sqlite.integridad import (
    MigracionDejoLaBaseInconsistente,
    comprobar_integridad,
)
from porteria.infraestructura.persistencia.sqlite.motor import crear_motor
from porteria.infraestructura.persistencia.sqlite.respaldo import respaldar
from tests.migracion.conftest import (
    NUMERO_DE_REMITO_HOSTIL,
    PATENTE_HOSTIL,
    comparar_volcados,
    migrar_a,
    volcar,
)


def _volcar_con_motor_propio(ruta_db: Path) -> dict:
    """Vuelca soltando el motor: en Windows una conexión viva traba el archivo."""
    motor = crear_motor(ruta_db)
    try:
        return volcar(motor)
    finally:
        motor.dispose()


def test_la_migracion_preserva_los_datos_fila_por_fila(base_en_0001: Path) -> None:
    antes = _volcar_con_motor_propio(base_en_0001)
    assert antes["remito"], "La siembra no dejó remitos: la prueba no verificaría nada."

    migrar_a(base_en_0001, "0002")
    despues = _volcar_con_motor_propio(base_en_0001)

    diferencias = comparar_volcados(antes, despues)
    assert diferencias == [], (
        "La migración perdió o alteró datos:\n" + "\n".join(f"  - {d}" for d in diferencias)
    )


def test_la_migracion_deja_la_base_integra_y_sin_referencias_colgadas(
    base_en_0001: Path,
) -> None:
    """Con las llaves foráneas apagadas durante el batch, ésta es la única red que queda."""
    migrar_a(base_en_0001, "0002")

    motor = crear_motor(base_en_0001)
    try:
        with motor.connect() as conexion:
            violaciones = list(conexion.exec_driver_sql("PRAGMA foreign_key_check"))
            estado = conexion.exec_driver_sql("PRAGMA integrity_check").scalar()
    finally:
        motor.dispose()

    assert violaciones == [], f"Quedaron referencias colgadas: {violaciones}"
    assert estado == "ok", f"`integrity_check` devolvió «{estado}» en vez de «ok»."


def test_el_peso_teorico_nulo_sigue_siendo_nulo_despues_de_migrar(base_en_0001: Path) -> None:
    """Si se hubiera convertido en 0.0, la diferencia contra la balanza sería falsa (D-31)."""
    migrar_a(base_en_0001, "0002")

    motor = crear_motor(base_en_0001)
    try:
        with motor.connect() as conexion:
            nulos = conexion.exec_driver_sql(
                "SELECT count(*) FROM articulo WHERE peso_teorico_kg IS NULL"
            ).scalar()
            ceros = conexion.exec_driver_sql(
                "SELECT count(*) FROM articulo WHERE peso_teorico_kg = 0.0"
            ).scalar()
    finally:
        motor.dispose()

    assert nulos == 2, f"Se esperaban 2 pesos ausentes y hay {nulos}."
    assert ceros == 0, (
        "Un peso ausente se convirtió en 0.0. Un cero es un peso real y legítimo, así que "
        "la ausencia se vuelve indistinguible de un peso conocido de cero kilos."
    )


def test_el_texto_con_enie_espacios_y_acentos_sobrevive_caracter_por_caracter(
    base_en_0001: Path,
) -> None:
    migrar_a(base_en_0001, "0002")

    motor = crear_motor(base_en_0001)
    try:
        with motor.connect() as conexion:
            numero = conexion.exec_driver_sql(
                "SELECT numero FROM remito WHERE id = 'r-2'"
            ).scalar()
            patente = conexion.exec_driver_sql(
                "SELECT patente FROM viaje WHERE id = 'v-1'"
            ).scalar()
    finally:
        motor.dispose()

    assert numero == NUMERO_DE_REMITO_HOSTIL
    assert patente == PATENTE_HOSTIL, (
        "La patente se normalizó al migrar. Se guarda cruda a propósito: es el dato que "
        "permite auditar después qué devolvió el ERP."
    )


def test_la_relacion_muchas_a_muchas_sobrevive_a_la_reescritura_de_la_tabla(
    base_en_0001: Path,
) -> None:
    """`remito` se reescribe entera en el bloque batch y `viaje_remito` la referencia."""
    migrar_a(base_en_0001, "0002")

    motor = crear_motor(base_en_0001)
    try:
        with motor.connect() as conexion:
            del_viaje_1 = conexion.exec_driver_sql(
                "SELECT count(*) FROM viaje_remito WHERE viaje_id = 'v-1'"
            ).scalar()
            viajes_del_compartido = conexion.exec_driver_sql(
                "SELECT count(*) FROM viaje_remito WHERE remito_id = 'r-2'"
            ).scalar()
    finally:
        motor.dispose()

    assert del_viaje_1 == 3, "El viaje con tres remitos perdió alguno."
    assert viajes_del_compartido == 2, "El remito compartido dejó de estar en los dos viajes."


def test_la_migracion_agrego_la_columna_nueva(base_en_0001: Path) -> None:
    """Anti-vacuidad: si la migración no hubiera hecho nada, todo lo de arriba pasaría igual."""
    migrar_a(base_en_0001, "0002")

    motor = crear_motor(base_en_0001)
    try:
        with motor.connect() as conexion:
            columnas = {
                str(fila[1]): int(fila[3])
                for fila in conexion.exec_driver_sql("PRAGMA table_info('remito')")
            }
    finally:
        motor.dispose()

    assert "creado_en_utc" in columnas, "La revisión 0002 no agregó la columna."
    assert columnas["numero"] == 1, (
        "`numero` tendría que haber quedado NOT NULL: es la parte de la revisión que "
        "obliga a reescribir la tabla, o sea el camino batch que DIS-05 verifica."
    )


# --------------------------------------------------------------------------- #
# La copia previa (D-34)
# --------------------------------------------------------------------------- #


def test_el_respaldo_previo_existe_es_abrible_y_tiene_las_filas_de_antes(
    base_en_0001: Path,
) -> None:
    """La red por si una migración rota llega igual al cliente."""
    antes = _volcar_con_motor_propio(base_en_0001)

    resultado = respaldar(base_en_0001)
    migrar_a(base_en_0001, "0002")

    assert resultado.ruta.is_file(), "El respaldo no quedó en disco."
    assert resultado.bytes_de_la_copia > 0, "El respaldo quedó vacío."

    # Se abre con sqlite3 directo: si sólo se pudiera abrir con el motor del producto, no
    # sería un respaldo utilizable por alguien que viene a rescatar los datos.
    conexion = sqlite3.connect(resultado.ruta)
    try:
        filas = conexion.execute("SELECT count(*) FROM remito").fetchone()[0]
        version = conexion.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        columnas = [f[1] for f in conexion.execute("PRAGMA table_info('remito')")]
    finally:
        conexion.close()

    assert filas == len(antes["remito"]), "El respaldo no tiene las filas de antes de migrar."
    assert version == "0001", (
        f"El respaldo quedó en la revisión {version}: se tomó después de migrar y no antes, "
        "así que no serviría para volver atrás."
    )
    assert "creado_en_utc" not in columnas, (
        "El respaldo ya tiene la columna que agrega la migración, o sea que es posterior."
    )


def test_el_respaldo_conserva_las_copias_acotadas(base_en_0001: Path) -> None:
    """Una carpeta que crece sin techo en el disco de la evidencia no es aceptable (D-34)."""
    for _ in range(4):
        resultado = respaldar(base_en_0001, conservar=2)

    assert resultado.copias_conservadas == 2, (
        f"Se conservaron {resultado.copias_conservadas} copias con `conservar=2`."
    )
    assert resultado.bytes_del_conjunto > 0


def test_la_poda_nunca_borra_la_copia_que_se_acaba_de_hacer(base_en_0001: Path) -> None:
    """Regresión: con `conservar=1` la poda llegó a borrar el respaldo recién creado.

    El síntoma en producción sería el peor posible para una red de seguridad: la orden
    `migrar` informa la ruta de una copia que ya no existe, y el operador queda creyendo que
    tiene un punto de retorno. Se entera cuando va a usarlo, o sea cuando ya no hay otro.
    """
    for _ in range(3):
        resultado = respaldar(base_en_0001, conservar=1)
        assert resultado.ruta.is_file(), (
            f"La copia informada «{resultado.ruta}» no está en disco: la poda se la llevó."
        )
        assert resultado.bytes_de_la_copia > 0


# --------------------------------------------------------------------------- #
# La comprobación obligatoria del final (la mitad del Criterio de Éxito 6)
# --------------------------------------------------------------------------- #


def test_una_referencia_colgada_hace_fallar_la_comprobacion(base_en_0001: Path) -> None:
    """Sembrar el fallo que sólo `foreign_key_check` puede ver.

    Durante el bloque batch las llaves foráneas están apagadas, así que SQLite **no avisa**
    mientras la migración corre: una fila que quedó apuntando a una que ya no existe pasa
    sin ruido. Ésta es la comprobación que lo detecta, y esta prueba es la que demuestra que
    no es decorativa. Se siembra con el motor de migración, que es el único que permite
    dejar la base en ese estado.
    """
    motor = crear_motor(base_en_0001, para_migracion=True)
    try:
        with motor.begin() as conexion:
            conexion.exec_driver_sql(
                "INSERT INTO viaje_remito (viaje_id, remito_id) VALUES ('v-1', 'r-que-no-existe')"
            )
    finally:
        motor.dispose()

    motor = crear_motor(base_en_0001, para_migracion=True)
    try:
        with motor.connect() as conexion, pytest.raises(
            MigracionDejoLaBaseInconsistente
        ) as capturado:
            comprobar_integridad(conexion)
    finally:
        motor.dispose()

    assert "colgadas" in str(capturado.value), (
        f"El mensaje no explica qué pasó ni qué hacer:\n{capturado.value}"
    )


def test_la_comprobacion_pasa_sobre_una_base_sana(base_en_0001: Path) -> None:
    """Anti-vacuidad: si levantara siempre, la prueba de arriba no diría nada."""
    migrar_a(base_en_0001, "0002")

    motor = crear_motor(base_en_0001, para_migracion=True)
    try:
        with motor.connect() as conexion:
            comprobar_integridad(conexion)
    finally:
        motor.dispose()
