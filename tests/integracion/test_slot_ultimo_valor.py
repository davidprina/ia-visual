"""El contrato de frescura como código: slot de capacidad 1, descarte del más viejo.

**Qué se está fijando acá y por qué no se puede retrofitear.** El punto de encuentro
entre el hilo que decodifica y el que consume es la pieza que decide si la foto es del
instante del botón o de dieciséis segundos antes. Medido en la investigación, con el
mismo video y el mismo consumidor a 5 Hz:

| | Slot de capacidad 1 | Cola ilimitada (el antipatrón) |
|---|---|---|
| Antigüedad mediana, 1.ª mitad | 25,8 ms | 4 152,7 ms |
| Antigüedad mediana, 2.ª mitad | **13,9 ms** (baja) | **12 218,7 ms** (sube) |
| Pendiente de crecimiento | ≈ 0 | **+806,6 ms por segundo** |
| Frames descartados | 403 de 503 | 0 — se acumulan |

Retro-imponer el contrato obliga a tocar interfaz, dominio y captura a la vez, así que se
fija ahora aunque las cámaras IP lleguen recién en la Fase 2.

**Estas pruebas viven en `integracion/` y no en `dominio/` a propósito:** ejercitan hilos
reales y el reloj real. No hay reloj falso en ninguna, porque lo que se mide es el
comportamiento de dos hilos concurrentes de verdad.
"""

from __future__ import annotations

import queue
import statistics
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pytest

from porteria.aplicacion.puertos.salida.fuente_de_video import (
    FrameSellado,
    FuenteDeVideo,
    PerfilDeFlujo,
)
from porteria.infraestructura.video import falsa as modulo_falsa
from porteria.infraestructura.video.falsa import FuenteFalsa
from porteria.infraestructura.video.metricas import (
    CLAVES_DE_METRICAS,
    MetricasDeFuente,
    RegistroDeMetricas,
)
from porteria.infraestructura.video.slot_ultimo_valor import SlotUltimoValor

#: Tope de duración de una llamada a `publicar`, en milisegundos, **sin consumidor
#: concurrente**. Sin otro hilo compitiendo no hay conmutación del GIL de por medio y el
#: tope del plan se sostiene tal cual.
TOPE_PUBLICAR_MS = 1.0

#: Topes con un consumidor concurrente. La mediana y el percentil 99 conservan el número
#: del plan —1 ms—; el **máximo** no puede: está acotado por abajo por el intervalo de
#: conmutación del GIL, no por el diseño del slot. Ver `TOPE_MAXIMO_MS`.
TOPE_MEDIANA_MS = 1.0
TOPE_P99_MS = 1.0

#: Cinco intervalos de conmutación del GIL. Se deriva de `sys.getswitchinterval()`
#: —5,000 ms en este equipo— en vez de cablear un número: cuando un hilo cede el GIL, el
#: que espera el lock puede quedar demorado hasta un intervalo completo aunque el lock
#: esté libre. Medido bajo pytest: máximos de hasta 4,4 ms, todos por debajo de **un**
#: intervalo. Un productor realmente bloqueado por el consumidor mide 195 ms —el período
#: del consumidor—, ocho veces por encima de este tope, así que la separación entre "ruido
#: del planificador" y "el productor espera al consumidor" es limpia.
TOPE_MAXIMO_MS = 5 * sys.getswitchinterval() * 1000

#: Piso que tiene que superar la contraprueba para demostrar que la medición detecta un
#: productor bloqueado. La mitad del período del consumidor a 5 Hz.
PISO_DE_BLOQUEO_MS = 100.0

NS_POR_MS = 1_000_000


def _frame(secuencia: int, instante_ns: int | None = None) -> FrameSellado:
    """Un frame sellado mínimo, con datos que no son `None` para no probar de mentira."""
    return FrameSellado(
        datos=np.zeros((4, 4, 3), dtype=np.uint8),
        instante_captura_ns=time.perf_counter_ns() if instante_ns is None else instante_ns,
        secuencia=secuencia,
    )


# --------------------------------------------------------------------------- #
# El frame sellado
# --------------------------------------------------------------------------- #


