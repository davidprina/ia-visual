# Phase 1: Núcleo, evidencia trazable y contratos externos congelados - Context

**Gathered:** 2026-07-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Esta fase entrega la fundación no-retrofiteable del sistema. Desde una orden por línea de comandos sobre un archivo de video, el sistema produce evidencia persistida con huella SHA-256 verificable, en una única transacción atómica, sobre un esquema que ya modela lo incómodo (Viaje↔Remito muchos-a-muchos, peso teórico ausente). Además congela los contratos de PALJET y de la balanza con dobles de prueba, después de un GET real contra cada uno.

**No hay interfaz gráfica en esta fase.** La única superficie de entrada es la línea de comandos. Toda decisión sobre pantallas, layouts o interacción táctil pertenece a las Fases 2 y 3.

**No hay inferencia ni detección en esta fase.** El motor de detección, el proveedor de ejecución y el reconocimiento de patentes son de las Fases 4 y 5.

**Requerimientos cubiertos:** NUC-01, NUC-04, NUC-05, NUC-06, CAP-03, CAP-04, EVI-05, EVI-06, VIA-05, INT-04, INT-05, DIS-05, DIS-06 (13 de 79).

</domain>

<decisions>
## Implementation Decisions

### Evidencia: formato, contenido y almacenamiento

- **D-01:** Las imágenes se persisten en **JPEG con calidad configurable por cámara**, admitiendo configuración sin pérdida donde el detalle lo exija (por ejemplo la cámara de patentes). La calidad es un parámetro por cámara, no una constante del producto.
- **D-02:** Se persiste el **frame limpio**, tal como salió del decodificador. Fecha, patente y cajas de detección se dibujan al visualizar o al exportar, leídas de los metadatos. Nunca se queman datos en el píxel. Motivo: la huella cubre un contenido que el propio sistema nunca alteró, y un cambio futuro del overlay no deja el histórico inconsistente.
- **D-03:** Organización en disco: **`evidencia/AAAA/MM/DD/<sha256>.jpg`**. Carpeta por fecha para navegabilidad humana y para evitar el problema de NTFS con cientos de miles de archivos en un mismo directorio; nombre derivado del contenido para conservar la propiedad anti-manipulación. Se descartó el almacén direccionado por contenido puro: en este dominio la deduplicación rinde prácticamente cero porque cada foto es única.
- **D-04:** Se genera **miniatura en el momento de la ingesta**, guardada como blob pequeño (~15 KB) dentro de SQLite. Motivo: para blobs de ese tamaño SQLite supera al sistema de archivos, y la grilla de consulta de la Fase 9 se pinta con una sola consulta.
- **D-05:** **Metadatos de procedencia amplios y sólo en la base**, nunca embebidos en el archivo: cámara, perfil de flujo, resolución y códec de origen, instante monotónico, instante UTC con su desfasaje, desvío contra el instante objetivo, versión de la aplicación, versión del esquema, y motor con versión de modelo cuando corresponda.
- **D-06:** **Dos raíces de almacenamiento independientes y configurables**: la base en disco local rápido, la evidencia en la ruta o disco que el cliente elija. En la base se persiste **ruta relativa a la raíz de evidencia, nunca absoluta**.
- **D-07:** Si al arrancar la raíz de evidencia no está disponible, la aplicación **arranca degradada**: estado en rojo indicando ruta esperada y encontrada, permite consultar lo ya persistido y reparar la configuración, y **bloquea nuevas capturas** hasta resolver.

### Integridad y cadena de custodia

