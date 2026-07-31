"""EVI-05, mitad «archivo»: recalcular la huella reproduce exactamente lo persistido.

La otra mitad —que alterar un byte lo rompa— vive en `test_manipulacion_evidencia.py`,
como tarea propia, porque es la prueba de la prueba de este criterio: sin ella, una
verificación que leyera sólo el primer bloque del archivo pasaría por buena.

**Por qué el archivo grande.** `hashlib.file_digest` lee por bloques. Un archivo de un
solo bloque no distinguiría una lectura completa de una truncada, así que las pruebas de
ida y vuelta usan un contenido de varios megabytes.
"""

from __future__ import annotations

import hashlib
import itertools
from pathlib import Path

import pytest

from porteria.dominio.comun.tiempo import FechaLocal
from porteria.dominio.evidencia.estados import EstadoDeIntegridad
from porteria.dominio.evidencia.huella import HuellaDeIntegridad
from porteria.infraestructura.persistencia.evidencia_fs import AlmacenDeEvidenciaEnDisco
from tests.conftest import RutaHostil

FECHA = FechaLocal("2026-07-30")

#: 3 MiB deterministas: varios bloques de lectura, sin depender del azar.
CONTENIDO_GRANDE = bytes(range(256)) * 4096

#: Una huella válida por su forma pero que no es la de ningún archivo de acá.
HUELLA_AJENA = HuellaDeIntegridad("0" * 64)

_contador = itertools.count()


@pytest.fixture
def almacen(ruta_hostil: RutaHostil) -> AlmacenDeEvidenciaEnDisco:
    raiz = ruta_hostil.raiz_evidencia / f"v{next(_contador)}"
    raiz.mkdir(parents=True, exist_ok=True)
    return AlmacenDeEvidenciaEnDisco(raiz)


def test_la_huella_devuelta_es_la_del_contenido_que_se_guardo(
    almacen: AlmacenDeEvidenciaEnDisco,
) -> None:
    huella, _ = almacen.guardar(CONTENIDO_GRANDE, FECHA)

    assert huella.valor == hashlib.sha256(CONTENIDO_GRANDE).hexdigest()


def test_recalcular_desde_el_archivo_reproduce_la_huella_de_la_ingesta(
    almacen: AlmacenDeEvidenciaEnDisco,
) -> None:
    """El corazón de EVI-05: lo que se persistió y lo que se lee coinciden."""
    huella, relativa = almacen.guardar(CONTENIDO_GRANDE, FECHA)

    with almacen.ruta_absoluta(relativa).open("rb") as archivo:
        recalculada = hashlib.file_digest(archivo, "sha256").hexdigest()

    assert recalculada == huella.valor


def test_verificar_devuelve_integra_cuando_nadie_tocó_el_archivo(
    almacen: AlmacenDeEvidenciaEnDisco,
) -> None:
    huella, relativa = almacen.guardar(CONTENIDO_GRANDE, FECHA)

    assert almacen.verificar(relativa, huella) is EstadoDeIntegridad.INTEGRA


def test_verificar_devuelve_comprometida_con_una_huella_que_no_es_la_del_archivo(
    almacen: AlmacenDeEvidenciaEnDisco,
) -> None:
    """Contraprueba: una implementación que siempre dijera INTEGRA fallaría acá."""
    _, relativa = almacen.guardar(CONTENIDO_GRANDE, FECHA)

    assert almacen.verificar(relativa, HUELLA_AJENA) is EstadoDeIntegridad.COMPROMETIDA


def test_verificar_no_borra_ni_oculta_el_archivo(
    almacen: AlmacenDeEvidenciaEnDisco,
) -> None:
    """D-09: la evidencia comprometida se marca, nunca se borra ni se esconde."""
    _, relativa = almacen.guardar(CONTENIDO_GRANDE, FECHA)
    absoluta = almacen.ruta_absoluta(relativa)

    almacen.verificar(relativa, HUELLA_AJENA)

    assert absoluta.is_file()
    assert absoluta.read_bytes() == CONTENIDO_GRANDE


def test_verificar_un_archivo_ausente_lo_dice_con_la_ruta(
    almacen: AlmacenDeEvidenciaEnDisco,
) -> None:
    """Un archivo que no está no es «comprometido»: es otro problema y se nombra."""
    relativa = f"2026/07/30/{'a' * 64}.jpg"

    with pytest.raises(FileNotFoundError) as capturado:
        almacen.verificar(relativa, HUELLA_AJENA)

    assert relativa in str(capturado.value).replace("\\", "/")


def test_dos_archivos_distintos_no_comparten_huella(
    almacen: AlmacenDeEvidenciaEnDisco,
) -> None:
    primera, ruta_primera = almacen.guardar(CONTENIDO_GRANDE, FECHA)
    segunda, ruta_segunda = almacen.guardar(CONTENIDO_GRANDE + b"!", FECHA)

    assert primera != segunda
    assert ruta_primera != ruta_segunda
    assert almacen.verificar(ruta_segunda, primera) is EstadoDeIntegridad.COMPROMETIDA


def test_la_verificacion_no_depende_del_objeto_que_guardó(
    ruta_hostil: RutaHostil,
) -> None:
    """Reabrir el almacén —o abrirlo en otro proceso— tiene que verificar igual."""
    raiz = ruta_hostil.raiz_evidencia / f"v{next(_contador)}"
    raiz.mkdir(parents=True, exist_ok=True)

    huella, relativa = AlmacenDeEvidenciaEnDisco(raiz).guardar(CONTENIDO_GRANDE, FECHA)
    otro = AlmacenDeEvidenciaEnDisco(Path(str(raiz)))

    assert otro.verificar(relativa, huella) is EstadoDeIntegridad.INTEGRA
