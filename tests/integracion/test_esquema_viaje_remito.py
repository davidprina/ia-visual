"""El esquema no retrofiteable, ejercitado con los casos que la fase promete sostener.

Acá se prueban las dos decisiones que después cuestan una migración sobre datos
productivos del cliente —Viaje↔Remito muchas a muchas (VIA-05) y peso teórico nulable con
estado derivado (D-31)— y la tercera que se acordó con el plan 01-04: la unicidad de
`item_evidencia` vive en `(captura_id, camara_id)` y **no** en `ruta_relativa`, porque el
almacén está direccionado por contenido y dos capturas de bytes idénticos comparten archivo.

**Los 21 nombres canónicos no se copian: se leen del dominio.** La prueba de columnas usa
`dataclasses.fields(ItemDeEvidencia)`. Si alguien renombra un campo del dominio sin tocar el
esquema, o al revés, la prueba lo dice. Copiar la lista acá la convertiría en una segunda
verdad que se puede desincronizar en silencio, que es exactamente lo que el plan 01-02 pidió
evitar.
"""

from __future__ import annotations

import dataclasses

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from porteria.dominio.evidencia.captura import ItemDeEvidencia
from porteria.infraestructura.configuracion.en_base import (
    COLUMNAS_REQUERIDAS,
    NOMBRE_DE_LA_TABLA,
)
from porteria.infraestructura.persistencia.sqlite import modelos

#: Las tres columnas que son del esquema y no del dominio (plan 01-02 → plan 01-05).
COLUMNAS_PROPIAS_DEL_ESQUEMA = frozenset({"id", "captura_id", "miniatura"})

#: Total exigido por el plan: 21 canónicos + 3 propias.
COLUMNAS_DE_ITEM_EVIDENCIA = 24

#: Las 12 columnas de `payload_crudo` viven en su propio archivo de prueba
#: (`test_esquema_payload_crudo.py`), que `01-VALIDATION.md` invoca por nombre.


@pytest.fixture
def esquema(motor_sqlite: Engine) -> Engine:
    """Crea el esquema completo sobre el motor real del producto."""
    modelos.Base.metadata.create_all(motor_sqlite)
    return motor_sqlite


def columnas_de(motor: Engine, tabla: str) -> list[tuple]:
    """`PRAGMA table_info`, en orden de declaración. Sin interpolar: SQLite lo permite ligado."""
    with motor.connect() as conexion:
        return list(conexion.exec_driver_sql(f"PRAGMA table_info('{tabla}')"))  # noqa: S608


# --------------------------------------------------------------------------- #
# VIA-05: Viaje ↔ Remito muchas a muchas
# --------------------------------------------------------------------------- #


def test_un_viaje_con_tres_remitos_se_guarda_y_se_recupera_con_los_tres(esquema: Engine) -> None:
    with Session(esquema) as sesion:
        viaje = modelos.Viaje(id="v-1", numero_legible="2026-000001")
        viaje.remitos = [
            modelos.Remito(id=f"r-{numero}", numero=f"R-{numero}") for numero in (1, 2, 3)
        ]
        sesion.add(viaje)
        sesion.commit()

    with Session(esquema) as sesion:
        recuperado = sesion.get(modelos.Viaje, "v-1")
        assert recuperado is not None
        assert {remito.numero for remito in recuperado.remitos} == {"R-1", "R-2", "R-3"}


def test_un_remito_puede_pertenecer_a_dos_viajes_y_se_ve_desde_ambos_lados(
    esquema: Engine,
) -> None:
    """El caso real que la Fase 6 tiene que sostener y que un uno-a-muchos haría imposible."""
    with Session(esquema) as sesion:
        compartido = modelos.Remito(id="r-compartido", numero="R-COMPARTIDO")
        primero = modelos.Viaje(id="v-1", numero_legible="2026-000001", remitos=[compartido])
        segundo = modelos.Viaje(id="v-2", numero_legible="2026-000002", remitos=[compartido])
        sesion.add_all([primero, segundo])
        sesion.commit()

    with Session(esquema) as sesion:
        remito = sesion.get(modelos.Remito, "r-compartido")
        assert remito is not None
        assert {viaje.id for viaje in remito.viajes} == {"v-1", "v-2"}, (
            "El remito compartido no se ve desde los dos viajes. Sin el sentido inverso, la "
            "pregunta «en qué viajes salió este remito» no se puede responder."
        )
        for identificador in ("v-1", "v-2"):
            viaje = sesion.get(modelos.Viaje, identificador)
            assert viaje is not None
            assert [r.id for r in viaje.remitos] == ["r-compartido"]


