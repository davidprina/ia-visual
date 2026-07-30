---
phase: 01-n-cleo-evidencia-trazable-y-contratos-externos-congelados
plan: 02
subsystem: dominio
tags: [dominio-puro, sha256, perf_counter_ns, hexagonal, tdd, stdlib, tamper-evident]

# Grafo de dependencias
requires:
  - phase: 01-01
    provides: proyecto uv, árbol de paquetes, compuerta única de CI, cuatro contratos de import-linter, fixtures de ruta hostil
provides:
  - "`dominio/` completo con cero dependencias externas, demostrado por la sonda de aislamiento con 17 módulos reales"
  - "`HuellaDeIntegridad` como valor de primera clase, sin cálculo de hash adentro"
  - "Modelo de integridad de tres niveles: huella por imagen, hash de manifiesto por captura, cadena de auditoría desde el registro uno"
  - "`CapturaDeControl` autónoma (sin viaje) con ventana de aceptación congelada por captura"
  - "Los 21 nombres canónicos de `ItemDeEvidencia` que el esquema de 01-05 mapea uno a uno"
  - "Viaje↔Remito muchas a muchas con peso teórico nulable y estado derivado"
  - "Puerto `Reloj` y `RelojDelProceso` con `perf_counter_ns`, ancla a UTC y reanclado tras suspensión"
  - "`RelojFijo` como doble determinista, usado por la fixture `reloj_determinista`"
  - "`Resultado[T]` con tres variantes para operar con datos ausentes sin excepciones de negocio"
affects: [01-03-fuentes-de-video, 01-04-persistencia-de-evidencia, 01-05-esquema-y-migraciones, 01-06-identidad-y-roles, 01-07-rebanada-vertical, 01-08-adaptadores-externos, 01-10-integraciones]

# Seguimiento técnico
tech-stack:
  added: []
  patterns:
    - "Reloj como puerto inyectable (`perf_counter_ns`) en vez de `import time` en el dominio"
    - "Valores de tiempo persistibles como texto ISO-8601 con offset más entero de desfasaje, nunca `datetime` con `tzinfo`"
    - "`Resultado[T]` de tres variantes en lugar de excepciones con semántica de negocio"
    - "Orden de hasheo derivado de los datos, nunca del orden de inserción"
    - "Entidades con igualdad por identificador; valores con igualdad por contenido"
    - "Estado derivado por propiedad calculada en lugar de campo persistido"

key-files:
  created:
    - src/porteria/dominio/comun/identificadores.py
    - src/porteria/dominio/comun/tiempo.py
    - src/porteria/dominio/comun/resultado.py
    - src/porteria/dominio/eventos.py
    - src/porteria/dominio/evidencia/huella.py
    - src/porteria/dominio/evidencia/estados.py
    - src/porteria/dominio/evidencia/captura.py
    - src/porteria/dominio/evidencia/manifiesto.py
    - src/porteria/dominio/evidencia/lapida.py
    - src/porteria/dominio/auditoria/registro.py
    - src/porteria/dominio/viaje/modelo.py
    - src/porteria/aplicacion/puertos/salida/reloj.py
    - src/porteria/infraestructura/runtime/reloj.py
    - tests/dominio/test_resultado.py
    - tests/dominio/test_huella.py
    - tests/dominio/test_captura.py
    - tests/dominio/test_cadena_auditoria.py
    - tests/dominio/test_viaje_remito.py
    - tests/integracion/test_reloj_del_proceso.py
    - tests/arquitectura/invariantes/inv_01_02.py
  modified:
    - tests/conftest.py

key-decisions:
  - "`HuellaDeIntegridad` RECHAZA la mayúscula en vez de normalizarla: `hexdigest()` siempre devuelve minúsculas, así que una huella en mayúsculas sólo puede venir de una edición a mano o de un cálculo ajeno, y normalizar convertiría esa señal en nada además de admitir dos textos para la misma clave única"
  - "El orden de hasheo del manifiesto se deriva de `(camara_id, instante_monotono_ns)`, nunca del orden de inserción: es la única forma de que agregar/quitar/alterar cambien el hash y reordenar la colección de entrada no lo cambie"
  - "`incertidumbre_sello_utc_ms` entra en el hash del manifiesto y cierra la Open Question 3: el sello UTC absoluto declara su ~15,6 ms de incertidumbre en vez de callarla"
  - "`Viaje` y `Remito` son entidades con igualdad por identificador (`eq=False`), no dataclasses comparadas campo por campo: la relación bidireccional hacía recursar la comparación generada"
  - "`CapturaDeControl.nueva` exige la ventana vigente sin valor por defecto, para que ninguna captura quede sellada con un criterio que nadie eligió (D-40)"
  - "`ventana_vigente_ms`, `desvio_ms` y `autor_id` los sella la captura y no se reciben en `agregar_evidencia`: si vinieran de afuera, cada uno sería una vía para escribir un número distinto del real"
  - "El criterio 'dos llamadas consecutivas al reloj devuelven valores distintos en 100 de 100' se reemplazó por dos mediciones válidas: es físicamente inalcanzable con paso de 100 ns porque dos llamadas de CPython caben en un tick"
  - "`CapturaDeControl` no es dataclass: los datos que fijan el disparo se exponen como propiedades de sólo lectura para que `captura.ventana_vigente_ms = 5000` no sea una línea válida (T-01-14)"

