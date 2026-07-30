"""`CapturaDeControl`, `ItemDeEvidencia` y el `Manifiesto` (D-05, D-08, D-21, D-28, D-40).

Las tres propiedades del hash del manifiesto que **no pueden contradecirse**, y que son
contrato no retrofiteable desde la primera captura persistida:

1. agregar o quitar un ítem **cambia** el hash;
2. alterar cualquier campo hasheado de un ítem **cambia** el hash;
3. reordenar la colección de entrada **no** lo cambia.

Las tres a la vez sólo son posibles si el orden de hasheo se **deriva de los datos**
(`camara_id`, después `instante_monotono_ns`) en vez de tomarse del orden de inserción.
Un ejecutor que adivinara la otra variante fijaría un contrato equivocado, y el hash de
una captura no se puede recalcular después sin invalidar la evidencia ya sellada.
"""

from __future__ import annotations

import dataclasses

import pytest

from porteria.dominio.comun.identificadores import CamaraId, CapturaId, UsuarioId, ViajeId
from porteria.dominio.comun.tiempo import Desfasaje, FechaLocal, InstanteUtc
from porteria.dominio.evidencia.captura import CapturaDeControl, ItemDeEvidencia
from porteria.dominio.evidencia.estados import EstadoDeIntegridad
from porteria.dominio.evidencia.huella import HuellaDeIntegridad
from porteria.dominio.evidencia.manifiesto import Manifiesto
from porteria.infraestructura.runtime.reloj import RelojFijo

VENTANA_MS = 150.0
INSTANTE_OBJETIVO_NS = 1_000_000_000

#: Los 21 nombres canónicos de la tabla de RESEARCH §Pattern 5. El esquema del plan 01-05
#: los mapea uno a uno y agrega exactamente tres columnas propias (`id`, `captura_id` y
#: `miniatura`). Se enumeran acá para que un renombre silencioso rompa una prueba en vez
#: de aparecer como una traducción en la capa de persistencia.
CAMPOS_CANONICOS = (
    "ruta_relativa",
    "sha256",
    "bytes_totales",
    "capturado_en_utc_iso",
    "desfasaje_local_min",
    "fecha_local",
    "instante_monotono_ns",
    "desvio_ms",
    "ventana_vigente_ms",
    "perfil_de_flujo",
    "resolucion",
    "codec_origen",
    "calidad_jpeg",
    "camara_id",
    "motor_id",
    "version_modelo",
    "sha256_modelo",
    "version_app",
    "version_esquema",
    "autor_id",
    "estado_integridad",
)


def huella_de(semilla: str) -> HuellaDeIntegridad:
    """Una huella válida y distinta por semilla, sin calcular nada."""
    return HuellaDeIntegridad(f"{semilla:0>4}".encode().hex().ljust(64, "0")[:64])


#: El autor por defecto de las capturas de estas pruebas. Vive como constante de módulo
#: porque `UsuarioId(...)` en el valor por defecto de un argumento se evalúa una sola vez al
#: importar, y ese patrón es una fuente clásica de estado compartido entre pruebas.
AUTOR = UsuarioId("usuario-1")


def nueva_captura(autor: UsuarioId | None = AUTOR) -> CapturaDeControl:
    return CapturaDeControl.nueva(
        instante_objetivo_ns=INSTANTE_OBJETIVO_NS,
        autor=autor,
        ventana_vigente_ms=VENTANA_MS,
        identificador=CapturaId("captura-1"),
    )


def agregar(
    captura: CapturaDeControl,
    camara: str = "carga-1",
    desvio_ms: float = 0.0,
    semilla: str = "1",
    ruta: str = "2026/07/25/foto.jpg",
) -> ItemDeEvidencia:
    """Agrega un ítem cuyo desvío contra el instante objetivo es el pedido."""
    return captura.agregar_evidencia(
        ruta_relativa=ruta,
        sha256=huella_de(semilla),
        bytes_totales=123_456,
        capturado_en_utc_iso=InstanteUtc("2026-07-25T22:24:45.133966+00:00"),
        desfasaje_local_min=Desfasaje.desde_minutos(-180),
        fecha_local=FechaLocal("2026-07-25"),
        instante_monotono_ns=INSTANTE_OBJETIVO_NS + int(desvio_ms * 1_000_000),
        perfil_de_flujo="evidencia",
        resolucion="1920x1080",
        codec_origen="h264",
        calidad_jpeg=92,
        camara_id=CamaraId(camara),
        version_app="0.1.0",
        version_esquema="1",
    )


