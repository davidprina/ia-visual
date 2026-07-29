"""El reloj del proceso, medido en la plataforma de destino.

Vive en `tests/integracion` y no en `tests/dominio` porque estas pruebas **miden la
máquina**: preguntan qué resolución tiene el reloj de rendimiento y qué resolución tiene
el reloj de pared, y fallan si la primera no alcanza para la ventana de ±150 ms de D-39.

La medición que fuerza la decisión (RESEARCH §Pitfall 1, verificada en Windows 11 con
Python 3.12): `time.monotonic()` se implementa con `GetTickCount64()` y produjo **20
valores distintos en 300 ms**; `time.perf_counter()` usa `QueryPerformanceCounter()` y
produjo **717 804**. Medir ±150 ms con un reloj de 15,625 ms de paso es arrancar con un
10 % de error de cuantización.
"""

from __future__ import annotations

import datetime as dt
import time

import pytest

from porteria.aplicacion.puertos.salida.reloj import Reloj
from porteria.dominio.comun.tiempo import Desfasaje, FechaLocal, InstanteUtc
from porteria.infraestructura.runtime.reloj import RelojDelProceso, RelojFijo

#: D-39 mide una ventana de ±150 ms; un reloj con paso de más de 1 µs no alcanza.
RESOLUCION_MAXIMA_ADMITIDA_S = 1e-6

REPETICIONES_DE_MONOTONIA = 100


# --------------------------------------------------------------------------- #
# Prueba de guardia de la plataforma
# --------------------------------------------------------------------------- #


def test_el_reloj_de_rendimiento_de_la_plataforma_alcanza_para_la_ventana() -> None:
    """Si esto falla, la plataforma no puede medir lo que la evidencia promete."""
    resolucion = time.get_clock_info("perf_counter").resolution

    assert resolucion <= RESOLUCION_MAXIMA_ADMITIDA_S, (
        f"El reloj de rendimiento de esta plataforma tiene una resolución de "
        f"{resolucion} s y el máximo admitido es {RESOLUCION_MAXIMA_ADMITIDA_S} s.\n"
        "Con ese paso NO se puede medir la ventana de ±150 ms de D-39: el desvío entre "
        "cámaras se reportaría en múltiplos del paso del reloj y la evidencia diría "
        "«sincronizada» sin haberlo medido.\n"
        "Qué revisar: que el intérprete sea CPython 3.12 o superior sobre una "
        "plataforma donde `perf_counter` use un contador de alta resolución "
        "(QueryPerformanceCounter en Windows, clock_gettime(MONOTONIC) en POSIX)."
    )


def test_el_reloj_del_proceso_no_usa_el_reloj_de_pared_para_medir() -> None:
    """`datetime.now(UTC)` devolvió el mismo valor cinco veces seguidas (RESEARCH).

    Es la contraprueba de la decisión: el reloj de pared es un calendario, no un
    cronómetro. Si esta prueba dejara de encontrar repetidos, sería porque la
    plataforma mejoró — no porque el reloj de pared sirva para medir deltas.
    """
    reloj = RelojDelProceso()

    instantes = [reloj.instante() for _ in range(5)]

    assert len(set(instantes)) == 5, (
        "El reloj del proceso repitió valores en cinco llamadas seguidas, que es "
        f"justamente lo que hace el reloj de pared. Valores: {instantes}"
    )


def test_dos_llamadas_consecutivas_siempre_devuelven_valores_distintos() -> None:
    """100 de 100: con paso de 100 ns, dos llamadas de Python nunca coinciden."""
    reloj = RelojDelProceso()
    repetidos = [
        (primero, segundo)
        for primero, segundo in (
            (reloj.instante(), reloj.instante()) for _ in range(REPETICIONES_DE_MONOTONIA)
        )
        if primero == segundo
    ]

    assert not repetidos, (
        f"{len(repetidos)} de {REPETICIONES_DE_MONOTONIA} pares consecutivos "
        "devolvieron el mismo instante. Señal de alerta de Pitfall 1: el reloj tiene "
        "menos resolución de la que declara."
    )


def test_los_instantes_no_retroceden() -> None:
    reloj = RelojDelProceso()

    instantes = [reloj.instante() for _ in range(1_000)]

    assert instantes == sorted(instantes)


# --------------------------------------------------------------------------- #
# El ancla a UTC
# --------------------------------------------------------------------------- #


def test_el_reloj_del_proceso_cumple_el_puerto() -> None:
    assert isinstance(RelojDelProceso(), Reloj)
    assert isinstance(RelojFijo(), Reloj)


def test_utc_de_devuelve_un_instante_utc_persistible() -> None:
    reloj = RelojDelProceso()

    sello = reloj.utc_de(reloj.instante())

    assert isinstance(sello, InstanteUtc)
    assert sello.texto.endswith("+00:00"), (
        f"El sello persistible tiene que llevar su offset explícito: {sello.texto!r}"
    )


