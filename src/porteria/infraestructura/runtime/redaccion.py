"""Redacción de secretos: el último eslabón antes de que un evento llegue a un destino.

Es el control (b) de la mitigación de T-01-04. La amenaza no es hipotética ni exótica: la
bitácora técnica se comprime y se manda por correo a soporte, y los cassettes de los
sistemas externos se versionan en git. Una contraseña de la base de PALJET o una cabecera
`Authorization: Basic …` que entre por cualquiera de esos dos caminos es un incidente que
**no se deshace**, porque el correo ya salió y el historial de git no se borra.

**Por qué el procesador y no un filtro en cada punto de emisión.** Un filtro por punto de
emisión se aplica donde alguien se acordó de aplicarlo. Este corre en la cadena compartida
de `structlog`, antes de que el evento llegue a ningún handler, así que un destino nuevo
—otro archivo, la consola, un panel de estado— hereda la protección sin hacer nada. Que
sea así está verificado de extremo a extremo: hay una prueba que emite una credencial y
exige que no aparezca en **ninguna** línea del archivo.

**Tres decisiones que vale la pena justificar:**

1. **La coincidencia es por subcadena y sin acentos ni mayúsculas.** Los nombres de clave
   los eligen los sistemas ajenos, no este proyecto: PALJET puede mandar `Password`,
   `API_KEY` o `contraseña`, y `hash_credencial` es un nombre nuestro que igual tiene que
   caer. Es deliberadamente amplio: redactar de más cuesta un dato de diagnóstico,
   redactar de menos cuesta un incidente.
2. **La recursión es obligatoria.** Un diccionario dentro de una lista dentro de otro
   diccionario es exactamente la forma de un payload real; redactar sólo el primer nivel
   dejaría el valor en claro justo donde los sistemas externos lo ponen. El tope de
   profundidad existe para que una estructura cíclica no cuelgue la emisión, y más allá
   del tope se redacta **entero**: no poder inspeccionar no es motivo para filtrar.
3. **La redacción de URL es parcial.** Un mensaje de soporte que dice
   `GET https://erp/api/remitos?desde=2026-01-01&token=«redactado»` sirve para diagnosticar;
   uno que dice `«redactado»` no sirve para nada, y una herramienta que no sirve es una
   herramienta que alguien apaga.

El plan 01-10 reutiliza este mismo módulo para el anonimizador de cassettes —incluidas las
cabeceras, que el esquema persiste comprimidas—, de modo que la lista de claves sensibles
sea **una sola** en todo el producto. Dos listas divergen; y la que divergiría es siempre
la que nadie mira.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

__all__ = [
    "CLAVES_SENSIBLES",
    "PATRON_EN_URL",
    "PROFUNDIDAD_MAXIMA",
    "REDACTADO",
    "redactar",
]

#: Lo que se emite en lugar del valor. Las comillas angulares lo hacen inconfundible con
#: un valor real y sobreviven al archivo porque se abre en UTF-8 (Pitfall 8).
REDACTADO = "«redactado»"

#: Nombres de clave que delatan una credencial. Se comparan **sin acentos y sin distinguir
#: mayúsculas**, y por subcadena: `hash_credencial`, `db_password` y `X-Api-Key` tienen que
#: caer igual que `token`.
CLAVES_SENSIBLES = re.compile(
    r"contrasena|password|token|secret|secreto|clave|apikey|api_key|authorization"
    r"|credencial",
    re.IGNORECASE,
)

#: Un secreto también viaja dentro de una URL, y ahí no hay clave que inspeccionar. Se
#: reemplaza sólo el valor del parámetro, conservando el resto de la consulta.
PATRON_EN_URL = re.compile(
    r"([?&](token|apikey|api_key|clave|password)=)([^&\s]+)",
    re.IGNORECASE,
)

#: Tope de anidamiento. Existe para que una estructura cíclica no cuelgue la emisión de un
#: evento; más allá del tope se redacta entero.
PROFUNDIDAD_MAXIMA = 10


def _sin_acentos(texto: str) -> str:
    """Devuelve el texto sin marcas diacríticas: `contraseña` se compara como `contrasena`."""
    descompuesto = unicodedata.normalize("NFD", texto)
    return "".join(letra for letra in descompuesto if not unicodedata.combining(letra))


def _es_sensible(clave: Any) -> bool:
    """Decide si el **nombre** de una clave delata que su valor es una credencial."""
    return CLAVES_SENSIBLES.search(_sin_acentos(str(clave))) is not None


def _redactar_texto(valor: str) -> str:
    """Reemplaza el valor de los parámetros sensibles de una URL, y nada más."""
    return PATRON_EN_URL.sub(lambda encontrado: encontrado.group(1) + REDACTADO, valor)


def _redactar_valor(valor: Any, profundidad: int) -> Any:
    """Recorre la estructura devolviendo una copia redactada. Nunca muta la original."""
    if profundidad > PROFUNDIDAD_MAXIMA:
        # Ante la duda, redactar: que la estructura sea demasiado honda o cíclica no es
        # una razón para dejar pasar en claro lo que haya adentro.
        return REDACTADO

    if isinstance(valor, dict):
        return {
            clave: (
                REDACTADO
                if _es_sensible(clave)
                else _redactar_valor(anidado, profundidad + 1)
            )
            for clave, anidado in valor.items()
        }

    if isinstance(valor, (list, tuple, set, frozenset)):
        redactados = [_redactar_valor(elemento, profundidad + 1) for elemento in valor]
        return type(valor)(redactados) if not isinstance(valor, list) else redactados

    if isinstance(valor, str):
        return _redactar_texto(valor)

    return valor


def redactar(
    logger: Any, nombre_metodo: str, evento: dict[str, Any]
) -> dict[str, Any]:
    """Procesador de `structlog`: devuelve el evento con toda credencial reemplazada.

    La firma —`(logger, nombre_metodo, evento)`— es la que `structlog` le pasa a cada
    eslabón de la cadena. Los dos primeros argumentos no se usan y se aceptan igual, que
    es lo que permite enchufarlo sin envoltorios.

    Devuelve una estructura **nueva**: mutar la que le pasó el llamador rompería al que
    esté usando ese mismo diccionario para otra cosa.
    """
    return _redactar_valor(evento, 0)