- **D-08:** La integridad se construye en **tres niveles**: huella SHA-256 por imagen, hash del manifiesto de cada captura (los hashes de sus imágenes más sus metadatos), y **bitácora de auditoría encadenada** donde cada registro incluye el hash del anterior. Detecta edición, ausencia de una foto dentro de una captura y borrado o reordenamiento de registros completos. **El encadenamiento debe arrancar en el registro número uno** — no es retrofiteable.
- **D-09:** Cuando la huella recalculada no coincide, la evidencia se **marca como comprometida y se muestra así** en toda pantalla, listado y exportación, y el hallazgo entra en la bitácora con instante y ruta. Nunca se borra ni se oculta.
- **D-10:** El sistema **nunca borra evidencia por sí solo**. Existe una purga manual por antigüedad que deja **lápida**: fila con hash, motivo, autor e instante, para que la cadena encadenada no se rompa y todo hueco tenga explicación. **La Fase 1 fija el esquema de la lápida y la invariante; la herramienta operable de purga se difiere.**
- **D-11:** La **bitácora técnica** (NUC-06) y la **bitácora de auditoría** son dos cosas separadas: la técnica va a archivos rotativos con nivel configurable y es borrable sin consecuencias; la de auditoría vive en la base, sólo agrega y va encadenada por hash. Motivo: subir el nivel de detalle para depurar no puede inundar la evidencia legal, y rotar archivos no puede borrar la cadena de custodia.

### Atomicidad y durabilidad

- **D-12:** Orden de escritura: **archivo primero** en temporal, sincronizado a disco y renombrado atómicamente a su ruta final; **recién entonces** la transacción de la base confirma fila, manifiesto y outbox juntos. Un corte sólo puede dejar archivos sin fila, nunca filas sin archivo — un archivo huérfano es basura recuperable, una fila huérfana es evidencia rota.
- **D-13:** Al arrancar, los archivos huérfanos se **mueven a cuarentena** con su fecha y quedan listados en el estado del sistema. No se eliminan: un huérfano puede ser justamente la foto del camión del corte de luz. El barrido corre en segundo plano para no demorar el arranque.
- **D-14:** SQLite corre en **modo WAL con sincronización completa** (`synchronous=FULL`) en cada confirmación: la transacción confirmada sobrevive a un corte de energía, no sólo al cierre del proceso. El costo en tiempo es irrelevante frente a la escala de una captura.

### Fuente de video y frescura del frame

- **D-15:** El puerto de fuente de video declara **dos perfiles desde el día uno**: perfil de monitoreo y perfil de evidencia. En la Fase 1 la fuente de archivo devuelve el mismo flujo para ambos. En la Fase 2 el visor consume el sub-stream liviano y la captura toma del main-stream — palanca de mayor impacto y menor costo sobre el consumo de CPU.
- **D-16:** La fuente de archivo soporta **dos modos de reproducción elegibles**: tiempo real (respeta la marca temporal de cada fotograma, necesario para verificar el contrato de frescura y la latencia con consumidor lento) y velocidad máxima (para pruebas deterministas en integración continua).
- **D-17:** Métricas por fuente **en memoria** — antigüedad del frame, frames descartados, fps efectivos, reconexiones — consultables mediante una orden de la línea de comandos, y más adelante desde el panel de estado de la interfaz. Sin escritura en el camino crítico.

### Identidad, autoría y roles

- **D-18:** **Hay usuarios con contraseña en v1.** *(Decisión del usuario por encima de la recomendación de perfiles sin credencial. Es alcance nuevo: no se deriva de ningún requerimiento v1 — las Fases 5, 7 y 9 piden registrar el operador, no autenticarlo. Se documenta como tal.)*
- **D-19:** De ese subsistema, la Fase 1 entrega **sólo el modelo de usuarios, el almacenamiento seguro de la credencial, la columna de autor en toda fila auditable y el actor en la bitácora encadenada**. El alta y la verificación se ejercitan por línea de comandos. La pantalla de inicio de sesión llega con la interfaz, en la Fase 2 o 3.
- **D-20:** **Cuatro roles fijos del negocio**: Portero, Logística, Compras y Administración — los mismos cuatro usuarios que identifica PROJECT.md. Permisos definidos en código, no configurables. Sin el rol de Compras en el esquema, la prueba automática de solo lectura que exige la Fase 9 no tiene contra qué correr.
- **D-21:** **La captura nunca se bloquea por falta de sesión.** Si no hay sesión iniciada, la evidencia se registra con autor "no identificado", el hecho queda marcado en el registro y se contabiliza en el panel de calidad. Misma regla que rige la captura parcial: registrar lo incompleto en lugar de impedirlo.
- **D-22:** Credenciales protegidas con **Argon2id** con parámetros modernos y sal por usuario. Única exigencia de política: longitud mínima razonable. **Sin caducidad forzada ni reglas de complejidad** — en un puesto compartido esas reglas producen la contraseña escrita en un papel pegado al monitor.
- **D-23:** **No existe ninguna credencial por defecto en el producto.** Un asistente de primer arranque crea el administrador inicial junto con las rutas de datos. En la Fase 1 el asistente es una orden de línea de comandos; en la Fase 11 se integra al instalador.
- **D-24:** **Identidad propia, independiente del usuario de Windows.** El usuario de Windows se registra sólo como dato de diagnóstico, sin valor de autoría. Motivo: en una portería la PC suele tener una única cuenta compartida por todos los turnos.
- **D-25:** Un usuario que ya firmó evidencia **no se elimina, se desactiva**: no puede volver a iniciar sesión y todas sus firmas anteriores conservan su nombre. La baja queda registrada con autor e instante. Es la única opción coherente con una bitácora encadenada.
- **D-26:** **La sesión no se cierra sola.** Cambio de operador explícito, con el nombre del operador activo siempre visible en pantalla. Sin expiración por inactividad ni por turno — una expiración justo cuando el camión está sobre la balanza produce evidencia firmada como no identificada en vez de firmada bien.

