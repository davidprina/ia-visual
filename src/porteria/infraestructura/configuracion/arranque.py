"""Capa 1 de D-30: el archivo mínimo con lo imprescindible para abrir.

**Dos campos, y ninguno más: ruta de la base y raíz de evidencia.** Que sean sólo dos no
es minimalismo estético, es el control (a) de la mitigación de T-01-04. Un archivo de
arranque en texto plano con la contraseña de la base de PALJET es exactamente el incidente
que hay que hacer imposible por diseño, y la forma de hacerlo imposible es que el archivo
**no tenga dónde ponerla**: las credenciales de sistemas externos viven en la base, en una
tabla aparte (plan 01-10). Hay una prueba que recorre `model_fields` y falla si alguna
clave nueva coincide con el patrón de claves sensibles del módulo de redacción.

**Dos raíces independientes** (D-06): la base va en disco local rápido y la evidencia en
la ruta o el disco que el cliente elija. No se derivan una de la otra ni comparten padre.

**El largo de la raíz de evidencia se valida al configurarla** (Pitfall 3). `MAX_PATH` de
260 caracteres está activo en muchas instalaciones de Windows y el sufijo
`AAAA/MM/DD/<64hex>.jpg` ya mide 89, así que la raíz no puede pasar de 170. Validarlo
ahora, con un mensaje que dice **el máximo y el largo elegido**, evita el
`FileNotFoundError` que aparecería a los tres meses sin decir una palabra sobre el largo
de la ruta.

**La ubicación por defecto la resuelve `platformdirs`** bajo el identificador técnico
`porteria` (D-36), no un `%APPDATA%` cableado: es lo que hace que Linux y macOS funcionen
cuando lleguen, sin un `if sys.platform`. *(Riesgo asumido de D-36: si el nombre comercial
cambia antes de la Fase 11, la carpeta de datos hay que renombrarla en instalaciones ya
desplegadas.)* La ubicación se puede fijar con una variable de entorno, que es lo que
permite que las pruebas y una instalación portable no escriban en la carpeta real del
usuario.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

import platformdirs
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = [
    "LARGO_MAXIMO_RAIZ_EVIDENCIA",
    "NOMBRE_ARCHIVO_DE_ARRANQUE",
    "VARIABLE_DE_DIRECTORIO",
    "ArchivoDeArranqueIlegible",
    "ConfiguracionDeArranque",
    "ConfiguracionDeArranqueAusente",
    "RaizDeEvidenciaDemasiadoLarga",
    "cargar_configuracion_de_arranque",
    "directorio_de_configuracion_por_defecto",
    "ruta_del_archivo_de_arranque",
    "validar_largo_de_raiz_evidencia",
]

#: Identificador técnico neutro de D-36, el mismo que usa la bitácora.
IDENTIFICADOR_TECNICO = "porteria"

#: Nombre del archivo de la capa 1. TOML porque lo escribe el instalador y lo puede leer
#: y corregir una persona sin herramientas.
NOMBRE_ARCHIVO_DE_ARRANQUE = "porteria.toml"

#: Variable de entorno que fija el directorio donde se busca el archivo. Es la vía por la
#: que las pruebas —y una instalación portable— evitan escribir en la carpeta real.
VARIABLE_DE_DIRECTORIO = "PORTERIA_DIRECTORIO_CONFIGURACION"

#: Pitfall 3: `MAX_PATH` de 260 está activo y el sufijo `AAAA/MM/DD/<64hex>.jpg` mide 89.
LARGO_MAXIMO_RAIZ_EVIDENCIA = 170

#: Ejemplo que se imprime cuando el archivo no está. Decir «falta el archivo» sin decir
#: qué va adentro deja a quien instala exactamente igual de trabado que antes (UI-05).
EJEMPLO_DE_ARCHIVO = (
    "ruta_base_datos = 'C:\\porteria\\datos\\porteria.sqlite3'\n"
    "raiz_evidencia = 'D:\\porteria\\evidencia'"
)


class ConfiguracionDeArranqueAusente(FileNotFoundError):
    """No hay archivo de arranque. La aplicación no inventa valores: informa."""


class ArchivoDeArranqueIlegible(ValueError):
    """El archivo existe pero no es TOML válido. Su contenido es entrada no confiable."""


class RaizDeEvidenciaDemasiadoLarga(ValueError):
    """La raíz elegida no entra en `MAX_PATH` con el sufijo de la evidencia."""


def directorio_de_configuracion_por_defecto() -> Path:
    """Dónde vive `porteria.toml` si nadie fijó otra ubicación."""
    return Path(platformdirs.user_config_dir(IDENTIFICADOR_TECNICO, appauthor=False))


def ruta_del_archivo_de_arranque(directorio: Path | str | None = None) -> Path:
    """Resuelve la ruta del archivo: argumento, variable de entorno o valor por defecto."""
    if directorio is not None:
        return Path(directorio) / NOMBRE_ARCHIVO_DE_ARRANQUE

    desde_entorno = os.environ.get(VARIABLE_DE_DIRECTORIO)
    if desde_entorno:
        return Path(desde_entorno) / NOMBRE_ARCHIVO_DE_ARRANQUE

    return directorio_de_configuracion_por_defecto() / NOMBRE_ARCHIVO_DE_ARRANQUE


def validar_largo_de_raiz_evidencia(raiz: Path | str) -> Path:
    """Devuelve la raíz si entra en `MAX_PATH`; si no, explica con los dos números.

    Se extrae como función propia para poder llamarla desde el cargador —donde el error
    tiene que llegarle limpio a quien está configurando el equipo— y desde el validador
    del modelo, sin duplicar ni el número ni el mensaje.
    """
    ruta = Path(raiz)
    largo = len(str(ruta))
    if largo > LARGO_MAXIMO_RAIZ_EVIDENCIA:
        raise RaizDeEvidenciaDemasiadoLarga(
            f"La raíz de evidencia no puede superar los {LARGO_MAXIMO_RAIZ_EVIDENCIA} "
            f"caracteres y la elegida tiene {largo}. Windows tiene el límite MAX_PATH de "
            "260 caracteres activo en la mayoría de las instalaciones, y el sistema le "
            "agrega a esta raíz un sufijo AAAA/MM/DD/<64 caracteres>.jpg que ya mide 89. "
            "Qué hacer: elegí una raíz más corta, por ejemplo D:\\porteria\\evidencia.\n"
            f"Raíz elegida: {ruta}"
        )
    return ruta


class ConfiguracionDeArranque(BaseSettings):
    """Los dos únicos parámetros que D-30 permite en la capa 1.

    Agregar un tercero tiene que ser un cambio deliberado y discutido: hay una prueba que
    afirma que son exactamente dos y otra que afirma que ninguno se parece a una
    credencial.

    Ninguno tiene valor por defecto a propósito. Una ruta inventada hace que la aplicación
    abra apuntando a cualquier lado —creando una base vacía donde no va— en vez de decir
    que le falta configuración, que es lo único útil en ese momento.
    """

    model_config = SettingsConfigDict(
        # Prefijo propio y específico: no puede chocar con otras variables `PORTERIA_*`
        # del entorno, como la que fija la base de las pruebas.
        env_prefix="PORTERIA_ARRANQUE_",
        extra="forbid",
    )

    ruta_base_datos: Path
    raiz_evidencia: Path

    @field_validator("raiz_evidencia")
    @classmethod
    def _validar_raiz_evidencia(cls, valor: Path) -> Path:
        return validar_largo_de_raiz_evidencia(valor)


def cargar_configuracion_de_arranque(
    ruta: Path | str | None = None,
) -> ConfiguracionDeArranque:
    """Lee el archivo de la capa 1 y devuelve la configuración ya validada.

    Args:
        ruta: Ruta del archivo. Si es `None`, se resuelve con `ruta_del_archivo_de_arranque`.

    Raises:
        ConfiguracionDeArranqueAusente: si el archivo no existe. El mensaje dice dónde lo
            buscó y qué tiene que contener.
        ArchivoDeArranqueIlegible: si existe pero no es TOML válido.
        RaizDeEvidenciaDemasiadoLarga: si la raíz de evidencia no entra en `MAX_PATH`.

    El largo de la raíz se valida **antes** de construir el modelo para que el error que
    llegue a la consola sea el mensaje con los dos números y no una `ValidationError` de
    la biblioteca, que en una planta sin área de sistemas no le dice nada a nadie.
    """
    archivo = Path(ruta) if ruta is not None else ruta_del_archivo_de_arranque()

    if not archivo.is_file():
        raise ConfiguracionDeArranqueAusente(
            f"No se encontró el archivo de configuración de arranque en «{archivo}».\n"
            "La aplicación no inventa rutas: sin este archivo no sabe dónde está la base "
            "ni dónde guardar la evidencia.\n"
            "Qué hacer: corré el asistente de primer arranque (`porteria primer-arranque`) "
            "o creá el archivo a mano con estas dos claves y nada más:\n"
            f"{EJEMPLO_DE_ARCHIVO}"
        )

    try:
        datos = tomllib.loads(archivo.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        raise ArchivoDeArranqueIlegible(
            f"El archivo «{archivo}» existe pero no se pudo interpretar: {error}\n"
            "Qué revisar: que sea TOML válido, que esté guardado en UTF-8 y que las rutas "
            "de Windows vayan entre comillas simples para que las barras invertidas no se "
            "interpreten como escapes. Ejemplo:\n"
            f"{EJEMPLO_DE_ARCHIVO}"
        ) from error

    if "raiz_evidencia" in datos:
        validar_largo_de_raiz_evidencia(str(datos["raiz_evidencia"]))

    return ConfiguracionDeArranque(**datos)
