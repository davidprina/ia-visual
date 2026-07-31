"""EVI-05, la prueba de la prueba: **un byte alterado en tres posiciones distintas**.

Esta es la mitad que le da valor probatorio a la otra. `test_verificacion_huella.py`
demuestra que recalcular reproduce lo persistido; acá se demuestra lo contrario —que
cualquier alteración lo rompe—, que es lo que un auditor va a querer ver.

**Por qué tres posiciones y no una.** Si la verificación estuviera truncando la lectura
—leyendo sólo el primer bloque, por ejemplo, que es el defecto clásico de un bucle de
lectura escrito a mano— una alteración en el primer byte se detectaría y una en el último
no. Probar sólo el primer byte daría una compuerta que pasa siempre y una propiedad de
auditoría que en realidad no existe. `test_una_verificacion_truncada_no_detecta_el_ultimo_byte`
lo demuestra sobre un verificador deliberadamente roto: sin las tres posiciones, ese
verificador pasaría por bueno.

**Por qué hay un caso de control.** Sin él, una implementación rota que devolviera siempre
`COMPROMETIDA` pasaría los tres casos de alteración con honores.

**Por qué el archivo mide 256 KiB.** Para que las tres posiciones caigan en bloques de
lectura genuinamente distintos. Con un archivo de unos pocos bytes, «primero», «medio» y
«último» son el mismo bloque y las tres pruebas serían una sola disfrazada de tres.

**Por qué XOR y no un literal fijo.** Escribir un valor fijo en la posición elegida no
garantiza que el byte cambie: si ya valía ese valor, el archivo queda idéntico, la huella
también, y la prueba pasa por accidente reportando una detección que no ocurrió. `b ^ 0xFF`
cambia el byte sea cual sea su valor original.

**Y por qué al final de cada caso se afirma que el archivo sigue existiendo.** D-09 y D-10:
el sistema **nunca** borra evidencia por sí solo. Detectar la manipulación y borrar el
archivo destruiría justamente la prueba de que hubo manipulación.
"""

from __future__ import annotations

import hashlib
import itertools
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from porteria.dominio.comun.tiempo import FechaLocal
from porteria.dominio.evidencia.estados import EstadoDeIntegridad, evaluar
from porteria.dominio.evidencia.huella import HuellaDeIntegridad
from porteria.infraestructura.persistencia.evidencia_fs import AlmacenDeEvidenciaEnDisco
from tests.conftest import RutaHostil

FECHA = FechaLocal("2026-07-30")

#: 256 KiB exactos y deterministas: 1024 repeticiones de los 256 valores posibles.
CONTENIDO = bytes(range(256)) * 1024

#: Tamaño del bloque que lee el verificador truncado de la anti-vacuidad.
BLOQUE_TRUNCADO = 64 * 1024

_contador = itertools.count()


@dataclass(frozen=True)
class EvidenciaPersistida:
    """Lo que hace falta para atacar un archivo ya guardado."""

    almacen: AlmacenDeEvidenciaEnDisco
    huella: HuellaDeIntegridad
    relativa: str
    absoluta: Path


@pytest.fixture
def evidencia(ruta_hostil: RutaHostil) -> Iterator[EvidenciaPersistida]:
    """Un archivo de 256 KiB recién persistido, en una raíz propia de esta prueba."""
    raiz = ruta_hostil.raiz_evidencia / f"m{next(_contador)}"
    raiz.mkdir(parents=True, exist_ok=True)
    almacen = AlmacenDeEvidenciaEnDisco(raiz)
    huella, relativa = almacen.guardar(CONTENIDO, FECHA)

    yield EvidenciaPersistida(
        almacen=almacen,
        huella=huella,
        relativa=relativa,
        absoluta=almacen.ruta_absoluta(relativa),
    )


def alterar_un_byte(archivo: Path, posicion: int) -> None:
    """Invierte el byte de `posicion` con XOR: cambia siempre, valga lo que valga."""
    with archivo.open("r+b") as manejador:
        manejador.seek(posicion)
        original = manejador.read(1)
        manejador.seek(posicion)
        manejador.write(bytes([original[0] ^ 0xFF]))


# --------------------------------------------------------------------------- #
# El archivo bajo ataque
# --------------------------------------------------------------------------- #


def test_el_archivo_de_prueba_mide_al_menos_256_kib(evidencia: EvidenciaPersistida) -> None:
    """Anti-vacuidad del tamaño: con un archivo chico las tres posiciones serían una."""
    assert evidencia.absoluta.stat().st_size >= 256 * 1024


def test_sin_alterar_nada_la_evidencia_esta_integra(evidencia: EvidenciaPersistida) -> None:
    """Caso de control. Sin él, una implementación que siempre acusa pasaría los tres."""
    estado = evidencia.almacen.verificar(evidencia.relativa, evidencia.huella)

    assert estado is EstadoDeIntegridad.INTEGRA
    assert evidencia.absoluta.is_file()


