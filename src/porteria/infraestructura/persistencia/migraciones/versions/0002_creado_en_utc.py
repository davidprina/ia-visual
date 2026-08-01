"""Agrega `remito.creado_en_utc` y endurece `remito.numero`.

Revisión: 0002
Revisión anterior: 0001

**Esta revisión existe para ejercitar el camino batch de verdad.** La línea base sola
demostraría únicamente que `CREATE TABLE` funciona; lo que DIS-05 pide verificar es que la
maquinaria de migración **preserve datos** cuando SQLite tiene que reescribir una tabla
entera, que es lo que pasa acá: `remito` está referenciada por `viaje_remito` y por
`articulo`, así que el `DROP TABLE` intermedio del bloque batch es exactamente el punto
donde una configuración equivocada del motor revienta.

`add_column` va **fuera** del bloque batch a propósito: agregar una columna es la única
alteración que SQLite soporta de forma nativa, y hacerla dentro del batch obligaría a una
reescritura extra sin ninguna ganancia.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from porteria.infraestructura.persistencia.sqlite.modelos import CONVENCION

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("remito", sa.Column("creado_en_utc", sa.String(32), nullable=True))

    # `naming_convention` es obligatoria: sin ella, la tabla reflejada trae las
    # restricciones sin nombre y el bloque batch no puede reconstruirlas al recrear la
    # tabla. El fallo aparece en la base del cliente, no acá.
    with op.batch_alter_table("remito", naming_convention=CONVENCION) as lote:
        lote.alter_column("numero", existing_type=sa.String(40), nullable=False)
        lote.create_unique_constraint("uq_remito_numero", ["numero"])


def downgrade() -> None:
    with op.batch_alter_table("remito", naming_convention=CONVENCION) as lote:
        lote.drop_constraint("uq_remito_numero", type_="unique")
        lote.alter_column("numero", existing_type=sa.String(40), nullable=True)

    op.drop_column("remito", "creado_en_utc")
