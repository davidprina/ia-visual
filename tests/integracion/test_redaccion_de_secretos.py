"""Pruebas del redactor de secretos: nada que parezca una credencial llega a un destino.

Es el control (b) de la mitigación de T-01-04, y la prueba de extremo a extremo del final
es el control (c). La diferencia entre las dos mitades de este archivo importa:

* Las pruebas de la primera mitad verifican que la **función** redacta bien: claves
  anidadas, cabeceras HTTP, hashes en formato PHC y patrones dentro de una URL.
* La prueba de extremo a extremo verifica que el procesador **está enchufado donde tiene
  que estar**. Es la única que puede fallar cuando alguien reordena la cadena de
  procesadores, y es la razón por la que existe: una función de redacción perfecta que
  nadie invoca redacta exactamente nada.

Una `Authorization: Basic …` en un archivo que se manda por correo a soporte, o versionada
en git, es un incidente que no se deshace: el historial no se borra.
"""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
import structlog
from porteria.infraestructura.runtime.redaccion import (
    CLAVES_SENSIBLES,
    PROFUNDIDAD_MAXIMA,
    REDACTADO,
    redactar,
)

from porteria.infraestructura.runtime.bitacora import (
    NOMBRE_ARCHIVO,
    cerrar_bitacora,
    configurar_bitacora,
    obtener_bitacora,
)
from tests.conftest import RutaHostil

_PROHIBIDOS_EN_RUTA = re.compile(r"[^\w.-]+", re.UNICODE)

#: Un valor que no se parece a nada del sistema: si aparece en un archivo, llegó de acá.
SECRETO = "Tr3n-Aznar-2026-ñandú!"


def aplicar(evento: dict[str, object]) -> dict[str, object]:
    """Corre el procesador con la firma que le pasa `structlog`."""
    return redactar(None, "info", evento)


@pytest.fixture
def directorio_de_bitacora(
    ruta_hostil: RutaHostil, request: pytest.FixtureRequest
) -> Iterator[Path]:
    """Un directorio propio por prueba, bajo la raíz con espacios y acentos (DIS-06)."""
    nombre = _PROHIBIDOS_EN_RUTA.sub("_", request.node.name)[:40]
    destino = ruta_hostil.raiz / "bitacora-redaccion" / nombre
    destino.mkdir(parents=True, exist_ok=True)
    try:
        yield destino
    finally:
        cerrar_bitacora()
        shutil.rmtree(destino, ignore_errors=True)


# --------------------------------------------------------------------------- #
# Una prueba por clave sensible
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "clave_sensible",
    [
        "contraseña",
        "contrasena",
        "password",
        "token",
        "secret",
        "secreto",
        "clave",
        "apikey",
        "api_key",
        "authorization",
        "credencial",
    ],
)
def test_una_clave_sensible_sale_redactada(clave_sensible: str) -> None:
    salida = aplicar({"event": "consulta_externa", clave_sensible: SECRETO})

    assert salida[clave_sensible] == REDACTADO, (
        f"La clave «{clave_sensible}» salió en claro. Es una de las que la mitigación de "
        f"T-01-04 enumera. Valor emitido: {salida[clave_sensible]!r}"
    )
    assert salida["event"] == "consulta_externa", (
        "El redactor tocó lo que no era sensible: el nombre del evento tiene que "
        "sobrevivir intacto o la bitácora deja de servir para diagnosticar."
    )


@pytest.mark.parametrize(
    "clave_sensible",
    ["CONTRASEÑA", "Password", "TOKEN", "Authorization", "Api_Key"],
)
def test_la_clave_se_reconoce_sin_distinguir_mayusculas(clave_sensible: str) -> None:
    salida = aplicar({"event": "consulta_externa", clave_sensible: SECRETO})

    assert salida[clave_sensible] == REDACTADO, (
        f"«{clave_sensible}» no se reconoció. Las mayúsculas de una clave de un payload "
        "ajeno no las decide este proyecto: PALJET puede mandar lo que quiera."
    )


def test_una_clave_compuesta_tambien_se_reconoce() -> None:
    """`hash_credencial` y `db_password` son nombres reales, no casos de laboratorio."""
    salida = aplicar(
        {
            "event": "arranque",
            "hash_credencial": "$argon2id$v=19$m=65536,t=3,p=4$c2FsZHNhbA$aG1hY2g",
            "db_password": SECRETO,
        }
    )

    assert salida["hash_credencial"] == REDACTADO, (
        "El hash en formato PHC salió en claro. ASVS V7 es explícito: nunca registrar la "
        "contraseña **ni el hash**; el hash es material para un ataque por diccionario "
        "sin límite de intentos."
    )
    assert salida["db_password"] == REDACTADO


