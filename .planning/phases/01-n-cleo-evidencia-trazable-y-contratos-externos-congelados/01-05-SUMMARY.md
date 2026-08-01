---
phase: 01-n-cleo-evidencia-trazable-y-contratos-externos-congelados
plan: 05
subsystem: persistencia-y-migraciones
tags: [sqlite, wal, alembic, batch-alter-table, esquema-no-retrofiteable, migracion-que-preserva, respaldo, tdd]

# Grafo de dependencias
requires:
  - phase: 01-01
    provides: proyecto uv, árbol de paquetes, compuerta única, fixtures de ruta hostil, maquinaria de invariantes, contrato de descubrimiento de cli/ordenes/
  - phase: 01-02
    provides: "los 21 nombres canónicos de `ItemDeEvidencia`, los 5 del manifiesto, y los dos mapeos no triviales (`desfasaje_local_min` → `.minutos`, `capturado_en_utc_iso` → `.texto`)"
provides:
  - "`crear_motor(ruta_db, *, para_migracion=False)` con los cuatro PRAGMA verificados leyéndolos de la base"
  - "Esquema completo no retrofiteable: 13 tablas en estilo tipado 2.0 con convención de nombres"
  - "Viaje↔Remito muchas a muchas y peso teórico nulable con estado derivado, ejercitados"
  - "`item_evidencia` con 24 columnas mapeadas uno a uno contra el dominio, unicidad en `(captura_id, camara_id)` y `ruta_relativa` NO única"
  - "`payload_crudo` con `operacion`, `cabeceras_comprimidas` y `anonimizado` NOT NULL sin default, listo para el cassette del plan 01-10"
  - "Tabla `configuracion` que honra `COLUMNAS_REQUERIDAS` del plan 01-06, probada con el adaptador real"
  - "Dos revisiones de Alembic (`0001`, `0002`) y el `env.py` con motor dedicado y comprobación obligatoria"
  - "`comprobar_integridad` como función importable y probada, no embebida en el entorno de Alembic"
  - "`respaldar(...)` con la API de copia de SQLite, consistente con WAL activo"
  - "`version_esquema.comprobar` que se niega a abrir una base más nueva nombrando las dos versiones"
  - "Orden de consola `porteria migrar` con `--hasta`, `--sin-respaldo`, `--base-de-datos` y `--json`"
  - "`sembrar_casos_feos`, `volcar` y `comparar_volcados` listos para que la revisión 0003 sólo parametrice"
affects: [01-07-rebanada-vertical, 01-08-adaptadores-externos, 01-09, 01-10-contratos-externos, 02-camaras-ip, 11-instalador]

# Seguimiento técnico
tech-stack:
  added: []
  patterns:
    - "Motor de migraciones **dedicado** en vez de manipular PRAGMA dentro de la transacción: no depende del orden de las operaciones de la revisión"
    - "Los instantes se persisten como texto ISO-8601 con offset más un entero de minutos aparte, nunca con el tipo de fecha con zona horaria"
    - "La versión de esquema **es** el identificador de la revisión cabeza de Alembic: una sola verdad sobre en qué versión está la base"
    - "Unicidad que modela el negocio y no el almacenamiento: `(captura_id, camara_id)` y no la ruta del archivo"
    - "La comparación de volcados vive en un solo lugar y la usan el caso feliz y el adverso"
    - "Una red de seguridad se protege de sí misma: la poda nunca puede borrar la copia que se acaba de tomar"

