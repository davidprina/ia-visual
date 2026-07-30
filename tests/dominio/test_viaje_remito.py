"""Viaje, remito, artículo y peso teórico nulable (D-27, D-31, D-45, VIA-05).

Este módulo admite lo incómodo desde el primer día, y eso es deliberado: **dos de las tres
decisiones no retrofiteables de esta fase viven acá.**

* **Viaje↔Remito muchas a muchas.** El caso real que la Fase 6 tiene que sostener es un
  viaje con tres remitos, uno de ellos compartido con otro viaje. Modelarlo como uno a
  muchos y migrar después obliga a tocar un esquema con datos productivos: años de
  evidencia y de remitos ya cargados.
* **Peso teórico ausente como caso normal** (D-31). `None` no es un error ni un dato
  faltante por descuido: es un valor legítimo del negocio. Y el estado del remito
  —completo o incompleto— **se deriva**, no se persiste, para que estado y datos no puedan
  contradecirse.
"""

from __future__ import annotations

import dataclasses

import pytest

from porteria.dominio.comun.identificadores import NumeroLegible, RemitoId, ViajeId
from porteria.dominio.comun.resultado import NoDisponible, Ok
from porteria.dominio.comun.tiempo import InstanteUtc
from porteria.dominio.viaje.modelo import (
    Articulo,
    Camion,
    Chofer,
    Patente,
    PesoTeorico,
    Remito,
    Transportista,
    Viaje,
)


def articulo(codigo: str, peso: float | None) -> Articulo:
    return Articulo(codigo=codigo, descripcion=f"artículo {codigo}", peso_teorico_kg=peso)


def remito(numero: str, *articulos: Articulo) -> Remito:
    return Remito(
        id=RemitoId(f"remito-{numero}"),
        numero=numero,
        articulos=list(articulos),
    )


def viaje(numero_legible: str = "2026-001842") -> Viaje:
    return Viaje(
        id=ViajeId(f"viaje-{numero_legible}"),
        numero_legible=NumeroLegible(numero_legible),
    )


# --------------------------------------------------------------------------- #
# Viaje ↔ Remito muchas a muchas (VIA-05)
# --------------------------------------------------------------------------- #


def test_un_viaje_puede_tener_tres_remitos() -> None:
    """El caso verificado en la investigación, tal cual."""
    uno = viaje()
    for numero in ("R-1", "R-2", "R-3"):
        uno.vincular_remito(remito(numero, articulo("ART-1", 1_000.0)))

    assert [r.numero for r in uno.remitos] == ["R-1", "R-2", "R-3"]


def test_un_remito_puede_pertenecer_a_dos_viajes() -> None:
    """El remito compartido: el caso que obliga a que la relación sea N:M desde el día uno."""
    compartido = remito("R-COMPARTIDO", articulo("ART-1", 500.0))
    primero = viaje("2026-000001")
    segundo = viaje("2026-000002")

    primero.vincular_remito(compartido)
    segundo.vincular_remito(compartido)

    assert [v.id for v in compartido.viajes] == ["viaje-2026-000001", "viaje-2026-000002"]
    assert compartido in primero.remitos
    assert compartido in segundo.remitos


def test_la_relacion_se_mantiene_en_los_dos_sentidos() -> None:
    """Vincular por un lado tiene que verse desde el otro: el sentido inverso se consulta."""
    uno = viaje()
    unico = remito("R-1", articulo("ART-1", 100.0))

    uno.vincular_remito(unico)

    assert unico.viajes == [uno]
    assert uno.remitos == [unico]


def test_comparar_dos_remitos_equivalentes_no_recursa_por_la_relacion() -> None:
    """Regresión de un defecto latente que la relación bidireccional hace fácil de escribir.

    Con la comparación campo por campo que genera `dataclass`, comparar dos remitos
    equivalentes recorre `Remito.viajes → Viaje.remitos → Remito.viajes` y revienta con
    `RecursionError`. `list.__contains__` lo tapa mientras se trate del **mismo** objeto,
    porque prueba identidad antes de igualdad — así que el defecto no aparece hasta el
    primer remito reconstruido desde la base, en el plan 01-05.

    La igualdad de estas dos entidades es por identificador, que además es lo que el negocio
    entiende: dos remitos con el mismo número son el mismo remito.
    """
    uno = viaje("2026-000001")
    otro = viaje("2026-000002")
    primero = remito("R-1", articulo("ART-1", 10.0))
    segundo = remito("R-1", articulo("ART-1", 10.0))
    uno.vincular_remito(primero)
    otro.vincular_remito(segundo)

    assert primero == segundo
    assert uno != otro
    assert len({primero, segundo}) == 1


