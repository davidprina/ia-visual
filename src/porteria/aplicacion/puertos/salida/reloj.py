"""Puerto `Reloj`: el tiempo entra al sistema por inyección, no por `import time`.

**Por qué es un puerto.** Un `import time` dentro del dominio o de un caso de uso vuelve
imposible una prueba determinista: no se puede afirmar "el desvío de esta cámara fue de
82 ms" si el instante lo decide la máquina en el momento de correr. Con el reloj
inyectado, la prueba fija los instantes y el resultado es el mismo en cualquier equipo y
a cualquier hora — que es exactamente lo que hace verificable la ventana de ±150 ms de
D-39.

**Por qué `incertidumbre_sello_ms` es parte del puerto.** El sello UTC absoluto hereda la
resolución del reloj de pared del equipo: ~15,6 ms en Windows con Python 3.12, porque
`time.time` usa `GetSystemTimeAsFileTime`. El desvío **relativo** entre cámaras, en
cambio, se calcula enteramente en espacio `perf_counter` y es preciso a microsegundos.
Medir esa incertidumbre es infraestructura; **declararla** en el manifiesto es evidencia.
El puerto la expone para que el dominio pueda declararla sin leer ningún reloj: es la
misma jugada que D-39 hace con la ventana: decir el número en vez de callarlo.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from porteria.dominio.comun.tiempo import Desfasaje, FechaLocal, InstanteUtc

__all__ = ["Reloj"]


@runtime_checkable
class Reloj(Protocol):
    """El único origen de tiempo del sistema.

    `runtime_checkable` para que una prueba pueda afirmar que una implementación cumple
    el protocolo. La comprobación en tiempo de ejecución sólo verifica que los métodos
    existan; el contrato completo lo verifica el verificador de tipos.
    """

    def instante(self) -> int:
        """Instante monotónico del proceso en nanosegundos, para medir **deltas**.

        Sólo comparable dentro de la misma corrida del proceso.
        """
        ...

    def utc_de(self, instante_ns: int) -> InstanteUtc:
        """Traduce un instante monotónico al sello UTC persistible.

        Se deriva del ancla; no vuelve a leer el reloj de pared. Dos llamadas con el
        mismo instante devuelven el mismo texto mientras el ancla no se mueva.
        """
        ...

    def fecha_local(self) -> FechaLocal:
        """El día local del equipo (D-37), que corta a medianoche local (D-38)."""
        ...

    def desfasaje_local(self) -> Desfasaje:
        """El offset local vigente, que se persiste aparte del sello UTC."""
        ...

    def incertidumbre_sello_ms(self) -> float:
        """Resolución real del reloj de **pared** del equipo, en milisegundos.

        Es la incertidumbre del sello UTC absoluto. Se mide en el equipo donde corre, no
        se cablea como constante, y entra en el hash del manifiesto.
        """
        ...
