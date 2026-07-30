"""`HuellaDeIntegridad` y los tres estados de la evidencia (D-08, D-09, D-10).

La huella es un **valor del dominio**, no el resultado de una operación del dominio. El
cálculo del SHA-256 es I/O sobre bytes y pertenece a `infraestructura/persistencia`
(plan 01-04): acá sólo se razona sobre la huella ya calculada y se decide si la evidencia
está comprometida. Es el riesgo de asignación que RESEARCH le marca al planner, y la
invariante de `inv_01_02.py` que prohíbe nombrar el módulo de hashing en `huella.py` es
la que lo mantiene así.
"""

from __future__ import annotations

import dataclasses

import pytest

from porteria.dominio.comun.identificadores import UsuarioId
from porteria.dominio.comun.tiempo import InstanteUtc
from porteria.dominio.evidencia.estados import EstadoDeIntegridad, evaluar
from porteria.dominio.evidencia.huella import HuellaDeIntegridad
from porteria.dominio.evidencia.lapida import Lapida

HEXADECIMAL_VALIDO = "a" * 64
OTRO_HEXADECIMAL = "b" * 64
#: Un digest real de SHA-256 (el de la cadena vacía), para que la prueba no viva sólo de
#: cadenas repetidas.
DIGEST_DE_LA_CADENA_VACIA = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


# --------------------------------------------------------------------------- #
# Formato
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("texto", [HEXADECIMAL_VALIDO, DIGEST_DE_LA_CADENA_VACIA, "0" * 64])
def test_acepta_64_caracteres_hexadecimales_en_minuscula(texto: str) -> None:
    assert HuellaDeIntegridad(texto).valor == texto


@pytest.mark.parametrize(
    ("texto", "por_que"),
    [
        ("a" * 63, "63 caracteres: un dígito de menos"),
        ("a" * 65, "65 caracteres: un dígito de más"),
        ("z" * 64, "z no es un dígito hexadecimal"),
        ("A" * 64, "mayúsculas: `hexdigest()` siempre devuelve minúsculas"),
        ("", "vacía"),
        ("  " + "a" * 62, "espacios"),
        ("a" * 62 + "==", "relleno de base64"),
    ],
)
def test_rechaza_cualquier_otra_cosa(texto: str, por_que: str) -> None:
    """La mayúscula **se rechaza**, no se normaliza. Decisión, con su motivo.

    `hashlib` devuelve siempre minúsculas, así que una huella en mayúsculas no puede
    venir del camino normal: viene de una edición a mano, de una importación mal hecha o
    de un cálculo que no es el nuestro. Normalizarla en silencio convertiría esa señal en
    nada, y encima admitiría dos textos distintos para la misma evidencia justo en el
    campo que es clave única en el esquema y nombre de archivo en el disco.
    """
    with pytest.raises(ValueError, match="64 caracteres hexadecimales") as capturado:
        HuellaDeIntegridad(texto)

    assert "minúscula" in str(capturado.value), (
        f"El mensaje tiene que decir que van en minúscula ({por_que}). "
        f"Mensaje: {capturado.value}"
    )


def test_la_huella_es_inmutable() -> None:
    huella = HuellaDeIntegridad(HEXADECIMAL_VALIDO)

    with pytest.raises(dataclasses.FrozenInstanceError):
        huella.valor = OTRO_HEXADECIMAL  # type: ignore[misc]


def test_dos_huellas_del_mismo_contenido_son_el_mismo_valor() -> None:
    """Es un valor, no una entidad: la igualdad es por contenido."""
    assert HuellaDeIntegridad(HEXADECIMAL_VALIDO) == HuellaDeIntegridad(HEXADECIMAL_VALIDO)
    assert len({HuellaDeIntegridad(HEXADECIMAL_VALIDO), HuellaDeIntegridad(HEXADECIMAL_VALIDO)}) == 1


def test_coincide_con_compara_dos_huellas() -> None:
    huella = HuellaDeIntegridad(HEXADECIMAL_VALIDO)

    assert huella.coincide_con(HuellaDeIntegridad(HEXADECIMAL_VALIDO))
    assert not huella.coincide_con(HuellaDeIntegridad(OTRO_HEXADECIMAL))


