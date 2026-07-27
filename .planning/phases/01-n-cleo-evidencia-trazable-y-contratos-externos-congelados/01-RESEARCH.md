# Phase 1: Núcleo, evidencia trazable y contratos externos congelados — Investigación

**Researched:** 2026-07-25
**Domain:** Arquitectura hexagonal en Python, persistencia transaccional evidencia↔SQLite, escritura atómica con huella criptográfica, contrato de frescura de frame, descubrimiento de contratos externos de solo lectura
**Confidence:** HIGH (la mayoría de las afirmaciones críticas se verificaron ejecutando código en esta máquina, Windows 11 + Python 3.12.12)

> **Nota metodológica.** Este documento distingue tres niveles de procedencia:
> `[VERIFICADO: <cómo>]` = comprobado ejecutando código o consultando el registro en esta sesión ·
> `[CITADO: <url>]` = tomado de documentación oficial · `[SUPUESTO]` = conocimiento de entrenamiento, sin verificar.
> Context7 no estuvo disponible en esta sesión; la vía de documentación fue WebFetch contra sitios oficiales
> más **ejecución real de sondas** en Python 3.12 sobre Windows, que es evidencia más fuerte que cualquier búsqueda.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Evidencia: formato, contenido y almacenamiento**

- **D-01:** Las imágenes se persisten en **JPEG con calidad configurable por cámara**, admitiendo configuración sin pérdida donde el detalle lo exija (por ejemplo la cámara de patentes). La calidad es un parámetro por cámara, no una constante del producto.
- **D-02:** Se persiste el **frame limpio**, tal como salió del decodificador. Fecha, patente y cajas de detección se dibujan al visualizar o al exportar, leídas de los metadatos. Nunca se queman datos en el píxel.
- **D-03:** Organización en disco: **`evidencia/AAAA/MM/DD/<sha256>.jpg`**. Carpeta por fecha para navegabilidad humana y para evitar el problema de NTFS con cientos de miles de archivos en un mismo directorio; nombre derivado del contenido para conservar la propiedad anti-manipulación. Se descartó el almacén direccionado por contenido puro.
- **D-04:** Se genera **miniatura en el momento de la ingesta**, guardada como blob pequeño (~15 KB) dentro de SQLite.
- **D-05:** **Metadatos de procedencia amplios y sólo en la base**, nunca embebidos en el archivo: cámara, perfil de flujo, resolución y códec de origen, instante monotónico, instante UTC con su desfasaje, desvío contra el instante objetivo, versión de la aplicación, versión del esquema, y motor con versión de modelo cuando corresponda.
- **D-06:** **Dos raíces de almacenamiento independientes y configurables**: la base en disco local rápido, la evidencia en la ruta o disco que el cliente elija. En la base se persiste **ruta relativa a la raíz de evidencia, nunca absoluta**.
- **D-07:** Si al arrancar la raíz de evidencia no está disponible, la aplicación **arranca degradada**: estado en rojo indicando ruta esperada y encontrada, permite consultar lo ya persistido y reparar la configuración, y **bloquea nuevas capturas** hasta resolver.

**Integridad y cadena de custodia**

- **D-08:** La integridad se construye en **tres niveles**: huella SHA-256 por imagen, hash del manifiesto de cada captura, y **bitácora de auditoría encadenada** donde cada registro incluye el hash del anterior. **El encadenamiento debe arrancar en el registro número uno** — no es retrofiteable.
- **D-09:** Cuando la huella recalculada no coincide, la evidencia se **marca como comprometida y se muestra así** en toda pantalla, listado y exportación, y el hallazgo entra en la bitácora con instante y ruta. Nunca se borra ni se oculta.
- **D-10:** El sistema **nunca borra evidencia por sí solo**. Existe una purga manual por antigüedad que deja **lápida**: fila con hash, motivo, autor e instante. **La Fase 1 fija el esquema de la lápida y la invariante; la herramienta operable de purga se difiere.**
- **D-11:** La **bitácora técnica** (NUC-06) y la **bitácora de auditoría** son dos cosas separadas: la técnica va a archivos rotativos con nivel configurable y es borrable sin consecuencias; la de auditoría vive en la base, sólo agrega y va encadenada por hash.

**Atomicidad y durabilidad**

- **D-12:** Orden de escritura: **archivo primero** en temporal, sincronizado a disco y renombrado atómicamente a su ruta final; **recién entonces** la transacción de la base confirma fila, manifiesto y outbox juntos. Un corte sólo puede dejar archivos sin fila, nunca filas sin archivo.
- **D-13:** Al arrancar, los archivos huérfanos se **mueven a cuarentena** con su fecha y quedan listados en el estado del sistema. No se eliminan. El barrido corre en segundo plano para no demorar el arranque.
- **D-14:** SQLite corre en **modo WAL con sincronización completa** (`synchronous=FULL`) en cada confirmación.

**Fuente de video y frescura del frame**

- **D-15:** El puerto de fuente de video declara **dos perfiles desde el día uno**: perfil de monitoreo y perfil de evidencia. En la Fase 1 la fuente de archivo devuelve el mismo flujo para ambos.
- **D-16:** La fuente de archivo soporta **dos modos de reproducción elegibles**: tiempo real y velocidad máxima (para pruebas deterministas en integración continua).
- **D-17:** Métricas por fuente **en memoria** — antigüedad del frame, frames descartados, fps efectivos, reconexiones — consultables mediante una orden de la línea de comandos. Sin escritura en el camino crítico.

**Identidad, autoría y roles**

- **D-18:** **Hay usuarios con contraseña en v1.** *(Decisión del usuario por encima de la recomendación. Es alcance nuevo: no se deriva de ningún requerimiento v1.)*
- **D-19:** De ese subsistema, la Fase 1 entrega **sólo el modelo de usuarios, el almacenamiento seguro de la credencial, la columna de autor en toda fila auditable y el actor en la bitácora encadenada**. El alta y la verificación se ejercitan por línea de comandos.
- **D-20:** **Cuatro roles fijos del negocio**: Portero, Logística, Compras y Administración. Permisos definidos en código, no configurables.
- **D-21:** **La captura nunca se bloquea por falta de sesión.** Si no hay sesión iniciada, la evidencia se registra con autor "no identificado", el hecho queda marcado en el registro y se contabiliza en el panel de calidad.
- **D-22:** Credenciales protegidas con **Argon2id** con parámetros modernos y sal por usuario. Única exigencia de política: longitud mínima razonable. **Sin caducidad forzada ni reglas de complejidad.**
- **D-23:** **No existe ninguna credencial por defecto en el producto.** Un asistente de primer arranque crea el administrador inicial junto con las rutas de datos. En la Fase 1 el asistente es una orden de línea de comandos.
- **D-24:** **Identidad propia, independiente del usuario de Windows.** El usuario de Windows se registra sólo como dato de diagnóstico.
- **D-25:** Un usuario que ya firmó evidencia **no se elimina, se desactiva**.
- **D-26:** **La sesión no se cierra sola.** Cambio de operador explícito, con el nombre del operador activo siempre visible.

**Esquema de datos**

- **D-27:** La Fase 1 modela **sólo lo no retrofiteable, completo y ejercitado**: captura, evidencia, manifiesto, bitácora encadenada, usuarios y roles, viaje↔remito muchos a muchos, artículos con peso teórico nulable, payload crudo externo y outbox.
- **D-28:** **Una captura puede existir sin viaje ni movimiento asociado.** Nace autónoma y se vincula después.
- **D-29:** **Doble identificador**: opaco único universal para uso interno, más un número legible por año del estilo `2026-001842`.
- **D-30:** Configuración en **dos capas**: archivo mínimo de arranque (ruta de la base y raíz de evidencia); **todo lo demás en la base**, editable desde la interfaz, incluido en la copia de seguridad y con registro de quién lo cambió y cuándo.
- **D-31:** El **peso teórico ausente** se modela como peso nulable por artículo. El estado del remito **no se persiste: se deriva**.
- **D-32:** **Idioma del código: dominio en español** (`Viaje`, `Remito`, `CapturaDeControl`, `PesoTeorico`), **infraestructura y bibliotecas en inglés**.

**Migraciones y versionado**

- **D-33:** Cada migración entra con una **prueba automática que siembra, migra y compara**, incluidos los casos feos (viaje con tres remitos, remito compartido, peso nulo, rutas con acentos).
- **D-34:** **Copia de seguridad automática de la base antes de cada migración.** Se conservan las últimas copias y se informa cuánto ocupan.
- **D-35:** **Versión de producto y versión de esquema separadas, con compatibilidad declarada.** Si la base es más nueva que la aplicación, se niega a abrir con un mensaje claro.
- **D-36:** **Nombre comercial diferido.** Se usa el identificador técnico neutro `porteria`.

**Tiempo y sincronía**

- **D-37:** La fecha que agrupa evidencia y reportes es la **zona local del equipo**. *(Decisión del usuario. Costo señalado y aceptado.)* En la base se sigue persistiendo el instante UTC junto con su desfasaje.
- **D-38:** Un día corta a **medianoche local**. Sin parámetros de jornada ni modelado de turnos.
- **D-39:** **Ventana de aceptación por defecto: ±150 ms**, **marcada explícitamente como no validada** con el cliente ni medida en campo.
- **D-40:** El parámetro de ventana **sólo lo cambia el rol de Administración**, el cambio queda en la bitácora, y **cada captura guarda cuál era la ventana vigente en el momento en que se hizo**.

**Descubrimiento de contratos externos**

- **D-41:** El descubrimiento **recorre todo lo que el dominio va a necesitar**: chofer, camión, transportista, remito con sus artículos y pesos teóricos, y la lectura de peso con su estado de estabilidad. Cada respuesta se guarda como cassette.
- **D-42:** Los cassettes se **anonimizan en el mismo acto de grabar**, **conservando estructura, tipos, largos, nulos y rarezas de formato**.
- **D-43:** Si no hay acceso a PALJET o a la balanza al ejecutar la fase, **la fase se completa igual**, y el descubrimiento faltante queda como **deuda bloqueante registrada con responsable y fecha**.
- **D-44:** **PALJET se consulta por los dos caminos según el dato**: interfaz de programación donde exista, consulta directa con SELECT donde la interfaz no exponga lo que el dominio necesita. *(Decisión del usuario.)*
- **D-45:** **Geomov:** se declara el puerto de telemetría con la **carga manual como implementación de referencia y camino principal**.
- **D-46:** El **payload crudo** (INT-05) se guarda íntegro y comprimido, con la petición, el instante, el código de respuesta y la duración. Purga por antigüedad configurable y **separada de la política de evidencia**.
- **D-47:** La regla de solo lectura se garantiza con **doble barrera más prueba**: un cliente compartido que no expone más verbos que GET, HEAD y OPTIONS; una conexión de base que rechaza toda sentencia que no empiece por SELECT o WITH; y encima la prueba de arquitectura que **falla la construcción**.

**Dobles de prueba y modo demostración**

- **D-48:** Los dobles de prueba con datos deliberadamente feos que exige NUC-04 **son también el modo demostración del producto**.

**Línea de comandos**

- **D-49:** La línea de comandos es una **herramienta de diagnóstico permanente que viaja en el producto vendido**, no un andamio desechable.
- **D-50:** **Todo en español, incluidas las órdenes y las opciones.** *(Decisión del usuario por encima de la convención de consola en inglés.)*
- **D-51:** Salida **legible por personas por defecto** y **estructurada bajo bandera**.

**Integración continua y calidad**

- **D-52:** La prueba de aislamiento del dominio corre en un **entorno separado que instala únicamente las dependencias que el dominio declara**. Es una prueba real, no una simulación: nada que se pueda sortear con un import diferido dentro de una función.
- **D-53:** **Bloquean la fusión** las pruebas rápidas: dominio, contrato, arquitectura, solo lectura y migración. Las de larga duración corren en **tanda programada periódica**.
- **D-54:** La compuerta corre **sobre Windows como única plataforma**.
- **D-55:** **Inventario de licencias de terceros desde el día uno**. La compuerta **falla ante una licencia contagiosa (AGPL, GPL) o no identificable**.
- **D-56:** **Pruebas antes del código para lo que la fase promete demostrar**, y después del código para el andamiaje y los adaptadores.
- **D-57:** **Cobertura medida y visible, nunca como compuerta.**

**Videos de referencia y datos de prueba**

- **D-58:** Los videos de referencia se **filman en la portería real**, guardados fuera del repositorio público.
- **D-59:** Del material real se extraen **recortes cortos y livianos** y **ésos sí se versionan** en el repositorio.

### Claude's Discretion

El usuario no delegó ninguna decisión con un "vos decidís" explícito. Quedan a criterio de investigación y planificación, por ser materia técnica y no de negocio:

- Estructura concreta de paquetes y módulos dentro de los límites que fija `ARCHITECTURE.md`.
- Bibliotecas concretas para cada responsabilidad, dentro de lo ya fijado en el stack (por ejemplo qué implementación de Argon2id, qué herramienta de inventario de licencias, qué marco de línea de comandos).
- Forma exacta de las tablas, índices y nombres de columnas, respetando D-27 a D-32.
- División de la fase en planes y su orden de ejecución.
- Parámetros concretos de Argon2id (memoria, iteraciones, paralelismo) según guía vigente.
- Mecanismo concreto de encadenamiento de la bitácora (qué campos entran en el hash y en qué orden), siempre que cumpla D-08.
- Nivel de compresión y formato concreto del payload crudo persistido.

### Deferred Ideas (OUT OF SCOPE)

**Pertenecen a fases posteriores del roadmap**
- Pantalla de inicio de sesión y de cambio de operador — Fase 2 o 3.
- Gestión completa de usuarios desde la interfaz — fase de interfaz.
- Herramienta operable de purga manual de evidencia por antigüedad — fase de consulta o de empaquetado.
- Política concreta de retención (cuántos meses) — el número se decide antes del instalador.
- Medición en campo de la ventana de sincronía (el ±150 ms de D-39) — Fase 2 o 3.
- Nombre comercial del producto — antes del instalador de la Fase 11.