def test_el_frame_sellado_es_inmutable() -> None:
    """Sellado significa sellado: nadie reescribe el instante de captura después."""
    frame = _frame(0)

    with pytest.raises((AttributeError, TypeError)):
        frame.instante_captura_ns = 0  # type: ignore[misc]


def test_comparar_dos_frames_no_revienta_por_el_arreglo_de_numpy() -> None:
    """La igualdad campo por campo compararía dos `ndarray` y `bool()` de eso levanta.

    Es un defecto latente del patrón copiado: `dataclass(frozen=True)` genera un `__eq__`
    que compara `datos == datos`, lo que devuelve un arreglo de booleanos y hace
    `ValueError: truth value of an array with more than one element is ambiguous` en
    cualquier `frame_a == frame_b`, `frame in lista` o `assert frame == esperado`.
    """
    uno, otro = _frame(0), _frame(1)

    assert (uno == otro) is False
    assert uno == uno
    assert uno in [uno, otro]


# --------------------------------------------------------------------------- #
# El slot: el productor nunca bloquea
# --------------------------------------------------------------------------- #


def test_publicar_no_bloquea_con_el_consumidor_detenido() -> None:
    """Sin ningún consumidor, publicar cien veces sigue siendo instantáneo."""
    slot = SlotUltimoValor()
    peor_ms = 0.0

    for numero in range(100):
        antes = time.perf_counter_ns()
        slot.publicar(_frame(numero))
        peor_ms = max(peor_ms, (time.perf_counter_ns() - antes) / NS_POR_MS)

    assert peor_ms < TOPE_PUBLICAR_MS, (
        f"La peor llamada a `publicar` tardó {peor_ms:.3f} ms sin ningún consumidor "
        f"activo, y el tope es {TOPE_PUBLICAR_MS} ms. Si el productor espera, el "
        "decodificador se frena y el buffer de red aguas arriba se llena: es exactamente "
        "lo que el contrato de frescura prohíbe."
    )


def test_publicar_dos_veces_descarta_el_viejo_y_deja_el_nuevo() -> None:
    """El descarte se cuenta en el mismo lugar donde ocurre, y queda el más reciente."""
    slot = SlotUltimoValor()

    slot.publicar(_frame(1))
    slot.publicar(_frame(2))

    assert slot.metricas["frames_descartados"] == 1
    entregado = slot.tomar(timeout=0.1)
    assert entregado is not None
    assert entregado.secuencia == 2, (
        "El slot entregó el frame viejo. Descarte del más viejo significa que lo que "
        "queda disponible es siempre el último publicado."
    )


def test_tomar_vacia_el_slot() -> None:
    """Un frame se entrega una sola vez: el slot no repite el último."""
    slot = SlotUltimoValor()
    slot.publicar(_frame(1))

    assert slot.tomar(timeout=0.1) is not None
    assert slot.metricas["ocupado"] is False
    assert slot.tomar(timeout=0.05) is None


def test_tomar_con_el_slot_vacio_espera_hasta_el_timeout_y_devuelve_none() -> None:
    """Con el slot vacío el consumidor espera; no gira en vacío ni levanta."""
    slot = SlotUltimoValor()

    antes = time.perf_counter_ns()
    resultado = slot.tomar(timeout=0.15)
    esperado_ms = (time.perf_counter_ns() - antes) / NS_POR_MS

    assert resultado is None
    assert esperado_ms >= 100.0, (
        f"`tomar` volvió en {esperado_ms:.1f} ms con un timeout de 150 ms: no esperó. "
        "Sin espera bloqueante el consumidor tiene que girar en vacío quemando CPU."
    )


def test_tomar_se_despierta_cuando_el_productor_publica() -> None:
    """La espera se corta al publicar, no al vencer el timeout."""
    slot = SlotUltimoValor()

    def publicar_mas_tarde() -> None:
        time.sleep(0.05)
        slot.publicar(_frame(7))

    hilo = threading.Thread(target=publicar_mas_tarde, name="productor-tardio")
    hilo.start()
    try:
        antes = time.perf_counter_ns()
        entregado = slot.tomar(timeout=5.0)
        tardanza_ms = (time.perf_counter_ns() - antes) / NS_POR_MS
    finally:
        hilo.join(timeout=5.0)

    assert entregado is not None
    assert entregado.secuencia == 7
    assert tardanza_ms < 1000.0, (
        f"El consumidor tardó {tardanza_ms:.1f} ms en recibir un frame publicado a los "
        "50 ms: la notificación no está despertando la espera."
    )


