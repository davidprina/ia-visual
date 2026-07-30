"""`HuellaDeIntegridad`: la afirmación del sistema sobre el contenido de un archivo.

**Acá no se calcula ningún hash.** Hashear un archivo es leer bytes del disco por
streaming, y eso vive en `infraestructura/persistencia` (plan 01-04). El dominio recibe la
huella **ya calculada** y razona sobre ella: si la persistida y la recalculada no
coinciden, la evidencia está comprometida (`estados.evaluar`). Es la tentación que
RESEARCH le marca al planner —"el hash es una regla de integridad, va en el dominio"— y no
lo es: meter el cálculo acá arrastraría el sistema de archivos dentro del dominio y
rompería NUC-01.

**Por qué es un valor y no un `str`.** Estos 64 caracteres son a la vez la clave única de
la fila de evidencia y el **nombre del archivo en el disco** (D-03:
`evidencia/AAAA/MM/DD/<sha256>.jpg`). Un texto arbitrario en ese lugar es a la vez una
clave inválida y una ruta inválida, así que el formato se valida al construir el valor y
no en cada borde de entrada —que son varios: la CLI, la futura interfaz, una importación
de otra instalación.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

__all__ = ["HuellaDeIntegridad"]

#: SHA-256 en hexadecimal: exactamente 64 caracteres, dígitos y `a`-`f` en minúscula.
PATRON_HUELLA: Final = re.compile(r"^[0-9a-f]{64}$")

#: Largo del digest de SHA-256 en hexadecimal.
LARGO_DE_LA_HUELLA: Final = 64


@dataclass(frozen=True, slots=True)
class HuellaDeIntegridad:
    """El digest SHA-256 de un archivo de evidencia, en hexadecimal y en minúscula.

    **La mayúscula se rechaza; no se normaliza.** `hexdigest()` devuelve siempre
    minúsculas, así que una huella en mayúsculas no puede venir del camino normal: viene
    de una edición a mano, de una importación mal hecha o de un cálculo ajeno. Normalizar
    en silencio convertiría esa señal en nada. Y peor: admitiría dos textos distintos para
    la misma evidencia justo en el campo que es clave única en el esquema y nombre de
    archivo en el disco, con lo que la verificación masiva por hash podría fallar en
    encontrar lo que sí está.
    """

    valor: str

    def __post_init__(self) -> None:
        if not PATRON_HUELLA.match(self.valor):
            raise ValueError(
                f"«{self.valor}» no es una huella de integridad válida. Una huella "
                f"SHA-256 son {LARGO_DE_LA_HUELLA} caracteres hexadecimales en "
                "minúscula (0-9 y a-f), sin espacios ni prefijos. La recibida tiene "
                f"{len(self.valor)} caracteres.\n"
                "Qué revisar: que el valor venga de `hexdigest()` y no de un digest en "
                "base64, en mayúsculas o truncado."
            )

    def coincide_con(self, otra: HuellaDeIntegridad) -> bool:
        """Dice si dos huellas afirman el mismo contenido.

        Existe como método con nombre propio —y no como un `==` suelto en el código que
        llama— porque el punto de comparación es la decisión de integridad de D-09, y
        conviene que se lea como tal en el lugar donde se toma.
        """
        return self.valor == otra.valor

    def __str__(self) -> str:
        return self.valor