**Capacidades nuevas, fuera del alcance de v1**
- Réplica de la evidencia a un recurso de red o NAS de la planta.
- Inicio de sesión único contra dominio corporativo.
- Política corporativa de contraseñas (complejidad, caducidad, historial, bloqueo por intentos).
- Muestreo periódico de métricas de fuente a la base.
- Copia de seguridad periódica programada de la base, más allá de la previa a cada migración.
- Modelado de turnos y horarios de la planta.
- Averiguar formalmente si Geomov expone alguna interfaz.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Descripción | Qué de esta investigación lo habilita |
|----|-------------|----------------------------------------|
| **NUC-01** | El paquete de dominio se importa en un entorno sin OpenCV, ONNX Runtime ni toolkit de interfaz | §Patrón 1 — doble compuerta: `import-linter` 2.13 (estático, atrapa las cuatro vías de evasión, verificado) + prueba de entorno realmente aislado con `uv run --isolated --no-project` (verificado) |
| **NUC-04** | Todos los puertos de salida tienen un doble de prueba | §Patrón 7 — jerarquía falso-en-memoria / cassette / suite de contrato compartida; §Don't Hand-Roll fila "cassette HTTP" |
| **NUC-05** | Cada operación persiste estado, evidencia y eventos en una única transacción atómica | §Patrón 3 — orden archivo-primero + una sola transacción SQLite; verificado que deja 0 filas huérfanas y N archivos huérfanos |
| **NUC-06** | Bitácora estructurada con nivel configurable y rotación automática | §Standard Stack — `structlog` 26.1.0 sobre `logging.handlers.RotatingFileHandler`; §Pitfall 9 (separación bitácora técnica ↔ auditoría) |
| **CAP-03** | Reproducción de archivos de video locales como fuente | §Patrón 4 — `cv2.VideoCapture` + `CAP_PROP_POS_MSEC` (backend FFMPEG verificado); dos modos D-16 |
| **CAP-04** | Cada fuente entrega el frame más reciente, la latencia no crece | §Patrón 4 y §Validation Architecture — slot de capacidad 1 medido contra cola ilimitada: 13,9 ms estables vs +806 ms/s de crecimiento |
| **EVI-05** | Huella SHA-256 en la ingesta, persistida con los metadatos | §Patrón 2 — `hashlib.file_digest` + escritura atómica; verificado que un byte alterado rompe la verificación |
| **EVI-06** | Imágenes en el sistema de archivos direccionadas por contenido, base sólo con metadatos y referencia | §Patrón 2 + D-03 (`evidencia/AAAA/MM/DD/<sha256>.jpg`); §Pitfall 3 (MAX_PATH) acota la raíz configurable |
| **VIA-05** | Viaje↔Remito muchos a muchos desde el diseño inicial | §Patrón 5 — tabla de asociación tipada SQLAlchemy 2.0; verificado con viaje de 3 remitos y remito en 2 viajes |
| **INT-04** | Toda comunicación con sistemas externos es de solo lectura | §Patrón 7 — triple barrera (credencial de solo lectura, cliente sin verbos de escritura, guardia `before_cursor_execute`); las 9 sentencias de prueba se comportaron como se esperaba |
| **INT-05** | Persistencia del payload crudo de cada consulta externa | §Patrón 7 — el payload crudo **es** el cassette; un solo mecanismo, dos propósitos |
| **DIS-05** | Migraciones versionadas que preservan los datos existentes | §Patrón 6 — Alembic `batch_alter_table` con motor dedicado `foreign_keys=OFF`; verificado preservando 9 filas y `foreign_key_check` limpio |
| **DIS-06** | Funciona en rutas con espacios y caracteres acentuados | §Patrón 6 + §Pitfalls 3, 5 y 8 — `URL.create`, MAX_PATH, normalización Unicode y consola cp1252, todo verificado en `…\PROYECTO PAGOS\IA visual ñandú áéí\` |
</phase_requirements>

---

## Summary

Esta fase no construye una funcionalidad: construye las **invariantes** sobre las que se van a apoyar once fases más. Por eso casi todo lo que sigue está verificado ejecutándolo, no leído. La investigación se hizo sobre Python 3.12.12 en Windows 11 —la plataforma de destino y de compuerta según D-54— y produjo **ocho hallazgos que contradicen el idioma POSIX habitual** y que, si no se atienden, se descubren tarde y caros.

El más importante, y el que más impacto tiene sobre decisiones marcadas como no retrofiteables: **en Python 3.12 sobre Windows, `time.monotonic()` tiene una resolución de 15,625 ms**, porque se implementa con `GetTickCount64()`. Medir una ventana de sincronía de ±150 ms con un reloj que avanza de a 15 ms es medir con un error de cuantización del 10 % antes de empezar. El reloj monotónico del proceso tiene que ser `time.perf_counter_ns()` (`QueryPerformanceCounter`, resolución de 100 ns, verificada). Esto cambia el tipo `InstanteMonotono` que `ARCHITECTURE.md` da por sentado, y cambiarlo después implica reinterpretar toda la evidencia ya persistida. Los otros siete: `os.fsync` sobre un directorio **no existe** en Windows (lanza `PermissionError`), `os.rename` sobre un archivo existente **falla** (hay que usar `os.replace`), `batch_alter_table` de Alembic **choca** con `PRAGMA foreign_keys=ON`, `DateTime(timezone=True)` en SQLite **pierde la zona horaria** al leer, el límite MAX_PATH de 260 caracteres está **activo** en esta máquina y acota la raíz de evidencia configurable a ~170 caracteres, la consola de Windows es **cp1252** y una línea de comandos íntegramente en español (D-50) **revienta con `UnicodeEncodeError`** sin modo UTF-8, y el paquete `alembic` está hoy en **1.18.5**, no en el 1.16.x que declara `CLAUDE.md`.

Del lado bueno: el contrato de frescura del frame no requiere ninguna biblioteca. Un slot de capacidad 1 con descarte del más viejo, ~40 líneas, mantuvo la antigüedad mediana del frame en 13,9 ms durante 20 segundos con un consumidor a 5 Hz contra una fuente a 25 fps, mientras que la contraprueba con una cola ilimitada creció a razón de **806 ms de latencia por cada segundo de operación** hasta 16 segundos de atraso. Eso es el Criterio de Éxito 5 demostrado en 20 segundos en vez de 10 minutos, lo cual resuelve la tensión con D-53 (las compuertas lentas se terminan salteando). Y la prueba de arquitectura del Criterio 1 tiene una respuesta clara y verificada: `import-linter` con contrato `forbidden` detecta las cuatro vías por las que alguien podría colar `cv2` en el dominio —import diferido dentro de una función, import bajo `TYPE_CHECKING`, import indirecto a través de un módulo propio, y violación de capas— y devuelve exit 1.

**Primary recommendation:** Fijar el reloj del proceso en `time.perf_counter_ns()` con un ancla `(perf_counter_ns, UTC)` reestablecible tras suspensión, y construir el resto de la fase sobre las cinco piezas verificadas de este documento —escritura atómica `os.replace` + `hashlib.file_digest`, orden archivo-primero con una única transacción SQLite en WAL/FULL, `import-linter` + entorno aislado con `uv`, slot de capacidad 1 con métricas, y `URL.create` para la ruta con acentos— antes de escribir cualquier otra cosa.

---

## Architectural Responsibility Map

Esta fase es una aplicación de escritorio de un solo proceso, sin servidor y sin interfaz gráfica. Los "tiers" son capas de la arquitectura hexagonal, no niveles de red.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Reglas de integridad, estados y ciclo de vida de la evidencia | `dominio/` | — | No depende de nada externo; es lo único que no se puede reescribir barato |
| Definición del contrato de frescura (qué es "antigüedad", qué es "descartado") | `dominio/` (tipos) + `aplicacion/puertos/salida` (protocolo) | `infraestructura/video` (implementación) | El puerto lo dicta el negocio; PyAV y OpenCV son dos implementaciones del mismo contrato |
| Cálculo y verificación de la huella SHA-256 | `dominio/evidencia` (valor `HuellaDeIntegridad`) | `infraestructura/persistencia/cas` (streaming sobre el archivo) | El dominio razona sobre la huella; sólo la infraestructura toca bytes |
| Escritura atómica en el sistema de archivos | `infraestructura/persistencia/cas` | — | `os.replace`, `fsync` y MAX_PATH son detalles de plataforma; jamás cruzan hacia arriba |
| Transacción única estado + evidencia + outbox | `aplicacion/unidad_de_trabajo` | `infraestructura/persistencia/sqlite` | La aplicación decide el límite transaccional; SQLAlchemy lo ejecuta |
| Esquema, migraciones y copia previa | `infraestructura/persistencia/sqlite` | — | Alembic y sus rarezas de SQLite no deben filtrarse al modelo |
| Reloj del proceso y desvío por cámara | `aplicacion/puertos/salida/reloj` (puerto) | `infraestructura/runtime/reloj` (`perf_counter_ns`) | Reloj inyectable = pruebas deterministas; es la razón por la que `Reloj` es un puerto y no un `import time` |
| Barrera de solo lectura hacia sistemas externos | `infraestructura/externos` (cliente y guardia) | `tests/arquitectura` (tercera barrera) | La restricción es de infraestructura, pero se convierte en prueba de compilación |
| Cassettes y payload crudo | `infraestructura/externos` | `infraestructura/persistencia/sqlite` (tabla de payload) | El payload crudo persistido **es** el cassette; mismo dato, dos usos |
| Línea de comandos (entrada) | `composicion/` + `cli/` | `aplicacion/puertos/entrada` | La CLI es un adaptador de entrada más; habla comandos, nunca toca el dominio |
| Bitácora técnica rotativa (NUC-06) | `infraestructura/runtime/bitacora` | — | Borrable sin consecuencias (D-11) |
| Bitácora de auditoría encadenada | `dominio/auditoria` (cadena) + `infraestructura/persistencia` (tabla) | — | La regla de encadenamiento es de negocio; la tabla es un detalle |

**Riesgo de asignación que el planner debe vigilar:** la tentación de poner el cálculo del SHA-256 en el dominio "porque es una regla de integridad". No lo es: es I/O sobre bytes. El dominio recibe una `HuellaDeIntegridad` ya calculada y decide si la evidencia está comprometida.

---

## Project Constraints (from CLAUDE.md)

| Directiva | Consecuencia para esta fase |
|-----------|------------------------------|
| **Acceso a APIs y bases externas: SOLO LECTURA. Sólo GET y SELECT. Sin excepciones.** | La barrera de D-47 es obligatoria y debe ser una prueba que falla la construcción. Ninguna tarea del plan puede emitir POST/PUT/PATCH/DELETE ni INSERT/UPDATE/DELETE/CREATE/DROP/ALTER contra PALJET, la balanza o Geomov. La aplicación **sí** escribe libremente en su SQLite local y en su raíz de evidencia. |
| **Windows es la plataforma primaria de desarrollo y validación** | Todo el código de sistema de archivos y de reloj se valida en Windows. Los ocho hallazgos de §Common Pitfalls son consecuencia directa de esto. |
| **Debe funcionar con GPU y sin ella** | No aplica a esta fase (no hay inferencia), pero la prueba de arquitectura debe prohibir `onnxruntime` en `dominio/` desde ahora. |
| **Instalador, mensajes de error comprensibles y configuración sin editar archivos son obligatorios** | Los mensajes de la CLI ya deben cumplir UI-05 (español claro, indicando qué hacer). La configuración de dos capas de D-30 es la que después alimenta la interfaz de la Fase 7. |
| **Prohibido Ultralytics (AGPL-3.0), YOLOv9, YOLOv7, YOLO-NAS** | No hay modelos en esta fase, pero la compuerta de licencias de D-55 se construye acá y es la que los va a atrapar cuando lleguen. |
| **`opencv-python-headless`, nunca `opencv-python`** | Verificado: `opencv-python-headless==5.0.0.93` instala y funciona en 3.12 (rueda `cp37-abi3-win_amd64`). |
| **Un solo paquete de `onnxruntime` por entorno** | Los grupos de dependencias de `uv` (§Patrón 8) deben mantener esa exclusión mutua desde el `pyproject.toml` inicial. |
| **GSD Workflow Enforcement** | Esta fase se ejecuta con `/gsd-execute-phase`. No hay ediciones directas fuera del flujo. |

---

## Standard Stack

Todas las versiones de esta sección se consultaron **hoy contra el registro PyPI** y, salvo donde se indica, se **instalaron y ejecutaron** en un entorno Python 3.12.12 real en Windows.

### Core

| Library | Version | License | Purpose | Why Standard |
|---------|---------|---------|---------|--------------|
| **Python** | 3.12.12 | PSF | Runtime | `[VERIFICADO: uv python install 3.12]` — instalado y usado para todas las sondas de este documento. **Ver §Pitfall 1**: la elección de 3.12 sobre 3.13 tiene una consecuencia concreta sobre el reloj que hay que absorber en el diseño |
| **SQLAlchemy** | 2.0.51 | MIT | ORM y capa de datos | `[VERIFICADO: PyPI + instalación, rueda cp312-cp312-win_amd64, publicada 2026-06-15]`. El estilo tipado `Mapped[]`/`mapped_column` es el idioma correcto de la 2.0 y se ejercitó con la relación N:M real |
| **Alembic** | **1.18.5** | MIT | Migraciones de esquema | `[VERIFICADO: PyPI, 2026-06-25]`. ⚠️ **`CLAUDE.md` dice 1.16.x — está desactualizado.** `batch_alter_table` verificado preservando datos |
| **Pydantic** | 2.13.4 | MIT | DTOs, contratos, config validada | `[VERIFICADO: PyPI + instalación]`. Rueda pura (`py3-none-any`); el binario es `pydantic-core` 2.46.4 |
| **pydantic-settings** | **2.14.2** | MIT | Configuración validada (capa 1 de D-30) | `[VERIFICADO: PyPI, 2026-06-19]`. `CLAUDE.md` dice "2.x" — la actual es 2.14.2 |
| **SQLite** | **3.50.4** (embebido en el `sqlite3` de Python 3.12.12) | Dominio público | Persistencia local | `[VERIFICADO: sqlite3.sqlite_version]`. WAL + `synchronous=FULL` + `foreign_keys` + `busy_timeout` verificados en ruta con espacios y acentos |
| **opencv-python-headless** | 5.0.0.93 | Apache-2.0 | Fuente de archivo de video (CAP-03) | `[VERIFICADO: instalado, `cv2.__version__` = 5.0.0, backend `FFMPEG`, `CAP_PROP_POS_MSEC` funcional, ruedas `cp37-abi3-win_amd64`]` |
| **NumPy** | 2.5.1 | BSD-3-Clause | Buffers de frame | `[VERIFICADO: PyPI + instalación, `requires_python >=3.12`]` |

### Supporting

| Library | Version | License | Purpose | When to Use |
|---------|---------|---------|---------|-------------|
| **import-linter** | **2.13** | BSD-2-Clause | Prueba de arquitectura (NUC-01, D-47, D-52) | `[VERIFICADO: instalado y ejercitado contra un paquete de prueba con violaciones deliberadas]`. Motor `grimp` 3.15. Compuerta bloqueante de D-53 |
| **Typer** | **0.27.0** | MIT | Línea de comandos (D-49 a D-51) | `[VERIFICADO: instalado, CLI en español ejecutada]`. Arrastra `click` 8.4.2 (BSD-3), `rich` 15.0.0 (MIT), `shellingham` (ISC). Ver §Pitfall 8 y §Alternativas |
| **argon2-cffi** | **25.1.0** | MIT | Hash de credenciales (D-22) | `[VERIFICADO: instalado; defaults m=65536 KiB, t=3, p=4, Type.ID; hash en 201 ms en esta máquina; formato PHC; `check_needs_rehash` disponible]` |
| **structlog** | **26.1.0** | MIT OR Apache-2.0 | Bitácora técnica estructurada (NUC-06) | `[VERIFICADO: PyPI + instalación]`. Se apoya en `logging` de la stdlib, así que la **rotación** la da `logging.handlers.RotatingFileHandler` sin dependencia extra |
| **platformdirs** | **4.11.0** | MIT | Ubicación por defecto de la config de arranque (D-30) | `[VERIFICADO: PyPI + instalación]`. Evita hardcodear `%APPDATA%` y resuelve bien en Linux/macOS cuando lleguen |
| **pytest** | **9.1.1** | MIT | Pruebas | `[VERIFICADO: PyPI + instalación]`. ⚠️ Es una major nueva (2026-06-19); ver §Assumptions Log A3 |
| **Ruff** | 0.16.0 | MIT | Lint + format | `[VERIFICADO: PyPI, 2026-07-23]` |
| **pip-licenses** | **5.5.5** | MIT | Inventario de licencias (D-55) | `[VERIFICADO: ejecutado sobre el entorno completo de la fase; las 35 dependencias transitivas resultaron permisivas; `--fail-on` funcional]` |
| **vcrpy** | **8.3.0** | MIT | Cassettes HTTP (D-41, D-42) | `[VERIFICADO: PyPI, 2026-07-04]`. 8.x reescribió el soporte httpx sobre httpcore y soltó urllib3 < 2 `[CITADO: vcrpy.readthedocs.io/en/latest/changelog.html]` |
| **pytest-recording** | 0.13.4 | MIT | Integración de vcrpy con pytest | `[VERIFICADO: PyPI, 2025-05-08]`. Es la integración que la propia documentación de VCR.py recomienda por sobre `pytest-vcr`, que está sin mantener `[CITADO: vcrpy.readthedocs.io]`. ⚠️ Sin publicar desde mayo 2025 — ver A4 |
| **uv** | **0.11.18** | MIT / Apache-2.0 | Entorno, lockfile y **entorno aislado del dominio** | `[VERIFICADO: instalado en esta máquina; `uv run --isolated --no-project` produce un entorno con cero paquetes de terceros]` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **`import-linter`** | Prueba propia con un `MetaPathFinder` que aborte al importar `cv2` | El finder sólo atrapa lo que se ejecuta; un import dentro de un `if` que la prueba no recorre pasa. `import-linter` analiza el grafo estático completo, atrapa los imports bajo `TYPE_CHECKING` y no depende de la cobertura. **Verificado que el finder no es equivalente.** Usar `import-linter` como compuerta y el entorno aislado como confirmación de runtime, no uno u otro |
| `import-linter` | `grimp` directo o `ast` propio | `import-linter` **es** la capa declarativa sobre `grimp`. Escribir el análisis a mano cuesta días y no aporta nada |
| **Typer 0.27** | **`click` 8.4.2 solo** | Ahorra `rich`, `shellingham`, `markdown-it-py`, `pygments`, `mdurl` (~6 paquetes, y `rich`+`pygments` pesan en el instalador de la Fase 11). A cambio se pierde la ayuda en paneles y hay que escribir el binding de tipos a mano. **Recomendación: Typer**, porque D-49 declara la CLI producto vendido y D-51 exige salida legible por personas — es exactamente lo que `rich` da gratis. Si la Fase 11 mide que `rich` pesa demasiado, migrar a `click` es mecánico (Typer *es* click por debajo) |
| Typer | `argparse` (stdlib) | Cero dependencias y cero peso. A cambio: subcomandos anidados verbosos, sin ayuda formateada, sin conversión de tipos. Para una herramienta con ~8 subcomandos que viaja en el producto, es falsa economía |
| **`structlog`** | `logging` de la stdlib con un `Formatter` JSON propio | Cero dependencias. `structlog` aporta contexto acumulado por hilo (`bind`), que es exactamente lo que hace legible una bitácora de N fuentes de video concurrentes en la Fase 2. Es una dependencia de 0 transitivas |
| `structlog` | `python-json-logger` 4.1.0 (BSD-2) | Sólo formatea JSON; no da contexto ni procesadores. `structlog` lo cubre y hace más |
| **`vcrpy` + `pytest-recording`** | Cassettes propios en JSON escritos a mano | Para HTTP, vcrpy da grabación, reproducción, filtrado de cabeceras sensibles y bloqueo de red en un paquete MIT maduro (2013). **Pero** ver §Don't Hand-Roll: para el camino SQL de D-44, vcrpy **no sirve** y ahí sí hay que escribir el cassette, reutilizando la tabla de payload crudo de INT-05 |
| `vcrpy` | `respx` 0.23.1 (BSD-3) | `respx` es para *simular* httpx, no para grabar tráfico real. D-41 exige un GET real grabado. No cubre el requisito |
| **`argon2-cffi`** | `hashlib.scrypt` (stdlib) | Cero dependencias, pero D-22 dice Argon2id explícitamente y es la recomendación vigente de OWASP `[CITADO: cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html]` |
| **`pip-licenses`** | `uv export` + verificación propia contra los metadatos | `pip-licenses` ya normaliza clasificadores y expresiones SPDX y trae `--fail-on` / `--allow-only`. Ver §Pitfall 10 por su limitación real |

**Installation:**

```bash
# Entorno del producto (Fase 1: sin GUI, sin inferencia)
uv sync