key-files:
  created:
    - alembic.ini
    - src/porteria/infraestructura/persistencia/sqlite/motor.py
    - src/porteria/infraestructura/persistencia/sqlite/modelos.py
    - src/porteria/infraestructura/persistencia/sqlite/version_esquema.py
    - src/porteria/infraestructura/persistencia/sqlite/respaldo.py
    - src/porteria/infraestructura/persistencia/sqlite/integridad.py
    - src/porteria/infraestructura/persistencia/migraciones/__init__.py
    - src/porteria/infraestructura/persistencia/migraciones/env.py
    - src/porteria/infraestructura/persistencia/migraciones/script.py.mako
    - src/porteria/infraestructura/persistencia/migraciones/versions/0001_linea_base.py
    - src/porteria/infraestructura/persistencia/migraciones/versions/0002_creado_en_utc.py
    - src/porteria/cli/ordenes/migrar.py
    - tests/integracion/test_motor_sqlite.py
    - tests/integracion/test_esquema_viaje_remito.py
    - tests/integracion/test_esquema_payload_crudo.py
    - tests/migracion/conftest.py
    - tests/migracion/test_migracion_preserva_datos.py
    - tests/migracion/test_migracion_que_pierde_datos_falla.py
    - tests/arquitectura/invariantes/inv_01_05.py
  modified:
    - tests/conftest.py

key-decisions:
  - "El segundo choque de plataforma que el plan documenta **no es lo que el plan afirma**, y se corrigió con la medición: emitir el PRAGMA dentro de la transacción no es un no-op incondicional, sino que depende de si ya hubo una sentencia de datos. Eso lo hace más peligroso, no menos, y refuerza la decisión del motor dedicado"
  - "`comprobar_integridad` vive en `sqlite/integridad.py` y no en `env.py`: el entorno de Alembic no es importable fuera de una corrida, y una comprobación que ninguna prueba puede invocar es una que nadie vio fallar nunca"
  - "La versión de esquema es el identificador de la revisión cabeza (`0002`) en vez de un número aparte: con dos números habría dos verdades sobre el mismo hecho y nada que impidiera que se contradijeran"
  - "`manifiesto.captura_id` es la clave primaria y no hay un `id` aparte: una captura tiene exactamente un manifiesto, y darle identidad propia permitiría dos manifiestos de la misma captura diciendo cosas distintas"
  - "La tabla `configuracion` **no** lleva columna `tipo`, contra la letra del plan 01-05 y a favor del contrato ya escrito del plan 01-06: el tipo lo declara el catálogo y una columna podría contradecirlo"
  - "`viaje.patente` se persiste **sin normalizar**: el dominio ya conserva el original al lado del canónico para poder auditar la traducción, y normalizar al guardar destruiría ese dato"
  - "La poda de respaldos protege explícitamente la copia recién creada, además de ordenar bien: una red de seguridad que puede borrar su propio último punto de retorno es peor que ninguna, porque el operador cree que la tiene"

patterns-established:
  - "Cuando una propiedad no es observable donde el criterio la buscaba, se verifica donde vive de verdad y se dice por qué: la unicidad compuesta se afirma en `index_list` (que opera) y en el DDL (que lleva el nombre que la hace migrable)"
  - "El caso adverso incluye su contraprueba: además de demostrar que la pérdida se detecta, se demuestra que agregar una columna **no** cuenta como pérdida, porque con ese criterio ninguna migración pasaría nunca"

requirements-completed: [VIA-05, DIS-05, DIS-06]

# Métricas
duration: 118min
completed: 2026-08-01
---

# Phase 01 Plan 05: Esquema no retrofiteable y maquinaria de migraciones Summary

**El esquema que el producto va a arrastrar durante años queda fijado con sus dos decisiones no retrofiteables ejercitadas —Viaje↔Remito N:M y peso teórico nulable con estado derivado—, y la maquinaria que permite cambiarlo sin perder evidencia queda demostrada con una migración real sobre datos sembrados, incluido el caso adverso que prueba que la comparación detecta pérdidas.**

## Performance

- **Duration:** 118 min
- **Tasks:** 3 (dos con ciclo TDD completo)
- **Files modified:** 20 (19 creados, 1 modificado)
- **Compuerta:** 504 pruebas rápidas (eran 446), 1 xfail deliberado, 4 contratos, 67 pruebas de invariantes, 36 dependencias

## Accomplishments