# --------------------------------------------------------------------------- #
# La captura nace autónoma (D-28) y no se bloquea por falta de sesión (D-21)
# --------------------------------------------------------------------------- #


def test_la_captura_nace_sin_viaje_asociado() -> None:
    """D-28: el portero saca la foto cuando el camión está delante y busca el viaje después."""
    captura = nueva_captura()

    assert captura.viaje is None


def test_el_viaje_se_vincula_despues() -> None:
    captura = nueva_captura()

    captura.vincular_viaje(ViajeId("viaje-1"))

    assert captura.viaje == "viaje-1"


def test_la_captura_se_construye_sin_autor_y_marca_el_hecho() -> None:
    """D-21: la captura **nunca** se bloquea por falta de sesión.

    Sin sesión iniciada, `autor=None` significa "no identificado", la evidencia se
    registra igual y el hecho queda marcado para que el panel de calidad lo cuente. Es la
    misma regla que rige la captura parcial: registrar lo incompleto en vez de impedirlo.
    """
    captura = nueva_captura(autor=None)

    assert captura.autor is None
    assert captura.autor_identificado is False

    item = agregar(captura)

    assert item.autor_id is None


def test_con_autor_la_captura_lo_propaga_a_cada_item() -> None:
    captura = nueva_captura(autor=UsuarioId("usuario-1"))

    assert captura.autor_identificado is True
    assert agregar(captura).autor_id == "usuario-1"


# --------------------------------------------------------------------------- #
# La ventana vigente queda congelada (D-40, T-01-14)
# --------------------------------------------------------------------------- #


def test_la_ventana_vigente_no_se_puede_ensanchar_despues() -> None:
    """T-01-14: si se pudiera, capturas viejas pasarían de estimadas a sincronizadas."""
    captura = nueva_captura()

    with pytest.raises(AttributeError):
        captura.ventana_vigente_ms = 5_000.0  # type: ignore[misc]


def test_cambiar_el_parametro_no_toca_las_capturas_ya_hechas() -> None:
    """El parámetro global cambia; la captura ya construida conserva el suyo."""
    vieja = nueva_captura()
    item_viejo = agregar(vieja, desvio_ms=400.0)

    nueva_con_ventana_ancha = CapturaDeControl.nueva(
        instante_objetivo_ns=INSTANTE_OBJETIVO_NS,
        autor=None,
        ventana_vigente_ms=5_000.0,
    )
    item_nuevo = agregar(nueva_con_ventana_ancha, desvio_ms=400.0)

    assert item_viejo.ventana_vigente_ms == VENTANA_MS
    assert item_viejo.sincronizada is False, (
        "Un desvío de 400 ms contra una ventana de 150 ms es una captura estimada, y "
        "tiene que seguir siéndolo aunque después alguien ensanche el parámetro."
    )
    assert item_nuevo.ventana_vigente_ms == 5_000.0
    assert item_nuevo.sincronizada is True


def test_cada_item_guarda_la_ventana_que_regia_y_su_desvio_real() -> None:
    captura = nueva_captura()

    item = agregar(captura, desvio_ms=-82.5)

    assert item.desvio_ms == pytest.approx(-82.5)
    assert item.ventana_vigente_ms == VENTANA_MS
    assert item.sincronizada is True


# --------------------------------------------------------------------------- #
# Los 21 campos canónicos de trazabilidad
# --------------------------------------------------------------------------- #


def test_el_item_declara_los_21_campos_canonicos_y_ninguno_mas() -> None:
    """El plan 01-05 mapea el esquema uno a uno contra estos nombres."""
    declarados = tuple(campo.name for campo in dataclasses.fields(ItemDeEvidencia))

    assert declarados == CAMPOS_CANONICOS
    assert len(declarados) == 21


def test_el_item_es_inmutable() -> None:
    item = agregar(nueva_captura())

    with pytest.raises(dataclasses.FrozenInstanceError):
        item.ruta_relativa = "otra"  # type: ignore[misc]


def test_el_item_nace_integro_y_los_campos_de_modelo_nulos() -> None:
    """`motor_id`, `version_modelo` y `sha256_modelo` se poblan desde la Fase 4."""
    item = agregar(nueva_captura())

    assert item.estado_integridad is EstadoDeIntegridad.INTEGRA
    assert (item.motor_id, item.version_modelo, item.sha256_modelo) == (None, None, None)