def test_vincular_dos_veces_el_mismo_remito_no_lo_duplica() -> None:
    uno = viaje()
    unico = remito("R-1", articulo("ART-1", 100.0))

    uno.vincular_remito(unico)
    uno.vincular_remito(unico)

    assert uno.remitos == [unico]
    assert unico.viajes == [uno]


# --------------------------------------------------------------------------- #
# Peso teórico nulable y estado derivado (D-31)
# --------------------------------------------------------------------------- #


def test_un_articulo_sin_peso_teorico_no_es_un_error() -> None:
    """D-31: `None` es un valor legítimo del negocio, no un dato faltante por error."""
    sin_peso = articulo("ART-SIN-PESO", None)

    assert sin_peso.peso_teorico_kg is None
    assert sin_peso.peso_teorico.presente is False


def test_el_remito_deriva_que_esta_incompleto() -> None:
    incompleto = remito("R-1", articulo("ART-1", 100.0), articulo("ART-2", None))

    assert incompleto.tiene_peso_teorico_completo is False


def test_el_remito_deriva_que_esta_completo() -> None:
    completo = remito("R-1", articulo("ART-1", 100.0), articulo("ART-2", 200.0))

    assert completo.tiene_peso_teorico_completo is True


def test_el_remito_enumera_los_articulos_sin_peso() -> None:
    """Es la consulta que alimenta el reporte de artículos sin peso maestro de la Fase 7."""
    incompleto = remito(
        "R-1",
        articulo("ART-1", 100.0),
        articulo("ART-2", None),
        articulo("ART-3", None),
    )

    assert incompleto.articulos_sin_peso == ("ART-2", "ART-3")


def test_el_estado_del_remito_no_es_un_campo_asignable() -> None:
    """Si fuera un campo, podría contradecir a los artículos que tiene al lado.

    La invariante de `inv_01_02.py` cubre la otra mitad: que el módulo no declare ningún
    `estado_remito` persistible.
    """
    incompleto = remito("R-1", articulo("ART-1", None))

    with pytest.raises(AttributeError):
        incompleto.tiene_peso_teorico_completo = True  # type: ignore[misc]


def test_un_remito_sin_articulos_no_se_declara_completo() -> None:
    """Un remito vacío no tiene pesos: decir «completo» sería sumar cero y llamarlo total."""
    vacio = remito("R-VACIO")

    assert vacio.tiene_peso_teorico_completo is False


# --------------------------------------------------------------------------- #
# El peso teórico total del viaje
# --------------------------------------------------------------------------- #


def test_el_total_suma_todos_los_remitos_cuando_estan_completos() -> None:
    uno = viaje()
    uno.vincular_remito(remito("R-1", articulo("ART-1", 1_000.5), articulo("ART-2", 500.5)))
    uno.vincular_remito(remito("R-2", articulo("ART-3", 250.0)))

    total = uno.peso_teorico_total()

    assert isinstance(total, Ok)
    assert total.valor == pytest.approx(1_751.0)


def test_el_total_no_esta_disponible_y_enumera_los_articulos_sin_peso() -> None:
    """Nunca inventa un número ni suma tratando `None` como cero.

    Un cero silencioso acá produciría una diferencia de peso enorme contra la balanza y un
    veredicto de auditoría falso. El tercer veredicto de AUD-03 —«peso teórico
    incompleto»— sale justamente de esta rama.
    """
    uno = viaje()
    uno.vincular_remito(remito("R-1", articulo("ART-1", 1_000.0), articulo("ART-2", None)))
    uno.vincular_remito(remito("R-2", articulo("ART-3", None)))

    total = uno.peso_teorico_total()

    assert isinstance(total, NoDisponible)
    assert total.detalles == ("ART-2", "ART-3")
    for codigo in ("ART-2", "ART-3"):
        assert codigo in total.motivo, (
            f"El motivo tiene que enumerar los códigos sin peso para que el portero sepa "
            f"qué pedirle a Logística. Motivo: {total.motivo}"
        )


def test_un_viaje_sin_remitos_no_tiene_total() -> None:
    total = viaje().peso_teorico_total()

    assert isinstance(total, NoDisponible)
    assert "remito" in total.motivo


def test_el_remito_compartido_se_cuenta_una_sola_vez_por_viaje() -> None:
    """Cada viaje suma sus propios remitos; compartir uno no lo duplica en ninguno."""
    compartido = remito("R-COMPARTIDO", articulo("ART-1", 100.0))
    primero = viaje("2026-000001")
    segundo = viaje("2026-000002")
    primero.vincular_remito(compartido)
    segundo.vincular_remito(compartido)
    primero.vincular_remito(remito("R-2", articulo("ART-2", 50.0)))

    assert primero.peso_teorico_total() == Ok(150.0)
    assert segundo.peso_teorico_total() == Ok(100.0)


