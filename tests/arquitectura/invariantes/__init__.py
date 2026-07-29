"""Invariantes de código declaradas por cada plan de la fase.

Cada plan agrega su propio `inv_01_0N.py` exponiendo `INVARIANTES` y nada más, para que
ningún plan de la misma ola edite el archivo de otro.
`tests/arquitectura/test_invariantes_de_codigo.py` los descubre con
`pkgutil.iter_modules` y convierte cada entrada en una prueba parametrizada.

**Por qué existe esta maquinaria.** Reemplaza los criterios de aceptación basados en
`grep` de los diez planes de la fase, y no por prolijidad: la plataforma de compuerta es
**Windows únicamente** (D-54) y ni el shell del runner ni el del cliente garantizan
`grep`. Varios de esos criterios definen propiedades de seguridad —cero `unlink` en el
módulo de cuarentena, cero `pickle` en el grabador, cero `permisos` en la orden de
usuarios—, y cuando el comando no existe, «no se pudo verificar» se lee como «pasó».
Convertidas en aserciones de pytest corren en cualquier plataforma y quedan como
regresión permanente en vez de una comprobación manual de una sola vez.

**Por qué el tipo `Invariante` vive acá y no en el módulo de prueba.** Si lo declarara
`test_invariantes_de_codigo.py`, cada `inv_01_0N.py` tendría que importar el módulo de
prueba que a su vez los importa a ellos, y el ciclo sólo funcionaría mientras nadie
moviera una línea. El paquete que declara las invariantes es el dueño natural del tipo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

#: `presente` exige al menos una coincidencia; `ausente` exige cero.
Modo = Literal["presente", "ausente"]


@dataclass(frozen=True)
class Invariante:
    """Una propiedad del texto de un archivo que tiene que seguir siendo cierta.

    Attributes:
        ruta: Ruta relativa a la raíz del repositorio. Si el archivo no existe, la
            prueba falla nombrándolo: significa que el plan que declaró la invariante
            no creó el módulo.
        modo: `"presente"` o `"ausente"`.
        patron: Expresión regular a buscar.
        motivo: Texto en español que se imprime al fallar. Es lo que alguien va a leer
            por teléfono desde una planta sin área de sistemas (UI-05), así que dice
            qué revisar y no sólo qué falló.
        ignorar_comentarios: Por defecto `True`. Descarta comentarios y docstrings antes
            de buscar, porque la prosa de un encabezado que explica **por qué** algo no
            debe existir invalidaría la propia invariante. Los literales de cadena que
            no son docstrings se conservan: varias invariantes de la fase buscan
            patrones que viven dentro de una cadena.
        solo_primeras_lineas: Acota la búsqueda a las primeras N líneas. El blanqueo de
            prosa conserva la numeración, así que sigue midiendo el archivo real.
        ignorar_mayusculas: Busca sin distinguir mayúsculas de minúsculas.
    """

    ruta: str
    modo: Modo
    patron: str
    motivo: str
    ignorar_comentarios: bool = True
    solo_primeras_lineas: int | None = None
    ignorar_mayusculas: bool = False

    def identificador(self) -> str:
        """Nombre legible para el informe de pytest."""
        return f"{self.ruta}[{self.modo}:{self.patron}]"