# --------------------------------------------------------------------------- #
# D-31: peso teórico nulable y estado derivado, nunca persistido
# --------------------------------------------------------------------------- #


def test_un_articulo_sin_peso_teorico_se_persiste_y_se_cuenta(esquema: Engine) -> None:
    with Session(esquema) as sesion:
        remito = modelos.Remito(id="r-1", numero="R-1")
        remito.articulos = [
            modelos.Articulo(remito=remito, codigo="A-1", descripcion="Con peso", peso_teorico_kg=12.5),
            modelos.Articulo(remito=remito, codigo="A-2", descripcion="Sin peso maestro"),
            modelos.Articulo(remito=remito, codigo="A-3", descripcion="Tampoco tiene"),
        ]
        sesion.add(remito)
        sesion.commit()

    with Session(esquema) as sesion:
        sin_peso = sesion.scalar(
            select(func.count())
            .select_from(modelos.Articulo)
            .where(modelos.Articulo.peso_teorico_kg.is_(None))
        )
        assert sin_peso == 2, (
            "El `NULL` del peso teórico no sobrevivió. Si se guardó como 0.0, la diferencia "
            "contra la balanza saldría enorme y el veredicto de auditoría sería falso."
        )


def test_el_estado_de_completitud_del_remito_no_existe_como_columna(esquema: Engine) -> None:
    """Se **deriva** de los artículos. Una columna podría contradecir a los datos que tiene al lado."""
    nombres = [str(fila[1]) for fila in columnas_de(esquema, "remito")]
    con_estado = [nombre for nombre in nombres if "estado" in nombre.lower()]

    assert con_estado == [], (
        "La tabla `remito` tiene columnas de estado: "
        f"{con_estado}. D-31 exige que la completitud se derive de si algún artículo carece "
        "de peso, para que estado y datos no puedan contradecirse."
    )


# --------------------------------------------------------------------------- #
# D-28 / D-21: la captura nace autónoma y no se bloquea por falta de sesión
# --------------------------------------------------------------------------- #


def test_una_captura_se_inserta_sin_viaje_y_sin_autor(esquema: Engine) -> None:
    with Session(esquema) as sesion:
        sesion.add(
            modelos.Captura(
                id="c-1",
                numero_legible="2026-000001",
                viaje_id=None,
                autor_id=None,
                instante_objetivo_ns=1_000,
                ventana_vigente_ms=150.0,
                fecha_local="2026-07-31",
                version_app="0.1.0",
                version_esquema="0002",
            )
        )
        sesion.commit()

    with Session(esquema) as sesion:
        captura = sesion.get(modelos.Captura, "c-1")
        assert captura is not None
        assert captura.viaje_id is None, "D-28: la captura tiene que poder existir sin viaje."
        assert captura.autor_id is None, "D-21: sin sesión iniciada la evidencia se registra igual."


# --------------------------------------------------------------------------- #
# Las 24 columnas de item_evidencia, contra el dominio
# --------------------------------------------------------------------------- #


