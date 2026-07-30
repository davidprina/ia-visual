"""La bitácora de auditoría encadenada (D-08, D-11, T-01-01).

**El encadenamiento arranca en el registro número uno y no es retrofiteable.** Si el
primer registro no participa de la cadena, todo el histórico anterior a la introducción
del encadenamiento queda fuera del alcance de la verificación — y no hay forma de
recuperarlo después, porque los hashes que faltaban nunca se calcularon.

**El límite honesto, que estas pruebas también fijan:** esto es *tamper-evident*, no
*tamper-proof*. La prueba `test_reencadenar_desde_el_punto_alterado_pasa_la_verificacion`
existe justamente para demostrar el límite en vez de dejarlo escrito sólo en prosa: quien
tenga acceso de escritura puede alterar un registro y rehacer la cadena desde ahí. Lo que
la cadena logra es elevar el costo de "editar una fila" a "rehacer todo el histórico
posterior". Vender "inalterable" lo que es "detectable" sería un riesgo de reputación
mayor que la amenaza técnica.
"""

from __future__ import annotations

import dataclasses

import pytest

from porteria.dominio.auditoria.registro import CadenaDeAuditoria, RegistroEncadenado
from porteria.dominio.comun.identificadores import UsuarioId
from porteria.dominio.comun.tiempo import InstanteUtc

LARGO_DE_LA_CADENA = 10


def instante(segundo: int) -> InstanteUtc:
    return InstanteUtc(f"2026-07-25T22:00:{segundo:02d}+00:00")


def cadena_de_diez() -> tuple[CadenaDeAuditoria, list[RegistroEncadenado]]:
    cadena = CadenaDeAuditoria()
    for numero in range(LARGO_DE_LA_CADENA):
        cadena.encadenar(
            nombre="captura.registrada",
            ocurrido_en=instante(numero),
            actor=UsuarioId("usuario-1"),
            datos={"captura_id": f"captura-{numero}"},
        )
    return cadena, list(cadena.registros)


# --------------------------------------------------------------------------- #
# El registro número uno
# --------------------------------------------------------------------------- #


def test_el_primer_registro_no_tiene_hash_anterior() -> None:
    cadena = CadenaDeAuditoria()

    primero = cadena.encadenar(nombre="sistema.iniciado", ocurrido_en=instante(0), actor=None)

    assert primero.numero == 1
    assert primero.hash_anterior is None


def test_el_segundo_registro_incluye_el_hash_del_primero() -> None:
    cadena = CadenaDeAuditoria()
    primero = cadena.encadenar(nombre="sistema.iniciado", ocurrido_en=instante(0), actor=None)

    segundo = cadena.encadenar(nombre="captura.registrada", ocurrido_en=instante(1), actor=None)

    assert segundo.numero == 2
    assert segundo.hash_anterior == primero.hash_propio


def test_la_numeracion_arranca_en_uno_y_no_salta() -> None:
    _, registros = cadena_de_diez()

    assert [registro.numero for registro in registros] == list(range(1, LARGO_DE_LA_CADENA + 1))


def test_el_registro_cero_no_existe() -> None:
    """Un registro numerado 0 sería un histórico anterior a la cadena colado por atrás."""
    with pytest.raises(ValueError, match="número"):
        RegistroEncadenado(
            numero=0,
            nombre="captura.registrada",
            ocurrido_en=instante(0),
            actor=None,
            datos={},
            hash_anterior=None,
            hash_propio="a" * 64,
        )


# --------------------------------------------------------------------------- #
# Verificación
# --------------------------------------------------------------------------- #


def test_una_cadena_entera_verifica_sin_senalar_nada() -> None:
    cadena, registros = cadena_de_diez()

    assert CadenaDeAuditoria.verificar(registros) is None
    assert cadena.esta_entera() is True


def test_la_cadena_vacia_esta_entera() -> None:
    """Antes del primer hecho no hay nada roto. Es el estado del primer arranque."""
    assert CadenaDeAuditoria.verificar([]) is None


@pytest.mark.parametrize("indice", [0, 1, 4, 9])
def test_alterar_un_registro_senala_su_indice(indice: int) -> None:
    """T-01-01 verificable: se altera el registro `k` de 10 y `verificar` devuelve `k`."""
    _, registros = cadena_de_diez()
    registros[indice] = dataclasses.replace(
        registros[indice], datos={"captura_id": "captura-adulterada"}
    )

    assert CadenaDeAuditoria.verificar(registros) == indice