### Esquema de datos

- **D-27:** La Fase 1 modela **sólo lo no retrofiteable, completo y ejercitado**: captura, evidencia, manifiesto, bitácora encadenada, usuarios y roles, viaje↔remito muchos a muchos, artículos con peso teórico nulable, payload crudo externo y outbox. Ingresos de proveedor, cronómetro de espera, órdenes de compra y excepciones llegan en su fase con su migración.
- **D-28:** **Una captura puede existir sin viaje ni movimiento asociado.** Nace autónoma, con su evidencia y su huella, y se vincula después. Lo exige la Fase 1 (la orden sobre un archivo no tiene viaje) y lo exige la operación real: el portero saca la foto cuando el camión está delante y busca el viaje después.
- **D-29:** **Doble identificador**: opaco único universal para uso interno (nunca colisiona si hay un segundo puesto o si se importa evidencia de otra instalación), más un número legible por año del estilo `2026-001842` para que el operador y Administración puedan referenciarlo por teléfono.
- **D-30:** Configuración en **dos capas**: archivo mínimo de arranque con lo imprescindible para abrir (ruta de la base y raíz de evidencia), escrito por el instalador y el asistente de primer arranque; **todo lo demás en la base**, editable desde la interfaz, incluido en la copia de seguridad y con registro de quién lo cambió y cuándo. Es el requisito de auditoría aplicado también a la configuración.
- **D-31:** El **peso teórico ausente** se modela como peso nulable por artículo. El estado del remito (completo o incompleto) **no se persiste: se deriva** de si algún artículo carece de peso. Así estado y datos no pueden contradecirse, y el reporte de artículos sin peso maestro que pide la Fase 7 sale de una consulta directa.
- **D-32:** **Idioma del código: dominio en español** (`Viaje`, `Remito`, `CapturaDeControl`, `PesoTeorico`), **infraestructura y bibliotecas en inglés**. Coincide con cómo ya está escrita la investigación de arquitectura. Cuando el portero dice "remito" y el código dice "remito" desaparece toda una capa de traducción donde se cuelan los errores de interpretación.

### Migraciones y versionado

- **D-33:** Cada migración entra con una **prueba automática que siembra, migra y compara**: se crea la base en la versión anterior, se la siembra con datos representativos incluidos los casos feos (viaje con tres remitos, remito compartido, peso nulo, rutas con acentos), se aplica la migración y se verifica fila por fila. El cliente actualiza sobre años de evidencia y no hay segunda oportunidad.
- **D-34:** Además, **copia de seguridad automática de la base antes de cada migración**. Son defensas de capas distintas: la prueba evita que una migración rota llegue al cliente, la copia es la red por si igual llega. Se conservan las últimas copias y se informa cuánto ocupan.
- **D-35:** **Versión de producto y versión de esquema separadas, con compatibilidad declarada.** Al arrancar la aplicación compara: si la base es más vieja, migra; si la base es **más nueva** que la aplicación — alguien instaló una versión anterior sobre datos ya migrados — se niega a abrir con un mensaje claro en lugar de corromper. Ese caso ocurre en campo cuando un cliente reinstala desde un instalador guardado.
- **D-36:** **Nombre comercial diferido.** Se usa un identificador técnico neutro (`porteria`) para el paquete, la orden de consola y la carpeta de datos; el nombre comercial se define antes del instalador de la Fase 11. *(Riesgo asumido: la carpeta de datos y el nombre del paquete quedan con el provisional o hay que renombrarlos, lo que toca instalaciones ya desplegadas.)*