def test_la_ruta_relativa_no_puede_ser_absoluta_ni_escapar_de_la_raiz() -> None:
    """D-06: relativa a la raíz de evidencia, siempre. Es la barrera del dominio.

    La ruta del archivo se deriva del hash y es inofensiva, pero la ruta **relativa** que
    se persiste es la que después se usa para leer, y una prueba que persistiera
    `../../windows/system32/x.jpg` convertiría la lectura en un path traversal.
    """
    captura = nueva_captura()

    for ruta in ("C:/evidencia/foto.jpg", "/evidencia/foto.jpg", "2026/../../secreto.jpg"):
        with pytest.raises(ValueError, match="relativa"):
            agregar(captura, ruta=ruta)


# --------------------------------------------------------------------------- #
# Los eventos se acumulan, no se publican
# --------------------------------------------------------------------------- #


def test_agregar_evidencia_acumula_un_evento_y_no_lo_publica() -> None:
    """D-12: el caso de uso los recoge y los persiste en el outbox, en la misma transacción."""
    captura = nueva_captura()

    agregar(captura, camara="carga-1", semilla="1")
    agregar(captura, camara="carga-2", semilla="2")

    assert [evento.nombre for evento in captura.eventos] == [
        "evidencia.agregada",
        "evidencia.agregada",
    ]
    assert captura.eventos[0].datos["camara_id"] == "carga-1"


def test_los_eventos_expuestos_no_se_pueden_modificar_desde_afuera() -> None:
    captura = nueva_captura()
    agregar(captura)

    assert isinstance(captura.eventos, tuple)
    assert isinstance(captura.items, tuple)


def test_dos_items_de_la_misma_camara_no_conviven_en_una_captura() -> None:
    """Una captura es un disparo: una foto por cámara. Dos sería un error de sincronía."""
    captura = nueva_captura()
    agregar(captura, camara="carga-1", semilla="1")

    with pytest.raises(ValueError, match="carga-1"):
        agregar(captura, camara="carga-1", semilla="2")


# --------------------------------------------------------------------------- #
# El manifiesto y su hash de segundo nivel (D-08)
# --------------------------------------------------------------------------- #


def manifiesto_de_tres_camaras(incertidumbre_ms: float = 15.625) -> Manifiesto:
    captura = nueva_captura()
    agregar(captura, camara="carga-2", desvio_ms=10.0, semilla="2")
    agregar(captura, camara="carga-1", desvio_ms=-5.0, semilla="1")
    agregar(captura, camara="patente", desvio_ms=30.0, semilla="3")
    return captura.manifiesto(incertidumbre_sello_utc_ms=incertidumbre_ms)


def test_el_manifiesto_declara_su_algoritmo_y_sus_campos() -> None:
    manifiesto = manifiesto_de_tres_camaras()

    assert manifiesto.algoritmo == "sha256"
    assert manifiesto.captura_id == "captura-1"
    assert "instante_monotono_ns" in manifiesto.campos_incluidos
    assert len(manifiesto.hash_manifiesto) == 64


def test_agregar_un_item_cambia_el_hash_del_manifiesto() -> None:
    captura = nueva_captura()
    agregar(captura, camara="carga-1", semilla="1")
    antes = captura.manifiesto(incertidumbre_sello_utc_ms=15.625)

    agregar(captura, camara="carga-2", semilla="2")
    despues = captura.manifiesto(incertidumbre_sello_utc_ms=15.625)

    assert antes.hash_manifiesto != despues.hash_manifiesto


def test_quitar_un_item_cambia_el_hash_del_manifiesto() -> None:
    """Detectar la **ausencia** de una foto dentro de una captura es el punto de D-08."""
    completo = manifiesto_de_tres_camaras()

    captura = nueva_captura()
    agregar(captura, camara="carga-2", desvio_ms=10.0, semilla="2")
    agregar(captura, camara="carga-1", desvio_ms=-5.0, semilla="1")
    incompleto = captura.manifiesto(incertidumbre_sello_utc_ms=15.625)

    assert completo.hash_manifiesto != incompleto.hash_manifiesto


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("sha256", HuellaDeIntegridad("f" * 64)),
        ("ruta_relativa", "2026/07/25/otra.jpg"),
        ("camara_id", CamaraId("carga-9")),
        ("instante_monotono_ns", INSTANTE_OBJETIVO_NS + 999),
        ("desvio_ms", 77.0),
    ],
)
def test_alterar_un_campo_hasheado_de_un_item_cambia_el_hash(campo: str, valor: object) -> None:
    """Los cinco campos de cada ítem que entran en el hash, uno por uno."""
    captura = nueva_captura()
    agregar(captura, camara="carga-1", desvio_ms=-5.0, semilla="1")
    agregar(captura, camara="carga-2", desvio_ms=10.0, semilla="2")
    original = captura.manifiesto(incertidumbre_sello_utc_ms=15.625)

    alterados = [dataclasses.replace(captura.items[0], **{campo: valor}), captura.items[1]]
    alterado = Manifiesto.de_items(
        captura_id=CapturaId("captura-1"),
        incertidumbre_sello_utc_ms=15.625,
        items=alterados,
    )

    assert original.hash_manifiesto != alterado.hash_manifiesto


