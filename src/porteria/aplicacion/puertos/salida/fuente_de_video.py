"""Puerto `FuenteDeVideo`: de dónde salen los cuadros, y con qué contrato de frescura.

**Los dos perfiles se declaran desde el día uno, aunque hoy devuelvan lo mismo (D-15).**
En la Fase 1 la única fuente es un archivo y devuelve el mismo flujo para el perfil de
monitoreo y para el de evidencia. En la Fase 2, con cámaras IP, el visor consume el
sub-stream liviano —640×360, unos pocos fps— y la captura toma del main-stream a
resolución plena. Es la palanca de mayor impacto y menor costo sobre el consumo de CPU del
puesto de portería, y retro-agregar el parámetro obligaría a tocar todos los llamadores
que hasta entonces se hubieran escrito sin él.

**Por qué `FrameSellado` vive acá y no en `infraestructura`.** El puerto lo nombra en su
firma, y el contrato de capas —`cli` → `infraestructura` → `aplicacion` → `dominio`—
prohíbe que `aplicacion` importe de `infraestructura`. Un puerto es dueño del dato que
mueve: el DTO va con el puerto y el adaptador lo importa desde acá.

`datos` se declara `Any` a propósito: lleva un `numpy.ndarray` y el tipo del arreglo no
puede aparecer en esta capa. Ese arreglo **nunca cruza al dominio** — el dominio razona
sobre huellas, instantes y desvíos, no sobre píxeles.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, runtime_checkable

__all__ = ["FrameSellado", "FuenteDeVideo", "PerfilDeFlujo"]


class PerfilDeFlujo(Enum):
    """Para qué se pide el cuadro: para mirar, o para guardar como evidencia (D-15)."""

    #: Vista viva del operador. Tolera resolución baja y descarte agresivo: lo único que
    #: importa es que lo que se ve en pantalla sea de **ahora**.
    MONITOREO = "monitoreo"

    #: El cuadro que se sella, se hashea y se audita. Resolución plena, y el desvío contra
    #: el instante del disparo se mide y se persiste.
    EVIDENCIA = "evidencia"


@dataclass(frozen=True, slots=True, eq=False)
class FrameSellado:
    """Un cuadro con el instante en que se lo capturó, no con el que dice el contenedor.

    `instante_captura_ns` es el `time.perf_counter_ns()` tomado **inmediatamente después
    de que el decodificador devuelve el cuadro**. No es el PTS del contenedor: el PTS mide
    tiempo de reproducción y no tiempo real transcurrido, así que con un consumidor lento
    el PTS seguiría avanzando prolijo mientras la antigüedad real crece sin techo — que es
    exactamente el fallo que hay que poder detectar.

    **`eq=False` no es un descuido.** El `__eq__` que genera `dataclass` compararía
    `datos == datos`, y comparar dos `numpy.ndarray` devuelve un arreglo de booleanos:
    cualquier `frame_a == frame_b`, `frame in lista` o `assert frame == esperado`
    levantaría `ValueError: truth value of an array with more than one element is
    ambiguous`. Con `eq=False` la igualdad es por identidad, que es la semántica correcta
    para un cuadro: dos capturas del mismo instante nominal no son "el mismo cuadro".
    """

    #: `numpy.ndarray` BGR. Nunca cruza al dominio.
    datos: Any

    #: `time.perf_counter_ns()` tras el decode. Sólo comparable dentro de la corrida.
    instante_captura_ns: int

    #: Número de orden dentro de la fuente, desde 0. Es lo que permite distinguir un
    #: cuadro nuevo de uno repetido sin comparar píxeles.
    secuencia: int


@runtime_checkable
class FuenteDeVideo(Protocol):
    """De dónde salen los cuadros: un archivo hoy, una cámara IP en la Fase 2.

    `runtime_checkable` para que una prueba pueda afirmar que una implementación cumple el
    protocolo; el contrato completo lo verifica el verificador de tipos.

    **Fin de flujo y fuente caída son estados, no excepciones.** `esta_viva()` es el dato
    que la interfaz muestra y `tomar_mas_reciente` devuelve `None`. Una fuente que levanta
    una excepción por quedarse sin cuadros obligaría a envolver cada llamada en un
    `try/except` y tarde o temprano alguien lo escribiría como `except: pass`.
    """

    def abrir(self) -> None:
        """Abre la fuente y arranca su hilo de decodificación.

        Un hilo por fuente, aislado: una excepción en una fuente no puede tumbar a otra ni
        al proceso. Levanta sólo si la fuente no se puede abrir en absoluto.
        """
        ...

    def cerrar(self) -> None:
        """Detiene el hilo y libera el recurso. Idempotente."""
        ...

    def tomar_mas_reciente(
        self, perfil: PerfilDeFlujo, timeout: float | None = None
    ) -> FrameSellado | None:
        """Devuelve el cuadro **más reciente** disponible, o `None` si no hay.

        Nunca devuelve el más viejo de una cola: el contrato de frescura es slot de
        capacidad 1 con descarte del más viejo.
        """
        ...

    def metricas(self) -> Mapping[str, object]:
        """Las métricas en memoria de esta fuente (D-17), para consola y panel."""
        ...

    def esta_viva(self) -> bool:
        """`False` cuando la fuente terminó o se cayó. Estado normal, no error."""
        ...
