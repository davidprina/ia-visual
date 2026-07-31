"""Pruebas de la configuración en dos capas y de la orden `configurar` (D-30).

La frontera entre las dos capas no es minimalismo estético, es el control (a) de la
mitigación de T-01-04: **el archivo de arranque lleva sólo rutas**. Un archivo de texto
plano con la contraseña de la base de PALJET es exactamente el incidente que hay que hacer
imposible por diseño, y la prueba que recorre `model_fields` contrastándolos contra el
patrón del módulo de redacción es la que lo mantiene imposible el día que alguien quiera
agregar "un campito más".

La segunda mitad es T-01-22: un cambio de configuración es un **hecho auditable**, no un
ajuste anónimo. Escribir sin autor falla, y `listar()` devuelve quién y cuándo. Es lo que
sostiene D-40: nadie ensancha la ventana de aceptación sin dejar rastro.

**Por qué la tabla la crea la prueba.** Este plan no depende del 01-05, que es el dueño del
esquema real. `ConfiguracionEnBase` recibe un `Engine` **inyectado**, así que acá se le
pasa uno apuntando a un esquema mínimo creado por esta misma prueba, y en el producto el
plan 01-07 le pasa el real sin modificar la clase. Que la tabla de acá y la de allá tengan
que coincidir es deliberado: si divergen, estas pruebas lo dicen.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from porteria.aplicacion.puertos.salida.configuracion import (
    Configuracion,
    ValorDeConfiguracion,
)
from porteria.infraestructura.configuracion.arranque import (
    LARGO_MAXIMO_RAIZ_EVIDENCIA,
    NOMBRE_ARCHIVO_DE_ARRANQUE,
    VARIABLE_DE_DIRECTORIO,
    ConfiguracionDeArranque,
    ConfiguracionDeArranqueAusente,
    RaizDeEvidenciaDemasiadoLarga,
    cargar_configuracion_de_arranque,
    directorio_de_configuracion_por_defecto,
    ruta_del_archivo_de_arranque,
)
from porteria.infraestructura.configuracion.en_base import (
    CATALOGO,
    AutorRequerido,
    ClaveDesconocida,
    ConfiguracionEnBase,
)
from pydantic import ValidationError
from sqlalchemy import Column, MetaData, String, Table, Text
from sqlalchemy.engine import Engine
from typer.testing import CliRunner

from porteria.cli.app import app
from porteria.infraestructura.runtime.redaccion import CLAVES_SENSIBLES
from porteria.infraestructura.runtime.reloj import RelojDelProceso
from tests.conftest import RutaHostil

#: Las siete claves que el composition root del plan 01-07 recorre para inyectar valores.
SIETE_CLAVES = {
    "ventana_aceptacion_ms",
    "nivel_bitacora",
    "bytes_maximos_bitacora",
    "respaldos_bitacora",
    "calidad_jpeg_por_camara",
    "dias_retencion_payload_crudo",
    "copias_de_seguridad_a_conservar",
}

#: Esquema mínimo, creado por la prueba. El dueño del esquema real es el plan 01-05.
_METADATOS = MetaData()
TABLA_CONFIGURACION = Table(
    "configuracion",
    _METADATOS,
    Column("clave", String(80), primary_key=True),
    Column("valor", Text, nullable=False),
    Column("cambiado_por", String(120), nullable=False),
    Column("cambiado_en_utc_iso", String(40), nullable=False),
)


@pytest.fixture
def motor_con_tabla(motor_sqlite: Engine) -> Engine:
    """El motor de la fixture de sesión, con la tabla `configuracion` ya creada."""
    _METADATOS.create_all(motor_sqlite)
    return motor_sqlite


@pytest.fixture
def configuracion(motor_con_tabla: Engine) -> ConfiguracionEnBase:
    return ConfiguracionEnBase(motor_con_tabla, RelojDelProceso())


@pytest.fixture
def directorio_de_arranque(
    ruta_hostil: RutaHostil, request: pytest.FixtureRequest
) -> Iterator[Path]:
    """Un directorio de configuración por prueba, bajo la ruta con espacios y acentos."""
    nombre = re.sub(r"[^\w.-]+", "_", request.node.name)[:40]
    destino = ruta_hostil.raiz / "configuracion" / nombre
    destino.mkdir(parents=True, exist_ok=True)
    yield destino


def escribir_archivo_de_arranque(directorio: Path, ruta_hostil: RutaHostil) -> Path:
    """Escribe un `porteria.toml` válido, con cadenas literales por los `\\` de Windows."""
    destino = directorio / NOMBRE_ARCHIVO_DE_ARRANQUE
    destino.write_text(
        f"ruta_base_datos = '{ruta_hostil.ruta_db}'\n"
        f"raiz_evidencia = '{ruta_hostil.raiz_evidencia}'\n",
        encoding="utf-8",
    )
    return destino


# --------------------------------------------------------------------------- #
# Capa 1: el archivo de arranque lleva sólo rutas (D-30, control (a) de T-01-04)
# --------------------------------------------------------------------------- #


def test_la_capa_1_declara_exactamente_dos_campos_obligatorios() -> None:
    """Agregar un tercero tiene que ser un cambio deliberado, no un descuido."""
    campos = ConfiguracionDeArranque.model_fields

    assert set(campos) == {"ruta_base_datos", "raiz_evidencia"}, (
        "La capa 1 dejó de llevar exactamente dos campos. D-30 es explícito: sólo lo "
        f"imprescindible para abrir. Campos declarados: {sorted(campos)}"
    )
    for nombre, campo in campos.items():
        assert campo.is_required(), (
            f"«{nombre}» tiene valor por defecto. Un valor inventado para una ruta hace "
            "que la aplicación abra apuntando a cualquier lado en vez de decir que le "
            "falta configuración."
        )


def test_ninguna_clave_de_la_capa_1_se_parece_a_una_credencial() -> None:
    """Control (a) de T-01-04, sostenido como prueba y no como buena intención."""
    culpables = [
        nombre
        for nombre in ConfiguracionDeArranque.model_fields
        if CLAVES_SENSIBLES.search(nombre) is not None
    ]

    assert not culpables, (
        f"Los campos {culpables} de la capa 1 coinciden con el patrón de claves "
        "sensibles. Las credenciales de sistemas externos van en la base, en una tabla "
        "aparte: un archivo de arranque en texto plano con la contraseña de PALJET es el "
        "incidente que D-30 hace imposible por diseño."
    )


def test_carga_el_archivo_de_arranque_bajo_la_ruta_con_espacios_y_acentos(
    directorio_de_arranque: Path, ruta_hostil: RutaHostil
) -> None:
    archivo = escribir_archivo_de_arranque(directorio_de_arranque, ruta_hostil)

    cargada = cargar_configuracion_de_arranque(archivo)

    assert cargada.ruta_base_datos == ruta_hostil.ruta_db
    assert cargada.raiz_evidencia == ruta_hostil.raiz_evidencia
    assert " " in str(cargada.raiz_evidencia), "La prueba dejó de correr en ruta hostil."


def _raiz_de_evidencia_demasiado_larga() -> tuple[Path, int]:
    """Una raíz de más de 200 caracteres, y cuánto mide."""
    larga = Path("C:/") / ("directorio con nombre larguisimo " * 7)
    largo = len(str(larga))
    assert largo > 200, f"La ruta de la prueba mide {largo}: no ejercita el límite."
    return larga, largo


def test_una_raiz_de_evidencia_demasiado_larga_dice_el_maximo_y_el_largo_elegido(
    directorio_de_arranque: Path, ruta_hostil: RutaHostil
) -> None:
    """Pitfall 3: el error tiene que decir el número, no un `FileNotFoundError` a los meses.

    Se ejercita el camino real —cargar el archivo— y no sólo el validador suelto, porque
    lo que tiene que llegarle a quien está configurando el equipo es el mensaje con los
    dos números, no una `ValidationError` de la biblioteca.
    """
    larga, largo = _raiz_de_evidencia_demasiado_larga()
    archivo = directorio_de_arranque / NOMBRE_ARCHIVO_DE_ARRANQUE
    archivo.write_text(
        f"ruta_base_datos = '{ruta_hostil.ruta_db}'\nraiz_evidencia = '{larga}'\n",
        encoding="utf-8",
    )

    with pytest.raises(RaizDeEvidenciaDemasiadoLarga) as capturado:
        cargar_configuracion_de_arranque(archivo)

    mensaje = str(capturado.value)
    assert str(LARGO_MAXIMO_RAIZ_EVIDENCIA) in mensaje, (
        f"El mensaje no dice el máximo permitido:\n{mensaje}"
    )
    assert str(largo) in mensaje, (
        f"El mensaje no dice cuánto mide la ruta elegida:\n{mensaje}"
    )


def test_el_modelo_tampoco_acepta_una_raiz_demasiado_larga() -> None:
    """La validación no vive sólo en el cargador: el tipo tampoco puede sostener el valor."""
    larga, largo = _raiz_de_evidencia_demasiado_larga()

    with pytest.raises(ValidationError) as capturado:
        ConfiguracionDeArranque(
            ruta_base_datos=Path("C:/p/porteria.sqlite3"), raiz_evidencia=larga
        )

    mensaje = str(capturado.value)
    assert str(LARGO_MAXIMO_RAIZ_EVIDENCIA) in mensaje and str(largo) in mensaje, (
        f"Los dos números tienen que sobrevivir también acá:\n{mensaje}"
    )


def test_si_el_archivo_no_existe_dice_donde_lo_busco_y_que_hacer(
    directorio_de_arranque: Path,
) -> None:
    """La aplicación no inventa valores: informa y dice cómo salir del paso."""
    faltante = directorio_de_arranque / NOMBRE_ARCHIVO_DE_ARRANQUE

    with pytest.raises(ConfiguracionDeArranqueAusente) as capturado:
        cargar_configuracion_de_arranque(faltante)

    mensaje = str(capturado.value)
    assert str(faltante) in mensaje, f"El mensaje no dice dónde buscó:\n{mensaje}"
    assert "ruta_base_datos" in mensaje and "raiz_evidencia" in mensaje, (
        f"El mensaje no dice qué tiene que contener el archivo:\n{mensaje}"
    )


def test_la_ubicacion_por_defecto_lleva_el_identificador_tecnico() -> None:
    assert "porteria" in str(directorio_de_configuracion_por_defecto()).lower(), (
        "La ubicación por defecto no usa el identificador técnico de D-36."
    )


def test_la_ubicacion_se_puede_fijar_con_una_variable_de_entorno(
    directorio_de_arranque: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sin esta vía, las pruebas escribirían en la carpeta real del usuario."""
    monkeypatch.setenv(VARIABLE_DE_DIRECTORIO, str(directorio_de_arranque))

    assert ruta_del_archivo_de_arranque() == (
        directorio_de_arranque / NOMBRE_ARCHIVO_DE_ARRANQUE
    )