- **Las dos decisiones no retrofiteables están fijadas y probadas contra el esquema real.** Un viaje con tres remitos, un remito recuperado desde los dos viajes que lo comparten, y `SELECT count(*) ... WHERE peso_teorico_kg IS NULL` devolviendo el número sembrado. La tabla `remito` **no tiene ninguna columna de estado**, verificado por una prueba que consulta el esquema: la completitud se deriva de los artículos y por construcción no puede contradecir a los datos que tiene al lado.

- **Los 21 nombres canónicos no se copiaron: se leen del dominio.** La prueba de columnas de `item_evidencia` usa `dataclasses.fields(ItemDeEvidencia)` y exige que el conjunto del esquema sea exactamente esos 21 más `id`, `captura_id` y `miniatura`. Si alguien renombra un campo de un lado sin tocar el otro, la compuerta lo dice. Copiar la lista habría creado la segunda verdad que el plan 01-02 pidió evitar.

- **El contenido duplicado ya no puede reventar una captura (T-01-27).** Dos filas con la **misma** `ruta_relativa` y distinta cámara se persisten sin error; dos filas con el mismo `(captura_id, camara_id)` fallan con `IntegrityError`. Es la decisión acordada con el plan 01-04, y es la que evita que la segunda foto de una pared quieta deje un archivo huérfano y un error incomprensible para el portero.

- **La migración preserva datos, demostrado sobre los cuatro casos feos y con el caso adverso.** Se siembra en `0001` (viaje con tres remitos, remito compartido, peso `NULL`, número con `ñ`/espacio/acento, patente cruda `" AB-123-CD "`), se respalda, se migra a `0002` —que reescribe `remito` entera con `batch_alter_table`— y se compara **valor por valor**. `foreign_key_check` sin violaciones, `integrity_check` en `ok`, el `NULL` sigue siendo `NULL` y no `0.0`, y el texto con acentos vuelve carácter por carácter.

- **El caso adverso demuestra las tres formas reales de perder datos y su contraprueba.** Soltar una columna poblada, cambiar una sola celda y perder filas: las tres se detectan con **la misma** función `comparar_volcados` que usa el caso feliz. Y agregar una columna **no** cuenta como pérdida — sin esa contraprueba, el criterio sería «que nada cambie», con el cual ninguna migración podría pasar nunca.

- **El operador gana la orden `migrar`, verificada en la consola real de Windows** con acentos intactos y sobre una ruta con espacios: base nueva (exit 0, `revision_aplicada: "0002"`), base ya migrada (informa que no hay pendientes), y migración `0001 → 0002` con copia previa de 184 320 bytes.

## Task Commits

1. **Tarea 1: Motor con PRAGMAs verificados y esquema no retrofiteable** — `591c200` (test) + `d4b0080` (feat)
2. **Tarea 2: Alembic con motor dedicado, respaldo y la orden `migrar`** — `e45379b`
3. **Tarea 3: Migración que preserva datos, con el caso adverso** — `f3ef141`

## Hallazgo que corrige el fundamento documentado del plan

El plan (y la investigación) afirman que emitir `PRAGMA foreign_keys=OFF` dentro de la transacción de la migración **es un no-op**. Lo reproduje en esta máquina con SQLAlchemy 2.0.51 y **no es exacto**. Lo medido:

| Caso | Lectura de `foreign_keys` tras pedir OFF | Resultado del batch |
|------|------------------------------------------|---------------------|
| Batch con motor de la aplicación | `1` | `IntegrityError: FOREIGN KEY constraint failed` — **confirmado literalmente** |
| PRAGMA dentro de la transacción, **sin** DML previa | `0` — **sí toma efecto** | el batch **pasa** |
| PRAGMA dentro de la transacción, **con** DML previa | `1` — ahí sí se ignora | `IntegrityError` |
| PRAGMA antes + `begin()` explícito | — | `InvalidRequestError: This connection has already initialized a SQLAlchemy Transaction()` — **confirmado literalmente** |
| Motor dedicado `para_migracion=True` | `0` | batch pasa · `foreign_key_check` sin violaciones · `integrity_check: ok` · `viaje_remito` preservado |