### Tiempo y sincronía

- **D-37:** La fecha que agrupa evidencia y reportes es la **zona local del equipo**. *(Decisión del usuario. Costo señalado y aceptado: si alguien cambia la zona horaria de Windows, el histórico se reagrupa distinto y los reportes de meses anteriores dejan de coincidir con los ya emitidos.)* En la base se sigue persistiendo el instante UTC junto con su desfasaje.
- **D-38:** Un día corta a **medianoche local**. El turno noche queda partido en dos días, igual que en la contabilidad y en el ERP. Sin parámetros de jornada ni modelado de turnos.
- **D-39:** **Ventana de aceptación por defecto: ±150 ms**, tomada de la investigación de arquitectura y **marcada explícitamente como no validada** con el cliente ni medida en campo. Medirla con cámaras reales queda agendado. Lo determinante no es acertar el número ahora sino que el desvío real quede persistido para poder revisarlo con datos.
- **D-40:** El parámetro de ventana **sólo lo cambia el rol de Administración**, el cambio queda en la bitácora con autor e instante, y **cada captura guarda cuál era la ventana vigente en el momento en que se hizo**. Así nadie puede ensanchar el criterio y hacer que capturas viejas pasen retroactivamente de estimadas a sincronizadas.

### Descubrimiento de contratos externos

- **D-41:** El descubrimiento **recorre todo lo que el dominio va a necesitar**: chofer, camión, transportista, remito con sus artículos y pesos teóricos, y la lectura de peso con su estado de estabilidad. Cada respuesta se guarda como cassette. El objetivo es responder ahora si el modelo que se está congelando encaja con lo que esos sistemas devuelven de verdad.
- **D-42:** Los cassettes se **anonimizan en el mismo acto de grabar**: nombres, documentos y patentes reemplazados por valores ficticios coherentes, **conservando estructura, tipos, largos, nulos y rarezas de formato** — que es lo único que el cassette necesita preservar. El repositorio de un producto comercial no puede llevar datos reales de choferes de un cliente, y el historial de git no se borra.
- **D-43:** Si no hay acceso a PALJET o a la balanza al ejecutar la fase, **la fase se completa igual** con todo lo que no depende de terceros, y el descubrimiento faltante queda como **deuda bloqueante registrada con responsable y fecha**, visible en el estado del proyecto, para ejecutar apenas haya acceso.
- **D-44:** **PALJET se consulta por los dos caminos según el dato**: interfaz de programación donde exista, consulta directa con SELECT donde la interfaz no exponga lo que el dominio necesita. *(Decisión del usuario. El descubrimiento debe documentar qué dato viene por cada camino, y la barrera de solo lectura debe cubrir ambos.)*
- **D-45:** **Geomov:** se declara el puerto de telemetría con la **carga manual como implementación de referencia y camino principal**, no como parche. Una eventual interfaz será una segunda implementación del mismo puerto. El modelo de viaje reserva lugar para kilómetros y horarios de salida y regreso.
- **D-46:** El **payload crudo** (INT-05) se guarda íntegro y comprimido, con la petición, el instante, el código de respuesta y la duración. Purga por antigüedad configurable y **separada de la política de evidencia** — un payload de hace dos años ya no sirve, una foto sí.
- **D-47:** La regla de solo lectura se garantiza con **doble barrera más prueba**: un cliente compartido que no expone más verbos que GET, HEAD y OPTIONS; una conexión de base que rechaza toda sentencia que no empiece por SELECT o WITH; y encima la prueba de arquitectura que ejercita todos los adaptadores y **falla la construcción** ante un verbo o sentencia prohibida. Escribir se vuelve algo que hay que hacer a propósito rompiendo dos capas.

