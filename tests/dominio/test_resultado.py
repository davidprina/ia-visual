"""El vocabulario común del dominio: identificadores, tiempo, resultado y eventos.

Cuatro módulos y una sola prueba por propiedad, porque lo que se está fijando acá es
contrato no retrofiteable: los nombres de los tipos, el formato del número legible
(D-29), la forma persistible del tiempo (Pitfall 4) y las tres variantes de `Resultado`.

**Por qué el tiempo se prueba acá y no en `tests/integracion`.** Nada de esto toca el
reloj real: `InstanteUtc`, `Desfasaje` y `FechaLocal` son texto validado. El reloj vive
en `tests/integracion/test_reloj_del_proceso.py`, que sí mide la plataforma.
"""

from __future__ import annotations

import dataclasses
import typing

import pytest

from porteria.dominio.comun import tiempo as modulo_tiempo
from porteria.dominio.comun.identificadores import (
    CamaraId,
    CapturaId,
    ItemDeEvidenciaId,
    NumeroLegible,
    RemitoId,
    UsuarioId,
    ViajeId,
)
from porteria.dominio.comun.resultado import (
    VARIANTES,
    Degradado,
    NoDisponible,
    Ok,
    Resultado,
)
from porteria.dominio.comun.tiempo import Desfasaje, FechaLocal, InstanteMonotono, InstanteUtc
from porteria.dominio.eventos import EventoDeDominio

# --------------------------------------------------------------------------- #
# Identificadores (D-29)
# --------------------------------------------------------------------------- #

TODOS_LOS_IDENTIFICADORES = (
    CapturaId,
    CamaraId,
    ViajeId,
    RemitoId,
    ItemDeEvidenciaId,
    UsuarioId,
)


def test_cada_identificador_es_un_tipo_distinto() -> None:
    """Seis `NewType` distintos, no seis alias de `str`.

    Es lo que hace que pasar un `ViajeId` donde se espera un `CapturaId` sea un error
    que el verificador de tipos marca, en vez de una confusión que se descubre con la
    evidencia ya persistida y asociada al viaje equivocado.
    """
    assert len(set(TODOS_LOS_IDENTIFICADORES)) == len(TODOS_LOS_IDENTIFICADORES)

    for identificador in TODOS_LOS_IDENTIFICADORES:
        assert identificador.__supertype__ is str, (
            f"«{identificador.__name__}» no es un NewType sobre str. El identificador "
            "opaco de D-29 se persiste como texto."
        )


def test_el_instante_monotono_es_un_tipo_distinto_sobre_entero() -> None:
    """Los nanosegundos de `perf_counter_ns` son enteros, nunca flotantes."""
    assert InstanteMonotono.__supertype__ is int


@pytest.mark.parametrize("texto", ["2026-001842", "1999-000001", "2026-999999"])
def test_el_numero_legible_acepta_el_formato_de_d29(texto: str) -> None:
    assert NumeroLegible(texto).texto == texto


@pytest.mark.parametrize(
    "texto",
    ["2026-1842", "26-001842", "2026-0018422", "2026001842", "", "AAAA-NNNNNN", "2026-00184a"],
)
def test_el_numero_legible_rechaza_todo_lo_demas(texto: str) -> None:
    """`2026-1842` y `26-001842` son los dos casos que el plan nombra explícitamente."""
    with pytest.raises(ValueError, match="AAAA-NNNNNN"):
        NumeroLegible(texto)


def test_el_numero_legible_expone_su_anio_y_su_secuencia() -> None:
    numero = NumeroLegible("2026-001842")

    assert numero.anio == 2026
    assert numero.secuencia == 1842
    assert str(numero) == "2026-001842"


def test_el_numero_legible_se_construye_desde_anio_y_secuencia() -> None:
    assert NumeroLegible.de(2026, 1842) == NumeroLegible("2026-001842")


# --------------------------------------------------------------------------- #
# Tiempo (Pitfall 4, D-37, D-38)
# --------------------------------------------------------------------------- #