# Entorno de la prueba de aislamiento del dominio (D-52): SIN opencv, SIN onnxruntime, SIN PySide6
uv sync --only-group dominio --no-default-groups --exact
```

`[CITADO: docs.astral.sh/uv/concepts/projects/dependencies/]` — `--only-group`, `--no-default-groups` y `--exact` son las tres banderas que producen un entorno que contiene *únicamente* el grupo pedido.

---

## Package Legitimacy Audit

Se ejecutó `gsd-tools query package-legitimacy check --ecosystem pypi …` sobre los 15 paquetes propuestos, y por separado se consultó la **fecha de primera publicación** de cada uno en PyPI, porque el veredicto automático usa la fecha del *último release* y por eso marca `too-new` a paquetes de 20 años que simplemente publicaron hace poco.

| Package | Registry | Antigüedad (1.ª publicación) | Releases | Repo | Veredicto seam | Disposición |
|---------|----------|------------------------------|----------|------|----------------|-------------|
| `sqlalchemy` | PyPI | 2006-02-14 (20 a) | 325 | sqlalchemy.org | SUS (`too-new`, `unknown-downloads`) | **Aprobado** — falso positivo |
| `alembic` | PyPI | 2011-11-30 (14 a) | 144 | alembic.sqlalchemy.org | SUS (ídem) | **Aprobado** — falso positivo |
| `pydantic` | PyPI | 2017-05-03 (9 a) | 203 | github.com/pydantic/pydantic | SUS (ídem) | **Aprobado** — falso positivo |
| `pydantic-settings` | PyPI | 2019-08-19 (6 a) | 44 | github.com/pydantic/pydantic-settings | SUS (ídem) | **Aprobado** — falso positivo |
| `import-linter` | PyPI | 2019-01-27 (7 a) | 49 | github.com/seddonym/import-linter | SUS (ídem) | **Aprobado** — falso positivo |
| `typer` | PyPI | 2019-12-20 (6 a) | 88 | github.com/fastapi/typer | SUS (ídem) | **Aprobado** — falso positivo |
| `vcrpy` | PyPI | 2013-02-22 (13 a) | 80 | github.com/kevin1024/vcrpy | SUS (ídem) | **Aprobado** — falso positivo |
| `pytest-recording` | PyPI | 2019-07-16 (7 a) | 26 | github.com/kiwicom/pytest-recording | SUS (ídem) | **Aprobado con reserva** — sin releases desde 2025-05-08; ver A4 |
| `argon2-cffi` | PyPI | 2015-12-10 (10 a) | 18 | github.com/hynek/argon2-cffi | SUS (ídem) | **Aprobado** — falso positivo |
| `structlog` | PyPI | 2013-09-12 (12 a) | 43 | github.com/hynek/structlog | SUS (ídem) | **Aprobado** — falso positivo |
| `ruff` | PyPI | 2022-08-27 (3 a) | 416 | docs.astral.sh/ruff | SUS (ídem) | **Aprobado** — falso positivo |
| `pytest` | PyPI | 2010-11-25 (15 a) | 192 | github.com/pytest-dev/pytest | SUS (`unknown-downloads`) | **Aprobado** — falso positivo |
| `opencv-python-headless` | PyPI | 2018-09-09 (7 a) | 55 | github.com/opencv/opencv-python | SUS (ídem) | **Aprobado** — falso positivo |
| `pip-licenses` | PyPI | 2018-02-05 (8 a) | 73 | github.com/raimon49/pip-licenses | SUS (`no-repository`) | **Aprobado** — el repo existe, está en `project_urls.homepage`, campo que el seam no lee |
| `platformdirs` | PyPI | 2021-05-13 (5 a) | 65 | github.com/tox-dev/platformdirs | SUS (ídem) | **Aprobado** — falso positivo |

**Paquetes eliminados por veredicto [SLOP]:** ninguno.
**Paquetes marcados como sospechosos [SUS] que requieran `checkpoint:human-verify`:** ninguno.

> **Lectura honesta del resultado.** La herramienta devolvió `SUS` para los 15 por dos motivos sistemáticos y no por señales reales: PyPI no expone descargas semanales en su API JSON (`unknown-downloads` sale siempre) y `too-new` se calcula sobre la fecha del último release, no sobre la del primero. La verificación que sostiene la aprobación es la **combinación** de: (a) primera publicación y número de releases consultados a PyPI, (b) repositorio público identificado, (c) instalación real y ejecución de los 15 en un entorno Python 3.12 de esta máquina, y (d) inventario de licencias ejecutado sobre el cierre transitivo completo.

**Inventario de licencias del cierre transitivo completo** `[VERIFICADO: pip-licenses 5.5.5 ejecutado sobre el entorno de la fase]` — 35 paquetes, cero contagiosas:

```
MIT (18) · BSD-3-Clause (7) · MIT License (5) · BSD-2-Clause (2) · Apache-2.0 OR BSD-2-Clause (1)
Apache Software License (1) · MIT OR Apache-2.0 (1) · MIT-0 (1) · ISC (1) · PSF-2.0 (1)
MIT AND PSF-2.0 (1) · BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 (1)
```

Cero GPL, cero AGPL, cero `UNKNOWN` en el campo de licencia. La compuerta de D-55 es viable desde el primer commit.

---

## Architecture Patterns

### System Architecture Diagram

Flujo de la orden de captura sobre un archivo de video, de la entrada al dato persistido.

```
  [ CLI en español ]                      [ CLI en español ]
  porteria capturar --fuente <archivo>    porteria verificar-huellas [--json]
          │                                        │
          ▼                                        ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │ composicion/arranque.py   (único módulo que conoce a todos)      │
  │  · carga config de arranque (2 capas, D-30)                      │
  │  · ¿raíz de evidencia disponible?  ──no──► MODO DEGRADADO (D-07) │
  │  · ¿versión de esquema compatible? ──no──► SE NIEGA A ABRIR      │
  │  · barrido de huérfanos → cuarentena (D-13, en 2.º plano)        │
  └───────────────────────────┬──────────────────────────────────────┘
                              ▼
     ┌──────────── aplicacion/casos_de_uso/ejecutar_captura ─────────────┐
     │                                                                    │
     │  T ← Reloj.instante()            [perf_counter_ns — UN solo T]     │
     │        │                                                           │
     │        ▼                                                           │
     │  FuenteDeVideo.tomar_mas_reciente()      ◄── puerto de salida      │
     │        │  devuelve FrameSellado(datos, instante_ns, secuencia)     │
     │        │  desvío = (T − instante_ns)                               │
     │        ▼                                                           │
     │  codificar JPEG (calidad por cámara, D-01)  ─► bytes               │
     │  generar miniatura (~15 KB, D-04)           ─► bytes               │
     │        │                                                           │
     │        ▼                                                           │
     │  ╔══ PASO 1: SISTEMA DE ARCHIVOS (siempre primero, D-12) ═══════╗  │
     │  ║ sha256 en streaming ─► ruta AAAA/MM/DD/<sha>.jpg             ║  │
     │  ║ escribir .tmp → fh.flush() → os.fsync(fd) → os.replace()     ║  │
     │  ║ (fsync de directorio: NO EXISTE en Windows — omitir)         ║  │
     │  ╚══════════════════════════════════════════════════════════════╝  │
     │        │  éxito                            │  fallo                │
     │        ▼                                   ▼                       │
     │  ╔══ PASO 2: UNA TRANSACCIÓN SQLite ════╗  borrar .tmp, propagar   │
     │  ║ Captura + ItemDeEvidencia + Manifiesto║  (nada quedó a medias)  │
     │  ║ + BitácoraEncadenada + Outbox         ║                         │
     │  ║ WAL · synchronous=FULL · commit único ║                         │
     │  ╚═══════════════════════════════════════╝                         │
     │        │  fallo ⇒ archivo huérfano ⇒ CUARENTENA al próximo arranque│
     └────────┼───────────────────────────────────────────────────────────┘
              ▼
       DespachadorDeOutbox ──► CanalDeEventos (en memoria; la UI llega en F2)

  ── Camino de descubrimiento externo (solo lectura, INT-04) ─────────────
   porteria descubrir-contratos --sistema paljet|balanza
          │
          ▼
   ClienteSoloLectura              ConexionSoloLectura
   (sólo expone get/head/options)  (guardia before_cursor_execute)
          │        ▲                        │        ▲
          │        └── barrera 1            │        └── barrera 2
          ▼                                 ▼
   [ PALJET HTTP ]                   [ PALJET SQL — D-44 ]     [ Balanza ]
          │                                 │                        │
          └────────────┬────────────────────┴────────────────────────┘
                       ▼
            anonimizar EN EL ACTO DE GRABAR (D-42)
                       ▼
        tabla payload_crudo  ═══ MISMO DATO ═══►  cassette exportado a tests/
        (INT-05, comprimido)                       (D-41, versionado en git)
                       │
                       ▼
              barrera 3: tests/arquitectura/ falla la construcción
```

### Recommended Project Structure

Derivada de `ARCHITECTURE.md` §Recommended Project Structure, recortada a lo que esta fase realmente crea, y con los huecos vacíos que D-32 y `ARCHITECTURE.md` exigen dejar como recordatorio.

```
pyproject.toml                        # uv, ruff, pytest, import-linter, alembic
uv.lock
src/porteria/
├── dominio/                          # CERO dependencias externas — compuerta de CI
│   ├── comun/
│   │   ├── identificadores.py        # CapturaId, CamaraId, ViajeId, RemitoId (NewType)
│   │   ├── tiempo.py                 # InstanteMonotono, InstanteUtc, Desfasaje
│   │   └── resultado.py              # Resultado[T] = Ok | NoDisponible | Degradado
│   ├── evidencia/                    # CapturaDeControl, ItemDeEvidencia,
│   │   │                             #   HuellaDeIntegridad, Manifiesto, Lapida
│   │   └── estados.py                # INTEGRA | COMPROMETIDA | PURGADA
│   ├── viaje/                        # Viaje, Remito, Articulo, PesoTeorico (nulable)
│   ├── auditoria/                    # RegistroEncadenado + regla de encadenamiento
│   ├── identidad/                    # Usuario, Rol (4 fijos), politica de contraseña
│   └── eventos.py                    # EventoDeDominio
│
├── aplicacion/
│   ├── puertos/
│   │   ├── entrada/                  # ApiDePorteria, Comando*
│   │   └── salida/                   # FuenteDeVideo, AlmacenDeEvidencia, Reloj,
│   │                                 #   ProveedorDeDatosMaestros, ProveedorDePesaje,
│   │                                 #   ProveedorDeTelemetria, RepositorioDe*
│   ├── casos_de_uso/
│   ├── servicios/
│   ├── unidad_de_trabajo.py
│   └── dto/                          # Pydantic, versionados desde el primer mensaje
│
├── infraestructura/
│   ├── video/
│   │   ├── archivo.py                # cv2.VideoCapture, dos modos (D-16)
│   │   ├── falsa.py                  # doble de prueba (NUC-04) + modo demo (D-48)
│   │   ├── slot_ultimo_valor.py      # capacidad 1, descarte del más viejo (CAP-04)
│   │   └── metricas.py               # en memoria, consultables por CLI (D-17)
│   ├── persistencia/
│   │   ├── sqlite/                   # engine, pragmas, modelos, repositorios, outbox
│   │   ├── migraciones/              # Alembic: env.py, versions/
│   │   └── evidencia_fs.py           # escritura atómica + cuarentena de huérfanos
│   ├── externos/
│   │   ├── comun/                    # ClienteSoloLectura, ConexionSoloLectura,
│   │   │                             #   grabador de cassette + anonimizador
│   │   ├── paljet/                   # http.py · sql.py · falso.py · cassettes/
│   │   ├── balanza/                  # http.py · falso.py · cassettes/
│   │   └── geomov/                   # manual.py (referencia, D-45)
│   ├── transporte/
│   │   ├── contrato.py               # SobreDeEvento con version_esquema
│   │   ├── en_memoria/
│   │   └── ipc/                      # VACÍO + README de una línea (recordatorio)
│   ├── runtime/
│   │   ├── reloj.py                  # perf_counter_ns + ancla UTC (§Patrón 7)
│   │   └── bitacora.py               # structlog + RotatingFileHandler (NUC-06)
│   ├── seguridad/                    # argon2-cffi
│   └── configuracion/                # pydantic-settings, dos capas (D-30)
│
├── cli/                              # Typer. Órdenes y opciones en español (D-50)
└── composicion/arranque.py           # composition root

tests/
├── dominio/                          # sin I/O, milisegundos
├── contrato/                         # MISMA suite contra falso y contra cassette
├── arquitectura/
│   ├── test_dominio_aislado.py       # entorno separado (D-52)
│   └── test_adaptadores_son_solo_lectura.py
├── migracion/                        # sembrar → migrar → comparar (D-33)
├── integracion/
├── lentas/                           # marcadas; tanda programada, no compuerta (D-53)
└── recursos/videos/                  # recortes cortos versionados (D-59)
```

**Decisión sobre `src/` layout:** obligatoria acá. Con layout plano, `import porteria` toma el código del directorio de trabajo y la prueba de entorno aislado de D-52 pierde sentido, porque el paquete se importa aunque no esté instalado. Con `src/`, el dominio se importa *sólo* si el paquete está realmente instalado en el entorno, que es exactamente lo que la prueba tiene que demostrar. `[VERIFICADO: la sonda de aislamiento usó src/ + PYTHONPATH explícito]`

---

### Pattern 1: Prueba de arquitectura en dos compuertas (Criterio de Éxito 1)

**What:** Una compuerta estática que analiza el grafo de imports completo, más una compuerta de runtime que importa el dominio en un entorno donde las dependencias prohibidas **no están instaladas**.
**When to use:** En cada fusión. Es la primera compuerta de D-53.
**Why two:** D-52 pide explícitamente que la prueba no sea sorteable "con un import diferido dentro de una función". Se probaron las cuatro vías de evasión y **`import-linter` las atrapa todas**; el entorno aislado sólo atrapa lo que se ejecuta. Pero el entorno aislado responde una pregunta distinta y que la compuerta estática no responde: *¿el dominio realmente arranca sin esos paquetes?* Las dos juntas cubren el criterio literal.

```toml
# pyproject.toml
[tool.importlinter]
root_package = "porteria"
include_external_packages = true        # IMPRESCINDIBLE para prohibir paquetes de terceros
# NO activar exclude_type_checking_imports: dejaría pasar los imports bajo TYPE_CHECKING

[[tool.importlinter.contracts]]
id = "dominio_limpio"
name = "El dominio no toca infraestructura pesada"
type = "forbidden"
source_modules = ["porteria.dominio"]
forbidden_modules = [
    "cv2", "onnxruntime", "PySide6", "PySide6-Essentials", "av",
    "numpy", "sqlalchemy", "alembic", "typer", "click", "structlog",
    "argon2", "pydantic",
]
allow_indirect_imports = false
as_packages = true

[[tool.importlinter.contracts]]
id = "capas"
name = "Capas: cli/ui -> infraestructura -> aplicacion -> dominio"
type = "layers"
layers = [
    "porteria.cli",
    "porteria.infraestructura",
    "porteria.aplicacion",
    "porteria.dominio",
]
exhaustive = false

[[tool.importlinter.contracts]]
id = "sin_conexion_cruda"
name = "Los adaptadores externos no pueden abrir una conexion cruda"
type = "forbidden"
source_modules = ["porteria.infraestructura.externos"]
forbidden_modules = ["sqlite3", "requests", "urllib", "http.client", "socket"]
allow_indirect_imports = false
```

```bash
# CI en Windows (D-54). Devuelve 1 si algun contrato se rompe.
uv run lint-imports --no-cache
```

`[VERIFICADO: import-linter 2.13 + grimp 3.15 ejecutados contra un paquete de prueba]` — se introdujeron cuatro violaciones y las cuatro fueron detectadas con exit code 1:

| Vía de evasión | Módulo sembrado | Detectada |
|----------------|-----------------|-----------|
| Import diferido dentro de una función | `def calcular(): import numpy` | ✅ `porteria.dominio.comun.sucio -> numpy (l.2)` |
| Import bajo `TYPE_CHECKING` | `if TYPE_CHECKING: import cv2` | ✅ `porteria.dominio.comun.sucio -> cv2 (l.3)` |
| Indirecto vía módulo propio | `dominio.sucio -> dominio.interno -> cv2` | ✅ `porteria.dominio.comun.interno -> cv2 (l.1)` |
| Violación de capas | `dominio -> infraestructura.video.archivo` | ✅ ambos contratos rotos, con la cadena completa |

Sin violaciones: `Contracts: 2 kept, 0 broken.` y exit code **0**.

La segunda compuerta, verificada:

```python
# tests/arquitectura/test_dominio_aislado.py  (se ejecuta como subproceso)
"""Importa TODO dominio/ y falla si alguna dependencia pesada quedo cargada."""
import importlib, pkgutil, sys
PROHIBIDOS = {"cv2", "onnxruntime", "PySide6", "numpy", "sqlalchemy", "alembic", "av"}
import porteria.dominio as d
for m in pkgutil.walk_packages(d.__path__, d.__name__ + "."):
    importlib.import_module(m.name)          # importa TODOS los submodulos, no solo el paquete
cargados = PROHIBIDOS & set(sys.modules)
sys.exit(1 if cargados else 0)
```

```bash
# Entorno realmente separado: cero paquetes de terceros disponibles.
uv run --python 3.12 --isolated --no-project python tests/arquitectura/test_dominio_aislado.py
# -> prohibidos cargados: ninguno | prohibidos instalables en este entorno: set() | exit=0
```

`[VERIFICADO: ejecutado; el entorno `--isolated --no-project` no tiene ninguno de los paquetes prohibidos, así que un import los rompería con `ModuleNotFoundError`]`

**Detalle práctico de CI en Windows:** `lint-imports` cachea el grafo en un directorio; en CI conviene `--no-cache` para que un cache viejo no oculte una violación nueva. El script de compuerta debe correr los dos pasos y propagar el peor exit code.

---

### Pattern 2: Escritura atómica con huella, en el idioma de Windows

**What:** SHA-256 en streaming, temporal en el **mismo directorio de destino**, `flush` + `fsync` del archivo, y `os.replace` al nombre final.
**When to use:** Toda escritura de evidencia. Nunca `open(destino, "wb")` directo.

```python
# infraestructura/persistencia/evidencia_fs.py
import os, hashlib, tempfile, datetime as dt
from pathlib import Path

CHUNK = 1 << 20

