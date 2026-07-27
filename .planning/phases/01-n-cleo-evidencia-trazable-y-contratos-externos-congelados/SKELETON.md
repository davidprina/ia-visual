# Walking Skeleton — Sistema de Control de Portería con Visión Artificial

**Phase:** 1
**Generated:** 2026-07-25
**Identificador técnico del producto:** `porteria` (nombre comercial diferido — D-36)

---

## Capacidad probada de punta a punta

> Una sola orden de consola sobre un archivo de video deja la imagen en el almacén de evidencia
> con su huella SHA-256 verificable y su fila de metadatos, escritas en una única transacción,
> sobre un esquema que ya modela viaje con varios remitos y peso teórico ausente.

```
uv run porteria capturar --fuente tests/recursos/videos/sintetico.mp4
```

Resultado observable:
- `<raiz_evidencia>/AAAA/MM/DD/<sha256>.jpg` existe (1 archivo)
- `item_evidencia` tiene 1 fila con `sha256`, `ruta_relativa` (relativa, separador `/`), `capturado_en_utc_iso`,
  `desfasaje_local_min`, `fecha_local`, `instante_monotono_ns`, `desvio_ms`, `ventana_vigente_ms`, `miniatura`
- `uv run porteria verificar-huellas` recalcula la huella y reproduce el valor persistido
- Alterar un byte del `.jpg` hace que la verificación reporte la evidencia como `COMPROMETIDA`

La rebanada se completa al final del **plan 01-07**. Los planes 01-01 a 01-06 construyen sus piezas;
la prueba de aceptación `tests/aceptacion/test_rebanada_captura.py` se escribe **primero**, en el plan
01-01, marcada `xfail(strict=True)`, y el plan 01-07 le quita el marcador. Si pasara antes de tiempo,
`strict=True` hace fallar la suite — es la señal de que la rebanada se cerró sin querer.

---

## Decisiones arquitectónicas

| Decisión | Elección | Fundamento |
|---|---|---|
| Lenguaje y runtime | **Python 3.12.12** (pinneado con `uv python pin`) | Único punto donde todas las ruedas del stack tienen build `cp312-win_amd64` verificado. Arrastra el costo del reloj (ver fila siguiente) |
| Reloj del proceso | **`time.perf_counter_ns()`**, nunca `time.monotonic()` | En Python 3.12 sobre Windows `monotonic` usa `GetTickCount64()` con **15,625 ms** de resolución; medir ±150 ms con eso es 10 % de error de cuantización antes de empezar. `perf_counter` da 100 ns. **No retrofiteable**: contamina evidencia ya persistida |
| Sello absoluto | `datetime.now(timezone.utc)` sólo en el **ancla**; el resto se deriva del delta monotónico | El desvío entre cámaras se calcula íntegramente en espacio `perf_counter` (microsegundos); el sello UTC absoluto hereda ~15,6 ms de incertidumbre y eso se declara en el manifiesto |
| Arquitectura | **Hexagonal**, dependencias hacia adentro: `cli` → `infraestructura` → `aplicacion` → `dominio` | `dominio/` con cero dependencias externas es el criterio de éxito 1 y la compuerta automática que lo hace real en vez de decorativo |
| Layout del proyecto | **`src/porteria/`** (src layout obligatorio) | Con layout plano `import porteria` toma el código del directorio de trabajo y la prueba de entorno aislado de D-52 pierde sentido |
| Idioma del código | **Dominio en español** (`Viaje`, `Remito`, `CapturaDeControl`, `PesoTeorico`), infraestructura y bibliotecas en inglés (D-32) | Cuando el portero dice "remito" y el código dice "remito", desaparece la capa de traducción donde se cuelan los errores de interpretación |
| Persistencia | **SQLite 3.50.4 + SQLAlchemy 2.0.51 (estilo `Mapped[]`) + Alembic 1.18.5** | Un puesto fijo, un proceso escritor, backup = copiar un archivo. `CLAUDE.md` dice Alembic 1.16.x y está desactualizado |
| PRAGMAs de la aplicación | `journal_mode=WAL`, `synchronous=FULL`, `busy_timeout=5000`, `foreign_keys=ON` | `FULL` en WAL hace un sync adicional tras cada commit: la transacción confirmada sobrevive a un **corte de energía**, no sólo al cierre del proceso (D-14) |
| PRAGMAs de migración | Motor **dedicado** con `foreign_keys=OFF` | `batch_alter_table` hace DROP+CREATE de la tabla real y choca con `foreign_keys=ON`. Emitir el PRAGMA dentro de la transacción es un no-op; emitirlo antes rompe por el autobegin de SQLAlchemy 2.0 |
| Evidencia en disco | **Filesystem**, `evidencia/AAAA/MM/DD/<sha256>.jpg`; en la base sólo metadatos y **ruta relativa** (D-03, D-06) | Carpeta por fecha para navegabilidad y para no meter cientos de miles de archivos en un directorio NTFS; nombre derivado del contenido para conservar la propiedad anti-manipulación |
| Escritura de evidencia | `tempfile.mkstemp` **en el directorio destino** → `flush` → `os.fsync(fd)` → **`os.replace`** | `os.rename` sobre un archivo existente falla en Windows (`FileExistsError`); `os.fsync` sobre un **directorio** lanza `PermissionError` en Windows y hay que guardar ese paso tras `if os.name != "nt"` |
| Orden transaccional | **Archivo primero**, transacción única después (D-12) | No existe transacción distribuida FS↔SQLite: se elige cuál huérfano se tolera. Un archivo huérfano es basura recuperable; una fila huérfana es evidencia rota |
| Miniaturas | **Blob de ~15 KB dentro de SQLite** (D-04) | Para blobs de ese tamaño SQLite supera al filesystem, y la grilla de consulta de la Fase 9 se pinta con una sola query. Las imágenes completas nunca van a la base |
| Fechas persistidas | **Texto ISO-8601 con offset** (`String(32)`) + `desfasaje_local_min` entero + `fecha_local` texto | `DateTime(timezone=True)` en SQLite **pierde el tzinfo al leer** y el código que después hace `.astimezone()` desplaza todo el histórico |
| Contrato de frescura | **Slot de capacidad 1 con descarte del más viejo** y contador de descartes (CAP-04) | Medido: la cola ilimitada acumula **+806 ms de latencia por segundo** de operación; el slot baja de 25,8 a 13,9 ms. `queue.Queue(maxsize=1)` bloquea al productor; `deque(maxlen=1)` no ofrece espera bloqueante ni contador |
| Identidad | **Argon2id vía `argon2-cffi` 25.1.0**, formato PHC, sin credencial por defecto (D-22, D-23) | Alcance agregado por el usuario (D-18) por encima de los 79 requerimientos v1. Cuatro roles fijos en código: Portero, Logística, Compras, Administración |
| Sistemas externos | **Solo lectura, triple barrera**: cliente sin verbos de escritura + guardia `before_cursor_execute` + prueba de arquitectura que falla la construcción (D-47) | Regla global del usuario y INT-04. La barrera **real** es la credencial con `GRANT SELECT`; las dos de código son defensa en profundidad |
| Payload crudo = cassette | **Un solo mecanismo, dos propósitos** (INT-05 + D-41) | El payload crudo que INT-05 exige persistir **es** exactamente un cassette. Cubre los dos caminos de D-44 (HTTP y SQL), donde `vcrpy` sólo cubriría HTTP |
| Superficie de entrada | **Línea de comandos en español** (Typer 0.27.0), permanente en el producto vendido (D-49, D-50) | No hay interfaz gráfica en la Fase 1. La CLI sobrevive como herramienta de diagnóstico remoto |
| Encoding de consola | `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` como **primera línea** del punto de entrada | La consola de Windows es cp1252 y una CLI en español revienta con `UnicodeEncodeError`. Es la única vía que sobrevive al empaquetado con PyInstaller sin depender del entorno del cliente |
| Compuerta de CI | **Windows únicamente** (D-54), rápida bloquea la fusión, `lenta` en tanda programada (D-53) | Rutas con espacios y acentos, nombres de usuario con ñ y el renombrado atómico se comportan distinto ahí |