La razón es que el conector difiere el `BEGIN` real de SQLite hasta la primera sentencia de datos, y un PRAGMA no lo dispara: `motor.begin()` de SQLAlchemy **no** implica una transacción SQLite abierta.

**Esto refuerza la decisión del plan en vez de debilitarla, y por un motivo peor que el declarado.** Un no-op incondicional sería un fallo determinista, visible la primera vez. Lo real es que la misma línea funciona o no **según lo que la revisión haya hecho antes**, sin ninguna señal: una revisión que hoy pasa se rompe el día que alguien le agrega un `UPDATE` más arriba. El motor dedicado no depende del orden de las operaciones. El docstring de `sqlite/motor.py` quedó corregido con lo medido.

## Deviations from Plan

### Criterio medido donde la propiedad vive de verdad

**1. La unicidad compuesta se verifica en dos lugares porque SQLite no expone su nombre donde el criterio lo buscaba**

- **Found during:** Tarea 1
- **Qué pedía el criterio:** que `PRAGMA index_list(item_evidencia)` afirme «que existe la restricción única sobre `(captura_id, camara_id)`», nombrada `uq_item_evidencia_captura_id_camara_id`.
- **Qué se observó:** SQLite materializa una restricción `UNIQUE` declarada en el `CREATE TABLE` con un **autoíndice de nombre generado** (`sqlite_autoindex_item_evidencia_2`, `unique=1`, `origin='u'`). El nombre declarado **sí existe**, en el DDL de `sqlite_master`: `CONSTRAINT uq_item_evidencia_captura_id_camara_id UNIQUE (captura_id, camara_id)`. Por construcción, `index_list` nunca lo va a devolver.
- **Medición implementada, que es más fuerte que la pedida:** se afirman las **dos** propiedades por separado, cada una donde vive. Que la unicidad **opera**: `index_list` devuelve exactamente un índice sobre esas dos columnas, único y con `origin='u'` (restricción, no índice suelto) — más el `IntegrityError` de la prueba funcional. Que lleva el **nombre que la hace migrable**: presente en el DDL, que es lo que `batch_alter_table` necesita para poder soltarla.
- **Por qué no es un debilitamiento:** el criterio quería garantizar dos cosas y sólo miraba un lugar donde una de ellas es inobservable. Ambas quedan verificadas.
- **Committed in:** `d4b0080`

### Auto-fixed Issues

**2. [Regla 1 - Defecto] La poda de respaldos borraba la copia que se acababa de crear**

- **Found during:** Tarea 3
- **Issue:** el nombre de la copia llevaba marca de tiempo con resolución de **segundo** y un sufijo de desempate (`-2`, `-3`). El orden alfabético dejó de coincidir con el cronológico, porque el guion (`0x2D`) precede al punto (`0x2E`): `respaldo-T-2.sqlite3` ordena **antes** que `respaldo-T.sqlite3` aunque sea más nuevo. La poda, que toma «las primeras» como las más viejas, terminó borrando la copia recién creada y `respaldar` falló al hacer `stat()` sobre ella.
- **Por qué importa más que un fallo de prueba:** el síntoma en producción es el peor posible para una red de seguridad. La orden `migrar` informa la ruta de un respaldo que ya no existe, y el operador queda creyendo que tiene punto de retorno. Se entera cuando va a usarlo, o sea cuando ya no hay otro.
- **Fix:** dos capas. La marca de tiempo pasa a llevar **milisegundos**, con lo cual el orden alfabético vuelve a coincidir con el cronológico y el desempate (ahora de ancho fijo) casi nunca hace falta. Y `_podar` recibe `proteger=destino`: la copia recién tomada **no se borra nunca**, pase lo que pase con el orden de los nombres.
- **Prueba de regresión:** `test_la_poda_nunca_borra_la_copia_que_se_acaba_de_hacer`, con `conservar=1` y tres respaldos seguidos, exigiendo que la ruta informada exista en disco cada vez.
- **Committed in:** `f3ef141`

