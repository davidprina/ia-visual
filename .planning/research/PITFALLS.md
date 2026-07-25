# Pitfalls Research

**Domain:** Aplicación de escritorio de control de portería con visión artificial (captura multi-cámara RTSP/USB, YOLO sobre ONNX Runtime, LPR de patentes argentinas, evidencia auditable, integraciones de solo lectura con ERP / balanza / rastreo satelital)
**Researched:** 2026-07-24
**Confidence:** HIGH en RTSP/OpenCV, ONNX Runtime, pre/postprocesamiento YOLO y empaquetado (issues y documentación oficial reproducibles). MEDIUM en LPR en producción (papers y guías de fabricante, no post-mortems del caso argentino) y en contexto industrial/operativo (evidencia sectorial, no post-mortems públicos de este proyecto exacto).

**Nomenclatura de fases usada en este documento** (propuesta para el roadmap, alineada con los bloques de PROJECT.md):

| Etiqueta | Fase sugerida |
|----------|---------------|
| **F1** | Núcleo headless: puerto de fuente de video, reloj, persistencia local |
| **F2** | Captura multi-cámara sincronizada + evidencia con metadatos |
| **F3** | Motor de inferencia (ONNX Runtime + YOLO) y motor OpenCV clásico |
| **F4** | LPR de patentes |
| **F5** | UI de portería y flujo operativo (egreso / ingreso / SLA) |
| **F6** | Empaquetado, instalador, despliegue en planta |
| **F7** | Integraciones externas (PALJET, balanza, Geomov) |

---

## Critical Pitfalls

### Pitfall 1: La foto no es del instante del botón (latencia acumulada de buffer RTSP)

**What goes wrong:**
El portero presiona "capturar" y el sistema guarda un frame que la cámara emitió hace 3, 10 o 40 segundos. El camión que aparece en la evidencia puede ser el anterior, o la carga puede estar en un estado distinto. La evidencia queda inutilizable para auditar y —peor— parece correcta: la imagen es nítida, tiene timestamp y está asociada al viaje.

**Why it happens:**
`cv2.VideoCapture` con backend FFMPEG mantiene un buffer interno. Si el hilo llama a `read()` más lento que el framerate del stream (por ejemplo porque entre lecturas corre inferencia YOLO), los frames se acumulan y `read()` empieza a devolver material viejo; la latencia crece monótonamente y no se recupera sola. Es el problema más reportado del ecosistema OpenCV+RTSP. Además `CAP_PROP_BUFFERSIZE` **no funciona con el backend FFMPEG** (devuelve `False` y se ignora), así que la "solución" que la mayoría copia de StackOverflow no hace nada en RTSP.

**How to avoid:**
- Patrón productor/consumidor obligatorio: un hilo dedicado por cámara que hace `read()` en bucle cerrado a full framerate y **descarta**, conservando solo el último frame en un slot de tamaño 1 protegido por lock. La captura y la inferencia nunca comparten hilo.
- Nunca usar una cola sin límite entre lector y consumidor (ver Pitfall 13). El único tamaño de buffer aceptable es 1.
- Si se usa GStreamer como backend alternativo: `appsink max-buffers=1 drop=true`, `latency=0`, `drop-on-latency=true`.
- Definir "frame fresco" como contrato explícito del puerto de fuente de video: cada frame entregado lleva su `monotonic_ts` de recepción, y la captura rechaza (o marca) frames con antigüedad mayor a un umbral configurable (p. ej. 500 ms).

**Warning signs:**
- Test manual con un cronómetro digital frente a la cámara: la diferencia entre el reloj filmado y el reloj del sistema **crece** a lo largo de una sesión de 10 minutos. Si crece, hay acumulación; si es constante, es solo latencia de red/decodificación.
- Uso de CPU alto y estable pero FPS mostrados por debajo del framerate nominal del stream.
- El delay empeora cuando se activa el motor de IA y mejora al desactivarlo.

**Phase to address:** F1 (contrato del puerto) y F2 (verificación con cronómetro filmado como criterio de aceptación).

---

### Pitfall 2: "Sincronizado" significa solo "pedido al mismo tiempo"

**What goes wrong:**
Se implementa la captura sincronizada como "un `for` sobre las cámaras llamando a `get_frame()`", se guardan tres imágenes con el mismo timestamp del sistema, y se declara resuelto el Core Value. En realidad cada imagen puede corresponder a instantes de escena distintos (por latencia de red, GOP/keyframe, decodificación y buffering de cada cámara). En un camión detenido nadie lo nota; en el momento en que una persona cruza el cuadro o se mueve la carga, la evidencia se contradice a sí misma.

**Why it happens:**
Cada stream RTSP tiene su propia latencia y su propio drift. Los relojes internos de las cámaras IP derivan por desviaciones de frecuencia de sus osciladores; el error se acumula linealmente. Aun con NTP correcto queda un error de 1–2 ms en el cliente, y en cámaras IP mal configuradas la desviación es de minutos. La literatura forense es explícita: timestamps inconsistentes entre cámaras deterioran o anulan el valor probatorio del material.

**How to avoid:**
- Un solo reloj de referencia: el del proceso de captura (monotónico para deltas, UTC para persistir). **Nunca** confiar en el timestamp que reporta la cámara para correlacionar.
- Cada evidencia guarda: `capture_request_id`, `utc_at_request`, `monotonic_at_request`, `monotonic_at_frame_received` por cámara, y el **skew** resultante (`t_frame_i - t_request`).
- Definir y persistir una ventana de sincronía aceptable (p. ej. ±300 ms). Si una cámara queda fuera, la captura se marca como *degradada* y la UI lo dice; no se descarta silenciosamente.
- Forzar NTP en las cámaras contra el mismo servidor que la PC de portería, y documentarlo en el manual de instalación (es requisito de despliegue, no de código).
- Sincronizar sobre keyframes cuando sea posible; conocer el GOP configurado en cada cámara (un GOP largo implica que el primer frame tras conectar puede tardar segundos).

**Warning signs:**
- El skew registrado varía entre capturas o crece con el tiempo de sesión.
- Filmar un cronómetro único con las dos cámaras a la vez y comparar los frames capturados: si difieren en más de la ventana declarada, la sincronía es nominal, no real.
- Las cámaras muestran horas distintas en su OSD.

**Phase to address:** F1 (modelo de reloj y metadatos) y F2 (criterio de aceptación medible con cronómetro filmado). Es el pitfall que define si el Core Value se cumple.

---

### Pitfall 3: El stream se congela sin lanzar ningún error

**What goes wrong:**
La cámara se reinicia, el switch parpadea o el cable se afloja. `cap.isOpened()` sigue devolviendo `True`, no se lanza excepción, y `read()` devuelve el último frame válido para siempre — o bloquea indefinidamente sin timeout. El sistema sigue "funcionando" y sigue guardando evidencia: la misma imagen congelada, con timestamps nuevos. Es el peor fallo posible para un sistema de auditoría, porque produce evidencia falsa con apariencia legítima.

**Why it happens:**
No existe manejo de error del lado de OpenCV para este caso; es un comportamiento documentado en issues abiertos de OpenCV (`isOpened()` True + `read()` colgado tras recuperación de la cámara, con consumo anómalo de CPU). El desarrollador asume que "si falla, tira excepción".

**How to avoid:**
- **Watchdog por cámara**: un timer que registra `last_frame_time`; si no llegan frames dentro de `watchdog_timeout` (5–10 s es el rango habitual), el stream se declara muerto, se cierra el `VideoCapture` y se reconecta. No basta con confiar en el valor de retorno de `read()`.
- Timeouts de FFMPEG explícitos vía `OPENCV_FFMPEG_CAPTURE_OPTIONS` (`stimeout`/`timeout`, `rw_timeout`) para que `read()` no pueda bloquear sin límite.
- **Detector de frame congelado**: hash o diferencia media entre frames consecutivos. N segundos de frames idénticos bit a bit en una escena exterior = stream congelado, aunque lleguen frames.
- Estado explícito por cámara en el dominio: `CONECTANDO | VIVA | DEGRADADA | MUERTA`, con antigüedad del último frame. La UI lo muestra siempre, no solo en la pantalla de configuración.
- **Regla dura**: si una cámara no está `VIVA` al momento de la captura, la evidencia se marca como incompleta y el registro lo refleja. Nunca se guarda un frame stale como si fuera actual.

**Warning signs:**
- En pruebas: desenchufar el cable de red de una cámara con el sistema corriendo. Si la UI no cambia de estado en menos de 15 s, el watchdog no existe o no funciona.
- Evidencias consecutivas con imágenes idénticas pixel a pixel y timestamps distintos.

**Phase to address:** F2. Debe ser criterio de aceptación explícito ("prueba del cable desenchufado").

---

### Pitfall 4: La reconexión filtra hilos, handles y memoria

**What goes wrong:**
Tras horas de operación con una red inestable, la aplicación acumula cientos de hilos zombis y cientos de MB de RSS; termina degradándose hasta que el portero la reinicia todos los días "porque se pone lenta". En el peor caso el proceso muere en medio de una captura.