---

## Estructura de directorios (contrato para las once fases siguientes)

```
pyproject.toml            uv · ruff · pytest · import-linter · dependency-groups
uv.lock                   lockfile determinista
alembic.ini
scripts/compuerta.py      encadena las cuatro compuertas y propaga el peor exit code
src/porteria/
├── dominio/              CERO dependencias externas — compuerta de CI
│   ├── comun/            identificadores · tiempo · resultado
│   ├── evidencia/        CapturaDeControl · ItemDeEvidencia · HuellaDeIntegridad · Manifiesto · Lapida
│   ├── viaje/            Viaje · Remito · Articulo · PesoTeorico (nulable)
│   ├── auditoria/        RegistroEncadenado + regla de encadenamiento
│   ├── identidad/        Usuario · Rol (4 fijos) · política de contraseña
│   └── eventos.py
├── aplicacion/
│   ├── puertos/entrada/  ApiDePorteria · Comando*
│   ├── puertos/salida/   FuenteDeVideo · AlmacenDeEvidencia · Reloj · ProveedorDe* · RepositorioDe*
│   ├── casos_de_uso/
│   ├── servicios/
│   ├── unidad_de_trabajo.py
│   └── dto/              Pydantic, versionados desde el primer mensaje
├── infraestructura/
│   ├── video/            archivo.py · falsa.py · slot_ultimo_valor.py · metricas.py
│   ├── imagen/           codificador JPEG + miniatura
│   ├── persistencia/     sqlite/ · migraciones/ · evidencia_fs.py
│   ├── externos/         comun/ · paljet/ · balanza/ · geomov/
│   ├── transporte/       contrato.py · en_memoria/ · ipc/ (VACÍO, recordatorio)
│   ├── runtime/          reloj.py · bitacora.py
│   ├── seguridad/        argon2-cffi
│   └── configuracion/    pydantic-settings, dos capas
├── cli/
│   ├── app.py            Typer; descubre y registra los módulos de cli/ordenes/
│   └── ordenes/          una orden por módulo, con función registrar(app)
└── composicion/arranque.py   composition root — único módulo que conoce a todos
tests/
├── dominio/ contrato/ arquitectura/ migracion/ integracion/ aceptacion/ lentas/
└── recursos/videos/      recortes cortos versionados (D-59)
```