**3. [Regla 3 - Bloqueo] `comprobar_integridad` no era invocable desde ninguna prueba**

- **Found during:** Tarea 3
- **Issue:** el criterio de la Tarea 2 exige «una prueba que lo demuestra sembrando una referencia colgada». La función vivía en `migraciones/env.py`, que **no es un módulo importable**: se ejecuta con el contexto de una migración en curso y acceder a su configuración fuera de una corrida falla. La comprobación que es la mitad del Criterio de Éxito 6 no se podía ver fallar.
- **Fix:** se movió a `sqlite/integridad.py` con su excepción, y `env.py` la importa y la invoca. Las dos invariantes que exigían los PRAGMA en `env.py` se reapuntaron al módulo donde ahora viven, y se **agregó una tercera** sobre `env.py` que exige `comprobar_integridad(` presente: que la comprobación exista no sirve de nada si la migración no la llama. El conjunto es más fuerte que el declarado por el plan.
- **Committed in:** `f3ef141`

**4. [Regla 3 - Bloqueo] La tabla `configuracion` no lleva la columna `tipo` que este plan pedía**

- **Found during:** Tarea 1
- **Issue:** el bloque `<action>` de este plan enumera `configuracion` con «clave, valor, **tipo**, cambiado_por, cambiado_en_utc_iso». El plan 01-06 ya está entregado y su `COLUMNAS_REQUERIDAS` declara cuatro columnas sin `tipo`, con una decisión explícita: el tipo lo declara el catálogo del código y el valor se guarda como JSON, porque una columna de tipo podría contradecir al catálogo y habría dos verdades sobre el mismo dato.
- **Fix:** se honró el contrato ya escrito. Además se agregó `test_la_configuracion_en_base_funciona_sobre_el_esquema_real`, que instancia `ConfiguracionEnBase` sobre la tabla que crea esta migración, escribe con autor y lee de vuelta — convirtiendo el contrato entre los dos planes en una prueba de integración real en vez de una coincidencia de nombres.
- **Committed in:** `d4b0080`

**5. [Regla 3 - Bloqueo] El caso feo de la patente no era sembrable: faltaba la columna**

- **Found during:** Tarea 3
- **Issue:** el bloque `<behavior>` pide sembrar «una patente con guiones y espacios (`" AB-123-CD "`)», pero el esquema de `viaje` que escribí siguiendo el patrón verificado de la investigación sólo tenía `id` y `numero_legible`. El dominio, en cambio, ya modela `Viaje.camion` con su `Patente`.
- **Fix:** se agregó `viaje.patente` (`String(20)`, nullable) a `modelos.py` y a la línea base, con el texto persistido **sin normalizar**: el valor `Patente` del dominio conserva el original al lado del canónico justamente para poder auditar la traducción, y normalizar al guardar destruiría ese dato. La prueba exige que vuelva carácter por carácter, espacios incluidos.
- **Por qué se cambió la línea base y no se agregó una revisión:** todavía no existe ninguna instalación con esta base. Corregir `0001` ahora es gratis; hacerlo después cuesta una migración sobre datos productivos, que es exactamente lo que este plan existe para evitar.
- **Committed in:** `f3ef141`

**6. [Regla 3 - Bloqueo] Las invariantes se agregaron de forma incremental**

- **Found during:** Tarea 1
- **Issue:** igual que en 01-02, 01-03 y 01-06: `test_invariantes_de_codigo.py` falla —correctamente— cuando una invariante nombra un archivo que todavía no existe.
- **Fix:** cada tarea agrega a `inv_01_05.py` las invariantes de los archivos que ella misma crea. Las 15 quedan declaradas al cerrar el plan (5 de la Tarea 1, 10 de la Tarea 2 y 3), una más que las 14 que el plan enumeraba, por la invariante extra de la desviación 3.
- **Committed in:** `d4b0080`, `e45379b`, `f3ef141`

