"""`Manifiesto`: el segundo nivel de integridad de D-08, con su receta fijada.

D-08 construye la integridad en tres niveles: la huella por imagen, **el hash del
manifiesto por captura** y la bitácora encadenada. El nivel de acá es el que detecta lo
que la huella por imagen no puede ver: que a una captura le **falte** una foto, que le
hayan **agregado** una, o que le hayan cambiado los metadatos de una sin tocar el archivo.

Qué campos entran en el hash y en qué orden — **contrato, no recomendación**
-----------------------------------------------------------------------------
D-08 deja el detalle a criterio técnico, pero una vez elegido queda fijado con la primera
captura persistida y no se retrofitea: cambiarlo invalidaría el hash de toda la evidencia
anterior. El orden es:

1. `captura_id`
2. `incertidumbre_sello_utc_ms`
3. los ítems **ordenados por `camara_id` y después por `instante_monotono_ns`**, y de cada
   ítem `sha256`, `ruta_relativa`, `camara_id`, `instante_monotono_ns` y `desvio_ms`.

**Por qué el orden de hasheo se deriva de los datos y no del orden de inserción.** Es lo
único que hace posibles al mismo tiempo las tres propiedades que el sistema necesita, y que
parecen contradecirse:

* agregar o quitar un ítem **cambia** el hash — los datos cambiaron;
* alterar cualquiera de los cinco campos de un ítem **cambia** el hash — los datos
  cambiaron;
* reordenar la colección de entrada **no** cambia el hash — el orden se recalcula.

La tercera no es un capricho: las cámaras responden en el orden que quieren, y si el hash
dependiera de eso, dos capturas idénticas darían hashes distintos y la verificación
reportaría "comprometida" ante una diferencia que no existe. Un ejecutor que fijara la
variante opuesta —hashear en orden de inserción— produciría exactamente esos falsos
positivos desde la primera captura, y ya no habría forma de arreglarlo sin invalidar lo
persistido.

**Por qué `incertidumbre_sello_utc_ms` entra en el hash.** Cierra la Open Question 3 de la
investigación. El desvío **relativo** entre cámaras se mide en espacio `perf_counter` y es
preciso a microsegundos; el sello UTC **absoluto** hereda la resolución del reloj de pared
del equipo (~15,6 ms en Windows con Python 3.12). El sistema declara ese número en vez de
callarlo —la misma jugada que D-39 hace con la ventana de ±150 ms—, y al entrar en el hash
nadie puede reescribirlo después para que la evidencia luzca más precisa de lo que fue.

**Por qué el hash sí se calcula acá y el de la imagen no.** El de la imagen es I/O sobre
bytes del disco. Éste es una función pura sobre metadatos que el dominio ya tiene en la
mano: no abre nada, no lee nada, y su resultado depende sólo de sus argumentos.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final, Protocol

from porteria.dominio.comun.identificadores import CamaraId, CapturaId
from porteria.dominio.evidencia.huella import HuellaDeIntegridad

__all__ = ["ItemHasheable", "Manifiesto", "validar_texto_hasheable"]

#: Separador entre los campos de un mismo ítem. `\x1f` es UNIT SEPARATOR de ASCII: no
#: puede aparecer en una ruta de Windows ni en un identificador, y `validar_texto_hasheable`
#: lo verifica en vez de suponerlo. Un separador que pudiera aparecer dentro de un campo
#: haría colisionar dos capturas distintas — el clásico `("a|b", "c")` contra `("a", "b|c")`.
SEPARADOR_DE_CAMPO: Final = "\x1f"

#: Separador entre ítems. `\x1e` es RECORD SEPARATOR de ASCII.
SEPARADOR_DE_ITEM: Final = "\x1e"

#: El algoritmo, declarado en el manifiesto para que dentro de cinco años se sepa con qué
#: se calculó lo que hay guardado.
ALGORITMO: Final = "sha256"

#: La receta del hash, persistida junto al hash. Es lo que permite que un auditor —o el
#: propio sistema en una versión futura— sepa exactamente qué se hasheó y en qué orden.
RECETA_DEL_HASH: Final = (
    "captura_id|incertidumbre_sello_utc_ms|"
    "items ordenados por (camara_id, instante_monotono_ns) de cada uno "
    "sha256|ruta_relativa|camara_id|instante_monotono_ns|desvio_ms"
)


class ItemHasheable(Protocol):
    """Los cinco campos de un ítem que entran en el hash del manifiesto, y sólo esos.

    Se declara como protocolo estructural en vez de importar `ItemDeEvidencia` por dos
    razones: evita el ciclo de imports con `captura.py` —que sí necesita este módulo— y
    deja escrito en el tipo qué parte del ítem es relevante para el sello. Los otros
    dieciséis campos de trazabilidad no entran en el hash; si alguno tuviera que entrar,
    sería un cambio de contrato y se vería acá.
    """

    @property
    def sha256(self) -> HuellaDeIntegridad: ...

    @property
    def ruta_relativa(self) -> str: ...

    @property
    def camara_id(self) -> CamaraId: ...

    @property
    def instante_monotono_ns(self) -> int: ...

    @property
    def desvio_ms(self) -> float: ...


def validar_texto_hasheable(valor: str, campo: str) -> str:
    """Verifica que un texto que va a entrar en el hash no contenga los separadores.

    Se valida al construir el ítem y otra vez al hashear. No es redundancia inútil: un
    ítem puede llegar reconstruido desde la base, y el hash tiene que poder confiar en lo
    que hashea sin importar por dónde entró el dato.
    """
    for separador, nombre in (
        (SEPARADOR_DE_CAMPO, "0x1F"),
        (SEPARADOR_DE_ITEM, "0x1E"),
    ):
        if separador in valor:
            raise ValueError(
                f"El campo «{campo}» contiene el carácter separador {nombre}, que el "
                "hash del manifiesto usa para delimitar campos. Si un campo pudiera "
                "contenerlo, dos capturas distintas producirían el mismo hash y la "
                f"verificación de integridad dejaría de servir. Valor recibido: {valor!r}"
            )
    return valor


def _texto_de_flotante(valor: float) -> str:
    """Representación decimal estable de un flotante para el hash.

    `repr` de un `float` en CPython devuelve la cadena más corta que vuelve al mismo
    valor, así que es reproducible entre corridas y entre plataformas para un mismo
    número. El `+ 0.0` normaliza `-0.0` a `0.0`: son el mismo número pero tienen `repr`
    distinto, y un desvío de cero no puede producir dos hashes según el signo con que se
    calculó.
    """
    return repr(valor + 0.0)


def _texto_de_item(item: ItemHasheable) -> str:
    """Los cinco campos hasheados de un ítem, en el orden del contrato."""
    return SEPARADOR_DE_CAMPO.join(
        (
            item.sha256.valor,
            validar_texto_hasheable(item.ruta_relativa, "ruta_relativa"),
            validar_texto_hasheable(str(item.camara_id), "camara_id"),
            str(item.instante_monotono_ns),
            _texto_de_flotante(item.desvio_ms),
        )
    )


def _ordenar(items: Iterable[ItemHasheable]) -> list[ItemHasheable]:
    """Orden derivado de los datos: `camara_id` y después `instante_monotono_ns`."""
    return sorted(items, key=lambda item: (str(item.camara_id), item.instante_monotono_ns))


def calcular_hash(
    captura_id: CapturaId,
    incertidumbre_sello_utc_ms: float,
    items: Iterable[ItemHasheable],
) -> str:
    """Calcula el hash de segundo nivel de D-08 según la receta de `RECETA_DEL_HASH`."""
    cabecera = SEPARADOR_DE_CAMPO.join(
        (
            validar_texto_hasheable(str(captura_id), "captura_id"),
            _texto_de_flotante(incertidumbre_sello_utc_ms),
        )
    )
    cuerpo = SEPARADOR_DE_ITEM.join(_texto_de_item(item) for item in _ordenar(items))
    texto = SEPARADOR_DE_ITEM.join((cabecera, cuerpo))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Manifiesto:
    """El sello de una captura completa. Sus cinco campos los mapea el plan 01-05.

    Attributes:
        captura_id: La captura que sella.
        hash_manifiesto: El hash de segundo nivel, 64 hexadecimales en minúscula.
        algoritmo: `sha256`, declarado para que el futuro sepa con qué se calculó.
        campos_incluidos: La receta, persistida junto al hash. Sin ella, verificar
            evidencia de hace tres años exigiría leer el código de hace tres años.
        incertidumbre_sello_utc_ms: La resolución real del reloj de pared del equipo donde
            se tomó la evidencia. Entra en el hash.
    """

    captura_id: CapturaId
    hash_manifiesto: str
    algoritmo: str
    campos_incluidos: str
    incertidumbre_sello_utc_ms: float

    @classmethod
    def de_items(
        cls,
        captura_id: CapturaId,
        incertidumbre_sello_utc_ms: float,
        items: Sequence[ItemHasheable],
    ) -> Manifiesto:
        """Sella una colección de ítems. El orden en que vengan no importa."""
        return cls(
            captura_id=captura_id,
            hash_manifiesto=calcular_hash(captura_id, incertidumbre_sello_utc_ms, items),
            algoritmo=ALGORITMO,
            campos_incluidos=RECETA_DEL_HASH,
            incertidumbre_sello_utc_ms=incertidumbre_sello_utc_ms,
        )

    def coincide_con(self, items: Sequence[ItemHasheable]) -> bool:
        """Dice si una colección de ítems sigue produciendo este mismo sello."""
        return self.hash_manifiesto == calcular_hash(
            self.captura_id, self.incertidumbre_sello_utc_ms, items
        )
