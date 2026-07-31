"""La raíz de evidencia como entrada no confiable: acentos, escapes y MAX_PATH.

Tres cosas distintas se prueban acá, y las tres tienen la misma forma: **un dato que
viene de afuera termina siendo una ruta del sistema de archivos**.

1. **DIS-06** — la raíz real de un cliente tiene espacios y acentos (`Producción`,
   `Portería`, `Evidencia fotográfica`). Toda la suite corre bajo una raíz así, y acá se
   afirma explícitamente que el almacén completo —guardar, verificar, releer— funciona
   sobre ella.

2. **T-01-02, path traversal** — el nombre del archivo se deriva del hash hexadecimal, 64
   caracteres de `[0-9a-f]`, imposible de envenenar. Pero la `ruta_relativa` que se lee de
   la base **vuelve del almacenamiento**, y ese es un borde de confianza: una fila alterada
   a mano con `../../windows/system32/x.jpg` no puede convertirse en una escritura ni en
   una lectura fuera de la raíz.

3. **T-01-17, MAX_PATH (Pitfall 3)** — el límite de 260 caracteres está activo en la
   mayoría de las instalaciones de Windows. Sin validación, el cliente configura una raíz
   larga, todo anda tres meses y después las escrituras empiezan a fallar con un
   `FileNotFoundError` que no dice una palabra sobre el largo de la ruta. El mensaje tiene
   que decir **los dos números** (UI-05).
"""

from __future__ import annotations

import itertools
from pathlib import Path

import pytest

from porteria.aplicacion.puertos.salida.almacen_de_evidencia import RutaFueraDeLaRaiz
from porteria.dominio.comun.tiempo import FechaLocal
from porteria.dominio.evidencia.estados import EstadoDeIntegridad
from porteria.dominio.evidencia.huella import HuellaDeIntegridad
from porteria.infraestructura.configuracion.arranque import LARGO_MAXIMO_RAIZ_EVIDENCIA
from porteria.infraestructura.persistencia.evidencia_fs import (
    AlmacenDeEvidenciaEnDisco,
    RaizDemasiadoLarga,
)
from tests.conftest import NOMBRE_RAIZ, SUBDIR_EVIDENCIA, RutaHostil

FECHA = FechaLocal("2026-07-30")
CONTENIDO = "evidencia con ñandú y áéíóú".encode()
HUELLA_AJENA = HuellaDeIntegridad("0" * 64)

#: Rutas que un atacante —o una fila corrompida— podría poner en `ruta_relativa`.
RUTAS_QUE_ESCAPAN = [
    "../../windows/system32/x.jpg",
    "..\\..\\windows\\system32\\x.jpg",
    "2026/07/30/../../../../x.jpg",
    "C:\\Windows\\x.jpg",
    "/etc/passwd",
    "\\\\servidor\\compartido\\x.jpg",
]

_contador = itertools.count()


@pytest.fixture
def raiz(ruta_hostil: RutaHostil) -> Path:
    destino = ruta_hostil.raiz_evidencia / f"h{next(_contador)}"
    destino.mkdir(parents=True, exist_ok=True)
    return destino


@pytest.fixture
def almacen(raiz: Path) -> AlmacenDeEvidenciaEnDisco:
    return AlmacenDeEvidenciaEnDisco(raiz)


def todo_lo_que_hay(raiz: Path) -> set[str]:
    return {str(hijo.relative_to(raiz)) for hijo in raiz.rglob("*")}


# --------------------------------------------------------------------------- #
# 1. DIS-06: la raíz real tiene espacios y acentos
# --------------------------------------------------------------------------- #


def test_la_raiz_de_la_suite_tiene_espacios_y_acentos(raiz: Path) -> None:
    """Anti-vacuidad: si la raíz fuera `C:\\tmp`, todo lo de abajo probaría nada."""
    texto = str(raiz)

    assert NOMBRE_RAIZ in texto
    assert SUBDIR_EVIDENCIA in texto
    assert " " in texto
    assert any(letra in texto for letra in "áéíóúñ")