@pytest.mark.parametrize(
    "nombre_de_la_posicion",
    ["primer byte", "byte del medio", "último byte"],
)
def test_alterar_un_solo_byte_deja_la_evidencia_comprometida(
    evidencia: EvidenciaPersistida, nombre_de_la_posicion: str
) -> None:
    largo = evidencia.absoluta.stat().st_size
    posicion = {
        "primer byte": 0,
        "byte del medio": largo // 2,
        "último byte": largo - 1,
    }[nombre_de_la_posicion]

    alterar_un_byte(evidencia.absoluta, posicion)

    estado = evidencia.almacen.verificar(evidencia.relativa, evidencia.huella)

    assert estado is EstadoDeIntegridad.COMPROMETIDA, (
        f"Se alteró el {nombre_de_la_posicion} (posición {posicion} de {largo}) y la "
        "verificación no lo detectó. Si sólo falla esta posición y las otras dos pasan, "
        "la lectura del archivo se está truncando."
    )
    assert evidencia.absoluta.stat().st_size == largo, (
        "La verificación cambió el tamaño del archivo: alterar un byte no puede "
        "convertirse en perder evidencia."
    )
    assert evidencia.absoluta.is_file(), (
        "El archivo desapareció tras detectar la manipulación. D-09 y D-10: la evidencia "
        "comprometida se marca y se muestra así, nunca se borra ni se oculta — borrarla "
        "destruye justamente la prueba de que hubo manipulación."
    )


def test_truncar_el_archivo_en_un_byte_deja_la_evidencia_comprometida(
    evidencia: EvidenciaPersistida,
) -> None:
    """Quitar contenido es tan manipulación como cambiarlo, y se detecta igual."""
    largo = evidencia.absoluta.stat().st_size
    with evidencia.absoluta.open("r+b") as manejador:
        manejador.truncate(largo - 1)

    estado = evidencia.almacen.verificar(evidencia.relativa, evidencia.huella)

    assert estado is EstadoDeIntegridad.COMPROMETIDA
    assert evidencia.absoluta.is_file()


def test_reemplazar_el_archivo_entero_deja_la_evidencia_comprometida(
    evidencia: EvidenciaPersistida,
) -> None:
    """El ataque más obvio: cambiar la foto por otra conservando el nombre."""
    evidencia.absoluta.write_bytes(b"otra foto completamente distinta")

    estado = evidencia.almacen.verificar(evidencia.relativa, evidencia.huella)

    assert estado is EstadoDeIntegridad.COMPROMETIDA
    assert evidencia.absoluta.is_file()


# --------------------------------------------------------------------------- #
# La prueba de la prueba: por qué tres posiciones y no una
# --------------------------------------------------------------------------- #


#: Lo que un sistema truncado habría persistido en la ingesta: el hash del primer bloque.
#: Tiene que ser el hash truncado y no el del archivo entero, porque un defecto de lectura
#: por bloques afecta a las dos puntas —se guarda mal y se verifica mal igual—, y ésa es
#: justamente la razón por la que el defecto pasa desapercibido.
HUELLA_TRUNCADA_EN_LA_INGESTA = HuellaDeIntegridad(
    hashlib.sha256(CONTENIDO[:BLOQUE_TRUNCADO]).hexdigest()
)


def verificador_truncado(absoluta: Path) -> EstadoDeIntegridad:
    """Un verificador **deliberadamente roto**: hashea sólo el primer bloque.

    Vive acá y no en el producto. Es el defecto clásico de un bucle de lectura escrito a
    mano —leer una vez y olvidarse del `while`— y existe para demostrar que la
    parametrización de tres posiciones no es decorativa.
    """
    with absoluta.open("rb") as manejador:
        digest = hashlib.sha256(manejador.read(BLOQUE_TRUNCADO)).hexdigest()
    return evaluar(HUELLA_TRUNCADA_EN_LA_INGESTA, HuellaDeIntegridad(digest))


def test_una_verificacion_truncada_no_detecta_el_ultimo_byte(
    evidencia: EvidenciaPersistida,
) -> None:
    """Si sólo se probara el primer byte, el verificador roto pasaría por bueno.

    Las dos aserciones juntas son el argumento completo: el verificador truncado **sí**
    acusa la alteración del primer byte —así que una compuerta que probara sólo esa
    posición lo aprobaría— y **no** acusa la del último. Ésa es la clase de falso verde que
    la sección de anti-vacuidad de la estrategia de validación manda cerrar con una tarea
    propia.
    """
    largo = evidencia.absoluta.stat().st_size

    alterar_un_byte(evidencia.absoluta, largo - 1)

    assert verificador_truncado(evidencia.absoluta) is EstadoDeIntegridad.INTEGRA, (
        "El verificador truncado detectó una alteración fuera de su bloque, así que ya no "
        "demuestra nada. Revisá BLOQUE_TRUNCADO contra el tamaño del contenido."
    )
    assert evidencia.almacen.verificar(evidencia.relativa, evidencia.huella) is (
        EstadoDeIntegridad.COMPROMETIDA
    ), "El verificador del producto tiene que detectar lo que el truncado se pierde."


def test_la_verificacion_truncada_si_detecta_el_primer_byte(
    evidencia: EvidenciaPersistida,
) -> None:
    """La otra mitad del argumento: por eso probar sólo el primer byte no alcanza."""
    alterar_un_byte(evidencia.absoluta, 0)

    assert verificador_truncado(evidencia.absoluta) is EstadoDeIntegridad.COMPROMETIDA
