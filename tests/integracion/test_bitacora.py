"""Pruebas de la bitácora técnica: rotación, nivel configurable, contexto y UTF-8 (NUC-06).

**Por qué son pruebas de integración y no unitarias.** Lo que hay que demostrar acá no es
que una función devuelva lo que se espera, sino que **el archivo en disco termina con el
contenido correcto**: que rotó cuando tenía que rotar, que el respaldo número 4 nunca
aparece, que un evento `info` no está cuando el nivel es `WARNING`, y que una `ñ` se relee
idéntica. Nada de eso se puede afirmar sin escribir un archivo de verdad.

**Todo corre bajo la raíz con espacios y acentos** (DIS-06). No es un caso especial: es la
condición de todo el entorno de prueba, y la fixture de sesión de `tests/conftest.py` la
instala con `autouse=True`. Acá se afirma explícitamente, además, para que el día que
alguien mueva la fixture el fallo diga por qué importa.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import re
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from porteria.infraestructura.runtime.bitacora import (
    NOMBRE_ARCHIVO,
    cerrar_bitacora,
    configurar_bitacora,
    directorio_de_bitacora_por_defecto,
    obtener_bitacora,
)

from tests.conftest import RutaHostil

#: Caracteres que no sirven como nombre de directorio en Windows.
_PROHIBIDOS_EN_RUTA = re.compile(r"[^\w.-]+", re.UNICODE)


@pytest.fixture
def directorio_de_bitacora(
    ruta_hostil: RutaHostil, request: pytest.FixtureRequest
) -> Iterator[Path]:
    """Un directorio propio por prueba, bajo la raíz con espacios y acentos.

    Uno por prueba y no uno compartido: la rotación cuenta archivos por nombre, y dos
    pruebas escribiendo en el mismo directorio se contarían los respaldos entre sí.
    """
    nombre = _PROHIBIDOS_EN_RUTA.sub("_", request.node.name)[:40]
    destino = ruta_hostil.raiz / "bitacora" / nombre
    destino.mkdir(parents=True, exist_ok=True)
    try:
        yield destino
    finally:
        cerrar_bitacora()
        shutil.rmtree(destino, ignore_errors=True)


def leer_eventos(archivo: Path) -> list[dict[str, object]]:
    """Devuelve los eventos del archivo, uno por línea, ya interpretados."""
    if not archivo.exists():
        return []
    crudo = archivo.read_text(encoding="utf-8")
    return [json.loads(linea) for linea in crudo.splitlines() if linea.strip()]


# --------------------------------------------------------------------------- #
# Formato: estructurado, una línea por evento
# --------------------------------------------------------------------------- #


def test_escribe_un_evento_estructurado_por_linea(directorio_de_bitacora: Path) -> None:
    archivo = configurar_bitacora(directorio_de_bitacora)

    bitacora = obtener_bitacora("porteria.prueba")
    bitacora.info("fuente_abierta", camara="lateral")
    bitacora.info("fuente_cerrada", camara="lateral")

    eventos = leer_eventos(archivo)
    assert len(eventos) == 2, (
        f"Se emitieron dos eventos y el archivo tiene {len(eventos)} líneas "
        f"interpretables. Contenido:\n{archivo.read_text(encoding='utf-8')}"
    )
    assert eventos[0]["event"] == "fuente_abierta"
    assert eventos[0]["level"] == "info"
    assert "timestamp" in eventos[0], (
        "Todo evento lleva su marca temporal: sin instante, una bitácora técnica no "
        "sirve para reconstruir qué pasó y en qué orden."
    )


def test_el_archivo_se_llama_como_declara_el_modulo(directorio_de_bitacora: Path) -> None:
    archivo = configurar_bitacora(directorio_de_bitacora)

    assert archivo == directorio_de_bitacora / NOMBRE_ARCHIVO
    assert archivo.exists()


# --------------------------------------------------------------------------- #
# Rotación (T-01-24: la bitácora técnica no puede llenar el disco de la evidencia)
# --------------------------------------------------------------------------- #


def test_rota_al_superar_el_tamano_maximo(directorio_de_bitacora: Path) -> None:
    """Aparece `porteria.log.1` y el archivo activo vuelve a crecer desde cero."""
    bytes_maximos = 1_000
    archivo = configurar_bitacora(
        directorio_de_bitacora, bytes_maximos=bytes_maximos, respaldos=3
    )

    bitacora = obtener_bitacora("porteria.prueba")
    emitidos = 40
    for numero in range(emitidos):
        bitacora.info("evento_de_relleno", numero=numero, relleno="x" * 60)

    primer_respaldo = directorio_de_bitacora / f"{NOMBRE_ARCHIVO}.1"
    assert primer_respaldo.exists(), (
        "El handler no rotó: con "
        f"{bytes_maximos} bytes de máximo y {emitidos} eventos tendría que existir "
        f"«{primer_respaldo.name}». Archivos presentes: "
        f"{sorted(p.name for p in directorio_de_bitacora.iterdir())}"
    )
    assert primer_respaldo.stat().st_size > 0

    activo = leer_eventos(archivo)
    assert len(activo) < emitidos, (
        "El archivo activo tiene los 40 eventos: no volvió a crecer desde cero, así que "
        "la rotación no ocurrió de verdad."
    )
    assert archivo.stat().st_size <= bytes_maximos, (
        f"El archivo activo mide {archivo.stat().st_size} bytes y el máximo configurado "
        f"es {bytes_maximos}: el handler dejó crecer el archivo por encima del tope."
    )


def test_nunca_hay_mas_respaldos_que_los_configurados(directorio_de_bitacora: Path) -> None:
    """Con `respaldos=3` no puede aparecer `porteria.log.4`, por mucho que se escriba."""
    respaldos = 3
    configurar_bitacora(directorio_de_bitacora, bytes_maximos=400, respaldos=respaldos)

    bitacora = obtener_bitacora("porteria.prueba")
    for numero in range(200):
        bitacora.info("evento_de_relleno", numero=numero, relleno="y" * 80)

    sobrante = directorio_de_bitacora / f"{NOMBRE_ARCHIVO}.{respaldos + 1}"
    assert not sobrante.exists(), (
        f"Apareció «{sobrante.name}» con respaldos={respaldos}. La bitácora técnica "
        "estaría creciendo sin techo en el disco donde vive la evidencia (T-01-24)."
    )
    presentes = sorted(p.name for p in directorio_de_bitacora.iterdir())
    assert len(presentes) <= respaldos + 1, (
        f"Hay {len(presentes)} archivos de bitácora y el tope es {respaldos + 1}: "
        f"{presentes}"
    )


# --------------------------------------------------------------------------- #
# Nivel configurable — sin editar código (NUC-06)
# --------------------------------------------------------------------------- #


def test_el_nivel_configurado_filtra_los_eventos_menos_severos(
    directorio_de_bitacora: Path,
) -> None:
    archivo = configurar_bitacora(directorio_de_bitacora, nivel="WARNING")

    bitacora = obtener_bitacora("porteria.prueba")
    bitacora.info("evento_informativo")
    bitacora.warning("evento_de_alerta")

    nombres = [evento["event"] for evento in leer_eventos(archivo)]
    assert "evento_informativo" not in nombres, (
        "Con nivel WARNING un evento `info` llegó al archivo: el nivel no está filtrando "
        f"nada. Eventos en el archivo: {nombres}"
    )
    assert "evento_de_alerta" in nombres, (
        f"El evento `warning` no llegó al archivo con nivel WARNING. Eventos: {nombres}"
    )


def test_el_nivel_se_cambia_sin_tocar_el_codigo(directorio_de_bitacora: Path) -> None:
    """La misma llamada con otro argumento cambia lo que aparece: nada que recompilar."""
    archivo = configurar_bitacora(directorio_de_bitacora, nivel="WARNING")
    obtener_bitacora("porteria.prueba").info("primer_informativo")

    configurar_bitacora(directorio_de_bitacora, nivel="DEBUG")
    obtener_bitacora("porteria.prueba").info("segundo_informativo")

    nombres = [evento["event"] for evento in leer_eventos(archivo)]
    assert "primer_informativo" not in nombres
    assert "segundo_informativo" in nombres, (
        "Bajar el nivel por configuración no cambió lo que llega al archivo. Eventos: "
        f"{nombres}"
    )


# --------------------------------------------------------------------------- #
# Contexto acumulado por hilo — lo que hace legible una bitácora de N fuentes
# --------------------------------------------------------------------------- #


def test_el_contexto_ligado_aparece_en_la_linea(directorio_de_bitacora: Path) -> None:
    archivo = configurar_bitacora(directorio_de_bitacora)

    obtener_bitacora("porteria.prueba").bind(camara="lateral").info("frame_perdido")

    eventos = leer_eventos(archivo)
    assert eventos, "No se escribió ninguna línea."
    assert eventos[0].get("camara") == "lateral", (
        "El par `camara=lateral` ligado con `bind` no salió en la línea. Sin contexto "
        "acumulado, una bitácora de varias fuentes concurrentes es ilegible. Evento: "
        f"{eventos[0]}"
    )


# --------------------------------------------------------------------------- #
# UTF-8 explícito (Pitfall 8)
# --------------------------------------------------------------------------- #


def test_un_mensaje_con_ene_y_tildes_se_relee_intacto(directorio_de_bitacora: Path) -> None:
    archivo = configurar_bitacora(directorio_de_bitacora)
    mensaje = "La cámara «ñandú» perdió la señal: revisá la conexión áéíóú"

    obtener_bitacora("porteria.prueba").warning("señal_perdida", detalle=mensaje)

    eventos = leer_eventos(archivo)
    assert eventos[0]["event"] == "señal_perdida"
    assert eventos[0]["detalle"] == mensaje, (
        "El mensaje con eñe, tildes y comillas angulares no volvió idéntico. La "
        "codificación por defecto de Windows es cp1252 y corrompe o revienta una "
        f"bitácora en español. Volvió: {eventos[0].get('detalle')!r}"
    )


# --------------------------------------------------------------------------- #
# Ubicación por defecto (D-36)
# --------------------------------------------------------------------------- #


def test_el_directorio_por_defecto_lleva_el_identificador_tecnico() -> None:
    directorio = directorio_de_bitacora_por_defecto()

    assert isinstance(directorio, Path)
    assert "porteria" in str(directorio).lower(), (
        "La ruta por defecto no contiene el identificador técnico «porteria» (D-36). "
        f"Devolvió: {directorio}"
    )


# --------------------------------------------------------------------------- #
# Higiene del proceso: configurar dos veces no deja handlers colgados
# --------------------------------------------------------------------------- #


def test_configurar_dos_veces_no_acumula_handlers(directorio_de_bitacora: Path) -> None:
    """Sin esto, cada llamada duplicaría cada línea y los archivos quedarían abiertos."""
    configurar_bitacora(directorio_de_bitacora)
    archivo = configurar_bitacora(directorio_de_bitacora)

    obtener_bitacora("porteria.prueba").info("evento_unico")

    eventos = [e for e in leer_eventos(archivo) if e["event"] == "evento_unico"]
    assert len(eventos) == 1, (
        f"El evento se escribió {len(eventos)} veces: configurar dos veces acumuló "
        "handlers en vez de reemplazarlos."
    )


def test_cerrar_bitacora_suelta_los_archivos(directorio_de_bitacora: Path) -> None:
    """En Windows un archivo abierto no se puede borrar; cerrar tiene que soltarlo."""
    configurar_bitacora(directorio_de_bitacora)
    obtener_bitacora("porteria.prueba").info("evento_previo_al_cierre")

    cerrar_bitacora()

    instalados = [
        manejador
        for manejador in logging.getLogger().handlers
        if isinstance(manejador, logging.handlers.RotatingFileHandler)
    ]
    assert not instalados, (
        f"Quedaron {len(instalados)} handlers rotativos en el logger raíz después de "
        "cerrar: el archivo sigue abierto y en Windows no se puede borrar ni mover."
    )


# --------------------------------------------------------------------------- #
# DIS-06 dicho de frente
# --------------------------------------------------------------------------- #


def test_las_pruebas_escriben_bajo_la_ruta_con_espacios_y_acentos(
    directorio_de_bitacora: Path,
) -> None:
    texto = str(directorio_de_bitacora)

    assert " " in texto, f"La ruta de prueba no tiene espacios: {texto}"
    assert "ñ" in texto or "á" in texto, f"La ruta de prueba no tiene acentos: {texto}"

    archivo = configurar_bitacora(directorio_de_bitacora)
    obtener_bitacora("porteria.prueba").info("evento_en_ruta_hostil")

    assert leer_eventos(archivo), (
        "No se pudo escribir la bitácora bajo la ruta con espacios y acentos (DIS-06)."
    )