**Why it happens:**
El patrón ingenuo de reconexión crea un nuevo `VideoCapture` y un nuevo hilo lector sin garantizar que el anterior terminó y liberó. Si el hilo viejo está bloqueado dentro de `read()` (Pitfall 3), nunca sale y nunca se libera el contexto FFMPEG asociado. Cada caída de red suma una fuga.

**How to avoid:**
- Un solo objeto "sesión de cámara" con ciclo de vida explícito: `start()` / `stop()` idempotentes; `stop()` espera con `join(timeout)` y **registra** si el hilo no terminó.
- Backoff exponencial con tope (1s → 2s → 4s → ... → 30s) y jitter, no reintento en bucle apretado — el reintento agresivo es lo que dispara el 20% de CPU reportado en el issue de OpenCV.
- Prohibir la creación de un nuevo `VideoCapture` mientras el anterior no se marcó como liberado; usar una máquina de estados, no flags booleanos.
- Test de resistencia obligatorio: 8–24 h con un script que corta y restaura la interfaz de red cada pocos minutos. Graficar RSS, número de hilos y handles del proceso. La curva debe ser plana.

**Warning signs:**
- Contador de hilos del proceso creciente en el Administrador de tareas / Process Explorer.
- RSS que sube escalonadamente y coincide con eventos de reconexión en el log.
- El log muestra "reconectando" con más frecuencia de la que hubo caídas reales.

**Phase to address:** F2, con el test de resistencia como gate de salida de la fase.

---

### Pitfall 5: El proveedor de ejecución cae a CPU en silencio

**What goes wrong:**
Se entrega el sistema a un cliente con GPU, se factura como "acelerado por GPU", y en realidad corre en CPU. Nadie se entera hasta que alguien mide. En el caso opuesto: en la PC de desarrollo funcionaba con GPU y en la PC de portería la inferencia tarda 10x más, y el sistema "va lento" sin causa aparente.

**Why it happens:**
ONNX Runtime, si el `CUDAExecutionProvider` no puede inicializarse (DLL faltante, versión de CUDA/cuDNN incompatible con el build de `onnxruntime-gpu`, `PATH` sin el `bin` de CUDA/cuDNN en Windows), **hace fallback a CPU** emitiendo a lo sumo un warning sin explicar el motivo — comportamiento reportado repetidamente. Además, `get_available_providers()` lista lo que el paquete soporta, no lo que la sesión realmente está usando. El requisito de PROJECT.md ("seleccionar automáticamente el mejor proveedor disponible") es exactamente donde este fallo se esconde.

**How to avoid:**
- Pasar **siempre** la lista de `providers` explícita al crear la sesión; nunca dejar el default.
- Verificar después de crear la sesión con `session.get_providers()` (los realmente activos) y **compararlo** con lo pedido. Si difieren, es un evento de primer nivel: se registra en log y se muestra en la UI ("Motor: CPU — no se pudo inicializar GPU: <motivo>").
- Exponer en la UI un panel de diagnóstico de motor: proveedor activo, versión de ONNX Runtime, versión de CUDA/cuDNN detectada, latencia media de inferencia. Es también la herramienta de soporte al cliente.
- Fijar la matriz de compatibilidad (build de `onnxruntime-gpu` ↔ CUDA major ↔ cuDNN major) en un documento y validarla en CI. Desde 1.21.0 existe `preload_dlls()` para controlar la carga de DLLs de CUDA/cuDNN/MSVC — usarlo en vez de depender del `PATH` del cliente.
- Decidir explícitamente la política de distribución: si se empaqueta `onnxruntime-gpu`, el instalador pesa cientos de MB y arrastra dependencias CUDA; si se empaqueta CPU, se pierde GPU. La opción sensata para un producto vendible es **CPU por defecto + paquete GPU opcional**, no un único instalador gigante.

**Warning signs:**
- Latencia de inferencia sospechosamente similar entre una máquina con GPU y una sin ella.
- Warnings de ONNX Runtime en el log del tipo "Falling back to CPUExecutionProvider" que nadie leyó.
- El instalador supera el gigabyte sin que nadie haya decidido que debía hacerlo.

**Phase to address:** F3 (verificación y panel de diagnóstico), F6 (política de distribución GPU/CPU).

---

### Pitfall 6: Fuga de memoria por sesiones de ONNX Runtime mal gestionadas

**What goes wrong:**
El RSS del proceso crece de forma sostenida durante la jornada. Se sospecha de los frames, pero el origen es la creación/destrucción repetida de `InferenceSession` (por ejemplo, al cambiar de motor IA ↔ OpenCV clásico, o al recargar configuración de cámaras).

**Why it happens:**
Está documentado que al destruir sesiones la memoria no se devuelve al SO ni con `ReleaseSession` ni con `ReleaseEnv`. Cada sesión crea su propio allocator de arena; la arena crece por duplicación (`initial_chunk_size_bytes`, ×2, ×4…) y no se contrae. Parte del crecimiento no es una fuga real sino comportamiento del allocator (glibc/arena retiene para reutilizar), pero para el usuario final la diferencia es irrelevante: la memoria sube.

**How to avoid:**
- **Una sesión por modelo, creada una vez, viva durante todo el proceso.** El cambio de motor no destruye ni recrea sesiones: enruta a un motor u otro ya instanciado.
- Si es imprescindible recargar un modelo, hacerlo en un subproceso desechable, no en el proceso principal.
- Configurar `enable_cpu_mem_arena=False` si la memoria estable importa más que ~40 ms de p50 (en este proyecto la inferencia es por evento, no por frame continuo: casi siempre conviene desactivar la arena).
- Considerar el allocator compartido entre sesiones (`shared arena based allocation`) si hay varios modelos (detección + placa + OCR son tres).
- Medir: test de 8 h con inferencias periódicas, graficando RSS. Meseta = OK; rampa = investigar.

**Warning signs:**
- RSS que escalona justo al tocar la configuración o al alternar motores.
- Tres modelos (vehículo/persona, placa, OCR) cargados y descargados según la pantalla activa.

**Phase to address:** F3 (arquitectura de sesiones) y F4 (al sumar modelos de LPR, revalidar el perfil de memoria).

---

### Pitfall 7: Letterbox y desescalado mal deshechos — precisión que se degrada sin que nadie lo note

**What goes wrong:**
Las cajas detectadas quedan desplazadas o escaladas respecto del objeto real. Con un camión que ocupa media pantalla nadie lo percibe. Con una patente de 120×40 px, un error de 15 px de offset recorta caracteres y el OCR falla — y el equipo culpa al modelo de OCR, no al preprocesamiento.

**Why it happens:**
El letterbox redimensiona preservando aspect ratio y agrega padding; para volver a coordenadas del frame original hay que **restar el padding antes de dividir por la escala**, no después. Los errores clásicos: usar el mismo padding en ambos ejes, olvidar que el padding puede ser asimétrico (arriba/abajo distinto), aplicar `resize` sin preservar aspect ratio (distorsión que degrada la predicción), o no hacer clamp a los límites de la imagen — hay issues reportados de coordenadas que exceden las dimensiones tras exportar a ONNX.

**How to avoid:**
- Implementar `letterbox()` y `unletterbox()` como par simétrico y **testearlas con un test de round-trip**: caja conocida → letterbox → unletterbox → debe volver a la caja original con tolerancia sub-pixel. Es un test unitario de 10 líneas que ahorra semanas.
- Fixture visual de regresión: 5–10 imágenes de referencia con detecciones esperadas guardadas; el CI compara IoU contra el resultado esperado. Cualquier cambio en preprocesamiento que rompa la geometría se detecta ahí.
- Clamp explícito de cajas al rectángulo del frame.
- Un solo lugar en el código donde se hace la transformación de coordenadas. Si aparece un segundo, es un bug esperando.

**Warning signs:**
- Cajas visualmente "corridas" hacia una esquina o sistemáticamente desplazadas en un eje.
- Las detecciones son buenas en imágenes cuadradas y malas en 16:9 (síntoma clásico de padding mal manejado).
- La confianza es alta pero el recorte de la patente sale mordido.

**Phase to address:** F3 (test de round-trip como criterio de aceptación), crítico para F4.

---

### Pitfall 8: BGR/RGB, normalización y layout — degradación silenciosa

**What goes wrong:**
El modelo funciona, detecta cosas, pero con confianzas bajas y falsos negativos con mal tiempo o poca luz. Nadie lo llama "bug" porque no hay excepción: solo se dice que "el modelo no es tan bueno".

**Why it happens:**
OpenCV entrega **BGR**; los modelos YOLO se entrenan en **RGB**. Olvidar `cv2.cvtColor(..., COLOR_BGR2RGB)` produce un modelo que sigue detectando (las redes convolucionales son tolerantes) pero con precisión degradada. Se suman: normalización (`/255.0` sí o no según cómo se exportó el modelo), layout NCHW vs NHWC, y `dtype` float32 vs float16.