# --------------------------------------------------------------------------- #
# PesoTeorico como valor
# --------------------------------------------------------------------------- #


def test_el_peso_teorico_ausente_no_es_cero_ni_menos_uno() -> None:
    ausente = PesoTeorico.ausente()

    assert ausente.presente is False
    assert ausente.kilogramos is None
    assert ausente != PesoTeorico.de(0.0)


@pytest.mark.parametrize("kilogramos", [-1.0, -0.5, -1_000.0])
def test_el_peso_teorico_rechaza_valores_negativos(kilogramos: float) -> None:
    """`-1` como centinela de «no sé» es el atajo que D-31 prohíbe explícitamente."""
    with pytest.raises(ValueError, match="negativo"):
        PesoTeorico.de(kilogramos)


def test_el_peso_teorico_admite_cero_como_peso_real() -> None:
    """Cero es un peso, no una ausencia. Confundirlos es el error que D-31 evita."""
    assert PesoTeorico.de(0.0).presente is True


# --------------------------------------------------------------------------- #
# Patente normalizada (la Fase 5 valida las gramáticas; acá sólo se normaliza)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "texto",
    [" AB-123-CD ", "ab 123 cd", "AB123CD", "ab-123-cd", "  ab123cd  ", "AB.123.CD"],
)
def test_todas_las_formas_feas_producen_el_mismo_valor_canonico(texto: str) -> None:
    """El doble de prueba del plan 01-08 devuelve `" AB-123-CD "` a propósito."""
    assert Patente(texto).canonica == "AB123CD"


def test_la_patente_conserva_el_texto_original() -> None:
    """Lo que dijo el ERP se guarda tal cual: es el dato que permite auditar la traducción."""
    patente = Patente(" AB-123-CD ")

    assert patente.original == " AB-123-CD "
    assert patente.canonica == "AB123CD"


def test_dos_patentes_del_mismo_vehiculo_son_iguales_aunque_vengan_distinto() -> None:
    """La igualdad es por el valor canónico: es el mismo camión."""
    assert Patente(" AB-123-CD ") == Patente("ab 123 cd")
    assert len({Patente(" AB-123-CD "), Patente("ab123cd")}) == 1


def test_la_patente_vacia_se_rechaza() -> None:
    with pytest.raises(ValueError, match="patente"):
        Patente("   ")


def test_la_patente_no_valida_la_gramatica_argentina_todavia() -> None:
    """Acá sólo se normaliza; validar `AA123AA` contra `ABC123` es de la Fase 5.

    Se prueba explícitamente para que nadie agregue esa validación en esta fase creyendo
    que falta: con una patente de Brasil o un remolque viejo en la puerta, rechazar en el
    dominio bloquearía la captura, y ninguna regla de formato vale eso.
    """
    assert Patente("XYZ-9").canonica == "XYZ9"


# --------------------------------------------------------------------------- #
# Telemetría reservada (D-45)
# --------------------------------------------------------------------------- #


def test_el_viaje_reserva_lugar_para_la_telemetria_y_arranca_vacio() -> None:
    """D-45: carga manual como camino principal, no como parche."""
    uno = viaje()

    assert uno.kilometros_recorridos is None
    assert uno.salida_en is None
    assert uno.regreso_en is None


def test_la_telemetria_se_carga_a_mano() -> None:
    uno = viaje()

    uno.kilometros_recorridos = 342.7
    uno.salida_en = InstanteUtc("2026-07-25T11:00:00+00:00")
    uno.regreso_en = InstanteUtc("2026-07-25T19:30:00+00:00")

    assert uno.kilometros_recorridos == pytest.approx(342.7)
    assert uno.salida_en.texto.endswith("+00:00")


def test_el_viaje_reserva_lugar_para_chofer_camion_y_transportista() -> None:
    uno = viaje()
    uno.chofer = Chofer(nombre="Juan Pérez", documento="20123456")
    uno.camion = Camion(patente=Patente("ab 123 cd"), patente_acoplado=Patente("XY-987-ZW"))
    uno.transportista = Transportista(nombre="Transportes Ñandú S.A.", cuit="30-12345678-9")

    assert uno.camion.patente.canonica == "AB123CD"
    assert uno.camion.patente_acoplado is not None
    assert uno.transportista.nombre.startswith("Transportes")


def test_el_camion_admite_no_llevar_acoplado() -> None:
    solo = Camion(patente=Patente("AB123CD"))

    assert solo.patente_acoplado is None


def test_los_valores_del_viaje_son_inmutables() -> None:
    """Chofer, camión y transportista son valores; el viaje es la entidad que los tiene."""
    chofer = Chofer(nombre="Juan Pérez", documento="20123456")

    with pytest.raises(dataclasses.FrozenInstanceError):
        chofer.nombre = "otro"  # type: ignore[misc]