def test_item_evidencia_tiene_las_24_columnas_y_son_las_del_dominio(esquema: Engine) -> None:
    canonicos = {campo.name for campo in dataclasses.fields(ItemDeEvidencia)}
    assert len(canonicos) == 21, (
        f"`ItemDeEvidencia` dejó de tener 21 campos canónicos: tiene {len(canonicos)}. Si el "
        "dominio cambió a propósito, el esquema y este número se actualizan juntos."
    )

    nombres = {str(fila[1]) for fila in columnas_de(esquema, "item_evidencia")}

    assert len(nombres) == COLUMNAS_DE_ITEM_EVIDENCIA, (
        f"`item_evidencia` tiene {len(nombres)} columnas y tiene que tener "
        f"{COLUMNAS_DE_ITEM_EVIDENCIA}: los 21 nombres canónicos del dominio más `id`, "
        f"`captura_id` y `miniatura`. Sobran o faltan: {sorted(nombres ^ (canonicos | COLUMNAS_PROPIAS_DEL_ESQUEMA))}"
    )
    assert nombres == canonicos | COLUMNAS_PROPIAS_DEL_ESQUEMA, (
        "Los nombres del esquema no coinciden uno a uno con los del dominio. Una divergencia "
        "de nombres se paga en traducciones silenciosas, que es donde se cuelan los errores "
        f"que nadie encuentra.\nSólo en la base: {sorted(nombres - canonicos - COLUMNAS_PROPIAS_DEL_ESQUEMA)}"
        f"\nSólo en el dominio: {sorted(canonicos - nombres)}"
    )


def test_capturado_en_utc_iso_es_texto_y_no_un_tipo_de_fecha(esquema: Engine) -> None:
    """Pitfall 4: el tipo con zona horaria de SQLAlchemy pierde el `tzinfo` al leer en SQLite."""
    tipos = {str(fila[1]): str(fila[2]).upper() for fila in columnas_de(esquema, "item_evidencia")}

    assert tipos["capturado_en_utc_iso"].startswith("VARCHAR"), (
        "`capturado_en_utc_iso` tiene que ser texto ISO-8601 con offset. Con el tipo de "
        "fecha con zona horaria, SQLite guarda sin offset y al leer devuelve un instante sin "
        f"zona: todo el histórico se desplaza. Tipo declarado: {tipos['capturado_en_utc_iso']}"
    )
    assert tipos["desfasaje_local_min"] == "INTEGER", (
        "`desfasaje_local_min` guarda los minutos enteros del `Desfasaje` del dominio."
    )


# --------------------------------------------------------------------------- #
# T-01-27: contenido duplicado no puede reventar la captura
# --------------------------------------------------------------------------- #


def _captura(sesion: Session, identificador: str, legible: str) -> None:
    sesion.add(
        modelos.Captura(
            id=identificador,
            numero_legible=legible,
            instante_objetivo_ns=0,
            ventana_vigente_ms=150.0,
            fecha_local="2026-07-31",
            version_app="0.1.0",
            version_esquema="0002",
        )
    )


def _item(captura_id: str, camara_id: str, ruta: str) -> modelos.ItemEvidencia:
    return modelos.ItemEvidencia(
        id=f"{captura_id}-{camara_id}",
        captura_id=captura_id,
        camara_id=camara_id,
        ruta_relativa=ruta,
        sha256="a" * 64,
        bytes_totales=1024,
        capturado_en_utc_iso="2026-07-31T10:00:00-03:00",
        desfasaje_local_min=-180,
        fecha_local="2026-07-31",
        instante_monotono_ns=1_000,
        desvio_ms=1.0,
        ventana_vigente_ms=150.0,
        perfil_de_flujo="evidencia",
        resolucion="320x240",
        codec_origen="mp4v",
        calidad_jpeg=90,
        version_app="0.1.0",
        version_esquema="0002",
        estado_integridad="INTEGRA",
    )


def test_dos_items_pueden_compartir_la_misma_ruta_relativa(esquema: Engine) -> None:
    """El almacén está direccionado por contenido: bytes idénticos ⇒ misma ruta (T-01-27)."""
    misma_ruta = "2026/07/31/" + "a" * 64 + ".jpg"

    with Session(esquema) as sesion:
        _captura(sesion, "c-1", "2026-000001")
        _captura(sesion, "c-2", "2026-000002")
        sesion.add(_item("c-1", "cam-1", misma_ruta))
        sesion.add(_item("c-2", "cam-1", misma_ruta))
        sesion.commit()

    with Session(esquema) as sesion:
        cuantas = sesion.scalar(
            select(func.count())
            .select_from(modelos.ItemEvidencia)
            .where(modelos.ItemEvidencia.ruta_relativa == misma_ruta)
        )
        assert cuantas == 2, (
            "Dos capturas con bytes idénticos tienen que producir dos filas sobre el mismo "
            "archivo. Con UNIQUE en `ruta_relativa`, la segunda captura reventaría con "
            "IntegrityError y dejaría un archivo huérfano que el portero no puede interpretar."
        )