def test_mil_publicaciones_y_diez_consumos_descartan_novecientos_noventa() -> None:
    """La cuenta exacta del contrato: 1000 publicados, 10 consumidos, 990 descartados."""
    slot = SlotUltimoValor()

    for ronda in range(10):
        for numero in range(100):
            slot.publicar(_frame(ronda * 100 + numero))
        assert slot.tomar(timeout=0.1) is not None

    metricas = slot.metricas
    assert metricas["frames_publicados"] == 1000
    assert metricas["frames_descartados"] == 990, (
        "La cuenta de descartes no cierra. En cada ronda el primer publicado entra en un "
        "slot vacío (no descarta) y los 99 siguientes descartan: 10 × 99 = 990."
    )
    assert metricas["frames_consumidos"] == 10
    assert metricas["ocupado"] is False


@dataclass(frozen=True)
class MedicionDePublicacion:
    """Lo que tardó cada `publicar` con un consumidor lento corriendo en paralelo."""

    duraciones_ms: list[float]
    consumidos: int
    fallas: list[Exception]

    @property
    def mediana_ms(self) -> float:
        return statistics.median(self.duraciones_ms)

    @property
    def p99_ms(self) -> float:
        ordenadas = sorted(self.duraciones_ms)
        return ordenadas[min(int(len(ordenadas) * 0.99), len(ordenadas) - 1)]

    @property
    def maxima_ms(self) -> float:
        return max(self.duraciones_ms)

    def resumen(self) -> str:
        return (
            f"{len(self.duraciones_ms)} publicaciones · mediana {self.mediana_ms:.4f} ms "
            f"· p99 {self.p99_ms:.4f} ms · máximo {self.maxima_ms:.4f} ms"
        )


def medir_publicaciones(
    publicar: Callable[[FrameSellado], None],
    tomar: Callable[[], FrameSellado | None],
    segundos: float,
) -> MedicionDePublicacion:
    """Corre un productor a 200 Hz contra un consumidor a 5 Hz y cronometra `publicar`.

    Se extrae como función propia para que la contraprueba use **exactamente la misma
    medición** sobre el antipatrón. Si cada prueba cronometrara a su manera, la
    contraprueba no demostraría nada sobre esta medición.

    Los hilos van como `daemon` a propósito: con el antipatrón el productor termina
    bloqueado dentro de `put()` esperando al consumidor, y un hilo no-daemon en ese estado
    cuelga el intérprete al salir. Que haga falta esa precaución para el antipatrón y no
    para el slot ya dice todo.
    """
    fin = threading.Event()
    duraciones_ms: list[float] = []
    fallas: list[Exception] = []
    consumidos = 0

    def producir() -> None:
        secuencia = 0
        try:
            while not fin.is_set():
                antes = time.perf_counter_ns()
                publicar(_frame(secuencia))
                duraciones_ms.append((time.perf_counter_ns() - antes) / NS_POR_MS)
                secuencia += 1
                time.sleep(0.005)  # 200 Hz
        except Exception as error:  # se reporta en la aserción del hilo principal
            fallas.append(error)

    def consumir() -> None:
        nonlocal consumidos
        try:
            while not fin.is_set():
                if tomar() is not None:
                    consumidos += 1
                time.sleep(0.2)  # 5 Hz
        except Exception as error:  # se reporta en la aserción del hilo principal
            fallas.append(error)

    productor = threading.Thread(target=producir, name="productor-200hz", daemon=True)
    consumidor = threading.Thread(target=consumir, name="consumidor-5hz", daemon=True)
    productor.start()
    consumidor.start()
    time.sleep(segundos)
    fin.set()
    consumidor.join(timeout=5.0)
    tomar()  # libera a un productor que hubiera quedado esperando al consumidor
    productor.join(timeout=5.0)

    return MedicionDePublicacion(duraciones_ms, consumidos, fallas)


