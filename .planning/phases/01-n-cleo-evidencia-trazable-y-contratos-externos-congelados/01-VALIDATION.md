---
phase: 1
slug: n-cleo-evidencia-trazable-y-contratos-externos-congelados
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-25
updated: 2026-07-26
---

# Phase 1 — Validation Strategy

> Contrato de validación por fase para el muestreo de retroalimentación durante la ejecución.
> Derivado de `01-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest` 9.1.1 |
| **Config file** | `pyproject.toml` → `[tool.pytest.ini_options]` — **no existe todavía, lo instala Wave 0** |
| **Quick run command** | `uv run pytest -q -m "not lenta"` |
| **Full suite command** | `uv run pytest -q` |
| **Compuerta de arquitectura (estática)** | `uv run lint-imports --no-cache` |
| **Compuerta de aislamiento (runtime)** | `uv run --python 3.12 --isolated --no-project python tests/arquitectura/sonda_dominio_aislado.py` — **sin `PYTHONPATH`**: la sonda se auto-resuelve `src/` en `sys.path[0]` como primera sentencia ejecutable, así el mismo comando literal corre a mano, desde pytest y desde `scripts/compuerta.py` |
| **Compuerta de invariantes de código** | `uv run pytest tests/arquitectura/test_invariantes_de_codigo.py -q` — reemplaza todo criterio basado en `grep`, que no es verificable en Windows (D-54) |
| **Compuerta de licencias** | `uv run pip-licenses --allow-only "<lista blanca>"` |
| **Plataforma de la compuerta** | **Windows únicamente** (D-54) |
| **Marcadores** | `lenta` — tanda programada, no bloquea la fusión (D-53) |
| **Estimated runtime** | Suite rápida **2–4 min** · Suite completa ~15 min (incluye las `lenta`) |

---

## Sampling Rate

- **Después de cada commit de tarea:** `uv run pytest -q -m "not lenta"` + `uv run lint-imports --no-cache`
- **Después de cada wave:** suite rápida completa + prueba de entorno aislado + inventario de licencias
- **Antes de `/gsd-verify-work`:** suite completa **incluidas las `lenta`** (frescura de 10 minutos, 20 repeticiones de muerte del proceso) en verde
- **Tanda programada (D-53):** las `lenta` abren un asunto al fallar, no traban la fusión
- **Max feedback latency:** **4 minutos** (suite rápida). El presupuesto honesto, desglosado: `test_frescura_acotada` 60 s —deliberado, medir acumulación de buffers reales exige tiempo real— más las pruebas de concurrencia (~3 s), Argon2id a ~201 ms por hash en varias pruebas de `01-09`, y la suite de solo-lectura de `01-10` con su piso deliberado de >50 ms. La anti-vacuidad de la cola (`test_la_prueba_de_frescura_detecta_la_cola`, ~20 s) se movió a `lenta` porque su valor es demostrativo, no de regresión continua.

---

## Per-Task Verification Map