**How to avoid:**
- Documentar el contrato de entrada del modelo en un archivo junto al `.onnx`: orden de canales, rango, layout, dtype, tamaño de entrada, nombres de entrada/salida. Leerlo desde el código en vez de hardcodear.
- Inspeccionar el modelo al cargarlo (`session.get_inputs()`) y **fallar ruidosamente** si la forma esperada no coincide, en vez de adaptarse mágicamente.
- Test de sanidad de precisión: la misma imagen procesada por el pipeline propio y por la referencia (Ultralytics) debe dar cajas con IoU > 0.9 y confianzas similares. Si difieren, hay un error de preprocesamiento.
- Cuidado con la forma dinámica: si el modelo se exporta con ejes dinámicos, ONNX Runtime no puede optimizar tan agresivamente y la primera inferencia con cada forma nueva paga recompilación. Para este proyecto conviene **forma fija** (una entrada por modelo), porque el tamaño de entrada no cambia en runtime.

**Warning signs:**
- Confianzas consistentemente 10–20 puntos por debajo de lo que reporta el modelo de referencia con la misma imagen.
- Objetos con color saturado (chalecos naranjas, camiones rojos) detectados peor que objetos neutros.

**Phase to address:** F3.

---

### Pitfall 9: NMS mal implementado

**What goes wrong:**
Detecciones duplicadas sobre el mismo camión (dos cajas, dos clases), o al revés, objetos legítimos suprimidos. En LPR, dos "patentes" detectadas sobre la misma placa que producen dos lecturas distintas y el sistema elige mal.

**Why it happens:**
Al reimplementar el postprocesamiento fuera de Ultralytics se acumulan errores:
- **Per-class vs class-agnostic**: por defecto YOLOv8 hace NMS por clase, con lo cual dos cajas superpuestas de clases distintas sobreviven ambas. El truco estándar es sumar un offset por clase a las coordenadas antes de un NMS único (torchvision no recibe clases). Si se copia el truco sin entenderlo, se aplica al caso equivocado.
- **Formato de salida**: YOLOv5 tiene objectness separado (confianza = obj × cls); YOLOv8/v11 **no tienen objectness** (confianza = score de clase directo). Multiplicar por un objectness inexistente, o no multiplicar cuando corresponde, mueve todos los umbrales.
- Umbral de IoU copiado sin adaptar a la escena (camiones grandes y muy superpuestos toleran otro umbral que patentes pequeñas y aisladas).

**How to avoid:**
- Elegir conscientemente: para detección de vehículo/persona, NMS por clase; para detección de placa (una sola clase), agnóstico y con un umbral de IoU bajo.
- Documentar en el código de qué versión de YOLO es el modelo y qué formato de salida tiene, y validarlo contra `session.get_outputs()[0].shape` al cargar.
- Fixture de regresión (el mismo del Pitfall 7): número de detecciones esperadas por imagen.

**Warning signs:**
- Cajas duplicadas visibles en la vista previa.
- Cambiar el umbral de confianza produce saltos discontinuos y contraintuitivos en el número de detecciones.

**Phase to address:** F3, revalidar en F4.

---

### Pitfall 10: Expectativa de precisión de LPR desconectada de la realidad de campo

**What goes wrong:**
Se demuestra el LPR con videos de prueba y da 95%+. Se instala en portería y da 60–70%. El portero pierde la confianza en la función, la ignora y vuelve a buscar el viaje a mano; la funcionalidad que se adelantó a v1 por decisión explícita queda muerta en producción.

**Why it happens:**
La brecha benchmark↔producción está bien documentada: en escenarios reales de baja calidad, incluso enfoques estado del arte no superan el 50–60%; sistemas "in the wild" reportan ~63% frente a >99% en datasets controlados. Las causas dominantes son de **instalación**, no de modelo: ángulo horizontal fuera del rango recomendado de 15°–30°, píxeles insuficientes sobre la placa, obturador lento que produce motion blur, contraluz, sol directo, suciedad y placas deterioradas. En una portería industrial se suman barro, polvo y placas dobladas por golpes.

**How to avoid:**
- **Tratar la cámara de patentes como hardware dedicado, no como una cámara de propósito general.** Especificación mínima a exigir en la propuesta comercial:
  - ≥100 px de ancho sobre la placa en la posición de detención (120–150 px si hay margen a defender); verificar con una regla en campo antes de cerrar la instalación.
  - Ángulo horizontal 15°–30° respecto de la placa; ángulo vertical bajo.
  - Obturador rápido acorde a la luz: 1/1000–1/2000 s a pleno sol, 1/250–1/500 s de noche con iluminación. Nunca por debajo de 1/250 s con vehículo en movimiento.
  - Iluminación IR dedicada para la noche (la placa es retrorreflectiva: con IR se lee mejor que con luz visible).
  - ≥15 fps para portería/barrera.
- **Explotar la ventaja del contexto**: en portería el camión está detenido sobre la balanza. Capturar una ráfaga de N frames y hacer **votación por consenso** de la lectura sube muchísimo la tasa efectiva respecto de un frame único. Esto es la mitigación más barata y más potente del proyecto.
- Diseñar el flujo para que el LPR sea una **sugerencia priorizada, no una decisión**: el sistema propone el viaje más probable y el portero confirma con un click. Con esta UX, 70% de acierto ya es valioso; con la UX de "autodetección total", 90% es frustrante.
- Registrar siempre el recorte de la placa junto a la lectura y la confianza. La evidencia visual sobrevive al error de OCR.
- Definir y medir un objetivo realista y escrito: p. ej. "≥85% de lectura exacta de 7 caracteres con vehículo detenido y placa limpia; ≥95% de acierto del viaje correcto entre las 3 sugerencias". No prometer 99%.

**Warning signs:**
- La demo se hace siempre con los mismos 3 videos, siempre de día, siempre de frente.
- Nadie midió los píxeles sobre la placa en la posición real de detención.
- No hay un conjunto de evaluación con camiones sucios, de noche, y a contraluz.

**Phase to address:** F4. Debe incluir una sub-tarea de "especificación y validación de la instalación física", no solo software. Y una decisión de UX en F5.

---

### Pitfall 11: Confusión de caracteres sin validación del formato argentino

**What goes wrong:**
El OCR devuelve `AB1Z3CD` o `0` donde va `O`. El sistema busca el viaje, no lo encuentra, y muestra "patente desconocida" — cuando bastaba una regla de formato para corregirlo.

**Why it happens:**
Se usa un OCR genérico sin restringir el alfabeto ni aplicar el layout de la patente. Los pares clásicos (0/O, 1/I/l, 8/B, 5/S, 2/Z, 6/G) son ambiguos en las tipografías de placa, especialmente con blur o suciedad.

**How to avoid:**
- Aprovechar que el formato es conocido y posicional:
  - **Mercosur (desde 04/2016):** `LL NNN LL` — 2 letras, 3 dígitos, 2 letras (`AB123CD`).
  - **Formato anterior (aún circulante):** `LLL NNN` (`ABC123`).
  - **Motos Mercosur:** `A NNN LLL`.
  - El alfabeto Mercosur excluye la Ñ deliberadamente para evitar confusión con N.
- Aplicar **desambiguación posicional**: en las posiciones que deben ser dígito, mapear O→0, I→1, B→8, S→5, Z→2; en las que deben ser letra, el mapeo inverso. Esto elimina de un golpe la mayor parte de los errores de OCR reales.
- Si tras la corrección la cadena no valida contra ninguno de los formatos, no se acepta la lectura: se marca baja confianza y se pide confirmación manual. Nunca se guarda una patente sintácticamente imposible.
- Matching contra el padrón de camiones precargados desde el ERP con **distancia de edición ≤1–2**, no igualdad exacta: es la segunda gran mitigación, y es gratis porque los camiones esperables en el día son pocos.
- Guardar la lectura cruda **y** la corregida, para poder auditar.

**Warning signs:**
- Logs con patentes de 6 o 8 caracteres, o con caracteres fuera del alfabeto permitido.
- Errores concentrados siempre en las mismas posiciones.

**Phase to address:** F4 (validador de formato + desambiguación posicional), con la parte de matching contra padrón dependiendo de F7 — mitigable con una tabla local de camiones cargada manualmente mientras tanto.

---

### Pitfall 12: La UI se congela mientras se decodifica o se infiere

**What goes wrong:**
Al presionar "capturar", la ventana deja de responder 1–3 segundos, Windows la pinta en gris y muestra "no responde". El portero, con la cola de camiones esperando, hace click de nuevo. Se disparan dos capturas.

**Why it happens:**
Decodificación de video, inferencia ONNX y escritura de imágenes a disco corriendo en el hilo de UI. Además, ONNX Runtime por defecto abre tantos hilos intra-op como núcleos y compite con el resto de la aplicación; la documentación recomienda fijar `intra_op_num_threads` explícitamente ("master switch") y, con múltiples sesiones, usar un thread pool global para evitar contención.

**How to avoid:**
- Regla arquitectónica: el hilo de UI solo pinta. Toda decodificación, inferencia y E/S corre en el núcleo headless (que PROJECT.md ya define como desacoplado — hay que **honrarlo** también en threading, no solo en módulos).
- Fijar explícitamente `intra_op_num_threads` (típicamente núcleos físicos − 1, o 2–4) y `inter_op_num_threads=1`; medir en la máquina destino, no en la de desarrollo.
- **Primera inferencia**: la primera pasada es notablemente más lenta que las siguientes. Hacer *warm-up* con un tensor dummy al arrancar la aplicación, mientras se muestra el splash. Nunca dejar que el primer camión del día pague ese costo.
- Botón de captura idempotente: se deshabilita al primer click y se rehabilita cuando la captura termina o falla, con feedback de progreso.
- Presupuesto de tiempo explícito: desde el click hasta el feedback visual, <200 ms; captura completa <2 s. Medirlo en cada release.

