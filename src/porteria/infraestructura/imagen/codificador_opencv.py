"""Codificación de la imagen con OpenCV: calidad por cámara y miniatura de la ingesta.

**Por qué `opencv-python-headless` y no `opencv-python`.** La rueda no headless embebe su
propio Qt5, que choca con el Qt6 de PySide6 en la Fase 2 y produce crashes de inicio muy
difíciles de diagnosticar. La invariante que lo prohíbe en `pyproject.toml` la declaró el
plan 01-01.

**Acá vive el `numpy.ndarray` y de acá no sale.** Este módulo es la frontera entre los
píxeles y el resto del sistema: entra un `FrameSellado` y sale `bytes`. El contrato
`dominio_limpio` de import-linter prohíbe `numpy` en el dominio y la compuerta lo verifica
en cada corrida.

**Sobre el tamaño de la miniatura.** D-04 pide ~15 KB. Medido en esta máquina con
`opencv-python-headless` 5.0.0.93, a 320 px de lado mayor y calidad 90: **7,5 KiB** sobre
una imagen representativa y **21,3 KiB** sobre ruido puro, que es el contenido más caro que
puede llegar de una cámara. Se eligió 90 y no 95 justamente porque 95 lleva el ruido a 32,7
KiB, fuera de la banda. El piso de la banda, en cambio, **no es una propiedad que este
módulo pueda garantizar**: un cuadro uniforme —una pared de noche, un lente tapado— mide
1,55 KiB a cualquier calidad, porque no hay información que codificar.

**Nada se dibuja sobre el píxel** (D-02). Ni fecha, ni patente, ni cajas de detección: eso
se dibuja al visualizar o al exportar, leído de los metadatos. Así la huella cubre un
contenido que el sistema nunca alteró, y cambiar el sobreimpreso mañana no deja
inconsistente la evidencia de ayer. `cv2.imencode` y `cv2.resize` devuelven arreglos
nuevos, así que el cuadro que entra tampoco se toca.
"""

from __future__ import annotations

from typing import Any, Final

import cv2
import numpy as np

from porteria.aplicacion.puertos.salida.codificador import DescripcionDeImagen
from porteria.aplicacion.puertos.salida.fuente_de_video import FrameSellado

__all__ = [
    "CALIDAD_DE_LA_MINIATURA",
    "CALIDAD_MAXIMA",
    "CALIDAD_MINIMA",
    "LADO_MAYOR_DE_LA_MINIATURA",
    "CalidadInvalida",
    "CodificadorOpenCV",
    "FalloDeCodificacion",
]

#: Rango que acepta `IMWRITE_JPEG_QUALITY`. El 0 queda afuera a propósito: produce una
#: imagen irreconocible, y una evidencia irreconocible no es evidencia.
CALIDAD_MINIMA: Final = 1
CALIDAD_MAXIMA: Final = 100

#: Lado mayor de la miniatura, en píxeles. Con 320 la grilla de la Fase 9 se ve bien en
#: pantallas normales sin que el blob crezca.
LADO_MAYOR_DE_LA_MINIATURA: Final = 320

#: Calidad de la miniatura. Ver el encabezado: 90 mantiene dentro de la banda tanto la
#: imagen representativa como el peor caso de ruido.
CALIDAD_DE_LA_MINIATURA: Final = 90

#: Extensiones que `cv2.imencode` usa para elegir el formato de salida.
_FORMATO_CON_PERDIDA: Final = ".jpg"
_FORMATO_SIN_PERDIDA: Final = ".png"


class CalidadInvalida(ValueError):
    """La calidad pedida está fuera del rango que admite el codificador."""


class FalloDeCodificacion(RuntimeError):
    """OpenCV no pudo codificar el cuadro. Nunca debería pasar con un cuadro válido."""


