"""La fuente de archivo con sus dos modos, y las dos órdenes de consola que la exponen.

**Por qué la fuente de archivo importa aunque las cámaras lleguen en la Fase 2.** Es el
banco de pruebas del contrato de frescura: un archivo reproducido en tiempo real es una
cámara reproducible, y sin ella el Criterio de Éxito 5 no tendría instrumento. Los dos
modos de D-16 sirven a dos públicos distintos: **tiempo real** verifica frescura y
latencia con consumidor lento; **velocidad máxima** hace deterministas las pruebas de
integración continua, que no pueden pagar el tiempo de reproducción de cada video.

**Lo que estas pruebas le exigen al producto y no sólo al código:** que abra rutas con
espacios y acentos (DIS-06), que reporte el backend efectivo —si mañana la rueda de
OpenCV viene sin FFMPEG, hay que enterarse acá y no en la planta—, y que un archivo que
no existe produzca un mensaje que diga qué revisar y no un traceback (UI-05).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import cv2
import numpy as np
import pytest
from typer.testing import CliRunner

from porteria.aplicacion.puertos.salida.fuente_de_video import (
    FuenteDeVideo,
    PerfilDeFlujo,
)
from porteria.cli.app import app
from porteria.infraestructura.video.archivo import (
    FuenteDeArchivo,
    FuenteNoDisponible,
    Modo,
)
from tests.conftest import (
    SUBDIR_VIDEO,
    VIDEO_ALTO,
    VIDEO_ANCHO,
    VIDEO_FPS,
    RutaHostil,
    _codec_mp4v,
)

#: Duración del video corto que usan las pruebas de tiempo. Cinco segundos son suficientes
#: para separar los dos modos con holgura y no castigan la compuerta rápida.
SEGUNDOS_DEL_VIDEO = 5

#: Tolerancia del modo tiempo real: ±15 % sobre los 5 s del video.
PISO_TIEMPO_REAL_S = 4.25
TECHO_TIEMPO_REAL_S = 5.75


@pytest.fixture(scope="module")
def video_de_cinco_segundos(ruta_hostil: RutaHostil) -> Path:
    """Un video de 5 s bajo la ruta con espacios y acentos.

    Se genera y no se versiona (D-59). Es más corto que el `video_sintetico` de sesión
    porque acá lo que se mide es el **tiempo de reproducción**, y cada segundo de video se
    paga en la compuerta.
    """
    destino = ruta_hostil.raiz / SUBDIR_VIDEO / "cinco segundos ñandú.mp4"
    if destino.exists():
        return destino

    escritor = cv2.VideoWriter(
        str(destino), _codec_mp4v(), VIDEO_FPS, (VIDEO_ANCHO, VIDEO_ALTO)
    )
    if not escritor.isOpened():
        raise pytest.UsageError(
            f"OpenCV no pudo abrir el escritor de video en «{destino}». Qué revisar: que "
            "el paquete instalado sea opencv-python-headless y que la ruta sea escribible."
        )
    try:
        for numero in range(VIDEO_FPS * SEGUNDOS_DEL_VIDEO):
            cuadro = np.zeros((VIDEO_ALTO, VIDEO_ANCHO, 3), dtype=np.uint8)
            izquierda = (numero * 4) % VIDEO_ANCHO
            cv2.rectangle(
                cuadro,
                (izquierda, 0),
                (min(izquierda + 40, VIDEO_ANCHO), VIDEO_ALTO),
                (0, 200, 255),
                -1,
            )
            escritor.write(cuadro)
    finally:
        escritor.release()

    return destino


def _reproducir_entera(fuente: FuenteDeArchivo, techo_s: float = 30.0) -> float:
    """Abre la fuente, espera a que termine el archivo y devuelve lo que tardó."""
    antes = time.perf_counter_ns()
    fuente.abrir()
    try:
        limite_ns = antes + int(techo_s * 1_000_000_000)
        while fuente.esta_viva() and time.perf_counter_ns() < limite_ns:
            time.sleep(0.02)
    finally:
        fuente.cerrar()
    return (time.perf_counter_ns() - antes) / 1_000_000_000


# --------------------------------------------------------------------------- #
# Los dos modos de reproducción (D-16)
# --------------------------------------------------------------------------- #


def test_el_modo_tiempo_real_respeta_la_marca_temporal_del_contenedor(
    video_de_cinco_segundos: Path,
) -> None:
    """Reproducir 5 s de video tarda 5 s: es lo que hace medible la frescura."""
    fuente = FuenteDeArchivo(video_de_cinco_segundos, modo=Modo.TIEMPO_REAL)

    tardanza_s = _reproducir_entera(fuente)

    assert PISO_TIEMPO_REAL_S <= tardanza_s <= TECHO_TIEMPO_REAL_S, (
        f"Reproducir {SEGUNDOS_DEL_VIDEO} s de video en modo tiempo real tardó "
        f"{tardanza_s:.2f} s, y tiene que estar entre {PISO_TIEMPO_REAL_S} y "
        f"{TECHO_TIEMPO_REAL_S} s. Si tarda de menos, el modo no está respetando "
        "`CAP_PROP_POS_MSEC` y la prueba de frescura estaría midiendo una cinta acelerada."
    )


def test_el_modo_velocidad_maxima_no_espera(video_de_cinco_segundos: Path) -> None:
    """Sin espera, la integración continua no paga el tiempo de reproducción."""
    lento = _reproducir_entera(
        FuenteDeArchivo(video_de_cinco_segundos, modo=Modo.TIEMPO_REAL)
    )
    rapido = _reproducir_entera(
        FuenteDeArchivo(video_de_cinco_segundos, modo=Modo.VELOCIDAD_MAXIMA)
    )

    assert rapido < lento / 2, (
        f"El modo velocidad máxima tardó {rapido:.2f} s contra {lento:.2f} s del modo "
        "tiempo real, y tendría que tardar menos de la mitad. Si tarda lo mismo, está "
        "esperando igual y los dos modos son uno solo."
    )


# --------------------------------------------------------------------------- #
# Apertura, backend y fin de archivo
# --------------------------------------------------------------------------- #


def test_la_fuente_abre_una_ruta_con_espacios_y_acentos_y_reporta_el_backend(
    video_de_cinco_segundos: Path,
) -> None:
    """DIS-06 más trazabilidad: qué decodificó el archivo tiene que ser un dato visible."""
    assert " " in video_de_cinco_segundos.name
    fuente = FuenteDeArchivo(video_de_cinco_segundos, modo=Modo.VELOCIDAD_MAXIMA)
    fuente.abrir()
    try:
        assert isinstance(fuente, FuenteDeVideo)
        assert fuente.backend, (
            "La fuente no reportó el backend efectivo de OpenCV. Si mañana la rueda viene "
            "sin FFMPEG hay que enterarse acá y no en la planta."
        )
        assert fuente.resolucion == (VIDEO_ANCHO, VIDEO_ALTO)
        assert fuente.fps_declarados == pytest.approx(VIDEO_FPS, abs=1.0)
        assert fuente.codec
    finally:
        fuente.cerrar()


def test_al_terminar_el_archivo_la_fuente_no_esta_viva_y_no_lanza(
    video_de_cinco_segundos: Path,
) -> None:
    """T-01-08: fin de archivo es un estado normal, no una excepción que tumbe nada."""
    fuente = FuenteDeArchivo(video_de_cinco_segundos, modo=Modo.VELOCIDAD_MAXIMA)
    _reproducir_entera(fuente)

    assert fuente.esta_viva() is False
    assert fuente.tomar_mas_reciente(PerfilDeFlujo.EVIDENCIA, timeout=0.05) is None


def test_los_dos_perfiles_devuelven_el_mismo_flujo(video_de_cinco_segundos: Path) -> None:
    """D-15: declarados desde el día uno, aunque en la Fase 1 sean el mismo flujo."""
    fuente = FuenteDeArchivo(video_de_cinco_segundos, modo=Modo.TIEMPO_REAL)
    fuente.abrir()
    try:
        monitoreo = fuente.tomar_mas_reciente(PerfilDeFlujo.MONITOREO, timeout=2.0)
        evidencia = fuente.tomar_mas_reciente(PerfilDeFlujo.EVIDENCIA, timeout=2.0)
    finally:
        fuente.cerrar()

    assert monitoreo is not None
    assert evidencia is not None
    assert "perfil" in (FuenteDeArchivo.tomar_mas_reciente.__doc__ or "").lower()


def test_la_fuente_repite_el_archivo_cuando_se_le_pide(
    video_de_cinco_segundos: Path,
) -> None:
    """Repetir convierte un recorte corto en una fuente indefinida.

    Es lo que permite medir frescura durante 60 s —y durante 600 s en la tanda
    programada— sin versionar un video de diez minutos, que D-59 no quiere en el
    repositorio.
    """
    fuente = FuenteDeArchivo(
        video_de_cinco_segundos, modo=Modo.VELOCIDAD_MAXIMA, repetir=True
    )
    fuente.abrir()
    try:
        time.sleep(2.0)
        publicados = fuente.metricas()["frames_publicados"]
        assert fuente.esta_viva() is True, (
            "La fuente terminó pese a que se le pidió repetir. Sin repetición, la prueba "
            "de frescura de 60 s se quedaría sin video a los 5 s."
        )
    finally:
        fuente.cerrar()

    assert isinstance(publicados, int)
    assert publicados > VIDEO_FPS * SEGUNDOS_DEL_VIDEO, (
        f"Se publicaron {publicados} cuadros y el archivo tiene "
        f"{VIDEO_FPS * SEGUNDOS_DEL_VIDEO}: no llegó a dar la vuelta."
    )


def test_la_fuente_descarta_cuadros_con_un_consumidor_lento(
    video_de_cinco_segundos: Path,
) -> None:
    """Pitfall 7: si nada se descarta con consumidor lento, todo se está acumulando."""
    fuente = FuenteDeArchivo(video_de_cinco_segundos, modo=Modo.TIEMPO_REAL)
    fuente.abrir()
    try:
        for _ in range(10):  # 10 entregas a 5 Hz = 2 s
            fuente.tomar_mas_reciente(PerfilDeFlujo.MONITOREO, timeout=1.0)
            time.sleep(0.2)
        descartados = fuente.metricas()["frames_descartados"]
    finally:
        fuente.cerrar()

    assert isinstance(descartados, int)
    assert descartados > 0, (
        "Con una fuente a 25 fps y un consumidor a 5 Hz no se descartó ningún cuadro. "
        "Eso no significa que todo esté bien: significa que los cuadros se están "
        "acumulando en algún lado y la antigüedad crece sin que nadie la vea."
    )


# --------------------------------------------------------------------------- #
# Errores que dicen qué revisar (UI-05, T-01-02, T-01-08)
# --------------------------------------------------------------------------- #


def test_abrir_un_archivo_inexistente_dice_que_revisar(ruta_hostil: RutaHostil) -> None:
    """UI-05: el mensaje lo va a leer alguien en una planta sin área de sistemas."""
    inexistente = ruta_hostil.raiz / SUBDIR_VIDEO / "no existe.mp4"

    with pytest.raises(FuenteNoDisponible) as capturado:
        FuenteDeArchivo(inexistente).abrir()

    mensaje = str(capturado.value)
    assert "no existe.mp4" in mensaje, (
        f"El mensaje no nombra el archivo que falta: {mensaje}"
    )
    assert "revis" in mensaje.lower(), (
        f"El mensaje no dice qué revisar, sólo qué falló: {mensaje}"
    )


def test_un_archivo_que_no_es_video_no_tumba_el_proceso(ruta_hostil: RutaHostil) -> None:
    """T-01-08: un archivo truncado o mentiroso es entrada no confiable, no un fallo."""
    falso = ruta_hostil.raiz / SUBDIR_VIDEO / "truncado.mp4"
    falso.write_bytes(b"esto no es un video, son 42 bytes de basura")

    with pytest.raises(FuenteNoDisponible) as capturado:
        FuenteDeArchivo(falso).abrir()

    assert "revis" in str(capturado.value).lower()


# --------------------------------------------------------------------------- #
# Las dos órdenes de consola (D-49, D-50, D-51)
# --------------------------------------------------------------------------- #


def test_probar_fuente_imprime_el_diagnostico_en_espanol(
    video_de_cinco_segundos: Path,
) -> None:
    """El operador apunta la herramienta a un archivo y lee si la cañería está sana."""
    resultado = CliRunner().invoke(
        app,
        ["probar-fuente", "--archivo", str(video_de_cinco_segundos), "--segundos", "2"],
    )

    assert resultado.exit_code == 0, (
        f"La orden terminó con código {resultado.exit_code}.\nSalida:\n{resultado.output}"
    )
    for texto in ("frames descartados", "frames publicados", "backend"):
        assert texto in resultado.output.lower(), (
            f"La salida legible no incluye «{texto}».\nSalida:\n{resultado.output}"
        )


def test_probar_fuente_con_json_produce_una_salida_parseable(
    video_de_cinco_segundos: Path,
) -> None:
    """D-51: las pruebas no parsean texto libre, y por eso existe la bandera."""
    resultado = CliRunner().invoke(
        app,
        [
            "probar-fuente",
            "--archivo",
            str(video_de_cinco_segundos),
            "--segundos",
            "2",
            "--json",
        ],
    )

    assert resultado.exit_code == 0, f"Salida:\n{resultado.output}"
    datos = json.loads(resultado.output)
    for clave in ("frames_descartados", "frames_publicados", "fps_efectivos"):
        assert clave in datos, f"Falta la clave «{clave}» en {sorted(datos)}"


def test_probar_fuente_en_json_no_filtra_la_ruta_absoluta(
    video_de_cinco_segundos: Path,
) -> None:
    """T-01-02: la salida estructurada nombra el archivo, no el árbol del sistema."""
    resultado = CliRunner().invoke(
        app,
        [
            "probar-fuente",
            "--archivo",
            str(video_de_cinco_segundos),
            "--segundos",
            "1",
            "--json",
        ],
    )

    assert resultado.exit_code == 0
    assert str(video_de_cinco_segundos.parent) not in resultado.output, (
        "La salida estructurada incluye la ruta absoluta del equipo. Un volcado que se "
        "pega en un correo de soporte no tiene por qué revelar el árbol de directorios "
        "del cliente."
    )
    assert json.loads(resultado.output)["archivo"] == video_de_cinco_segundos.name


def test_probar_fuente_con_un_archivo_inexistente_no_muestra_un_traceback() -> None:
    """Un traceback en la consola de una planta es un fallo de producto (UI-05)."""
    resultado = CliRunner().invoke(app, ["probar-fuente", "--archivo", "no-existe.mp4"])

    assert resultado.exit_code != 0, (
        "Una fuente que no se puede abrir tiene que terminar en un código distinto de 0: "
        "es lo que un script de despliegue mira."
    )
    assert "Traceback" not in resultado.output, (
        f"La salida muestra un traceback:\n{resultado.output}"
    )
    assert "revis" in resultado.output.lower(), (
        f"La salida no dice qué revisar:\n{resultado.output}"
    )


def test_metricas_con_json_produce_json_parseable() -> None:
    """`porteria metricas` tiene que ser consumible por una herramienta (D-51)."""
    resultado = CliRunner().invoke(app, ["metricas", "--json"])

    assert resultado.exit_code == 0, f"Salida:\n{resultado.output}"
    datos = json.loads(resultado.output)
    assert "fuentes" in datos


def test_metricas_sin_fuentes_lo_dice_en_vez_de_mostrar_un_cero() -> None:
    """Las métricas viven en memoria (D-17): otra consola no ve las fuentes de ésta.

    Un volcado vacío que se leyera como "todo en cero, todo bien" sería peor que no tener
    la orden, así que el texto explica por qué está vacío y qué hacer.
    """
    resultado = CliRunner().invoke(app, ["metricas"])

    assert resultado.exit_code == 0
    assert "probar-fuente" in resultado.output, (
        "El volcado vacío no le dice al operador qué correr para tener algo que mirar.\n"
        f"Salida:\n{resultado.output}"
    )