def test_alterar_el_actor_de_un_registro_tambien_lo_delata() -> None:
    """La autoría entra en el hash: cambiar quién firmó rompe la cadena (D-19)."""
    _, registros = cadena_de_diez()
    registros[3] = dataclasses.replace(registros[3], actor=UsuarioId("otro-usuario"))

    assert CadenaDeAuditoria.verificar(registros) == 3


def test_borrar_un_registro_del_medio_rompe_la_cadena() -> None:
    """Detectar el borrado de registros completos es la mitad del punto de D-08."""
    _, registros = cadena_de_diez()
    del registros[5]

    assert CadenaDeAuditoria.verificar(registros) == 5


def test_reordenar_dos_registros_rompe_la_cadena() -> None:
    _, registros = cadena_de_diez()
    registros[3], registros[4] = registros[4], registros[3]

    assert CadenaDeAuditoria.verificar(registros) == 3


def test_reencadenar_desde_el_punto_alterado_pasa_la_verificacion() -> None:
    """El límite honesto, demostrado: tamper-EVIDENT, no tamper-PROOF.

    Quien tenga escritura en el disco puede alterar el registro 5 y rehacer los cinco
    siguientes. La verificación entonces pasa — y eso **no** es un defecto de la cadena
    sino su límite real. Lo que la cadena consigue es que la manipulación exija rehacer
    todo el histórico posterior en vez de editar una fila. Volverla tamper-proof requiere
    un ancla externa (medio de solo-anexado, sellado por un tercero, o publicación
    periódica del hash de la cabeza), que esta fase deja como hueco de diseño.
    """
    _, registros = cadena_de_diez()

    rehecha = CadenaDeAuditoria()
    for indice, registro in enumerate(registros):
        datos = dict(registro.datos)
        if indice == 5:
            datos["captura_id"] = "captura-adulterada"
        rehecha.encadenar(
            nombre=registro.nombre,
            ocurrido_en=registro.ocurrido_en,
            actor=registro.actor,
            datos=datos,
        )

    assert CadenaDeAuditoria.verificar(rehecha.registros) is None
    assert rehecha.registros[5].datos["captura_id"] == "captura-adulterada"
    assert rehecha.registros[9].hash_propio != registros[9].hash_propio, (
        "Rehacer la cadena tiene que cambiar todos los hashes posteriores al punto "
        "alterado. Si no cambiaran, el hash del anterior no estaría entrando en el "
        "cálculo y la cadena no encadenaría nada."
    )


# --------------------------------------------------------------------------- #
# Propiedades del registro
# --------------------------------------------------------------------------- #


def test_el_registro_es_inmutable_y_sus_datos_tambien() -> None:
    cadena = CadenaDeAuditoria()
    registro = cadena.encadenar(
        nombre="captura.registrada",
        ocurrido_en=instante(0),
        actor=None,
        datos={"captura_id": "captura-1"},
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        registro.nombre = "otro"  # type: ignore[misc]
    with pytest.raises(TypeError):
        registro.datos["captura_id"] = "otra"  # type: ignore[index]


def test_el_registro_admite_actor_nulo() -> None:
    """D-21: un hecho sin sesión iniciada se registra igual, con autor no identificado."""
    cadena = CadenaDeAuditoria()

    registro = cadena.encadenar(nombre="captura.registrada", ocurrido_en=instante(0), actor=None)

    assert registro.actor is None
    assert CadenaDeAuditoria.verificar(cadena.registros) is None


def test_el_hash_propio_es_un_sha256_hexadecimal() -> None:
    cadena = CadenaDeAuditoria()

    registro = cadena.encadenar(nombre="captura.registrada", ocurrido_en=instante(0), actor=None)

    assert len(registro.hash_propio) == 64
    assert registro.hash_propio == registro.hash_propio.lower()


def test_dos_hechos_identicos_en_distinta_posicion_dan_hashes_distintos() -> None:
    """Porque el número y el hash del anterior entran en el cálculo."""
    cadena = CadenaDeAuditoria()
    primero = cadena.encadenar(nombre="igual", ocurrido_en=instante(0), actor=None)
    segundo = cadena.encadenar(nombre="igual", ocurrido_en=instante(0), actor=None)

    assert primero.hash_propio != segundo.hash_propio
