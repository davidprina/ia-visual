"""Fuente de video sobre un archivo, con los dos modos de reproducción de D-16.

**Por qué existe una fuente de archivo en un producto que lee cámaras.** Es el banco de
pruebas del contrato de frescura: un archivo reproducido en tiempo real es una cámara
reproducible, y sin ella el Criterio de Éxito 5 no tendría instrumento. Además es lo que
permite diagnosticar la cañería —`porteria probar-fuente`— sin depender de que haya una
cámara conectada.

**Los dos modos sirven a dos públicos que no se pueden mezclar:**

* `TIEMPO_REAL` respeta `CAP_PROP_POS_MSEC`, la marca temporal del contenedor. Es el único
  modo con el que la prueba de frescura mide algo: si la cinta corre acelerada, la
  acumulación de latencia que hay que detectar no llega a producirse.
* `VELOCIDAD_MAXIMA` no espera. Es el modo de la integración continua, que no puede pagar
  el tiempo de reproducción de cada video.

**Por qué `opencv-python-headless` y no `opencv-python`.** La rueda no headless embebe su
propio Qt5, que choca con el Qt6 de PySide6 en la Fase 2 y produce crashes de inicio muy
difíciles de diagnosticar. La invariante que lo prohíbe en `pyproject.toml` la declaró el
plan 01-01.

**Por qué OpenCV acá y PyAV en la Fase 2.** `cv2.VideoCapture` alcanza y sobra para
archivos y webcams USB. Para RTSP no: ignora `CAP_PROP_BUFFERSIZE`, sus timeouts sólo se
configuran por una variable de entorno global del proceso, y ante un fallo devuelve `False`
sin causa —no se puede distinguir "cuadro perdido" de "cámara caída", que es exactamente
lo que la lógica de reconexión necesita saber—. Ese adaptador se escribe con PyAV y usa
este mismo punto de encuentro sin cambiarle una línea.

**Un hilo por fuente, aislado.** Una excepción en una fuente no puede tumbar a otra ni al
proceso. Acá no hay reconexión con backoff: el fin de archivo es un estado normal, no una
caída. El backoff exponencial con jitter llega en la Fase 2, cuando haya una red del otro
lado.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from typing import Final

import cv2

from porteria.aplicacion.puertos.salida.fuente_de_video import (
    FrameSellado,
    PerfilDeFlujo,
)
from porteria.infraestructura.video.metricas import (
    REGISTRO_DEL_PROCESO,
    MetricasDeFuente,
)
from porteria.infraestructura.video.slot_ultimo_valor import (
    PuntoDeEncuentro,
    SlotUltimoValor,
)

__all__ = ["FuenteDeArchivo", "FuenteNoDisponible", "Modo"]

NS_POR_MS: Final = 1_000_000
NS_POR_S: Final = 1_000_000_000

#: Cuántos bytes se leen para comprobar que el archivo es legible antes de abrirlo con
#: OpenCV. Comprobarlo con Python da un `OSError` con causa; `cv2.VideoCapture` sólo
#: devolvería `False`, que no distingue "no tengo permiso" de "el códec no está".
BYTES_DE_SONDA: Final = 1


class Modo(Enum):
    """Cómo se reproduce el archivo (D-16)."""

    #: Respeta la marca temporal de cada cuadro. Reproducir 5 s tarda 5 s.
    TIEMPO_REAL = "tiempo-real"

    #: No espera. Determinista y barato, para la integración continua.
    VELOCIDAD_MAXIMA = "velocidad-maxima"


class FuenteNoDisponible(RuntimeError):
    """La fuente no se pudo abrir, y el mensaje dice qué revisar (UI-05).

    Es un error de la aplicación y no un defecto: un archivo que no está, una ruta sin
    permiso o un contenedor que OpenCV no puede decodificar son casos esperables. La
    consola lo convierte en un código de salida y un mensaje, nunca en un traceback.
    """


class FuenteDeArchivo:
    """Reproduce un archivo de video publicando en un punto de encuentro de capacidad 1.

    Args:
        ruta: Archivo a reproducir. Se resuelve a absoluta en la construcción (T-01-02).
        modo: `TIEMPO_REAL` o `VELOCIDAD_MAXIMA` (D-16).
        repetir: Si al terminar el archivo vuelve a empezar. `False` por defecto: fin de
            archivo es un estado normal y la fuente pasa a no viva. En `True` convierte un
            recorte corto en una fuente indefinida, que es lo que permite medir frescura
            durante 60 s —y durante 600 s en la tanda programada— sin versionar un video
            de diez minutos, que D-59 no quiere en el repositorio.
        nombre: Con qué nombre aparece en el volcado de métricas. Por defecto, el del
            archivo sin extensión.
        destino: Punto de encuentro donde publica el hilo decodificador. Por defecto un
            `SlotUltimoValor`, que es el contrato. Se puede inyectar **sólo** para que la
            prueba de la prueba de CAP-04 monte el antipatrón a propósito y demuestre que
            la evaluación de frescura lo detecta.
    """

    def __init__(
        self,
        ruta: Path | str,
        modo: Modo = Modo.TIEMPO_REAL,
        repetir: bool = False,
        nombre: str | None = None,
        destino: PuntoDeEncuentro | None = None,
    ) -> None:
        # T-01-02: la ruta viene de la línea de comandos, así que se resuelve una vez y
        # todo lo demás trabaja sobre la resuelta.
        self.ruta = Path(ruta).resolve()
        self.modo = modo
        self.repetir = repetir
        self.nombre = nombre or self.ruta.stem

        self._metricas = MetricasDeFuente(destino if destino is not None else SlotUltimoValor())
        self._captura: cv2.VideoCapture | None = None
        self._fin = threading.Event()
        self._hilo: threading.Thread | None = None
        self._viva = False

        self.backend: str = ""
        self.resolucion: tuple[int, int] = (0, 0)
        self.fps_declarados: float = 0.0
        self.codec: str = ""

    # ------------------------------------------------------------- apertura #

    def _validar_la_ruta(self) -> None:
        """Comprueba existencia y legibilidad **antes** de dárselo a OpenCV (T-01-02).

        Se valida con Python y no con `cv2.VideoCapture` porque `VideoCapture` devuelve
        `False` sin causa: no distingue "el archivo no está" de "no tengo permiso" de "el
        códec no está disponible", y son tres cosas distintas para quien tiene que
        arreglarlo.
        """
        if not self.ruta.exists():
            raise FuenteNoDisponible(
                f"No se encontró el archivo de video en «{self.ruta}». Revisá la ruta y "
                "que el archivo no esté en uso por otro programa."
            )
        if not self.ruta.is_file():
            raise FuenteNoDisponible(
                f"«{self.ruta}» existe pero no es un archivo. Revisá que la ruta apunte "
                "al video y no a la carpeta que lo contiene."
            )
        try:
            with self.ruta.open("rb") as descriptor:
                descriptor.read(BYTES_DE_SONDA)
        except OSError as error:
            raise FuenteNoDisponible(
                f"No se pudo leer «{self.ruta.name}»: {error}. Revisá los permisos del "
                "archivo y que ningún otro programa lo tenga abierto en exclusiva."
            ) from error

    def _abrir_captura(self) -> cv2.VideoCapture:
        """Abre el contenedor con OpenCV y falla con un mensaje que dice qué revisar."""
        captura = cv2.VideoCapture(str(self.ruta))
        if not captura.isOpened():
            captura.release()
            raise FuenteNoDisponible(
                f"OpenCV no pudo abrir «{self.ruta.name}» como video. Revisá que el "
                "archivo esté completo —una descarga cortada o una copia a medias dan "
                "este mismo error— y que el formato sea uno que el reproductor del "
                "equipo también abra."
            )
        return captura

    def _leer_los_datos_del_contenedor(self, captura: cv2.VideoCapture) -> None:
        """Anota backend, resolución, códec y fps declarados.

        El **backend efectivo** se reporta a propósito: si mañana la rueda de OpenCV viene
        sin FFMPEG, el síntoma sería un archivo que no abre en la planta y nadie sabría
        por qué. Que el dato esté en la salida de `porteria probar-fuente` lo convierte en
        la primera pregunta del soporte remoto en vez de en un misterio.

        Los fps declarados son los que **dice el contenedor**, no los que la fuente
        entrega. Los efectivos se miden aparte y comparar los dos es un diagnóstico en sí
        mismo.
        """
        self.backend = captura.getBackendName()
        self.resolucion = (
            int(captura.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(captura.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )
        self.fps_declarados = float(captura.get(cv2.CAP_PROP_FPS))
        codigo = int(captura.get(cv2.CAP_PROP_FOURCC))
        self.codec = (
            "".join(chr((codigo >> desplazamiento) & 0xFF) for desplazamiento in (0, 8, 16, 24))
            .strip()
            .strip("\x00")
        )

    # ----------------------------------------------------------- decodificación #

    def _producir(self) -> None:
        """Decodifica y publica hasta el fin del archivo o hasta que se cierre la fuente.

        **Dónde se sella el cuadro y por qué ahí.** El sello es el `perf_counter_ns()`
        inmediatamente anterior a publicar, es decir después de la espera de cadencia. En
        `VELOCIDAD_MAXIMA` no hay espera y el sello queda justo tras el decode. En
        `TIEMPO_REAL` la espera **es** la simulación del momento en que una cámara habría
        entregado ese cuadro: sellarlo antes de esperar le atribuiría una antigüedad que no
        tuvo —un sesgo constante de un período completo, 40 ms a 25 fps— y las medianas
        que se reportan como evidencia estarían infladas por construcción.

        El sello **no** es el PTS del contenedor: el PTS mide tiempo de reproducción y no
        tiempo real transcurrido, así que con un consumidor lento seguiría avanzando
        prolijo mientras la antigüedad real crece sin techo. Un instrumento que no puede
        detectar el único fallo que importa.
        """
        captura = self._captura
        if captura is None:  # pragma: no cover - `abrir` siempre la deja puesta
            return

        secuencia = 0
        try:
            arranque_ns = time.perf_counter_ns()
            while not self._fin.is_set():
                leido, cuadro = captura.read()

                if not leido:
                    if not self.repetir:
                        break
                    captura = self._rebobinar(captura)
                    arranque_ns = time.perf_counter_ns()
                    continue

                pts_ms = captura.get(cv2.CAP_PROP_POS_MSEC)
                if self.modo is Modo.TIEMPO_REAL:
                    objetivo_ns = arranque_ns + int(pts_ms * NS_POR_MS)
                    espera_s = (objetivo_ns - time.perf_counter_ns()) / NS_POR_S
                    if espera_s > 0:
                        self._fin.wait(espera_s)

                self._metricas.publicar(
                    FrameSellado(
                        datos=cuadro,
                        instante_captura_ns=time.perf_counter_ns(),
                        secuencia=secuencia,
                    )
                )
                secuencia += 1
        finally:
            self._viva = False
            captura.release()
            self._captura = None

    def _rebobinar(self, captura: cv2.VideoCapture) -> cv2.VideoCapture:
        """Vuelve al principio reabriendo el contenedor.

        Se reabre en vez de usar `CAP_PROP_POS_FRAMES = 0` porque el posicionamiento por
        búsqueda depende del contenedor y del backend, y en varios casos deja
        `CAP_PROP_POS_MSEC` sin reiniciar — con lo que la cadencia del modo tiempo real
        quedaría corrida y la medición de frescura, arruinada, sin ninguna señal de que
        pasó. Reabrir cuesta unos milisegundos cada vuelta completa del archivo.
        """
        captura.release()
        return self._abrir_captura()

    # ---------------------------------------------------------------- puerto #

    def abrir(self) -> None:
        """Valida la ruta, abre el contenedor y arranca el hilo. Idempotente.

        Raises:
            FuenteNoDisponible: si el archivo no está, no se puede leer o no es un video.
        """
        if self._hilo is not None:
            return

        self._validar_la_ruta()
        captura = self._abrir_captura()
        self._leer_los_datos_del_contenedor(captura)

        self._captura = captura
        self._fin.clear()
        self._viva = True
        self._hilo = threading.Thread(
            target=self._producir, name=f"fuente-archivo-{self.nombre}", daemon=True
        )
        self._hilo.start()
        REGISTRO_DEL_PROCESO.registrar(self.nombre, self._metricas)

    def cerrar(self) -> None:
        """Detiene el hilo y libera el contenedor. Idempotente."""
        self._fin.set()
        self._viva = False
        if self._hilo is not None:
            self._hilo.join(timeout=5.0)
            self._hilo = None
        if self._captura is not None:
            self._captura.release()
            self._captura = None
        REGISTRO_DEL_PROCESO.olvidar(self.nombre)

    def tomar_mas_reciente(
        self, perfil: PerfilDeFlujo, timeout: float | None = None
    ) -> FrameSellado | None:
        """Devuelve el cuadro más reciente, o `None` si no hay ninguno.

        En esta fase el **perfil** no cambia el flujo: monitoreo y evidencia reciben el
        mismo cuadro, porque el archivo es uno solo. El parámetro se recibe desde el día
        uno para que en la Fase 2 el visor consuma el sub-stream liviano y la captura tome
        del main-stream sin tocar a ningún llamador (D-15).
        """
        del perfil  # D-15: mismo flujo para los dos perfiles en la Fase 1.
        return self._metricas.tomar(timeout)

    def metricas(self) -> Mapping[str, object]:
        """El volcado en memoria de esta fuente (D-17)."""
        return self._metricas.como_diccionario()

    def esta_viva(self) -> bool:
        """`False` antes de abrir, después de cerrar y al llegar al fin del archivo."""
        return self._viva

    # ------------------------------------------------------------ diagnóstico #

    def descripcion(self) -> dict[str, object]:
        """Lo que la consola muestra sobre el contenedor, sin las métricas.

        `archivo` es el **nombre** y no la ruta: un volcado estructurado que se pega en un
        correo de soporte no tiene por qué revelar el árbol de directorios del cliente
        (T-01-02). La ruta completa se muestra en la salida legible, que la lee quien está
        sentado frente al equipo.
        """
        ancho, alto = self.resolucion
        return {
            "archivo": self.ruta.name,
            "backend": self.backend,
            "resolucion": f"{ancho}x{alto}",
            "codec": self.codec,
            "fps_declarados": round(self.fps_declarados, 3),
            "modo": self.modo.value,
        }