### Dobles de prueba y modo demostración

- **D-48:** Los dobles de prueba con datos deliberadamente feos que exige NUC-04 **son también el modo demostración del producto**: los falsos en memoria se activan desde un modo demo que permite mostrar el sistema sin balanza, sin ERP y sin cámaras. Como se ejercitan en cada corrida de pruebas, nunca se pudren.

### Línea de comandos

- **D-49:** La línea de comandos es una **herramienta de diagnóstico permanente que viaja en el producto vendido**, no un andamio desechable: verificar huellas, volcar métricas, probar una fuente, crear el administrador inicial, exportar el estado del sistema, aplicar migraciones. En una planta sin área de sistemas, poder decir "escribí esto y leeme lo que sale" es la diferencia entre resolver por teléfono y viajar.
- **D-50:** **Todo en español, incluidas las órdenes y las opciones.** *(Decisión del usuario por encima de la convención de consola en inglés. Consecuencia a manejar: las órdenes no se pegan desde documentación de terceros y conviven con nombres de infraestructura en inglés según D-32.)*
- **D-51:** Salida **legible por personas por defecto** (español claro, indicando qué hacer, según UI-05) y **estructurada bajo bandera** para que la consuman las pruebas automatizadas, el instalador y herramientas futuras. Un solo comando sirve a los dos públicos y las pruebas no parsean texto libre.

### Integración continua y calidad

- **D-52:** La prueba de aislamiento del dominio corre en un **entorno separado que instala únicamente las dependencias que el dominio declara** — sin opencv, sin onnxruntime, sin el toolkit de interfaz — e importa el paquete completo allí. Es una prueba real, no una simulación: nada que se pueda sortear con un import diferido dentro de una función.
- **D-53:** **Bloquean la fusión** las pruebas rápidas: dominio, contrato, arquitectura, solo lectura y migración. Las de larga duración (los diez minutos de frescura, las ocho horas de la Fase 2) corren en **tanda programada periódica** y su falla abre un asunto, no traba la fusión. Una compuerta lenta es una compuerta que se termina salteando.
- **D-54:** La compuerta corre **sobre Windows como única plataforma**. Rutas con espacios y acentos, nombres de usuario con ñ, comportamiento del sistema de archivos y renombrado atómico se comportan distinto ahí, y el criterio de éxito 6 exige demostrarlo en la plataforma de destino.
- **D-55:** **Inventario de licencias de terceros desde el día uno**, generado a partir de las dependencias resueltas y verificado en cada fusión. La compuerta **falla ante una licencia contagiosa (AGPL, GPL) o no identificable**. El proyecto ya tiene prohibiciones explícitas — Ultralytics, YOLOv9, YOLO-NAS — y detectarlas cuando entran cuesta segundos, mientras que descubrirlas enterradas en una dependencia transitiva antes de vender es un incendio legal.
- **D-56:** **Pruebas antes del código para lo que la fase promete demostrar** (los seis criterios de éxito son afirmaciones verificables y se escriben primero, fallando), **y después del código para el andamiaje y los adaptadores** contra bibliotecas de terceros, donde escribir la prueba primero verifica lo que uno imaginaba y no lo que la biblioteca hace.
- **D-57:** **Cobertura medida y visible, nunca como compuerta.** Lo que bloquea es que existan y pasen las pruebas que demuestran los criterios de éxito. Un porcentaje obligatorio empuja a escribir pruebas que recorren código sin verificar nada.

### Videos de referencia y datos de prueba

- **D-58:** Los videos de referencia se **filman en la portería real**, con acuerdo escrito del cliente sobre el uso para desarrollo, guardados fuera del repositorio público y no distribuidos con el producto. Nada sustituye al video real: la luz, el contraluz, la suciedad de las patentes y cómo maniobra un camión no se simulan.
- **D-59:** Del material real se extraen **recortes cortos y livianos** — pocos segundos, recortados, a la resolución justa para lo que cada prueba verifica — y **ésos sí se versionan** en el repositorio. Los originales completos quedan en un almacén aparte acordado con el cliente. Así la integración continua es reproducible por cualquiera que clone, y el material sensible no se multiplica en cada copia.