def test_productor_a_200_hz_y_consumidor_a_5_hz_conservan_el_contador() -> None:
    """Tres segundos de concurrencia real: sin excepciones y sin perder la cuenta.

    **Sobre el tope del máximo, que no es el del plan.** El plan pedía que ninguna llamada
    a `publicar` superara 1 ms. Medido en este equipo, ese criterio no mide el slot sino el
    planificador de CPython: `sys.getswitchinterval()` es de 5 ms, y cuando el consumidor
    cede el GIL el productor puede quedar demorado hasta un intervalo completo aunque el
    lock esté libre. Bajo pytest aparecieron máximos de 4,4 ms de forma reproducible —tres
    de tres— con el slot funcionando perfectamente.

    Lo que sí es medible, y es lo que el criterio quería decir, son tres cosas a la vez:
    mediana y percentil 99 por debajo del milisegundo del plan (medido: 0,016 ms y
    0,10 ms), y máximo por debajo de cinco intervalos de conmutación. La contraprueba de
    más abajo demuestra que esta medición detecta un productor realmente bloqueado.
    """
    slot = SlotUltimoValor()

    medicion = medir_publicaciones(
        slot.publicar, lambda: slot.tomar(timeout=0.2), segundos=3.0
    )

    assert not medicion.fallas, f"Un hilo levantó una excepción: {medicion.fallas!r}"

    metricas = slot.metricas
    ocupado = 1 if metricas["ocupado"] else 0
    assert metricas["frames_publicados"] == (
        metricas["frames_descartados"] + metricas["frames_consumidos"] + ocupado
    ), (
        "El contador no se conserva: cada frame publicado tiene que estar descartado, "
        f"consumido o todavía en el slot. Métricas: {metricas}"
    )
    assert metricas["frames_descartados"] > 0, (
        "Con un productor a 200 Hz y un consumidor a 5 Hz tiene que haber descartes. "
        "Cero descartes con consumidor lento es la señal de que la latencia se acumula "
        "en otro lado (Pitfall 7)."
    )
    assert medicion.mediana_ms < TOPE_MEDIANA_MS, (
        f"La mediana de `publicar` fue {medicion.mediana_ms:.4f} ms y el tope es "
        f"{TOPE_MEDIANA_MS} ms. {medicion.resumen()}"
    )
    assert medicion.p99_ms < TOPE_P99_MS, (
        f"El percentil 99 de `publicar` fue {medicion.p99_ms:.4f} ms y el tope es "
        f"{TOPE_P99_MS} ms. {medicion.resumen()}"
    )
    assert medicion.maxima_ms < TOPE_MAXIMO_MS, (
        f"La peor llamada a `publicar` tardó {medicion.maxima_ms:.4f} ms y el tope son "
        f"cinco intervalos de conmutación del GIL ({TOPE_MAXIMO_MS:.1f} ms). Un productor "
        "bloqueado por el consumidor mide del orden de 195 ms, así que esto no es ruido "
        f"del planificador. {medicion.resumen()}"
    )


def test_la_medicion_detecta_un_productor_bloqueado_por_el_consumidor() -> None:
    """Prueba de la prueba: la misma medición contra el antipatrón tiene que fallar.

    Monta a propósito `queue.Queue(maxsize=1)` —la estructura obvia de la biblioteca
    estándar, la que el contrato prohíbe— y comprueba que la medición de más arriba la
    delata. Sin esta contraprueba, un tope mal escrito pasaría siempre y nadie se
    enteraría de que la medición no distingue nada.

    Medido: con la cola el productor publica **16 veces en 3 segundos** contra 557 del
    slot, y su mediana es de 195 ms —exactamente el período del consumidor a 5 Hz—. El
    `put()` no está lento: está esperando. Trasladado a una cámara, esperar es frenar el
    decodificador y llenar el buffer de red aguas arriba, donde ninguna métrica lo ve.
    """
    cola: queue.Queue[FrameSellado] = queue.Queue(maxsize=1)

    def tomar() -> FrameSellado | None:
        try:
            return cola.get(timeout=0.2)
        except queue.Empty:
            return None

    medicion = medir_publicaciones(cola.put, tomar, segundos=2.0)

    assert medicion.mediana_ms > PISO_DE_BLOQUEO_MS, (
        "La medición no detectó el bloqueo del productor contra una `queue.Queue"
        f"(maxsize=1)`: mediana {medicion.mediana_ms:.4f} ms, y se esperaba por encima de "
        f"{PISO_DE_BLOQUEO_MS} ms. Si el antipatrón pasa la medición, entonces la prueba "
        f"del slot no está verificando nada. {medicion.resumen()}"
    )
    assert medicion.mediana_ms > TOPE_MEDIANA_MS, (
        "El antipatrón cumpliría el tope que se le exige al slot. La medición sería "
        f"vacua. {medicion.resumen()}"
    )


