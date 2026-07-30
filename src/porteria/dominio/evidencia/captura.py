"""`CapturaDeControl` e `ItemDeEvidencia`: el disparo y cada foto que produjo.

**La captura nace autónoma** (D-28). Sin viaje, sin movimiento, sin nada más que su
instante objetivo y su evidencia. Se vincula a un viaje después. Lo exige la operación
real —el portero saca la foto cuando el camión está delante y busca el viaje después— y lo
exige esta fase, donde la orden de captura corre sobre un archivo de video que no tiene
viaje alguno.

**La captura nunca se bloquea por falta de sesión** (D-21). Sin sesión iniciada,
`autor=None` significa "no identificado", la evidencia se registra igual y el hecho queda
marcado para el panel de calidad. Es la misma regla que rige la captura parcial: registrar
lo incompleto en lugar de impedirlo. Una expiración de sesión justo cuando el camión está
sobre la balanza no puede costar la evidencia.

**La ventana vigente queda congelada en la instancia** (D-40, amenaza T-01-14). Cada ítem
guarda cuál era la ventana de aceptación en el momento en que se capturó. Sin eso, un
administrador que ensanchara el parámetro haría que todas las capturas viejas pasaran
retroactivamente de "estimadas" a "sincronizadas" — reescribiendo la calidad del histórico
sin tocar un solo dato. Por eso es una propiedad de sólo lectura y no un campo asignable.

**Los eventos se acumulan, no se publican.** El caso de uso los recoge y los persiste en el
outbox dentro de la misma transacción que confirma la fila y el manifiesto (D-12). Si el
agregado publicara, existirían eventos de capturas que no se guardaron.

Los 21 campos de `ItemDeEvidencia` son los nombres canónicos de la tabla de trazabilidad
(D-05, EVI-05, EVI-06). El esquema del plan 01-05 los mapea uno a uno y agrega exactamente
tres columnas propias (`id`, `captura_id` y `miniatura`). Una divergencia de nombres se
paga en traducciones silenciosas entre el dominio y la base, que es donde se cuelan los
errores que nadie encuentra.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Final

from porteria.dominio.comun.identificadores import (
    CamaraId,
    CapturaId,
    NumeroLegible,
    UsuarioId,
    ViajeId,
)
from porteria.dominio.comun.tiempo import Desfasaje, FechaLocal, InstanteUtc
from porteria.dominio.eventos import EventoDeDominio
from porteria.dominio.evidencia.estados import EstadoDeIntegridad
from porteria.dominio.evidencia.huella import HuellaDeIntegridad
from porteria.dominio.evidencia.manifiesto import Manifiesto, validar_texto_hasheable

__all__ = ["VENTANA_POR_DEFECTO_MS", "CapturaDeControl", "ItemDeEvidencia"]

#: D-39: ±150 ms, tomada de la investigación de arquitectura y **explícitamente no
#: validada** con el cliente ni medida en campo. Es el valor con el que la configuración
#: arranca, no un supuesto del dominio: `CapturaDeControl.nueva` **exige** que la ventana se
#: pase, para que ninguna captura quede sellada con una ventana que nadie eligió.
VENTANA_POR_DEFECTO_MS: Final = 150.0

#: Nanosegundos en un milisegundo.
NS_POR_MS: Final = 1_000_000

#: Nombre del hecho que se acumula al agregar evidencia.
EVENTO_EVIDENCIA_AGREGADA: Final = "evidencia.agregada"


@dataclass(frozen=True, slots=True)
class ItemDeEvidencia:
    """Una foto y todo lo que hace falta para auditarla dentro de veinte años.

    Los 21 campos, en el orden canónico. `motor_id`, `version_modelo` y `sha256_modelo`
    quedan nulos en esta fase y se poblan desde la Fase 4, cuando haya inferencia.
    """

    ruta_relativa: str
    sha256: HuellaDeIntegridad
    bytes_totales: int
    capturado_en_utc_iso: InstanteUtc
    desfasaje_local_min: Desfasaje
    fecha_local: FechaLocal
    instante_monotono_ns: int
    desvio_ms: float
    ventana_vigente_ms: float
    perfil_de_flujo: str
    resolucion: str
    codec_origen: str
    calidad_jpeg: int
    camara_id: CamaraId
    motor_id: str | None
    version_modelo: str | None
    sha256_modelo: HuellaDeIntegridad | None
    version_app: str
    version_esquema: str
    autor_id: UsuarioId | None
    estado_integridad: EstadoDeIntegridad

    def __post_init__(self) -> None:
        self._validar_ruta()
        validar_texto_hasheable(str(self.camara_id), "camara_id")
        if self.bytes_totales <= 0:
            raise ValueError(
                f"«{self.ruta_relativa}» declara {self.bytes_totales} bytes. Un archivo "
                "de evidencia de cero bytes es un archivo truncado, y el tamaño es "
                "justamente lo que permite detectar el truncamiento antes de leerlo todo."
            )

    def _validar_ruta(self) -> None:
        """D-06: la ruta se persiste **relativa** a la raíz de evidencia, nunca absoluta.

        La raíz de evidencia es configurable y el cliente la puede mover a otro disco; una
        ruta absoluta obligaría a migrar la base para eso. Y una ruta con `..` convierte la
        lectura posterior en un path traversal: el nombre del archivo se deriva del hash y
        es inofensivo, pero la ruta relativa persistida es la que después se abre.
        """
        ruta = self.ruta_relativa
        validar_texto_hasheable(ruta, "ruta_relativa")

        absoluta = ruta.startswith(("/", "\\")) or (len(ruta) > 1 and ruta[1] == ":")
        if not ruta or absoluta or ".." in ruta.split("/") or ".." in ruta.split("\\"):
            raise ValueError(
                f"«{ruta}» no es una ruta relativa válida de evidencia. Tiene que ser "
                "relativa a la raíz de evidencia, con separador «/» y sin «..», por "
                "ejemplo 2026/07/25/<sha256>.jpg.\n"
                "Qué revisar: que quien la construyó no haya usado la ruta absoluta del "
                "disco. Persistir la absoluta impide mover la evidencia a otro disco sin "
                "migrar la base (D-06)."
            )

    @property
    def sincronizada(self) -> bool:
        """Dice si el desvío entra en la ventana que regía cuando se capturó (D-40).

        Se **deriva**; no se persiste. Un campo booleano guardado podría contradecir al
        desvío y a la ventana que están al lado, y entonces habría que decidir a cuál
        creerle.
        """
        return abs(self.desvio_ms) <= self.ventana_vigente_ms


class CapturaDeControl:
    """Un disparo del botón: un instante objetivo y las fotos que se pudieron obtener.

    No es una dataclass a propósito. Los datos que fijan la identidad del disparo
    —identificador, instante objetivo, ventana vigente y autor— se exponen como
    propiedades de sólo lectura, y lo único que crece es la colección de evidencia y la de
    eventos. Con una dataclass mutable, `captura.ventana_vigente_ms = 5000` sería una línea
    válida en cualquier parte del sistema, y es exactamente la línea que T-01-14 describe.
    """

    def __init__(
        self,
        identificador: CapturaId,
        instante_objetivo_ns: int,
        ventana_vigente_ms: float,
        autor: UsuarioId | None = None,
        numero_legible: NumeroLegible | None = None,
    ) -> None:
        if ventana_vigente_ms <= 0:
            raise ValueError(
                f"La ventana vigente de aceptación es {ventana_vigente_ms} ms y tiene que "
                "ser mayor que cero: con una ventana de cero ninguna captura podría "
                "declararse sincronizada nunca. El valor por defecto de D-39 es "
                f"{VENTANA_POR_DEFECTO_MS} ms."
            )

        self._id = identificador
        self._numero_legible = numero_legible
        self._instante_objetivo_ns = instante_objetivo_ns
        self._ventana_vigente_ms = float(ventana_vigente_ms)
        self._autor = autor
        self._viaje: ViajeId | None = None
        self._items: list[ItemDeEvidencia] = []
        self._eventos: list[EventoDeDominio] = []

    @classmethod
    def nueva(
        cls,
        instante_objetivo_ns: int,
        autor: UsuarioId | None,
        ventana_vigente_ms: float,
        identificador: CapturaId | None = None,
        numero_legible: NumeroLegible | None = None,
    ) -> CapturaDeControl:
        """Crea una captura nueva, **sin viaje asociado** (D-28).

        `ventana_vigente_ms` no tiene valor por defecto a propósito: quien dispara tiene
        que decir con qué criterio se va a evaluar esta captura, porque ese número queda
        sellado en cada ítem y ya no se puede cambiar (D-40).

        `identificador` es el opaco universal de D-29 y se genera acá si no viene dado; se
        admite inyectarlo para que las pruebas y una importación de otra instalación puedan
        fijarlo.
        """
        return cls(
            identificador=identificador or CapturaId(str(uuid.uuid4())),
            instante_objetivo_ns=instante_objetivo_ns,
            ventana_vigente_ms=ventana_vigente_ms,
            autor=autor,
            numero_legible=numero_legible,
        )

    # ------------------------------------------------------------ propiedades #

    @property
    def id(self) -> CapturaId:
        return self._id

    @property
    def numero_legible(self) -> NumeroLegible | None:
        """El número que una persona puede dictar por teléfono (D-29)."""
        return self._numero_legible

    @property
    def instante_objetivo_ns(self) -> int:
        """El instante contra el que se mide el desvío de cada foto."""
        return self._instante_objetivo_ns

    @property
    def ventana_vigente_ms(self) -> float:
        """La ventana que regía en este disparo. Sólo lectura, para siempre (D-40)."""
        return self._ventana_vigente_ms

    @property
    def autor(self) -> UsuarioId | None:
        """Quién disparó, o `None` si no había sesión iniciada (D-21)."""
        return self._autor

    @property
    def autor_identificado(self) -> bool:
        """El hecho que el panel de calidad contabiliza (D-21)."""
        return self._autor is not None

    @property
    def viaje(self) -> ViajeId | None:
        """El viaje al que se vinculó después, si ya se vinculó (D-28)."""
        return self._viaje

    @property
    def items(self) -> tuple[ItemDeEvidencia, ...]:
        """La evidencia acumulada. Tupla: nadie la modifica desde afuera."""
        return tuple(self._items)

    @property
    def eventos(self) -> tuple[EventoDeDominio, ...]:
        """Los hechos acumulados, para que el caso de uso los persista en el outbox."""
        return tuple(self._eventos)

    @property
    def esta_sincronizada(self) -> bool:
        """Todas las fotos entraron en la ventana. Con cero fotos, no hay nada sincronizado."""
        return bool(self._items) and all(item.sincronizada for item in self._items)

    # ------------------------------------------------------------ operaciones #

    def vincular_viaje(self, viaje: ViajeId) -> None:
        """Asocia la captura a un viaje, después del hecho (D-28)."""
        self._viaje = viaje

    def agregar_evidencia(
        self,
        *,
        ruta_relativa: str,
        sha256: HuellaDeIntegridad,
        bytes_totales: int,
        capturado_en_utc_iso: InstanteUtc,
        desfasaje_local_min: Desfasaje,
        fecha_local: FechaLocal,
        instante_monotono_ns: int,
        perfil_de_flujo: str,
        resolucion: str,
        codec_origen: str,
        calidad_jpeg: int,
        camara_id: CamaraId,
        version_app: str,
        version_esquema: str,
        motor_id: str | None = None,
        version_modelo: str | None = None,
        sha256_modelo: HuellaDeIntegridad | None = None,
        estado_integridad: EstadoDeIntegridad = EstadoDeIntegridad.INTEGRA,
    ) -> ItemDeEvidencia:
        """Acumula una foto en la captura y el hecho correspondiente.

        La captura sella tres cosas que **no** son del que llama, y por eso no se reciben:
        el `desvio_ms` (se calcula contra el instante objetivo del disparo), la
        `ventana_vigente_ms` (la de esta captura, congelada) y el `autor_id` (el del
        disparo). Si vinieran de afuera, cada una sería una vía para escribir un número
        distinto del real.
        """
        if any(item.camara_id == camara_id for item in self._items):
            raise ValueError(
                f"La captura «{self._id}» ya tiene evidencia de la cámara «{camara_id}». "
                "Una captura es un disparo y le corresponde una foto por cámara: dos "
                "fotos de la misma cámara en el mismo disparo son un error de "
                "sincronización, no dos evidencias."
            )

        item = ItemDeEvidencia(
            ruta_relativa=ruta_relativa,
            sha256=sha256,
            bytes_totales=bytes_totales,
            capturado_en_utc_iso=capturado_en_utc_iso,
            desfasaje_local_min=desfasaje_local_min,
            fecha_local=fecha_local,
            instante_monotono_ns=instante_monotono_ns,
            desvio_ms=(instante_monotono_ns - self._instante_objetivo_ns) / NS_POR_MS,
            ventana_vigente_ms=self._ventana_vigente_ms,
            perfil_de_flujo=perfil_de_flujo,
            resolucion=resolucion,
            codec_origen=codec_origen,
            calidad_jpeg=calidad_jpeg,
            camara_id=camara_id,
            motor_id=motor_id,
            version_modelo=version_modelo,
            sha256_modelo=sha256_modelo,
            version_app=version_app,
            version_esquema=version_esquema,
            autor_id=self._autor,
            estado_integridad=estado_integridad,
        )

        self._items.append(item)
        self._eventos.append(
            EventoDeDominio(
                nombre=EVENTO_EVIDENCIA_AGREGADA,
                ocurrido_en=capturado_en_utc_iso,
                instante_monotono_ns=instante_monotono_ns,
                datos={
                    "captura_id": str(self._id),
                    "camara_id": str(camara_id),
                    "sha256": sha256.valor,
                    "desvio_ms": repr(item.desvio_ms),
                    "sincronizada": str(item.sincronizada).lower(),
                },
            )
        )
        return item

    def manifiesto(self, incertidumbre_sello_utc_ms: float) -> Manifiesto:
        """Sella la captura con el hash de segundo nivel de D-08.

        La incertidumbre del sello UTC absoluto la mide el puerto `Reloj` en el equipo y la
        recibe acá como dato: medirla es infraestructura, declararla es evidencia.
        """
        return Manifiesto.de_items(
            captura_id=self._id,
            incertidumbre_sello_utc_ms=incertidumbre_sello_utc_ms,
            items=self.items,
        )