def guardar_atomico(contenido: bytes, raiz: Path, fecha_local: dt.date) -> tuple[str, str]:
    """Devuelve (sha256_hex, ruta_relativa_posix). Nunca deja un archivo a medias."""
    h = hashlib.sha256(contenido).hexdigest()
    destino_dir = raiz / f"{fecha_local:%Y/%m/%d}"       # D-03: carpeta por fecha LOCAL (D-37)
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / f"{h}.jpg"
    relativa = destino.relative_to(raiz).as_posix()      # D-06: SIEMPRE relativa, separador '/'

    if destino.exists():                                 # mismo contenido = mismo archivo
        return h, relativa

    # El temporal va en el MISMO directorio: os.replace solo es atomico dentro del mismo volumen.
    fd, tmpname = tempfile.mkstemp(dir=destino_dir, prefix=".tmp_", suffix=".part")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(contenido)
            fh.flush()
            os.fsync(fh.fileno())        # el ARCHIVO si se puede sincronizar en Windows
        if os.name != "nt":
            # El fsync del directorio padre es idioma POSIX y NO EXISTE en Windows:
            # os.open(dir) + os.fsync(fd) lanza PermissionError(13). VERIFICADO.
            dfd = os.open(destino_dir, os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
        os.replace(tmpname, destino)     # os.replace, NUNCA os.rename (ver abajo)
    except BaseException:
        try:
            os.unlink(tmpname)
        except OSError:
            pass
        raise
    return h, relativa


def verificar(raiz: Path, relativa: str, sha_esperado: str) -> bool:
    """EVI-05: recalcular reproduce el valor persistido; un byte alterado lo rompe."""
    with open(raiz / relativa, "rb") as fh:
        return hashlib.file_digest(fh, "sha256").hexdigest() == sha_esperado
```

`[VERIFICADO ejecutando en Windows 11 / Python 3.12.12 sobre `…\PROYECTO PAGOS\IA visual ñandú áéí\`]`:

| Comportamiento | Resultado medido |
|---|---|
| `os.replace(tmp, existente)` | **OK** — el destino queda con el contenido nuevo |
| `os.rename(tmp, existente)` | **`FileExistsError` (17)** — falla donde POSIX tendría éxito |
| `os.fsync(fd_de_archivo)` | **OK** |
| `os.fsync(fd_de_directorio)` | **`PermissionError` (13)** — el paso POSIX es imposible |
| `hashlib.file_digest(fh, "sha256")` vs streaming manual | **idénticos** — usar el de la stdlib (3.11+) |
| Verificación tras alterar 1 byte | **`False`** — la manipulación se detecta |
| Largo de `AAAA/MM/DD/<64hex>.jpg` | **79 caracteres** |

**Consecuencia honesta sobre `os.replace`:** en Windows se implementa con `MoveFileEx(MOVEFILE_REPLACE_EXISTING)`, que **no está garantizado como atómico en todos los casos** — bajo ciertas circunstancias puede caer a una copia no atómica `[CITADO: github.com/untitaker/python-atomicwrites]`. Es lo mejor disponible sin llamar a `NtSetInformationFile`, y el orden archivo-primero de D-12 lo cubre igual: si el rename queda a medias, lo que aparece es un archivo huérfano o un `.tmp` colgado, nunca una fila apuntando a nada. **No hace falta la dependencia `atomicwrites`** (sin mantener desde 2022): `os.replace` de la stdlib es lo que esa biblioteca terminó recomendando.

---

### Pattern 3: Orden archivo-primero con una única transacción (Criterio de Éxito 3)

**What:** No existe transacción distribuida entre el sistema de archivos y SQLite. Se elige **cuál de los dos huérfanos posibles se prefiere** y se ordena la escritura para que sólo ese pueda ocurrir.
**When to use:** Todo caso de uso que persista evidencia.

```python
# aplicacion/casos_de_uso/ejecutar_captura.py  (esqueleto)
def ejecutar(self, cmd: EjecutarCaptura) -> ResultadoDeCaptura:
    t_objetivo = self.reloj.instante()                       # perf_counter_ns, uno solo
    frame = self.fuente.tomar_mas_reciente()
    jpeg = self.codificador.codificar(frame, cmd.calidad)
    mini = self.codificador.miniatura(frame)

    # PASO 1 — sistema de archivos. Si falla, no se toco la base.
    sha, relativa = guardar_atomico(jpeg, self.raiz_evidencia, self.reloj.fecha_local())

    # PASO 2 — UNA transaccion: estado + evidencia + manifiesto + bitacora + outbox
    with self.uow:                                            # NUC-05
        captura = CapturaDeControl.nueva(t_objetivo, cmd.autor)
        captura.agregar_evidencia(relativa, HuellaDeIntegridad(sha), frame.instante_ns, mini)
        self.uow.capturas.guardar(captura)
        self.uow.manifiestos.guardar(captura.manifiesto())
        self.uow.auditoria.encadenar(captura.eventos())       # D-08, arranca en el registro 1
        self.uow.outbox.encolar(captura.eventos())
        self.uow.confirmar()                                  # commit unico
    return ResultadoDeCaptura(captura.id, sha, relativa)
```

Configuración obligatoria del motor `[VERIFICADO ejecutando]`:

```python
# infraestructura/persistencia/sqlite/motor.py
from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL
from pathlib import Path

def crear_motor(ruta_db: Path, *, para_migracion: bool = False):
    # URL.create maneja solo el path de Windows con espacios y acentos.
    # NO concatenar "sqlite:///" + str(path) a mano.
    url = URL.create("sqlite", database=str(ruta_db))
    motor = create_engine(url)

    @event.listens_for(motor, "connect")
    def _pragmas(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")       # D-14
        cur.execute("PRAGMA synchronous=FULL")       # D-14: sobrevive corte de energia
        cur.execute("PRAGMA busy_timeout=5000")
        # OJO: durante una migracion con batch_alter_table esto DEBE ir en OFF. Ver Patron 6.
        cur.execute("PRAGMA foreign_keys=" + ("OFF" if para_migracion else "ON"))
        cur.close()

    return motor
```

Lecturas medidas tras conectar: `journal_mode = wal`, `synchronous = 2` (FULL), `foreign_keys = 1`, `busy_timeout = 5000`, y los sidecar `porteria.sqlite3-wal` / `-shm` creados en la ruta con acentos.

`[CITADO: sqlite.org/pragma.html]` — con `synchronous=FULL` en modo WAL se hace un sync adicional del WAL después de cada commit, que es lo que asegura durabilidad frente a un corte de energía; con `NORMAL` se garantiza integridad pero no durabilidad del último commit. D-14 pide durabilidad, así que `FULL` es la lectura correcta de la decisión.

**Prueba del Criterio 3, verificada:**

```python
class FalloInyectado(Exception): pass

def test_transaccion_cortada_no_deja_filas_huerfanas(uow, raiz_evidencia, monkeypatch):
    def explotar(*a, **k):
        raise FalloInyectado("corte deliberado antes del commit")
    monkeypatch.setattr(UnidadDeTrabajo, "confirmar", explotar)

    with pytest.raises(FalloInyectado):
        caso_de_uso.ejecutar(comando)

    filas = {i.ruta_relativa for i in repositorio.todos()}
    archivos = {p.relative_to(raiz_evidencia).as_posix()
                for p in raiz_evidencia.rglob("*.jpg")}
    assert filas - archivos == set()      # INVARIANTE DURA: cero filas huerfanas
    assert archivos - filas               # huerfanos de archivo: esperados, van a cuarentena
```

`[VERIFICADO: ejecutado]` — con 1 commit exitoso y 2 fallos inyectados: **1 fila en base, 3 archivos en disco, 0 filas huérfanas, 2 archivos huérfanos.** Exactamente la invariante de D-12.

**Segunda variante necesaria (no cubierta por la anterior):** matar el proceso, no lanzar una excepción. `monkeypatch` demuestra que el *código* ordena bien; sólo un `subprocess` que se mata con `SIGKILL`/`TerminateProcess` en mitad del commit demuestra que **WAL** recupera bien. Ver §Validation Architecture.

---

### Pattern 4: Contrato de frescura — slot de capacidad 1 con descarte del más viejo (Criterio de Éxito 5)

**What:** El punto de encuentro entre el hilo que decodifica y el que consume es un **slot de un elemento que se sobrescribe**, con contador de descartes. Nunca una cola.
**When to use:** La ruta viva (monitoreo). La ruta de evidencia usa el buffer circular con timestamps de la Fase 3.

**Definición operativa de "antigüedad", que hay que fijar acá porque es lo que se persiste y se reporta:**

> `antigüedad_ms = (instante_de_entrega − instante_de_captura) / 1e6`
> donde `instante_de_captura` es el `perf_counter_ns()` tomado **inmediatamente después de que el decodificador devuelve el frame**, e `instante_de_entrega` es el `perf_counter_ns()` del momento en que el consumidor lo recibe. No es el PTS del contenedor, que mide tiempo de reproducción, no tiempo real transcurrido.

```python
# infraestructura/video/slot_ultimo_valor.py
import threading, dataclasses
from typing import Any

@dataclasses.dataclass(frozen=True)
class FrameSellado:
    datos: Any                    # numpy.ndarray — NUNCA cruza al dominio
    instante_captura_ns: int      # perf_counter_ns tras el decode
    secuencia: int

class SlotUltimoValor:
    """Capacidad 1, descarte del mas viejo. Contrato de frescura CAP-04.
    El mismo contrato lo implementa despues el adaptador PyAV sin cambios."""
    __slots__ = ("_lock", "_nuevo", "_item", "_descartados", "_publicados")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._nuevo = threading.Condition(self._lock)
        self._item: FrameSellado | None = None
        self._descartados = 0
        self._publicados = 0

    def publicar(self, f: FrameSellado) -> None:
        with self._nuevo:
            if self._item is not None:
                self._descartados += 1        # METRICA consultable (D-17)
            self._item = f
            self._publicados += 1
            self._nuevo.notify()

    def tomar(self, timeout: float | None = None) -> FrameSellado | None:
        with self._nuevo:
            if self._item is None:
                self._nuevo.wait(timeout)
            f, self._item = self._item, None
            return f

    @property
    def metricas(self) -> dict:
        with self._lock:
            return {"frames_descartados": self._descartados,
                    "frames_publicados": self._publicados,
                    "ocupado": self._item is not None}
```

**Por qué esto y no `queue.Queue(maxsize=1)` ni `collections.deque(maxlen=1)`:**

| Opción | Problema |
|--------|----------|
| `queue.Queue(maxsize=1)` | `put()` bloquea al productor cuando está lleno, que es exactamente lo que **no** hay que hacer: bloquear al decodificador llena el buffer de red aguas arriba. `put_nowait()` + `get_nowait()` para vaciar antes es una carrera con dos locks |
| `collections.deque(maxlen=1)` | Es thread-safe para `append`/`popleft` individuales, pero no ofrece una espera bloqueante para el consumidor ni un contador de descartes. Habría que envolverlo con un `Condition` — es decir, escribir el slot igual, pero con una estructura de más |
| **Slot con `Condition`** | El productor **nunca** bloquea, el consumidor puede esperar con timeout, y el descarte se cuenta en el mismo lugar donde ocurre |

**Medición real** `[VERIFICADO: 20 s de reproducción en tiempo real, video 320×240 a 25 fps, consumidor a 5 Hz]`:

| | **Slot de capacidad 1** | **Cola ilimitada (el antipatrón)** |
|---|---|---|
| Antigüedad mediana, 1.ª mitad | **25,8 ms** | 4 152,7 ms |
| Antigüedad mediana, 2.ª mitad | **13,9 ms** | 12 218,7 ms |
| Antigüedad máxima | 155,6 ms | 16 175,8 ms |
| Pendiente de crecimiento | ≈ 0 (baja) | **+806,6 ms por segundo** |
| Frames descartados | 403 de 503 (métrica) | 0 (se acumulan) |
| Backlog al final | 0 | 406 frames |

La antigüedad con el slot **no crece**: baja de 25,8 a 13,9 ms. Con la cola crece a razón de 0,8 s por cada segundo de operación. Esto es Pitfall 1 de `PITFALLS.md` reproducido en laboratorio y su mitigación demostrada.

**Fuente de archivo, dos modos (D-16)** `[VERIFICADO: backend FFMPEG, `CAP_PROP_POS_MSEC` y `CAP_PROP_FPS` funcionales, ruta con acentos OK]`:

```python
# infraestructura/video/archivo.py
pts_ms = cap.get(cv2.CAP_PROP_POS_MSEC)          # marca temporal del contenedor
if self.modo is Modo.TIEMPO_REAL:                # verifica frescura y latencia
    objetivo_ns = self._t0 + int(pts_ms * 1e6)
    espera = (objetivo_ns - time.perf_counter_ns()) / 1e9
    if espera > 0:
        time.sleep(espera)
# Modo.VELOCIDAD_MAXIMA: no espera. Pruebas deterministas en CI.
self._slot.publicar(FrameSellado(fr, time.perf_counter_ns(), self._leidos))
```

---

### Pattern 5: Esquema tipado — Viaje↔Remito N:M y peso teórico nulable

**What:** Tabla de asociación explícita con `Table` de Core y `relationship(secondary=…)` en estilo tipado 2.0. El estado del remito **no se persiste, se deriva** (D-31).

```python
# infraestructura/persistencia/sqlite/modelos.py
from __future__ import annotations
import datetime as dt, uuid
from typing import Optional
from sqlalchemy import (Table, Column, ForeignKey, String, Integer, Float,
                        LargeBinary, Index, MetaData, UniqueConstraint)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

CONVENCION = {                       # OBLIGATORIO: sin esto, batch_alter_table no puede
    "ix": "ix_%(column_0_label)s",   # soltar restricciones sin nombre en SQLite
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENCION)

def _uuid() -> str:
    return str(uuid.uuid4())

viaje_remito = Table(                                    # VIA-05
    "viaje_remito", Base.metadata,
    Column("viaje_id",  ForeignKey("viaje.id",  ondelete="RESTRICT"), primary_key=True),
    Column("remito_id", ForeignKey("remito.id", ondelete="RESTRICT"), primary_key=True),
    Index("ix_viaje_remito_remito_id", "remito_id"),     # el sentido inverso tambien se consulta
)

class Viaje(Base):
    __tablename__ = "viaje"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)   # D-29 opaco
    numero_legible: Mapped[str] = mapped_column(String(20), unique=True)           # D-29 '2026-001842'
    remitos: Mapped[list["Remito"]] = relationship(
        secondary=viaje_remito, back_populates="viajes", lazy="selectin")

class Remito(Base):
    __tablename__ = "remito"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    numero: Mapped[str] = mapped_column(String(40), unique=True)
    viajes: Mapped[list[Viaje]] = relationship(
        secondary=viaje_remito, back_populates="remitos", lazy="selectin")
    articulos: Mapped[list["Articulo"]] = relationship(back_populates="remito", lazy="selectin")

class Articulo(Base):
    __tablename__ = "articulo"
    id: Mapped[int] = mapped_column(primary_key=True)
    remito_id: Mapped[str] = mapped_column(ForeignKey("remito.id"), index=True)
    codigo: Mapped[str] = mapped_column(String(40), index=True)
    # D-31: NULL es un valor legitimo del negocio, no un dato faltante por error.
    peso_teorico_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    remito: Mapped[Remito] = relationship(back_populates="articulos")
```

`[VERIFICADO: ejecutado]` — un viaje con **3 remitos**, un remito compartido por **2 viajes**, y `SELECT count(*) FROM articulo WHERE peso_teorico_kg IS NULL` devolviendo 1. El reporte de AUD-05 sale de esa consulta, sin columna de estado que pueda contradecir a los datos.

**Columnas de trazabilidad de la evidencia (D-05, EVI-05, EVI-06):**

| Columna | Tipo | Por qué |
|---------|------|---------|
| `id` | `String(36)` PK | Identificador opaco (D-29) |
| `captura_id` | `String(36)` FK + índice | Agrupa las fotos del mismo disparo |
| `camara_id` | `String(40)` índice | Trazabilidad de origen |
| `ruta_relativa` | `String(255)` **unique** | D-06: relativa a la raíz, separador `/`, nunca absoluta |
| `sha256` | `String(64)` índice | EVI-05. Índice porque la verificación masiva consulta por hash |
| `bytes_totales` | `Integer` | Detecta truncamiento antes de leer todo el archivo |
| **`capturado_en_utc_iso`** | **`String(32)`** | **NO `DateTime(timezone=True)` — ver Pitfall 4.** ISO-8601 con offset, ordenable lexicográficamente |
| `desfasaje_local_min` | `Integer` | D-37: el offset local vigente, guardado aparte |
| `fecha_local` | `String(10)` índice | `AAAA-MM-DD` local; es la clave de agrupación de D-37/D-38 y la que ordena el directorio de D-03 |
| `instante_monotono_ns` | `Integer` (SQLite: entero de 64 bits) | `perf_counter_ns` crudo. Sólo comparable dentro de la misma corrida; ver Patrón 7 |
| `desvio_ms` | `Float` | EVI-02: desvío real contra el instante objetivo |
| `ventana_vigente_ms` | `Float` | **D-40**: la ventana que regía cuando se capturó, para que nadie la ensanche retroactivamente |
| `perfil_de_flujo` | `String(20)` | D-15: monitoreo o evidencia |
| `resolucion`, `codec_origen` | `String` | D-05 |
| `calidad_jpeg` | `Integer` | D-01, por cámara |
| `miniatura` | `LargeBinary` nullable | D-04, ~15 KB, en la base a propósito |
| `motor_id`, `version_modelo`, `sha256_modelo` | `String` nullable | D-05; nulos en esta fase, poblados desde la Fase 4 |
| `version_app`, `version_esquema` | `String` | D-35 |
| `autor_id` | `String(36)` FK nullable | D-19/D-21: nulo = "no identificado", y el hecho se marca |
| `estado_integridad` | `String(16)` | D-09: `INTEGRA` / `COMPROMETIDA` / `PURGADA` (lápida, D-10) |

**Índices necesarios:** `(fecha_local)`, `(captura_id)`, `(sha256)`, `(camara_id, fecha_local)` para la consulta de la Fase 9, y `(estado_integridad)` parcial si SQLite lo permite en la versión objetivo. `ruta_relativa` UNIQUE es la que garantiza que dos filas no puedan reclamar el mismo archivo.

---

### Pattern 6: Migraciones que preservan datos en SQLite (Criterio de Éxito 6)

**What:** SQLite no soporta `ALTER COLUMN`, `DROP COLUMN` con restricciones ni `ADD CONSTRAINT`. Alembic lo resuelve con `batch_alter_table`, que hace **reflejar → crear tabla nueva → `INSERT…SELECT` → `DROP` → `RENAME`** `[CITADO: alembic.sqlalchemy.org/en/latest/batch.html]`.

**El choque que nadie ve venir, reproducido en vivo:**

```
sqlalchemy.exc.IntegrityError: (sqlite3.IntegrityError) FOREIGN KEY constraint failed
[SQL: DROP TABLE remito]
```

`[VERIFICADO: ocurrió al ejecutar `batch_alter_table("remito")` con `PRAGMA foreign_keys=ON` y una fila en `viaje_remito` referenciando `remito`]`. El motor de la aplicación pone `foreign_keys=ON` —y debe hacerlo— pero eso **rompe toda migración batch**.

**La solución que funciona**, y por qué las obvias no:

```python
# infraestructura/persistencia/migraciones/env.py
# Motor DEDICADO a migraciones: identico al de la app salvo foreign_keys=OFF.
motor_migracion = crear_motor(ruta_db, para_migracion=True)
```

- ❌ Emitir `PRAGMA foreign_keys=OFF` dentro del `with conn.begin()`: **es un no-op**, SQLite ignora ese PRAGMA dentro de una transacción.
- ❌ Emitirlo antes con `exec_driver_sql`: SQLAlchemy 2.0 hace *autobegin*, así que la siguiente llamada a `conn.begin()` lanza `InvalidRequestError: This connection has already initialized a SQLAlchemy Transaction()`.
- ✅ **Un motor aparte cuyo listener `connect` ya trae `foreign_keys=OFF`.** Limpio, sin trucos de aislamiento, y deja explícito en el código que la migración corre bajo otras reglas.

```python
# migraciones/versions/xxxx_agrega_creado_en.py
def upgrade() -> None:
    op.add_column("remito", sa.Column("creado_en_utc", sa.String(32), nullable=True))
    with op.batch_alter_table("remito", naming_convention=CONVENCION) as b:
        b.alter_column("numero", existing_type=sa.Text(), nullable=False)
        b.create_unique_constraint("uq_remito_numero", ["numero"])
```

Y en `env.py`, para que `alembic revision --autogenerate` produzca bloques batch: `context.configure(connection=conn, target_metadata=Base.metadata, render_as_batch=True)` `[CITADO: alembic.sqlalchemy.org/en/latest/batch.html]`.

**Verificación de preservación** `[VERIFICADO: ejecutado sobre `…\mi proyecto ñ\datos con espacios ñ\porteria.sqlite3`]` — datos sembrados con los casos feos de D-33 (viaje con 3 remitos, remito compartido, peso teórico `NULL`, número de remito con `ñ` y con espacio):

```
ANTES:   {'viaje': 2, 'remito': 3, 'viaje_remito': 4}
DESPUES: {'viaje': 2, 'remito': 3, 'viaje_remito': 4}
  columnas de remito: ['id','numero','peso_teorico_kg','creado_en_utc']
  remito r2 peso teorico: [('r2','R-2',None,None)]     <- el NULL sobrevivio
  viaje_remito preservado identico: True
  viaje preservado identico: True
  remito: columnas originales preservadas: True
  integrity_check: ok
  foreign_key_check: sin violaciones
```

> **`PRAGMA foreign_key_check` después de migrar es obligatorio, no opcional.** Con `foreign_keys=OFF` durante el batch, SQLite no valida nada; si la migración dejó una referencia colgada, el único momento en que se puede detectar es al final. Esta comprobación es la mitad del Criterio 6.

**Copia previa (D-34)**, con la API de backup de SQLite en vez de copiar el archivo (que con WAL activo dejaría fuera el `-wal`):

```python
import sqlite3
src, dst = sqlite3.connect(ruta_db), sqlite3.connect(ruta_backup)
with dst:
    src.backup(dst)          # consistente aunque haya escritores
src.close(); dst.close()
```

`[VERIFICADO: produjo una copia de 28 672 bytes consistente antes de la migración]`

---

### Pattern 7: Reloj único del proceso, con ancla a UTC

**What:** **Dos** relojes con roles que no se mezclan, más un **ancla** que los une, más una **regla de invalidación** tras suspensión.

```python
# infraestructura/runtime/reloj.py
import time, datetime as dt

class RelojDelProceso:
    """Puerto Reloj. Inyectable => pruebas deterministas.

    perf_counter_ns y NO monotonic_ns: en Python 3.12 sobre Windows,
    time.monotonic() usa GetTickCount64() con resolucion de 15,625 ms.
    Medir una ventana de +-150 ms con eso es tener 10% de error de
    cuantizacion antes de empezar. VERIFICADO en esta maquina.
    """
    def __init__(self) -> None:
        self._anclar()

    def _anclar(self) -> None:
        self._ancla_mono_ns = time.perf_counter_ns()
        self._ancla_utc = dt.datetime.now(dt.timezone.utc)

    def instante(self) -> int:
        """Instante monotonico del proceso, en ns. Para medir DELTAS."""
        return time.perf_counter_ns()

    def utc_de(self, instante_ns: int) -> dt.datetime:
        """Traduce un instante monotonico al UTC persistible.
        La precision RELATIVA es de microsegundos; la ABSOLUTA hereda
        la del ancla (~15,6 ms en Windows/3.12). Lo que se audita es
        el desvio entre camaras, que es relativo."""
        delta_us = (instante_ns - self._ancla_mono_ns) / 1000
        return self._ancla_utc + dt.timedelta(microseconds=delta_us)

    def reanclar_tras_suspension(self) -> None:
        """QueryPerformanceCounter no avanza durante suspend/resume y
        GetTickCount64 si. Tras un resume, el ancla es invalida."""
        self._anclar()

    def fecha_local(self) -> dt.date:
        return dt.datetime.now().astimezone().date()      # D-37/D-38: dia local
```

**La medición que fuerza esta decisión** `[VERIFICADO: `time.get_clock_info` + muestreo en bucle apretado, Windows 11]`:

| Reloj | Python 3.12.12 | Python 3.14.0 |
|-------|----------------|---------------|
| `time.monotonic` | `GetTickCount64()` · resolución **0,015625 s** · paso medido **15 000 000 ns** · sólo **20 valores distintos** en 300 ms | `QueryPerformanceCounter()` · 1e-07 |
| `time.perf_counter` | `QueryPerformanceCounter()` · resolución **1e-07** · paso medido **100 ns** · **717 804 valores distintos** en 300 ms | `QueryPerformanceCounter()` · 1e-07 |
| `time.time` | `GetSystemTimeAsFileTime()` · resolución **0,015625 s** | `GetSystemTimePreciseAsFileTime()` · 1e-07 |

`datetime.datetime.now(timezone.utc)` llamado cinco veces seguidas devolvió **el mismo valor las cinco veces**. Es un reloj de pared, no un cronómetro. `[VERIFICADO]`

**La contrapartida, dicha con honestidad:** `GetTickCount64` **sí** avanza durante suspensión y `QueryPerformanceCounter` se comporta mal a través de suspend/resume `[CITADO: learn.microsoft.com/…/nf-sysinfoapi-gettickcount64]`. La elección de `perf_counter_ns` es correcta para lo que esta fase mide —sub-segundo, dentro de una sesión— y **incorrecta** para medir horas a través de una suspensión. El cronómetro de espera de la Fase 8 debe usar UTC persistido, no el reloj monotónico. Y el `reanclar_tras_suspension()` es la razón por la que el ancla vive en un objeto y no en dos variables sueltas.

**Cómo se persiste:** `capturado_en_utc_iso` como texto ISO-8601 con offset (`2026-07-25T19:24:45.133966-03:00`), `desfasaje_local_min` = `-180` como entero aparte, `fecha_local` = `2026-07-25` como texto para agrupar, e `instante_monotono_ns` crudo para poder recalcular desvíos dentro de la misma corrida. `sync_delta_ms` / `desvio_ms` se calcula **enteramente en espacio `perf_counter`**, así que su precisión es de microsegundos aunque el sello UTC absoluto sea grueso. Esa descomposición es lo que hace que la afirmación auditable —"estas tres fotos están a menos de 150 ms una de otra"— sea defendible.

---

### Pattern 8: ACL de solo lectura con triple barrera, y el cassette que ya estaba escrito

**What:** Tres capas independientes, más el hallazgo de que **el payload crudo de INT-05 y el cassette de D-41 son el mismo dato**.

```python
# infraestructura/externos/comun/cliente.py — BARRERA 1
class ClienteSoloLectura:
    """No expone metodos de escritura. Para hacer un POST hay que
    reescribir esta clase, no llamar a otro metodo."""
    VERBOS = frozenset({"GET", "HEAD", "OPTIONS"})
    def get(self, url, **kw):     return self._pedir("GET", url, **kw)
    def head(self, url, **kw):    return self._pedir("HEAD", url, **kw)
    def options(self, url, **kw): return self._pedir("OPTIONS", url, **kw)
```

```python
# infraestructura/externos/comun/conexion.py — BARRERA 2
import re
from sqlalchemy import event

class EscrituraProhibida(RuntimeError): ...

_PERMITIDO = re.compile(r"^\s*(?:--[^\n]*\n|/\*.*?\*/|\s)*(SELECT|WITH)\b", re.I | re.S)
_VETADO = re.compile(r"\b(INSERT|UPDATE|DELETE|MERGE|CREATE|DROP|ALTER|TRUNCATE|"
                     r"GRANT|REVOKE|REPLACE|ATTACH|DETACH|VACUUM|PRAGMA|"
                     r"EXEC|EXECUTE|CALL|SET)\b", re.I)

def blindar_solo_lectura(motor, registro: list) -> None:
    @event.listens_for(motor, "before_cursor_execute")
    def _guardia(conn, cursor, statement, parameters, context, executemany):
        registro.append(statement)                       # el espia de la barrera 3
        if not _PERMITIDO.match(statement) or _VETADO.search(statement):
            raise EscrituraProhibida(statement.strip()[:120])
```

`[VERIFICADO: 9 casos ejecutados, los 9 se comportaron como se esperaba]`

| Sentencia | Resultado |
|-----------|-----------|
| `SELECT nro, peso FROM remitos` | PASÓ |
| `WITH x AS (SELECT 1 AS a) SELECT a FROM x` | PASÓ |
| `-- comentario\n SELECT 1` | PASÓ |
| `select 1 from remitos where nro='x'--'` | PASÓ |
| `INSERT INTO remitos VALUES (…)` | **BLOQUEADA** |
| `UPDATE remitos SET peso=0` | **BLOQUEADA** |
| `DELETE FROM remitos` | **BLOQUEADA** |
| `DROP TABLE remitos` | **BLOQUEADA** |
| `SELECT 1; DROP TABLE remitos` (apilada) | **BLOQUEADA** |

**Tres limitaciones que hay que escribir en el código, no descubrir en producción:**

1. **La regex tiene falsos positivos.** `SELECT * FROM t WHERE nota = 'update pendiente'` queda bloqueada. Es un tripwire deliberadamente paranoico; la lista de sentencias legítimas de PALJET es finita y se congela en el cassette, así que el falso positivo se detecta en la Fase 1 y no en campo.
2. **`before_cursor_execute` no ve el DBAPI crudo.** `motor.raw_connection().cursor().execute(...)` la esquiva. Por eso el tercer contrato de `import-linter` del Patrón 1 prohíbe `sqlite3`, `socket` y `http.client` dentro de `infraestructura.externos`.
3. **La barrera real es la credencial.** Las dos capas de código son defensa en profundidad; lo que impide de verdad escribir en el ERP del cliente es un usuario de base con `GRANT SELECT` y nada más. **El plan debe incluir la tarea de pedirlo por escrito**, y el documento de contratos congelados debe registrar qué permisos tiene la credencial usada.

**BARRERA 3 — la prueba que falla la construcción (D-47):**

```python
# tests/arquitectura/test_adaptadores_son_solo_lectura.py
def test_ningun_adaptador_externo_emite_verbos_de_escritura(espia_http):
    ejercitar_todos_los_adaptadores(espia_http)      # contra cassettes, sin red
    assert {ll.metodo for ll in espia_http.llamadas} <= {"GET", "HEAD", "OPTIONS"}
    assert espia_http.llamadas, "la prueba no ejercito ningun adaptador"   # anti-vacuidad

def test_ninguna_sentencia_externa_muta(registro_sql):
    ejercitar_todos_los_adaptadores_sql(registro_sql)
    assert all(_PERMITIDO.match(s) and not _VETADO.search(s) for s in registro_sql)
    assert registro_sql, "la prueba no ejercito ninguna consulta"
```

La aserción anti-vacuidad importa: una suite que no ejercita nada pasa trivialmente y da falsa seguridad. Es el modo de fallo silencioso más común en pruebas de arquitectura.

**El cassette y el payload crudo son el mismo dato.** INT-05 ya exige persistir, de cada consulta externa, el payload íntegro con la petición, el instante, el código de respuesta y la duración (D-46). Eso **es** exactamente un cassette. La recomendación es un solo mecanismo:

```
GET real → anonimizador (D-42) → tabla payload_crudo (INT-05, comprimido)
                                        │
                                        └─► `porteria exportar-cassette` → tests/…/cassettes/*.json
                                                                            (versionado en git, D-41)
```

Ventajas sobre montar vcrpy encima: (a) cubre **los dos caminos** de D-44 —vcrpy sólo intercepta HTTP y no puede grabar un `SELECT` contra PALJET—, (b) la anonimización ocurre en el acto de grabar y no en un `before_record_response` que se puede olvidar, y (c) el formato del cassette es un contrato propio y estable en vez de un YAML atado a la versión de vcrpy.

**Recomendación sobre vcrpy, entonces, matizada:** `vcrpy` 8.3.0 + `pytest-recording` 0.13.4 siguen siendo la opción correcta **para el subconjunto HTTP**, si y sólo si se necesita grabar tráfico que el `ClienteSoloLectura` no atraviesa. Si todo el tráfico HTTP pasa por ese cliente —que es el diseño de D-47—, entonces el grabador propio ya cubre el 100 % y vcrpy es una dependencia sin trabajo que hacer. **La decisión concreta depende de un dato que hoy no existe: si PALJET habla HTTP, SQL o ambos.** Ver §Open Questions 1.

**Si no hay acceso al ejecutar la fase (D-43):** el diseño no cambia en nada. El puerto lo dicta el dominio (`ProveedorDeDatosMaestros.obtener_peso_teorico(remitos) -> Resultado[PesoTeorico]`), el falso en memoria se escribe igual con los datos feos, y el cassette es un archivo que hoy contiene una respuesta **sintética marcada como tal** (`"origen": "sintetico", "grabado_en": null`) y mañana se reemplaza por una real sin tocar una línea de código de producción. El dato mínimo para no bloquear la fase: **qué campos necesita el dominio**, que ya está en `ARCHITECTURE.md` §Pattern 7 y en D-41. Lo que la fase no puede responder sin acceso es si el modelo que se congela *encaja* — y esa es precisamente la deuda bloqueante que D-43 manda registrar con responsable y fecha.

---

### Pattern 9: Línea de comandos en español que no se rompe

```python
# cli/app.py
import sys, typer
import typer.rich_utils as ru

# D-50: la ayuda generada por Typer/Click viene en ingles. Estas constantes
# son de modulo y se pueden reemplazar. VERIFICADO que existen en typer 0.27.0.
ru.OPTIONS_PANEL_TITLE   = "Opciones"
ru.COMMANDS_PANEL_TITLE  = "Órdenes"
ru.ARGUMENTS_PANEL_TITLE = "Argumentos"
ru.ERRORS_PANEL_TITLE    = "Error"
ru.ABORTED_TEXT          = "Cancelado."
ru.REQUIRED_LONG_STRING  = "[obligatorio]"
ru.DEFAULT_STRING        = "por defecto: {}"

app = typer.Typer(add_completion=False, help="Herramienta de diagnóstico de portería.")

@app.command("verificar-huellas")
def verificar_huellas(
    camara: str = typer.Option("todas", "--camara", "-c", help="Cámara a verificar"),
    desde: str | None = typer.Option(None, "--desde", help="Fecha inicial AAAA-MM-DD"),
    estructurado: bool = typer.Option(False, "--json", help="Salida estructurada"),
) -> None:
    """Verifica la huella SHA-256 de la evidencia persistida."""
    ...
```

`[VERIFICADO: ejecutado]` — órdenes con guiones y palabras en español (`verificar-huellas`, `crear-administrador`), opciones en español (`--camara`, `--desde`, `--json`), salida legible por defecto y JSON bajo bandera (D-51), y exit code **2** ante una orden inexistente.

**Dos límites honestos de D-50:**
1. Los nombres de las opciones se declaran como cadena explícita (`typer.Option(..., "--camara")`), así que pueden ser cualquier cosa; pero **conviene que no lleven tildes**. Una opción `--cámara` obliga al operador a escribir un acento en una consola cuyo teclado y encoding no están garantizados. Palabras españolas sin tilde en los nombres de opción, tildes libres en la **ayuda y en la salida**.
2. Los mensajes de error propios de Click (`No such command`, `Missing argument`) no salen de `rich_utils` y siguen en inglés salvo que se subclasee `TyperGroup`/`UsageError`. Decisión para el planner: aceptarlos, o agregar una tarea acotada de subclase.

---

### Anti-Patterns to Avoid

- **Usar `time.monotonic()` como reloj de sincronía.** 15,6 ms de resolución en la plataforma de destino. Es el error más caro de esta fase porque contamina evidencia ya persistida.
- **Escribir la fila y después el archivo.** Invierte el huérfano que se puede tolerar. Una fila sin archivo es evidencia rota (D-12).
- **Poner las imágenes como BLOB en SQLite.** `ARCHITECTURE.md` §Anti-Pattern 8. Los thumbnails de ~15 KB **sí** van en la base (D-04); las imágenes completas no.
- **Concatenar `"sqlite:///" + str(path)`.** Usar `URL.create("sqlite", database=str(path))`.
- **Poner `foreign_keys=ON` en el motor de migraciones.** Rompe todo `batch_alter_table`.
- **Usar `DateTime(timezone=True)` en SQLite y confiar en el `tzinfo` al leer.** Se pierde. Ver Pitfall 4.
- **Una cola entre decodificador y consumidor.** Medido: +806 ms/s de latencia acumulada.
- **Que la prueba de solo-lectura pase sin ejercitar nada.** Aserción anti-vacuidad obligatoria.
- **Diseñar el puerto copiando el esquema de PALJET.** `ARCHITECTURE.md` §Anti-Pattern 13. El puerto lo dicta el dominio.
- **Confiar en `--fail-on` de `pip-licenses` con una sola cadena.** Ver Pitfall 10.
- **Bloquear la fusión con la prueba de 10 minutos.** D-53: compuerta rápida con la versión corta, tanda programada con la larga.

---

## Don't Hand-Roll

| Problema | No construir | Usar en su lugar | Por qué |
|----------|--------------|------------------|---------|
| Verificar que el dominio no importa infraestructura | Un `MetaPathFinder` propio o un escaneo con `ast` | **`import-linter` 2.13** | Verificado que atrapa las cuatro vías de evasión, incluidas `TYPE_CHECKING` e indirectas. El finder propio sólo ve lo que se ejecuta |
| Grafo de imports del proyecto | Recorrer `ast` a mano | **`grimp`** (viene con import-linter) | Resuelve imports relativos, paquetes namespace y ciclos |
| Hash de un archivo en streaming | Bucle `while chunk := fh.read(…)` | **`hashlib.file_digest(fh, "sha256")`** (stdlib 3.11+) | Verificado idéntico al bucle manual, sin el riesgo de olvidar el tamaño de chunk |
| Escritura atómica | Biblioteca `atomicwrites` | **`tempfile.mkstemp` + `fsync` + `os.replace`** | `atomicwrites` está sin mantener desde 2022 y su autor recomienda exactamente este patrón de stdlib |
| Hash de contraseñas | PBKDF2 propio, `hashlib.sha256(sal+pass)` | **`argon2-cffi` 25.1.0** | Formato PHC que guarda los parámetros dentro del hash, `check_needs_rehash` para migrar parámetros sin pedir la contraseña, defaults por encima del mínimo de OWASP |
| Migraciones de esquema | Scripts SQL numerados a mano | **Alembic 1.18.5** con `render_as_batch=True` | El "move and copy" de SQLite (reflejar/crear/copiar/soltar/renombrar) tiene una decena de casos borde con restricciones sin nombre |
| Copia de la base antes de migrar | `shutil.copy(db)` | **`sqlite3.Connection.backup()`** | Con WAL activo, copiar sólo el `.sqlite3` deja afuera transacciones que viven en el `-wal` |
| Grabar tráfico HTTP real | Interceptar `urllib` a mano | **`vcrpy` 8.3.0 + `pytest-recording`** — *sólo si hace falta más allá del `ClienteSoloLectura`* | Filtrado de cabeceras sensibles, bloqueo de red y modos de grabación resueltos |
| Grabar resultados de consultas SQL | (no existe estándar) | **Cassette propio reutilizando la tabla de payload crudo de INT-05** | `vcrpy` no intercepta DBAPI. Verificado que no hay una biblioteca de referencia para esto; `pytest-adbc-replay` existe pero es específico de ADBC |
| Bitácora estructurada con contexto por hilo | `logging.LoggerAdapter` con `dict` manual | **`structlog` 26.1.0** sobre `RotatingFileHandler` | El contexto acumulado por hilo es lo que hace legible una bitácora de N fuentes concurrentes en la Fase 2 |
| Ubicación de la config de arranque | Hardcodear `%APPDATA%` | **`platformdirs` 4.11.0** | Resuelve Windows hoy y Linux/macOS cuando lleguen, sin `if sys.platform` |
| Inventario de licencias | Parsear `METADATA` a mano | **`pip-licenses` 5.5.5** | Normaliza clasificadores viejos y expresiones SPDX nuevas; verificado sobre las 35 dependencias |
| Slot de último valor | `queue.Queue(maxsize=1)` | **~40 líneas propias con `threading.Condition`** | Es el único caso de esta tabla donde *sí* conviene escribirlo: `Queue` bloquea al productor y `deque` no ofrece espera bloqueante ni contador de descartes. Ver Patrón 4 |

**Key insight:** en esta fase, casi todo lo que parece "un detalle de plataforma" ya está resuelto en la biblioteca estándar de Python 3.12 (`hashlib.file_digest`, `os.replace`, `sqlite3.backup`, `tempfile.mkstemp`), y casi todo lo que parece "una biblioteca sencilla de escribir" —el análisis de imports, las migraciones batch de SQLite— tiene una decena de casos borde que ya costaron años a otros. La única excepción es el slot de capacidad 1: es la pieza donde la semántica que el proyecto necesita no coincide con ninguna estructura de la stdlib.

---

## Common Pitfalls

### Pitfall 1: `time.monotonic()` en Windows con Python 3.12 tiene 15,6 ms de resolución
**Qué sale mal:** el desvío entre cámaras, la antigüedad del frame y la ventana de ±150 ms se miden con un reloj que sólo puede reportar múltiplos de ~15 ms. Dos frames capturados con 10 ms de diferencia reportan desvío 0. La evidencia dice "sincronizada" sin haberlo medido.
**Por qué pasa:** `time.monotonic()` se implementa con `GetTickCount64()` hasta Python 3.12 inclusive; recién 3.13 pasa a `QueryPerformanceCounter`. `CLAUDE.md` fija 3.12 por compatibilidad de ruedas, y esa elección —correcta— arrastra este costo.
**Cómo evitarlo:** `time.perf_counter_ns()` como reloj del proceso, encapsulado en el puerto `Reloj` (Patrón 7). Y una prueba de arranque que falla si `time.get_clock_info("perf_counter").resolution > 1e-6`.
**Señales de alerta:** desvíos persistidos que son siempre 0 o siempre múltiplos de 15; `edad_del_frame_ms` con muy pocos valores distintos.
`[VERIFICADO: get_clock_info + muestreo, 20 valores distintos en 300 ms vs 717 804 de perf_counter]`

### Pitfall 2: `os.fsync` sobre un directorio no existe en Windows
**Qué sale mal:** se copia el patrón POSIX canónico de escritura durable (escribir, `fsync` del archivo, `rename`, `fsync` del directorio padre) y la aplicación revienta con `PermissionError: [Errno 13] Permission denied` en la plataforma de destino.
**Por qué pasa:** Windows no expone un descriptor de directorio sincronizable.
**Cómo evitarlo:** guardar ese paso con `if os.name != "nt"`. La durabilidad del rename en NTFS se apoya en el journal del sistema de archivos, no en un `fsync` explícito.
**Señales de alerta:** el código de almacenamiento tiene un `try/except OSError: pass` alrededor del fsync — eso oculta el problema en vez de documentarlo.
`[VERIFICADO: PermissionError(13) reproducido]`

### Pitfall 3: MAX_PATH de 260 caracteres está activo y acota la raíz de evidencia configurable
**Qué sale mal:** el cliente configura la evidencia en `D:\Compartido\Producción\Portería\Evidencia fotográfica 2026\` y a los tres meses las escrituras empiezan a fallar con `FileNotFoundError`, un error que no dice nada sobre el largo de la ruta.
**Por qué pasa:** `LongPathsEnabled = 0` en esta máquina (valor por defecto en muchas instalaciones). El sufijo `evidencia/AAAA/MM/DD/<64hex>.jpg` mide **89 caracteres**, así que la raíz no puede pasar de **~170**.
**Cómo evitarlo:** (a) validar el largo de la raíz al configurarla y rechazar con un mensaje que diga el número —"la ruta no puede superar 170 caracteres, la elegida tiene 214"—, cumpliendo UI-05; (b) usar el prefijo `\\?\` para las rutas de evidencia, que verificado sí funciona hasta 400 caracteres; (c) documentar `LongPathsEnabled` como requisito de despliegue para la Fase 11.
**Señales de alerta:** `FileNotFoundError` al escribir en un directorio que existe.
`[VERIFICADO: 259 chars OK, 261 chars FileNotFoundError, con prefijo \\?\ OK; el límite de 255 por componente sigue vigente]`

### Pitfall 4: `DateTime(timezone=True)` en SQLite pierde la zona horaria al leer
**Qué sale mal:** se persiste `datetime.now(timezone.utc)` en una columna `DateTime(timezone=True)` y al leerla vuelve **naive**. El código que después hace `.astimezone()` interpreta ese naive como hora local y desplaza todo el histórico tres horas.
**Por qué pasa:** SQLite no tiene tipo de fecha; el dialecto serializa a texto sin offset y al leer construye un `datetime` sin `tzinfo`.
**Cómo evitarlo:** persistir **texto ISO-8601 con offset** (`String(32)`) más una columna entera `desfasaje_local_min`, como en el Patrón 5. Es ordenable lexicográficamente, no depende del dialecto y hace explícito lo que D-05 y D-37 piden guardar.
**Señales de alerta:** cualquier `.replace(tzinfo=...)` en el código de lectura — eso es adivinar.
`[VERIFICADO: guardado `2026-07-25 22:24:45.076838`, leído con `tzinfo: None`]`

### Pitfall 5: `batch_alter_table` de Alembic contra `PRAGMA foreign_keys=ON`
**Qué sale mal:** la primera migración que toque una tabla referenciada falla en el cliente con `IntegrityError: FOREIGN KEY constraint failed [SQL: DROP TABLE remito]`. El cliente queda con la base a medio migrar y años de evidencia detrás.
**Por qué pasa:** batch hace DROP+CREATE de la tabla real.
**Cómo evitarlo:** motor dedicado a migraciones con `foreign_keys=OFF` en el listener `connect` (no dentro de la transacción — ahí el PRAGMA es no-op), y `PRAGMA foreign_key_check` obligatorio al terminar.
**Señales de alerta:** `env.py` reutiliza el motor de la aplicación.
`[VERIFICADO: el error se reprodujo y la solución se validó preservando 9 filas]`

### Pitfall 6: `os.rename` sobre un archivo existente falla en Windows
**Qué sale mal:** el código funciona en la máquina del desarrollador si es Linux, y en Windows falla `FileExistsError` en el único caso que importa: reescribir evidencia con el mismo hash.
**Cómo evitarlo:** `os.replace`, siempre. Y el temporal en el **mismo directorio** que el destino, porque `os.replace` sólo puede ser atómico dentro del mismo volumen.
`[VERIFICADO: FileExistsError(17) reproducido]`

### Pitfall 7: la cola entre decodificador y consumidor
**Qué sale mal:** la latencia crece monótonamente y nunca se recupera. Es el Pitfall 1 de `PITFALLS.md`.
**Cómo evitarlo:** slot de capacidad 1 con descarte del más viejo y contador (Patrón 4).
**Señales de alerta:** `frames_descartados` en 0 con un consumidor más lento que la fuente. Es la métrica que delata el problema: si nada se descarta, todo se está acumulando.
`[VERIFICADO: +806,6 ms/s de crecimiento medido con la cola, ≈0 con el slot]`

### Pitfall 8: la consola de Windows es cp1252 y la CLI en español revienta
**Qué sale mal:** `porteria verificar-huellas` termina con `UnicodeEncodeError: 'charmap' codec can't encode character '\u2713'`. En un producto cuya CLI es la herramienta de soporte remoto (D-49), es un fallo de primer día.
**Por qué pasa:** `sys.stdout.encoding` es `cp1252` por defecto en Python 3.12 sobre Windows, aunque `sys.getfilesystemencoding()` sea `utf-8`.
**Cómo evitarlo:** activar el modo UTF-8 del intérprete — `PYTHONUTF8=1` en el entorno, `-X utf8` en el arranque, o `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` como primera línea del punto de entrada. La última es la única que sobrevive al empaquetado con PyInstaller sin depender del entorno del cliente.
**Señales de alerta:** cualquier `try/except UnicodeEncodeError` en la CLI.
`[VERIFICADO: UnicodeEncodeError reproducido sin el modo; con PYTHONUTF8=1 la salida `Cámara «patente ñ» … Ñandú áéíóú ✓` sale intacta]`

### Pitfall 9: confundir la bitácora técnica con la de auditoría
**Qué sale mal:** subir el nivel de detalle para depurar un problema de cámara inunda de ruido la evidencia legal, o la rotación de archivos borra parte de la cadena de custodia.
**Cómo evitarlo:** D-11 ya lo resuelve, pero el plan tiene que materializarlo como **dos módulos distintos con dos destinos distintos**: `structlog` → `RotatingFileHandler` para la técnica, tabla encadenada en SQLite para la de auditoría. Ni una línea de código compartida entre ambas, para que sea imposible confundirlas por accidente.
**Señales de alerta:** un solo `logger` con un parámetro `es_auditoria=True`.

### Pitfall 10: `pip-licenses --fail-on` compara cadenas y las cadenas varían
**Qué sale mal:** la compuerta de D-55 pasa en verde con una dependencia GPL porque su metadato dice `GNU General Public License v3 or later (GPLv3+)` y la lista de bloqueo decía `GPLv3`.
**Por qué pasa:** el ecosistema Python está a mitad de la transición de clasificadores Trove a expresiones SPDX. En el inventario verificado convivieron `MIT`, `MIT License`, `MIT-0`, `MIT OR Apache-2.0`, `BSD License` y `BSD-3-Clause` — seis formas para dos licencias.
**Cómo evitarlo:** usar `--allow-only` con una **lista blanca explícita** de todas las variantes aceptadas, no `--fail-on` con una lista negra. La lista blanca falla ante lo desconocido, que es el comportamiento que D-55 pide ("falla ante una licencia contagiosa **o no identificable**"). Complementar con una prueba que falle si alguna dependencia reporta licencia `UNKNOWN`.
**Señales de alerta:** la compuerta nunca falló desde que se creó.
`[VERIFICADO: `--fail-on` ejecutado con exit 0 sobre 35 paquetes; las seis variantes de cadena observadas]`

### Pitfall 11: la prueba de solo-lectura que no ejercita nada
**Qué sale mal:** `assert {ll.metodo for ll in espia.llamadas} <= {"GET"}` pasa trivialmente cuando el conjunto está vacío, y nadie se entera de que el adaptador nunca se llamó.
**Cómo evitarlo:** aserción anti-vacuidad explícita en cada prueba de barrera, y una prueba de la prueba: un adaptador de mentira que hace un POST debe hacer fallar la suite.
**Señales de alerta:** la suite de arquitectura corre en menos de 50 ms.

---

## Code Examples

Todos los fragmentos de §Architecture Patterns se ejecutaron en Python 3.12.12 sobre Windows 11 durante esta investigación. Los tres de mayor densidad de riesgo, aislados:

### Motor SQLite listo para producción (WAL + FULL + FK + ruta con acentos)

```python
from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL
from pathlib import Path

def crear_motor(ruta_db: Path, *, para_migracion: bool = False):
    url = URL.create("sqlite", database=str(ruta_db))   # maneja espacios y acentos solo
    motor = create_engine(url)

    @event.listens_for(motor, "connect")
    def _pragmas(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=FULL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.execute("PRAGMA foreign_keys=" + ("OFF" if para_migracion else "ON"))
        cur.close()

    return motor
```

### Escritura atómica de evidencia (Windows-correcta)

Ver Patrón 2. Los tres puntos que no se pueden omitir: temporal en el mismo directorio, `os.replace` en vez de `os.rename`, y el `fsync` de directorio guardado tras `if os.name != "nt"`.

### Reloj del proceso con ancla a UTC

Ver Patrón 7. `perf_counter_ns` para deltas, `datetime.now(timezone.utc)` sólo en el ancla, y `reanclar_tras_suspension()` como método público porque la Fase 2 lo va a necesitar.

---

## State of the Art

| Enfoque viejo | Enfoque actual | Cuándo cambió | Impacto en esta fase |
|---------------|----------------|---------------|----------------------|
| `declarative_base()` + `Column()` + `relationship()` sin tipos | `DeclarativeBase` + `Mapped[]` + `mapped_column()` | SQLAlchemy 2.0 (2023) | Todo el esquema se escribe en estilo tipado; los ejemplos 1.x que aparecen en búsquedas son incorrectos |
| `Query` API (`session.query(X).filter(...)`) | `select()` + `session.scalars()` / `session.execute()` | SQLAlchemy 2.0 | Los repositorios usan `select()` |
| Bucle manual `while chunk := fh.read(8192)` para hashear | `hashlib.file_digest(fh, "sha256")` | Python 3.11 | Una línea, sin decidir el tamaño de chunk |
| `[project.optional-dependencies]` para grupos de desarrollo | `[dependency-groups]` (PEP 735) | 2024; soportado por uv | Es lo que permite el entorno aislado del dominio de D-52 con `--only-group` |
| `time.monotonic()` como "el reloj monotónico" en Windows | `time.perf_counter()` hasta 3.12; unificados en 3.13+ | Python 3.13 | **El hallazgo central de esta investigación**; en 3.12 hay que elegir explícitamente |
| `pytest-vcr` | `pytest-recording` | La propia doc de VCR.py lo declara sin mantener | Si se usa vcrpy, la integración es `pytest-recording` |
| `atomicwrites` como dependencia | `tempfile.mkstemp` + `os.replace` de la stdlib | El paquete quedó sin mantener en 2022 | Una dependencia menos |
| Clasificadores Trove de licencia | Expresiones SPDX en `license-expression` | PEP 639, adopción en curso | Obliga a lista blanca en la compuerta de licencias (Pitfall 10) |

**Deprecado / desactualizado:**
- **`CLAUDE.md` dice Alembic 1.16.x** — la versión actual es **1.18.5**. El planner debe usar la actual y proponer la corrección de `CLAUDE.md`.
- **`CLAUDE.md` dice `pydantic-settings` 2.x** — la actual es **2.14.2**.
- **`argon2.__version__`** está deprecado; usar `importlib.metadata.version("argon2-cffi")`. `[VERIFICADO: DeprecationWarning emitido]`
- **`pytest-vcr`**, **`atomicwrites`** — sin mantener.

---

## Assumptions Log

| # | Claim | Section | Riesgo si es incorrecto |
|---|-------|---------|--------------------------|
| **A1** | `LongPathsEnabled = 0` en la PC de portería del cliente, igual que en la máquina de desarrollo donde se midió | Pitfall 3 | Si el cliente lo tiene activado, la restricción de 170 caracteres es innecesariamente severa; si lo tiene en 0 y no se valida, las escrituras fallan a los meses. **La mitigación (validar el largo + prefijo `\\?\`) es correcta en ambos casos**, así que el riesgo es bajo |
| **A2** | `PRAGMA synchronous=FULL` en WAL tiene un costo despreciable a escala de una captura (D-14) | Patrón 3 | No se midió el costo en un disco lento o de red. Si la raíz de evidencia está en un NAS (extensión contemplada), el commit podría notarse. **Medible con `pytest-benchmark` en la Fase 3** |
| **A3** | `pytest` 9.1.1 (major nueva, 2026-06-19) no rompe nada de lo que esta fase necesita | Standard Stack | Se instaló pero no se ejecutó una suite real. Si hay incompatibilidad con algún plugin, se detecta en la primera tarea. Riesgo bajo, detección temprana |
| **A4** | `pytest-recording` 0.13.4 sigue siendo compatible con `vcrpy` 8.3.0 pese a no publicar desde 2025-05-08 | Standard Stack / Patrón 8 | Si no lo es, la alternativa es usar `vcrpy` directo con un fixture propio de ~15 líneas, o el grabador propio del Patrón 8 que ya se recomienda. **Riesgo bajo porque el diseño recomendado no depende de vcrpy** |
| **A5** | El desvío entre cámaras medido en espacio `perf_counter` es defendible en una auditoría aunque el sello UTC absoluto tenga ~15 ms de incertidumbre | Patrón 7 | Es un argumento técnico correcto, pero **nunca fue puesto a prueba por un auditor real ni por el cliente**. Si Administración exige precisión absoluta de milisegundos en el sello UTC, hace falta una fuente de tiempo externa (NTP disciplinado, RTCP de las cámaras). Ver Open Question 3 |
| **A6** | Los 4 roles de D-20 y el modelo de usuarios de D-19 se pueden congelar sin haber validado los permisos concretos con Logística, Compras y Administración | Patrón 5 / esquema | D-18 es alcance nuevo que el usuario agregó por encima de los requerimientos. Si los permisos reales no encajan en 4 roles fijos en código, hay que migrar el esquema — pero la migración es barata comparada con la bitácora encadenada, que sí es no retrofiteable |
| **A7** | Que el falso en memoria sirva simultáneamente como modo demostración del producto (D-48) no crea tensión entre "datos deliberadamente feos para las pruebas" y "datos presentables para una demostración comercial" | Patrón 8 | Un viaje con peso teórico nulo y una patente con guiones es exactamente lo que **no** se quiere mostrar en una demo de venta. Probablemente hagan falta **dos juegos de datos sembrados** sobre el mismo falso. Bajo costo, pero el planner debe preverlo |
| **A8** | PALJET expone algo consultable por HTTP, además del acceso SQL directo de D-44 | Patrón 8 | Si es 100 % SQL, `vcrpy` y `pytest-recording` son dependencias sin uso y hay que sacarlas del stack. Si es 100 % HTTP, el cassette propio para SQL no hace falta. **El diseño del Patrón 8 funciona en los tres escenarios**, pero la lista de dependencias no se puede cerrar sin este dato |

---

## Open Questions (RESOLVED)

> **Estado al cerrar la planificación de la Fase 1 (2026-07-26).** Las cinco preguntas quedaron
> resueltas por los planes `01-01` … `01-10`. Cada una lleva abajo su línea `**Resolución:**` con el
> plan que la cierra. Q1 y Q2 se cierran *con deuda declarada* mientras no haya acceso a PALJET ni a
> la balanza — eso es exactamente lo que habilita D-43, y `01-10` lo reporta como tal en vez de
> fingir que el contrato se congeló.

1. **¿PALJET habla HTTP, SQL directo, o ambos — y qué dato viene por cada camino?**
   - Lo que sabemos: D-44 dice explícitamente "los dos caminos según el dato", y que el descubrimiento debe documentar cuál viene por cuál. `STATE.md` registra que la documentación existe y el usuario la tiene, pero no se leyó.
   - Lo que falta: el reparto concreto. De él depende si `vcrpy` entra al stack (A8) y si el cassette propio necesita cubrir SQL.
   - Recomendación: **hacer que la primera tarea de la fase sea leer esa documentación**, antes de fijar dependencias. Si no hay acceso, D-43 aplica: se implementan las dos vías del Patrón 8, la lista de dependencias incluye vcrpy provisionalmente, y la deuda queda registrada con responsable y fecha.
   - **Resolución (plan `01-10`, con deuda declarada):** se implementan las dos vías. El transporte HTTP quedó decidido en `01-01` — `urllib.request` de la stdlib envuelto en `porteria.composicion.transporte_externo` e inyectado, **sin agregar ninguna dependencia HTTP** ni `vcrpy`: el cassette es propio y cubre los dos caminos. La tarea del GET real es `autonomous: false` porque necesita credenciales que hoy no existen. Mientras el cassette tenga `origen: "sintetico"`, el Criterio de Éxito 4 se cierra como **cumplido con deuda declarada**, y `VERIFICATION.md` debe decirlo textualmente.

2. **¿Con qué credencial se va a consultar PALJET, y tiene sólo `SELECT`?**
   - Lo que sabemos: la regla global del usuario y INT-04 exigen solo lectura; el Patrón 8 implementa dos barreras de código.
   - Lo que falta: la tercera barrera, que es la única real — un usuario de base con `GRANT SELECT` y nada más, otorgado por el DBA del cliente.
   - Recomendación: tarea explícita de solicitud por escrito, y que el documento de contratos congelados registre qué permisos tiene la credencial efectivamente usada. Sin eso, la afirmación "el sistema no puede escribir en el ERP" es una promesa de código, no una garantía.
   - **Resolución (plan `01-10`, con deuda declarada):** las dos barreras de código quedan planificadas y verificadas — el contrato `sin_conexion_cruda` de import-linter y la prueba de arquitectura de INT-04 con su aserción anti-vacuidad, que falla si el conjunto de adaptadores inspeccionados está vacío. La tercera barrera (el `GRANT SELECT` otorgado por el DBA del cliente) **no es código y sigue abierta**: queda como tarea `autonomous: false` con solicitud por escrito. La honestidad que exige esta pregunta se preserva: la Fase 1 entrega la promesa de código, no la garantía del permiso.

3. **¿La incertidumbre de ~15 ms en el sello UTC absoluto es aceptable para la auditoría?**
   - Lo que sabemos: el desvío **relativo** entre cámaras es preciso a microsegundos; el sello **absoluto** hereda la resolución de `GetSystemTimeAsFileTime` (15,6 ms en 3.12).
   - Lo que falta: si alguna vez alguien va a comparar el sello de una foto contra un registro externo (el ticket de la balanza, un log del ERP) con precisión de milisegundos.
   - Recomendación: persistir ambos (`capturado_en_utc_iso` derivado del ancla, con precisión de microsegundos en el texto, e `instante_monotono_ns` crudo) y documentar la incertidumbre real en el manifiesto de exportación de EVI-08. Convierte un supuesto silencioso en un dato auditable, que es la misma jugada que D-39 hace con la ventana de ±150 ms.
   - **Resolución (plan `01-02`, cerrada):** se adoptó la recomendación y se adelantó de EVI-08 a la Fase 1, porque el manifiesto es contrato no retrofiteable. `Reloj.incertidumbre_sello_ms()` mide la resolución real del reloj de pared con `time.get_clock_info("time").resolution` —**no se cablea como constante**, se mide en el equipo donde corre— y `Manifiesto.incertidumbre_sello_utc_ms` la persiste **entrando en el hash**. Se agregó además una prueba de guardia que falla si `time.get_clock_info("perf_counter").resolution > 1e-6`, es decir si la plataforma no alcanza para medir la ventana de ±150 ms. La pregunta de auditoría ("¿es aceptable?") deja de necesitar respuesta anticipada: el dato queda declarado y quien audite decide con él a la vista.

4. **¿Los cuatro roles fijos de D-20 resisten el contacto con Logística, Compras y Administración?**
   - Lo que sabemos: D-20 los declara fijos y con permisos en código; el rol de Compras es necesario para la prueba de solo-lectura de la Fase 9.
   - Lo que falta: validación con los usuarios indirectos, que todavía no participaron.
   - Recomendación: congelar los 4 roles ahora (el costo de agregar uno es una migración barata) pero **no** congelar la matriz de permisos; dejarla en un módulo de dominio aislado y con pruebas propias, para que evolucione sin tocar el esquema.
   - **Resolución (plan `01-09`, cerrada):** se adoptó la recomendación tal cual. Los cuatro roles se congelan en el esquema; la matriz de permisos vive en un módulo de dominio aislado con su propia matriz de pruebas, de modo que la validación pendiente con Logística, Compras y Administración pueda cambiar permisos sin una migración. Agregar un quinto rol sigue siendo una migración barata.

5. **¿Existe ya el video de referencia para las pruebas de CAP-03 y CAP-04?**
   - Lo que sabemos: D-58 y D-59 fijan cómo se obtienen (filmados en la portería real, recortes cortos versionados). `code_context` de CONTEXT.md dice que el repositorio no tiene código todavía.
   - Lo que falta: el material y el acuerdo escrito con el cliente.
   - Recomendación: la fase **no debe bloquearse** por esto. Las pruebas de frescura se pueden correr sobre un video sintético generado con `cv2.VideoWriter` —así se hizo en esta investigación, y midió perfectamente el crecimiento de latencia— porque lo que se verifica es el comportamiento de la cañería, no el contenido de la imagen. El material real se incorpora cuando exista, para las Fases 4 y 5.
   - **Resolución (plan `01-01`, cerrada):** la fase no se bloquea. La fixture de sesión `video_sintetico` genera con `cv2.VideoWriter` un archivo de 320×240 a 25 fps y ~30 s bajo la raíz de pruebas, y **se genera, no se versiona** (D-59). Es exactamente el material con el que esta investigación midió el crecimiento de latencia, así que la frescura se verifica sobre el comportamiento de la cañería y no sobre el contenido de la imagen. El material real de la portería llega en las Fases 4 y 5.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| **uv** | Entorno, lockfile, entorno aislado de D-52 | ✓ | 0.11.18 | — |
| **Python 3.12** | Runtime del producto | ✓ | 3.12.12 (instalado vía uv) | — |
| Python 3.14 | (no requerido) | ✓ | 3.14.0 (sistema) | No usar: `CLAUDE.md` pinea 3.12 |
| **SQLite** | Persistencia local | ✓ | 3.50.4 (embebido en el `sqlite3` de 3.12.12) | — |
| **git** | Versionado, cassettes, recortes de video | ✓ | repo limpio en `main` | — |
| **FFmpeg** (embebido en opencv) | Lectura y escritura de archivos de video | ✓ | backend `FFMPEG` de opencv-python-headless 5.0.0.93 | — |
| **Acceso a PALJET** | D-41, D-44, Criterio de Éxito 4 | ✗ | — | **D-43**: cassette sintético marcado como tal + deuda bloqueante con responsable y fecha |
| **Acceso a la balanza** | D-41, Criterio de Éxito 4 | ✗ | — | **D-43**: ídem |
| **Acceso a Geomov** | (fuera de alcance de la fase) | ✗ | — | **D-45**: la carga manual es la implementación de referencia, no un parche |
| **Video de referencia real** | CAP-03, CAP-04 | ✗ | — | Video sintético con `cv2.VideoWriter`; verificado que basta para medir el contrato de frescura |
| **Runner de CI en Windows** | D-53, D-54 | ✗ (no configurado) | — | Sin fallback: es tarea de la fase. La compuerta debe correr en Windows por D-54 |

**Dependencias faltantes sin alternativa viable:**
- **Runner de integración continua en Windows.** No existe todavía y es requisito de D-53/D-54. Es una tarea del plan, no un bloqueo.

**Dependencias faltantes con alternativa viable:**
- PALJET y balanza → cassette sintético + deuda bloqueante registrada (D-43). **El Criterio de Éxito 4 no se puede declarar cumplido sin ellos**, así que la verificación de la fase debe distinguir explícitamente entre "cumplido" y "cumplido con deuda declarada".
- Video real → video sintético para las pruebas de cañería.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest` 9.1.1 `[VERIFICADO: PyPI + instalado]` |
| Config file | Ninguno todavía — `[tool.pytest.ini_options]` en `pyproject.toml` es tarea de Wave 0 |
| Quick run command | `uv run pytest -q -m "not lenta"` |
| Full suite command | `uv run pytest -q` |
| Compuerta de arquitectura | `uv run lint-imports --no-cache` (exit 1 si se rompe un contrato) `[VERIFICADO]` |
| Compuerta de aislamiento | `uv run --isolated --no-project python tests/arquitectura/test_dominio_aislado.py` `[VERIFICADO]` |
| Compuerta de licencias | `uv run pip-licenses --allow-only "<lista blanca>"` (ver Pitfall 10) |
| Plataforma de la compuerta | **Windows únicamente** (D-54) |
| Marcadores | `lenta` (tanda programada, no bloquea la fusión — D-53) |

### Phase Requirements → Test Map

| Req ID | Comportamiento | Test Type | Automated Command | File Exists? |
|--------|----------------|-----------|-------------------|--------------|
| NUC-01 | El dominio no importa cv2/onnxruntime/PySide6 (estático) | arquitectura | `uv run lint-imports --no-cache` | ❌ Wave 0 |
| NUC-01 | El dominio se importa entero en un entorno sin esos paquetes | arquitectura | `uv run --isolated --no-project python tests/arquitectura/test_dominio_aislado.py` | ❌ Wave 0 |
| NUC-04 | Todo puerto de salida tiene doble; el sistema corre sin hardware | contrato | `uv run pytest tests/contrato -q` | ❌ Wave 0 |
| NUC-04 | Los datos feos existen y se usan (3 remitos, remito compartido, peso nulo, patente con guiones) | contrato | `uv run pytest tests/contrato/test_datos_feos.py -q` | ❌ Wave 0 |
| NUC-05 | Estado + evidencia + outbox en una sola transacción | integración | `uv run pytest tests/integracion/test_transaccion_unica.py -x -q` | ❌ Wave 0 |
| NUC-06 | La bitácora rota archivos y respeta el nivel configurado | unit | `uv run pytest tests/integracion/test_bitacora.py -q` | ❌ Wave 0 |
| CAP-03 | La fuente de archivo entrega frames en los dos modos | integración | `uv run pytest tests/integracion/test_fuente_archivo.py -q` | ❌ Wave 0 |
| CAP-04 | La antigüedad del frame no crece; los descartes se cuentan | integración + lenta | `uv run pytest tests/integracion/test_frescura.py -q` / `-m lenta` | ❌ Wave 0 |
| EVI-05 | La huella se calcula en ingesta y se persiste | unit | `uv run pytest tests/dominio/test_huella.py -q` | ❌ Wave 0 |
| EVI-05 | Recalcular reproduce el valor; un byte alterado lo rompe | integración | `uv run pytest tests/integracion/test_verificacion_huella.py -q` | ❌ Wave 0 |
| EVI-06 | La imagen va al filesystem, la base sólo metadatos y ruta relativa | integración | `uv run pytest tests/integracion/test_almacen_evidencia.py -q` | ❌ Wave 0 |
| VIA-05 | Viaje con 3 remitos y remito en 2 viajes | integración | `uv run pytest tests/integracion/test_esquema_viaje_remito.py -q` | ❌ Wave 0 |
| INT-04 | Ningún adaptador emite verbos ni sentencias de escritura | arquitectura | `uv run pytest tests/arquitectura/test_adaptadores_son_solo_lectura.py -q` | ❌ Wave 0 |
| INT-05 | El payload crudo se persiste con petición, instante, código y duración | integración | `uv run pytest tests/integracion/test_payload_crudo.py -q` | ❌ Wave 0 |
| DIS-05 | La migración preserva datos, incluidos los casos feos | migración | `uv run pytest tests/migracion -q` | ❌ Wave 0 |
| DIS-06 | Todo funciona en ruta con espacios y acentos | integración | `uv run pytest -q -k "acentos"` (fixture de ruta rara aplicada a toda la suite) | ❌ Wave 0 |

### Cómo se prueba cada Criterio de Éxito

**Criterio 1 — aislamiento del dominio.**
*Qué se mide:* presencia de aristas prohibidas en el grafo de imports (estático) y de módulos prohibidos en `sys.modules` tras importar todo el dominio (runtime).
*Instrumento:* `import-linter` 2.13 + subproceso `uv run --isolated --no-project`.
*Frecuencia:* cada commit. Compuerta bloqueante.
*Señal de fallo:* exit code 1 con la cadena completa del import ofensor (`porteria.dominio.comun.sucio -> cv2 (l.3)`).
*Prueba de la prueba:* un test que introduce temporalmente un módulo con `import cv2` en `dominio/` y verifica que `lint-imports` devuelve 1. Sin esto, un contrato mal escrito pasa siempre y nadie se entera.

**Criterio 2 — huella verificable.**
*Qué se mide:* igualdad entre el SHA-256 recalculado y el persistido; y desigualdad tras alterar un byte.
*Instrumento:* `hashlib.file_digest`.
*Frecuencia:* cada commit. Milisegundos.
*Señal de fallo:* `assert recalculado == persistido` falla, o el caso de manipulación devuelve `True` cuando debería devolver `False`.
*Muestreo:* no hace falta — es determinista. Pero la prueba de manipulación debe alterar **un byte en tres posiciones distintas** (primer byte, medio, último) para descartar que la lectura esté truncando.
`[VERIFICADO: ambos sentidos]`

**Criterio 3 — transacción cortada. Necesita dos estrategias, no una aserción.**
*Qué se mide:* la invariante `filas_persistidas − archivos_en_disco = ∅` (cero filas huérfanas), en dos modos de fallo distintos.
- **Modo A — fallo lógico.** `monkeypatch` sobre `UnidadDeTrabajo.confirmar` lanzando una excepción. Rápido (ms), determinista, corre en cada commit. Demuestra que el **orden del código** es correcto. `[VERIFICADO: 1 fila, 3 archivos, 0 filas huérfanas, 2 archivos huérfanos]`
- **Modo B — muerte del proceso.** Un `subprocess` que ejecuta la captura y al que se le manda `TerminateProcess` en un punto de sincronización (un archivo centinela que el hijo toca justo antes del commit). El padre reabre la base y verifica la invariante. Demuestra que **WAL recupera** bien, que es una propiedad distinta y la que importa ante un corte de energía (D-14, Pitfall 18).
*Frecuencia de muestreo del modo B:* **20 repeticiones con el punto de muerte desplazado aleatoriamente** dentro de una ventana de ±50 ms alrededor del commit. Una sola ejecución sólo prueba un instante; el fallo interesante vive en la ventana estrecha entre el `os.replace` y el commit del WAL.
*Señal de fallo:* cualquier repetición en la que `filas − archivos ≠ ∅`, o `PRAGMA integrity_check` distinto de `ok` al reabrir.
*Marcador:* modo A sin marcar (compuerta), modo B marcado `lenta` (tanda programada, D-53).

**Criterio 4 — contratos externos congelados.**
*Qué se mide:* (a) existe un cassette por cada sistema con `origen: "real"` y su payload crudo; (b) los dobles devuelven los cuatro casos feos exigidos; (c) la suite completa corre con los dobles y sin red.
*Instrumento:* suite de contrato parametrizada que corre **la misma clase de tests** contra el falso y contra el cassette; más un test de bloqueo de red (`socket.socket` monkeypatcheado para explotar) que garantiza que "corre sin sistemas externos" no es una ilusión de caché.
*Frecuencia:* cada commit para (b) y (c). Para (a), una verificación de presencia del archivo.
*Señal de fallo:* el cassette tiene `origen: "sintetico"` → el criterio se reporta como **cumplido con deuda declarada**, no como cumplido. Esta distinción tiene que estar en VERIFICATION.md, porque D-43 permite completar la fase pero no permite fingir que el contrato se congeló.
*Los cuatro casos feos, explícitos:* viaje con tres remitos · remito repartido en dos viajes · artículo con `peso_teorico_kg IS NULL` · patente con guiones y espacios (`" AB-123-CD "`). Cada uno con su aserción propia. `[VERIFICADO: los tres primeros ejercitados en el esquema real]`

**Criterio 5 — frescura sostenida. Necesita medir la pendiente, no un valor.**
*Qué se mide:* la **pendiente** de `antigüedad_del_frame` contra el tiempo, no su valor absoluto. Un valor máximo alto puede ser un pico legítimo; una pendiente positiva sostenida es el fallo.
*Instrumento:* fuente de archivo en modo tiempo real + consumidor a 5 Hz. Se registra `(t, antigüedad_ms)` en cada entrega.
*Frecuencia de muestreo:* una muestra por entrega, ≈5 Hz. En 60 s son ~300 muestras; en 600 s, ~3000. Suficiente para una regresión lineal estable.
*Criterios de aprobación, los tres a la vez:*
  1. `pendiente(antigüedad ~ t)` < **5 ms/s** — con la cola ilimitada se midieron **806 ms/s**, así que el umbral tiene dos órdenes de magnitud de margen y no es frágil.
  2. `mediana(segunda mitad)` ≤ `mediana(primera mitad) × 1,5` — con el slot se midió una **bajada** de 25,8 a 13,9 ms.
  3. `frames_descartados > 0` — si es 0 con un consumidor más lento que la fuente, el slot no está descartando y la latencia se está acumulando en otro lado.
*Cómo se resuelve la tensión con D-53:* **dos pruebas del mismo comportamiento.**
  - `test_frescura_acotada` — **60 segundos**, sin marcar, compuerta bloqueante. Verificado que 20 s ya separan las dos arquitecturas por un factor de 800; 60 s da margen de sobra.
  - `test_frescura_sostenida_diez_minutos` — **600 segundos**, marcada `lenta`, tanda programada. Es la que satisface el criterio literal del roadmap.
  No se usa reloj virtual: el fenómeno que se mide **es** la acumulación de buffers reales en el decodificador de FFmpeg, y un reloj falso lo haría desaparecer. La aceleración correcta es acortar la ventana, no falsificar el tiempo.
*Señal de fallo:* pendiente positiva sostenida, o `frames_descartados == 0` con consumidor lento.
`[VERIFICADO: los tres criterios medidos, slot vs cola]`

**Criterio 6 — rutas raras y migración que preserva.**
*Qué se mide:* dos cosas independientes que conviene no mezclar.
- **Rutas:** una fixture de sesión que planta base y evidencia en `…/PROYECTO PAGOS/IA visual ñandú áéí/` y que se aplica a **toda** la suite de integración, no a un test aislado. Que DIS-06 sea una condición de todo el entorno de prueba y no un caso especial es lo que evita que se rompa por descuido en la Fase 5.
- **Migración:** sembrar en la versión N−1 con los casos feos → copia previa (`sqlite3.backup`) → migrar → comparar **fila por fila**, no sólo contar → `PRAGMA foreign_key_check` → `PRAGMA integrity_check`.
*Frecuencia:* cada commit. Y **cada migración nueva agrega su propio test**, que es literalmente lo que dice D-33.
*Señal de fallo:* diferencia en cualquier fila, `foreign_key_check` con filas, o `integrity_check ≠ 'ok'`.
*Muestreo del caso adverso:* además del camino feliz, un test que verifica que **una migración que perdería datos falla la prueba** — por ejemplo un `drop_column` sin respaldo. Sin ese caso negativo, la prueba de migración es un espejo del código de migración y no verifica nada.
`[VERIFICADO: 9 filas preservadas, `integrity_check: ok`, `foreign_key_check: sin violaciones`]`

### Sampling Rate

- **Por commit de tarea:** `uv run pytest -q -m "not lenta"` + `uv run lint-imports --no-cache`
- **Por merge de wave:** suite rápida completa + prueba de entorno aislado + inventario de licencias
- **Compuerta de fase:** suite completa incluidas las `lenta` (10 minutos de frescura, 20 repeticiones de muerte del proceso) en verde antes de `/gsd-verify-work`
- **Tanda programada (D-53):** las `lenta`, cuya falla abre un asunto y no traba la fusión

### Wave 0 Gaps

- [ ] `pyproject.toml` — `[tool.pytest.ini_options]` con `markers = ["lenta: ..."]`, `testpaths`, `pythonpath`
- [ ] `pyproject.toml` — `[tool.importlinter]` con los tres contratos de §Patrón 1 — cubre NUC-01, D-47
- [ ] `pyproject.toml` — `[dependency-groups]` con el grupo `dominio` aislado — cubre D-52
- [ ] `tests/conftest.py` — fixture de sesión con la ruta con espacios y acentos (DIS-06), fixture de motor SQLite, fixture de reloj determinista
- [ ] `tests/arquitectura/test_dominio_aislado.py` + su script de subproceso — NUC-01
- [ ] `tests/arquitectura/test_adaptadores_son_solo_lectura.py` con aserciones anti-vacuidad — INT-04
- [ ] `tests/contrato/conftest.py` — parametrización falso ↔ cassette — NUC-04
- [ ] `tests/recursos/videos/` — video sintético generado en `conftest` (el real llega con D-58/D-59) — CAP-03
- [ ] Script de compuerta de CI en Windows que encadena pytest + lint-imports + entorno aislado + licencias y propaga el peor exit code — D-53, D-54
- [ ] Activación del modo UTF-8 en el punto de entrada de la CLI — D-50, Pitfall 8
- [ ] Instalación del framework: `uv sync` (pytest ya está en el conjunto verificado)

---

## Security Domain

ASVS nivel 1 (`security_asvs_level: 1`, `security_block_on: high`). Esta fase es una aplicación de escritorio local, de un solo proceso, sin servidor, sin red entrante y con acceso saliente exclusivamente de lectura. El modelo de amenazas real es acotado y **conviene decir con precisión qué protege y qué no**, porque es un producto de auditoría que se vende como tal.

### Applicable ASVS Categories

| ASVS Category | Aplica | Control estándar |
|---------------|--------|------------------|
| **V2 Authentication** | **Sí** (D-18 a D-26) | `argon2-cffi` 25.1.0, Argon2id, sal por usuario, formato PHC. Sin credencial por defecto (D-23) |
| **V3 Session Management** | Parcial | No hay sesión de red. La "sesión" es estado en memoria del proceso y no expira por diseño (D-26). Sin token, sin cookie, sin superficie de fijación |
| **V4 Access Control** | **Sí** (D-20) | Cuatro roles fijos, permisos en código. La verificación tiene que ocurrir en la **aplicación**, nunca en la CLI ni en la futura UI |
| **V5 Input Validation** | **Sí** | `pydantic` 2.13.4 para toda entrada externa (config, argumentos de CLI, payloads de PALJET/balanza). Los datos del ERP son entrada no confiable aunque vengan de "adentro" |
| **V6 Cryptography** | **Sí** | `hashlib` de la stdlib para SHA-256, `argon2-cffi` para credenciales. **Cero criptografía propia** |
| **V7 Error Handling & Logging** | **Sí** (NUC-06, D-11) | Bitácora técnica rotativa + bitácora de auditoría encadenada, separadas. Nunca registrar la contraseña ni el hash |
| **V8 Data Protection** | **Sí** | Permisos del directorio de evidencia; anonimización de cassettes en el acto de grabar (D-42) |
| **V12 Files & Resources** | **Sí** | Construcción de rutas desde datos externos; deserialización |
| **V13 API & Web Service** | No | No hay API expuesta en esta fase (CON-01 es Fase 9 y es de solo lectura) |

### Known Threat Patterns

| Patrón | STRIDE | Severidad | Mitigación concreta y verificable |
|--------|--------|-----------|-----------------------------------|
| **Manipulación de la evidencia después de persistida** | Tampering | **Alta** | SHA-256 por imagen + hash de manifiesto + bitácora encadenada (D-08). **Límite honesto: esto es tamper-EVIDENT, no tamper-PROOF.** Quien tenga acceso de escritura al disco de la PC de portería puede reemplazar la foto, recalcular su hash, reescribir la fila y re-encadenar toda la bitácora desde ese punto. La cadena hace que la manipulación exija **rehacer todo el histórico posterior** en vez de editar un archivo, que es una elevación de costo enorme pero no una imposibilidad. Lo único que la vuelve tamper-proof es un ancla externa: replicación a un medio de solo-anexado, sellado de tiempo por un tercero, o publicación periódica del hash de la cabeza de la cadena. **Recomendación: decir esto explícitamente en el material comercial** y dejar el hueco de diseño para el ancla externa. Vender "inalterable" lo que es "detectable" es un riesgo de reputación mayor que la amenaza técnica |
| **Path traversal al construir la ruta de evidencia** | Tampering / Elevation | **Media** | El nombre de archivo se deriva del **hash hexadecimal**, no de datos externos — 64 caracteres de `[0-9a-f]`, imposible de envenenar. Pero la **fecha** que forma el directorio y la **raíz configurable** sí vienen de fuera. Control: `Path(raiz).resolve()` y verificar `destino.resolve().is_relative_to(raiz.resolve())` antes de escribir; validar que la ruta relativa persistida no contenga `..` ni sea absoluta antes de leerla. Verificable con un test que intente persistir `../../windows/system32/x.jpg` |
| **Inyección SQL en la base local** | Tampering | **Baja** | SQLAlchemy 2.0 con `Mapped[]` y `select()` parametriza siempre; el ORM tipado no expone una vía de concatenación accidental. El riesgo real está en `exec_driver_sql` con f-strings. Control: contrato de `import-linter` o regla de Ruff que prohíba f-strings dentro de `exec_driver_sql`/`text()` en `infraestructura/persistencia` |
| **Inyección SQL hacia PALJET** | Tampering | **Media** | Es una base **de otro**, así que el impacto de un error es del cliente. Triple barrera del Patrón 8, más parametrización obligatoria: la guardia de `before_cursor_execute` inspecciona la sentencia, no los parámetros, así que un valor interpolado a mano en el SQL pasaría la barrera. Control: prohibir f-strings en `infraestructura/externos` con la misma regla de arriba |
| **Secretos de PALJET y balanza en la configuración** | Information Disclosure | **Alta** | Contraseña de base de datos o token de API en el archivo de arranque. Controles: (a) el archivo de arranque de D-30 sólo lleva rutas — **las credenciales van en la base, en una tabla aparte**; (b) `structlog` con un procesador que redacta claves cuyo nombre matchee `contraseña|password|token|secret|clave|apikey`, aplicado antes de cualquier handler; (c) test que ejecuta un descubrimiento completo y verifica que la credencial no aparece en la bitácora ni en el payload crudo; (d) el anonimizador de cassettes (D-42) debe correr también sobre las **cabeceras**, no sólo sobre el cuerpo — una `Authorization: Basic …` versionada en git es un incidente |
| **Permisos del directorio de evidencia en Windows** | Tampering / Information Disclosure | **Media** | Por defecto la evidencia hereda los permisos del padre; en una PC de portería con cuenta compartida (D-24 dice que eso es lo normal), cualquier usuario del equipo puede borrarla. Control: al crear la raíz, aplicar una ACL que dé escritura sólo a la cuenta que corre la aplicación y lectura a los demás; verificar al arrancar y **reportarlo en el estado del sistema** en vez de fallar. La mitigación completa (evidencia en un recurso donde el operador no tenga escritura) es una decisión de despliegue de la Fase 11 |
| **Deserialización insegura** | Tampering / RCE | **Media si aparece** | Hoy no hay `pickle` en el stack verificado. Riesgos latentes: usar `pickle` para el payload crudo comprimido, `yaml.load` sin `SafeLoader` si se adoptan cassettes YAML de vcrpy, y `numpy.load(..., allow_pickle=True)`. Controles: contrato de `import-linter` que **prohíbe `pickle` y `shelve` en todo `porteria`**; el payload crudo se persiste como **bytes comprimidos con `zlib`/`gzip` de un JSON**, nunca como objeto serializado; si entran cassettes YAML, `yaml.safe_load` obligatorio |
| **Denegación de servicio por disco lleno** | Denial of Service | **Media** | Es Pitfall 14 de `PITFALLS.md`, asignado a EVI-10 en la Fase 3. Lo que **esta** fase debe dejar listo: que el fallo de escritura sea limpio y no deje `.tmp` acumulados (el `except BaseException: unlink` del Patrón 2) y que la transacción no se confirme si el archivo no se escribió |
| **Contraseña débil en un puesto compartido** | Spoofing | **Media, aceptada** | D-22 fija explícitamente sin complejidad ni caducidad, con la justificación correcta (el papel pegado al monitor). Único control: longitud mínima. **Riesgo residual aceptado y documentado por el usuario.** Recomendación técnica compatible con D-22: contrastar contra una lista corta de contraseñas prohibidas (`portero`, `123456`, `porteria`, el nombre de usuario) — no es una regla de complejidad, es un piso de sensatez, y OWASP lo recomienda por encima de las reglas de composición |
| **Parámetros de Argon2id insuficientes** | Spoofing | **Baja** | `argon2-cffi` 25.1.0 trae por defecto `m=65536 KiB (64 MiB), t=3, p=4`, muy por encima del mínimo de OWASP (`m=19 MiB, t=2, p=1`) `[CITADO: cheatsheetseries.owasp.org]`. Medido: **201 ms por hash** en esta máquina. Controles: usar los defaults del perfil `RFC_9106_LOW_MEMORY`, guardar el hash en formato PHC (los parámetros viajan dentro), y llamar a `check_needs_rehash` en cada verificación exitosa para poder subir los parámetros en el futuro sin pedirle la contraseña a nadie. **Verificar el tiempo en el hardware real de portería**: 64 MiB y 4 hilos en una PC industrial vieja podría pasar de 1 s `[VERIFICADO: defaults y tiempo medidos]` |

---

## Sources

### Primary (HIGH confidence)

- **Ejecución directa en esta máquina** (Windows 11 · Python 3.12.12 · uv 0.11.18) — la fuente más fuerte de este documento:
  - `time.get_clock_info()` + muestreo de granularidad en 3.12 y 3.14
  - `os.replace` / `os.rename` / `os.fsync(dir)` / MAX_PATH / normalización Unicode NFC-NFD
  - SQLite 3.50.4: WAL, `synchronous=FULL`, `foreign_keys`, `busy_timeout` en ruta con espacios y acentos
  - SQLAlchemy 2.0.51: `URL.create`, esquema `Mapped[]` N:M, `before_cursor_execute`, `DateTime(timezone=True)`
  - Alembic 1.18.5: `batch_alter_table`, el choque con `foreign_keys=ON`, preservación de datos, `sqlite3.backup`
  - import-linter 2.13 + grimp 3.15: cuatro vías de evasión, exit codes
  - `uv run --isolated --no-project`: entorno con cero terceros
  - opencv-python-headless 5.0.0.93: backend FFMPEG, `CAP_PROP_POS_MSEC`, slot vs cola durante 20 s cada uno
  - Typer 0.27.0: CLI en español, `rich_utils`, encoding de consola
  - argon2-cffi 25.1.0: defaults, formato PHC, tiempo de hash
  - pip-licenses 5.5.5: inventario de las 35 dependencias transitivas
- **PyPI JSON API** — versiones, licencias, fechas de primera y última publicación, y disponibilidad de ruedas `cp312-win_amd64` / `abi3` de los 26 paquetes evaluados
- `docs.sqlalchemy.org/en/20/dialects/sqlite.html` y `/core/engines.html` — listener `connect`, formato de URL, control transaccional de pysqlite
- `alembic.sqlalchemy.org/en/latest/batch.html` — "move and copy", `render_as_batch`, convención de nombres, desactivación de FK durante batch
- `import-linter.readthedocs.io/en/stable/contract_types/forbidden/` y `/get_started/configure/` — opciones completas del contrato `forbidden`, sintaxis en `pyproject.toml`
- `docs.astral.sh/uv/concepts/projects/dependencies/` — PEP 735, `--only-group`, `--no-default-groups`, `--exact`
- `docs.python.org/3.12/library/time.html` y `/3/library/time.html` — semántica de `monotonic`, `perf_counter`, `get_clock_info`
- `cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html` — Argon2id `m=19456, t=2, p=1` como mínimo

### Secondary (MEDIUM confidence)

- `sqlite.org/pragma.html` — durabilidad de `synchronous=FULL` en WAL frente a corte de energía (consultado vía búsqueda, coherente con la doc oficial)
- `learn.microsoft.com/…/nf-sysinfoapi-gettickcount64` y `/sysinfo/acquiring-high-resolution-time-stamps` — GetTickCount64 avanza durante suspensión, QPC se comporta mal en suspend/resume
- `github.com/untitaker/python-atomicwrites` — `MoveFileEx` no garantizado como atómico en todos los casos
- `vcrpy.readthedocs.io/en/latest/changelog.html` — cambios de 8.0.0, `pytest-recording` como integración recomendada
- `peps.python.org/pep-0418/` — semántica de relojes monotónicos y de rendimiento

### Tertiary (LOW confidence)

- Discusiones de foro sobre degradación de NTFS con >300 000 archivos por directorio — respaldan la justificación de D-03 (carpeta por fecha) pero los números concretos no se verificaron
- Comparativas de blogs sobre Typer/Click/argparse — se usaron sólo como panorama; las licencias y versiones se verificaron aparte contra PyPI

---

## Metadata

**Confidence breakdown:**
- **Standard stack:** HIGH — las 26 versiones se consultaron contra PyPI y las 15 principales se instalaron y ejecutaron en un entorno Python 3.12 real
- **Comportamiento de Windows (relojes, filesystem, MAX_PATH, encoding):** HIGH — todo medido en la plataforma de destino, nada inferido
- **Persistencia y migraciones:** HIGH — WAL, transacción única, N:M, `batch_alter_table` y preservación de datos ejecutados de punta a punta, incluido el modo de fallo
- **Contrato de frescura:** HIGH — medido con y sin la mitigación, con dos órdenes de magnitud de separación entre ambos
- **Prueba de arquitectura:** HIGH — las cuatro vías de evasión probadas contra un paquete real
- **Contratos externos y cassettes:** **MEDIUM** — el diseño de las tres barreras se verificó; **la forma real de PALJET y de la balanza es desconocida** y ése es el límite honesto de esta investigación (Open Questions 1 y 2, supuesto A8)
- **Seguridad:** MEDIUM-HIGH — las amenazas y mitigaciones son sólidas y verificables; el límite tamper-evident vs tamper-proof está declarado explícitamente y es una decisión de producto pendiente
- **CLI:** HIGH — ejecutada en español en una consola de Windows real, con el modo de fallo reproducido

**Research date:** 2026-07-25
**Valid until:** 2026-08-24 (30 días). Se acorta a 7 días para las líneas que dependen de PALJET y de la balanza: apenas haya acceso, el descubrimiento de D-41 puede invalidar supuestos del modelo de datos que esta fase congela.
