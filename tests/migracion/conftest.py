"""Ayudantes compartidos de las pruebas de migración: sembrar, volcar y comparar.

**D-33: cada migración nueva agrega su propia prueba.** La revisión `0003` que agregue
cualquier fase futura no tiene que reescribir nada de esto: alcanza con parametrizar
`base_en_revision` con la versión anterior y llamar a `comparar_volcados`. Una migración sin
prueba se estrena sobre los años de evidencia de un cliente, que es el único lugar donde no
hay segunda oportunidad.

**Por qué la comparación vive acá y no dentro de cada prueba.** Las dos pruebas —la que
verifica que se preservan los datos y la que verifica que una pérdida **se detecta**— tienen
que usar exactamente el mismo juicio. Si cada una reimplementara la comparación, el caso
adverso no demostraría nada sobre el caso feliz: estaría probando su propia copia.

**Por qué `volcar` devuelve filas con nombre de columna y no tuplas.** Una migración agrega
columnas, y ése es su trabajo. Con tuplas posicionales, agregar `creado_en_utc` haría que
todas las filas de `remito` se vieran distintas y la comparación no podría distinguir «la
migración agregó una columna» —correcto— de «la migración cambió los datos» —desastre—. Con
las columnas nombradas, la comparación mira las que existían antes y exige que sigan valiendo
lo mismo, que es exactamente la propiedad que DIS-05 pide.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from alembic import command
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from porteria.cli.ordenes.migrar import construir_config
from porteria.infraestructura.persistencia.sqlite.motor import crear_motor
from tests.conftest import RutaHostil

#: La tabla de control de Alembic cambia a propósito en cada migración: compararla sería
#: exigir que la migración no hiciera su trabajo.
TABLAS_EXCLUIDAS = frozenset({"alembic_version"})

#: Un número de remito con eñe, con espacio interior y con acento, todo junto (DIS-06).
NUMERO_DE_REMITO_HOSTIL = "R-2026 ñandú áéí"

#: Una patente tal como puede llegar: con guiones y con espacios alrededor. Se persiste sin
#: normalizar a propósito, así que la migración tiene que devolverla carácter por carácter.
PATENTE_HOSTIL = " AB-123-CD "


def volcar(motor: Engine) -> dict[str, list[dict[str, Any]]]:
    """Todas las filas de todas las tablas, con orden determinista.

    El orden se fija ordenando por todas las columnas: sin un orden estable, dos volcados
    de los mismos datos podrían diferir sólo por cómo SQLite decidió devolverlos, y la
    comparación fila por fila daría falsos positivos.
    """
    inspector = inspect(motor)
    volcado: dict[str, list[dict[str, Any]]] = {}

    with motor.connect() as conexion:
        for tabla in sorted(inspector.get_table_names()):
            if tabla in TABLAS_EXCLUIDAS:
                continue

            columnas = [columna["name"] for columna in inspector.get_columns(tabla)]
            if not columnas:  # pragma: no cover - una tabla sin columnas no es posible
                continue

            lista = ", ".join(f'"{nombre}"' for nombre in columnas)
            orden = ", ".join(f'"{nombre}"' for nombre in columnas)
            filas = conexion.exec_driver_sql(
                f'SELECT {lista} FROM "{tabla}" ORDER BY {orden}'  # noqa: S608
            ).fetchall()

            volcado[tabla] = [dict(zip(columnas, fila, strict=True)) for fila in filas]

    return volcado


def comparar_volcados(
    antes: dict[str, list[dict[str, Any]]],
    despues: dict[str, list[dict[str, Any]]],
) -> list[str]:
    """Devuelve las diferencias que representan **pérdida** de datos.

    Agregar tablas, columnas o filas no es una diferencia: es lo que una migración hace.
    Perder una tabla, perder una columna que tenía datos, perder filas o cambiar un valor
    existente **sí** lo es. Devolver la lista en vez de afirmar permite que el caso adverso
    exija que la lista **no** esté vacía usando el mismo juicio que el caso feliz.
    """
    diferencias: list[str] = []

    for tabla, filas_antes in antes.items():
        if tabla not in despues:
            diferencias.append(f"la tabla «{tabla}» desapareció")
            continue

        filas_despues = despues[tabla]

        if len(filas_antes) != len(filas_despues):
            diferencias.append(
                f"«{tabla}» tenía {len(filas_antes)} filas y ahora tiene "
                f"{len(filas_despues)}"
            )
            continue

        for indice, (fila_antes, fila_despues) in enumerate(
            zip(filas_antes, filas_despues, strict=True)
        ):
            for columna, valor_antes in fila_antes.items():
                if columna not in fila_despues:
                    diferencias.append(
                        f"«{tabla}» perdió la columna «{columna}», que tenía datos "
                        f"(fila {indice}: {valor_antes!r})"
                    )
                    continue

                valor_despues = fila_despues[columna]
                if valor_antes != valor_despues:
                    diferencias.append(
                        f"«{tabla}» fila {indice} columna «{columna}»: "
                        f"antes {valor_antes!r}, ahora {valor_despues!r}"
                    )

    return diferencias


def sembrar_casos_feos(motor: Engine) -> None:
    """Inserta los cuatro casos que la fase promete sostener, más la patente cruda.

    Los cuatro son los de D-33 y ninguno es un caso de borde inventado: los tres remitos por
    viaje y el remito compartido son la operación real que la Fase 6 tiene que soportar, el
    peso ausente es el maestro de artículos del ERP tal como está, y el número con eñe y
    acento es cómo se escriben los remitos en esta planta.
    """
    with motor.begin() as conexion:
        # Caso 1: un viaje con TRES remitos.
        conexion.exec_driver_sql(
            "INSERT INTO viaje (id, numero_legible, patente) VALUES (?, ?, ?)",
            ("v-1", "2026-000001", PATENTE_HOSTIL),
        )
        # Caso 2: un segundo viaje que comparte uno de esos remitos.
        conexion.exec_driver_sql(
            "INSERT INTO viaje (id, numero_legible, patente) VALUES (?, ?, ?)",
            ("v-2", "2026-000002", None),
        )

        # Caso 4: el número con eñe, espacio interior y acento.
        for identificador, numero in (
            ("r-1", "R-0001"),
            ("r-2", NUMERO_DE_REMITO_HOSTIL),
            ("r-3", "R-0003"),
        ):
            conexion.exec_driver_sql(
                "INSERT INTO remito (id, numero) VALUES (?, ?)", (identificador, numero)
            )

        for viaje, remito in (("v-1", "r-1"), ("v-1", "r-2"), ("v-1", "r-3"), ("v-2", "r-2")):
            conexion.exec_driver_sql(
                "INSERT INTO viaje_remito (viaje_id, remito_id) VALUES (?, ?)", (viaje, remito)
            )

        # Caso 3: un artículo con peso teórico ausente. `NULL`, no cero (D-31).
        for remito, codigo, descripcion, peso in (
            ("r-1", "A-1", "Con peso conocido", 12.5),
            ("r-1", "A-2", "Sin peso en el maestro", None),
            ("r-2", "A-3", "Tampoco tiene", None),
        ):
            conexion.exec_driver_sql(
                "INSERT INTO articulo (remito_id, codigo, descripcion, peso_teorico_kg) "
                "VALUES (?, ?, ?, ?)",
                (remito, codigo, descripcion, peso),
            )


@pytest.fixture
def ruta_db_migracion(ruta_hostil: RutaHostil, tmp_path_factory) -> Path:  # noqa: ANN001
    """Una base propia por prueba, bajo la raíz con espacios y acentos.

    No se reutiliza `ruta_hostil.ruta_db` porque estas pruebas migran, respaldan y a veces
    dejan la base a medio migrar a propósito: compartirla contaminaría a las demás.
    """
    directorio = ruta_hostil.raiz / "migraciones de prueba"
    directorio.mkdir(parents=True, exist_ok=True)
    ruta = directorio / f"{tmp_path_factory.mktemp('m').name}.sqlite3"
    yield ruta

    for sufijo in ("", "-wal", "-shm"):
        Path(f"{ruta}{sufijo}").unlink(missing_ok=True)


def migrar_a(ruta_db: Path, revision: str) -> None:
    """Lleva la base a la revisión pedida con la misma maquinaria que usa el producto."""
    command.upgrade(construir_config(ruta_db), revision)


@pytest.fixture
def base_en_0001(ruta_db_migracion: Path) -> Path:
    """Una base creada en la revisión anterior y ya sembrada con los casos feos."""
    migrar_a(ruta_db_migracion, "0001")

    motor = crear_motor(ruta_db_migracion)
    try:
        sembrar_casos_feos(motor)
    finally:
        motor.dispose()

    return ruta_db_migracion
