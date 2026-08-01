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
    # --- 3. La ruta de la base no vive en un archivo versionado ----------------- #
    Invariante(
        ruta="alembic.ini",
        modo="ausente",
        patron=r"sqlalchemy\.url",
        motivo=(
            "La ruta de la base la elige el cliente y se resuelve en tiempo de ejecución "
            "desde el archivo de arranque (D-30). Una URL versionada en el repositorio es "
            "la ruta de la máquina de quien la escribió: en el mejor caso migra una base "
            "que no es la del cliente, y en el peor crea una base vacía en otra carpeta y "
            "la migración «pasa» sin haber tocado los datos que había que migrar."
        ),
    ),
    # --- 4. El respaldo habla el idioma de WAL, no el de copiar archivos -------- #
    Invariante(
        ruta="src/porteria/infraestructura/persistencia/sqlite/respaldo.py",
        modo="presente",
        patron=r"\.backup\(",
        motivo=(
            "La copia se hace con la API de copia de SQLite, que recorre las páginas por "
            "dentro del motor e incluye lo que vive en el sidecar del diario. Es lo único "
            "que produce una copia consistente con el diario activo."
        ),
    ),
    Invariante(
        ruta="src/porteria/infraestructura/persistencia/sqlite/respaldo.py",
        modo="ausente",
        patron=r"\bshutil\b",
        motivo=(
            "Copiar el archivo de la base con las utilidades de copia de archivos deja "
            "afuera las transacciones confirmadas que todavía viven en el sidecar del "
            "diario. El resultado es un respaldo que **abre perfectamente** y al que le "
            "faltan las últimas capturas: nadie se entera hasta que hace falta restaurarlo, "
            "que es el peor momento posible para descubrirlo."
        ),
    ),
    # --- 5. El entorno de Alembic corre bajo las reglas correctas --------------- #
    Invariante(
        ruta="src/porteria/infraestructura/persistencia/migraciones/env.py",
        modo="presente",
        patron=r"render_as_batch=True",
        motivo=(
            "Sin `render_as_batch`, `alembic revision --autogenerate` produce sentencias "
            "ALTER que SQLite no soporta. La migración generada se ve bien en el "
            "repositorio y falla al ejecutarse en la base del cliente."
        ),
    ),
    Invariante(
        ruta="src/porteria/infraestructura/persistencia/migraciones/env.py",
        modo="presente",
        patron=r"para_migracion=True",
        motivo=(
            "El motor de migraciones es un motor **dedicado** con las llaves foráneas "
            "apagadas. Con las llaves encendidas, todo bloque batch falla al soltar la "
            "tabla que está reescribiendo si alguien la referencia. Las dos alternativas "
            "obvias están descartadas con la medición en el docstring de `sqlite/motor.py`."
        ),
    ),
    Invariante(
        ruta="src/porteria/infraestructura/persistencia/sqlite/integridad.py",
        modo="presente",
        patron=r"foreign_key_check",
        motivo=(
            "Durante el bloque batch las llaves foráneas están apagadas, así que SQLite no "
            "valida nada mientras la migración corre. Ésta es la única comprobación que "
            "detecta una referencia que quedó colgando, y el final es el único momento en "
            "que se puede hacer. Es la mitad del Criterio de Éxito 6."
        ),
    ),
    Invariante(
        ruta="src/porteria/infraestructura/persistencia/sqlite/integridad.py",
        modo="presente",
        patron=r"integrity_check",
        motivo=(
            "La segunda mitad de la comprobación obligatoria: detecta la base dañada a "
            "nivel de páginas, que es lo que puede dejar una migración interrumpida por un "
            "corte de energía."
        ),
    ),
    Invariante(
        ruta="src/porteria/infraestructura/persistencia/migraciones/env.py",
        modo="presente",
        patron=r"comprobar_integridad\(",
        motivo=(
            "Que la comprobación exista no sirve de nada si la migración no la invoca. "
            "Esta invariante cierra el otro lado: `env.py` tiene que **llamarla** al "
            "terminar el `upgrade`. La función vive en `sqlite/integridad.py` y no acá "
            "porque `env.py` no es importable fuera de una corrida de Alembic, y una "
            "comprobación que ninguna prueba puede invocar es una que nadie vio fallar."
        ),
    ),
    # --- 6. La revisión que ejercita el camino batch ---------------------------- #
    Invariante(
        ruta="src/porteria/infraestructura/persistencia/migraciones/versions/0002_creado_en_utc.py",
        modo="presente",
        patron=r"batch_alter_table",
        motivo=(
            "Sin una revisión que reescriba una tabla de verdad, DIS-05 no tiene nada real "
            "que verificar: una línea base sola sólo demuestra que `CREATE TABLE` funciona."
        ),
    ),
    Invariante(
        ruta="src/porteria/infraestructura/persistencia/migraciones/versions/0002_creado_en_utc.py",
        modo="presente",
        patron=r"naming_convention",
        motivo=(
            "El bloque batch necesita la convención de nombres para poder reconstruir las "
            "restricciones al recrear la tabla. Sin ella, la tabla reflejada las trae sin "
            "nombre y el bloque falla en la base del cliente, no en el repositorio."
        ),
    ),
)