def test_una_clave_inocente_no_se_toca() -> None:
    salida = aplicar(
        {
            "event": "fuente_abierta",
            "camara": "lateral",
            "fps_efectivos": 25.01,
            "frames_descartados": 402,
        }
    )

    assert salida == {
        "event": "fuente_abierta",
        "camara": "lateral",
        "fps_efectivos": 25.01,
        "frames_descartados": 402,
    }, (
        "El redactor tocó datos de diagnóstico. Si redacta de más, la bitácora deja de "
        "servir y alguien la va a terminar apagando, que es el peor resultado posible."
    )


# --------------------------------------------------------------------------- #
# Recursividad: la forma real de un payload de un sistema externo
# --------------------------------------------------------------------------- #


def test_un_secreto_anidado_a_tres_niveles_sale_redactado() -> None:
    """Diccionario → lista → diccionario → diccionario. Es la forma de un payload real."""
    evento = {
        "event": "consulta_paljet",
        "peticion": {
            "destinos": [
                {"nombre": "principal", "conexion": {"usuario": "lector", "clave": SECRETO}},
                {"nombre": "respaldo", "conexion": {"usuario": "lector", "token": SECRETO}},
            ]
        },
    }

    salida = aplicar(evento)

    destinos = salida["peticion"]["destinos"]  # type: ignore[index]
    assert destinos[0]["conexion"]["clave"] == REDACTADO
    assert destinos[1]["conexion"]["token"] == REDACTADO
    assert destinos[0]["conexion"]["usuario"] == "lector", (
        "El usuario no es un secreto y sirve para diagnosticar: tiene que sobrevivir."
    )
    assert SECRETO not in json.dumps(salida, ensure_ascii=False, default=str), (
        "El secreto sobrevivió en algún rincón de la estructura. Redactar sólo el primer "
        "nivel deja el valor en claro justo donde los sistemas externos lo ponen."
    )


def test_el_evento_original_no_se_modifica_en_el_lugar() -> None:
    """Quien emitió el evento sigue teniendo su estructura: el redactor no la destruye."""
    original = {"event": "consulta", "credencial": SECRETO, "anidado": {"token": SECRETO}}
    copia = {"event": "consulta", "credencial": SECRETO, "anidado": {"token": SECRETO}}

    aplicar(original)

    assert original == copia, (
        "El redactor mutó la estructura que le pasaron. Un procesador que destruye el "
        "objeto del llamador es una bomba de tiempo: el mismo diccionario puede estar "
        "siendo usado para otra cosa."
    )


def test_una_estructura_ciclica_no_cuelga_el_proceso() -> None:
    """Con tope de profundidad, una estructura cíclica no puede colgar la emisión."""
    ciclico: dict[str, object] = {"event": "raro"}
    ciclico["yo_mismo"] = ciclico

    salida = aplicar(ciclico)

    assert salida["event"] == "raro"
    assert PROFUNDIDAD_MAXIMA > 0


def test_mas_alla_del_tope_de_profundidad_se_redacta_entero() -> None:
    """Ante la duda, redactar: no poder inspeccionar no es motivo para filtrar."""
    hondo: dict[str, object] = {"token": SECRETO}
    for _ in range(PROFUNDIDAD_MAXIMA + 3):
        hondo = {"nivel": hondo}
    evento = {"event": "muy_anidado", **hondo}

    salida = aplicar(evento)

    assert SECRETO not in json.dumps(salida, ensure_ascii=False, default=str), (
        "Un secreto enterrado más allá del tope de profundidad salió en claro. El tope "
        "existe para no colgarse, no para dejar de proteger."
    )


# --------------------------------------------------------------------------- #
# Cabeceras HTTP — control (d) de la mitigación
# --------------------------------------------------------------------------- #


def test_la_cabecera_de_autorizacion_sale_redactada() -> None:
    salida = aplicar(
        {
            "event": "get_remitos",
            "cabeceras": {
                "Authorization": "Basic dXNlcjpwYXNz",
                "Accept": "application/json",
            },
        }
    )

    cabeceras = salida["cabeceras"]
    assert cabeceras["Authorization"] == REDACTADO, (  # type: ignore[index]
        "La cabecera `Authorization` salió en claro. Una `Authorization: Basic …` en un "
        "archivo que viaja por correo o en el historial de git es un incidente que no se "
        "deshace."
    )
    assert cabeceras["Accept"] == "application/json", (  # type: ignore[index]
        "Las cabeceras que no son secretas son justamente las que explican un 406."
    )