# --------------------------------------------------------------------------- #
# Estados de integridad (D-09, D-10)
# --------------------------------------------------------------------------- #


def test_los_estados_son_exactamente_tres() -> None:
    """Tres y no cuatro: cada estado es una columna de la evidencia y una pantalla."""
    assert [estado.value for estado in EstadoDeIntegridad] == [
        "INTEGRA",
        "COMPROMETIDA",
        "PURGADA",
    ]


def test_el_estado_es_texto_persistible() -> None:
    """`StrEnum` para que la columna guarde `INTEGRA` y no `EstadoDeIntegridad.INTEGRA`."""
    assert EstadoDeIntegridad.INTEGRA == "INTEGRA"
    assert f"{EstadoDeIntegridad.COMPROMETIDA}" == "COMPROMETIDA"


def test_evaluar_devuelve_integra_cuando_las_huellas_coinciden() -> None:
    huella = HuellaDeIntegridad(HEXADECIMAL_VALIDO)

    assert evaluar(huella, huella) is EstadoDeIntegridad.INTEGRA


def test_evaluar_devuelve_comprometida_ante_discrepancia() -> None:
    """D-09: la evidencia comprometida se marca y se muestra; nunca se borra ni se oculta."""
    persistida = HuellaDeIntegridad(HEXADECIMAL_VALIDO)
    recalculada = HuellaDeIntegridad(OTRO_HEXADECIMAL)

    assert evaluar(persistida, recalculada) is EstadoDeIntegridad.COMPROMETIDA


def test_evaluar_es_una_funcion_pura_sin_efectos() -> None:
    """No borra, no marca en ningún lado, no escribe: sólo dice qué estado corresponde."""
    persistida = HuellaDeIntegridad(HEXADECIMAL_VALIDO)
    recalculada = HuellaDeIntegridad(OTRO_HEXADECIMAL)

    primero = evaluar(persistida, recalculada)
    segundo = evaluar(persistida, recalculada)

    assert primero is segundo
    assert persistida.valor == HEXADECIMAL_VALIDO


# --------------------------------------------------------------------------- #
# Lápida (D-10)
# --------------------------------------------------------------------------- #


def test_la_lapida_lleva_huella_motivo_autor_e_instante() -> None:
    """Todo hueco tiene explicación: sin eso la cadena queda con un agujero mudo."""
    lapida = Lapida(
        sha256=HuellaDeIntegridad(HEXADECIMAL_VALIDO),
        motivo="purga manual por antigüedad mayor a 5 años",
        autor=UsuarioId("usuario-1"),
        ocurrido_en=InstanteUtc("2026-07-25T22:24:45+00:00"),
    )

    assert lapida.sha256.valor == HEXADECIMAL_VALIDO
    assert lapida.autor == "usuario-1"


@pytest.mark.parametrize("faltante", ["motivo", "autor"])
def test_la_lapida_no_se_construye_sin_motivo_ni_sin_autor(faltante: str) -> None:
    campos = {
        "sha256": HuellaDeIntegridad(HEXADECIMAL_VALIDO),
        "motivo": "purga manual por antigüedad",
        "autor": UsuarioId("usuario-1"),
        "ocurrido_en": InstanteUtc("2026-07-25T22:24:45+00:00"),
    }
    campos[faltante] = ""

    with pytest.raises(ValueError, match=faltante):
        Lapida(**campos)  # type: ignore[arg-type]


def test_la_lapida_omitida_por_completo_no_compila() -> None:
    """Los cuatro campos son obligatorios en la firma, no validados a posteriori."""
    with pytest.raises(TypeError):
        Lapida(sha256=HuellaDeIntegridad(HEXADECIMAL_VALIDO))  # type: ignore[call-arg]


def test_la_lapida_es_inmutable() -> None:
    lapida = Lapida(
        sha256=HuellaDeIntegridad(HEXADECIMAL_VALIDO),
        motivo="purga manual",
        autor=UsuarioId("usuario-1"),
        ocurrido_en=InstanteUtc("2026-07-25T22:24:45+00:00"),
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        lapida.motivo = "otro"  # type: ignore[misc]
