"""El almacén de evidencia en disco: escritura atómica, ruta relativa y reintento seguro.

Cubre EVI-06 —la imagen va al sistema de archivos y la base sólo guarda metadatos y la
ruta **relativa**— y la mitad de escritura de D-12: el archivo se escribe primero, en un
temporal del mismo directorio, se sincroniza y recién entonces se renombra.

**Por qué hay una prueba dedicada a guardar dos veces el mismo contenido.** El almacén
está direccionado por contenido: el nombre del archivo es el SHA-256 de sus bytes. Dos
capturas distintas con bytes idénticos —trivial con el video sintético en pausa, o con una
cámara apuntando a una pared quieta— producen la misma huella y la misma ruta. Eso no es
un error: es la propiedad que hace que reintentar una escritura sea seguro, y el esquema
del plan 01-05 la acompaña dejando `ruta_relativa` **sin** UNIQUE.

**Por qué se inyecta el fallo en dos puntos distintos.** Un fallo antes del `os.replace`
—la sincronización— y otro en el `os.replace` mismo recorren las dos mitades del camino.
Si sólo se probara una, la otra podría dejar un `.tmp` colgado en cada disco lleno
(T-01-08) sin que nada lo delate.
"""

from __future__ import annotations

import itertools
import os
from pathlib import Path

import pytest

from porteria.aplicacion.puertos.salida.almacen_de_evidencia import AlmacenDeEvidencia
from porteria.dominio.comun.tiempo import FechaLocal
from porteria.dominio.evidencia.huella import HuellaDeIntegridad
from porteria.infraestructura.persistencia import evidencia_fs
from porteria.infraestructura.persistencia.evidencia_fs import AlmacenDeEvidenciaEnDisco
from tests.conftest import RutaHostil

#: Un día cualquiera, fijo: la carpeta de destino depende de la fecha **local** (D-37) y
#: una prueba que use la fecha de hoy dejaría de verificar el formato el día que alguien
#: cambie el separador.
FECHA = FechaLocal("2026-07-30")

#: Contenido determinista. No hace falta que sea un JPEG real: el almacén guarda bytes y
#: la codificación es responsabilidad del codificador (Tarea 3).
CONTENIDO = b"\xff\xd8\xff\xe0 bytes de evidencia \xc3\xb1and\xc3\xba \x00\x01\x02"
OTRO_CONTENIDO = b"\xff\xd8\xff\xe0 otra evidencia distinta \x03\x04\x05"

_contador = itertools.count()


class FalloInyectado(OSError):
    """Corte deliberado en mitad de la escritura."""


@pytest.fixture
def raiz(ruta_hostil: RutaHostil) -> Path:
    """Una raíz propia por prueba, bajo la ruta con espacios y acentos (DIS-06)."""
    destino = ruta_hostil.raiz_evidencia / f"a{next(_contador)}"
    destino.mkdir(parents=True, exist_ok=True)
    return destino


@pytest.fixture
def almacen(raiz: Path) -> AlmacenDeEvidenciaEnDisco:
    return AlmacenDeEvidenciaEnDisco(raiz)


def archivos_de_evidencia(raiz: Path) -> list[Path]:
    return sorted(raiz.rglob("*.jpg"))


def temporales(raiz: Path) -> list[Path]:
    return sorted(raiz.rglob(".tmp_*.part"))


# --------------------------------------------------------------------------- #
# D-03 y D-06: dónde queda el archivo y qué se persiste
# --------------------------------------------------------------------------- #


def test_el_almacen_en_disco_cumple_el_puerto(almacen: AlmacenDeEvidenciaEnDisco) -> None:
    assert isinstance(almacen, AlmacenDeEvidencia), (
        "El adaptador de disco tiene que cumplir el puerto `AlmacenDeEvidencia`: es lo "
        "que permite que el caso de uso del plan 01-07 lo reciba inyectado y que el modo "
        "degradado de D-07 pueda sustituirlo."
    )


def test_guardar_deja_el_archivo_en_la_carpeta_de_la_fecha_local(
    almacen: AlmacenDeEvidenciaEnDisco, raiz: Path
) -> None:
    huella, relativa = almacen.guardar(CONTENIDO, FECHA)

    assert relativa == f"2026/07/30/{huella}.jpg"
    assert (raiz / "2026" / "07" / "30" / f"{huella}.jpg").is_file()


def test_el_nombre_del_archivo_es_la_huella_del_contenido(
    almacen: AlmacenDeEvidenciaEnDisco,
) -> None:
    import hashlib

    huella, relativa = almacen.guardar(CONTENIDO, FECHA)

    esperada = hashlib.sha256(CONTENIDO).hexdigest()
    assert huella == HuellaDeIntegridad(esperada)
    assert relativa.endswith(f"{esperada}.jpg")


def test_la_ruta_devuelta_es_relativa_con_barras_y_sin_contrabarras(
    almacen: AlmacenDeEvidenciaEnDisco,
) -> None:
    """D-06: en la base se persiste ruta **relativa**, con `/`, para poder mover el disco."""
    _, relativa = almacen.guardar(CONTENIDO, FECHA)

    assert not Path(relativa).is_absolute()
    assert "\\" not in relativa
    assert ".." not in relativa
    assert relativa.count("/") == 3


def test_el_contenido_persistido_es_identico_byte_a_byte(
    almacen: AlmacenDeEvidenciaEnDisco,
) -> None:
    """EVI-06: la imagen vive en el sistema de archivos, entera y sin transformar."""
    _, relativa = almacen.guardar(CONTENIDO, FECHA)

    assert almacen.ruta_absoluta(relativa).read_bytes() == CONTENIDO