def test_dos_items_de_la_misma_camara_en_la_misma_captura_fallan(esquema: Engine) -> None:
    """La unicidad real del negocio: una captura tiene a lo sumo un ítem por cámara."""
    with Session(esquema) as sesion:
        _captura(sesion, "c-1", "2026-000001")
        sesion.add(_item("c-1", "cam-1", "2026/07/31/" + "a" * 64 + ".jpg"))
        sesion.commit()

    with Session(esquema) as sesion, pytest.raises(IntegrityError):
        repetido = _item("c-1", "cam-1", "2026/07/31/" + "b" * 64 + ".jpg")
        repetido.id = "otro-id"
        sesion.add(repetido)
        sesion.commit()


def test_ningun_indice_sobre_ruta_relativa_es_unico_y_existe_el_de_captura_y_camara(
    esquema: Engine,
) -> None:
    with esquema.connect() as conexion:
        indices = list(conexion.exec_driver_sql("PRAGMA index_list('item_evidencia')"))
        detalle = {
            str(fila[1]): [str(c[2]) for c in conexion.exec_driver_sql(f"PRAGMA index_info('{fila[1]}')")]  # noqa: S608
            for fila in indices
        }
        unicidad = {str(fila[1]): int(fila[2]) for fila in indices}

    sobre_ruta = {nombre for nombre, columnas in detalle.items() if columnas == ["ruta_relativa"]}
    assert sobre_ruta, (
        "No existe ningún índice sobre `ruta_relativa`. Sin él, la consulta por ruta hace "
        "un barrido completo de la tabla de evidencia."
    )
    assert all(unicidad[nombre] == 0 for nombre in sobre_ruta), (
        f"Hay un índice único sobre `ruta_relativa`: {sorted(sobre_ruta)}. Es la restricción "
        "que rompe la segunda captura de un contenido repetido."
    )

    sobre_captura_y_camara = {
        nombre for nombre, columnas in detalle.items() if columnas == ["captura_id", "camara_id"]
    }
    assert sobre_captura_y_camara == {"uq_item_evidencia_captura_id_camara_id"}, (
        "Falta la restricción única `uq_item_evidencia_captura_id_camara_id` sobre "
        f"(captura_id, camara_id). Índices encontrados: {detalle}"
    )
    assert unicidad["uq_item_evidencia_captura_id_camara_id"] == 1


# --------------------------------------------------------------------------- #
# El contrato con el plan 01-06: la tabla `configuracion`
# --------------------------------------------------------------------------- #


def test_la_tabla_de_configuracion_tiene_las_columnas_que_el_plan_01_06_espera(
    esquema: Engine,
) -> None:
    """`COLUMNAS_REQUERIDAS` es el contrato que `ConfiguracionEnBase` declaró antes de existir el esquema."""
    nombres = {str(fila[1]) for fila in columnas_de(esquema, NOMBRE_DE_LA_TABLA)}

    assert set(COLUMNAS_REQUERIDAS) <= nombres, (
        "El esquema real no tiene las columnas que `ConfiguracionEnBase` espera. "
        f"Faltan: {sorted(set(COLUMNAS_REQUERIDAS) - nombres)}"
    )


def test_la_configuracion_en_base_funciona_sobre_el_esquema_real(esquema: Engine) -> None:
    """Prueba de integración de verdad: el adaptador del 01-06 contra la tabla del 01-05."""
    from porteria.infraestructura.configuracion.en_base import ConfiguracionEnBase
    from porteria.infraestructura.runtime.reloj import RelojFijo

    configuracion = ConfiguracionEnBase(esquema, RelojFijo())
    configuracion.escribir("ventana_aceptacion_ms", 220, autor="ñandú áéí")

    assert configuracion.leer("ventana_aceptacion_ms") == 220
    valor = configuracion.listar()["ventana_aceptacion_ms"]
    assert valor.cambiado_por == "ñandú áéí", (
        "La autoría no sobrevivió al viaje por la tabla real. T-01-22 exige que cada cambio "
        "de configuración diga quién y cuándo."
    )