**Warning signs:**
- La ventana se pinta gris o el cursor pasa a "ocupado" durante la captura.
- Registros duplicados en la base con el mismo `capture_request_id` lógico.
- El primer uso del día es mucho más lento que el resto (falta warm-up).

**Phase to address:** F3 (configuración de hilos y warm-up), F5 (idempotencia del botón y feedback).

---

### Pitfall 13: Crecimiento de memoria por frames retenidos

**What goes wrong:**
La aplicación consume 400 MB al arrancar y 4 GB después de medio día con 3 cámaras. Termina en swap o en `MemoryError`.

**Why it happens:**
Un frame de 1080p en BGR son ~6 MB; a 25 fps por cámara y 3 cámaras se generan ~450 MB/s de arrays. Basta una cola sin límite entre productor y consumidor, una lista de "últimas detecciones" que nunca se poda, o un historial de miniaturas en la UI, para que la memoria explote. En Python se agrava con referencias retenidas por closures y por la vista previa.

**How to avoid:**
- Slot de tamaño 1 por cámara (ya cubierto en Pitfall 1); ninguna cola sin `maxsize`.
- Todo buffer histórico (últimas N capturas, miniaturas) con tamaño fijo y explícito (`deque(maxlen=N)`).
- La vista previa se renderiza a resolución de pantalla, no a resolución de cámara: escalar antes de convertir a bitmap de UI.
- Un solo lugar donde los frames "entran" a la UI, para poder auditar las referencias.
- Test de 8 h con las 3 cámaras y layout 2×2 activo, midiendo RSS.

**Warning signs:**
- RSS con pendiente positiva constante durante la ejecución en reposo (sin capturas).
- El consumo crece al cambiar a un layout con más cámaras y no baja al volver a 1.

**Phase to address:** F2 (pipeline) y F5 (vista previa y layouts).

---

### Pitfall 14: El disco se llena y el sistema deja de registrar evidencia

**What goes wrong:**
A los ocho meses, la partición de la PC de portería está al 100%. La aplicación no puede escribir la imagen, la base local falla, y el sistema —que es un sistema de auditoría— deja de auditar justo cuando nadie está mirando.

**Why it happens:**
Nadie dimensionó el crecimiento. 3 imágenes por captura × ~1,5 MB × 80 camiones/día ≈ 360 MB/día ≈ 130 GB/año, y eso sin contar la digitalización de remitos ni ráfagas de LPR. No se implementó retención porque "es evidencia, hay que guardarla toda", que es una decisión de negocio nunca tomada explícitamente.

**How to avoid:**
- Calcular y documentar el presupuesto de almacenamiento por año **en la fase de diseño**, y ponerlo en la propuesta comercial.
- Política de retención configurable con reglas por antigüedad y por tipo (p. ej. full-res 90 días, luego JPEG recomprimido o solo la evidencia de capturas con desvío de peso). Decisión del cliente, mecanismo del producto.
- Monitor de espacio libre con umbrales: aviso al 80%, alarma visible al 90%, y a partir del 95% **bloqueo de nuevas capturas con mensaje explícito** — es preferible frenar a registrar sin evidencia.
- Ruta de almacenamiento configurable (disco secundario o NAS) desde el instalador, sin editar archivos.
- Escritura atómica de evidencia: escribir a `.tmp` + `fsync` + rename, e insertar la fila en la base **después**. Si no, un corte de energía deja filas apuntando a archivos que no existen.
- Verificar la integridad al leer: hash del archivo guardado en la base. Una evidencia que no valida su hash debe reportarse como comprometida, no mostrarse como buena.

**Warning signs:**
- No existe una cifra escrita de GB/año en ningún documento del proyecto.
- La ruta de evidencia está hardcodeada al disco C.
- No hay ninguna prueba de "qué pasa si el disco está lleno".

**Phase to address:** F1 (esquema de persistencia, hashes, escritura atómica), F5 (monitor y alertas), F6 (configuración en el instalador).

---

### Pitfall 15: El instalador que el antivirus bloquea y el cliente no puede instalar

**What goes wrong:**
Se entrega el instalador y Windows Defender lo marca como troyano, o SmartScreen lo bloquea. El cliente concluye que el producto no es serio. En el mejor caso pierde un día de instalación; en el peor, el área de IT del cliente veta el despliegue.

**Why it happens:**
- Los ejecutables generados con **PyInstaller son marcados como falsos positivos de forma sistemática**; el modo `--onefile` (auto-extraíble comprimido) agrava la heurística, y hay reportes de que versiones 6+ empeoraron la situación.
- Sin firma de código, SmartScreen bloquea por reputación en cualquier binario nuevo. La firma no elimina los falsos positivos pero los reduce drásticamente y permite que los AV pongan en lista blanca el certificado en vez de cada hash.
- Los pesos `.onnx` son binarios opacos de decenas/cientos de MB, lo que suma a la heurística y al tamaño.

**How to avoid:**
- **Firma de código con certificado OV/EV desde la primera entrega**, no "cuando se venda". Es un ítem de costo y de plazo (validación de identidad), no una tarea técnica de última hora — planificarlo con semanas de anticipación.
- Preferir modo `--onedir` + instalador (Inno Setup / MSI) por sobre `--onefile`. Es más rápido de arrancar y menos sospechoso.
- Evaluar Nuitka como alternativa: compila a binario nativo y genera menos falsos positivos.
- Subir cada release a VirusTotal antes de entregar y reportar falsos positivos a los vendors (existen canales para eso).
- No empaquetar CUDA. GPU como paquete adicional opcional (ver Pitfall 5).
- **Rutas con espacios y acentos**: la ruta base de este proyecto ya contiene un espacio y un punto inicial (`.PROYECTO PAGOS`), y los clientes argentinos tendrán rutas con acentos y `ñ`. Probar explícitamente la instalación en `C:\Program Files\...`, en una ruta con acentos, y con el usuario `José Ñandú`. FFMPEG/OpenCV y algunas rutas de modelos tienen historial de problemas con codificación no-ASCII en Windows: usar siempre rutas absolutas, `pathlib`, y evitar pasar rutas por línea de comandos sin comillas.
- Verificar dependencias nativas faltantes en una **VM Windows limpia sin Visual C++ Redistributable ni Python**: es el único test válido. La PC de desarrollo miente siempre.

**Warning signs:**
- El instalador nunca se probó fuera de la máquina de desarrollo.
- No hay línea de presupuesto para el certificado de firma.
- El tamaño del instalador supera 1 GB sin decisión consciente.

**Phase to address:** F6, pero la **compra del certificado y la prueba en VM limpia deben empezar mucho antes** (recomendado: al cerrar F3, con un instalador "de humo" aunque el producto esté incompleto).

---

### Pitfall 16: Dejar las integraciones para el final invalida el modelo de datos

**What goes wrong:**
Se construyen seis meses de subsistema de visión sobre supuestos de cómo son los datos del ERP y de la balanza. Al llegar a F7 aparece que PALJET no expone el peso teórico por remito sino por línea de artículo, que la patente viene en un campo libre con formatos mixtos (`AB123CD`, `AB 123 CD`, `ABC-123`), que un viaje puede tener N remitos y un remito puede repartirse en varios viajes, o que la balanza devuelve el peso solo mientras el camión está sobre la plataforma y sin timestamp. Cada uno de esos hallazgos toca el esquema de la base y el flujo, que ya están construidos y con datos.

**Why it happens:**
La decisión de PROJECT.md (integraciones al final) es razonable como estrategia de **desbloqueo**, y su contrapartida ya está registrada. El riesgo real no es el orden de implementación: es haber diferido también el **descubrimiento**. Implementar tarde está bien; enterarse tarde, no.

**How to avoid — acciones a ejecutar YA, no en F7:**
1. **Leer la documentación de la API de PALJET y de la balanza ahora** (ambas existen según PROJECT.md) y extraer únicamente los *contratos de datos*: entidades, cardinalidades, tipos, unidades, formato de patente, si hay timestamp, si el peso teórico puede venir nulo. Eso no requiere credenciales.
2. **Una sola llamada GET real, lo antes posible.** Un solo `curl` autenticado contra un endpoint de lectura vale más que tres meses de suposiciones — y está permitido por la regla de solo lectura. Si no hay credenciales, escalarlo como bloqueante administrativo hoy, no en el mes 6.
3. **Congelar un contrato y un doble.** Definir los puertos `ProveedorDeViajes`, `ProveedorDePeso`, `ProveedorDeRecorrido` con implementaciones fake que devuelven datos representativos y **feos** (patente con guiones, peso teórico nulo, remito con 40 artículos, viaje con 3 remitos). El flujo completo de F5 se desarrolla contra los fakes.
4. **Modelar hoy las cardinalidades incómodas.** Viaje↔Remito N:M, peso teórico nulo (ya exigido por la regla de negocio "peso teórico incompleto"), patente normalizada como valor de dominio con parser tolerante. Estas tres decisiones son las que duele cambiar después.
5. **Persistir siempre el payload crudo** de toda respuesta externa junto al dato interpretado. Cuando la interpretación resulte errónea, se puede reprocesar sin volver a pedirle nada a un tercero.
6. **Geomov**: dado que no hay acceso ni documentación, diseñar la carga manual como **camino principal** desde el día uno y la API como optimización futura. No dejar un hueco en la UI esperando una API que puede no existir.