> Mapa completado el 2026-07-26 contra los 10 planes reales. La columna **Plan** y la columna
> **Wave** son firmes: salen del frontmatter de cada PLAN.md. El número de tarea dentro del plan se
> confirma al ejecutar —varios planes ganaron tareas durante la revisión— por eso se anota como
> `01-0N·T?` cuando el requisito se cubre a lo largo de varias tareas del mismo plan.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01·T3 | 01-01 | 1 | NUC-01 | — | El dominio no importa cv2/onnxruntime/PySide6 (estático) | arquitectura | `uv run lint-imports --no-cache` | ❌ W0 | ⬜ pending |
| 01-01·T2 | 01-01 | 1 | NUC-01 | — | El dominio se importa entero sin esos paquetes instalados | arquitectura | `uv run --python 3.12 --isolated --no-project python tests/arquitectura/sonda_dominio_aislado.py` | ❌ W0 | ⬜ pending |
| 01-02·T? | 01-02 | 2 | NUC-01 | — | El dominio permanece limpio al crecer (entidades, reloj, manifiesto) | arquitectura | `uv run lint-imports --no-cache` | ❌ W0 | ⬜ pending |
| 01-08·T? | 01-08 | 4 | NUC-04 | — | Todo puerto de salida tiene doble; el sistema corre sin hardware | contrato | `uv run pytest tests/contrato -q` | ❌ W0 | ⬜ pending |
| 01-08·T? | 01-08 | 4 | NUC-04 | — | Los cuatro datos feos existen y se ejercitan | contrato | `uv run pytest tests/contrato/test_datos_feos.py -q` | ❌ W0 | ⬜ pending |
| 01-08·T3 | 01-08 | 4 | NUC-04 | — | **Anti-vacuidad:** la suite corre con la red bloqueada (`socket` que explota) | contrato | `uv run pytest tests/contrato -q` | ❌ W0 | ⬜ pending |
| 01-10·T3 | 01-10 | 5 | NUC-04 | — | Cassette real de PALJET y de la balanza (`origen: "real"`) | manual | — (`autonomous: false`, requiere credenciales) | ❌ W0 | ⬜ pending |
| 01-07·T? | 01-07 | 4 | NUC-05 | T-01 | Estado + evidencia + outbox en una sola transacción | integración | `uv run pytest tests/integracion/test_transaccion_unica.py -x -q` | ❌ W0 | ⬜ pending |
| 01-07·T3 | 01-07 | 4 | NUC-05 | T-01 | **Modo A** — corte lógico con `monkeypatch` sobre `confirmar` | integración | `uv run pytest tests/integracion/test_transaccion_unica.py -x -q` | ❌ W0 | ⬜ pending |
| 01-07·T3 | 01-07 | 4 | NUC-05 | T-01 | **Modo B** — muerte del proceso, 20 repeticiones con punto desplazado ±50 ms | integración (`lenta`) | `uv run pytest tests/lentas -m lenta -q` | ❌ W0 | ⬜ pending |
| 01-09·T? | 01-09 | 5 | NUC-05 | — | Autoría y matriz de permisos dentro de la misma transacción | integración | `uv run pytest tests/integracion -q -k "autoria"` | ❌ W0 | ⬜ pending |
| 01-06·T? | 01-06 | 3 | NUC-06 | — | La bitácora rota archivos y respeta el nivel configurado | unit | `uv run pytest tests/integracion/test_bitacora.py -q` | ❌ W0 | ⬜ pending |
| 01-07·T2 | 01-07 | 4 | NUC-06 | — | **Cableado:** tras `porteria capturar` existe `porteria.log` con ≥1 línea | integración | `uv run pytest tests/integracion/test_cableado_de_arranque.py -q` | ❌ W0 | ⬜ pending |
| 01-03·T? | 01-03 | 2 | CAP-03 | — | La fuente de archivo entrega frames en los dos modos | integración | `uv run pytest tests/integracion/test_fuente_archivo.py -q` | ❌ W0 | ⬜ pending |
| 01-03·T3 | 01-03 | 2 | CAP-04 | — | La antigüedad del frame no crece; los descartes se cuentan (60 s, bloqueante) | integración | `uv run pytest tests/integracion/test_frescura.py -q -m "not lenta"` | ❌ W0 | ⬜ pending |
| 01-03·T3 | 01-03 | 2 | CAP-04 | — | Frescura sostenida durante 10 minutos | integración (`lenta`) | `uv run pytest tests/integracion/test_frescura.py -m lenta -q` | ❌ W0 | ⬜ pending |
| 01-03·T3 | 01-03 | 2 | CAP-04 | — | **Anti-vacuidad:** cero descartes con consumidor lento es un fallo | integración | `uv run pytest tests/integracion/test_frescura.py tests/integracion/test_frescura_anti_vacuidad.py -q -m "not lenta"` | ❌ W0 | ⬜ pending |
| 01-02·T? | 01-02 | 2 | EVI-05 | T-01 | La huella se calcula en ingesta y se persiste | unit | `uv run pytest tests/dominio/test_huella.py -q` | ❌ W0 | ⬜ pending |
| 01-04·T2 | 01-04 | 3 | EVI-05 | T-01 | **Anti-vacuidad:** un byte alterado en 3 posiciones (primera, media, última) rompe la verificación | integración | `uv run pytest tests/integracion/test_verificacion_huella.py -q` | ❌ W0 | ⬜ pending |
| 01-04·T? | 01-04 | 3 | EVI-06 | T-02 | La imagen va al filesystem; la base sólo metadatos y ruta relativa | integración | `uv run pytest tests/integracion/test_almacen_evidencia.py -q` | ❌ W0 | ⬜ pending |
| 01-07·T? | 01-07 | 4 | EVI-06 | T-01-27 | Contenido duplicado: **1 archivo, 2 filas, ambas verificables** | integración | `uv run pytest tests/integracion/test_contenido_duplicado.py -q` | ❌ W0 | ⬜ pending |
| 01-02·T? | 01-02 | 2 | VIA-05 | — | Viaje↔Remito N:M y peso teórico nulo en el dominio | unit | `uv run pytest tests/dominio -q` | ❌ W0 | ⬜ pending |
| 01-05·T? | 01-05 | 3 | VIA-05 | — | Viaje con 3 remitos y remito repartido en 2 viajes, en el esquema | integración | `uv run pytest tests/integracion/test_esquema_viaje_remito.py -q` | ❌ W0 | ⬜ pending |
| 01-10·T2 | 01-10 | 5 | INT-04 | T-03 | Ningún adaptador emite verbos ni sentencias de escritura | arquitectura | `uv run pytest tests/arquitectura/test_adaptadores_son_solo_lectura.py -q` | ❌ W0 | ⬜ pending |
| 01-10·T2 | 01-10 | 5 | INT-04 | T-03 | **Anti-vacuidad:** falla si el conjunto de adaptadores inspeccionados está vacío | arquitectura | `uv run pytest tests/arquitectura/test_adaptadores_son_solo_lectura.py -q` | ❌ W0 | ⬜ pending |
| 01-05·T1 | 01-05 | 3 | INT-05 | T-01-04 | `payload_crudo` tiene las 12 columnas, con `anonimizado` NOT NULL y sin default | integración | `uv run pytest tests/integracion/test_esquema_payload_crudo.py -q` | ❌ W0 | ⬜ pending |
| 01-10·T1 | 01-10 | 5 | INT-05 | T-04 | El payload crudo se persiste con petición, instante, código y duración | integración | `uv run pytest tests/integracion/test_payload_crudo.py -q` | ❌ W0 | ⬜ pending |
| 01-10·T2 | 01-10 | 5 | INT-05 | T-04 | **Cobertura:** cada adaptador descubierto graba — `payload_crudo` crece en 1 por consulta | integración | `uv run pytest tests/integracion/test_payload_crudo.py -q` | ❌ W0 | ⬜ pending |
| 01-05·T3 | 01-05 | 3 | DIS-05 | — | La migración preserva datos fila por fila, incluidos los casos feos | migración | `uv run pytest tests/migracion -q` | ❌ W0 | ⬜ pending |
| 01-05·T3 | 01-05 | 3 | DIS-05 | — | **Caso adverso:** una migración que perdería datos falla la prueba | migración | `uv run pytest tests/migracion -q` | ❌ W0 | ⬜ pending |
| 01-01·T2 | 01-01 | 1 | DIS-06 | T-02 | Toda la suite corre bajo ruta con espacios y acentos (fixture de sesión `autouse`) | integración | `uv run pytest -q -m "not lenta"` | ❌ W0 | ⬜ pending |
| 01-01·T2 | 01-01 | 1 | DIS-06 | — | **Anti-vacuidad:** `pytest_sessionfinish` falla si `testscollected == 0`; prohibido `pytest.skip` de sesión | integración | `uv run pytest -q -m "not lenta"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

### Estrategias de muestreo que NO son una sola aserción

Tres criterios de éxito no se prueban con un `assert`. El planner debe convertir cada uno en
tareas separadas, no colapsarlas:

**Criterio 3 — transacción cortada (dos modos de fallo).**
- **Modo A — fallo lógico:** `monkeypatch` sobre `UnidadDeTrabajo.confirmar` lanzando excepción.
  Milisegundos, determinista, compuerta bloqueante. Prueba que el **orden del código** es correcto.
- **Modo B — muerte del proceso:** `subprocess` + `TerminateProcess` en un punto de sincronización
  por archivo centinela. **20 repeticiones con el punto de muerte desplazado ±50 ms** alrededor del
  commit. Marcado `lenta`. Prueba que **WAL recupera**, que es una propiedad distinta.
- **Invariante medida:** `filas_persistidas − archivos_en_disco = ∅` + `PRAGMA integrity_check = ok`.

**Criterio 5 — frescura del frame (se mide la pendiente, no el valor).**
- Muestreo ≈5 Hz, una muestra `(t, antigüedad_ms)` por entrega.
- **Tres criterios de aprobación simultáneos:** pendiente < 5 ms/s · `mediana(2ª mitad) ≤ mediana(1ª mitad) × 1,5` · `frames_descartados > 0`.
- **Dos pruebas del mismo comportamiento:** `test_frescura_acotada` (60 s, bloqueante) y
  `test_frescura_sostenida_diez_minutos` (600 s, `lenta`). **No se usa reloj virtual** — el fenómeno
  medido *es* la acumulación de buffers reales de FFmpeg y un reloj falso lo haría desaparecer.

**Criterio 6 — migración que preserva.**
- Sembrar en versión N−1 con los casos feos → `sqlite3.backup` → migrar → comparar **fila por fila**
  (no contar) → `PRAGMA foreign_key_check` → `PRAGMA integrity_check`.
- **Caso adverso obligatorio:** un test que verifica que una migración que *perdería* datos falla la
  prueba. Sin él, la prueba de migración es un espejo del código de migración y no verifica nada.

### Pruebas de la prueba (anti-vacuidad)

Estas verificaciones existen para que una compuerta mal escrita no pase siempre en silencio.
Son tareas propias, no notas al pie:

- **NUC-01:** introducir temporalmente un módulo con `import cv2` en `dominio/` y verificar que
  `lint-imports` devuelve exit 1 con la cadena del import ofensor.
- **NUC-04:** bloqueo de red (`socket.socket` monkeypatcheado para explotar) durante la suite de
  contrato, para que "corre sin sistemas externos" no sea una ilusión de caché.
- **INT-04:** aserciones anti-vacuidad en el test de solo-lectura — debe fallar si el conjunto de
  adaptadores inspeccionados está vacío.
- **EVI-05:** alterar **un byte en tres posiciones distintas** (primero, medio, último) para
  descartar que la lectura esté truncando.
- **CAP-04:** `frames_descartados == 0` con un consumidor más lento que la fuente es un fallo, no un
  éxito — significa que la latencia se está acumulando en otro lado.

---

## Wave 0 Requirements

- [ ] `pyproject.toml` — `[tool.pytest.ini_options]` con `markers = ["lenta: ..."]`, `testpaths`, `pythonpath`
- [ ] `pyproject.toml` — `[tool.importlinter]` con los **cuatro** contratos: los tres de RESEARCH § Patrón 1 más `sin_deserializacion_insegura` que agregaron los planes — cubre NUC-01, D-47
- [ ] `tests/arquitectura/test_invariantes_de_codigo.py` + `tests/arquitectura/invariantes/inv_01_0N.py` (uno por plan) — reemplaza todo criterio basado en `grep`, inverificable en Windows (D-54)
- [ ] `pyproject.toml` — `[dependency-groups]` con el grupo `dominio` aislado — cubre D-52
- [ ] `tests/conftest.py` — fixture de sesión con ruta con espacios y acentos (DIS-06), fixture de motor SQLite, fixture de reloj determinista
- [ ] `tests/arquitectura/test_dominio_aislado.py` + su script de subproceso — NUC-01
- [ ] `tests/arquitectura/test_adaptadores_son_solo_lectura.py` con aserciones anti-vacuidad — INT-04
- [ ] `tests/contrato/conftest.py` — parametrización falso ↔ cassette — NUC-04
- [ ] `tests/recursos/videos/` — video sintético generado en `conftest` (el real llega con D-58/D-59) — CAP-03
- [ ] Script de compuerta de CI en Windows: encadena pytest + lint-imports + entorno aislado + licencias y propaga el peor exit code — D-53, D-54
- [ ] Activación del modo UTF-8 en el punto de entrada de la CLI — D-50
- [ ] Instalación del framework: `uv sync` (pytest ya está en el conjunto verificado)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| GET real contra PALJET y persistencia de su payload crudo como cassette con `origen: "real"` | INT-05, NUC-04 | Requiere credenciales y conectividad a un sistema de terceros al que hoy **no hay acceso** (Open Question 1 del research). No automatizable en CI. | Con acceso disponible: ejecutar el comando de descubrimiento del puerto PALJET (solo GET), verificar que el cassette queda con `origen: "real"` y payload crudo íntegro, y que el doble derivado reproduce la forma. |
| GET real contra la balanza y su cassette | INT-05, NUC-04 | Requiere hardware físico / endpoint de la balanza, hoy sin acceso (Open Question 2). | Ídem PALJET, contra el endpoint de la balanza. |
| Estado de deuda declarada cuando un cassette tiene `origen: "sintetico"` | NUC-04 | Es un juicio de reporte, no una aserción: D-43 permite completar la fase con cassette sintético, pero **VERIFICATION.md debe reportarlo como cumplido-con-deuda, no como cumplido**. | Al cerrar la fase, inspeccionar el campo `origen` de cada cassette y reflejarlo textualmente en VERIFICATION.md. |

---

## Validation Sign-Off

- [x] Todas las tareas tienen verify `<automated>` o dependencia declarada de Wave 0
- [x] Continuidad de muestreo: no hay 3 tareas consecutivas sin verify automatizado
- [x] Wave 0 cubre todas las referencias MISSING
- [x] Sin flags de watch-mode
- [x] Feedback latency declarada honestamente (4 min en la suite rápida, no 90 s)
- [x] Las **cinco** pruebas-de-la-prueba están planificadas como tareas propias: NUC-01 (`01-01·T3`, sabotaje `import cv2`), NUC-04 (`01-08·T3`, red bloqueada), INT-04 (`01-10·T2`, anti-vacuidad del conjunto de adaptadores), EVI-05 (`01-04·T2`, byte alterado en tres posiciones), CAP-04 (`01-03·T3`, cero descartes es fallo)
- [x] Ningún criterio de aceptación depende de `grep` — todos migrados a invariantes de pytest
- [x] `nyquist_compliant: true` seteado en el frontmatter
- [ ] `wave_0_complete: true` — **pendiente hasta que la ola 0 se ejecute**

**Approval:** approved 2026-07-26 (planificación). La ola 0 todavía no corrió: `wave_0_complete` sigue en `false` a propósito.