patterns-established:
  - "Invariantes de código declaradas por plan en `tests/arquitectura/invariantes/inv_01_0N.py`, agregadas de forma incremental en el commit de la tarea que crea el archivo que vigilan, para que la compuerta quede verde en cada commit"
  - "Separadores de hash declarados por módulo y validados en el dato (`validar_texto_hasheable`) en vez de supuestos"
  - "Docstring de módulo que declara el límite honesto de la garantía (tamper-evident, no tamper-proof), con invariante que exige que el texto esté presente"
  - "Los agregados acumulan eventos de dominio y no los publican; el caso de uso los persiste en el outbox en la misma transacción"

requirements-completed: [NUC-01, EVI-05, VIA-05]

# Métricas
duration: 41min
completed: 2026-07-29
---

# Phase 01 Plan 02: Núcleo del dominio y reloj del proceso Summary

**Dominio completo con cero dependencias externas —integridad en tres niveles con SHA-256, cadena de auditoría desde el registro uno, Viaje↔Remito N:M con peso teórico nulable— más el reloj del proceso en `perf_counter_ns` con ancla a UTC reanclable.**

## Performance

- **Duration:** 41 min
- **Started:** 2026-07-29T00:00:00Z
- **Completed:** 2026-07-29T00:41:00Z
- **Tasks:** 3 (las tres con ciclo TDD completo)
- **Files modified:** 21 (20 creados, 1 modificado)

## Accomplishments

- **La compuerta pasa de vigilar un árbol vacío a vigilar el dominio real.** La sonda de aislamiento (`uv run --isolated --no-project`) importa 17 módulos de dominio en un intérprete sin ninguna dependencia de terceros instalada y devuelve 0. Es la primera vez que la prueba de NUC-01 mide código de verdad.
- **Tres de las seis decisiones no retrofiteables quedan fijadas y probadas:** la huella SHA-256 como valor de primera clase del dominio, la relación Viaje↔Remito muchas a muchas (tres remitos por viaje y un remito compartido entre dos viajes), y el peso teórico admitiendo ausencia con estado derivado.
- **El reloj queda fijado en `perf_counter_ns`,** con la medición que fuerza la decisión convertida en regresión permanente: la prueba exige más de 50 000 instantes distintos en 100 ms, cuando `time.monotonic()` en Windows con Python 3.12 daría unos 7.
- **El límite honesto de la garantía está escrito en el código y demostrado por una prueba.** `test_reencadenar_desde_el_punto_alterado_pasa_la_verificacion` altera un registro, rehace la cadena desde ahí y comprueba que la verificación pasa: es tamper-evident, no tamper-proof.
- Suite completa: **242 pruebas verdes** (eran 133 al empezar) más el xfail deliberado de la rebanada vertical, y los cuatro contratos de arquitectura intactos.

## Task Commits

Cada tarea se commiteó de forma atómica, con ciclo TDD (test → feat):

1. **Tarea 1: Vocabulario común del dominio y reloj del proceso** — `acf7417` (test) + `80fac74` (feat)
2. **Tarea 2: Evidencia, manifiesto, lápida y bitácora de auditoría encadenada** — `9310a36` (test) + `6e7f76b` (feat)
3. **Tarea 3: Viaje, remito, artículo y peso teórico nulable** — `ea7bbd4` (test) + `3a175bf` (feat)

## Files Created/Modified

**Vocabulario común**

- `src/porteria/dominio/comun/identificadores.py` — seis `NewType` opacos y `NumeroLegible` con formato `AAAA-NNNNNN` (D-29)
- `src/porteria/dominio/comun/tiempo.py` — `InstanteMonotono`, `InstanteUtc`, `Desfasaje` y `FechaLocal`, todos persistibles como texto o entero (Pitfall 4)
- `src/porteria/dominio/comun/resultado.py` — `Ok` / `NoDisponible` / `Degradado`
- `src/porteria/dominio/eventos.py` — `EventoDeDominio` inmutable con los dos relojes

