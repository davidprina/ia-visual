"""El esquema que el producto va a arrastrar durante años (D-27).

Sólo lo **no retrofiteable**, y completo: una tabla que nace incompleta se corrige con una
migración sobre la evidencia de años del cliente, y una que nace de más es una columna que
nadie llena. Las dos decisiones que esta fase congela acá son la relación Viaje↔Remito
**muchas a muchas** (VIA-05) y el peso teórico **admitiendo ausencia** con el estado del
remito derivado en vez de persistido (D-31).

**La convención de nombres es obligatoria, no cosmética.** Sin `naming_convention`, SQLite
guarda las restricciones sin nombre y `batch_alter_table` no puede soltarlas: la migración
que reescribe la tabla se queda sin forma de referirse a lo que tiene que quitar. Es la
diferencia entre poder migrar el esquema del cliente y no poder.

**Sobre el tiempo.** Los instantes se persisten como **texto ISO-8601 con offset** más un
entero de minutos aparte, nunca con el tipo de fecha con zona horaria de SQLAlchemy: ese
tipo, sobre SQLite, escribe sin la zona y al leer devuelve un instante sin `tzinfo`, con lo
cual todo el histórico se desplaza en silencio. El desplazamiento no rompe nada visible el
día que ocurre; aparece meses después, cuando alguien audita una captura de madrugada. Hay
invariantes de código que exigen que ese tipo no aparezca en este archivo, y también que no
aparezca la fábrica declarativa vieja: el esquema está en estilo tipado 2.0
(`DeclarativeBase` + `Mapped[]` + `mapped_column`), que es lo que permite que el verificador
de tipos vea las columnas y lo que mantiene el SQL siempre parametrizado (T-01-05).

**Las imágenes completas no van en la base.** Van al filesystem con su ruta relativa y su
SHA-256 acá (EVI-06, D-06). Una base con cientos de GB de fotos deja de poder respaldarse
copiando un archivo, que es justamente la propiedad que la hace administrable en una planta
sin área de sistemas. La excepción deliberada son las **miniaturas** de ~15 KB (D-04): para
blobs chicos SQLite es más rápido que el filesystem y la grilla de la interfaz se pinta con
una sola consulta en vez de miles de aperturas de archivo.

**Unicidad de `item_evidencia`, acordada con el plan 01-04.** El almacén de evidencia está
direccionado por contenido: el nombre del archivo es el SHA-256 de sus bytes, así que dos
capturas de bytes idénticos —una cámara apuntando a una pared quieta— producen la **misma**
`ruta_relativa`. Por eso `ruta_relativa` lleva un índice **no único**, y la unicidad vive en
`(captura_id, camara_id)`, que es la invariante real del negocio: una captura tiene a lo
sumo un ítem por cámara. Con UNIQUE en la ruta, la segunda captura de un contenido repetido
reventaría con `IntegrityError` dejando un archivo huérfano y un error incomprensible para
el portero (T-01-27).
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

__all__ = [
    "CONVENCION",
    "Articulo",
    "Base",
    "BitacoraAuditoria",
    "Captura",
    "Configuracion",
    "ItemEvidencia",
    "Lapida",
    "Manifiesto",
    "Outbox",
    "PayloadCrudo",
    "Remito",
    "Usuario",
    "Viaje",
    "viaje_remito",
]

#: Sin esto, `batch_alter_table` no puede soltar restricciones sin nombre en SQLite.
CONVENCION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

#: Largos de columna que se repiten. Nombrados para que cambiar uno no sea un barrido.
LARGO_ID_OPACO = 36
LARGO_NUMERO_LEGIBLE = 20
LARGO_SHA256 = 64
LARGO_INSTANTE_ISO = 32
LARGO_FECHA_LOCAL = 10
LARGO_RUTA_RELATIVA = 255


class Base(DeclarativeBase):
    """Raíz declarativa del esquema, con la convención de nombres puesta."""

    metadata = MetaData(naming_convention=CONVENCION)


def _uuid() -> str:
    """El identificador opaco de D-29, generado del lado de la aplicación."""
    return str(uuid.uuid4())


# --------------------------------------------------------------------------- #
# Viaje ↔ Remito: la relación muchas a muchas (VIA-05)
# --------------------------------------------------------------------------- #

#: `ondelete="RESTRICT"` en los dos lados: borrar un viaje que todavía tiene remitos
#: asociados —o al revés— es siempre un error de programa, no una operación del negocio.
viaje_remito = Table(
    "viaje_remito",
    Base.metadata,
    Column("viaje_id", ForeignKey("viaje.id", ondelete="RESTRICT"), primary_key=True),
    Column("remito_id", ForeignKey("remito.id", ondelete="RESTRICT"), primary_key=True),
    # El sentido inverso también se consulta: dado un remito, en qué viajes salió.
    Index("ix_viaje_remito_remito_id", "remito_id"),
)


class Viaje(Base):
    """Un viaje del ERP, con sus remitos."""

    __tablename__ = "viaje"

    id: Mapped[str] = mapped_column(String(LARGO_ID_OPACO), primary_key=True, default=_uuid)
    numero_legible: Mapped[str] = mapped_column(String(LARGO_NUMERO_LEGIBLE), unique=True)

    remitos: Mapped[list[Remito]] = relationship(
        secondary=viaje_remito, back_populates="viajes", lazy="selectin"
    )


class Remito(Base):
    """Un remito. Puede pertenecer a más de un viaje (VIA-05).

    `creado_en_utc` lo agrega la revisión `0002`, que es la que ejercita el camino batch de
    Alembic sobre datos sembrados.
    """

    __tablename__ = "remito"

    id: Mapped[str] = mapped_column(String(LARGO_ID_OPACO), primary_key=True, default=_uuid)
    numero: Mapped[str] = mapped_column(String(40), nullable=False)
    creado_en_utc: Mapped[str | None] = mapped_column(String(LARGO_INSTANTE_ISO), nullable=True)

    viajes: Mapped[list[Viaje]] = relationship(
        secondary=viaje_remito, back_populates="remitos", lazy="selectin"
    )
    articulos: Mapped[list[Articulo]] = relationship(
        back_populates="remito", lazy="selectin", cascade="all, delete-orphan"
    )

    # La restricción se nombra a mano para que coincida con la que crea la revisión 0002.
    __table_args__ = (UniqueConstraint("numero", name="uq_remito_numero"),)


class Articulo(Base):
    """Una línea del remito. Su peso teórico puede no existir, y eso es normal (D-31).

    `NULL` es un valor legítimo del negocio, no un dato faltante por error: el maestro de
    artículos del ERP tiene artículos sin peso cargado. Guardarlo como `0.0` produciría una
    diferencia enorme contra la balanza y un veredicto de auditoría falso.
    """

    __tablename__ = "articulo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    remito_id: Mapped[str] = mapped_column(ForeignKey("remito.id"), index=True)
    codigo: Mapped[str] = mapped_column(String(40), index=True)
    descripcion: Mapped[str] = mapped_column(String(200))
    peso_teorico_kg: Mapped[float | None] = mapped_column(Float, nullable=True)

    remito: Mapped[Remito] = relationship(back_populates="articulos")


# --------------------------------------------------------------------------- #
# La evidencia
# --------------------------------------------------------------------------- #


class Captura(Base):
    """Un disparo del botón.

    `viaje_id` es **nullable** (D-28): el portero saca la foto cuando el camión está
    delante y busca el viaje después. `autor_id` también (D-21): una expiración de sesión
    justo cuando el camión está sobre la balanza no puede costar la evidencia; el hecho de
    que no haya autor queda registrado y el panel de calidad lo cuenta.
    """

    __tablename__ = "captura"

    id: Mapped[str] = mapped_column(String(LARGO_ID_OPACO), primary_key=True, default=_uuid)
    numero_legible: Mapped[str] = mapped_column(String(LARGO_NUMERO_LEGIBLE), unique=True)
    viaje_id: Mapped[str | None] = mapped_column(ForeignKey("viaje.id"), nullable=True)
    autor_id: Mapped[str | None] = mapped_column(ForeignKey("usuario.id"), nullable=True)
    instante_objetivo_ns: Mapped[int] = mapped_column(Integer)
    ventana_vigente_ms: Mapped[float] = mapped_column(Float)
    fecha_local: Mapped[str] = mapped_column(String(LARGO_FECHA_LOCAL), index=True)
    version_app: Mapped[str] = mapped_column(String(20))
    version_esquema: Mapped[str] = mapped_column(String(20))

    items: Mapped[list[ItemEvidencia]] = relationship(
        back_populates="captura", lazy="selectin"
    )


class ItemEvidencia(Base):
    """Una foto y todo lo que hace falta para auditarla dentro de veinte años.

    Los 21 nombres canónicos son los de `dominio.evidencia.captura.ItemDeEvidencia`, mapeados
    uno a uno, más tres columnas propias del esquema: `id`, `captura_id` y `miniatura`.
    Dos mapeos no son triviales y el plan 01-02 los dejó anotados: `desfasaje_local_min`
    lleva un `Desfasaje` del dominio y la columna guarda su `.minutos`;
    `capturado_en_utc_iso` lleva un `InstanteUtc` y la columna guarda su `.texto`.
    """

    __tablename__ = "item_evidencia"

    # --- las tres columnas propias del esquema ---------------------------------- #
    id: Mapped[str] = mapped_column(String(LARGO_ID_OPACO), primary_key=True, default=_uuid)
    captura_id: Mapped[str] = mapped_column(ForeignKey("captura.id"), index=True)

    # --- los 21 nombres canónicos del dominio ----------------------------------- #
    ruta_relativa: Mapped[str] = mapped_column(String(LARGO_RUTA_RELATIVA), index=True)
    sha256: Mapped[str] = mapped_column(String(LARGO_SHA256), index=True)
    bytes_totales: Mapped[int] = mapped_column(Integer)
    capturado_en_utc_iso: Mapped[str] = mapped_column(String(LARGO_INSTANTE_ISO))
    desfasaje_local_min: Mapped[int] = mapped_column(Integer)
    fecha_local: Mapped[str] = mapped_column(String(LARGO_FECHA_LOCAL), index=True)
    instante_monotono_ns: Mapped[int] = mapped_column(Integer)
    desvio_ms: Mapped[float] = mapped_column(Float)
    ventana_vigente_ms: Mapped[float] = mapped_column(Float)
    perfil_de_flujo: Mapped[str] = mapped_column(String(20))
    resolucion: Mapped[str] = mapped_column(String(20))
    codec_origen: Mapped[str] = mapped_column(String(20))
    calidad_jpeg: Mapped[int] = mapped_column(Integer)
    camara_id: Mapped[str] = mapped_column(String(40))
    motor_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    version_modelo: Mapped[str | None] = mapped_column(String(40), nullable=True)
    sha256_modelo: Mapped[str | None] = mapped_column(String(LARGO_SHA256), nullable=True)
    version_app: Mapped[str] = mapped_column(String(20))
    version_esquema: Mapped[str] = mapped_column(String(20))
    autor_id: Mapped[str | None] = mapped_column(ForeignKey("usuario.id"), nullable=True)
    estado_integridad: Mapped[str] = mapped_column(String(16), index=True)

    # --- la tercera columna propia: ~15 KB en la base a propósito (D-04) --------- #
    miniatura: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    captura: Mapped[Captura] = relationship(back_populates="items")

    __table_args__ = (
        # La invariante real del negocio: un ítem por cámara y por captura. Se nombra a
        # mano porque la convención sólo toma la primera columna.
        UniqueConstraint(
            "captura_id", "camara_id", name="uq_item_evidencia_captura_id_camara_id"
        ),
        # La consulta de la Fase 9: qué sacó esta cámara este día.
        Index("ix_item_evidencia_camara_id_fecha_local", "camara_id", "fecha_local"),
    )


class Manifiesto(Base):
    """El hash de segundo nivel que sella una captura entera (D-08).

    `captura_id` es la clave primaria y no hay un `id` aparte: una captura tiene exactamente
    un manifiesto, y darle identidad propia abriría la puerta a que existan dos manifiestos
    de la misma captura diciendo cosas distintas.

    `incertidumbre_sello_utc_ms` entra en el hash y se persiste: el sello UTC absoluto
    **declara** su incertidumbre en vez de callarla.
    """

    __tablename__ = "manifiesto"

    captura_id: Mapped[str] = mapped_column(ForeignKey("captura.id"), primary_key=True)
    hash_manifiesto: Mapped[str] = mapped_column(String(LARGO_SHA256))
    algoritmo: Mapped[str] = mapped_column(String(20))
    campos_incluidos: Mapped[str] = mapped_column(String(500))
    incertidumbre_sello_utc_ms: Mapped[float] = mapped_column(Float)


class Lapida(Base):
    """El hueco con explicación que deja una purga manual (D-10).

    El sistema nunca llega a crear una lápida por su cuenta: no borra evidencia solo. Los
    cuatro campos son obligatorios porque una lápida sin motivo o sin autor es un agujero
    mudo, indistinguible de un borrado encubierto.
    """

    __tablename__ = "lapida"

    sha256: Mapped[str] = mapped_column(String(LARGO_SHA256), primary_key=True)
    motivo: Mapped[str] = mapped_column(String(500))
    autor_id: Mapped[str] = mapped_column(ForeignKey("usuario.id"))
    ocurrido_en_utc_iso: Mapped[str] = mapped_column(String(LARGO_INSTANTE_ISO))


# --------------------------------------------------------------------------- #
# Auditoría e identidad
# --------------------------------------------------------------------------- #


class BitacoraAuditoria(Base):
    """La cadena de custodia: cada registro encadena el hash del anterior (D-08).

    `hash_anterior` es nulo **sólo en el registro 1**. No se puede expresar esa restricción
    en el esquema sin un disparador, y un disparador sería una segunda verdad frente a
    `dominio.auditoria.registro`, que ya la sostiene y la prueba.
    """

    __tablename__ = "bitacora_auditoria"

    secuencia: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hash_anterior: Mapped[str | None] = mapped_column(String(LARGO_SHA256), nullable=True)
    hash_propio: Mapped[str] = mapped_column(String(LARGO_SHA256))
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("usuario.id"), nullable=True)
    accion: Mapped[str] = mapped_column(String(60))
    datos: Mapped[str] = mapped_column(String(2000))
    ocurrido_en_utc_iso: Mapped[str] = mapped_column(String(LARGO_INSTANTE_ISO))


class Usuario(Base):
    """Un usuario del sistema.

    `activo` en vez de borrado (D-25): un usuario que se va sigue siendo el autor de la
    evidencia que tomó, y borrarlo dejaría capturas firmadas por un identificador que ya no
    resuelve a nadie. `usuario_windows` se guarda **sólo como diagnóstico** (D-24): la
    identidad del sistema operativo no autentica a nadie en un puesto compartido.
    """

    __tablename__ = "usuario"

    id: Mapped[str] = mapped_column(String(LARGO_ID_OPACO), primary_key=True, default=_uuid)
    nombre_de_usuario: Mapped[str] = mapped_column(String(60), unique=True)
    hash_credencial: Mapped[str] = mapped_column(String(255))
    rol: Mapped[str] = mapped_column(String(20))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    usuario_windows: Mapped[str | None] = mapped_column(String(120), nullable=True)


# --------------------------------------------------------------------------- #
# Integraciones y despacho
# --------------------------------------------------------------------------- #


class PayloadCrudo(Base):
    """Lo que dijeron los sistemas externos, tal cual, comprimido y anonimizado (D-46).

    `operacion` y `cabeceras_comprimidas` existen desde la línea base porque el `Cassette`
    del plan 01-10 exporta desde esta tabla y porque el anonimizador tiene que alcanzar
    también a las cabeceras: una `Authorization: Basic …` versionada en git es un incidente.

    `anonimizado` es `NOT NULL` **sin valor por defecto**, y es deliberado: un default
    verdadero convertiría «nadie anonimizó» en «dice que sí». Quien inserta declara.

    El cuerpo y las cabeceras son **bytes de un JSON comprimido**, nunca un objeto
    serializado: el contrato de arquitectura prohíbe deserializar formatos que ejecutan
    código (T-01-07).
    """

    __tablename__ = "payload_crudo"

    id: Mapped[str] = mapped_column(String(LARGO_ID_OPACO), primary_key=True, default=_uuid)
    sistema: Mapped[str] = mapped_column(String(20))
    operacion: Mapped[str] = mapped_column(String(64))
    peticion: Mapped[str] = mapped_column(String(500))
    instante_utc_iso: Mapped[str] = mapped_column(String(LARGO_INSTANTE_ISO), index=True)
    codigo_respuesta: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duracion_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    cuerpo_comprimido: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    cabeceras_comprimidas: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    algoritmo_compresion: Mapped[str] = mapped_column(String(20))
    origen: Mapped[str] = mapped_column(String(12))
    anonimizado: Mapped[bool] = mapped_column(Boolean, nullable=False)


class Outbox(Base):
    """Los eventos de dominio, persistidos en la misma transacción que la evidencia (D-12).

    `despachado_en_utc_iso` nulo significa pendiente. Si el agregado publicara los eventos
    en vez de acumularlos, existirían eventos de capturas que no se guardaron.
    """

    __tablename__ = "outbox"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    captura_id: Mapped[str | None] = mapped_column(ForeignKey("captura.id"), nullable=True)
    tipo_evento: Mapped[str] = mapped_column(String(60))
    datos: Mapped[str] = mapped_column(String(2000))
    creado_en_utc_iso: Mapped[str] = mapped_column(String(LARGO_INSTANTE_ISO))
    despachado_en_utc_iso: Mapped[str | None] = mapped_column(
        String(LARGO_INSTANTE_ISO), nullable=True, index=True
    )


class Configuracion(Base):
    """La capa 2 de D-30: los parámetros que viven en la base, con quién y cuándo.

    Las columnas son exactamente las que `ConfiguracionEnBase` del plan 01-06 declaró en su
    `COLUMNAS_REQUERIDAS`. `clave` es la clave primaria porque la escritura de ese adaptador
    usa `ON CONFLICT(clave)`.

    **No hay columna `tipo`**, y es una decisión del plan 01-06 que este esquema honra: el
    tipo lo declara el catálogo del código y el valor se guarda como JSON. Una columna de
    tipo podría contradecir al catálogo, y entonces habría dos verdades sobre el mismo dato
    sin forma de saber a cuál creerle.
    """

    __tablename__ = "configuracion"

    clave: Mapped[str] = mapped_column(String(60), primary_key=True)
    valor: Mapped[str] = mapped_column(String(2000))
    cambiado_por: Mapped[str | None] = mapped_column(String(60), nullable=True)
    cambiado_en_utc_iso: Mapped[str | None] = mapped_column(
        String(LARGO_INSTANTE_ISO), nullable=True
    )
