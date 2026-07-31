r"""Almacén de evidencia en disco: escritura atómica **en el idioma de Windows**.

El patrón POSIX canónico de escritura durable —escribir a un temporal, sincronizar el
archivo, renombrar, sincronizar el directorio padre— tiene dos pasos que en la plataforma
de destino no funcionan, y los dos fallan de forma ruidosa recién en el equipo del cliente.
Medido en esta máquina (Windows 11, Python 3.12):

| Operación | Resultado |
|---|---|
| `os.fsync` sobre un descriptor de **directorio** | `PermissionError` (errno 13) |
| `os.rename` sobre un archivo que ya existe | `FileExistsError` (errno 17, WinError 183) |
| `os.replace` sobre un archivo que ya existe | OK, el destino queda con el contenido nuevo |

El segundo es el que más engaña: falla justo en el único caso que importa —reescribir
evidencia que ya tiene el mismo hash—, así que un desarrollo hecho sobre Linux pasa todas
las pruebas y revienta en la portería el día que dos capturas dan bytes idénticos.

**El límite honesto de `os.replace`.** En Windows se implementa con
`MoveFileEx(MOVEFILE_REPLACE_EXISTING)`, que no está garantizado como atómico en todos los
casos: bajo ciertas circunstancias puede caer a una copia no atómica. Es lo mejor
disponible sin bajar a `NtSetInformationFile`, y el orden archivo-primero de D-12 lo cubre
igual — si el renombrado queda a medias lo que aparece es un archivo huérfano o un temporal
colgado, **nunca una fila apuntando a nada**. Un archivo huérfano es basura recuperable;
una fila huérfana es evidencia rota.

**Sobre el `fsync` del directorio.** El paso va guardado tras `if os.name != "nt"` en vez
de envuelto en un `try/except` silencioso, y eso es deliberado: un `except OSError: pass`
oculta el problema en lugar de documentarlo, y el día que la aplicación corra sobre Linux
—donde el paso sí hace falta— nadie sabría si se está ejecutando. Hay una invariante de
código que verifica las dos cosas. En NTFS la durabilidad del renombrado se apoya en el
journal del sistema de archivos.

**Sobre el largo de la ruta (Pitfall 3, T-01-17).** `MAX_PATH` de 260 caracteres está
activo en la mayoría de las instalaciones. El sufijo que este módulo agrega —
`AAAA/MM/DD/<64 hexadecimales>.jpg`— mide **79 caracteres medidos**; el tope de 170 que
valida la capa de configuración deja además margen para el componente `evidencia/` de la
organización canónica de D-03. Como cinturón adicional, las operaciones de archivo usan el
prefijo extendido `\\?\`, que verificado funciona hasta 400 caracteres. Para el despliegue
de la Fase 11 queda anotado `LongPathsEnabled` como requisito recomendado del equipo.

**El SHA-256 se calcula acá y en la ingesta, no en el dominio y no después.** El dominio
recibe una `HuellaDeIntegridad` ya construida. Para la verificación se usa
`hashlib.file_digest` de la biblioteca estándar y no un bucle de lectura propio: el
resultado es idéntico y no hay forma de equivocarse con el tamaño del bloque.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import tempfile
from pathlib import Path, PureWindowsPath
from typing import Final

from porteria.aplicacion.puertos.salida.almacen_de_evidencia import RutaFueraDeLaRaiz
from porteria.dominio.comun.tiempo import FechaLocal
from porteria.dominio.evidencia.estados import EstadoDeIntegridad, evaluar
from porteria.dominio.evidencia.huella import HuellaDeIntegridad
from porteria.infraestructura.configuracion.arranque import (
    RaizDeEvidenciaDemasiadoLarga,
    validar_largo_de_raiz_evidencia,
)

__all__ = [
    "EXTENSION_DE_EVIDENCIA",
    "PREFIJO_TEMPORAL",
    "SUFIJO_TEMPORAL",
    "AlmacenDeEvidenciaEnDisco",
    "RaizDemasiadoLarga",
    "RutaFueraDeLaRaiz",
    "guardar_atomico",
    "ruta_absoluta",
    "ruta_para_el_sistema",
    "verificar",
]

#: Alias del error que ya declara la capa de configuración. Se **reutiliza** en vez de
#: declarar uno propio para que el tope y el mensaje con los dos números existan una sola
#: vez: dos validaciones del mismo límite terminan divergiendo, y la que quede corta deja
#: pasar rutas que después fallan con un `FileNotFoundError` mudo en la planta.
RaizDemasiadoLarga = RaizDeEvidenciaDemasiadoLarga

#: D-03: la evidencia se guarda con la extensión del formato con pérdida por defecto.
EXTENSION_DE_EVIDENCIA: Final = ".jpg"

#: El temporal se reconoce por su forma: la cuarentena de huérfanos lo busca así.
PREFIJO_TEMPORAL: Final = ".tmp_"
SUFIJO_TEMPORAL: Final = ".part"

#: Prefijo de ruta extendida de Windows. Cuatro caracteres: barra, barra, signo, barra.
_PREFIJO_LARGO: Final = "\\\\?\\"


def ruta_para_el_sistema(ruta: Path | str) -> str:
    r"""Devuelve la ruta lista para la llamada al sistema, con prefijo extendido si aplica.

    Es público —y no un ayudante privado— porque la cuarentena necesita exactamente lo
    mismo: su sufijo `cuarentena/AAAA-MM-DD/<64 hexadecimales>.jpg` mide 90 caracteres,
    once más que el de la evidencia, así que es el que primero se pasaría de `MAX_PATH`.

    Fuera de Windows devuelve el texto tal cual. En Windows antepone `\\?\` —o `\\?\UNC\`
    para un recurso de red—, que es lo que saltea el límite de 260 caracteres. El prefijo
    exige una ruta ya absoluta y normalizada, y por eso todas las rutas de este módulo
    pasan antes por `resolve()`.
    """
    texto = str(ruta)
    if os.name != "nt" or texto.startswith(_PREFIJO_LARGO):
        return texto
    if texto.startswith("\\\\"):
        return _PREFIJO_LARGO + "UNC\\" + texto[2:]
    if len(texto) > 1 and texto[1] == ":":
        return _PREFIJO_LARGO + texto
    return texto


def _exigir_relativa_sin_escape(ruta_relativa: str) -> None:
    """Rechaza una ruta persistida que sea absoluta o que contenga `..` (T-01-02).

    Se interpreta con `PureWindowsPath` **en las dos plataformas** a propósito: es la
    gramática más amplia de las dos —entiende la letra de unidad, el recurso UNC y las dos
    barras—, así que una base copiada de un equipo Windows a uno Linux se sigue validando
    con el mismo criterio con el que se escribió.
    """
    if not ruta_relativa or not ruta_relativa.strip():
        raise RutaFueraDeLaRaiz(
            "La ruta de evidencia está vacía. Se esperaba una ruta relativa a la raíz, "
            "con la forma AAAA/MM/DD/<64 hexadecimales>.jpg."
        )

    interpretada = PureWindowsPath(ruta_relativa)

    if interpretada.is_absolute() or interpretada.drive or interpretada.root:
        raise RutaFueraDeLaRaiz(
            f"«{ruta_relativa}» es una ruta absoluta y la evidencia se persiste siempre "
            "relativa a la raíz configurada (D-06). Una ruta absoluta en la base impide "
            "mover la evidencia a otro disco y, peor, permitiría leer o escribir fuera de "
            "la raíz.\n"
            "Qué revisar: la columna `ruta_relativa` de la fila que se está usando."
        )

    if ".." in interpretada.parts:
        raise RutaFueraDeLaRaiz(
            f"«{ruta_relativa}» sale de la raíz de evidencia con «..», y la evidencia "
            "nunca vive fuera de su raíz. Una ruta así sólo puede venir de una fila "
            "alterada a mano o de una importación mal hecha.\n"
            "Qué revisar: la columna `ruta_relativa` de la fila que se está usando."
        )


def ruta_absoluta(raiz: Path | str, ruta_relativa: str) -> Path:
    """Compone la ruta absoluta y comprueba que caiga **dentro** de la raíz.

    La comprobación final con `is_relative_to` sobre las dos rutas ya resueltas es la que
    ataja lo que la inspección del texto no ve: un enlace simbólico o una unión de
    directorio que apunte afuera.

    Raises:
        RutaFueraDeLaRaiz: si la ruta es absoluta, contiene `..` o resuelve fuera.
    """
    _exigir_relativa_sin_escape(ruta_relativa)

    raiz_resuelta = Path(raiz).resolve()
    destino = Path(os.path.normpath(raiz_resuelta / ruta_relativa))

    if not destino.is_relative_to(raiz_resuelta):
        raise RutaFueraDeLaRaiz(
            f"«{ruta_relativa}» resuelve fuera de la raíz de evidencia y no se va a "
            f"tocar.\nRaíz: {raiz_resuelta}\nResolvió en: {destino}"
        )

    return destino


def _partes_de_la_fecha(fecha_local: FechaLocal | dt.date) -> tuple[str, str, str]:
    """Devuelve `(AAAA, MM, DD)` de la fecha **local** del equipo (D-03 y D-37)."""
    if isinstance(fecha_local, FechaLocal):
        anio, mes, dia = fecha_local.texto.split("-")
        return anio, mes, dia
    return f"{fecha_local.year:04d}", f"{fecha_local.month:02d}", f"{fecha_local.day:02d}"


def guardar_atomico(
    contenido: bytes, raiz: Path | str, fecha_local: FechaLocal | dt.date
) -> tuple[HuellaDeIntegridad, str]:
    """Persiste los bytes y devuelve `(huella, ruta_relativa)`. Nunca deja nada a medias.

    El orden es el de D-12 y no admite atajos: hash del contenido, temporal en el **mismo
    directorio de destino** —`os.replace` sólo puede ser atómico dentro del mismo
    volumen—, escritura, `flush`, `fsync` del archivo, y recién entonces el renombrado.

    Si el destino ya existe se devuelve la huella y la ruta **sin reescribir**: el almacén
    está direccionado por contenido y ese es el camino feliz del reintento, no un error.

    Raises:
        RutaFueraDeLaRaiz: si la fecha recibida compusiera una ruta fuera de la raíz.
    """
    huella = HuellaDeIntegridad(hashlib.sha256(contenido).hexdigest())
    anio, mes, dia = _partes_de_la_fecha(fecha_local)
    relativa = f"{anio}/{mes}/{dia}/{huella}{EXTENSION_DE_EVIDENCIA}"

    destino = ruta_absoluta(raiz, relativa)
    destino_dir = destino.parent

    if os.path.exists(ruta_para_el_sistema(destino)):
        return huella, relativa

    os.makedirs(ruta_para_el_sistema(destino_dir), exist_ok=True)

    descriptor, temporal = tempfile.mkstemp(
        dir=ruta_para_el_sistema(destino_dir),
        prefix=PREFIJO_TEMPORAL,
        suffix=SUFIJO_TEMPORAL,
    )
    try:
        with os.fdopen(descriptor, "wb") as archivo:
            archivo.write(contenido)
            archivo.flush()
            os.fsync(archivo.fileno())

        if os.name != "nt":
            # El `fsync` del directorio padre es el idioma POSIX de la escritura durable.
            # En Windows es imposible: sobre un descriptor de directorio lanza
            # PermissionError(13), reproducido en esta máquina.
            descriptor_dir = os.open(destino_dir, os.O_RDONLY)
            try:
                os.fsync(descriptor_dir)
            finally:
                os.close(descriptor_dir)

        os.replace(temporal, ruta_para_el_sistema(destino))
    except BaseException:
        # Sin esta limpieza, cada escritura fallida deja un temporal, y un disco lleno
        # los acumula hasta llenar lo poco que quedaba libre (T-01-08). Se re-lanza
        # siempre: quien llamó tiene que enterarse de que la evidencia no se guardó.
        Path(temporal).unlink(missing_ok=True)
        raise

    return huella, relativa


def verificar(
    raiz: Path | str, ruta_relativa: str, huella: HuellaDeIntegridad
) -> EstadoDeIntegridad:
    """Recalcula la huella del archivo y devuelve `INTEGRA` o `COMPROMETIDA` (EVI-05).

    No borra, no mueve y no oculta nada (D-09). El recálculo usa `hashlib.file_digest`, que
    lee por bloques: la evidencia puede ser grande y no tiene por qué entrar en memoria.

    Raises:
        RutaFueraDeLaRaiz: si la ruta relativa intenta salir de la raíz.
        FileNotFoundError: si el archivo no está.
    """
    destino = ruta_absoluta(raiz, ruta_relativa)

    if not os.path.isfile(ruta_para_el_sistema(destino)):
        raise FileNotFoundError(
            f"No hay archivo de evidencia en «{ruta_relativa}».\n"
            f"Se lo buscó en: {destino}\n"
            "Un archivo ausente no es evidencia comprometida: es una purga con lápida "
            "(D-10), una fila huérfana o una raíz de evidencia que no está montada. "
            "Confundirlos escondería el problema real detrás del otro."
        )

    with open(ruta_para_el_sistema(destino), "rb") as archivo:
        recalculada = HuellaDeIntegridad(hashlib.file_digest(archivo, "sha256").hexdigest())

    return evaluar(huella, recalculada)


class AlmacenDeEvidenciaEnDisco:
    """Implementación del puerto `AlmacenDeEvidencia` sobre el sistema de archivos local.

    La raíz se valida **una sola vez, al construir**, y no en cada escritura: el momento
    útil para decir «esta ruta no entra en MAX_PATH» es cuando alguien la está eligiendo,
    no tres meses después con el disco lleno de evidencia y una captura a medio guardar.

    La clase guarda estado —la raíz ya resuelta— y delega en las funciones de módulo, que
    son las que hacen el trabajo. Esa separación no es ceremonia: las funciones se pueden
    ejercitar con una raíz cualquiera desde una prueba o desde una herramienta de soporte,
    sin construir el objeto.
    """

    __slots__ = ("_raiz",)

    def __init__(self, raiz: Path | str) -> None:
        """Valida el largo de la raíz. **No** la crea: eso es del primer arranque.

        Raises:
            RaizDemasiadoLarga: con el máximo y el largo elegido, los dos números (UI-05).
        """
        resuelta = Path(raiz).resolve()
        validar_largo_de_raiz_evidencia(resuelta)
        self._raiz = resuelta

    @property
    def raiz(self) -> Path:
        """La raíz ya resuelta. Sólo lectura: cambiarla en caliente rompería las rutas."""
        return self._raiz

    def guardar(
        self, contenido: bytes, fecha_local: FechaLocal
    ) -> tuple[HuellaDeIntegridad, str]:
        return guardar_atomico(contenido, self._raiz, fecha_local)

    def verificar(self, ruta_relativa: str, huella: HuellaDeIntegridad) -> EstadoDeIntegridad:
        return verificar(self._raiz, ruta_relativa, huella)

    def ruta_absoluta(self, ruta_relativa: str) -> Path:
        return ruta_absoluta(self._raiz, ruta_relativa)

    def esta_disponible(self) -> bool:
        """D-07: dice si la raíz está y se puede escribir en ella. Nunca levanta.

        Se responde con `os.access` en vez de escribiendo un archivo de sonda porque este
        método lo consulta el estado del sistema, que puede refrescarse seguido: dejar
        basura en la raíz de evidencia cada vez que alguien mira el panel sería peor que
        el dato que devuelve.
        """
        ruta = ruta_para_el_sistema(self._raiz)
        return os.path.isdir(ruta) and os.access(ruta, os.W_OK)
