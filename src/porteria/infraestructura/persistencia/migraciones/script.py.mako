"""${message}

Revisión: ${up_revision}
Revisión anterior: ${down_revision | comma,n}
Creada: ${create_date}

RECORDATORIOS DE ESTE PRODUCTO (D-33, D-34):

1. Toda revisión que reescriba una tabla usa `batch_alter_table` **con
   `naming_convention=CONVENCION`**. Sin la convención, SQLite no puede soltar las
   restricciones sin nombre y el bloque batch falla en la base del cliente, no acá.

2. Toda revisión nueva agrega **su propia prueba** en `tests/migracion/`, que siembra en la
   versión anterior, migra y compara **fila por fila**. El ayudante `comparar_volcados` de
   `tests/migracion/conftest.py` ya está listo: alcanza con parametrizarlo. Una migración
   sin prueba es una migración que se estrena sobre los años de evidencia de un cliente.

3. `downgrade()` se escribe de verdad o se deja fallando con un motivo explícito. Un
   `pass` silencioso promete una vuelta atrás que no existe.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from porteria.infraestructura.persistencia.sqlite.modelos import CONVENCION

# Identificadores de revisión. Numéricos con ceros a la izquierda: la versión de esquema
# del producto ES el identificador de la revisión cabeza (D-35).
revision: str = ${repr(up_revision)}
down_revision: str | None = ${repr(down_revision)}
branch_labels: str | None = ${repr(branch_labels)}
depends_on: str | None = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