**Regla de extensión para las fases 2 a 12:** una orden nueva de la CLI se agrega creando
`cli/ordenes/<nombre>.py` con una función `registrar(app)`. Ningún plan edita `cli/app.py`.
Esto es lo que permite que planes de la misma ola no colisionen sobre el mismo archivo.

---

## Stack tocado en la Fase 1

- [x] Andamiaje del proyecto (uv, ruff, pytest, import-linter, dependency-groups, lockfile)
- [x] Punto de entrada real — la orden `porteria capturar` sobre un archivo de video
- [x] Base de datos — una escritura real (fila de evidencia + manifiesto + bitácora + outbox en una transacción) y una lectura real (`porteria verificar-huellas`)
- [x] Sistema de archivos — una escritura atómica real con huella SHA-256 verificable
- [x] Migraciones — línea base de Alembic + una migración con su prueba de preservación de datos
- [x] Compuerta ejecutable — `scripts/compuerta.py` en Windows, encadenando pytest + import-linter + entorno aislado + inventario de licencias
- [ ] Interfaz gráfica — **no existe en la Fase 1 por diseño** (Fases 2 y 3)
- [ ] Instalador — Fase 11

---

## Fuera de alcance (diferido a rebanadas posteriores)

Lista explícita para que ninguna fase futura vuelva a litigar el minimalismo de la Fase 1:

- Pantalla de inicio de sesión y de cambio de operador → Fase 2 o 3
- Gestión de usuarios desde la interfaz (alta, baja, cambio de contraseña, recuperación) → fase de interfaz
- Cámaras IP por RTSP con PyAV, reconexión y estado por fuente → Fase 2
- Captura sincronizada de N cámaras con ventana mirando hacia atrás → Fase 3
- Cualquier inferencia, detección o lectura de patentes → Fases 4 y 5
- Herramienta operable de purga manual de evidencia (la Fase 1 fija el esquema de **lápida** y la invariante de no borrado automático) → Fase 9 u 11
- Política concreta de retención en meses → antes del instalador
- Medición en campo de la ventana de sincronía (±150 ms de D-39 queda marcado **no validado**) → Fase 2 o 3
- Adaptadores reales de balanza y PALJET (la Fase 1 congela el **contrato**, no la implementación) → Fase 10
- Réplica de evidencia a NAS, inicio de sesión único, política corporativa de contraseñas, modelado de turnos → fuera de v1
- Nombre comercial del producto → antes del instalador de la Fase 11

---

## Deuda declarada que la fase abre (D-43)

| Deuda | Motivo | Qué la cierra |
|---|---|---|
| Cassette de PALJET con `origen: "sintetico"` | No hay acceso ni credenciales al ejecutar la fase (Open Question 1 de RESEARCH) | Un GET real registrado con `origen: "real"`, sin cambiar una línea de código de producción |
| Cassette de la balanza con `origen: "sintetico"` | Ídem (Open Question 2) | Ídem |
| Credencial de PALJET con `GRANT SELECT` verificado por escrito | La barrera real es la credencial; las dos de código son defensa en profundidad | Solicitud por escrito al DBA del cliente + registro del permiso efectivo en el documento de contratos congelados |
| Video de referencia real filmado en portería (D-58, D-59) | No existe todavía; las pruebas de cañería corren con video sintético | Acuerdo escrito con el cliente + recortes versionados |

**Consecuencia para el cierre de la fase:** mientras un cassette tenga `origen: "sintetico"`, el
Criterio de Éxito 4 se reporta en `VERIFICATION.md` como **cumplido con deuda declarada**, nunca
como cumplido. D-43 permite completar la fase; no permite fingir que el contrato se congeló.

---

## Plan de rebanadas siguientes

Cada fase posterior agrega una rebanada vertical sobre este esqueleto sin alterar sus decisiones
arquitectónicas:

- **Fase 2:** el operador ve en vivo cámaras IP, webcam y archivos con estado honesto por fuente
- **Fase 3:** un botón, todas las cámaras, el mismo instante, el desvío medido y persistido
- **Fase 4:** detección por IA sobre ONNX Runtime con el proveedor real expuesto
- **Fase 5:** lectura de patente como sugerencia confirmable
- **Fase 6:** viaje precargado, captura vinculada y liberación
- **Fase 7:** auditoría de peso con tolerancias y excepciones registradas
- **Fase 8:** ingreso de proveedores, documentación y SLA de espera
- **Fase 9:** consulta, evidencia exportable y vista de solo lectura para Compras
- **Fase 10:** los dobles se sustituyen por los adaptadores reales sin tocar el dominio
- **Fase 11:** instalador firmado y resiliencia en planta
- **Fase 12:** motor de visión clásica seleccionable en caliente