**Evidencia e integridad**

- `src/porteria/dominio/evidencia/huella.py` — `HuellaDeIntegridad`, sin cálculo de hash adentro
- `src/porteria/dominio/evidencia/estados.py` — `INTEGRA` / `COMPROMETIDA` / `PURGADA` y `evaluar()` puro
- `src/porteria/dominio/evidencia/captura.py` — `CapturaDeControl` e `ItemDeEvidencia` con los 21 campos canónicos
- `src/porteria/dominio/evidencia/manifiesto.py` — hash de segundo nivel, su receta persistida y el protocolo `ItemHasheable`
- `src/porteria/dominio/evidencia/lapida.py` — `Lapida` con sus cuatro campos obligatorios
- `src/porteria/dominio/auditoria/registro.py` — `RegistroEncadenado` y `CadenaDeAuditoria`

**Viaje**

- `src/porteria/dominio/viaje/modelo.py` — `Viaje`, `Remito`, `Articulo`, `PesoTeorico`, `Chofer`, `Camion`, `Transportista`, `Patente`

**Reloj**

- `src/porteria/aplicacion/puertos/salida/reloj.py` — puerto `Reloj` con cinco métodos
- `src/porteria/infraestructura/runtime/reloj.py` — `RelojDelProceso` y `RelojFijo`

**Pruebas**

- `tests/dominio/test_resultado.py`, `test_huella.py`, `test_captura.py`, `test_cadena_auditoria.py`, `test_viaje_remito.py` — 156 pruebas de dominio sin I/O
- `tests/integracion/test_reloj_del_proceso.py` — la guardia de resolución de la plataforma y el ancla a UTC
- `tests/arquitectura/invariantes/inv_01_02.py` — 8 invariantes de este plan
- `tests/conftest.py` — la fixture `reloj_determinista` pasa a devolver el `RelojFijo` del producto

## Decisions Made

Las decisiones completas están en el frontmatter. Las tres que más peso tienen sobre los planes siguientes:

1. **Orden de hasheo derivado de los datos.** El manifiesto ordena por `(camara_id, instante_monotono_ns)` antes de hashear. Es lo único que permite las tres propiedades a la vez sin contradicción, y el plan lo marcaba como contrato: un ejecutor que hubiera hasheado en orden de inserción habría producido falsos "comprometida" desde la primera captura, porque las cámaras responden en el orden que quieren.
2. **`Viaje` y `Remito` con igualdad por identificador.** Ver la desviación 2: además de corregir un defecto real, es el modelado correcto — dos remitos con el mismo número son el mismo remito aunque uno tenga los artículos todavía sin cargar.
3. **La captura sella lo que es suyo.** `agregar_evidencia` no recibe `desvio_ms`, `ventana_vigente_ms` ni `autor_id`: los calcula o los toma del disparo. Cada uno de esos parámetros habría sido una vía para persistir un número distinto del real, y los tres son exactamente los que la auditoría lee.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] El criterio de aceptación del reloj era físicamente inalcanzable en la plataforma de destino**

- **Found during:** Tarea 1 (vocabulario común y reloj del proceso)
- **Issue:** El plan pedía que "dos llamadas consecutivas a `RelojDelProceso().instante()` devuelvan valores distintos en al menos 100 de 100 repeticiones". Medido en este equipo: **7 de 100 pares coincidieron**. No es un defecto del reloj sino su contrario — `QueryPerformanceCounter` tiene un paso de 100 ns y dos llamadas consecutivas de CPython caben dentro de un mismo tick. El criterio, tomado literalmente, sólo se podría satisfacer con un reloj *más lento* por llamada.
- **Fix:** Se reemplazó por dos mediciones que sí verifican la intención del criterio (Pitfall 1: que la resolución sea real y no de 15,6 ms), ambas con margen de tres órdenes de magnitud contra el reloj bueno y ninguno contra el malo:
  - `test_el_reloj_produce_cientos_de_miles_de_instantes_distintos` — la medición exacta de RESEARCH, exigiendo más de 50 000 instantes distintos en 100 ms (`monotonic` daría ~7).
  - `test_el_reloj_distingue_dos_eventos_separados_por_microsegundos` — 100 de 100 con trabajo real entre las dos lecturas, deliberadamente sin esperar consultando el reloj, que sería una prueba circular.
  - Se conservaron además la guardia de resolución (`<= 1e-6`), la no regresión de los instantes y la contraprueba de que cinco llamadas seguidas no repiten.
