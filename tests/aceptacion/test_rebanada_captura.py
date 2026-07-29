"""Prueba de aceptación de la rebanada de captura, escrita antes del código (D-56).

Describe el resultado observable completo que `SKELETON.md` § "Capacidad probada de
punta a punta" promete: una sola orden de consola sobre un archivo de video deja la
imagen en el almacén de evidencia con su huella SHA-256 verificable y su fila de
metadatos.

Está marcada `xfail(strict=True)` a propósito. Mientras la rebanada no exista, tiene que
estar en **rojo declarado**; y `strict=True` garantiza que si algún día pasara sin que
nadie le saque el marcador, la suite falla — que es la señal correcta, porque significa
que la rebanada se cerró sin que nadie lo notara. El plan 01-07 quita el marcador como
parte de su cierre.

Los planes 01-02 a 01-06 construyen las piezas; ninguno la hace pasar por sí solo.
"""

import hashlib
import re
from pathlib import Path

import pytest
from sqlalchemy import text
from typer.testing import CliRunner

from porteria.cli.app import app
from tests.conftest import RutaHostil

#: Nombre de archivo de evidencia: la huella SHA-256 del contenido, y nada más.
PATRON_NOMBRE = re.compile(r"^[0-9a-f]{64}\.jpg$")
PATRON_ANIO = re.compile(r"^\d{4}$")
PATRON_MES_O_DIA = re.compile(r"^\d{2}$")


def _huella_del_archivo(archivo: Path) -> str:
    """Recalcula la huella SHA-256 leyendo el archivo del disco."""
    with archivo.open("rb") as descriptor:
        return hashlib.file_digest(descriptor, "sha256").hexdigest()


@pytest.mark.xfail(reason="la rebanada cierra en el plan 01-07", strict=True)
def test_la_rebanada_de_captura_deja_evidencia_verificable(
    ruta_hostil: RutaHostil,
    video_sintetico: Path,
    motor_sqlite,
) -> None:
    corredor = CliRunner()

    # Los nombres de estas variables de entorno los confirma el plan 01-06, que trae la
    # configuración en dos capas. Esta prueba es el contrato que ese plan tiene que
    # satisfacer: la orden escribe donde la configuración dice, no donde el código
    # decidió.
    resultado = corredor.invoke(
        app,
        ["capturar", "--fuente", str(video_sintetico)],
        env={
            "PORTERIA_RAIZ_EVIDENCIA": str(ruta_hostil.raiz_evidencia),
            "PORTERIA_BASE_DE_DATOS": str(ruta_hostil.ruta_db),
        },
    )

    assert resultado.exit_code == 0, (
        "La orden `porteria capturar` no terminó bien.\n"
        f"Código de salida: {resultado.exit_code}\nSalida:\n{resultado.output}"
    )

    # --- 1. El archivo de evidencia, uno solo, en su carpeta por fecha ------------- #
    archivos = sorted(ruta_hostil.raiz_evidencia.rglob("*.jpg"))

    assert len(archivos) == 1, (
        f"Se esperaba exactamente 1 archivo de evidencia bajo "
        f"«{ruta_hostil.raiz_evidencia}» y hay {len(archivos)}: "
        f"{[str(a) for a in archivos]}"
    )
    archivo = archivos[0]

    partes = archivo.relative_to(ruta_hostil.raiz_evidencia).parts
    assert len(partes) == 4, (
        "La evidencia tiene que vivir en AAAA/MM/DD/<archivo> para que el directorio "
        f"no acumule cientos de miles de archivos. Ruta obtenida: {'/'.join(partes)}"
    )
    assert PATRON_ANIO.match(partes[0]), f"El año no tiene cuatro dígitos: {partes[0]!r}"
    assert PATRON_MES_O_DIA.match(partes[1]), f"El mes no tiene dos dígitos: {partes[1]!r}"
    assert PATRON_MES_O_DIA.match(partes[2]), f"El día no tiene dos dígitos: {partes[2]!r}"

    # --- 2. El nombre del archivo ES la huella del contenido ----------------------- #
    assert PATRON_NOMBRE.match(archivo.name), (
        "El nombre del archivo tiene que ser 64 caracteres hexadecimales más `.jpg` "
        f"—la huella SHA-256 del contenido—, y es {archivo.name!r}."
    )

    huella_recalculada = _huella_del_archivo(archivo)
    assert huella_recalculada == archivo.stem, (
        "Recalcular la huella SHA-256 del archivo no reproduce su nombre: la evidencia "
        "no es verificable.\n"
        f"Nombre:      {archivo.stem}\nRecalculada: {huella_recalculada}"
    )

    # --- 3. Una fila de metadatos, coherente con el archivo ------------------------ #
    with motor_sqlite.connect() as conexion:
        filas = conexion.execute(
            text("select ruta_relativa, sha256 from item_evidencia")
        ).all()

    assert len(filas) == 1, (
        f"Se esperaba exactamente 1 fila en `item_evidencia` y hay {len(filas)}."
    )
    ruta_relativa, sha256_persistido = filas[0]

    assert not Path(ruta_relativa).is_absolute(), (
        "`ruta_relativa` es absoluta. Guardarla relativa es lo que permite mover el "
        f"almacén de evidencia a otro disco sin migrar la base. Valor: {ruta_relativa!r}"
    )
    assert "\\" not in ruta_relativa, (
        "`ruta_relativa` usa la barra invertida de Windows. El separador persistido es "
        f"`/`, para que la base sea legible en cualquier plataforma. Valor: {ruta_relativa!r}"
    )
    assert "/" in ruta_relativa, (
        "`ruta_relativa` no tiene separadores: debería incluir el camino AAAA/MM/DD. "
        f"Valor: {ruta_relativa!r}"
    )
    assert (ruta_hostil.raiz_evidencia / ruta_relativa).is_file(), (
        f"`ruta_relativa` no apunta a un archivo existente: {ruta_relativa!r} bajo "
        f"«{ruta_hostil.raiz_evidencia}»."
    )
    assert sha256_persistido == huella_recalculada, (
        "La huella persistida no coincide con la del archivo en disco.\n"
        f"Persistida:  {sha256_persistido}\nRecalculada: {huella_recalculada}"
    )