def test_ningun_valor_persistible_del_tiempo_es_un_datetime() -> None:
    """Pitfall 4: `DateTime(timezone=True)` en SQLite vuelve *naive* al leer.

    La consecuencia se paga en el esquema del plan 01-05, así que la barrera se pone
    en el tipo: todo campo de los valores exportados por `comun.tiempo` es texto o
    entero. `datetime` puede aparecer como parámetro o como valor de retorno de un
    método de conversión, nunca como estado del valor.
    """
    admitidos = {str, int, float}
    revisados = 0

    for nombre in modulo_tiempo.__all__:
        tipo = getattr(modulo_tiempo, nombre)
        if not dataclasses.is_dataclass(tipo):
            continue

        revisados += 1
        anotaciones = typing.get_type_hints(tipo)
        for campo in dataclasses.fields(tipo):
            assert anotaciones[campo.name] in admitidos, (
                f"«{tipo.__name__}.{campo.name}» se anota como "
                f"{anotaciones[campo.name]!r}. El valor persistible del tiempo es "
                "siempre texto ISO-8601 con offset más un entero de desfasaje: un "
                "`datetime` con `tzinfo` pierde la zona al volver de SQLite "
                "(Pitfall 4) y desplaza todo el histórico."
            )

    assert revisados >= 3, (
        "Se revisaron menos de tres valores del tiempo. La prueba pasaría en vacío si "
        f"`__all__` dejara de exportarlos. Revisados: {revisados}"
    )


@pytest.mark.parametrize(
    "texto",
    [
        "2026-07-25T19:24:45.133966-03:00",
        "2026-07-25T22:24:45.133966+00:00",
        "2026-07-25T22:24:45+00:00",
    ],
)
def test_el_instante_utc_acepta_iso8601_con_offset(texto: str) -> None:
    assert InstanteUtc(texto).texto == texto


@pytest.mark.parametrize(
    "texto",
    [
        "2026-07-25T22:24:45.133966",  # sin offset: el caso exacto de Pitfall 4
        "2026-07-25 22:24:45",
        "25/07/2026 22:24",
        "",
    ],
)
def test_el_instante_utc_rechaza_lo_que_no_lleva_offset(texto: str) -> None:
    with pytest.raises(ValueError, match="ISO-8601"):
        InstanteUtc(texto)


def test_el_desfasaje_argentino_se_representa_como_menos_tres() -> None:
    assert Desfasaje.desde_minutos(-180).texto == "-03:00"
    assert str(Desfasaje.desde_minutos(-180)) == "-03:00"


@pytest.mark.parametrize(
    ("minutos", "esperado"),
    [(0, "+00:00"), (-180, "-03:00"), (330, "+05:30"), (-570, "-09:30"), (720, "+12:00")],
)
def test_el_desfasaje_se_representa_con_signo_y_dos_puntos(minutos: int, esperado: str) -> None:
    assert Desfasaje.desde_minutos(minutos).texto == esperado


@pytest.mark.parametrize("minutos", [1440, -1440, 5000])
def test_el_desfasaje_rechaza_lo_que_no_es_un_offset(minutos: int) -> None:
    with pytest.raises(ValueError, match="desfasaje"):
        Desfasaje.desde_minutos(minutos)


@pytest.mark.parametrize("texto", ["2026-07-25", "1999-01-01"])
def test_la_fecha_local_acepta_el_formato_de_agrupacion(texto: str) -> None:
    assert FechaLocal(texto).texto == texto


@pytest.mark.parametrize("texto", ["25-07-2026", "2026-7-25", "2026-13-01", "2026-07-32", ""])
def test_la_fecha_local_rechaza_todo_lo_demas(texto: str) -> None:
    with pytest.raises(ValueError, match="AAAA-MM-DD"):
        FechaLocal(texto)


def test_la_fecha_local_ordena_lexicograficamente() -> None:
    """D-38: la fecha local es la clave de agrupación y del directorio de D-03."""
    fechas = [FechaLocal("2026-07-25"), FechaLocal("2026-01-02"), FechaLocal("2025-12-31")]

    assert [f.texto for f in sorted(fechas, key=lambda f: f.texto)] == [
        "2025-12-31",
        "2026-01-02",
        "2026-07-25",
    ]


# --------------------------------------------------------------------------- #
# Resultado
# --------------------------------------------------------------------------- #


def test_resultado_tiene_exactamente_tres_variantes() -> None:
    """Tres y no cuatro: agregar una cuarta obliga a revisar cada `match` del sistema."""
    assert VARIANTES == (Ok, NoDisponible, Degradado)
    assert len(VARIANTES) == 3


