"""Implementaciones del puerto `Reloj`: la del proceso y la determinista.

**Por qué `time.perf_counter_ns()` y no `time.monotonic_ns()`** — es la decisión más
barata de tomar hoy y la más cara de cambiar después, porque el desvío entre cámaras
queda persistido y cambiar el reloj obliga a reinterpretar toda la evidencia ya guardada.

Medición hecha en Windows 11 con Python 3.12, con `time.get_clock_info` y muestreo en
bucle apretado:

| Reloj                | Implementación                | Resolución | Valores distintos en 300 ms |
|----------------------|-------------------------------|------------|-----------------------------|
| `time.monotonic`     | `GetTickCount64()`            | 0,015625 s | **20**                      |
| `time.perf_counter`  | `QueryPerformanceCounter()`   | 1e-07 s    | **717 804**                 |
| `time.time`          | `GetSystemTimeAsFileTime()`   | 0,015625 s | —                           |

El reloj obvio —`time.monotonic()`— tiene un paso de 15,625 ms hasta Python 3.12
inclusive; recién 3.13 pasa a `QueryPerformanceCounter`. Medir la ventana de ±150 ms de
D-39 con ese paso es arrancar con un 10 % de error de cuantización: dos fotos tomadas con
10 ms de diferencia reportarían desvío 0 y la evidencia diría "sincronizada" sin haberlo
medido. `CLAUDE.md` fija Python 3.12 por compatibilidad de ruedas, y esa elección
—correcta— arrastra este costo, que se absorbe acá.

**La contrapartida, dicha con honestidad.** `GetTickCount64` **sí** avanza durante la
suspensión del equipo y `QueryPerformanceCounter` se comporta mal a través de
suspend/resume. La elección es correcta para lo que esta fase mide —sub-segundo, dentro de
una sesión— e **incorrecta** para medir horas a través de una suspensión: el cronómetro de
espera de la Fase 8 tiene que usar UTC persistido, no el reloj de rendimiento. Y ésa es la
razón por la que el ancla vive en un objeto con `reanclar_tras_suspension()` y no en dos
variables sueltas.

**Los dos relojes y el ancla que los une.** El de rendimiento mide deltas con paso de
100 ns pero no sabe qué día es; el de pared sabe qué día es pero tiene 15,6 ms de paso y
puede saltar hacia atrás si alguien corrige la hora. El ancla `(instante, UTC)` se toma
una vez y todo sello UTC posterior se **deriva** de ella, de modo que la precisión relativa
entre fotos de la misma captura es de microsegundos aunque el sello absoluto sea grueso.
`incertidumbre_sello_ms()` declara cuán grueso es, medido en este equipo.
"""

from __future__ import annotations

import datetime as dt
import time

from porteria.dominio.comun.tiempo import Desfasaje, FechaLocal, InstanteUtc

__all__ = ["RelojDelProceso", "RelojFijo"]

#: Nanosegundos en un milisegundo.
NS_POR_MS = 1_000_000

#: Milisegundos en un segundo, para pasar la resolución de `get_clock_info` a ms.
MS_POR_S = 1_000


