"""Línea base: el esquema completo que el cliente va a tener instalado.

Revisión: 0001
Revisión anterior: ninguna

**Lo que se omita acá cuesta una migración sobre datos productivos.** Por eso la línea base
nace con todo lo que D-27 declaró no retrofiteable, incluidas las columnas que hoy no llena
nadie: `payload_crudo.operacion` y `payload_crudo.cabeceras_comprimidas` las necesita el
cassette del plan 01-10, y los tres campos de trazabilidad de inferencia de `item_evidencia`
se pueblan recién desde la Fase 4.

**`remito.numero` nace sin restricción de unicidad y admitiendo nulo, a propósito.** Es lo
que le da a la revisión `0002` un camino batch **real** que ejercitar sobre datos sembrados.
Una línea base sola no demuestra que la maquinaria de migración preserve nada: demostraría
solamente que `CREATE TABLE` funciona.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None

#: Largos de columna, iguales a los de `sqlite/modelos.py`.
ID_OPACO = 36
NUMERO_LEGIBLE = 20
SHA256 = 64
INSTANTE_ISO = 32
FECHA_LOCAL = 10
RUTA_RELATIVA = 255


def upgrade() -> None:
    # --- Identidad (D-24, D-25) --------------------------------------------- #
    op.create_table(
        "usuario",
        sa.Column("id", sa.String(ID_OPACO), nullable=False),
        sa.Column("nombre_de_usuario", sa.String(60), nullable=False),
        sa.Column("hash_credencial", sa.String(255), nullable=False),
        sa.Column("rol", sa.String(20), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("usuario_windows", sa.String(120), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_usuario"),
        sa.UniqueConstraint("nombre_de_usuario", name="uq_usuario_nombre_de_usuario"),
    )

    # --- Viaje ↔ Remito: la relación muchas a muchas (VIA-05) --------------- #
    op.create_table(
        "viaje",
        sa.Column("id", sa.String(ID_OPACO), nullable=False),
        sa.Column("numero_legible", sa.String(NUMERO_LEGIBLE), nullable=False),
        # El texto tal como llegó del ERP o de la carga manual, sin normalizar: es lo que
        # permite auditar después la traducción a la forma canónica.
        sa.Column("patente", sa.String(20), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_viaje"),
        sa.UniqueConstraint("numero_legible", name="uq_viaje_numero_legible"),
    )

    # `numero` nullable y sin unicidad: la revisión 0002 es la que las agrega, y es lo que
    # le da un camino batch real que ejercitar.
    op.create_table(
        "remito",
        sa.Column("id", sa.String(ID_OPACO), nullable=False),
        sa.Column("numero", sa.String(40), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_remito"),
    )

    op.create_table(
        "viaje_remito",
        sa.Column("viaje_id", sa.String(ID_OPACO), nullable=False),
        sa.Column("remito_id", sa.String(ID_OPACO), nullable=False),
        sa.ForeignKeyConstraint(
            ["viaje_id"], ["viaje.id"], name="fk_viaje_remito_viaje_id_viaje", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["remito_id"],
            ["remito.id"],
            name="fk_viaje_remito_remito_id_remito",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("viaje_id", "remito_id", name="pk_viaje_remito"),
    )
    # El sentido inverso también se consulta: dado un remito, en qué viajes salió.
    op.create_index("ix_viaje_remito_remito_id", "viaje_remito", ["remito_id"], unique=False)

    # `peso_teorico_kg` nullable: `NULL` es un valor legítimo del negocio (D-31).
    op.create_table(
        "articulo",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("remito_id", sa.String(ID_OPACO), nullable=False),
        sa.Column("codigo", sa.String(40), nullable=False),
        sa.Column("descripcion", sa.String(200), nullable=False),
        sa.Column("peso_teorico_kg", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["remito_id"], ["remito.id"], name="fk_articulo_remito_id_remito"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_articulo"),
    )
    op.create_index("ix_articulo_remito_id", "articulo", ["remito_id"], unique=False)
    op.create_index("ix_articulo_codigo", "articulo", ["codigo"], unique=False)

    # --- La evidencia -------------------------------------------------------- #
    # `viaje_id` y `autor_id` nullable: la captura nace autónoma (D-28) y no se bloquea
    # por falta de sesión (D-21).
    op.create_table(
        "captura",
        sa.Column("id", sa.String(ID_OPACO), nullable=False),
        sa.Column("numero_legible", sa.String(NUMERO_LEGIBLE), nullable=False),
        sa.Column("viaje_id", sa.String(ID_OPACO), nullable=True),
        sa.Column("autor_id", sa.String(ID_OPACO), nullable=True),
        sa.Column("instante_objetivo_ns", sa.Integer(), nullable=False),
        sa.Column("ventana_vigente_ms", sa.Float(), nullable=False),
        sa.Column("fecha_local", sa.String(FECHA_LOCAL), nullable=False),
        sa.Column("version_app", sa.String(20), nullable=False),
        sa.Column("version_esquema", sa.String(20), nullable=False),
        sa.ForeignKeyConstraint(["viaje_id"], ["viaje.id"], name="fk_captura_viaje_id_viaje"),
        sa.ForeignKeyConstraint(["autor_id"], ["usuario.id"], name="fk_captura_autor_id_usuario"),
        sa.PrimaryKeyConstraint("id", name="pk_captura"),
        sa.UniqueConstraint("numero_legible", name="uq_captura_numero_legible"),
    )
    op.create_index("ix_captura_fecha_local", "captura", ["fecha_local"], unique=False)

    # `ruta_relativa` **sin** UNIQUE: el almacén está direccionado por contenido, así que
    # dos capturas de bytes idénticos comparten archivo legítimamente (T-01-27). La
    # unicidad vive en (captura_id, camara_id), que es la invariante real del negocio.
    op.create_table(
        "item_evidencia",
        sa.Column("id", sa.String(ID_OPACO), nullable=False),
        sa.Column("captura_id", sa.String(ID_OPACO), nullable=False),
        sa.Column("ruta_relativa", sa.String(RUTA_RELATIVA), nullable=False),
        sa.Column("sha256", sa.String(SHA256), nullable=False),
        sa.Column("bytes_totales", sa.Integer(), nullable=False),
        # `String(32)` y no un tipo de fecha con zona: sobre SQLite ese tipo pierde el
        # `tzinfo` al leer y desplaza todo el histórico en silencio.
        sa.Column("capturado_en_utc_iso", sa.String(INSTANTE_ISO), nullable=False),
        sa.Column("desfasaje_local_min", sa.Integer(), nullable=False),
        sa.Column("fecha_local", sa.String(FECHA_LOCAL), nullable=False),
        sa.Column("instante_monotono_ns", sa.Integer(), nullable=False),
        sa.Column("desvio_ms", sa.Float(), nullable=False),
        sa.Column("ventana_vigente_ms", sa.Float(), nullable=False),
        sa.Column("perfil_de_flujo", sa.String(20), nullable=False),
        sa.Column("resolucion", sa.String(20), nullable=False),
        sa.Column("codec_origen", sa.String(20), nullable=False),
        sa.Column("calidad_jpeg", sa.Integer(), nullable=False),
        sa.Column("camara_id", sa.String(40), nullable=False),
        sa.Column("motor_id", sa.String(40), nullable=True),
        sa.Column("version_modelo", sa.String(40), nullable=True),
        sa.Column("sha256_modelo", sa.String(SHA256), nullable=True),
        sa.Column("version_app", sa.String(20), nullable=False),
        sa.Column("version_esquema", sa.String(20), nullable=False),
        sa.Column("autor_id", sa.String(ID_OPACO), nullable=True),
        sa.Column("estado_integridad", sa.String(16), nullable=False),
        # ~15 KB en la base a propósito (D-04). Las imágenes completas van al filesystem.
        sa.Column("miniatura", sa.LargeBinary(), nullable=True),
        sa.ForeignKeyConstraint(
            ["captura_id"], ["captura.id"], name="fk_item_evidencia_captura_id_captura"
        ),
        sa.ForeignKeyConstraint(
            ["autor_id"], ["usuario.id"], name="fk_item_evidencia_autor_id_usuario"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_item_evidencia"),
        sa.UniqueConstraint(
            "captura_id", "camara_id", name="uq_item_evidencia_captura_id_camara_id"
        ),
    )
    op.create_index("ix_item_evidencia_captura_id", "item_evidencia", ["captura_id"], unique=False)
    op.create_index(
        "ix_item_evidencia_ruta_relativa", "item_evidencia", ["ruta_relativa"], unique=False
    )
    op.create_index("ix_item_evidencia_sha256", "item_evidencia", ["sha256"], unique=False)
    op.create_index(
        "ix_item_evidencia_fecha_local", "item_evidencia", ["fecha_local"], unique=False
    )
    op.create_index(
        "ix_item_evidencia_camara_id_fecha_local",
        "item_evidencia",
        ["camara_id", "fecha_local"],
        unique=False,
    )
    op.create_index(
        "ix_item_evidencia_estado_integridad", "item_evidencia", ["estado_integridad"], unique=False
    )

    # Una captura, un manifiesto: `captura_id` es la clave primaria (D-08).
    op.create_table(
        "manifiesto",
        sa.Column("captura_id", sa.String(ID_OPACO), nullable=False),
        sa.Column("hash_manifiesto", sa.String(SHA256), nullable=False),
        sa.Column("algoritmo", sa.String(20), nullable=False),
        sa.Column("campos_incluidos", sa.String(500), nullable=False),
        sa.Column("incertidumbre_sello_utc_ms", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["captura_id"], ["captura.id"], name="fk_manifiesto_captura_id_captura"
        ),
        sa.PrimaryKeyConstraint("captura_id", name="pk_manifiesto"),
    )

    # El hueco con explicación que deja una purga manual (D-10).
    op.create_table(
        "lapida",
        sa.Column("sha256", sa.String(SHA256), nullable=False),
        sa.Column("motivo", sa.String(500), nullable=False),
        sa.Column("autor_id", sa.String(ID_OPACO), nullable=False),
        sa.Column("ocurrido_en_utc_iso", sa.String(INSTANTE_ISO), nullable=False),
        sa.ForeignKeyConstraint(["autor_id"], ["usuario.id"], name="fk_lapida_autor_id_usuario"),
        sa.PrimaryKeyConstraint("sha256", name="pk_lapida"),
    )

    # --- Auditoría (D-08) ---------------------------------------------------- #
    # `hash_anterior` nullable: es nulo sólo en el registro 1.
    op.create_table(
        "bitacora_auditoria",
        sa.Column("secuencia", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hash_anterior", sa.String(SHA256), nullable=True),
        sa.Column("hash_propio", sa.String(SHA256), nullable=False),
        sa.Column("actor_id", sa.String(ID_OPACO), nullable=True),
        sa.Column("accion", sa.String(60), nullable=False),
        sa.Column("datos", sa.String(2000), nullable=False),
        sa.Column("ocurrido_en_utc_iso", sa.String(INSTANTE_ISO), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["usuario.id"], name="fk_bitacora_auditoria_actor_id_usuario"
        ),
        sa.PrimaryKeyConstraint("secuencia", name="pk_bitacora_auditoria"),
    )

    # --- Integraciones y despacho ------------------------------------------- #
    # `anonimizado` NOT NULL **sin default**: quien inserta declara si anonimizó. Un
    # default verdadero convertiría «nadie anonimizó» en «dice que sí» (D-46, T-01-04).
    op.create_table(
        "payload_crudo",
        sa.Column("id", sa.String(ID_OPACO), nullable=False),
        sa.Column("sistema", sa.String(20), nullable=False),
        sa.Column("operacion", sa.String(64), nullable=False),
        sa.Column("peticion", sa.String(500), nullable=False),
        sa.Column("instante_utc_iso", sa.String(INSTANTE_ISO), nullable=False),
        sa.Column("codigo_respuesta", sa.Integer(), nullable=True),
        sa.Column("duracion_ms", sa.Float(), nullable=True),
        sa.Column("cuerpo_comprimido", sa.LargeBinary(), nullable=True),
        sa.Column("cabeceras_comprimidas", sa.LargeBinary(), nullable=True),
        sa.Column("algoritmo_compresion", sa.String(20), nullable=False),
        sa.Column("origen", sa.String(12), nullable=False),
        sa.Column("anonimizado", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_payload_crudo"),
    )
    op.create_index(
        "ix_payload_crudo_instante_utc_iso", "payload_crudo", ["instante_utc_iso"], unique=False
    )

    op.create_table(
        "outbox",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("captura_id", sa.String(ID_OPACO), nullable=True),
        sa.Column("tipo_evento", sa.String(60), nullable=False),
        sa.Column("datos", sa.String(2000), nullable=False),
        sa.Column("creado_en_utc_iso", sa.String(INSTANTE_ISO), nullable=False),
        sa.Column("despachado_en_utc_iso", sa.String(INSTANTE_ISO), nullable=True),
        sa.ForeignKeyConstraint(
            ["captura_id"], ["captura.id"], name="fk_outbox_captura_id_captura"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_outbox"),
    )
    op.create_index(
        "ix_outbox_despachado_en_utc_iso", "outbox", ["despachado_en_utc_iso"], unique=False
    )

    # La capa 2 de D-30. Las columnas son el contrato que declaró el plan 01-06 en
    # `COLUMNAS_REQUERIDAS`; `clave` es la primaria porque ese adaptador usa ON CONFLICT.
    op.create_table(
        "configuracion",
        sa.Column("clave", sa.String(60), nullable=False),
        sa.Column("valor", sa.String(2000), nullable=False),
        sa.Column("cambiado_por", sa.String(60), nullable=True),
        sa.Column("cambiado_en_utc_iso", sa.String(INSTANTE_ISO), nullable=True),
        sa.PrimaryKeyConstraint("clave", name="pk_configuracion"),
    )


def downgrade() -> None:
    """Deshace la línea base entera. En orden inverso por las llaves foráneas."""
    op.drop_table("configuracion")
    op.drop_index("ix_outbox_despachado_en_utc_iso", table_name="outbox")
    op.drop_table("outbox")
    op.drop_index("ix_payload_crudo_instante_utc_iso", table_name="payload_crudo")
    op.drop_table("payload_crudo")
    op.drop_table("bitacora_auditoria")
    op.drop_table("lapida")
    op.drop_table("manifiesto")
    op.drop_index("ix_item_evidencia_estado_integridad", table_name="item_evidencia")
    op.drop_index("ix_item_evidencia_camara_id_fecha_local", table_name="item_evidencia")
    op.drop_index("ix_item_evidencia_fecha_local", table_name="item_evidencia")
    op.drop_index("ix_item_evidencia_sha256", table_name="item_evidencia")
    op.drop_index("ix_item_evidencia_ruta_relativa", table_name="item_evidencia")
    op.drop_index("ix_item_evidencia_captura_id", table_name="item_evidencia")
    op.drop_table("item_evidencia")
    op.drop_index("ix_captura_fecha_local", table_name="captura")
    op.drop_table("captura")
    op.drop_index("ix_articulo_codigo", table_name="articulo")
    op.drop_index("ix_articulo_remito_id", table_name="articulo")
    op.drop_table("articulo")
    op.drop_index("ix_viaje_remito_remito_id", table_name="viaje_remito")
    op.drop_table("viaje_remito")
    op.drop_table("remito")
    op.drop_table("viaje")
    op.drop_table("usuario")