# --------------------------------------------------------------------------- #
# Capa 2: el catálogo que el plan 01-07 consume
# --------------------------------------------------------------------------- #


def test_el_catalogo_declara_exactamente_las_siete_claves() -> None:
    assert set(CATALOGO) == SIETE_CLAVES, (
        "El catálogo de la capa 2 cambió. El composition root del plan 01-07 lo recorre "
        "para inyectar valores y tiene una prueba que exige estas siete.\n"
        f"Sobran: {sorted(set(CATALOGO) - SIETE_CLAVES)}\n"
        f"Faltan: {sorted(SIETE_CLAVES - set(CATALOGO))}"
    )
    for nombre, declarada in CATALOGO.items():
        assert declarada.nombre == nombre
        assert isinstance(declarada.tipo, type), f"«{nombre}» no declara su tipo."
        assert isinstance(declarada.por_defecto, declarada.tipo), (
            f"El valor por defecto de «{nombre}» no es del tipo que la clave declara."
        )
        assert declarada.ayuda.strip(), f"«{nombre}» no tiene ayuda para el operador."


def test_la_ventana_por_defecto_es_150_y_esta_marcada_como_no_validada() -> None:
    """D-39: el número no está medido en campo, y eso se dice donde se lee el valor."""
    ventana = CATALOGO["ventana_aceptacion_ms"]

    assert ventana.por_defecto == 150
    assert ventana.tipo is int
    assert "no validado" in ventana.ayuda.lower(), (
        "La ayuda no marca el valor como no validado. Un número que nadie midió y que el "
        f"código presenta como un hecho es peor que no tener número. Ayuda: {ventana.ayuda}"
    )