def test_el_ciclo_completo_funciona_sobre_la_raiz_con_acentos(
    almacen: AlmacenDeEvidenciaEnDisco,
) -> None:
    huella, relativa = almacen.guardar(CONTENIDO, FECHA)

    assert almacen.ruta_absoluta(relativa).read_bytes() == CONTENIDO
    assert almacen.verificar(relativa, huella) is EstadoDeIntegridad.INTEGRA


# --------------------------------------------------------------------------- #
# 2. T-01-02: la ruta relativa que vuelve de la base no puede escapar
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("relativa", RUTAS_QUE_ESCAPAN)
def test_una_ruta_que_escapa_de_la_raiz_se_rechaza_sin_tocar_el_disco(
    almacen: AlmacenDeEvidenciaEnDisco, raiz: Path, relativa: str
) -> None:
    antes = todo_lo_que_hay(raiz)

    with pytest.raises(RutaFueraDeLaRaiz):
        almacen.ruta_absoluta(relativa)

    assert todo_lo_que_hay(raiz) == antes


@pytest.mark.parametrize("relativa", RUTAS_QUE_ESCAPAN)
def test_verificar_una_ruta_que_escapa_se_rechaza_antes_de_leer(
    almacen: AlmacenDeEvidenciaEnDisco, relativa: str
) -> None:
    """El rechazo llega antes que el `open`: no es un `FileNotFoundError` con suerte."""
    with pytest.raises(RutaFueraDeLaRaiz):
        almacen.verificar(relativa, HUELLA_AJENA)


def test_el_mensaje_del_rechazo_nombra_la_ruta_ofensiva(
    almacen: AlmacenDeEvidenciaEnDisco,
) -> None:
    with pytest.raises(RutaFueraDeLaRaiz) as capturado:
        almacen.ruta_absoluta("../../windows/system32/x.jpg")

    assert "windows/system32" in str(capturado.value).replace("\\", "/")


def test_una_ruta_relativa_legitima_no_se_rechaza(
    almacen: AlmacenDeEvidenciaEnDisco,
) -> None:
    """Contraprueba: si la guardia rechazara todo, las de arriba pasarían igual."""
    _, relativa = almacen.guardar(CONTENIDO, FECHA)

    assert almacen.ruta_absoluta(relativa).is_file()


# --------------------------------------------------------------------------- #
# 3. T-01-17: MAX_PATH y el mensaje que dice los dos números (UI-05)
# --------------------------------------------------------------------------- #


def test_una_raiz_demasiado_larga_se_rechaza_al_construir_el_almacen(
    ruta_hostil: RutaHostil,
) -> None:
    larga = ruta_hostil.raiz_evidencia / ("l" * 120) / ("a" * 120)
    largo_real = len(str(larga.resolve()))

    with pytest.raises(RaizDemasiadoLarga) as capturado:
        AlmacenDeEvidenciaEnDisco(larga)

    mensaje = str(capturado.value)
    assert str(LARGO_MAXIMO_RAIZ_EVIDENCIA) in mensaje, (
        "El mensaje no dice cuál es el máximo, así que quien configura el equipo no sabe "
        f"a qué achicar la ruta. Mensaje:\n{mensaje}"
    )
    assert str(largo_real) in mensaje, (
        "El mensaje no dice cuánto mide la ruta elegida, así que no se puede saber por "
        f"cuánto se pasó. Largo real: {largo_real}. Mensaje:\n{mensaje}"
    )


def test_la_raiz_demasiado_larga_no_se_crea_en_el_disco(ruta_hostil: RutaHostil) -> None:
    larga = ruta_hostil.raiz_evidencia / ("l" * 120) / ("a" * 120)

    with pytest.raises(RaizDemasiadoLarga):
        AlmacenDeEvidenciaEnDisco(larga)

    assert not larga.exists()
    assert not larga.parent.exists()


def test_una_raiz_que_entra_en_el_limite_se_acepta(raiz: Path) -> None:
    """Anti-vacuidad de la anterior: si rechazara toda raíz, pasaría igual."""
    assert len(str(raiz.resolve())) <= LARGO_MAXIMO_RAIZ_EVIDENCIA

    almacen = AlmacenDeEvidenciaEnDisco(raiz)

    assert almacen.esta_disponible() is True
