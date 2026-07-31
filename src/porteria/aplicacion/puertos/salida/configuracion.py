"""Puerto `Configuracion`: los parámetros de operación entran al sistema por inyección.

Es la capa 2 de D-30 vista desde adentro. Lo que el caso de uso necesita es «cuál es la
ventana de aceptación vigente» y «cuál es la calidad de JPEG de esta cámara», no «leé la
tabla `configuracion`». Con el puerto declarado acá, el dominio y los casos de uso quedan
ignorantes de dónde vive el valor —hoy SQLite, mañana lo que sea— y las pruebas pueden
inyectar un doble sin montar una base.

**Por qué `escribir` exige autor.** Es T-01-22 y es D-40: un cambio de configuración es un
hecho auditable, no un ajuste anónimo. Nadie ensancha la ventana de aceptación para que
capturas viejas pasen de estimadas a sincronizadas sin dejar quién y cuándo. Que el autor
sea un parámetro **obligatorio de la firma** es lo que hace que olvidarlo sea un error de
llamada y no una omisión silenciosa.

**Por qué el DTO vive acá y no en el adaptador.** El puerto lo nombra en la firma de
`listar()`, y el contrato de capas prohíbe que `aplicacion` importe de `infraestructura`.
Es la misma razón por la que `FrameSellado` vive con el puerto de video y no con el slot.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

__all__ = ["Configuracion", "ValorDeConfiguracion"]


@dataclass(frozen=True, slots=True)
class ValorDeConfiguracion:
    """Un parámetro con su rastro: qué vale, quién lo cambió y cuándo.

    `cambiado_por` y `cambiado_en_utc_iso` son `None` cuando la clave nunca se escribió y
    el valor que se está mostrando es el que declara el catálogo. Es deliberado: inventar
    un autor para un valor por defecto sería fabricar un rastro que nadie dejó, y un
    rastro fabricado es peor que ninguno.
    """

    clave: str
    valor: Any
    cambiado_por: str | None = None
    cambiado_en_utc_iso: str | None = None

    @property
    def es_valor_por_defecto(self) -> bool:
        """Verdadero si nadie tocó nunca esta clave."""
        return self.cambiado_por is None


@runtime_checkable
class Configuracion(Protocol):
    """La capa 2 de D-30: todo lo que no es una ruta de arranque.

    `runtime_checkable` para que una prueba pueda afirmar que una implementación cumple el
    protocolo. La comprobación en tiempo de ejecución sólo verifica que los métodos
    existan; el contrato completo lo verifica el verificador de tipos.
    """

    def leer(self, clave: str) -> Any:
        """Devuelve el valor vigente, ya tipado, o el que declara el catálogo."""
        ...

    def escribir(self, clave: str, valor: Any, autor: str) -> None:
        """Persiste el valor junto con quién lo cambió y cuándo. Sin autor, falla."""
        ...

    def listar(self) -> Mapping[str, ValorDeConfiguracion]:
        """Devuelve **todas** las claves del catálogo, tocadas o no, con su rastro."""
        ...
