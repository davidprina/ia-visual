"""`payload_crudo`: la tabla donde se graba lo que dijeron los sistemas externos (D-46).

Nace con las doce columnas desde la línea base, y dos de ellas parecen prematuras y no lo
son. `operacion` la declara el `Cassette` del plan 01-10 y es por donde ese plan exporta;
`cabeceras_comprimidas` existe porque el anonimizador tiene que alcanzar también a las
cabeceras —una `Authorization: Basic …` versionada en git es un incidente— y sin columna no
hay dónde guardarlas ni forma de reproducir la respuesta. Agregarlas después costaría una
migración sobre datos productivos.

**`anonimizado` es `NOT NULL` y no tiene valor por defecto, y ésa es la prueba central de
este archivo.** Un `server_default` verdadero convertiría «nadie anonimizó» en «dice que
sí»; uno falso dejaría filas que nadie miró marcadas como no anonimizadas sin que nadie lo
haya declarado. Sin default, quien inserta **tiene** que decidir, y la omisión falla en el
acto en vez de quedar registrada como un hecho falso (T-01-04).
"""

from __future__ import annotations

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from porteria.infraestructura.persistencia.sqlite import modelos

#: Las 12 columnas, en el orden en que la línea base las crea.
COLUMNAS_ESPERADAS = (
    "id",
    "sistema",
    "operacion",
    "peticion",
    "instante_utc_iso",
    "codigo_respuesta",
    "duracion_ms",
    "cuerpo_comprimido",
    "cabeceras_comprimidas",
    "algoritmo_compresion",
    "origen",
    "anonimizado",
)


@pytest.fixture
def esquema(motor_sqlite: Engine) -> Engine:
    modelos.Base.metadata.create_all(motor_sqlite)
    return motor_sqlite


def tabla_info(motor: Engine) -> list[tuple]:
    with motor.connect() as conexion:
        return list(conexion.exec_driver_sql("PRAGMA table_info('payload_crudo')"))


def test_payload_crudo_tiene_sus_doce_columnas_en_orden(esquema: Engine) -> None:
    nombres = tuple(str(fila[1]) for fila in tabla_info(esquema))

    assert nombres == COLUMNAS_ESPERADAS, (
        "Las columnas de `payload_crudo` no son las doce esperadas o están en otro orden.\n"
        f"Esperadas: {COLUMNAS_ESPERADAS}\nEncontradas: {nombres}"
    )


def test_anonimizado_es_obligatorio_y_no_tiene_valor_por_defecto(esquema: Engine) -> None:
    fila = next(f for f in tabla_info(esquema) if str(f[1]) == "anonimizado")
    _, _, _, notnull, dflt_value, _ = fila

    assert int(notnull) == 1, (
        "`anonimizado` admite NULL. Un nulo ahí significa «no sé si se anonimizó», que es "
        "indistinguible de «no se anonimizó» a la hora de decidir si el cassette se puede "
        "versionar en git."
    )
    assert dflt_value is None, (
        f"`anonimizado` tiene el valor por defecto {dflt_value!r}. Un default convierte la "
        "omisión en una declaración que nadie hizo: con `1` diría que se anonimizó sin que "
        "nadie lo haya hecho, y con `0` marcaría como no anonimizadas filas que sí lo están. "
        "Sin default, quien inserta tiene que decidir."
    )


def test_insertar_sin_declarar_anonimizado_falla(esquema: Engine) -> None:
    """La consecuencia operativa de no tener default: la omisión revienta, no pasa callada."""
    with Session(esquema) as sesion, pytest.raises(IntegrityError):
        sesion.add(
            modelos.PayloadCrudo(
                id="p-1",
                sistema="paljet",
                operacion="viaje_por_numero",
                peticion="GET /viajes/2026-000001",
                instante_utc_iso="2026-07-31T10:00:00-03:00",
                codigo_respuesta=200,
                duracion_ms=42.0,
                cuerpo_comprimido=b"\x78\x9c",
                cabeceras_comprimidas=b"\x78\x9c",
                algoritmo_compresion="zlib",
                origen="sintetico",
            )
        )
        sesion.commit()


def test_un_payload_declarado_como_anonimizado_se_persiste(esquema: Engine) -> None:
    """Anti-vacuidad de la prueba anterior: con el campo declarado, la inserción funciona."""
    with Session(esquema) as sesion:
        sesion.add(
            modelos.PayloadCrudo(
                id="p-1",
                sistema="balanza",
                operacion="peso_actual",
                peticion="GET /peso",
                instante_utc_iso="2026-07-31T10:00:00-03:00",
                codigo_respuesta=200,
                duracion_ms=12.5,
                cuerpo_comprimido=b"\x78\x9c",
                cabeceras_comprimidas=b"\x78\x9c",
                algoritmo_compresion="zlib",
                origen="real",
                anonimizado=True,
            )
        )
        sesion.commit()

    with Session(esquema) as sesion:
        guardado = sesion.get(modelos.PayloadCrudo, "p-1")
        assert guardado is not None
        assert guardado.anonimizado is True
        assert guardado.operacion == "peso_actual"
        assert guardado.cabeceras_comprimidas == b"\x78\x9c"


def test_el_cuerpo_y_las_cabeceras_se_guardan_como_bytes(esquema: Engine) -> None:
    """T-01-07: JSON comprimido con zlib, nunca un objeto serializado que ejecute código al leer."""
    tipos = {str(fila[1]): str(fila[2]).upper() for fila in tabla_info(esquema)}

    assert tipos["cuerpo_comprimido"] == "BLOB"
    assert tipos["cabeceras_comprimidas"] == "BLOB"