- **Files modified:** `tests/integracion/test_reloj_del_proceso.py`
- **Verification:** 20 pruebas del reloj en verde; la invariante `ausente: monotonic` sobre el módulo del reloj sigue pasando.
- **Committed in:** `80fac74`

**2. [Rule 1 - Bug] Recursión infinita latente en la comparación de `Viaje` y `Remito`**

- **Found during:** Tarea 3 (viaje, remito y peso teórico)
- **Issue:** Con el `__eq__` que genera `dataclass`, comparar dos remitos recorre `Remito.viajes → Viaje.remitos → Remito.viajes` sin fondo. Las pruebas pasaban igual porque `list.__contains__` prueba identidad antes de igualdad, así que el defecto quedaba **tapado mientras se tratara del mismo objeto en memoria** y habría aparecido con el primer remito reconstruido desde la base, en el plan 01-05.
- **Fix:** `@dataclass(eq=False)` con `__eq__`/`__hash__` por identificador en las dos entidades, y prueba de regresión `test_comparar_dos_remitos_equivalentes_no_recursa_por_la_relacion` que compara dos objetos distintos con contenido equivalente.
- **Files modified:** `src/porteria/dominio/viaje/modelo.py`, `tests/dominio/test_viaje_remito.py`
- **Verification:** 35 pruebas de viaje/remito en verde, incluida la de regresión.
- **Committed in:** `3a175bf`

**3. [Rule 3 - Blocking] `tests/conftest.py` no figuraba en `files_modified` del plan**

- **Found during:** Tarea 1
- **Issue:** El bloque `<action>` de la Tarea 1 exige explícitamente "hacer que la fixture `reloj_determinista` de `tests/conftest.py` use `RelojFijo`", pero `conftest.py` no está listado en el `files_modified` del frontmatter. Sin tocarlo, quedarían dos dobles de reloj en paralelo y el de las pruebas podría dejar de cumplir el puerto sin que nada lo delate.
- **Fix:** La clase `RelojDeterminista` de 01-01 se reemplazó por un alias de `RelojFijo`, conservando el nombre histórico y los métodos `instante_ns()` y `avanzar_ms()` que usa `tests/arquitectura/test_compuerta_de_pruebas.py`. `test_la_fixture_del_reloj_determinista_es_el_reloj_fijo` afirma que son el mismo objeto.
- **Files modified:** `tests/conftest.py`, `src/porteria/infraestructura/runtime/reloj.py`
- **Verification:** Suite completa en verde, incluida la prueba de la fixture que ya existía.
- **Committed in:** `acf7417` / `80fac74`

**4. [Rule 3 - Blocking] Las invariantes de las tareas 2 y 3 se agregaron de forma incremental**

- **Found during:** Tarea 1
- **Issue:** El plan declara todas las invariantes de `inv_01_02.py` como si el archivo se escribiera completo en la Tarea 1. Pero `test_invariantes_de_codigo.py` falla —correctamente— cuando una invariante nombra un archivo que no existe, así que declarar en la Tarea 1 las invariantes de `huella.py`, `registro.py` y `modelo.py` habría dejado la compuerta en rojo en los commits de las tareas 1 y 2.
- **Fix:** Cada tarea agrega a `inv_01_02.py` las invariantes de los archivos que ella misma crea. Las 8 quedan declaradas al cerrar el plan, exactamente como el plan pedía.
- **Files modified:** `tests/arquitectura/invariantes/inv_01_02.py`
- **Verification:** `uv run pytest tests/arquitectura/test_invariantes_de_codigo.py -q` → 31 pruebas en verde.
- **Committed in:** `acf7417`, `9310a36`, `ea7bbd4`

---

**Total deviations:** 4 auto-corregidas (2 defectos, 2 bloqueos)
**Impact on plan:** Ninguna amplía el alcance. Las dos primeras corrigen defectos reales —una afirmación de prueba imposible de satisfacer y una recursión latente que habría explotado en 01-05—; las dos últimas son ajustes de secuencia para que la compuerta quede verde en cada commit, que es requisito de la ejecución. Los tres criterios de éxito del plan se cumplen sin excepción.

## Issues Encountered

- **`@dataclass(frozen=True, slots=True)` con genéricos PEP 695 revienta con `TypeError: super(type, obj)` al asignar un atributo que no es campo.** Apareció como fallo de una prueba propia que asignaba `motivo` sobre un `Ok`, que no tiene ese campo. Es un detalle conocido de la combinación `slots=True` + recreación de la clase: la asignación de un campo *existente* levanta `FrozenInstanceError` con normalidad. Se corrigió la prueba, que era la que estaba mal, y no la implementación.
- **Ruff `B008`** marcó `UsuarioId("usuario-1")` como valor por defecto de un argumento en un ayudante de prueba. Se movió a constante de módulo: el valor por defecto se evalúa una sola vez al importar y es una fuente clásica de estado compartido entre pruebas.