**Warning signs:**
- Al mes 4 nadie vio todavía una respuesta real de PALJET ni de la balanza.
- El esquema de la base modela "un viaje tiene un remito".
- La patente se guarda como `varchar` sin normalizar.
- Hay campos en la UI cuyo origen de datos "se define después".

**Phase to address:** **F1 (descubrimiento y contratos) — no F7.** F7 implementa; el riesgo se mata antes.

---

### Pitfall 17: El operador fuerza el sistema para no frenar la cola

**What goes wrong:**
En hora pico, con seis camiones esperando, el portero descubre que puede saltear la captura, seleccionar cualquier viaje, o capturar con la cámara caída. Al mes, la mitad de los registros tienen evidencia incompleta o mal asociada. El sistema no eliminó el error humano: lo trasladó, exactamente lo que PROJECT.md marca como fracaso.

**Why it happens:**
El diseño optimiza el camino feliz y castiga el camino de excepción con fricción (diálogos, campos obligatorios, esperas). Bajo presión de cola, el operador siempre encuentra el atajo. La literatura de automatización de básculas documenta que la congestión es precisamente el momento en que aparecen los desvíos y la manipulación (incluida la deliberada: "fantasmear" un camión en un segundo viaje, capturar con alguien parado en la plataforma, manipular tickets).

**How to avoid:**
- **Hacer el camino correcto el más rápido.** La captura completa debe ser más veloz que cualquier atajo. Si el atajo es más rápido, se usará el atajo.
- **No prohibir la excepción: registrarla.** Permitir "capturar sin cámara X" o "seleccionar viaje manualmente", pero dejando marca indeleble en el registro y visible en el panel de auditoría. Lo que se prohíbe se elude; lo que se registra se corrige.
- **Panel de calidad de registro** para Administración: % de capturas completas, % con override, % con LPR confirmado manualmente, por turno y por operador. Convierte un problema técnico invisible en un indicador de gestión.
- Ningún registro editable a posteriori; correcciones como eventos nuevos que apuntan al original (append-only). Va en línea con la restricción de solo-escritura-local.
- Timestamps del servidor/proceso, nunca del reloj editable por el usuario.
- Medir en campo el tiempo real de ciclo por camión antes y después. Si el sistema agrega más de ~30 s por camión, se va a eludir.

**Warning signs:**
- En las pruebas de usabilidad el portero pregunta "¿y si tengo apuro, cómo lo salteo?".
- Aparecen capturas con 1 de 3 cámaras de forma sistemática y siempre en la misma franja horaria.
- El mismo viaje seleccionado para dos camiones distintos.

**Phase to address:** F5 (diseño del flujo y del panel de auditoría). Debe validarse con el portero real, en portería, con cola, antes de cerrar la fase.

---

### Pitfall 18: Corte de energía y suspensión del equipo

**What goes wrong:**
Vuelve la luz y la aplicación no está corriendo, o corre pero ninguna cámara reconecta, o la base local quedó corrupta a mitad de una transacción. El portero no sabe reiniciar nada; opera manualmente todo el turno y nadie se entera hasta el día siguiente.

**Why it happens:**
- No hay arranque automático ni verificación de estado post-arranque.
- Tras `suspend/resume` de Windows, los dispositivos USB pueden resetearse si perdieron alimentación durante el sleep, y los handles de DirectShow/MSMF quedan inválidos; la aplicación debe reabrir el dispositivo (DirectShow notifica `EC_DEVICE_LOST`, pero OpenCV no lo propaga). Los relojes monotónicos y los timers también se comportan distinto al reanudar.
- La base local se escribe sin modo WAL ni transacciones, y un corte a mitad de escritura la deja inconsistente.

**How to avoid:**
- Arranque automático de la aplicación al iniciar sesión de Windows, y **pantalla de estado del sistema al arrancar**: cámaras vivas, espacio en disco, motor de inferencia, conectividad. Verde/rojo, sin jerga.
- Tratar el resume como una reconexión total: al detectar el evento de reanudación (o simplemente al detectar frames vencidos vía watchdog), cerrar y reabrir **todas** las fuentes, incluidas las USB. No asumir que un handle sobrevive al sleep.
- Configurar en el instalador: desactivar suspensión del equipo y suspensión selectiva de USB en el plan de energía (documentarlo como requisito de despliegue).
- SQLite en modo WAL + transacciones + `synchronous=FULL` para el registro de evidencia; escritura de archivos atómica (Pitfall 14).
- Recomendar UPS en el pliego de instalación: es más barato que cualquier mitigación de software.
- Test explícito: cortar la alimentación del equipo con una captura en curso y verificar que al volver no hay filas huérfanas ni archivos truncados.

**Warning signs:**
- Nadie probó el reinicio en frío.
- La webcam USB deja de funcionar "a veces" y se arregla desenchufándola.
- No hay pantalla de estado; hay que abrir un log para saber si el sistema está sano.