def test_ruta_absoluta_devuelve_el_archivo_bajo_la_raiz(
    almacen: AlmacenDeEvidenciaEnDisco, raiz: Path
) -> None:
    _, relativa = almacen.guardar(CONTENIDO, FECHA)

    absoluta = almacen.ruta_absoluta(relativa)
    assert absoluta.is_absolute()
    assert absoluta.is_relative_to(raiz.resolve())


# --------------------------------------------------------------------------- #
# Contenido duplicado: el camino feliz del reintento, no un error
# --------------------------------------------------------------------------- #


def test_guardar_dos_veces_el_mismo_contenido_deja_un_solo_archivo(
    almacen: AlmacenDeEvidenciaEnDisco, raiz: Path
) -> None:
    primera_huella, primera_ruta = almacen.guardar(CONTENIDO, FECHA)

    # La segunda llamada no puede lanzar: si lanzara, cada reintento tras un corte
    # dejaría al portero con un error que no puede interpretar.
    segunda_huella, segunda_ruta = almacen.guardar(CONTENIDO, FECHA)

    assert segunda_huella == primera_huella
    assert segunda_ruta == primera_ruta
    assert len(archivos_de_evidencia(raiz)) == 1
    assert not temporales(raiz)


def test_dos_contenidos_distintos_dejan_dos_archivos(
    almacen: AlmacenDeEvidenciaEnDisco, raiz: Path
) -> None:
    """Contraprueba de la anterior: si el almacén siempre devolviera lo mismo, pasaría."""
    primera, _ = almacen.guardar(CONTENIDO, FECHA)
    segunda, _ = almacen.guardar(OTRO_CONTENIDO, FECHA)

    assert primera != segunda
    assert len(archivos_de_evidencia(raiz)) == 2


# --------------------------------------------------------------------------- #
# D-12 y T-01-08: una escritura interrumpida no deja nada a medias
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("funcion_que_falla", ["fsync", "replace"])
def test_un_fallo_en_la_escritura_no_deja_temporal_ni_archivo_final(
    almacen: AlmacenDeEvidenciaEnDisco,
    raiz: Path,
    monkeypatch: pytest.MonkeyPatch,
    funcion_que_falla: str,
) -> None:
    def explotar(*_args: object, **_kwargs: object) -> None:
        raise FalloInyectado("corte deliberado en mitad de la escritura")

    monkeypatch.setattr(evidencia_fs.os, funcion_que_falla, explotar)

    with pytest.raises(FalloInyectado):
        almacen.guardar(CONTENIDO, FECHA)

    monkeypatch.undo()

    assert not archivos_de_evidencia(raiz), (
        "Quedó un .jpg en la ruta final después de un fallo: la escritura no fue atómica."
    )
    assert not temporales(raiz), (
        "Quedó un temporal .tmp_*.part colgado. Sin la limpieza, un disco lleno los "
        "acumula hasta llenar lo poco que queda (T-01-08)."
    )


def test_tras_el_fallo_se_puede_volver_a_guardar(
    almacen: AlmacenDeEvidenciaEnDisco, raiz: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El estado que deja el fallo tiene que ser reintentable, no un callejón sin salida."""

    def explotar(*_args: object, **_kwargs: object) -> None:
        raise FalloInyectado("corte deliberado")

    monkeypatch.setattr(evidencia_fs.os, "replace", explotar)
    with pytest.raises(FalloInyectado):
        almacen.guardar(CONTENIDO, FECHA)
    monkeypatch.undo()

    _, relativa = almacen.guardar(CONTENIDO, FECHA)

    assert almacen.ruta_absoluta(relativa).read_bytes() == CONTENIDO
    assert len(archivos_de_evidencia(raiz)) == 1


# --------------------------------------------------------------------------- #
# D-07: el modo degradado necesita saber si la raíz está
# --------------------------------------------------------------------------- #


def test_esta_disponible_distingue_la_raiz_presente_de_la_ausente(
    ruta_hostil: RutaHostil,
) -> None:
    ausente = ruta_hostil.raiz_evidencia / f"a{next(_contador)}-sin-crear"
    almacen = AlmacenDeEvidenciaEnDisco(ausente)

    assert almacen.esta_disponible() is False

    ausente.mkdir(parents=True)
    assert almacen.esta_disponible() is True


def test_el_directorio_de_la_fecha_se_crea_solo(
    almacen: AlmacenDeEvidenciaEnDisco, raiz: Path
) -> None:
    assert not (raiz / "2026").exists()

    almacen.guardar(CONTENIDO, FECHA)

    assert (raiz / "2026" / "07" / "30").is_dir()


def test_el_temporal_vive_en_el_directorio_de_destino(
    almacen: AlmacenDeEvidenciaEnDisco, raiz: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`os.replace` sólo puede ser atómico dentro del mismo volumen (Pitfall 6)."""
    vistos: list[str] = []
    mkstemp_real = evidencia_fs.tempfile.mkstemp

    def espiar(*args: object, **kwargs: object) -> tuple[int, str]:
        descriptor, nombre = mkstemp_real(*args, **kwargs)  # type: ignore[arg-type]
        vistos.append(nombre)
        return descriptor, nombre

    monkeypatch.setattr(evidencia_fs.tempfile, "mkstemp", espiar)

    _, relativa = almacen.guardar(CONTENIDO, FECHA)

    assert vistos, "No se usó `tempfile.mkstemp`: la escritura no pasó por un temporal."
    destino = almacen.ruta_absoluta(relativa)
    assert Path(os.fspath(vistos[0])).parent.name == destino.parent.name