class CodificadorOpenCV:
    """Implementación del puerto `CodificadorDeImagen` sobre `cv2.imencode`.

    El códec de origen se recibe **al construir** y no por cuadro: es una propiedad de la
    fuente —qué backend abrió el flujo—, no del cuadro. El plan 01-07 lo toma de las
    métricas de la fuente y arma un codificador por cámara, que es la misma granularidad
    que ya tiene la calidad (D-01).
    """

    __slots__ = ("_codec_de_origen",)

    def __init__(self, codec_de_origen: str = "desconocido") -> None:
        self._codec_de_origen = codec_de_origen

    def codificar(self, frame: FrameSellado, calidad: int | None) -> bytes:
        """Codifica el cuadro limpio. `calidad=None` produce PNG sin pérdida (D-01).

        Raises:
            CalidadInvalida: si la calidad está fuera de 1 a 100.
            FalloDeCodificacion: si OpenCV rechaza el cuadro.
        """
        imagen = self._imagen(frame)

        if calidad is None:
            return self._codificar_con(imagen, _FORMATO_SIN_PERDIDA, [])

        if not CALIDAD_MINIMA <= calidad <= CALIDAD_MAXIMA:
            raise CalidadInvalida(
                f"La calidad de imagen tiene que estar entre {CALIDAD_MINIMA} y "
                f"{CALIDAD_MAXIMA}, y se pidió {calidad}.\n"
                "Qué hacer: corregí el valor de `calidad_jpeg_por_camara` para esta "
                "cámara, o dejalo sin valor para guardar sin pérdida."
            )

        return self._codificar_con(
            imagen, _FORMATO_CON_PERDIDA, [cv2.IMWRITE_JPEG_QUALITY, int(calidad)]
        )

    def miniatura(self, frame: FrameSellado) -> bytes:
        """Miniatura de 320 px de lado mayor, manteniendo la proporción (D-04).

        `INTER_AREA` y no `INTER_LINEAR`: al achicar es el que promedia los píxeles de
        origen en vez de muestrearlos, y por lo tanto el único que no produce el aliasing
        que vuelve ilegible una patente en la vista de grilla.
        """
        imagen = self._imagen(frame)
        alto, ancho = imagen.shape[:2]
        lado_mayor = max(alto, ancho)

        if lado_mayor > LADO_MAYOR_DE_LA_MINIATURA:
            escala = LADO_MAYOR_DE_LA_MINIATURA / lado_mayor
            destino = (max(1, round(ancho * escala)), max(1, round(alto * escala)))
            imagen = cv2.resize(imagen, destino, interpolation=cv2.INTER_AREA)

        return self._codificar_con(
            imagen,
            _FORMATO_CON_PERDIDA,
            [cv2.IMWRITE_JPEG_QUALITY, CALIDAD_DE_LA_MINIATURA],
        )

    def describir(self, frame: FrameSellado) -> DescripcionDeImagen:
        """Resolución del cuadro y códec con el que llegó, para persistir (D-05)."""
        alto, ancho = self._imagen(frame).shape[:2]
        return DescripcionDeImagen(
            ancho=int(ancho), alto=int(alto), codec_de_origen=self._codec_de_origen
        )

    @staticmethod
    def _imagen(frame: FrameSellado) -> Any:
        """Saca el arreglo del cuadro comprobando que sea uno, y no `None`.

        Una fuente caída puede entregar un cuadro sin datos, y el mensaje de OpenCV en ese
        caso —un `cv2.error` con la firma de la función en C++— no le sirve a nadie en una
        planta sin área de sistemas.
        """
        imagen = frame.datos
        if not isinstance(imagen, np.ndarray) or imagen.size == 0:
            raise FalloDeCodificacion(
                "El cuadro llegó sin imagen, así que no hay nada que codificar. "
                "Qué revisar: que la fuente de video esté viva y que el cuadro venga de "
                "`tomar_mas_reciente`, que devuelve `None` cuando no hay nada fresco."
            )
        return imagen

    @staticmethod
    def _codificar_con(imagen: Any, formato: str, parametros: list[int]) -> bytes:
        salio_bien, buffer = cv2.imencode(formato, imagen, parametros)
        if not salio_bien:
            raise FalloDeCodificacion(
                f"OpenCV no pudo codificar el cuadro a «{formato}». Qué revisar: que la "
                "imagen tenga tres canales de 8 bits, que es lo que entrega el "
                "decodificador."
            )
        return bytes(buffer.tobytes())