def test_reordenar_la_coleccion_de_entrada_no_cambia_el_hash() -> None:
    """El orden de hasheo se **recalcula** de los datos, no se toma de la inserción.

    Es la propiedad que hace que las otras dos sean posibles al mismo tiempo: si el hash
    dependiera del orden de inserción, dos capturas idénticas cuyas cámaras respondieron
    en distinto orden tendrían hashes distintos y la verificación diría "comprometida"
    ante una diferencia que no existe.
    """
    manifiesto = manifiesto_de_tres_camaras()
    captura = nueva_captura()
    agregar(captura, camara="patente", desvio_ms=30.0, semilla="3")
    agregar(captura, camara="carga-1", desvio_ms=-5.0, semilla="1")
    agregar(captura, camara="carga-2", desvio_ms=10.0, semilla="2")

    otro_orden = captura.manifiesto(incertidumbre_sello_utc_ms=15.625)

    assert manifiesto.hash_manifiesto == otro_orden.hash_manifiesto


def test_el_orden_de_hasheo_desempata_por_instante_dentro_de_la_misma_camara() -> None:
    """`camara_id` primero, `instante_monotono_ns` después: los dos, en ese orden.

    El desempate no es decorativo. Sin él, dos ítems de la misma cámara quedarían en un
    orden que depende de la implementación de `sorted`, y el hash de la misma evidencia
    cambiaría según cómo se hubiera armado la lista. Se ejercita con `Manifiesto.de_items`
    porque una captura sana nunca tiene dos fotos de la misma cámara — pero el orden de
    hasheo tiene que estar totalmente determinado igual.
    """
    base = agregar(nueva_captura(), camara="carga-1", semilla="1")
    temprano = dataclasses.replace(base, instante_monotono_ns=INSTANTE_OBJETIVO_NS - 1_000)
    tardio = dataclasses.replace(base, instante_monotono_ns=INSTANTE_OBJETIVO_NS + 1_000)

    en_orden = Manifiesto.de_items(
        captura_id=CapturaId("captura-1"),
        incertidumbre_sello_utc_ms=15.625,
        items=[temprano, tardio],
    )
    al_reves = Manifiesto.de_items(
        captura_id=CapturaId("captura-1"),
        incertidumbre_sello_utc_ms=15.625,
        items=[tardio, temprano],
    )

    assert en_orden.hash_manifiesto == al_reves.hash_manifiesto


def test_la_incertidumbre_del_sello_sale_del_puerto_reloj() -> None:
    """Open Question 3: un supuesto silencioso convertido en dato auditable."""
    reloj = RelojFijo(incertidumbre_sello_ms=15.625)

    manifiesto = manifiesto_de_tres_camaras(incertidumbre_ms=reloj.incertidumbre_sello_ms())

    assert manifiesto.incertidumbre_sello_utc_ms == reloj.incertidumbre_sello_ms()


def test_cambiar_la_incertidumbre_cambia_el_hash_del_manifiesto() -> None:
    """Entra en el hash: nadie puede reescribirla después para que la evidencia luzca mejor."""
    con_windows = manifiesto_de_tres_camaras(incertidumbre_ms=15.625)
    con_reloj_fino = manifiesto_de_tres_camaras(incertidumbre_ms=0.0001)

    assert con_windows.hash_manifiesto != con_reloj_fino.hash_manifiesto


def test_el_hash_del_manifiesto_es_estable_entre_corridas() -> None:
    """Si no lo fuera, no se podría verificar evidencia de ayer contra el código de hoy."""
    assert (
        manifiesto_de_tres_camaras().hash_manifiesto
        == manifiesto_de_tres_camaras().hash_manifiesto
    )


def test_el_manifiesto_rechaza_un_campo_con_el_separador_del_hash() -> None:
    """Si el separador pudiera aparecer en un campo, dos capturas distintas colisionarían."""
    captura = nueva_captura()

    with pytest.raises(ValueError, match="separador"):
        agregar(captura, ruta="2026/07/25/fo\x1fto.jpg")