**Phase to address:** F1 (persistencia transaccional), F2 (resume = reconexión), F6 (arranque automático, plan de energía, requisitos de despliegue).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Leer frames en el hilo de UI para "salir rápido del prototipo" | Prototipo visible en un día | Reescritura del pipeline completo; latencia acumulada indetectable hasta producción | **Nunca**. Es el eje de la arquitectura; el patrón productor/consumidor cuesta medio día |
| `time.time()` de la PC como único timestamp de evidencia | Simple | Imposible correlacionar cámaras y balanza; evidencia impugnable | Aceptable solo como *complemento* de un monotónico y del skew por cámara |
| Reimplementar el postprocesamiento YOLO "a mano" sin fixtures de regresión | Menos dependencias, control total | Errores geométricos silenciosos que degradan LPR meses después | Aceptable **con** test de round-trip + fixtures visuales. Sin eso, nunca |
| Empaquetar `onnxruntime-gpu` en el instalador único | "Funciona con GPU en todos lados" | Instalador de >1 GB, más falsos positivos de AV, matriz CUDA/cuDNN frágil | Solo si el cliente destino tiene GPU y se entrega instalador dedicado |
| Guardar toda la evidencia sin política de retención | Nada que decidir hoy | Disco lleno a los 8–12 meses; falla silenciosa de la auditoría | Aceptable en piloto <3 meses, con monitor de espacio activo |
| Hardcodear la ruta de evidencia en `C:\` | Un parámetro menos | Choca con la restricción "configuración sin editar archivos"; imposible usar disco secundario | **Nunca** — es requisito de producto explícito |
| Mockear el ERP con datos "lindos" (una patente perfecta, un remito por viaje) | Desarrollo fluido de F5 | El modelo de datos se rompe al integrar; retrabajo de esquema con datos productivos | **Nunca**. Los fakes deben ser feos a propósito |
| Motor OpenCV clásico implementado como copia del pipeline de IA | Reutilización rápida | Dos motores con contratos divergentes; el "modo alternativo" nunca se prueba y se pudre | Aceptable si comparten el **puerto** (interfaz) pero no la implementación, y si el motor clásico está en el set de pruebas de regresión |
| LPR con OCR genérico sin validación de formato argentino | Funciona en la demo | Errores 0/O y 1/I permanentes; el portero deja de usar la función | **Nunca**: la validación posicional es ~50 líneas |
| Postergar el certificado de firma de código | Ahorro inmediato | Bloqueo de instalación en el cliente, semanas de demora en la primera venta | Aceptable en piloto interno; nunca en la primera entrega comercial |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| **Cámaras IP (RTSP/ONVIF)** | Guardar `rtsp://user:pass@ip/...` en un archivo de configuración en texto plano; usar la contraseña de fábrica | Credenciales en el almacén del SO (Windows Credential Manager / DPAPI), nunca en el archivo de config ni en los logs. Exigir cambio de contraseña de fábrica en el checklist de instalación; VLAN aislada para cámaras y **nunca** exponer RTSP a Internet |
| **Cámaras IP (transporte)** | Dejar el transporte por defecto (UDP) porque "tiene menos latencia" | Forzar `rtsp_transport=tcp` vía `OPENCV_FFMPEG_CAPTURE_OPTIONS`. Con UDP, incluso 0,5% de pérdida produce imagen severamente distorsionada y archivos corruptos; los 100–300 ms que se ganan no valen una evidencia rota. TCP degrada dropeando frames, que es un fallo mucho más benigno |
| **Cámaras IP (descubrimiento)** | Asumir una URL RTSP genérica para todas las marcas | Las rutas RTSP son específicas por fabricante y modelo. Descubrimiento ONVIF cuando esté disponible + campo de URL manual editable en la UI, con botón "probar conexión" que reporte el error real |
| **Webcam USB (documentos)** | Reutilizar el mismo pipeline que RTSP y dejar la resolución por defecto | Backend distinto (DSHOW/MSMF en Windows), fijar resolución máxima explícitamente (los defaults suelen ser 640×480, ilegibles para un remito), enfoque y exposición manuales si el driver lo permite. Reabrir el dispositivo tras resume del equipo |
| **ERP PALJET** | Asumir el modelo de datos; integrar recién en F7 | Leer la doc y hacer un GET real **ahora**; congelar contratos y fakes feos; persistir payload crudo. Solo GET (restricción global del proyecto) |
| **ERP PALJET (patentes)** | Comparar la patente leída por LPR con el campo del ERP por igualdad exacta | Normalizar ambos lados (mayúsculas, sin espacios ni guiones) y matchear por distancia de edición ≤1–2 contra el conjunto acotado de camiones esperados del día |
| **ERP PALJET (peso teórico)** | Asumir que siempre viene | La regla de negocio ya dice que faltan pesos: el estado "peso teórico incompleto" es de **primera clase** en el modelo, no un caso de error. La auditoría cae en la evidencia fotográfica |
| **Balanza** | Leer el peso "cuando se pueda" y asumir que corresponde al camión actual | Leer peso y fotos dentro de la misma transacción lógica de captura, con el mismo `capture_request_id`; registrar el timestamp de la lectura de peso y el skew respecto de las fotos; validar estabilidad (peso quieto durante N segundos) antes de aceptar |
| **Balanza** | Probar solo con la balanza libre | Probar con báscula ocupada, camión mal posicionado, peso oscilando y balanza sin responder. Definir qué hace el sistema en cada caso *antes* de programarlo |
| **Geomov** | Diseñar la UI asumiendo que la API existirá | Carga manual como camino principal; API como mejora opcional detrás del mismo puerto. Sin acceso ni documentación, cualquier otra cosa es especulación |
| **Todas** | Sin ambiente de pruebas: se prueba contra producción | Con solo-lectura el riesgo de escritura es nulo, pero el de **rate limit y saturación** no: throttling propio, caché local de datos maestros con TTL, y modo offline que opera con el último snapshot válido |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Decodificar todos los streams a full framerate para mostrarlos en vista previa | CPU al 100% con 3 cámaras; UI a tirones | Vista previa a FPS reducido (5–10) y escalada al tamaño del widget; decodificación completa solo en la cámara enfocada | 3+ cámaras 1080p en un i5 sin GPU |
| Inferencia sobre cada frame de cada cámara | CPU/GPU saturada, latencia creciente | En este producto la inferencia es **por evento** (click de captura), no continua. Si se agrega detección continua, hacerlo a 1–2 fps y solo en la cámara de patentes | 2+ streams con inferencia continua |
| Cola sin límite entre lector e inferencia | RSS creciente, latencia creciente | Slot de 1, drop del frame viejo | Inmediato en cuanto la inferencia sea más lenta que el stream |
| Crear una `InferenceSession` por cada inferencia | Primera inferencia lenta *siempre*; memoria creciente | Sesiones long-lived, warm-up al arrancar | Desde el primer día |
| Escribir la evidencia sincrónicamente en el hilo de captura | El botón tarda segundos en volver | Escritura en un worker con cola acotada y confirmación en UI; escritura atómica | 3+ imágenes por captura en HDD |
| Consulta de historial de evidencia sin índices ni paginación | La pantalla de auditoría tarda cada vez más | Índices por fecha, viaje y patente; paginación desde el primer día | ~50k registros (≈2 años de operación) |
| Miniaturas generadas al vuelo desde la imagen full-res | La grilla de auditoría se arrastra | Generar y guardar miniatura al capturar | ~500 registros en pantalla |
| `intra_op_num_threads` por defecto | Inferencia rápida aislada, UI trabada con múltiples cámaras activas | Fijarlo explícitamente y medirlo en el hardware destino | En cuanto haya trabajo concurrente |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Credenciales RTSP/ERP/balanza en archivo de configuración en claro | Cualquiera con acceso al equipo de portería (turnos rotativos, personal externo) obtiene acceso a las cámaras y al ERP | Almacén de credenciales del SO (DPAPI en Windows); en la UI mostrar la URL enmascarada |
| URL RTSP completa escrita en los logs | Filtración de contraseñas en archivos que se envían a soporte | Sanitizar toda URL antes de loguear; test unitario que verifica que ninguna cadena de log contiene `@` en una URL |
| Cámaras con contraseña de fábrica en la red de planta | Acceso a video, reclutamiento en botnets, movimiento lateral | Checklist de instalación obligatorio con cambio de contraseña; VLAN dedicada para cámaras; sin exposición a Internet (VPN si hace falta acceso remoto) |
| RTSP sin cifrar en la red general de la planta | Interceptación del video y de las credenciales en tránsito | Red segmentada; RTSPS/TLS si la cámara lo soporta; asumir la red de cámaras como no confiable y no ponerla en el mismo segmento que administración |
| Evidencia almacenada sin control de integridad ni de acceso | Se puede sustituir o borrar una foto para encubrir un faltante — que es exactamente el fraude que el sistema debe detectar | Hash (SHA-256) de cada archivo en la base; registro append-only; permisos de sistema de archivos que impidan escritura al usuario de portería; opción de replicar la evidencia a un recurso de red de solo-append |
| El usuario de portería con permisos de administrador del equipo | Puede alterar el reloj del sistema, borrar evidencia, desinstalar | Cuenta limitada; el reloj sincronizado por NTP y no editable; la aplicación no exige admin para operar |
| Un solo usuario compartido para todos los turnos | Imposible atribuir un override o una selección incorrecta de viaje | Identificación mínima de operador por turno (aunque sea un PIN); registrar el operador en cada captura y en cada override |
| Base local sin protección, con datos personales (DNI y foto de choferes) | Exposición de datos personales; obligaciones bajo la Ley 25.326 de Protección de Datos Personales (Argentina) | Minimizar lo que se guarda; cifrado del volumen o de la base; política de retención también para datos personales; declarar el tratamiento en la documentación del producto |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Mostrar que la cámara "está" sin mostrar si el frame es fresco | El portero confía en una imagen congelada | Indicador permanente por cámara: vivo/degradado/muerto + antigüedad del último frame. Superponer un aviso visible sobre el video congelado |
| Capturar sin feedback inmediato | Doble click, capturas duplicadas | Deshabilitar el botón al instante, mostrar progreso por cámara y un resumen de "3 de 3 capturadas" con las miniaturas |
| Presentar el LPR como automático total | Cuando falla (y va a fallar ~1 de cada 4 veces en condiciones reales), el sistema parece roto | Sugerir el viaje más probable con confianza visible y alternativas; un click confirma. El error deja de ser fallo y pasa a ser una sugerencia descartada |
| Errores técnicos crudos ("cv2.error: ... (-215:Assertion failed)") | El portero no puede hacer nada y llama a soporte | Mensajes accionables: "Cámara Lateral sin señal. Verificá el cable de red. Reintentando en 5 s." Detalle técnico plegado, con botón de copiar |
| Bloquear la salida por diferencia de peso sin ruta de resolución | Cola frenada, presión sobre el portero, se busca el atajo | Bloqueo + camino explícito: notificar al responsable, adjuntar evidencia, registrar autorización de excepción con usuario y motivo |
| Configuración de cámaras que exige saber qué es una URL RTSP | El cliente no puede instalar solo | Descubrimiento ONVIF + plantillas por marca + botón "probar" con vista previa y error legible |
| Semáforo de SLA que solo vive en la pantalla de portería | Compras no se entera del camión esperando, que es el objetivo del requerimiento | Panel consultable por Compras/Logística desde su propio puesto, en tiempo real |
| Layouts 3×3 / 4×4 con 3 cámaras configuradas | Pantalla mayormente vacía, consumo de recursos innecesario | Ofrecer solo los layouts que tienen sentido para la cantidad de fuentes activas |
| Digitalización de remitos con múltiples pasos | Retrasa la fila, que es exactamente lo que el requerimiento pide evitar | Un click captura, previsualiza y guarda; recorte y corrección de perspectiva automáticos; opción de re-tomar sin salir de la pantalla |

---

## "Looks Done But Isn't" Checklist