# --------------------------------------------------------------------------- #
# El puerto: los dos perfiles desde el día uno (D-15)
# --------------------------------------------------------------------------- #


def test_el_perfil_de_flujo_declara_exactamente_monitoreo_y_evidencia() -> None:
    """D-15: los dos perfiles se declaran hoy aunque hoy devuelvan lo mismo.

    Retro-agregar el parámetro obligaría a tocar todos los llamadores en la Fase 2,
    cuando el visor pase a consumir el sub-stream liviano y la captura el main-stream.
    """
    assert {miembro.name for miembro in PerfilDeFlujo} == {"MONITOREO", "EVIDENCIA"}


def test_la_fuente_falsa_cumple_el_puerto() -> None:
    """El doble de prueba de NUC-04 y el motor del modo demostración de D-48."""
    assert isinstance(FuenteFalsa(), FuenteDeVideo)


def test_la_fuente_falsa_no_abre_ningun_archivo() -> None:
    """Sin OpenCV en el módulo: el doble no depende de que haya un video en el disco."""
    assert not hasattr(modulo_falsa, "cv2"), (
        "`falsa.py` importó OpenCV. El doble de prueba tiene que generar sus cuadros en "
        "memoria: si dependiera de un archivo, dejaría de servir como falso del modo "
        "demostración de D-48."
    )


def test_la_fuente_falsa_genera_cuadros_deterministas() -> None:
    """El mismo número de secuencia produce siempre el mismo cuadro, en cualquier equipo."""
    uno = FuenteFalsa.cuadro_de(42)
    otro = FuenteFalsa.cuadro_de(42)
    distinto = FuenteFalsa.cuadro_de(43)

    assert np.array_equal(uno, otro)
    assert not np.array_equal(uno, distinto), (
        "Dos cuadros de secuencias distintas salieron idénticos: una prueba de frescura "
        "no podría distinguir un cuadro nuevo de uno repetido."
    )


def test_la_fuente_falsa_entrega_los_cuadros_que_genera() -> None:
    """Ejercitada en cada corrida, la fuente falsa no se pudre (D-48)."""
    fuente = FuenteFalsa(hz=200.0)
    fuente.abrir()
    try:
        entregado = fuente.tomar_mas_reciente(PerfilDeFlujo.MONITOREO, timeout=2.0)
        assert entregado is not None
        assert np.array_equal(entregado.datos, FuenteFalsa.cuadro_de(entregado.secuencia))
        assert fuente.esta_viva() is True
    finally:
        fuente.cerrar()

    assert fuente.esta_viva() is False


def test_la_fuente_falsa_devuelve_el_mismo_flujo_para_los_dos_perfiles() -> None:
    """En la Fase 1 los dos perfiles son el mismo flujo, y eso está declarado."""
    fuente = FuenteFalsa(hz=200.0)
    fuente.abrir()
    try:
        monitoreo = fuente.tomar_mas_reciente(PerfilDeFlujo.MONITOREO, timeout=2.0)
        evidencia = fuente.tomar_mas_reciente(PerfilDeFlujo.EVIDENCIA, timeout=2.0)
    finally:
        fuente.cerrar()

    assert monitoreo is not None
    assert evidencia is not None
    assert "perfil" in (FuenteFalsa.tomar_mas_reciente.__doc__ or "").lower()


def test_la_fuente_falsa_termina_al_agotar_los_cuadros_pedidos() -> None:
    """Fin de flujo es un estado normal, no una excepción."""
    fuente = FuenteFalsa(hz=500.0, cuadros=3)
    fuente.abrir()
    try:
        limite = time.perf_counter_ns() + 5 * 1_000_000_000
        while fuente.esta_viva() and time.perf_counter_ns() < limite:
            fuente.tomar_mas_reciente(PerfilDeFlujo.MONITOREO, timeout=0.05)
        assert fuente.esta_viva() is False
        assert fuente.metricas()["frames_publicados"] == 3
    finally:
        fuente.cerrar()


