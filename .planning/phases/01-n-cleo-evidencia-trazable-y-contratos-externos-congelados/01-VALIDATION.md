---
phase: 1
slug: n-cleo-evidencia-trazable-y-contratos-externos-congelados
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-25
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
| **Compuerta de aislamiento (runtime)** | `uv run --isolated --no-project python tests/arquitectura/test_dominio_aislado.py` |
| **Compuerta de licencias** | `uv run pip-licenses --allow-only "<lista blanca>"` |
| **Plataforma de la compuerta** | **Windows únicamente** (D-54) |
| **Marcadores** | `lenta` — tanda programada, no bloquea la fusión (D-53) |
| **Estimated runtime** | Suite rápida ~90 s (incluye `test_frescura_acotada` de 60 s) · Suite completa ~15 min (incluye las `lenta`) |

---

## Sampling Rate

- **Después de cada commit de tarea:** `uv run pytest -q -m "not lenta"` + `uv run lint-imports --no-cache`
- **Después de cada wave:** suite rápida completa + prueba de entorno aislado + inventario de licencias
- **Antes de `/gsd-verify-work`:** suite completa **incluidas las `lenta`** (frescura de 10 minutos, 20 repeticiones de muerte del proceso) en verde
- **Tanda programada (D-53):** las `lenta` abren un asunto al fallar, no traban la fusión
- **Max feedback latency:** 90 s (suite rápida). El único test que domina esa cifra es `test_frescura_acotada` (60 s), y es deliberado: medir acumulación de buffers reales exige tiempo real.

---

## Per-Task Verification Map

> Los IDs de tarea se completan cuando el planner emita los PLAN.md. Hasta entonces, el mapa se
> ancla a nivel de requisito — es el contrato que cada tarea debe heredar.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | 0 | NUC-01 | — | El dominio no importa cv2/onnxruntime/PySide6 (estático) | arquitectura | `uv run lint-imports --no-cache` | ❌ W0 | ⬜ pending |
| TBD | TBD | 0 | NUC-01 | — | El dominio se importa entero sin esos paquetes instalados | arquitectura | `uv run --isolated --no-project python tests/arquitectura/test_dominio_aislado.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | NUC-04 | — | Todo puerto de salida tiene doble; el sistema corre sin hardware | contrato | `uv run pytest tests/contrato -q` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | NUC-04 | — | Los cuatro datos feos existen y se ejercitan | contrato | `uv run pytest tests/contrato/test_datos_feos.py -q` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | NUC-05 | T-01 (manipulación de evidencia) | Estado + evidencia + outbox en una sola transacción | integración | `uv run pytest tests/integracion/test_transaccion_unica.py -x -q` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | NUC-06 | — | La bitácora rota archivos y respeta el nivel configurado | unit | `uv run pytest tests/integracion/test_bitacora.py -q` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | CAP-03 | — | La fuente de archivo entrega frames en los dos modos | integración | `uv run pytest tests/integracion/test_fuente_archivo.py -q` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | CAP-04 | — | La antigüedad del frame no crece; los descartes se cuentan | integración | `uv run pytest tests/integracion/test_frescura.py -q` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | CAP-04 | — | Frescura sostenida durante 10 minutos | integración (`lenta`) | `uv run pytest tests/integracion/test_frescura.py -m lenta -q` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | EVI-05 | T-01 | La huella se calcula en ingesta y se persiste | unit | `uv run pytest tests/dominio/test_huella.py -q` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | EVI-05 | T-01 | Recalcular reproduce el valor; un byte alterado lo rompe | integración | `uv run pytest tests/integracion/test_verificacion_huella.py -q` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | EVI-06 | T-02 (path traversal) | La imagen va al filesystem; la base sólo metadatos y ruta relativa | integración | `uv run pytest tests/integracion/test_almacen_evidencia.py -q` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | VIA-05 | — | Viaje con 3 remitos y remito repartido en 2 viajes | integración | `uv run pytest tests/integracion/test_esquema_viaje_remito.py -q` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | INT-04 | T-03 (escritura a sistema externo) | Ningún adaptador emite verbos ni sentencias de escritura | arquitectura | `uv run pytest tests/arquitectura/test_adaptadores_son_solo_lectura.py -q` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | INT-05 | T-04 (secretos en payload) | El payload crudo se persiste con petición, instante, código y duración | integración | `uv run pytest tests/integracion/test_payload_crudo.py -q` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DIS-05 | — | La migración preserva datos, incluidos los casos feos | migración | `uv run pytest tests/migracion -q` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DIS-06 | T-02 | Todo funciona en ruta con espacios y acentos | integración | `uv run pytest -q -k "acentos"` (fixture de sesión aplicada a toda la suite) | ❌ W0 | ⬜ pending |

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
- [ ] `pyproject.toml` — `[tool.importlinter]` con los tres contratos de RESEARCH § Patrón 1 — cubre NUC-01, D-47
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

- [ ] Todas las tareas tienen verify `<automated>` o dependencia declarada de Wave 0
- [ ] Continuidad de muestreo: no hay 3 tareas consecutivas sin verify automatizado
- [ ] Wave 0 cubre todas las referencias MISSING
- [ ] Sin flags de watch-mode
- [ ] Feedback latency < 90 s en la suite rápida
- [ ] Las tres pruebas-de-la-prueba (NUC-01, NUC-04, INT-04) están planificadas como tareas propias
- [ ] `nyquist_compliant: true` seteado en el frontmatter

**Approval:** pending