### Claude's Discretion

El usuario no delegó ninguna decisión con un "vos decidís" explícito. Quedan a criterio de investigación y planificación, por ser materia técnica y no de negocio:

- Estructura concreta de paquetes y módulos dentro de los límites que fija `ARCHITECTURE.md`.
- Bibliotecas concretas para cada responsabilidad, dentro de lo ya fijado en el stack (por ejemplo qué implementación de Argon2id, qué herramienta de inventario de licencias, qué marco de línea de comandos).
- Forma exacta de las tablas, índices y nombres de columnas, respetando D-27 a D-32.
- División de la fase en planes y su orden de ejecución.
- Parámetros concretos de Argon2id (memoria, iteraciones, paralelismo) según guía vigente.
- Mecanismo concreto de encadenamiento de la bitácora (qué campos entran en el hash y en qué orden), siempre que cumpla D-08.
- Nivel de compresión y formato concreto del payload crudo persistido.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Contexto y alcance del proyecto
- `.planning/PROJECT.md` — Core Value, restricciones, tabla de Key Decisions, Out of Scope. Fija que la aplicación sólo lee de sistemas externos y escribe únicamente en su persistencia local.
- `.planning/REQUIREMENTS.md` — Los 79 requerimientos v1 con sus identificadores. Los 13 de esta fase: NUC-01, NUC-04, NUC-05, NUC-06, CAP-03, CAP-04, EVI-05, EVI-06, VIA-05, INT-04, INT-05, DIS-05, DIS-06.
- `.planning/ROADMAP.md` §"Phase 1" — Goal, los seis criterios de éxito verificables, y la tabla de decisiones no retrofiteables con la fase que fija cada una.
- `Requerimientos App logista.docx` — Documento fuente del cliente. Define los dos flujos operativos y las reglas de negocio. Ver PROJECT.md §Context para las correcciones detectadas en el relevamiento (el ERP es PALJET, no Calipso/Actual).

### Arquitectura — de lectura obligatoria antes de planificar
- `.planning/research/ARCHITECTURE.md` §"Regla rectora" — La distinción entre zona caliente y zona fría, y la prueba objetiva del límite del dominio que sostiene el criterio de éxito 1.
- `.planning/research/ARCHITECTURE.md` §"Recommended Project Structure" — Estructura de paquetes con los límites de importación. Ya está escrita con el dominio en español, coherente con D-32.
- `.planning/research/ARCHITECTURE.md` §"Pattern 3" — Las dos rutas con disciplinas opuestas: slot de último valor para la ruta viva, cola acotada sin descarte para la ruta de evidencia. Base del contrato de frescura de D-15 a D-17.
- `.planning/research/ARCHITECTURE.md` §"Pattern 4" — Captura sincronizada por ventana mirando hacia atrás, resultado parcial de primera clase, y los tres relojes sin mezclar. Base de D-37 a D-40.
- `.planning/research/ARCHITECTURE.md` §"Pattern 6" — Eventos en tres niveles y outbox transaccional sobre SQLite. Base de D-12.
- `.planning/research/ARCHITECTURE.md` §"Pattern 7" — ACL solo-lectura con gemelo falso obligatorio, jerarquía de dobles de prueba y suite de contrato compartida. Base de D-41 a D-48.
- `.planning/research/ARCHITECTURE.md` §"Flujo 3" y §"Anti-Patterns" — Persistencia de evidencia y los trece antipatrones a evitar, incluidos "imágenes como BLOB", "sincronizar con el reloj de pared" y "diseñar los puertos copiando el esquema del ERP".
- `.planning/research/ARCHITECTURE.md` §"Orden de Construcción Recomendado" filas 0 a 2 — Justifica por qué el esqueleto, el puerto de fuente con adaptador de archivo y la captura con almacén van primero.