def test_utc_de_deriva_el_delta_del_ancla_y_no_del_reloj_de_pared() -> None:
    """Dos instantes separados por 50 ms de `perf_counter` distan 50 ms en UTC.

    Es lo que hace defendible la afirmación auditable: la precisión **relativa** entre
    fotos es de microsegundos aunque el sello absoluto herede los ~15,6 ms del ancla.
    """
    reloj = RelojDelProceso()
    base = reloj.instante()

    primero = reloj.utc_de(base)
    segundo = reloj.utc_de(base + 50_000_000)

    delta = dt.datetime.fromisoformat(segundo.texto) - dt.datetime.fromisoformat(primero.texto)

    assert abs(delta.total_seconds() - 0.050) < 1e-6


def test_utc_de_es_una_funcion_pura_del_instante() -> None:
    """Dos traducciones del mismo instante dan el mismo texto: no relee el reloj."""
    reloj = RelojDelProceso()
    instante = reloj.instante()

    assert reloj.utc_de(instante).texto == reloj.utc_de(instante).texto


def test_reanclar_tras_suspension_mueve_el_ancla() -> None:
    """Y eso es correcto, no un defecto.

    `QueryPerformanceCounter` no avanza durante la suspensión y el reloj de pared sí,
    así que después de un resume el ancla vieja traduce mal. Que `utc_de` cambie para
    un mismo instante es la prueba de que el ancla se movió.
    """
    reloj = RelojDelProceso()
    instante = reloj.instante()
    antes = reloj.utc_de(instante)

    time.sleep(0.01)
    reloj.reanclar_tras_suspension()
    despues = reloj.utc_de(instante)

    assert antes.texto != despues.texto


# --------------------------------------------------------------------------- #
# Fecha local y desfasaje (D-37, D-38)
# --------------------------------------------------------------------------- #


def test_la_fecha_local_es_la_del_equipo() -> None:
    reloj = RelojDelProceso()

    fecha = reloj.fecha_local()

    assert isinstance(fecha, FechaLocal)
    assert fecha.texto == dt.datetime.now().astimezone().date().isoformat()


def test_el_desfasaje_local_es_el_del_equipo() -> None:
    reloj = RelojDelProceso()
    esperado = dt.datetime.now().astimezone().utcoffset()
    assert esperado is not None

    desfasaje = reloj.desfasaje_local()

    assert isinstance(desfasaje, Desfasaje)
    assert desfasaje.minutos == int(esperado.total_seconds() // 60)


# --------------------------------------------------------------------------- #
# La incertidumbre del sello absoluto (Open Question 3)
# --------------------------------------------------------------------------- #


def test_la_incertidumbre_del_sello_se_mide_y_no_se_cablea() -> None:
    """El valor sale de la plataforma, no de una constante del código.

    En Windows con Python 3.12 son ~15,6 ms porque `time.time` usa
    `GetSystemTimeAsFileTime`. En 3.14 baja a 1e-7. La evidencia **declara** el número
    que midió el equipo en vez de callarlo, que es la misma jugada que D-39 hace con la
    ventana de ±150 ms.
    """
    reloj = RelojDelProceso()

    incertidumbre = reloj.incertidumbre_sello_ms()

    assert incertidumbre > 0
    assert incertidumbre == time.get_clock_info("time").resolution * 1000


# --------------------------------------------------------------------------- #
# El doble determinista
# --------------------------------------------------------------------------- #


def test_el_reloj_fijo_no_avanza_solo() -> None:
    reloj = RelojFijo(inicial_ns=1_000)

    assert reloj.instante() == 1_000
    time.sleep(0.01)
    assert reloj.instante() == 1_000


def test_el_reloj_fijo_avanza_lo_que_la_prueba_le_pide() -> None:
    reloj = RelojFijo()
    inicial = reloj.instante()

    reloj.avanzar_ms(150)

    assert reloj.instante() == inicial + 150_000_000


def test_el_reloj_fijo_traduce_a_utc_de_forma_determinista() -> None:
    reloj = RelojFijo(inicial_ns=0, ancla_utc="2026-07-25T22:00:00+00:00")

    reloj.avanzar_ms(1_500)

    assert reloj.utc_de(reloj.instante()).texto == "2026-07-25T22:00:01.500000+00:00"


def test_la_fixture_del_reloj_determinista_es_el_reloj_fijo() -> None:
    """El doble de `conftest.py` y el del producto tienen que ser el mismo objeto.

    Si fueran dos, el doble de las pruebas podría dejar de cumplir el puerto `Reloj`
    sin que nada lo delate — y entonces las pruebas de dominio estarían verificando un
    contrato que la aplicación no usa.
    """
    from tests.conftest import RelojDeterminista

    assert RelojDeterminista is RelojFijo


@pytest.mark.parametrize("metodo", ["instante", "utc_de", "fecha_local", "desfasaje_local"])
def test_el_reloj_fijo_implementa_todo_el_puerto(metodo: str) -> None:
    assert callable(getattr(RelojFijo(), metodo))
