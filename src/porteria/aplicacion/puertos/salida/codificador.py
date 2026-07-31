"""Puerto `CodificadorDeImagen`: de cuadro decodificado a bytes persistibles.

**La codificación es infraestructura y el `numpy.ndarray` nunca cruza al dominio.** El
dominio razona sobre huellas, instantes y desvíos, no sobre píxeles; el contrato
`dominio_limpio` de import-linter prohíbe `numpy` ahí adentro y la compuerta lo verifica.
Este puerto es la frontera: recibe un `FrameSellado` —cuyo campo `datos` está declarado
`Any` justamente para que el tipo del arreglo no aparezca en esta capa— y devuelve `bytes`,
que es lo único que el almacén necesita.

**La calidad es un parámetro por cámara, no una constante del producto** (D-01). La cámara
del portón puede ir en JPEG 85 y la de patentes sin pérdida, porque en esa el detalle es el
producto. El plan 01-07 inyecta el valor desde la clave `calidad_jpeg_por_camara` de la
capa 2 de configuración; acá viaja como argumento para que el codificador no tenga que
conocer la configuración ni la identidad de la cámara.

**Lo que se codifica es el frame limpio** (D-02): tal como salió del decodificador, sin
fecha, sin patente y sin cajas de detección dibujadas encima. Todo eso se dibuja al
visualizar o al exportar, leído de los metadatos. Dos razones, y las dos son de auditoría:
la huella cubre entonces un contenido que el propio sistema nunca alteró, y un cambio
futuro en cómo se dibuja el sobreimpreso no deja inconsistente el histórico ya guardado.

**Por qué `describir` está en el puerto y no se deduce después.** D-05 manda persistir la
resolución y el códec de origen junto con la evidencia. Leerlos del archivo ya codificado
sería leer las propiedades de la copia, no las del original: la resolución sobreviviría
pero el códec de origen se habría perdido para siempre en el momento de codificar.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from porteria.aplicacion.puertos.salida.fuente_de_video import FrameSellado

__all__ = ["CodificadorDeImagen", "DescripcionDeImagen"]


@dataclass(frozen=True, slots=True)
class DescripcionDeImagen:
    """Procedencia de la imagen, tal como D-05 pide persistirla.

    Es un valor con igualdad por contenido: dos descripciones con la misma resolución y el
    mismo códec describen lo mismo, y no hay identidad que preservar.
    """

    #: Píxeles de ancho del frame **original**, antes de codificar.
    ancho: int

    #: Píxeles de alto del frame original.
    alto: int

    #: Con qué llegó el cuadro hasta acá: `FFMPEG/h264`, `MSMF`, un archivo. Es un dato de
    #: la fuente y no del cuadro, así que lo aporta el codificador ya configurado.
    codec_de_origen: str


@runtime_checkable
class CodificadorDeImagen(Protocol):
    """Convierte un cuadro en bytes, y describe de dónde venía."""

    def codificar(self, frame: FrameSellado, calidad: int | None) -> bytes:
        """Devuelve los bytes del cuadro **limpio**, sin nada dibujado encima (D-02).

        Args:
            frame: El cuadro tal como lo entregó la fuente.
            calidad: De 1 a 100 para el formato con pérdida. `None` codifica **sin
                pérdida**, que es lo que la cámara de patentes necesita.
        """
        ...

    def miniatura(self, frame: FrameSellado) -> bytes:
        """Devuelve la miniatura que D-04 manda generar **en la ingesta**.

        Se genera ahora y no cuando alguien abra la grilla: para blobs de este tamaño
        SQLite es más rápido que el sistema de archivos, y la consulta de la Fase 9 se
        pinta con una sola query en vez de miles de aperturas de archivo.
        """
        ...

    def describir(self, frame: FrameSellado) -> DescripcionDeImagen:
        """Resolución y códec de origen del cuadro, para persistir junto a la evidencia."""
        ...