# --------------------------------------------------------------------------- #
# Las métricas por fuente (D-17)
# --------------------------------------------------------------------------- #


def test_las_metricas_exponen_las_claves_del_contrato() -> None:
    """Lo que la consola y el panel de estado de la Fase 2 leen, declarado en un lugar."""
    metricas = MetricasDeFuente(SlotUltimoValor())
    volcado = metricas.como_diccionario()

    for clave in (
        "frames_descartados",
        "frames_publicados",
        "ocupado",
        "antiguedad_ultimo_ms",
        "fps_efectivos",
        "reconexiones",
    ):
        assert clave in volcado, f"Falta la clave «{clave}» en el volcado de métricas."

    assert set(volcado) == set(CLAVES_DE_METRICAS)


def test_la_antiguedad_es_la_diferencia_entre_entrega_y_captura() -> None:
    """La definición operativa, la misma que después se persiste y se reporta.

    `antiguedad_ms = (instante_de_entrega − instante_de_captura) / 1e6`. **No** es el
    PTS del contenedor, que mide tiempo de reproducción y no tiempo real transcurrido.
    """
    metricas = MetricasDeFuente(SlotUltimoValor())
    cincuenta_ms_atras = time.perf_counter_ns() - 50 * NS_POR_MS

    metricas.publicar(_frame(0, instante_ns=cincuenta_ms_atras))
    assert metricas.tomar(timeout=0.1) is not None

    antiguedad = metricas.como_diccionario()["antiguedad_ultimo_ms"]
    assert isinstance(antiguedad, float)
    assert 45.0 <= antiguedad <= 80.0, (
        f"La antigüedad medida fue {antiguedad:.1f} ms para un frame sellado 50 ms "
        "antes de entregarse. La fórmula no es la del contrato."
    )


def test_los_fps_efectivos_salen_de_los_instantes_de_captura() -> None:
    """Se derivan de los sellos de los frames, no del reloj de la prueba.

    Que la medición salga del dato y no del momento en que corre la prueba es lo que la
    hace exacta en cualquier equipo, incluido un runner de integración continua cargado.
    """
    metricas = MetricasDeFuente(SlotUltimoValor())
    base = time.perf_counter_ns()

    for numero in range(11):
        metricas.publicar(_frame(numero, instante_ns=base + numero * 10 * NS_POR_MS))

    assert metricas.como_diccionario()["fps_efectivos"] == pytest.approx(100.0, abs=0.01)


def test_las_reconexiones_arrancan_en_cero_y_se_cuentan() -> None:
    """La Fase 2 puebla este contador con las cámaras IP; el hueco existe desde hoy."""
    metricas = MetricasDeFuente(SlotUltimoValor())
    assert metricas.como_diccionario()["reconexiones"] == 0

    metricas.registrar_reconexion()
    assert metricas.como_diccionario()["reconexiones"] == 1


def test_las_metricas_no_escriben_nada_en_el_camino_critico() -> None:
    """D-17: acumulador en memoria. La ventana deslizante está acotada."""
    metricas = MetricasDeFuente(SlotUltimoValor(), ventana=8)
    base = time.perf_counter_ns()

    for numero in range(1000):
        metricas.publicar(_frame(numero, instante_ns=base + numero * NS_POR_MS))

    assert metricas.tamano_de_la_ventana() <= 8, (
        "La ventana de métricas creció con el tiempo de ejecución. Un acumulador que "
        "crece sin techo es una fuga de memoria en un puesto que corre todo el turno."
    )


def test_el_registro_de_metricas_arranca_vacio_y_olvida_lo_que_se_cierra() -> None:
    """`porteria metricas` sobre un proceso sin fuentes tiene que decir la verdad."""
    registro = RegistroDeMetricas()
    assert registro.instantanea() == {}

    metricas = MetricasDeFuente(SlotUltimoValor())
    registro.registrar("camara-1", metricas)
    assert "camara-1" in registro.instantanea()

    registro.olvidar("camara-1")
    assert registro.instantanea() == {}
