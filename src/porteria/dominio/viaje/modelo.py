"""Viaje, remito, artículo y peso teórico: el modelo que admite lo incómodo (D-27).

Todo en español (D-32). Cuando el portero dice "remito" y el código dice `Remito`
desaparece una capa entera de traducción, que es donde se cuelan los errores de
interpretación entre lo que el negocio pidió y lo que el sistema hace.

**Viaje↔Remito es muchas a muchas desde el diseño** (VIA-05), no una lista de conveniencia.
El caso real que la Fase 6 tiene que sostener es exactamente ése: un viaje con tres
remitos, uno de ellos compartido con otro viaje. Modelarlo como uno a muchos y migrar
después obliga a tocar un esquema con años de datos productivos, y por eso es una de las
seis decisiones no retrofiteables de la fase.

**El peso teórico puede estar ausente, y la ausencia es un caso normal** (D-31). No es cero
y no es `-1`: es `None`. El estado del remito —completo o incompleto— **se deriva** de si
algún artículo carece de peso, y no se persiste en ningún campo, para que estado y datos no
puedan contradecirse. `Viaje.peso_teorico_total()` devuelve `Resultado[float]`: cuando falta
algún peso devuelve `NoDisponible` con la lista de códigos, que es lo que alimenta el
reporte de artículos sin peso maestro de la Fase 7 y el tercer veredicto de AUD-03, "peso
teórico incompleto". Nunca inventa un número: un cero silencioso produciría una diferencia
enorme contra la balanza y un veredicto de auditoría falso.

**Los puertos externos se diseñan a partir de esto y nunca copiando el esquema de PALJET.**
El puerto lo dicta el negocio —"necesito el peso teórico del viaje"— y no el ERP —"PALJET
devuelve `ART_PES_UNI`"—. Si el modelo se copiara del ERP, cada cambio del ERP sería un
cambio del dominio.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final

from porteria.dominio.comun.identificadores import NumeroLegible, RemitoId, ViajeId
from porteria.dominio.comun.resultado import NoDisponible, Ok, Resultado
from porteria.dominio.comun.tiempo import InstanteUtc

__all__ = [
    "Articulo",
    "Camion",
    "Chofer",
    "Patente",
    "PesoTeorico",
    "Remito",
    "Transportista",
    "Viaje",
]

#: Todo lo que no es letra ni dígito se descarta al normalizar una patente: espacios,
#: guiones, puntos y lo que traiga el ERP o tipee el operador.
NO_ALFANUMERICO: Final = re.compile(r"[^A-Za-z0-9]")


@dataclass(frozen=True, slots=True)
class Patente:
    """Una patente normalizada, con su texto original conservado al lado.

    **Acá no se valida la gramática argentina.** Distinguir el formato Mercosur `AA123AA`
    del viejo `ABC123` es de la Fase 5, y a propósito: en la puerta puede aparecer un
    camión de Brasil, un acoplado con patente vieja o una chapa ilegible, y rechazar en el
    dominio por formato bloquearía la captura de evidencia. Ninguna regla de formato vale
    eso.

    La igualdad es por el valor canónico —es el mismo camión— y el original se conserva
    fuera de la comparación porque es el dato que permite auditar la traducción: si mañana
    hay que revisar qué devolvió el ERP, está tal cual llegó.
    """

    original: str = field(compare=False)
    canonica: str = field(init=False)

    def __post_init__(self) -> None:
        canonica = NO_ALFANUMERICO.sub("", self.original).upper()
        if not canonica:
            raise ValueError(
                f"«{self.original}» no contiene ninguna letra ni dígito, así que no es una "
                "patente. Qué revisar: que el campo no haya llegado vacío del ERP o de la "
                "carga manual."
            )
        object.__setattr__(self, "canonica", canonica)

    def __str__(self) -> str:
        return self.canonica


@dataclass(frozen=True, slots=True)
class PesoTeorico:
    """Un peso que puede estar **ausente**. No cero, no `-1`, no un centinela (D-31).

    Existe como valor con nombre propio para que la ausencia sea imposible de confundir con
    un peso de cero kilos, que es un peso real y legítimo. El centinela `-1` —el atajo
    clásico para "no sé"— se rechaza explícitamente: un centinela numérico se suma sin que
    nadie lo note.
    """

    kilogramos: float | None

    def __post_init__(self) -> None:
        if self.kilogramos is not None and self.kilogramos < 0:
            raise ValueError(
                f"{self.kilogramos} kg es un peso teórico negativo. Un peso no puede ser "
                "negativo, y `-1` como centinela de «no sé» es justamente lo que D-31 "
                "prohíbe: la ausencia se expresa con `PesoTeorico.ausente()`, que ninguna "
                "suma puede tragarse por accidente."
            )

    @classmethod
    def de(cls, kilogramos: float) -> PesoTeorico:
        """Un peso conocido. Cero es un peso conocido."""
        return cls(kilogramos)

    @classmethod
    def ausente(cls) -> PesoTeorico:
        """El peso que el maestro de artículos no tiene cargado."""
        return cls(None)

    @property
    def presente(self) -> bool:
        return self.kilogramos is not None


@dataclass(frozen=True, slots=True)
class Chofer:
    """Quién maneja. Los datos que el descubrimiento de D-41 tiene que traer."""

    nombre: str
    documento: str | None = None


@dataclass(frozen=True, slots=True)
class Camion:
    """El vehículo, con su acoplado si lo lleva."""

    patente: Patente
    patente_acoplado: Patente | None = None


@dataclass(frozen=True, slots=True)
class Transportista:
    """La empresa que transporta."""

    nombre: str
    cuit: str | None = None


@dataclass(slots=True)
class Articulo:
    """Una línea del remito. Su peso teórico puede no existir, y eso es normal (D-31)."""

    codigo: str
    descripcion: str
    peso_teorico_kg: float | None = None

    @property
    def peso_teorico(self) -> PesoTeorico:
        """El peso como valor, para que la ausencia se pueda pasar sin perder el sentido."""
        return PesoTeorico(self.peso_teorico_kg)


@dataclass(slots=True, eq=False)
class Remito:
    """Un remito con sus artículos. Puede pertenecer a más de un viaje (VIA-05).

    **`eq=False` con igualdad por identificador, y no la comparación campo por campo que
    genera `dataclass`.** Dos razones, y la primera es un defecto real:

    1. La relación N:M es bidireccional, así que comparar campo por campo entraría en
       `Remito.viajes → Viaje.remitos → Remito.viajes` y **recursaría infinitamente** en
       cuanto se comparen dos objetos distintos con contenido equivalente. `list.__contains__`
       lo tapa mientras se traten del mismo objeto, porque prueba identidad antes de
       igualdad, y ahí el defecto queda latente esperando el primer remito reconstruido
       desde la base.
    2. Un remito es una **entidad**, no un valor: dos remitos con el mismo identificador son
       el mismo remito aunque uno tenga los artículos todavía sin cargar. Comparar por
       contenido diría que son distintos, que es lo contrario de lo que el negocio entiende.
    """

    id: RemitoId
    numero: str
    articulos: list[Articulo] = field(default_factory=list)
    viajes: list[Viaje] = field(default_factory=list)

    def __eq__(self, otro: object) -> bool:
        if not isinstance(otro, Remito):
            return NotImplemented
        return self.id == otro.id

    def __hash__(self) -> int:
        return hash(("Remito", self.id))

    @property
    def tiene_peso_teorico_completo(self) -> bool:
        """Se **deriva** de los artículos; no existe ningún campo que pueda contradecirlo.

        Un remito sin artículos no se declara completo: no tiene pesos que sumar, y decir
        "completo" ahí equivaldría a sumar cero y llamarlo total.
        """
        return bool(self.articulos) and all(
            articulo.peso_teorico.presente for articulo in self.articulos
        )

    @property
    def articulos_sin_peso(self) -> tuple[str, ...]:
        """Los códigos sin peso teórico, en el orden en que están en el remito.

        Es la consulta que alimenta el reporte de artículos sin peso maestro de la Fase 7.
        """
        return tuple(
            articulo.codigo for articulo in self.articulos if not articulo.peso_teorico.presente
        )

    @property
    def peso_teorico_kg(self) -> Resultado[float]:
        """La suma del remito, o `NoDisponible` con los códigos que faltan."""
        faltantes = self.articulos_sin_peso
        if not self.articulos:
            return NoDisponible(
                f"El remito «{self.numero}» no tiene artículos cargados, así que no tiene "
                "peso teórico."
            )
        if faltantes:
            return NoDisponible(
                f"El remito «{self.numero}» tiene artículos sin peso teórico cargado en el "
                f"maestro: {', '.join(faltantes)}.",
                faltantes,
            )
        return Ok(sum(articulo.peso_teorico_kg or 0.0 for articulo in self.articulos))


@dataclass(slots=True, eq=False)
class Viaje:
    """Un viaje con sus remitos, su vehículo y su telemetría cargada a mano (D-45).

    Igualdad por identificador, por las dos razones que explica `Remito`: es una entidad, y
    la comparación campo por campo recursaría por la relación bidireccional.
    """

    id: ViajeId
    numero_legible: NumeroLegible
    remitos: list[Remito] = field(default_factory=list)
    chofer: Chofer | None = None
    camion: Camion | None = None
    transportista: Transportista | None = None

    #: Telemetría de D-45. Geomov se declara como puerto con la **carga manual como
    #: implementación de referencia y camino principal**, no como parche: una eventual
    #: interfaz será una segunda implementación del mismo puerto. El modelo reserva el
    #: lugar desde ahora para no tener que migrar cuando llegue.
    kilometros_recorridos: float | None = None
    salida_en: InstanteUtc | None = None
    regreso_en: InstanteUtc | None = None

    def __eq__(self, otro: object) -> bool:
        if not isinstance(otro, Viaje):
            return NotImplemented
        return self.id == otro.id

    def __hash__(self) -> int:
        return hash(("Viaje", self.id))

    def vincular_remito(self, remito: Remito) -> None:
        """Ata el remito al viaje **en los dos sentidos**, sin duplicar.

        Los dos sentidos porque el inverso también se consulta: dado un remito, saber en
        qué viajes salió es justamente la pregunta del remito compartido.
        """
        if remito not in self.remitos:
            self.remitos.append(remito)
        if self not in remito.viajes:
            remito.viajes.append(self)

    def peso_teorico_total(self) -> Resultado[float]:
        """Suma el peso teórico de todos los artículos de todos sus remitos.

        Returns:
            `Ok(total)` cuando todos los artículos de todos los remitos tienen peso.
            `NoDisponible` con el detalle de qué códigos faltan cuando alguno no lo tiene.
            Nunca un número inventado ni una suma que trate `None` como cero: ese cero
            silencioso produciría una diferencia enorme contra la balanza y un veredicto de
            auditoría falso.
        """
        if not self.remitos:
            return NoDisponible(
                f"El viaje «{self.numero_legible}» todavía no tiene ningún remito "
                "asociado, así que no hay peso teórico que sumar."
            )

        faltantes = tuple(
            codigo for remito in self.remitos for codigo in remito.articulos_sin_peso
        )
        vacios = tuple(remito.numero for remito in self.remitos if not remito.articulos)

        if vacios:
            return NoDisponible(
                f"El viaje «{self.numero_legible}» tiene remitos sin artículos cargados: "
                f"{', '.join(vacios)}.",
                vacios,
            )
        if faltantes:
            return NoDisponible(
                f"El viaje «{self.numero_legible}» no tiene peso teórico completo: faltan "
                f"los pesos de {', '.join(faltantes)} en el maestro de artículos.",
                faltantes,
            )

        return Ok(
            sum(
                articulo.peso_teorico_kg or 0.0
                for remito in self.remitos
                for articulo in remito.articulos
            )
        )
