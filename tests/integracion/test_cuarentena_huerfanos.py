"""Codificación de la imagen y cuarentena de huérfanos: las dos mitades de la Tarea 3.

Van juntas porque son las dos puntas del mismo archivo: el codificador produce los bytes
que el almacén persiste, y la cuarentena decide qué pasa con los que quedaron sin fila.

**El criterio que ordena la cuarentena** es el mismo que ordena la escritura en D-12: *un
archivo huérfano es basura recuperable, una fila huérfana es evidencia rota*. Por eso el
barrido **mueve** y nunca elimina — el huérfano puede ser justamente la foto del camión del
corte de luz, y esa foto es la que alguien va a pedir.

**Sobre el tamaño de la miniatura.** D-04 pide ~15 KB. Medido en esta máquina con
`opencv-python-headless` 5.0.0.93, una miniatura de 320 px de lado mayor a calidad 90 mide
7,5 KiB sobre un frame representativo y 21,3 KiB sobre ruido puro —el peor caso—, o sea que
la banda de 5 a 30 KiB se cumple para imágenes con detalle. **No es una propiedad que el
codificador pueda garantizar para cualquier frame**: un frame plano (una pared de noche, un
lente tapado) mide 1,55 KiB a cualquier calidad, porque no hay información que codificar.
La prueba mide lo que sí es medible y `test_un_frame_plano_queda_por_debajo_de_la_banda`
deja el límite escrito en vez de escondido.
"""

from __future__ import annotations

import itertools
from pathlib import Path

import cv2
import numpy as np
import pytest

from porteria.aplicacion.puertos.salida.codificador import (
    CodificadorDeImagen,
    DescripcionDeImagen,
)
from porteria.aplicacion.puertos.salida.fuente_de_video import FrameSellado
from porteria.dominio.comun.tiempo import FechaLocal
from porteria.infraestructura.imagen.codificador_opencv import (
    LADO_MAYOR_DE_LA_MINIATURA,
    CalidadInvalida,
    CodificadorOpenCV,
)
from porteria.infraestructura.persistencia.cuarentena import (
    NOMBRE_DE_LA_CUARENTENA,
    barrer_en_segundo_plano,
    barrer_huerfanos,
)
from porteria.infraestructura.persistencia.evidencia_fs import AlmacenDeEvidenciaEnDisco
from tests.conftest import RutaHostil

FECHA = FechaLocal("2026-07-30")

#: Firmas de formato, leídas del propio archivo y no de la extensión.
FIRMA_PNG = b"\x89PNG\r\n\x1a\n"
FIRMA_JPEG = b"\xff\xd8\xff"

#: La banda de D-04, con la tolerancia que fija el plan.
MINIATURA_MINIMA = 5 * 1024
MINIATURA_MAXIMA = 30 * 1024

_contador = itertools.count()


# --------------------------------------------------------------------------- #
# Frames de prueba
# --------------------------------------------------------------------------- #


def imagen_representativa(alto: int = 1080, ancho: int = 1920, semilla: int = 0) -> np.ndarray:
    """Algo parecido a una foto de camión: degradé, formas, patente y ruido de sensor."""
    generador = np.random.default_rng(semilla)
    imagen = np.zeros((alto, ancho, 3), dtype=np.uint8)
    for fila in range(alto):
        imagen[fila, :, :] = int(40 + 180 * fila / alto)
    cv2.rectangle(imagen, (300, 300), (1500, 850), (60, 70, 90), -1)
    cv2.rectangle(imagen, (320, 330), (900, 600), (200, 200, 190), -1)
    cv2.circle(imagen, (520, 860), 90, (20, 20, 20), -1)
    cv2.circle(imagen, (1300, 860), 90, (20, 20, 20), -1)
    cv2.putText(imagen, "AB 123 CD", (700, 980), cv2.FONT_HERSHEY_SIMPLEX, 3, (250, 250, 250), 6)
    ruido = generador.integers(-18, 18, size=imagen.shape, dtype=np.int16)
    return np.clip(imagen.astype(np.int16) + ruido, 0, 255).astype(np.uint8)


def sellar(imagen: np.ndarray) -> FrameSellado:
    return FrameSellado(datos=imagen, instante_captura_ns=1_234_567_890, secuencia=7)


@pytest.fixture
def codificador() -> CodificadorOpenCV:
    return CodificadorOpenCV(codec_de_origen="FFMPEG/h264")