- [ ] **Captura sincronizada:** suele faltar la *medición* de la sincronía — verificar con un cronómetro digital filmado simultáneamente por todas las cámaras y comparar los frames guardados
- [ ] **Reconexión de cámara:** suele faltar el caso "congelada sin error" — verificar desenchufando el cable de red y también bloqueando el tráfico con firewall (el segundo caso no genera desconexión TCP)
- [ ] **Reconexión de cámara:** suele faltar la ausencia de fugas — verificar con 8 h de cortes de red cíclicos midiendo hilos, handles y RSS
- [ ] **Selección de proveedor de ejecución:** suele faltar la verificación *a posteriori* — verificar que `session.get_providers()` coincide con lo solicitado y que la UI reporta el motor real
- [ ] **Postprocesamiento YOLO:** suele faltar el test de round-trip de coordenadas — verificar caja conocida → letterbox → unletterbox con tolerancia sub-pixel
- [ ] **Preprocesamiento YOLO:** suele faltar la validación BGR/RGB — verificar contra la implementación de referencia (Ultralytics) con IoU > 0.9 sobre las mismas imágenes
- [ ] **LPR:** suele faltar el conjunto de evaluación adverso — verificar con camiones sucios, de noche, a contraluz y con placas deterioradas, no solo con los videos de la demo
- [ ] **LPR:** suele faltar la validación de formato — verificar que ninguna patente sintácticamente imposible llega a la base
- [ ] **LPR:** suele faltar la verificación de píxeles sobre la placa en la posición real de detención — verificar en campo con la cámara instalada, antes de aceptar la instalación
- [ ] **Evidencia almacenada:** suele faltar la integridad — verificar que existe hash por archivo y que hay un chequeo que detecta un archivo alterado o ausente
- [ ] **Evidencia almacenada:** suele faltar el caso disco lleno — verificar llenando artificialmente la partición y comprobando que el sistema avisa y bloquea en vez de fallar en silencio
- [ ] **Persistencia local:** suele faltar el corte de energía — verificar cortando la alimentación durante una captura y comprobando que no quedan filas huérfanas ni archivos truncados
- [ ] **UI:** suele faltar la respuesta bajo carga — verificar que la ventana nunca entra en "no responde" con 3 cámaras activas + inferencia + escritura
- [ ] **UI:** suele faltar el multi-monitor con DPI mixto — verificar arrastrando la ventana entre un monitor 100% y uno 150%, comprobando que el video no se estira ni pierde relación de aspecto y que los controles no se superponen
- [ ] **Suspender/reanudar:** suele faltar por completo — verificar suspendiendo el equipo 10 minutos y comprobando que todas las fuentes (incluida la USB) vuelven solas
- [ ] **Instalador:** suele faltar la máquina limpia — verificar en una VM Windows recién instalada, sin Python, sin VC++ Redistributable, sin CUDA
- [ ] **Instalador:** suele faltar la ruta hostil — verificar instalando en una ruta con espacios y con acentos, y con un usuario de Windows con `ñ` o tilde en el nombre
- [ ] **Instalador:** suele faltar el antivirus — verificar subiendo el binario a VirusTotal y probando en un Windows con Defender activo y SmartScreen en modo estándar
- [ ] **Integraciones:** suele faltar el dato feo — verificar que el flujo completo funciona con peso teórico nulo, viaje con 3 remitos, y patente en formato con guiones
- [ ] **Flujo operativo:** suele faltar la validación con presión real — verificar en portería, en hora pico, con el portero real y cola de camiones, midiendo el tiempo de ciclo

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Latencia acumulada de buffer descubierta tarde | **MEDIUM** | Aislar el pipeline de captura detrás del puerto ya definido y reemplazar la implementación por productor/consumidor. Si el puerto no existe, sube a HIGH: se toca UI, dominio y captura a la vez |
| Frames congelados guardados como evidencia válida | **HIGH** | Auditoría retroactiva por hash de imágenes duplicadas para marcar registros sospechosos; comunicar al cliente. Daño reputacional irreversible: es el fallo que hay que prevenir a cualquier costo |
| Fuga de memoria / hilos en reconexión | **LOW-MEDIUM** | Reemplazar el manejo de ciclo de vida por una máquina de estados; agregar el test de resistencia. Contenida si la captura está encapsulada |
| Fallback silencioso a CPU detectado en el cliente | **LOW** | Agregar verificación y panel de diagnóstico; publicar la matriz de compatibilidad. Recuperación técnica barata, costo comercial si ya se prometió GPU |
| Error de letterbox descubierto durante F4 | **LOW** | Corregir la transformación, agregar test de round-trip y fixtures. Barato **si** la transformación está en un solo lugar |
| Precisión de LPR por debajo de lo prometido | **MEDIUM-HIGH** | Primero revisar instalación (ángulo, píxeles sobre placa, obturador, IR) antes que el modelo — en general el problema es físico. Luego votación por ráfaga + validación de formato + matching contra padrón. Si ya se prometió 99% comercialmente, renegociar expectativas |
| Disco lleno en producción | **MEDIUM** | Purga guiada por antigüedad + recompresión + mover a disco secundario; implementar retención y monitor. Riesgo de haber perdido registros durante la ventana de falla |
| Modelo de datos incompatible con el ERP, descubierto en F7 | **HIGH** | Migración de esquema con datos ya cargados + retrabajo de flujo y UI. **La única recuperación barata es la prevención del Pitfall 16** |
| Instalador bloqueado por antivirus en el cliente | **MEDIUM** | Firmar el binario (semanas de trámite si no se empezó antes), reportar falsos positivos a los vendors, cambiar `--onefile` por `--onedir`+instalador. Bloqueante comercial mientras dura |
| Operadores eludiendo el flujo | **MEDIUM** | Instrumentar y medir overrides, rediseñar el camino rápido, agregar panel de calidad para Administración. Requiere acompañamiento organizacional, no solo software |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. Latencia acumulada de buffer RTSP | F1 (contrato del puerto), F2 | Cronómetro filmado 10 min: la deriva no crece |
| 2. Sincronía nominal vs real | F1, F2 | Cronómetro filmado por todas las cámaras: skew dentro de la ventana declarada; skew persistido en cada evidencia |
| 3. Stream congelado sin error | F2 | Prueba del cable desenchufado + prueba de bloqueo por firewall: estado cambia en <15 s; detector de frames idénticos activo |
| 4. Fuga de hilos/memoria en reconexión | F2 | Soak de 8 h con cortes cíclicos: hilos, handles y RSS planos |
| 5. Fallback silencioso a CPU | F3, F6 | `get_providers()` verificado y visible en el panel de diagnóstico; test en máquina sin GPU |
| 6. Fuga de sesiones ONNX Runtime | F3, revalidar F4 | Soak de 8 h con inferencias periódicas: RSS en meseta |
| 7. Letterbox / desescalado | F3 | Test unitario de round-trip + fixtures de regresión visual en CI |
| 8. BGR/RGB y normalización | F3 | Comparación contra implementación de referencia: IoU > 0.9 |
| 9. NMS mal implementado | F3, F4 | Fixtures con número de detecciones esperado; decisión per-class/agnostic documentada |
| 10. Precisión de LPR irreal | F4 (+ especificación de instalación) | Conjunto de evaluación adverso (noche, sucio, contraluz); medición de píxeles sobre placa en campo; objetivo escrito y medido |
| 11. Confusión de caracteres / formato argentino | F4 | Ninguna patente inválida en la base; test con las 3 gramáticas (Mercosur auto, formato anterior, moto) |
| 12. UI bloqueada / primera inferencia lenta | F3, F5 | Feedback <200 ms, captura <2 s, sin estado "no responde"; warm-up verificado en el arranque |
| 13. Crecimiento de memoria por frames | F2, F5 | Soak de 8 h con layout 2×2: RSS plano |
| 14. Disco lleno | F1, F5, F6 | Cifra de GB/año documentada; prueba de partición llena; alarma y bloqueo verificados |
| 15. Empaquetado / antivirus / rutas | F6 (certificado iniciado en F3) | VM Windows limpia + ruta con acentos + VirusTotal + Defender activo |
| 16. Integraciones descubiertas tarde | **F1** (descubrimiento), F7 (implementación) | Contratos congelados y fakes feos en F1; al menos un GET real ejecutado antes de cerrar F1 |
| 17. Operador eludiendo el flujo | F5 | Prueba en portería en hora pico; tiempo de ciclo medido; panel de overrides operativo |
| 18. Corte de energía / suspensión | F1, F2, F6 | Corte de energía durante captura sin corrupción; suspend/resume de 10 min con recuperación automática de todas las fuentes |

---

## Sources

