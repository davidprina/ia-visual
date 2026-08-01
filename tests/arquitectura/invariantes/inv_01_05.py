"""Invariantes declaradas por el plan 01-05: el esquema, el motor y las migraciones.

Todas cierran modos de fallo que **ninguna prueba funcional puede detectar**, porque
describen cómo está escrito el código y no qué devuelve. Los tres casos son del mismo tipo:
el código equivocado pasa en verde hoy y falla en la instalación del cliente meses después.

1. **El tipo de fecha con zona horaria de SQLAlchemy no puede aparecer en el esquema.**
   Sobre SQLite ese tipo escribe sin la zona y al leer devuelve un instante sin `tzinfo`
   (Pitfall 4). Una prueba que escribe y lee en el mismo proceso pasa igual, porque compara
   el desplazado contra el desplazado. Lo que se rompe es la interpretación del histórico
   dentro de dos años, y para entonces el dato ya está guardado mal.

2. **La fábrica declarativa vieja no puede aparecer.** El estilo tipado 2.0 es lo que hace
   que las columnas sean visibles para el verificador de tipos y lo que mantiene todo el SQL
   parametrizado por construcción (T-01-05). Mezclar los dos estilos funciona hasta que
   alguien agrega una consulta a mano.

3. **El prefijo de URL de SQLite no puede aparecer en el módulo del motor.** Concatenarlo
   con la ruta es el antipatrón que rompe con espacios y acentos — es decir, en la
   configuración que este producto tiene por diseño (DIS-06). `URL.create` lo resuelve.

Nótese que la prosa de estos módulos explica por qué esas expresiones no deben existir
**sin escribirlas**: si las escribiera, invalidaría su propia invariante. El blanqueo de
comentarios y docstrings de la maquinaria protege del caso general, pero un literal de
cadena sí cuenta, así que la disciplina sigue haciendo falta en el código.
"""

from tests.arquitectura.invariantes import Invariante

INVARIANTES: tuple[Invariante, ...] = (
    # --- 1. El esquema no puede hablar el idioma que SQLite no sostiene ---------- #
    Invariante(
        ruta="src/porteria/infraestructura/persistencia/sqlite/modelos.py",
        modo="ausente",
        patron=r"DateTime\(\s*timezone\s*=\s*True\s*\)",
        motivo=(
            "El tipo de fecha con zona horaria de SQLAlchemy **pierde el `tzinfo` al leer** "
            "en SQLite: el dialecto serializa a texto sin offset y reconstruye sin zona, "
            "con lo cual todo el histórico se desplaza en silencio. Los instantes se "
            "persisten como texto ISO-8601 con offset (`capturado_en_utc_iso`, `String(32)`) "
            "más el desfasaje en minutos en una columna aparte. Señal de alerta en "
            "producción: capturas de madrugada que aparecen con la fecha del día anterior."
        ),
    ),
    Invariante(
        ruta="src/porteria/infraestructura/persistencia/sqlite/modelos.py",
        modo="ausente",
        patron=r"declarative_base\(\)",
        motivo=(
            "El esquema está en estilo tipado 2.0 (`DeclarativeBase` + `Mapped[]` + "
            "`mapped_column`). La fábrica vieja deja las columnas invisibles para el "
            "verificador de tipos, que es justamente lo que evita persistir la evidencia "
            "contra el viaje equivocado, y convive mal con el resto del esquema."
        ),
    ),
    Invariante(
        ruta="src/porteria/infraestructura/persistencia/sqlite/modelos.py",
        modo="presente",
        patron=r"naming_convention",
        motivo=(
            "La convención de nombres sobre el `MetaData` es **obligatoria**: sin ella "
            "SQLite guarda las restricciones sin nombre y `batch_alter_table` no puede "
            "soltarlas, así que ninguna migración futura puede reescribir una tabla. Es la "
            "diferencia entre poder migrar el esquema del cliente y no poder."
        ),
    ),
    Invariante(
        ruta="src/porteria/infraestructura/persistencia/sqlite/modelos.py",
        modo="presente",
        patron=r"viaje_remito",
        motivo=(
            "La tabla de asociación es la materialización de VIA-05: Viaje↔Remito es "
            "muchas a muchas desde el diseño. Si desapareciera, el caso real de la Fase 6 "
            "—un viaje con tres remitos, uno compartido con otro viaje— dejaría de poder "
            "representarse, y corregirlo después obliga a migrar un esquema con años de "
            "datos productivos."
        ),
    ),
    # --- 2. El motor arma la URL con la fábrica, nunca por concatenación --------- #
    Invariante(
        ruta="src/porteria/infraestructura/persistencia/sqlite/motor.py",
        modo="ausente",
        patron=r"sqlite:///",
        motivo=(
            "Concatenar el prefijo de esquema de SQLite con la ruta rompe cuando la ruta "
            "tiene espacios o acentos, que es exactamente la configuración que este "
            "producto tiene por diseño (DIS-06): la ruta de la base la elige el cliente. "
            "`URL.create(\"sqlite\", database=str(ruta))` se ocupa del escapado. Señal de "
            "alerta: la base «no se puede abrir» sólo en las instalaciones cuyo cliente "
            "puso la carpeta en «Mis Documentos»."
        ),
    ),
)
