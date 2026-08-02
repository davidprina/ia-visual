"""Los valores de tiempo del dominio, todos persistibles como texto o como entero.

**Por qué ningún valor de acá lleva un `datetime`.** Pitfall 4, verificado: se persiste
`datetime.now(timezone.utc)` en una columna `DateTime(timezone=True)` de SQLite y al
leerla vuelve **naive** — se guardó `2026-07-25 22:24:45.076838` y se leyó con
`tzinfo: None`. El código que después hace `.astimezone()` interpreta ese naive como hora
local y desplaza tres horas todo el histórico. SQLite no tiene tipo de fecha, así que el
dialecto serializa a texto sin offset y al leer reconstruye sin zona.

La consecuencia se absorbe en el tipo, no en la capa de persistencia: el valor
persistible es **siempre** texto ISO-8601 con offset (`InstanteUtc`) más un entero de
minutos aparte (`Desfasaje`), más la fecha local como texto `AAAA-MM-DD` (`FechaLocal`).
Es ordenable lexicográficamente, no depende del dialecto y hace explícito lo que D-05 y
D-37 piden guardar. `datetime` aparece sólo como parámetro o como valor de retorno de un
método de conversión, jamás como estado.

**Dos relojes con roles que no se mezclan** (Patrón 7):

* `InstanteMonotono` — nanosegundos crudos de `time.perf_counter_ns()`. Sirve para medir
  **deltas** con paso de 100 ns; sólo es comparable dentro de la misma corrida del
  proceso. Es el espacio donde se calcula el desvío entre cámaras, y por eso ese desvío
  es preciso a microsegundos.
* `InstanteUtc` — el sello de calendario que se lee y se audita. Su precisión
  **absoluta** hereda la del reloj de pared del equipo (~15,6 ms en Windows con Python
  3.12), y el sistema **declara** esa incertidumbre en el manifiesto en vez de callarla.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from typing import Final, NewType

# SABOTAJE DELIBERADO — rama de prueba `prueba/compuerta-en-rojo`, Tarea 4 del plan 01-01.
# `cv2` está en `forbidden_modules` del contrato `dominio_limpio` (pyproject.toml). Esta
# línea existe para provocar la compuerta en rojo y comprobar que la protección de rama
# bloquea la fusión. NO fusionar esta rama: se cierra el pull request y se borra.
import cv2  # noqa: F401

__all__ = [
    "Desfasaje",
    "FechaLocal",
    "InstanteMonotono",
    "InstanteUtc",
]

#: Nanosegundos de `time.perf_counter_ns()`. Entero, nunca flotante: un flotante de
#: doble precisión pierde resolución de nanosegundo con los valores que devuelve el
#: contador de rendimiento después de unas horas de proceso vivo.
InstanteMonotono = NewType("InstanteMonotono", int)

#: `AAAA-MM-DD`, la clave de agrupación de D-37/D-38 y el directorio de D-03.
PATRON_FECHA_LOCAL: Final = re.compile(r"^\d{4}-\d{2}-\d{2}$")

#: Un offset horario válido está estrictamente dentro de ±24 h.
MINUTOS_DE_UN_DIA: Final = 24 * 60


@dataclass(frozen=True, slots=True)
class InstanteUtc:
    """Un instante de calendario, persistible como texto ISO-8601 **con offset**.

    Ejemplo: `2026-07-25T22:24:45.133966+00:00`. El offset explícito es lo que hace que
    el texto no dependa de quién lo lea, y es exactamente lo que Pitfall 4 muestra que
    se pierde cuando el tipo de la columna intenta ser inteligente.
    """

    texto: str

    def __post_init__(self) -> None:
        try:
            momento = dt.datetime.fromisoformat(self.texto)
        except ValueError as error:
            raise ValueError(
                f"«{self.texto}» no es un instante ISO-8601 válido. El formato es "
                "AAAA-MM-DDTHH:MM:SS[.ffffff]±HH:MM, por ejemplo "
                "2026-07-25T22:24:45.133966+00:00."
            ) from error

        if momento.utcoffset() is None:
            raise ValueError(
                f"«{self.texto}» es un instante ISO-8601 sin offset, y un instante sin "
                "offset no dice nada: quien lo lea va a suponer una zona horaria y va a "
                "suponer mal. Agregá el offset explícito, por ejemplo "
                "2026-07-25T22:24:45.133966+00:00."
            )

    @classmethod
    def desde_datetime(cls, momento: dt.datetime) -> InstanteUtc:
        """Convierte un `datetime` **con zona** en el valor persistible.

        Es el único punto donde `datetime` entra al dominio, y entra como parámetro de
        una conversión: lo que queda guardado es el texto.
        """
        if momento.tzinfo is None or momento.utcoffset() is None:
            raise ValueError(
                "El instante recibido no tiene zona horaria. Un `datetime` naive "
                "obliga a adivinar la zona, y adivinar es justamente lo que produce el "
                "corrimiento de tres horas de Pitfall 4."
            )
        return cls(momento.isoformat())

    def como_datetime(self) -> dt.datetime:
        """Devuelve el `datetime` con zona para **calcular**, nunca para persistir."""
        return dt.datetime.fromisoformat(self.texto)

    def __str__(self) -> str:
        return self.texto


@dataclass(frozen=True, slots=True)
class Desfasaje:
    """El offset local vigente, en minutos enteros y guardado aparte (D-37).

    Se persiste como entero y no como texto porque es el dato con el que se reagrupa:
    `-180` es Argentina. La representación `±HH:MM` es para mostrar y para componer el
    texto ISO.
    """

    minutos: int

    def __post_init__(self) -> None:
        if not -MINUTOS_DE_UN_DIA < self.minutos < MINUTOS_DE_UN_DIA:
            raise ValueError(
                f"{self.minutos} no es un desfasaje horario posible: tiene que estar "
                f"estrictamente entre -{MINUTOS_DE_UN_DIA} y {MINUTOS_DE_UN_DIA} "
                "minutos. Argentina es -180."
            )

    @classmethod
    def desde_minutos(cls, minutos: int) -> Desfasaje:
        """Construye el desfasaje desde minutos enteros. `-180` es Argentina."""
        return cls(minutos)

    @property
    def texto(self) -> str:
        """La representación `±HH:MM` que se compone en el texto ISO-8601."""
        signo = "-" if self.minutos < 0 else "+"
        horas, restantes = divmod(abs(self.minutos), 60)
        return f"{signo}{horas:02d}:{restantes:02d}"

    def __str__(self) -> str:
        return self.texto


@dataclass(frozen=True, slots=True)
class FechaLocal:
    """El día local del equipo, `AAAA-MM-DD` (D-37 y D-38).

    Agrupa evidencia y reportes, ordena el directorio de D-03 y corta a **medianoche
    local**: el turno noche queda partido en dos días, igual que en la contabilidad y en
    el ERP. Sin parámetros de jornada ni modelado de turnos.

    Se guarda como texto de ancho fijo justamente para que el orden lexicográfico y el
    cronológico coincidan.
    """

    texto: str

    def __post_init__(self) -> None:
        valida = bool(PATRON_FECHA_LOCAL.match(self.texto))
        if valida:
            try:
                dt.date.fromisoformat(self.texto)
            except ValueError:
                valida = False

        if not valida:
            raise ValueError(
                f"«{self.texto}» no es una fecha local válida. El formato es AAAA-MM-DD "
                "con los ceros de relleno, por ejemplo 2026-07-25."
            )

    @classmethod
    def desde_date(cls, dia: dt.date) -> FechaLocal:
        """Convierte un `date` en el valor persistible."""
        return cls(dia.isoformat())

    def __str__(self) -> str:
        return self.texto
