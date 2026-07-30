"""La bitácora de auditoría encadenada: tercer nivel de integridad de D-08.

Cada registro incluye el hash del anterior en su propio cálculo. Eso detecta lo que los dos
niveles de abajo no pueden ver: el **borrado** o el **reordenamiento** de registros
completos. La huella detecta que una foto cambió; el manifiesto, que a una captura le falta
una foto; la cadena, que falta una captura entera.

**El encadenamiento arranca en el registro número uno y no es retrofiteable.** Si el primer
registro no participa de la cadena, todo lo anterior a la introducción del encadenamiento
queda fuera del alcance de la verificación para siempre: los hashes que hubieran hecho falta
nunca se calcularon y no hay forma de reconstruirlos. Por eso `numero` arranca en 1 y un
registro numerado 0 se rechaza.

**El límite honesto: esto es tamper-evident, no tamper-proof.**
Quien tenga acceso de escritura al disco de la PC de portería puede reemplazar la foto,
recalcular su hash, reescribir la fila y **re-encadenar la bitácora desde ese punto**. La
verificación entonces pasa. Lo que la cadena consigue es que la manipulación exija rehacer
**todo el histórico posterior** en vez de editar un archivo: es una elevación de costo
enorme, pero no una imposibilidad. Lo único que la volvería tamper-proof es un ancla
externa —replicación a un medio de solo-anexado, sellado de tiempo por un tercero, o
publicación periódica del hash de la cabeza de la cadena—, y esta fase deja ese hueco de
diseño abierto a propósito.

Está escrito acá, en el código, y hay una prueba que lo demuestra
(`test_reencadenar_desde_el_punto_alterado_pasa_la_verificacion`), porque vender
"inalterable" lo que es "detectable" es un riesgo de reputación mayor que la amenaza
técnica. Este es un producto de auditoría: lo que promete tiene que ser lo que hace.

**Por qué la bitácora de auditoría no es la bitácora técnica** (D-11): la técnica va a
archivos rotativos con nivel configurable y es borrable sin consecuencias; ésta vive en la
base, sólo agrega y va encadenada. Subir el detalle para depurar no puede inundar la
evidencia legal, y rotar archivos no puede borrar la cadena de custodia.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Final

from porteria.dominio.comun.identificadores import UsuarioId
from porteria.dominio.comun.tiempo import InstanteUtc

__all__ = ["CadenaDeAuditoria", "RegistroEncadenado", "calcular_hash_de_registro"]

#: Separadores del texto que se hashea. Se declaran acá, independientes de los del
#: manifiesto, **a propósito**: son dos contratos de hash separados y acoplarlos haría que
#: un cambio en uno alterara los hashes del otro.
SEPARADOR_DE_CAMPO: Final = "\x1f"
SEPARADOR_DE_PAR: Final = "\x1e"

#: El primer registro de la cadena. No hay registro 0 (ver el docstring del módulo).
PRIMER_NUMERO: Final = 1

#: Texto que ocupa el lugar del hash anterior en el primer registro. Es una cadena y no la
#: vacía para que "primer registro" y "registro cuyo anterior tenía hash vacío" no puedan
#: producir el mismo texto hasheado.
SIN_ANTERIOR: Final = "GENESIS"

#: Texto que ocupa el lugar del actor cuando no hubo sesión iniciada (D-21).
SIN_ACTOR: Final = "NO_IDENTIFICADO"


def _texto_de_datos(datos: Mapping[str, str]) -> str:
    """Serializa los datos de forma estable: pares ordenados por clave.

    El orden se **deriva** de las claves y no del orden de inserción del diccionario, por la
    misma razón que en el manifiesto: el hash tiene que depender de los datos, no de cómo
    se armó el diccionario que los trajo.
    """
    return SEPARADOR_DE_PAR.join(
        f"{clave}{SEPARADOR_DE_CAMPO}{datos[clave]}" for clave in sorted(datos)
    )


def calcular_hash_de_registro(
    numero: int,
    nombre: str,
    ocurrido_en: InstanteUtc,
    actor: UsuarioId | None,
    datos: Mapping[str, str],
    hash_anterior: str | None,
) -> str:
    """Calcula el hash de un registro, incluyendo el del anterior.

    El `numero` entra en el cálculo además del hash anterior: así dos hechos idénticos en
    posiciones distintas no pueden producir el mismo hash, y mover un registro de lugar
    rompe la cadena aunque su contenido no haya cambiado.
    """
    texto = SEPARADOR_DE_PAR.join(
        (
            str(numero),
            nombre,
            ocurrido_en.texto,
            str(actor) if actor is not None else SIN_ACTOR,
            _texto_de_datos(datos),
            hash_anterior if hash_anterior is not None else SIN_ANTERIOR,
        )
    )
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class RegistroEncadenado:
    """Un hecho auditable, sellado y atado al anterior.

    Attributes:
        numero: Posición en la cadena, desde 1.
        nombre: Qué ocurrió, por ejemplo `captura.registrada`.
        ocurrido_en: Cuándo, como texto ISO-8601 con offset.
        actor: Quién, o `None` si no había sesión iniciada (D-21).
        datos: Detalle del hecho. Entra en el hash.
        hash_anterior: El hash del registro previo. `None` sólo en el registro 1.
        hash_propio: El hash de este registro, que incluye `hash_anterior`.
    """

    numero: int
    nombre: str
    ocurrido_en: InstanteUtc
    actor: UsuarioId | None
    datos: Mapping[str, str]
    hash_anterior: str | None
    hash_propio: str

    def __post_init__(self) -> None:
        if self.numero < PRIMER_NUMERO:
            raise ValueError(
                f"El número de registro {self.numero} no es válido: la cadena arranca en "
                f"{PRIMER_NUMERO}. Un registro numerado por debajo sería histórico "
                "anterior a la cadena colado por atrás, que es exactamente lo que el "
                "encadenamiento desde el registro uno existe para impedir."
            )
        if not self.nombre:
            raise ValueError("Todo registro de auditoría tiene que decir qué ocurrió.")
        if self.numero == PRIMER_NUMERO and self.hash_anterior is not None:
            raise ValueError(
                "El primer registro de la cadena no puede tener hash anterior: no hay "
                "nada antes de él."
            )
        if self.numero > PRIMER_NUMERO and self.hash_anterior is None:
            raise ValueError(
                f"El registro {self.numero} no tiene hash anterior. Sólo el primero puede "
                "no tenerlo; un registro posterior sin él sería una cadena arrancada de "
                "nuevo en el medio, y todo lo anterior quedaría fuera de la verificación."
            )
        object.__setattr__(self, "datos", MappingProxyType(dict(self.datos)))

    def hash_recalculado(self) -> str:
        """Vuelve a calcular el hash a partir de los campos que tiene ahora."""
        return calcular_hash_de_registro(
            numero=self.numero,
            nombre=self.nombre,
            ocurrido_en=self.ocurrido_en,
            actor=self.actor,
            datos=self.datos,
            hash_anterior=self.hash_anterior,
        )


@dataclass
class CadenaDeAuditoria:
    """La bitácora encadenada: sólo agrega, nunca modifica ni borra."""

    _registros: list[RegistroEncadenado] = field(default_factory=list)

    @property
    def registros(self) -> tuple[RegistroEncadenado, ...]:
        return tuple(self._registros)

    def encadenar(
        self,
        nombre: str,
        ocurrido_en: InstanteUtc,
        actor: UsuarioId | None = None,
        datos: Mapping[str, str] | None = None,
    ) -> RegistroEncadenado:
        """Agrega un hecho al final de la cadena y devuelve el registro sellado."""
        anterior = self._registros[-1] if self._registros else None
        numero = anterior.numero + 1 if anterior is not None else PRIMER_NUMERO
        hash_anterior = anterior.hash_propio if anterior is not None else None
        contenido = dict(datos or {})

        registro = RegistroEncadenado(
            numero=numero,
            nombre=nombre,
            ocurrido_en=ocurrido_en,
            actor=actor,
            datos=contenido,
            hash_anterior=hash_anterior,
            hash_propio=calcular_hash_de_registro(
                numero=numero,
                nombre=nombre,
                ocurrido_en=ocurrido_en,
                actor=actor,
                datos=contenido,
                hash_anterior=hash_anterior,
            ),
        )
        self._registros.append(registro)
        return registro

    @staticmethod
    def verificar(registros: Sequence[RegistroEncadenado]) -> int | None:
        """Recorre la cadena y devuelve el **índice** del primer registro roto.

        Es estático y recibe la secuencia porque el caso de uso normal es verificar lo que
        se leyó de la base, no lo que se tiene en memoria.

        Returns:
            El índice en `registros` del primer problema, o `None` si la cadena está
            entera. Se devuelve el índice de la lista y no el `numero` del registro,
            porque cuando falta un registro del medio los dos dejan de coincidir y lo que
            hace falta señalar es la posición donde mirar.
        """
        hash_previo: str | None = None
        numero_esperado = PRIMER_NUMERO

        for indice, registro in enumerate(registros):
            if registro.numero != numero_esperado:
                return indice
            if registro.hash_anterior != hash_previo:
                return indice
            if registro.hash_propio != registro.hash_recalculado():
                return indice

            hash_previo = registro.hash_propio
            numero_esperado += 1

        return None

    def esta_entera(self) -> bool:
        """Atajo legible para el estado del sistema."""
        return self.verificar(self.registros) is None