# --------------------------------------------------------------------------- #
# URL: redacción parcial, conservando lo que sirve para diagnosticar
# --------------------------------------------------------------------------- #


def test_una_url_con_token_conserva_lo_que_no_es_secreto() -> None:
    salida = aplicar(
        {
            "event": "consulta_externa",
            "url": "https://erp/api/remitos?desde=2026-01-01&token=abc123",
        }
    )

    url = str(salida["url"])
    assert "desde=2026-01-01" in url, (
        "Se redactó la URL entera. Un mensaje de soporte que dice ««redactado»» no le "
        f"sirve a nadie; el que dice qué se pidió, sí. Quedó: {url}"
    )
    assert "abc123" not in url, f"El token sobrevivió dentro de la URL: {url}"
    assert REDACTADO in url


def test_un_token_dentro_del_texto_libre_del_evento_tambien_se_redacta() -> None:
    salida = aplicar(
        {"event": "fallo al pedir https://erp/api/pesos?apikey=zzz999&modo=vivo"}
    )

    texto = str(salida["event"])
    assert "zzz999" not in texto, f"El secreto sobrevivió en el texto del evento: {texto}"
    assert "modo=vivo" in texto


# --------------------------------------------------------------------------- #
# El enchufe: el procesador corre antes de cualquier destino
# --------------------------------------------------------------------------- #


def test_el_redactor_esta_en_la_cadena_antes_del_renderizador(
    directorio_de_bitacora: Path,
) -> None:
    """Inspecciona la configuración efectiva de structlog, no la intención del código."""
    configurar_bitacora(directorio_de_bitacora)

    procesadores = list(structlog.get_config()["processors"])

    assert redactar in procesadores, (
        "`redactar` no está en la cadena de procesadores efectiva. La función existe pero "
        f"no la invoca nadie. Cadena: {[p.__name__ for p in procesadores]}"
    )
    envoltorio = structlog.stdlib.ProcessorFormatter.wrap_for_formatter
    assert envoltorio in procesadores, (
        "La cadena no termina entregando el evento al formateador de la stdlib."
    )
    assert procesadores.index(redactar) < procesadores.index(envoltorio), (
        "`redactar` corre después del envoltorio que entrega el evento a los handlers: "
        "algún destino podría ver el valor en claro."
    )


def test_ningun_secreto_llega_al_archivo_de_bitacora(directorio_de_bitacora: Path) -> None:
    """La prueba de extremo a extremo que exige la sección de seguridad (control (c))."""
    archivo = configurar_bitacora(directorio_de_bitacora)

    bitacora = obtener_bitacora("porteria.prueba").bind(camara="patente")
    bitacora.info(
        "consulta_paljet",
        url="https://erp/api/remitos?desde=2026-01-01&token=" + SECRETO,
        contraseña=SECRETO,
        cabeceras={"Authorization": f"Basic {SECRETO}", "Accept": "application/json"},
        peticion={"destinos": [{"conexion": {"clave": SECRETO}}]},
        hash_credencial="$argon2id$v=19$m=65536,t=3,p=4$" + SECRETO,
    )
    bitacora.warning("reintento", token=SECRETO)

    lineas = (directorio_de_bitacora / NOMBRE_ARCHIVO).read_text(
        encoding="utf-8"
    ).splitlines()

    assert lineas, "No se escribió ninguna línea: la prueba no verificaría nada."
    culpables = [numero for numero, linea in enumerate(lineas, 1) if SECRETO in linea]
    assert not culpables, (
        f"El secreto aparece en las líneas {culpables} de «{archivo.name}». El redactor no "
        "está corriendo antes de los handlers, o alguna vía lo esquiva."
    )
    assert any(REDACTADO in linea for linea in lineas), (
        "No aparece la marca de redacción en ninguna línea: puede que no se haya escrito "
        "nada de lo que se pidió y la prueba esté pasando en el vacío."
    )
    assert any("camara" in linea for linea in lineas), (
        "El contexto ligado desapareció: se redactó de más y la bitácora perdió lo que "
        "sirve para diagnosticar."
    )


def test_el_patron_de_claves_sensibles_esta_compilado_sin_distinguir_mayusculas() -> None:
    """Un patrón sin `IGNORECASE` dejaría pasar `Authorization` y `TOKEN`."""
    assert CLAVES_SENSIBLES.flags & re.IGNORECASE
    assert CLAVES_SENSIBLES.search("Authorization") is not None
    assert CLAVES_SENSIBLES.search("camara") is None