def test_ninguna_clave_del_catalogo_es_una_credencial() -> None:
    """Las credenciales de sistemas externos viven en otra tabla (plan 01-10)."""
    culpables = [nombre for nombre in CATALOGO if CLAVES_SENSIBLES.search(nombre)]

    assert not culpables, (
        f"Las claves {culpables} del catálogo se parecen a credenciales. Esta orden no "
        "lee ni escribe credenciales: van en una tabla aparte."
    )


def test_leer_una_clave_no_escrita_devuelve_el_valor_por_defecto(
    configuracion: ConfiguracionEnBase,
) -> None:
    assert configuracion.leer("ventana_aceptacion_ms") == 150
    assert configuracion.leer("nivel_bitacora") == CATALOGO["nivel_bitacora"].por_defecto


def test_escribir_y_leer_devuelve_el_valor_nuevo(
    configuracion: ConfiguracionEnBase,
) -> None:
    configuracion.escribir("ventana_aceptacion_ms", 200, autor="admin")

    assert configuracion.leer("ventana_aceptacion_ms") == 200


def test_escribir_sin_autor_falla(configuracion: ConfiguracionEnBase) -> None:
    """T-01-22: el requisito de auditoría se aplica también a la configuración."""
    with pytest.raises(TypeError):
        configuracion.escribir("ventana_aceptacion_ms", 200)  # type: ignore[call-arg]

    with pytest.raises(AutorRequerido):
        configuracion.escribir("ventana_aceptacion_ms", 200, autor="   ")


