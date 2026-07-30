"""Los tres estados en los que puede estar un ítem de evidencia (D-09, D-10).

`INTEGRA` — la huella recalculada coincide con la persistida.

`COMPROMETIDA` — no coinciden. D-09 es explícito y la regla vale para toda la aplicación:
la evidencia comprometida **se marca y se muestra así en toda pantalla, listado y
exportación, y nunca se borra ni se oculta**. El hallazgo entra además en la bitácora
encadenada con su instante y su ruta. Ocultarla sería destruir justamente el dato que
prueba que hubo manipulación.

`PURGADA` — el archivo ya no está porque alguien ejecutó la purga manual por antigüedad, y
en su lugar quedó una `Lapida` con hash, motivo, autor e instante (D-10). Es un hueco
**con explicación**, que es lo que distingue una purga de un borrado. El sistema nunca
llega a este estado por su cuenta: no borra evidencia por sí solo.

`evaluar` es una función pura sin efectos: dice qué estado corresponde y nada más. Marcar,
registrar en la bitácora y mostrar son responsabilidades de las capas de arriba.
"""

from __future__ import annotations

from enum import StrEnum

from porteria.dominio.evidencia.huella import HuellaDeIntegridad

__all__ = ["EstadoDeIntegridad", "evaluar"]


class EstadoDeIntegridad(StrEnum):
    """Estado de integridad de un ítem de evidencia.

    `StrEnum` para que la columna del esquema guarde `INTEGRA` y no la representación del
    objeto, y para que la comparación con el texto leído de la base funcione sin
    conversiones — que es donde se cuelan los errores silenciosos.
    """

    INTEGRA = "INTEGRA"
    COMPROMETIDA = "COMPROMETIDA"
    PURGADA = "PURGADA"


def evaluar(
    huella_persistida: HuellaDeIntegridad,
    huella_recalculada: HuellaDeIntegridad,
) -> EstadoDeIntegridad:
    """Compara la huella guardada con la del archivo tal como está hoy.

    Args:
        huella_persistida: La que se guardó cuando se tomó la evidencia.
        huella_recalculada: La que resulta de volver a hashear el archivo ahora.

    Returns:
        `INTEGRA` si coinciden, `COMPROMETIDA` si no. Nunca `PURGADA`: ese estado lo fija
        la purga manual junto con su lápida, no una comparación de huellas.
    """
    if huella_persistida.coincide_con(huella_recalculada):
        return EstadoDeIntegridad.INTEGRA
    return EstadoDeIntegridad.COMPROMETIDA