### Pitfalls que esta fase ataca
- `.planning/research/PITFALLS.md` §"Pitfall 1" — La foto no es del instante del botón: latencia acumulada de buffer RTSP.
- `.planning/research/PITFALLS.md` §"Pitfall 2" — "Sincronizado" significa sólo "pedido al mismo tiempo": modelo de reloj monotónico/UTC y desvío persistido.
- `.planning/research/PITFALLS.md` §"Pitfall 14" — El disco se llena y el sistema deja de registrar evidencia; escritura atómica y hash.
- `.planning/research/PITFALLS.md` §"Pitfall 16" — Dejar las integraciones para el final invalida el modelo de datos. Es la justificación entera del descubrimiento temprano de D-41 a D-45.
- `.planning/research/PITFALLS.md` §"Pitfall 18" — Corte de energía y suspensión del equipo; persistencia transaccional con WAL. Base de D-12 a D-14.

### Stack y restricciones de licencia
- `.planning/research/STACK.md` — Las siete decisiones de stack con versiones verificadas. Relevante para esta fase: Python 3.12, SQLite + SQLAlchemy 2.0.51 + Alembic, PyAV para RTSP, filesystem con hash y no BLOBs, `uv` con lockfile determinista.
- `.planning/research/STACK.md` §"What NOT to Use" — Prohibiciones explícitas que la compuerta de D-55 debe hacer cumplir: Ultralytics en cualquier forma, YOLOv9, YOLOv7, YOLO-NAS, RF-DETR-XL/2XL, PyQt6, `opencv-python` no headless junto a PySide6.
- `.planning/research/SUMMARY.md` — Síntesis de la investigación de dominio.
- `CLAUDE.md` — Instrucciones del proyecto. Contiene la restricción global de solo lectura sobre APIs y bases de datos externas, sin excepciones.

### A crear en esta fase (aún no existen)
- Documento de contratos externos congelados con los cassettes anonimizados de PALJET y balanza, y el registro de qué dato viene por interfaz de programación y cuál por consulta directa (D-41, D-42, D-44).
- Registro de la deuda de descubrimiento si no hubiera acceso a alguno de los dos sistemas, con responsable y fecha (D-43).

</canonical_refs>

<code_context>
## Existing Code Insights

**No hay código todavía.** El repositorio contiene únicamente `CLAUDE.md`, el documento fuente `Requerimientos App logista.docx` y el directorio `.planning/`. Esta fase escribe la primera línea de código del proyecto.

### Reusable Assets
Ninguno. Todo se construye desde cero.

### Established Patterns
Los patrones no vienen del código sino de `.planning/research/ARCHITECTURE.md`, que los define con nivel de detalle de implementación. Los que esta fase debe establecer como precedente para las once fases siguientes:

- **Dependencias apuntando hacia adentro**: infraestructura → aplicación → dominio. El dominio no importa nada de las capas externas.
- **Puertos declarados por la aplicación, no por el proveedor**: el puerto lo dicta el negocio ("necesito el peso teórico del viaje"), no el ERP ("PALJET devuelve `ART_PES_UNI`").
- **`Resultado[T] = Ok | NoDisponible | Degradado`** en todos los puertos externos, para que el dominio pueda operar con datos ausentes sin `try/except` con semántica de negocio.
- **Agregados que acumulan eventos, no que los publican**; el caso de uso persiste estado, evidencia y outbox en una única transacción.
- **Contrato núcleo↔UI serializable y versionado desde el primer mensaje**, aunque el transporte de v1 sea en memoria. El directorio de transporte IPC existe vacío como recordatorio.

### Integration Points
- **Salida hacia el sistema de archivos**: almacén de evidencia con escritura atómica (D-12) y cuarentena de huérfanos (D-13).
- **Salida hacia SQLite**: repositorios, unidad de trabajo, outbox, migraciones Alembic, bitácora encadenada.
- **Salida hacia sistemas externos**: cliente compartido con doble barrera de solo lectura (D-47), usado por los adaptadores de PALJET y balanza.
- **Entrada por línea de comandos**: única superficie de esta fase (D-49 a D-51), que sobrevive como herramienta de diagnóstico del producto.
- **Hueco reservado para la interfaz**: el puerto de entrada y el canal de eventos se declaran ahora aunque la interfaz llegue en la Fase 2.