def test_listar_devuelve_el_valor_con_quien_lo_cambio_y_cuando(
    configuracion: ConfiguracionEnBase,
) -> None:
    configuracion.escribir("ventana_aceptacion_ms", 200, autor="jefa de logistica")

    listado = configuracion.listar()
    ventana = listado["ventana_aceptacion_ms"]

    assert isinstance(ventana, ValorDeConfiguracion)
    assert ventana.valor == 200
    assert ventana.cambiado_por == "jefa de logistica"
    assert ventana.cambiado_en_utc_iso is not None
    assert ventana.cambiado_en_utc_iso.startswith("20"), (
        f"El instante no parece ISO-8601: {ventana.cambiado_en_utc_iso}"
    )
    assert set(listado) == SIETE_CLAVES, (
        "El listado tiene que mostrar las siete claves, no sólo las escritas: el operador "
        "necesita ver también lo que está en su valor por defecto."
    )
    sin_tocar = listado["nivel_bitacora"]
    assert sin_tocar.cambiado_por is None, (
        "Una clave que nadie cambió no puede reportar un autor: sería inventar un rastro."
    )


def test_el_ultimo_cambio_pisa_al_anterior_y_deja_su_propio_rastro(
    configuracion: ConfiguracionEnBase,
) -> None:
    configuracion.escribir("respaldos_bitacora", 3, autor="soporte")
    configuracion.escribir("respaldos_bitacora", 9, autor="administracion")

    valor = configuracion.listar()["respaldos_bitacora"]
    assert valor.valor == 9
    assert valor.cambiado_por == "administracion"


def test_una_clave_desconocida_falla_nombrando_las_que_existen(
    configuracion: ConfiguracionEnBase,
) -> None:
    with pytest.raises(ClaveDesconocida) as capturado:
        configuracion.leer("ventana_aceptacion")

    assert "ventana_aceptacion_ms" in str(capturado.value), (
        f"El error no sugiere las claves válidas:\n{capturado.value}"
    )


def test_un_valor_del_tipo_equivocado_no_se_persiste(
    configuracion: ConfiguracionEnBase,
) -> None:
    """Un `"doscientos"` guardado hoy es un fallo al arrancar dentro de seis meses."""
    with pytest.raises(ValueError):
        configuracion.escribir("ventana_aceptacion_ms", "doscientos", autor="admin")

    assert configuracion.leer("ventana_aceptacion_ms") == 150


def test_una_clave_de_tipo_compuesto_va_y_vuelve_intacta(
    configuracion: ConfiguracionEnBase,
) -> None:
    """D-01: la calidad del JPEG es un parámetro **por cámara**, no una constante."""
    por_camara = {"patente": 100, "lateral": 85}

    configuracion.escribir("calidad_jpeg_por_camara", por_camara, autor="admin")

    assert configuracion.leer("calidad_jpeg_por_camara") == por_camara


def test_la_clase_cumple_el_puerto_de_configuracion(
    configuracion: ConfiguracionEnBase,
) -> None:
    assert isinstance(configuracion, Configuracion)


# --------------------------------------------------------------------------- #
# La orden `configurar` (D-49, D-50, D-51)
# --------------------------------------------------------------------------- #


@pytest.fixture
def consola_configurada(
    directorio_de_arranque: Path,
    ruta_hostil: RutaHostil,
    motor_con_tabla: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Path]:
    """Deja la orden apuntando a un arranque y una base reales bajo la ruta hostil."""
    escribir_archivo_de_arranque(directorio_de_arranque, ruta_hostil)
    monkeypatch.setenv(VARIABLE_DE_DIRECTORIO, str(directorio_de_arranque))
    yield directorio_de_arranque