@pytest.fixture
def frame() -> FrameSellado:
    return sellar(imagen_representativa())


@pytest.fixture
def raiz(ruta_hostil: RutaHostil) -> Path:
    destino = ruta_hostil.raiz_evidencia / f"c{next(_contador)}"
    destino.mkdir(parents=True, exist_ok=True)
    return destino


# --------------------------------------------------------------------------- #
# D-01: calidad por cámara, y sin pérdida donde el detalle lo exige
# --------------------------------------------------------------------------- #


def test_el_codificador_cumple_el_puerto(codificador: CodificadorOpenCV) -> None:
    assert isinstance(codificador, CodificadorDeImagen)


def test_mas_calidad_produce_mas_bytes(
    codificador: CodificadorOpenCV, frame: FrameSellado
) -> None:
    """D-01: la calidad es un parámetro real por cámara, no un adorno de la configuración."""
    alta = codificador.codificar(frame, 100)
    baja = codificador.codificar(frame, 70)

    assert len(alta) > len(baja)
    assert alta.startswith(FIRMA_JPEG)
    assert baja.startswith(FIRMA_JPEG)


def test_sin_calidad_se_codifica_sin_perdida_en_png(
    codificador: CodificadorOpenCV, frame: FrameSellado
) -> None:
    """La cámara de patentes necesita el detalle intacto: `calidad=None` es PNG."""
    bytes_png = codificador.codificar(frame, None)

    assert bytes_png.startswith(FIRMA_PNG)
    decodificada = cv2.imdecode(np.frombuffer(bytes_png, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert np.array_equal(decodificada, frame.datos), (
        "El PNG no reprodujo el frame exactamente, así que no es sin pérdida."
    )


@pytest.mark.parametrize("calidad", [0, -1, 101, 1000])
def test_una_calidad_fuera_de_rango_se_rechaza_diciendo_el_rango(
    codificador: CodificadorOpenCV, frame: FrameSellado, calidad: int
) -> None:
    with pytest.raises(CalidadInvalida) as capturado:
        codificador.codificar(frame, calidad)

    assert "100" in str(capturado.value)


# --------------------------------------------------------------------------- #
# D-02: el frame limpio, sin nada quemado en el píxel
# --------------------------------------------------------------------------- #


def test_codificar_dos_veces_el_mismo_frame_da_los_mismos_bytes(
    codificador: CodificadorOpenCV, frame: FrameSellado
) -> None:
    """D-02: si se dibujara la fecha o la patente sobre el píxel, los bytes diferirían.

    Es la prueba más barata que existe de que el codificador no quema nada: cualquier
    marca con la hora, un contador o un identificador de captura haría que la segunda
    codificación difiriera de la primera.
    """
    assert codificador.codificar(frame, 85) == codificador.codificar(frame, 85)


def test_el_frame_no_se_modifica_al_codificarlo(
    codificador: CodificadorOpenCV, frame: FrameSellado
) -> None:
    """La otra mitad de D-02: tampoco se dibuja sobre el arreglo original."""
    copia = frame.datos.copy()

    codificador.codificar(frame, 85)
    codificador.miniatura(frame)

    assert np.array_equal(frame.datos, copia)


# --------------------------------------------------------------------------- #
# D-04: la miniatura de la ingesta
# --------------------------------------------------------------------------- #


def test_la_miniatura_tiene_320_px_de_lado_mayor_y_mantiene_la_proporcion(
    codificador: CodificadorOpenCV, frame: FrameSellado
) -> None:
    bytes_miniatura = codificador.miniatura(frame)

    imagen = cv2.imdecode(np.frombuffer(bytes_miniatura, dtype=np.uint8), cv2.IMREAD_COLOR)
    alto, ancho = imagen.shape[:2]

    assert max(alto, ancho) == LADO_MAYOR_DE_LA_MINIATURA
    proporcion_original = frame.datos.shape[1] / frame.datos.shape[0]
    assert abs(ancho / alto - proporcion_original) < 0.02


@pytest.mark.parametrize("semilla", [0, 1, 2])
def test_la_miniatura_de_una_imagen_con_detalle_entra_en_la_banda(
    codificador: CodificadorOpenCV, semilla: int
) -> None:
    """D-04: ~15 KB. Medido: 7,5 KiB con detalle, 21,3 KiB con ruido puro."""
    bytes_miniatura = codificador.miniatura(sellar(imagen_representativa(semilla=semilla)))

    assert MINIATURA_MINIMA <= len(bytes_miniatura) <= MINIATURA_MAXIMA, (
        f"La miniatura mide {len(bytes_miniatura) / 1024:.1f} KiB y la banda es de 5 a 30 "
        "KiB. Qué revisar: la calidad de la miniatura y el lado mayor."
    )


def test_la_miniatura_del_peor_caso_sigue_entrando_en_la_banda(
    codificador: CodificadorOpenCV,
) -> None:
    """Ruido puro: el contenido más caro de codificar que puede llegar de una cámara."""
    generador = np.random.default_rng(3)
    ruido = generador.integers(0, 256, size=(1080, 1920, 3), dtype=np.uint8)

    bytes_miniatura = codificador.miniatura(sellar(ruido))

    assert len(bytes_miniatura) <= MINIATURA_MAXIMA


def test_un_frame_plano_queda_por_debajo_de_la_banda(codificador: CodificadorOpenCV) -> None:
    """El límite honesto: el piso de 5 KiB no es una propiedad del codificador.

    Un frame uniforme —una pared de noche, un lente tapado, una cámara sin señal que
    devuelve negro— no tiene información que codificar y su miniatura mide ~1,5 KiB a
    cualquier calidad. Exigir 5 KiB para **cualquier** frame sería exigir que el
    codificador invente bytes. Se deja escrito acá en vez de esconderlo detrás de una
    prueba que sólo usa imágenes convenientes.
    """
    plano = np.full((1080, 1920, 3), 128, dtype=np.uint8)

    assert len(codificador.miniatura(sellar(plano))) < MINIATURA_MINIMA


# --------------------------------------------------------------------------- #
# D-05: lo que hay que persistir sobre la procedencia de la imagen
# --------------------------------------------------------------------------- #


def test_describir_devuelve_resolucion_y_codec_de_origen(
    codificador: CodificadorOpenCV, frame: FrameSellado
) -> None:
    descripcion = codificador.describir(frame)

    assert descripcion == DescripcionDeImagen(
        ancho=1920, alto=1080, codec_de_origen="FFMPEG/h264"
    )


# --------------------------------------------------------------------------- #
# D-13 y T-01-18: los huérfanos van a cuarentena, nunca a la papelera
# --------------------------------------------------------------------------- #


def test_los_huerfanos_se_mueven_y_el_conocido_se_queda(raiz: Path) -> None:
    """Tres archivos y una ruta conocida: dos se mueven, cero se eliminan."""
    almacen = AlmacenDeEvidenciaEnDisco(raiz)
    _, conocida = almacen.guardar(b"la foto que si tiene fila", FECHA)
    _, huerfana_a = almacen.guardar(b"huerfana a", FECHA)
    _, huerfana_b = almacen.guardar(b"huerfana b", FECHA)

    movidos = barrer_huerfanos(raiz, {conocida}, fecha_local=FECHA)

    assert len(movidos) == 2
    assert almacen.ruta_absoluta(conocida).is_file(), (
        "Se movió el archivo que sí tiene fila: eso deja una fila huérfana, que es "
        "exactamente lo que D-12 ordena que no pueda pasar."
    )
    for original, en_cuarentena, tamano in movidos:
        assert original in {huerfana_a, huerfana_b}
        assert not (raiz / original).exists()
        assert (raiz / en_cuarentena).is_file(), (
            "El huérfano no está en su nueva ubicación. El barrido mueve; si desapareció, "
            "se eliminó evidencia y puede haber sido la foto del camión del corte de luz."
        )
        assert tamano > 0


def test_el_huerfano_va_a_la_carpeta_de_la_fecha_conservando_el_nombre(raiz: Path) -> None:
    almacen = AlmacenDeEvidenciaEnDisco(raiz)
    _, huerfana = almacen.guardar(b"huerfana con nombre", FECHA)

    [(_, en_cuarentena, _)] = barrer_huerfanos(raiz, set(), fecha_local=FECHA)

    assert en_cuarentena.startswith(f"{NOMBRE_DE_LA_CUARENTENA}/2026-07-30/")
    assert en_cuarentena.endswith(Path(huerfana).name)


def test_el_contenido_del_huerfano_llega_intacto_a_la_cuarentena(raiz: Path) -> None:
    almacen = AlmacenDeEvidenciaEnDisco(raiz)
    contenido = b"la foto del camion del corte de luz"
    _, huerfana = almacen.guardar(contenido, FECHA)

    [(_, en_cuarentena, tamano)] = barrer_huerfanos(raiz, set(), fecha_local=FECHA)

    assert (raiz / en_cuarentena).read_bytes() == contenido
    assert tamano == len(contenido)


def test_un_temporal_colgado_tambien_va_a_cuarentena(raiz: Path) -> None:
    """Una escritura interrumpida deja un `.tmp_*.part`: tampoco se borra."""
    directorio = raiz / "2026" / "07" / "30"
    directorio.mkdir(parents=True)
    temporal = directorio / ".tmp_abc123.part"
    temporal.write_bytes(b"escritura a medias")

    movidos = barrer_huerfanos(raiz, set(), fecha_local=FECHA)

    assert len(movidos) == 1
    assert not temporal.exists()
    assert (raiz / movidos[0][1]).read_bytes() == b"escritura a medias"


def test_barrer_dos_veces_no_vuelve_a_mover_lo_que_ya_esta_en_cuarentena(raiz: Path) -> None:
    """La cuarentena no se barre a sí misma, o el huérfano se hundiría un nivel por día."""
    almacen = AlmacenDeEvidenciaEnDisco(raiz)
    almacen.guardar(b"huerfana unica", FECHA)

    primera = barrer_huerfanos(raiz, set(), fecha_local=FECHA)
    segunda = barrer_huerfanos(raiz, set(), fecha_local=FECHA)

    assert len(primera) == 1
    assert segunda == []
    assert (raiz / primera[0][1]).is_file()


def test_dos_huerfanos_con_el_mismo_nombre_no_se_pisan(raiz: Path) -> None:
    """Sin esto, el segundo movimiento eliminaría al primero por la puerta de atrás."""
    nombre = f"{'a' * 64}.jpg"
    for dia, contenido in (("30", b"del treinta"), ("31", b"del treinta y uno")):
        directorio = raiz / "2026" / "07" / dia
        directorio.mkdir(parents=True)
        (directorio / nombre).write_bytes(contenido)

    movidos = barrer_huerfanos(raiz, set(), fecha_local=FECHA)

    assert len(movidos) == 2
    destinos = {en_cuarentena for _, en_cuarentena, _ in movidos}
    assert len(destinos) == 2, "Los dos huérfanos fueron al mismo destino: uno se perdió."
    contenidos = {(raiz / destino).read_bytes() for destino in destinos}
    assert contenidos == {b"del treinta", b"del treinta y uno"}


def test_las_rutas_devueltas_son_relativas_y_con_barras(raiz: Path) -> None:
    """D-06: nada de rutas absolutas hacia afuera, tampoco desde la cuarentena."""
    almacen = AlmacenDeEvidenciaEnDisco(raiz)
    almacen.guardar(b"huerfana", FECHA)

    [(original, en_cuarentena, _)] = barrer_huerfanos(raiz, set(), fecha_local=FECHA)

    for ruta in (original, en_cuarentena):
        assert not Path(ruta).is_absolute()
        assert "\\" not in ruta


def test_una_raiz_sin_huerfanos_devuelve_la_lista_vacia(raiz: Path) -> None:
    """Contraprueba: si el barrido moviera cualquier cosa, esto lo delataría."""
    almacen = AlmacenDeEvidenciaEnDisco(raiz)
    _, conocida = almacen.guardar(b"la unica foto, y tiene fila", FECHA)

    assert barrer_huerfanos(raiz, {conocida}, fecha_local=FECHA) == []
    assert almacen.ruta_absoluta(conocida).is_file()


def test_el_barrido_en_segundo_plano_no_bloquea_y_termina(raiz: Path) -> None:
    """D-13: el barrido corre en segundo plano para no demorar el arranque."""
    almacen = AlmacenDeEvidenciaEnDisco(raiz)
    almacen.guardar(b"huerfana en segundo plano", FECHA)

    hilo = barrer_en_segundo_plano(raiz, set(), fecha_local=FECHA)

    assert hilo.daemon, (
        "Un barrido que no es demonio puede impedir que la aplicación cierre, y cerrar la "
        "aplicación es lo que el portero hace al terminar el turno."
    )
    hilo.join(timeout=10)
    assert not hilo.is_alive()
    assert list((raiz / NOMBRE_DE_LA_CUARENTENA).rglob("*.jpg"))