</code_context>

<specifics>
## Specific Ideas

- **"El riesgo no es integrar tarde, es enterarse tarde"** — la frase del roadmap que justifica que el descubrimiento de contratos ocurra en la Fase 1 aunque las integraciones se construyan en la Fase 10. El descubrimiento debe alcanzar para responder si el modelo que se congela encaja con la realidad, no sólo para confirmar que hay conectividad.
- **"Registrar lo incompleto en lugar de impedirlo"** — regla transversal que el usuario aplicó de forma consistente en tres decisiones distintas: captura parcial, evidencia comprometida (D-09) y captura sin sesión (D-21). El sistema nunca frena la operación para proteger su propia prolijidad; deja constancia y sigue.
- **Un archivo huérfano es basura recuperable, una fila huérfana es evidencia rota** — el criterio que ordena la escritura en D-12 y que explica por qué la cuarentena de D-13 no borra.
- **La lápida** — nombre que quedó para la fila que sobrevive al borrado manual de una imagen, con hash, motivo, autor e instante (D-10).
- El usuario eligió consistentemente la opción recomendada salvo en cuatro puntos, todos deliberados y documentados como suyos: usuarios con contraseña (D-18), PALJET por los dos caminos (D-44), zona local del equipo (D-37) y línea de comandos íntegramente en español (D-50).

</specifics>

<deferred>
## Deferred Ideas

### Pertenecen a fases posteriores del roadmap
- **Pantalla de inicio de sesión y de cambio de operador** — la Fase 1 deja el modelo y la credencial; la interfaz llega en la Fase 2 o 3.
- **Gestión completa de usuarios desde la interfaz** (alta, baja, cambio de contraseña, recuperación) — fase de interfaz.
- **Herramienta operable de purga manual de evidencia por antigüedad** — la Fase 1 fija el esquema de lápida y la invariante de no borrado automático; la herramienta con su pantalla corresponde a la fase de consulta o de empaquetado.
- **Política concreta de retención**: cuántos meses se conservan imágenes y payloads. El mecanismo se fija ahora, el número se decide antes del instalador (coincide con el gap 5 de `ARCHITECTURE.md`).
- **Medición en campo de la ventana de sincronía** — el ±150 ms de D-39 queda marcado como no validado; medirlo con cámaras reales es tarea de la Fase 2 o 3, y volver a validarlo al cerrar la compra de hardware.
- **Nombre comercial del producto** — a definir antes del instalador de la Fase 11 (D-36).

### Capacidades nuevas, fuera del alcance de v1 tal como está definido
- **Réplica de la evidencia a un recurso de red o NAS de la planta** — capacidad con su propio manejo de errores y reintentos. `STACK.md` la contempla como extensión sin cambiar el modelo.
- **Inicio de sesión único contra dominio corporativo** — argumento de venta en plantas grandes, pero es una capacidad entera con su propia infraestructura de pruebas.
- **Política corporativa de contraseñas** (complejidad, caducidad, historial, bloqueo por intentos) — evaluar sólo si un pliego de venta concreto lo exige.
- **Muestreo periódico de métricas de fuente a la base** para diagnóstico retrospectivo ("la cámara lateral estuvo degradada toda la mañana del martes") — evaluar cuando exista el panel de estado.
- **Copia de seguridad periódica programada de la base**, más allá de la previa a cada migración — corresponde a la fase de resiliencia en planta.
- **Modelado de turnos y horarios de la planta** — apareció dos veces (límite del día y cierre de sesión) y se descartó las dos: no está en ningún requerimiento y se rompe cuando alguien cubre a un compañero. Si el panel de calidad por turno de la Fase 7 lo termina exigiendo, se reevalúa ahí.
- **Averiguar formalmente si Geomov expone alguna interfaz** — el documento fuente pide evaluar su factibilidad. Se optó por declarar el puerto con carga manual y no bloquear; la gestión con el tercero queda como tarea comercial sin fecha.

</deferred>

---

*Phase: 1-Núcleo, evidencia trazable y contratos externos congelados*
*Context gathered: 2026-07-25*