---

**Total deviations:** 6 — 1 criterio medido donde la propiedad vive, 1 defecto real corregido, 4 bloqueos resueltos.
**Impact on plan:** ninguna amplía el alcance y ninguna debilita una verificación. Tres de las seis (2, 3, 5) corrigen cosas que habrían llegado al cliente: un respaldo que se borra a sí mismo, una comprobación de integridad que nadie podía ver fallar, y un caso de prueba que el esquema no permitía sembrar. La desviación 4 elige el contrato ya entregado por encima de la letra de este plan, que es lo que el propio prompt de ejecución indicaba.

## Issues Encountered

- **`PRAGMA index_list` no muestra el nombre de una restricción `UNIQUE` declarada en el `CREATE TABLE`.** Es la causa de la desviación 1 y vale como advertencia general para el resto de la fase: verificar restricciones por nombre exige mirar el DDL de `sqlite_master`, no los índices.
- **Un fallo de migración deja residuos que contaminan la siguiente corrida.** Mi primer script de verificación de los tres choques encadenaba los casos sobre la misma base, y la tabla `_alembic_tmp_remito` que dejó el primer fallo hizo fallar a los dos siguientes por un motivo que no era el suyo (`table _alembic_tmp_remito already exists`). Rehecho con una base limpia por caso, la medición cambió — y es la que está en la tabla de arriba. Vale como recordatorio: un experimento que reutiliza estado no mide lo que cree medir.
- **Ruff `B008`** marcó la opción `--base-de-datos` de la orden `migrar` y no las opciones `bool` de las demás órdenes. Se resolvió con una constante de módulo, que es el mismo patrón que adoptó el plan 01-02 ante este aviso.

## Known Stubs

Ninguno. Hay columnas que hoy nadie llena y **no son stubs**, sino esquema deliberadamente completo por D-27, cada una con su plan de destino declarado:

- `item_evidencia.motor_id`, `version_modelo` y `sha256_modelo` — se pueblan desde la Fase 4, cuando exista inferencia (D-05). Ya estaban probadas en su estado nulo por el plan 01-02.
- `payload_crudo.operacion` y `cabeceras_comprimidas` — las escribe el cassette del plan 01-10. Existen desde la línea base porque agregarlas después costaría una migración sobre datos productivos.
- `usuario.*` y `lapida.*` — el esquema de identidad y el de purga manual; sus herramientas operables llegan en sus fases (D-10, D-25).

`viaje` no persiste chofer ni transportista: el dominio los modela, el esquema todavía no. **No es un stub sino un faltante consciente** — son columnas nullable que se agregan con un `ADD COLUMN`, que es la única alteración que SQLite soporta de forma nativa y por lo tanto la más barata de retrofitear. Lo no retrofiteable de esa tabla —la relación N:M— sí está.

## Threat Flags

Ninguna superficie nueva fuera de la que el plan ya modeló. Las siete amenazas con disposición `mitigate` quedan cubiertas y verificables:

| Amenaza | Estado | Verificable con |
|---------|--------|-----------------|
| T-01-05 (el ORM no expone concatenación de SQL) | mitigada | `uv run ruff check src/porteria/infraestructura` limpio, esquema tipado 2.0 sin `declarative_base()` (invariante) |
| T-01-19 (migración sobre datos productivos) | mitigada, con las tres capas | `tests/migracion/` completo: preservación fila por fila, caso adverso, `foreign_key_check`+`integrity_check` que **fallan** la migración, y copia previa |
| T-01-20 (abrir una base más nueva) | mitigada | `test_una_base_mas_nueva_se_niega_a_abrir_nombrando_las_dos_versiones` |
| T-01-04 (`anonimizado` sin default) | mitigada | `test_anonimizado_es_obligatorio_y_no_tiene_valor_por_defecto` y `test_insertar_sin_declarar_anonimizado_falla` |
| T-01-21 (durabilidad ante corte) | mitigada | `test_el_motor_de_la_aplicacion_arranca_con_los_cuatro_pragma` afirma `synchronous = 2` leído de la base |
| T-01-07 (sin deserialización insegura) | mitigada | `cuerpo_comprimido`/`cabeceras_comprimidas` son `BLOB` de JSON comprimido; contrato `sin_deserializacion_insegura` intacto |
| T-01-27 (contenido duplicado) | mitigada | `test_dos_items_pueden_compartir_la_misma_ruta_relativa` |

