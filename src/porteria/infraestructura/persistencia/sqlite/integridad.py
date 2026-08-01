"""La comprobación obligatoria que corre al terminar cada migración.

**Vive acá y no dentro del entorno de Alembic para poder probarla.** El `env.py` de Alembic
no es un módulo importable: se ejecuta con el contexto de una migración en curso y acceder a
su configuración fuera de una corrida falla. Una comprobación que no se puede invocar desde
una prueba es una comprobación que nadie vio fallar nunca, y ésta es la mitad del Criterio
de Éxito 6 — precisamente la que no puede ser decorativa.

**Por qué hace falta.** Durante un bloque batch las llaves foráneas están apagadas, porque
sin apagarlas SQLite no deja soltar la tabla que se está reescribiendo. La consecuencia es
que mientras la migración corre **no se valida nada**: una fila que queda apuntando a otra
que ya no existe pasa sin ruido, la migración termina «bien», la base abre «bien», y el
problema aparece meses después en una auditoría. El final de la migración es el único
momento en que se puede detectar.
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

__all__ = [
    "PRAGMA_REFERENCIAS",
    "PRAGMA_PAGINAS",
    "MigracionDejoLaBaseInconsistente",
    "comprobar_integridad",
]

#: Detecta filas que referencian a otras que no existen. Literal, sin interpolar.
PRAGMA_REFERENCIAS = "PRAGMA foreign_key_check"

#: Detecta daño a nivel de páginas, que es lo que deja una migración interrumpida.
PRAGMA_PAGINAS = "PRAGMA integrity_check"

#: Cuántas violaciones se muestran en el mensaje. Volcar miles no ayuda a nadie.
VIOLACIONES_A_MOSTRAR = 10


class MigracionDejoLaBaseInconsistente(RuntimeError):
    """La migración terminó pero la base no pasa las comprobaciones de integridad."""


def comprobar_integridad(conexion: Connection) -> None:
    """Corre las dos comprobaciones de SQLite y falla si alguna no está limpia.

    Args:
        conexion: Una conexión abierta sobre la base recién migrada.

    Raises:
        MigracionDejoLaBaseInconsistente: si hay referencias colgadas o la base está dañada.
            El mensaje dice qué pasó y qué hacer, porque lo va a leer alguien en una planta
            sin área de sistemas (UI-05).
    """
    violaciones = list(conexion.exec_driver_sql(PRAGMA_REFERENCIAS))
    if violaciones:
        raise MigracionDejoLaBaseInconsistente(
            "La migración terminó dejando referencias colgadas: hay filas que apuntan a "
            "otras que no existen.\n"
            f"Violaciones ({len(violaciones)}): {violaciones[:VIOLACIONES_A_MOSTRAR]}\n"
            "Durante una migración batch las llaves foráneas están apagadas, así que SQLite "
            "no avisa mientras corre; ésta es la única comprobación que lo detecta.\n"
            "Qué hacer: no seguir usando esta base. Restaurar la copia previa, que la orden "
            "`migrar` deja siempre salvo que se le pase --sin-respaldo."
        )

    estado = conexion.exec_driver_sql(PRAGMA_PAGINAS).scalar()
    if estado != "ok":
        raise MigracionDejoLaBaseInconsistente(
            f"La comprobación de integridad de la base no dio «ok» sino «{estado}».\n"
            "La base está dañada a nivel de páginas: suele ser una migración interrumpida "
            "por un corte de energía o un problema del disco.\n"
            "Qué hacer: no seguir usando esta base. Restaurar la copia previa a la "
            "migración."
        )