def test_el_alias_resultado_une_las_tres_variantes() -> None:
    """`type Resultado[T] = …` guarda la unión perezosa en `__value__` (PEP 695).

    Se inspecciona el alias además de `VARIANTES` para que las dos declaraciones no
    puedan divergir: una cuarta variante agregada sólo a la unión quedaría fuera de la
    tupla, y una quitada de la unión seguiría figurando en ella.
    """
    partes = typing.get_args(Resultado.__value__)

    assert {typing.get_origin(parte) or parte for parte in partes} == set(VARIANTES)


def test_ok_lleva_el_valor_y_nada_mas() -> None:
    assert Ok(42).valor == 42


def test_no_disponible_lleva_motivo_y_detalles() -> None:
    """El motivo es lo que se le muestra al portero; los detalles alimentan reportes."""
    resultado = NoDisponible("faltan pesos teóricos: ART-1, ART-2", ("ART-1", "ART-2"))

    assert "ART-1" in resultado.motivo
    assert resultado.detalles == ("ART-1", "ART-2")


def test_degradado_lleva_valor_motivo_y_antiguedad() -> None:
    """Un dato viejo sirve, pero el dominio tiene que poder decir cuán viejo es."""
    resultado = Degradado(31_500.0, "última lectura de la balanza en caché", 4_200.0)

    assert resultado.valor == 31_500.0
    assert resultado.antiguedad_ms == 4_200.0


def test_las_tres_variantes_se_consumen_con_match() -> None:
    """El dominio opera con datos ausentes sin `try/except` con semántica de negocio."""

    def describir(resultado: Resultado[float]) -> str:
        match resultado:
            case Ok(valor=valor):
                return f"exacto:{valor}"
            case Degradado(valor=valor, antiguedad_ms=antiguedad):
                return f"viejo:{valor}:{antiguedad}"
            case NoDisponible(motivo=motivo):
                return f"ausente:{motivo}"
        raise AssertionError("variante no contemplada")

    assert describir(Ok(1.0)) == "exacto:1.0"
    assert describir(Degradado(1.0, "caché", 10.0)) == "viejo:1.0:10.0"
    assert describir(NoDisponible("sin PALJET")) == "ausente:sin PALJET"


@pytest.mark.parametrize(
    ("variante", "campo"),
    [(Ok(1), "valor"), (NoDisponible("x"), "motivo"), (Degradado(1, "x", 2.0), "valor")],
)
def test_las_variantes_son_inmutables(variante: object, campo: str) -> None:
    """Un resultado que se puede editar después de producido deja de ser una respuesta."""
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(variante, campo, "otro")


# --------------------------------------------------------------------------- #
# Eventos de dominio
# --------------------------------------------------------------------------- #


def test_el_evento_de_dominio_lleva_los_dos_relojes() -> None:
    """El sello UTC es para leer; el instante monotónico es para medir (Patrón 7)."""
    evento = EventoDeDominio(
        nombre="evidencia.agregada",
        ocurrido_en=InstanteUtc("2026-07-25T22:24:45.133966+00:00"),
        instante_monotono_ns=1_234_567_890,
        datos={"camara_id": "carga-1"},
    )

    assert evento.nombre == "evidencia.agregada"
    assert evento.instante_monotono_ns == 1_234_567_890
    assert evento.datos["camara_id"] == "carga-1"


def test_los_datos_del_evento_no_se_pueden_modificar() -> None:
    """Un evento acumulado y después editado es un evento que miente."""
    evento = EventoDeDominio(
        nombre="evidencia.agregada",
        ocurrido_en=InstanteUtc("2026-07-25T22:24:45+00:00"),
        instante_monotono_ns=1,
        datos={"camara_id": "carga-1"},
    )

    with pytest.raises(TypeError):
        evento.datos["camara_id"] = "otra"  # type: ignore[index]


def test_modificar_el_diccionario_de_origen_no_altera_el_evento() -> None:
    origen = {"camara_id": "carga-1"}
    evento = EventoDeDominio(
        nombre="evidencia.agregada",
        ocurrido_en=InstanteUtc("2026-07-25T22:24:45+00:00"),
        instante_monotono_ns=1,
        datos=origen,
    )

    origen["camara_id"] = "otra"

    assert evento.datos["camara_id"] == "carga-1"


def test_el_evento_rechaza_un_nombre_vacio() -> None:
    with pytest.raises(ValueError, match="nombre"):
        EventoDeDominio(
            nombre="",
            ocurrido_en=InstanteUtc("2026-07-25T22:24:45+00:00"),
            instante_monotono_ns=1,
        )