class RelojDelProceso:
    """El reloj real: contador de rendimiento para medir, ancla a UTC para sellar."""

    def __init__(self) -> None:
        self._anclar()

    # ----------------------------------------------------------------- ancla #

    def _anclar(self) -> None:
        """Toma el par `(instante de rendimiento, UTC de pared)` que une los relojes."""
        self._ancla_instante_ns = time.perf_counter_ns()
        self._ancla_utc = dt.datetime.now(dt.UTC)

    def reanclar_tras_suspension(self) -> None:
        """Vuelve a tomar el ancla porque la anterior quedó inválida.

        El contador de rendimiento no avanza mientras el equipo está suspendido y el
        reloj de pared sí. Después de un resume, el ancla vieja traduce mal: un instante
        tomado antes de la suspensión se traduciría a un UTC anterior al real por toda la
        duración del sueño. Que `utc_de` devuelva otro texto después de reanclar es el
        comportamiento correcto, no un defecto.
        """
        self._anclar()

    # ---------------------------------------------------------------- puerto #

    def instante(self) -> int:
        """Instante del proceso en nanosegundos, con paso de 100 ns."""
        return time.perf_counter_ns()

    def utc_de(self, instante_ns: int) -> InstanteUtc:
        """Traduce un instante del proceso a UTC derivándolo del ancla.

        No vuelve a leer el reloj de pared: si lo hiciera, dos fotos de la misma captura
        heredarían dos lecturas distintas de un reloj con 15,6 ms de paso y el desvío
        medido entre ellas sería ruido del reloj, no desvío real de las cámaras.
        """
        microsegundos = (instante_ns - self._ancla_instante_ns) / 1_000
        return InstanteUtc.desde_datetime(
            self._ancla_utc + dt.timedelta(microseconds=microsegundos)
        )

    def fecha_local(self) -> FechaLocal:
        """El día local del equipo (D-37), que corta a medianoche local (D-38)."""
        return FechaLocal.desde_date(dt.datetime.now().astimezone().date())

    def desfasaje_local(self) -> Desfasaje:
        """El offset local vigente del equipo, en minutos enteros."""
        offset = dt.datetime.now().astimezone().utcoffset()
        if offset is None:  # pragma: no cover - `astimezone()` siempre deja zona
            raise RuntimeError(
                "El sistema operativo no informó el desfasaje horario local. Qué "
                "revisar: la configuración de zona horaria del equipo."
            )
        return Desfasaje.desde_minutos(int(offset.total_seconds() // 60))

    def incertidumbre_sello_ms(self) -> float:
        """Resolución del reloj de pared de **este** equipo, en milisegundos.

        Se mide, no se cablea: en Windows con Python 3.12 son ~15,625 ms porque
        `time.time` usa `GetSystemTimeAsFileTime`; en 3.14 baja a 1e-4 ms. El número que
        entra en el manifiesto es el de la máquina donde se tomó la evidencia.
        """
        return time.get_clock_info("time").resolution * MS_POR_S


class RelojFijo:
    """El doble determinista: el instante lo decide quien prueba, no el sistema.

    Vive en el producto y no en `tests/` a propósito. Es la misma pieza que D-48 describe
    para los falsos en memoria: el doble que se ejercita en cada corrida de pruebas no se
    pudre, y el día que haga falta un modo demostración con tiempo controlado ya está.
    """

    def __init__(
        self,
        inicial_ns: int = 0,
        ancla_utc: str = "2026-01-01T00:00:00+00:00",
        desfasaje_minutos: int = -180,
        incertidumbre_sello_ms: float = 15.625,
    ) -> None:
        self._instante_ns = inicial_ns
        self._ancla_instante_ns = inicial_ns
        self._ancla_utc = InstanteUtc(ancla_utc).como_datetime()
        self._desfasaje = Desfasaje.desde_minutos(desfasaje_minutos)
        self._incertidumbre_sello_ms = incertidumbre_sello_ms

    # ------------------------------------------------------------- gobierno #

    def fijar_ns(self, instante_ns: int) -> int:
        """Fija el instante de forma absoluta y devuelve el nuevo."""
        self._instante_ns = instante_ns
        return self._instante_ns

    def avanzar_ms(self, milisegundos: float) -> int:
        """Adelanta el reloj los milisegundos pedidos y devuelve el nuevo instante."""
        self._instante_ns += int(milisegundos * NS_POR_MS)
        return self._instante_ns

    def instante_ns(self) -> int:
        """Alias de `instante()`, por el nombre con que nació la fixture en 01-01."""
        return self.instante()

    # ---------------------------------------------------------------- puerto #

    def instante(self) -> int:
        return self._instante_ns

    def utc_de(self, instante_ns: int) -> InstanteUtc:
        microsegundos = (instante_ns - self._ancla_instante_ns) / 1_000
        return InstanteUtc.desde_datetime(
            self._ancla_utc + dt.timedelta(microseconds=microsegundos)
        )

    def fecha_local(self) -> FechaLocal:
        desplazado = self.utc_de(self._instante_ns).como_datetime() + dt.timedelta(
            minutes=self._desfasaje.minutos
        )
        return FechaLocal.desde_date(desplazado.date())

    def desfasaje_local(self) -> Desfasaje:
        return self._desfasaje

    def incertidumbre_sello_ms(self) -> float:
        return self._incertidumbre_sello_ms