## Known Stubs

Ninguno. Los tres campos que quedan nulos en esta fase —`motor_id`, `version_modelo` y `sha256_modelo` de `ItemDeEvidencia`— no son stubs: son campos del esquema de trazabilidad que se poblan desde la Fase 4, cuando exista inferencia, y así lo declara D-05. Están probados en su estado nulo.

## Threat Flags

Ninguna. No se introdujo ninguna superficie de red, de autenticación, de acceso a archivos ni de esquema en un límite de confianza: el paquete `dominio/` no toca I/O y la sonda de aislamiento lo demuestra en un intérprete sin terceros. Las cuatro amenazas con disposición `mitigate` del registro del plan quedan cubiertas y verificables:

| Amenaza | Estado | Verificable con |
|---------|--------|-----------------|
| T-01-01 (manipulación de evidencia) | mitigada, con límite declarado | `tests/dominio/test_cadena_auditoria.py` — 10 registros, se altera el `k` y `verificar` devuelve `k` |
| T-01-14 (ensanchar la ventana retroactivamente) | mitigada | `test_cambiar_el_parametro_no_toca_las_capturas_ya_hechas` |
| T-01-05 (el dominio no toca SQL) | mitigada | `uv run lint-imports --no-cache` → 4 contratos intactos |
| T-01-07 (deserialización insegura) | mitigada | contrato `sin_deserializacion_insegura` sobre todo `porteria` |

T-01-13 (autoría no identificable) sigue **aceptada** por el usuario según D-21, y el hecho queda marcado: `CapturaDeControl.autor_identificado` es el dato que el panel de calidad contabiliza.

## User Setup Required

Ninguno. No hay configuración de servicios externos en este plan.

## Next Phase Readiness

**Listo para los planes que dependen de este:**

- **01-03 (fuentes de video)** — tiene `InstanteMonotono` y el puerto `Reloj` para medir la antigüedad del frame en espacio `perf_counter`, y `Resultado[T]` para expresar "no hay frame fresco" sin excepciones.
- **01-04 (persistencia de evidencia)** — le corresponde el cálculo del SHA-256 por streaming. El dominio espera recibir una `HuellaDeIntegridad` ya construida; la invariante que prohíbe `hashlib` en `huella.py` es el recordatorio.
- **01-05 (esquema y migraciones)** — los 21 nombres canónicos de `ItemDeEvidencia` y los 5 de `Manifiesto` están fijados y contados en un solo lugar. El esquema los mapea uno a uno y agrega exactamente tres columnas propias (`id`, `captura_id`, `miniatura`). Atención a dos mapeos no triviales: `desfasaje_local_min` lleva un `Desfasaje` y la columna guarda su `.minutos`; `capturado_en_utc_iso` lleva un `InstanteUtc` y la columna guarda su `.texto` en `String(32)` — nunca `DateTime(timezone=True)` (Pitfall 4).
- **01-07 (rebanada vertical)** — `tests/aceptacion/test_rebanada_captura.py` sigue en `xfail` a propósito, como corresponde.

**Sin bloqueos.** Queda abierta, de 01-01 y sin relación con este plan, la Tarea 4 de protección de rama en GitHub, que es configuración de repositorio y no produce artefacto. Y sigue abierto como hueco de diseño declarado el **ancla externa** que convertiría la cadena de tamper-evident en tamper-proof (replicación a medio de solo-anexado, sellado por un tercero o publicación periódica del hash de la cabeza); no es alcance de la Fase 1.

## Self-Check: PASSED

- 20 archivos declarados como creados: los 20 existen en el árbol.
- 6 hashes de commit declarados: los 6 existen en `git log`.
- `uv run python scripts/compuerta.py` → **COMPUERTA EN VERDE**, los cuatro pasos, exit 0.
- `uv run pytest -q -m "not lenta"` → 242 pruebas en verde, 1 xfail esperado.
- `uv run lint-imports --no-cache` → 4 contratos intactos, 0 roscos.
- `uv run --isolated --no-project python tests/arquitectura/sonda_dominio_aislado.py` → exit 0, 17 módulos de dominio, prohibidos cargados: ninguno.
- `uv run ruff check .` → sin hallazgos.

---
*Phase: 01-n-cleo-evidencia-trazable-y-contratos-externos-congelados*
*Completed: 2026-07-29*