def test_configurar_listar_en_json_es_parseable(consola_configurada: Path) -> None:
    resultado = CliRunner().invoke(app, ["configurar", "--listar", "--json"])

    assert resultado.exit_code == 0, f"Salida:\n{resultado.output}"
    datos = json.loads(resultado.output)
    assert set(datos["claves"]) == SIETE_CLAVES


def test_configurar_listar_en_json_funciona_sin_archivo_de_arranque(
    directorio_de_arranque: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sin base todavía, el listado muestra los valores por defecto y dice de dónde salen.

    Fallar acá sería lo peor de los dos mundos: quien está instalando el producto no
    puede ver qué claves existen justo cuando más lo necesita.
    """
    monkeypatch.setenv(VARIABLE_DE_DIRECTORIO, str(directorio_de_arranque))

    resultado = CliRunner().invoke(app, ["configurar", "--listar", "--json"])

    assert resultado.exit_code == 0, f"Salida:\n{resultado.output}"
    datos = json.loads(resultado.output)
    assert set(datos["claves"]) == SIETE_CLAVES
    assert datos["origen"] == "catalogo"


def test_configurar_listar_legible_muestra_la_marca_de_no_validado(
    consola_configurada: Path,
) -> None:
    resultado = CliRunner().invoke(app, ["configurar", "--listar"])

    assert resultado.exit_code == 0, f"Salida:\n{resultado.output}"
    assert "ventana_aceptacion_ms" in resultado.output
    assert "no validado" in resultado.output.lower(), (
        "La salida legible no marca el valor como no validado (D-39):\n"
        f"{resultado.output}"
    )


def test_configurar_escribe_y_deja_el_rastro(
    consola_configurada: Path, motor_con_tabla: Engine
) -> None:
    resultado = CliRunner().invoke(
        app,
        [
            "configurar",
            "--clave",
            "ventana_aceptacion_ms",
            "--valor",
            "200",
            "--autor",
            "administracion",
        ],
    )

    assert resultado.exit_code == 0, f"Salida:\n{resultado.output}"

    persistida = ConfiguracionEnBase(motor_con_tabla, RelojDelProceso()).listar()
    ventana = persistida["ventana_aceptacion_ms"]
    assert ventana.valor == 200
    assert ventana.cambiado_por == "administracion"
    assert ventana.cambiado_en_utc_iso is not None


def test_configurar_sin_autor_no_muestra_un_traceback(consola_configurada: Path) -> None:
    """UI-05: en una planta sin área de sistemas, un traceback no le sirve a nadie."""
    resultado = CliRunner().invoke(
        app, ["configurar", "--clave", "ventana_aceptacion_ms", "--valor", "200"]
    )

    assert resultado.exit_code == 2, f"Salida:\n{resultado.output}"
    assert "Traceback" not in resultado.output, f"Salida:\n{resultado.output}"
    assert "--autor" in resultado.output, (
        f"La salida no dice qué falta para poder escribir:\n{resultado.output}"
    )


def test_configurar_con_una_clave_desconocida_dice_cuales_existen(
    consola_configurada: Path,
) -> None:
    resultado = CliRunner().invoke(
        app,
        ["configurar", "--clave", "ventana", "--valor", "200", "--autor", "admin"],
    )

    assert resultado.exit_code == 2, f"Salida:\n{resultado.output}"
    assert "Traceback" not in resultado.output
    assert "ventana_aceptacion_ms" in resultado.output, (
        f"La salida no enumera las claves válidas:\n{resultado.output}"
    )


def test_configurar_con_un_valor_del_tipo_equivocado_no_muestra_un_traceback(
    consola_configurada: Path,
) -> None:
    resultado = CliRunner().invoke(
        app,
        [
            "configurar",
            "--clave",
            "ventana_aceptacion_ms",
            "--valor",
            "doscientos",
            "--autor",
            "admin",
        ],
    )

    assert resultado.exit_code == 2, f"Salida:\n{resultado.output}"
    assert "Traceback" not in resultado.output
    assert "entero" in resultado.output.lower(), (
        f"La salida no dice qué tipo de valor se esperaba:\n{resultado.output}"
    )


def test_configurar_en_json_no_filtra_rutas_absolutas(
    consola_configurada: Path, ruta_hostil: RutaHostil
) -> None:
    """T-01-02: un volcado que se pega en un correo no revela el árbol del cliente."""
    resultado = CliRunner().invoke(app, ["configurar", "--listar", "--json"])

    assert resultado.exit_code == 0
    assert str(ruta_hostil.raiz) not in resultado.output, (
        f"La salida estructurada incluye la ruta absoluta del equipo:\n{resultado.output}"
    )