**RTSP / OpenCV / cámaras IP**
- [opencv/opencv#22677 — VideoCapture.read() permanently stuck after reconnecting IP camera](https://github.com/opencv/opencv/issues/22677) (HIGH — issue oficial: `isOpened()` True con `read()` colgado y CPU anómala)
- [opencv/opencv#25889 — RTSP streaming gets stopped using OpenCV](https://github.com/opencv/opencv/issues/25889) (HIGH)
- [OpenCV Forum — RTSP VideoCapture.read() hangs if call-rate falls behind stream's framerate](https://forum.opencv.org/t/rtsp-videocapture-read-hangs-if-call-rate-falls-behind-streams-framerate/3328) (HIGH)
- [opencv/opencv#23430 — I can't set the buffersize in OpenCV](https://github.com/opencv/opencv/issues/23430) y [dactylroot/rtsp#13 — Can't set CV_CAP_PROP_BUFFERSIZE](https://github.com/statueofmike/rtsp/issues/13) (HIGH — `CAP_PROP_BUFFERSIZE` ignorado con backend FFMPEG)
- [Roboflow — Process RTSP Streams for Real-Time Video Analytics](https://blog.roboflow.com/process-rtsp-streams/) (MEDIUM — describe los tres modos de fallo: lag acumulado, caídas silenciosas, contención de hilos; watchdog 10 s, reconexión 5 s)
- [Qengineering/RTSP-with-OpenCV — interfaz de video con latencia despreciable](https://github.com/Qengineering/RTSP-with-OpenCV) (MEDIUM)
- [FFmpeg trac #258 — RTP over UDP: doesn't reorder packets](https://trac.ffmpeg.org/ticket/258) y [FFmpeg Protocols Documentation](https://ffmpeg.org/ffmpeg-protocols.html) (HIGH — comportamiento de `rtsp_transport`)
- [IPVM — Resolving IP Camera / VMS Time Sync Problems](https://ipvm.com/reports/network-time-sync-issues) y [NTP / Network Time Guide For Video Surveillance](https://ipvm.com/reports/network-time-guide-for-video-surveillance) (MEDIUM-HIGH — implicancias forenses de timestamps desalineados)
- [LukasBommes/rtsp-streamsync — RTSP Video Stream Synchronizer](https://github.com/LukasBommes/rtsp-streamsync) (MEDIUM — estimación de timestamps UTC por frame)
- [Aardwolf Security — IP Camera Penetration Testing](https://aardwolfsecurity.com/ip-camera-penetration-testing/) y [SmartVision — ONVIF vs RTSP: Security Best Practices](https://smartvision.dev/rtsp-onvif.htm) (MEDIUM — credenciales en claro, contraseñas de fábrica, botnets)

**ONNX Runtime**
- [microsoft/onnxruntime#26831 — Memory leak when destroying InferenceSession](https://github.com/microsoft/onnxruntime/issues/26831) (HIGH)
- [microsoft/onnxruntime#22271 — Memory leak after running ONNX model numerous times](https://github.com/microsoft/onnxruntime/issues/22271) y [#11118 — Memory leak during inference](https://github.com/microsoft/onnxruntime/issues/11118) (HIGH)
- [ONNX Runtime docs — Memory consumption / arena allocator](https://onnxruntime.ai/docs/performance/tune-performance/memory.html) (HIGH — documentación oficial)
- [ONNX Runtime docs — Thread management](https://onnxruntime.ai/docs/performance/tune-performance/threading.html) (HIGH — `intra_op_num_threads`, thread pool global)
- [microsoft/onnxruntime#23612 — Inference silently defaults to CPUExecutionProvider even though GPU is visible](https://github.com/microsoft/onnxruntime/issues/23612) (HIGH)
- [ONNX Runtime docs — NVIDIA CUDA Execution Provider](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html) (HIGH — matriz CUDA/cuDNN, `preload_dlls` desde 1.21.0, `PATH` en Windows)
- [microsoft/onnxruntime#11581 — onnxruntime-gpu inference slow when once, fast when continuous](https://github.com/microsoft/onnxruntime/issues/11581) (HIGH — costo de la primera inferencia)
- [microsoft/onnxruntime#14260 — Creating an inference session takes longer when there are many sessions](https://github.com/microsoft/onnxruntime/issues/14260) (HIGH)
- [Taktile Engineering — Your Lambda isn't leaking memory, your metrics are lying to you](https://engineering.taktile.com/blog/onnx-memory-usage-on-lambda/) (MEDIUM — arena vs fuga real; RSS 625 MB → 415 MB desactivando la arena, +40 ms p50)

**YOLO pre/postprocesamiento**
- [Finalizing YOLO Inference: Box Mapping and Visualization](https://isvidhi.medium.com/finalizing-yolo-inference-box-mapping-and-visualization-249c67e5530d) (MEDIUM — letterbox y mapeo inverso)
- [Deci-AI/super-gradients#1998 — Bounding box coordinates exceeding image dimensions after ONNX export](https://github.com/Deci-AI/super-gradients/issues/1998) (HIGH)
- [opencv/opencv#23977 — YOLOv8 bounding box dimensions are 0 with ONNX model on OpenCV CUDA build](https://github.com/opencv/opencv/issues/23977) (HIGH)
- [ultralytics/ultralytics#3751 — YOLOv8 NMS is per class?](https://github.com/ultralytics/ultralytics/issues/3751) y [ultralytics/yolov5#5825 — In NMS, what does "offset by class" do?](https://github.com/ultralytics/yolov5/discussions/5825) (HIGH)
- [ultralytics/yolov5#1648 — Duplicated boxes between classes all with high probabilities](https://github.com/ultralytics/yolov5/issues/1648) (HIGH)

**LPR**
- [PlateRecognizer — LPR Camera Resolution Guide: Pixels Needed at Every Distance](https://platerecognizer.com/lpr-camera-resolution-guide/) (MEDIUM-HIGH — 100 px sobre placa, 120–150 px de margen, obturador por nivel de luz, fps por velocidad)
- [ICPR 2026 Competition on Low-Resolution License Plate Recognition](https://arxiv.org/pdf/2604.22506) (HIGH — SOTA no supera 50–60% en imágenes reales de baja calidad)
- [PatrolVision: Automated License Plate Recognition in the wild](https://arxiv.org/html/2504.10810v1) (HIGH — ~63% en condiciones no controladas)
- [License plate recognition for complex scenarios based on improved YOLOv5s and LPRNet](https://www.nature.com/articles/s41598-025-18311-4) (HIGH — degradación por clima, inclinación y distancia)
- [A Dataset and Model for Realistic License Plate Deblurring](https://arxiv.org/pdf/2404.13677) (HIGH — impacto del motion blur)
- [Automatic License Plate Recognition in Real-World Traffic Videos Captured in Unconstrained Environment](https://doi.org/10.3390/electronics11091408) (HIGH)
- [MERCOSUR/GMC Res. N° 33/14 — Reglamentación Patente Única del Mercosur](https://agacapital.org.ar/downloads/Res_33_14_PATNT_MERCOSUR.pdf) (HIGH — formato `LLNNNLL`, alfabeto sin Ñ para evitar confusión con N)
- [Software libre para reconocimiento automático de las nuevas patentes del Mercosur](https://www.researchgate.net/publication/327160491_Software_libre_para_reconocimiento_automatico_de_las_nuevas_patentes_del_Mercosur) (MEDIUM — contexto argentino específico)

**Empaquetado / escritorio Windows**
- [pyinstaller/pyinstaller#6754 — --onefile exe getting anti-virus false positive flags](https://github.com/pyinstaller/pyinstaller/issues/6754) (HIGH)
- [pyinstaller/pyinstaller#8164 — PyInstaller above v5.13.2 results in numerous false-positives on VirusTotal](https://github.com/pyinstaller/pyinstaller/issues/8164) (HIGH)
- [PythonGUIs — How to Fix Antivirus False Positives with PyInstaller Executables](https://www.pythonguis.com/faq/problems-with-antivirus-software-and-pyinstaller/) (MEDIUM — firma de código, `--onedir`, Nuitka)
- [Microsoft Q&A — Executables created by PyInstaller incorrectly flagged by antivirus](https://learn.microsoft.com/en-us/answers/questions/4078397/where-executables-created-by-pyinstaller-are-being) (MEDIUM)
- [hankhank10/false-positive-malware-reporting](https://github.com/hankhank10/false-positive-malware-reporting) (MEDIUM — canales de reporte a vendors de AV)
- [Microsoft USB Blog — Do USB devices get reset on system sleep resume?](https://techcommunity.microsoft.com/blog/microsoftusbblog/do-usb-devices-get-reset-on-system-sleep-resume/270683) (HIGH)
- [opencv/opencv#11696 — Windows MSMF not opening connected device](https://github.com/opencv/opencv/issues/11696) (HIGH)

**Contexto industrial / básculas**
- [Mining Weekly — AI weighbridge solutions combat coal corruption](https://www.miningweekly.com/article/ai-weighbridge-solutions-combat-coal-corruption-2024-05-31) (MEDIUM — la congestión como disparador de desvíos; manipulación de tickets, camiones "fantasma", ayudante sobre la plataforma)
- [Weightron Bilanciai — How Does Weighbridge Automation Work?](https://www.weightron.com/news/how-does-weighbridge-automation-work/) (MEDIUM)
- [Racklify — Integrating Software with Your Weighbridge](https://racklify.com/encyclopedia/automation-in-action-integrating-software-with-your-weighbridge-truck-scale/) (LOW-MEDIUM — contenido comercial)

**Confianza por área:** RTSP/OpenCV **HIGH** · ONNX Runtime **HIGH** · YOLO pre/postproceso **HIGH** · LPR **MEDIUM-HIGH** (fuerte en física de captura y en brecha benchmark↔producción; MEDIUM en tasas específicas para patentes argentinas, no hay benchmark público local) · Empaquetado **HIGH** · Contexto industrial y operativo **MEDIUM** (evidencia sectorial y guías de fabricante, sin post-mortems públicos de proyectos equivalentes) · Integraciones PALJET/balanza/Geomov **LOW** (sin acceso a documentación al momento de la investigación; las recomendaciones son de mitigación de riesgo, no de contrato conocido)

---
*Pitfalls research for: sistema de control de portería con visión artificial (multi-cámara RTSP/USB, YOLO+ONNX Runtime, LPR argentino, evidencia auditable)*
*Researched: 2026-07-24*