## User Setup Required

Ninguno para que la fase siga. Para operar el producto en un equipo real hace falta el archivo de arranque `porteria.toml` con `ruta_base_datos`, que es de donde la orden `migrar` toma la base cuando no se le pasa `--base-de-datos`.

## Next Phase Readiness

**Listo para los planes que dependen de este:**

- **01-07 (rebanada vertical)** — tiene el motor real (`crear_motor(ruta_db)`), el esquema completo con `captura`, `item_evidencia`, `manifiesto` y `outbox` para la transacción única de D-12, y la tabla `configuracion` ya probada contra `ConfiguracionEnBase` del plan 01-06. La captura puede insertarse con `viaje_id` y `autor_id` nulos, verificado.
- **01-10 (contratos externos)** — `payload_crudo` nace con las 12 columnas que el cassette necesita, `anonimizado` sin default para que la ausencia de anonimización sea detectable, y `operacion` para exportar por operación.
- **Cualquier fase que agregue la revisión `0003`** — `tests/migracion/conftest.py` deja `sembrar_casos_feos`, `volcar` y `comparar_volcados` listos: alcanza con parametrizar la revisión anterior. D-33 queda escrito como recordatorio en el docstring del módulo y en `script.py.mako`, que es lo que ve quien genera una revisión nueva.

**Sin bloqueos.** Sigue abierta, de 01-01 y sin relación con este plan, la Tarea 4 de protección de rama en GitHub.

**Dato para el planificador:** la compuerta rápida quedó en **1 min 51 s** con 504 pruebas (eran 446 en 1 min 37 s). Las 58 pruebas nuevas suman unos 6 s en total: las 15 de migración corren en 2,3 s porque cada una migra una base vacía de 13 tablas, que es barato. El presupuesto sigue dominado por los 60 s de la prueba de frescura del plan 01-03.

## Self-Check: PASSED

- 18 artefactos declarados en `files_modified`: los 18 existen en el árbol (más `sqlite/integridad.py`, creado por la desviación 3).
- 4 hashes de commit declarados: los 4 existen en `git log`.
- `uv run python scripts/compuerta.py` → **COMPUERTA EN VERDE**, los cuatro pasos, exit 0.
- `uv run pytest -q -m "not lenta"` → **504 pruebas en verde**, 1 xfail esperado (`test_rebanada_captura.py`, que cierra en 01-07 y no se tocó).
- `uv run pytest tests/arquitectura/test_invariantes_de_codigo.py -q` → 67 en verde, 15 invariantes de este plan.
- `uv run lint-imports --no-cache` → 4 contratos intactos, 0 rotos.
- `uv run ruff check .` → sin hallazgos.
- `uv run alembic -c alembic.ini heads` → `0002 (head)`, una sola cabeza.
- Esquema de `modelos.py` vs. el que producen `0001`+`0002`: **cero diferencias** de tablas y columnas, verificado con `inspect`.
- `src/porteria/cli/app.py` sin modificar por este plan: `git diff 3b0a2e0..HEAD -- src/porteria/cli/app.py` → vacío.
- La orden verificada en la consola real de Windows sobre rutas con espacios y acentos: base nueva (exit 0, JSON parseable), base ya migrada (sin cambios), `0001 → 0002` con copia previa de 184 320 bytes.

---
*Phase: 01-n-cleo-evidencia-trazable-y-contratos-externos-congelados*
*Completed: 2026-08-01*
