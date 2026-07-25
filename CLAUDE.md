<!-- GSD:project-start source:PROJECT.md -->

## Project

**Sistema de Control de Portería con Visión Artificial**

Aplicación de escritorio para el puesto de portería de una planta industrial que automatiza el control de ingreso y egreso de camiones. Con la menor interacción manual posible (idealmente un solo botón) captura de forma sincronizada el peso de la balanza, fotografías de la carga desde múltiples cámaras y los datos del viaje provenientes del ERP, y audita automáticamente las diferencias entre el peso real y el peso teórico del remito.

El usuario directo es el **portero** (operación diaria); los usuarios indirectos son **Logística** (precarga de viajes), **Compras** (trazabilidad de proveedores en tiempo real) y **Administración** (auditoría posterior). Es un producto destinado a comercializarse, no de uso interno exclusivo.

El proyecto se construye en dos grandes bloques: primero el **subsistema de visión** (captura multi-cámara, evidencia y reconocimiento de patentes), después las **integraciones externas** (ERP PALJET, balanza, Geomov).

**Core Value:** Que la captura de evidencia visual sea confiable, sincronizada y trazable: cuando el portero presiona el botón, el sistema debe obtener sí o sí las fotos de todas las cámaras del mismo instante, asociadas al vehículo correcto, y guardarlas de forma que puedan auditarse después. Si esto falla, el sistema no elimina el error humano, lo traslada.

### Constraints

- **Seguridad / Acceso a datos**: La aplicación solo puede leer de APIs y bases de datos externas (GET y SELECT). Escribe exclusivamente en su propia persistencia local — Regla global del usuario, sin excepciones para este proyecto.
- **Plataforma**: Windows es la plataforma primaria de desarrollo y validación; Linux y macOS se sostienen por diseño multiplataforma pero se validan después — El puesto de portería es una PC con Windows.
- **Hardware de ejecución**: Debe funcionar tanto con GPU como sin ella, seleccionando el proveedor de ejecución en runtime — El equipo destino no está garantizado y el producto se comercializa a distintos clientes.
- **Dependencias externas**: Las integraciones con ERP PALJET, balanza y Geomov se desarrollan al final del proyecto — Decisión del usuario para no bloquear el avance esperando accesos y documentación de terceros.
- **Calidad de producto**: Instalador, mensajes de error comprensibles y configuración sin editar archivos son obligatorios — Es un producto para vender, no de uso interno.
- **Dato faltante crítico**: No hay acceso ni documentación de la API de Geomov — El propio documento fuente marca que hay que evaluar su factibilidad y prever carga manual como plan B.

<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->

## Technology Stack

## TL;DR — Las siete decisiones

| # | Eje | Decisión | Confianza |
|---|-----|----------|-----------|
| 1 | Lenguaje + UI | **Python 3.12 + PySide6 6.11.1 (LGPLv3)** | HIGH |
| 2 | Inferencia | **ONNX Runtime**: `onnxruntime-directml` 1.24.4 como build único de Windows (CPU + cualquier GPU DX12); `onnxruntime` 1.27.0 en Linux/macOS; CUDA solo como variante opt-in | HIGH |
| 3 | Detector | **RF-DETR-Nano/Small (Apache-2.0)**, exportado a ONNX opset 17. **Prohibido Ultralytics (AGPL-3.0)** | HIGH |
| 4 | LPR/ANPR | **fast-alpr (MIT)** = detector de placa + **fast-plate-ocr (MIT)** `cct-s-v2-global-model`, con `argentinian-plates-cnn-synth-model` como segundo lector. ⚠️ Reemplazar el detector de placa por uno propio antes de comercializar | MEDIUM |
| 5 | RTSP | **PyAV 18.0.0 (BSD-3, FFmpeg LGPL embebido)** para IP; **OpenCV VideoCapture** solo para webcam USB y archivos | MEDIUM-HIGH |
| 6 | Persistencia | **SQLite (dominio público) + SQLAlchemy 2.0.51 (MIT) + Alembic**; imágenes en filesystem con hash SHA-256 en la base | HIGH |
| 7 | Empaquetado | **PyInstaller 6.21.0 `--onedir` + Inno Setup 7** con licencia comercial. Instalador esperado **180–280 MB**, instalado **450–650 MB** | MEDIUM |

## Recommended Stack

### Core Technologies

| Technology | Version | License | Purpose | Why Recommended |
|------------|---------|---------|---------|-----------------|
| **Python** | 3.12.x (64-bit) | PSF (permisiva) | Lenguaje del núcleo y de la UI | Único punto del ecosistema donde ONNX Runtime, OpenCV, PyAV y todo el stack de ALPR abierto conviven con bindings de primera clase. Se elige 3.12 sobre 3.13/3.14 porque **todas** las ruedas del stack tienen build `cp312-win_amd64` verificado, y sobre 3.11 porque `onnxruntime>=1.27` exige `>=3.11` y 3.12 ya es el piso maduro. Evitar 3.13t (free-threading): no aporta nada acá y rompe ruedas binarias |
| **PySide6-Essentials** | 6.11.1 | **LGPL-3.0-only** (o GPL-2.0/GPL-3.0 a elección) | Framework de UI de escritorio | Qt es el único toolkit que resuelve *bien* render de N streams de video, layouts 1/2x2/3x3/4x4, y paridad real Win/Linux/macOS. `PySide6` es de The Qt Company y su rueda es **LGPLv3**: permite producto comercial de código cerrado si se enlaza dinámicamente (que es lo que hace Python por definición). `PyQt6` sería GPL-3.0 o licencia comercial paga — descartado. Se usa `PySide6-Essentials` (77.5 MB de rueda) y **no** el metapaquete `PySide6` completo, que arrastra Addons (~250 MB) inútiles acá |
| **ONNX Runtime** | 1.27.0 (`onnxruntime`, `onnxruntime-gpu`) / 1.24.4 (`onnxruntime-directml`) | **MIT** | Motor de inferencia | MIT puro, sin fricción comercial. Selección de execution provider en runtime por lista de prioridad, exactamente el requisito del proyecto. Un solo formato de modelo (`.onnx`) sirve para CPU, DirectML, CUDA y CoreML sin recompilar |
| **OpenCV (`opencv-python-headless`)** | 5.0.0.93 | **Apache 2.0** (ruedas embeben FFmpeg **LGPLv2.1**) | Motor de visión clásica, preprocesado, codificación JPEG, webcam USB, archivos de video | Apache 2.0 desde 4.5.0 — sin problema comercial. Se usa la variante **headless** en el núcleo (evita que OpenCV arrastre su propio Qt5 LGPLv3 y choque con el Qt6 de PySide6 — este conflicto es una causa clásica de crashes al inicio en Windows y Linux). OpenCV 5.0 es de junio 2026 y es seguro para uso Python/CPU: la API `cv2` es retrocompatible; lo que rompió fue la C API de OpenCV 1.x y algunos módulos contrib |
| **PyAV** | 18.0.0 | **BSD-3-Clause** (FFmpeg embebido **LGPL**) | Ingesta RTSP de cámaras IP | Ver decisión 5. Acceso a nivel paquete/frame, timeouts reales, `rtsp_transport=tcp` explícito y excepciones limpias para la lógica de reconexión — todo lo que `cv2.VideoCapture` no expone |
| **SQLite** | 3.4x (stdlib `sqlite3`) | **Dominio público** | Persistencia local | Cero licencia, cero servidor, un archivo, transaccional. Es el motor embebido correcto para un puesto fijo con un solo proceso escritor |
| **NumPy** | 2.5.1 | BSD-3-Clause | Tensores, interoperabilidad cv2 ↔ ORT ↔ Qt | Punto de encuentro de todo el stack. Toda la cadena de esta página ya está en el ABI de NumPy 2.x |

### Supporting Libraries

| Library | Version | License | Purpose | When to Use |
|---------|---------|---------|---------|-------------|
| `rfdetr` | 1.8.3 | **Apache-2.0** | Exportar RF-DETR a ONNX | Solo en la máquina de build/dev. **No es dependencia de runtime**: se exporta el `.onnx` una vez y el instalador solo lleva el archivo. Esto evita meter PyTorch (~2.5 GB) en el producto |
| `fast-alpr` | 0.4.0 | **MIT** | Pipeline ALPR (detección de placa → recorte → OCR) | Runtime. Orquesta `open-image-models` + `fast-plate-ocr` sobre ONNX Runtime, con extras por EP (`onnx-gpu`, `onnx-directml`, `onnx-openvino`) |
| `fast-plate-ocr` | 1.1.0 | **MIT** | OCR de patentes | Runtime. Modelos CCT propios del autor, publicados MIT. Incluye modelo argentino específico |
| `open-image-models` | 0.5.1 | **MIT** (código) — ⚠️ pesos derivados de YOLOv9 | Detección de placa | Runtime en v1 / prototipo. **Marcar para reemplazo antes de release comercial** (ver decisión 4) |
| `SQLAlchemy` | 2.0.51 | **MIT** | ORM / capa de datos | Runtime. API 2.0 tipada, funciona sin acoplar el dominio al esquema |
| `alembic` | 1.16.x | **MIT** | Migraciones de esquema | Obligatorio en producto vendido: los clientes actualizan versiones sobre bases con años de evidencia |
| `pydantic` | 2.13.4 | **MIT** | DTOs, config validada, contratos del puerto de transporte | **Encaja directo con la decisión arquitectónica del proyecto**: los mensajes núcleo↔UI se definen como modelos Pydantic; en v1 se pasan como objetos en memoria, y el día que el transporte se vuelva IPC se serializan a JSON sin tocar el dominio |
| `pydantic-settings` | 2.x | MIT | Configuración de la app | Cumple el requisito "configuración sin editar archivos": la UI escribe, Pydantic valida, se persiste en SQLite/JSON |
| `onvif-zeep-async` | 4.2.1 | **MIT** | Descubrimiento ONVIF y obtención de URIs RTSP | Cuando se agregue autodescubrimiento de cámaras. ONVIF resuelve *descubrir y configurar*; el video sigue viniendo por RTSP |
| `WSDiscovery` | 2.1.2 | LGPL-3.0 | Probe WS-Discovery en la LAN | Opcional, para el botón "buscar cámaras". LGPL: uso como librería dinámica, sin problema |
| `msgspec` | 0.21.1 | BSD-3-Clause | Serialización rápida del transporte | Solo cuando el transporte pase a proceso separado. Más rápido que JSON estándar y con validación de esquema |
| `pyzmq` | 27.1.0 | BSD-3-Clause (libzmq: MPL-2.0) | Transporte IPC futuro | Solo en la fase de extracción del núcleo a proceso separado. MPL-2.0 es copyleft por archivo → no contamina el producto |

### Development Tools

| Tool | Version | License | Purpose | Notes |
|------|---------|---------|---------|-------|
| **uv** | 0.9.x | MIT/Apache-2.0 | Gestor de entorno y dependencias | Lockfile determinista (`uv.lock`) — imprescindible para que el instalador sea reproducible. 10–50× más rápido que pip en CI |
| **PyInstaller** | 6.21.0 | GPLv2+ **con excepción explícita para el bootloader** que permite empaquetar apps propietarias | Congelar la app | Ver decisión 7. Usar `--onedir`, nunca `--onefile` |
| **Inno Setup** | 7.0.2 | Propia, tipo BSD modificada — ⚠️ desde 6.5.0 se solicita licencia comercial paga | Instalador Windows | Perpetua, pago único. Alternativa 100 % gratis: **NSIS** (licencia zlib) |
| **Ruff** | 0.16.0 | MIT | Lint + format | Reemplaza flake8+black+isort |
| **pytest** + **pytest-qt** 4.5.0 | — | MIT | Tests | `pytest-qt` para la UI; el **núcleo headless se testea sin Qt**, que es exactamente el beneficio de la arquitectura elegida |
| **Azure Trusted Signing** o cert OV/EV | — | — | Firma Authenticode | Sin firma, SmartScreen bloquea el instalador y el producto parece malware. Desde 2023 los certs OV exigen token HW/HSM; Trusted Signing evita el hardware |

## Decisión 1 — Lenguaje y framework de UI

### Veredicto: **Python 3.12 + PySide6** · Confianza HIGH

| Criterio | Python + PySide6 | C++ + Qt | Rust (Tauri/egui/slint) | C# + Avalonia |
|----------|------------------|----------|--------------------------|---------------|
| Bindings ONNX Runtime | Referencia, oficial MS, MIT | Nativo, oficial MS | `ort` (comunidad, pykeio) — bueno pero wrapper | `Microsoft.ML.OnnxRuntime` oficial MS, primera clase |
| Bindings OpenCV | `cv2` oficial, Apache-2.0 | Nativo | `opencv-rust` comunidad, build doloroso en Windows | OpenCvSharp (Apache-2.0) OK · **Emgu.CV = GPL o comercial paga ⚠️** |
| Ecosistema ALPR abierto | **fast-alpr, fast-plate-ocr, PaddleOCR, EasyOCR** | Casi nada listo | Nada | Casi nada |
| Render multi-stream | Qt: sólido | Qt: mejor | egui/slint: inmaduro para video · Tauri: pasar frames a un webview es el cuello de botella | Avalonia: aceptable, video menos maduro |
| Instalador Windows | PyInstaller+Inno: pesado pero probado | MSVC+windeployqt: excelente, chico | Excelente, muy chico | Self-contained ~80 MB, excelente |
| Paridad Linux/macOS real | Alta (Qt + ruedas manylinux/universal2) | Alta | Alta | Alta |
| Velocidad de desarrollo | **Máxima** | Baja | Media-baja | Media |
| Separación núcleo headless | Trivial (módulo puro sin `import PySide6`) | Trivial | Trivial | Trivial |

- **Rust + Tauri** — mover frames de video a un webview es la peor arquitectura posible para esta app; además `opencv-rust` en Windows es un dolor de build y no hay ecosistema ALPR.
- **Rust + egui/slint** — inmaduros para superficies de video multi-panel; slint además es GPL/comercial/Royalty-free-con-condiciones, no una licencia permisiva simple.
- **Electron / interfaz web** — descartado también por PROJECT.md ("Aplicación móvil o interfaz web" está en Out of Scope).
- **Tkinter, Kivy, wxPython** — no producen una UI de calidad de producto vendible con layouts de video configurables.

### Render de múltiples streams en Qt — patrón concreto

- Un `QWidget` por cámara con `paintEvent` que dibuja un `QImage` construido **sin copia** sobre el buffer del `numpy.ndarray` BGR: `QImage(buf.data, w, h, buf.strides[0], QImage.Format_BGR888)`. Qt tiene formato BGR888 nativo → **cero `cv2.cvtColor` por frame**.
- Un `QThread`/`threading.Thread` por cámara para decodificar, y una `queue.Queue(maxsize=1)` con política *drop-oldest*: si la UI no alcanza, se descartan frames viejos en vez de acumular latencia. Este es el mecanismo que evita el clásico "el video se atrasa cada vez más".
- Señal Qt (`Signal(object)`) del hilo de captura al widget. Nunca tocar widgets desde hilos que no son el main.
- La grilla 1 / 2x2 / 3x3 / 4x4 se implementa con `QGridLayout` reconfigurable, no con widgets distintos por layout.

### Cumplimiento LGPLv3 de PySide6 (obligatorio para vender)

## Decisión 2 — ONNX Runtime y execution providers

### Veredicto Windows: **una sola build, `onnxruntime-directml`** · Confianza HIGH

| Paquete | Versión | Rueda `cp312-win_amd64` | EPs incluidos | Dependencias externas |
|---------|---------|------------------------|---------------|-----------------------|
| `onnxruntime` | 1.27.0 | **13.4 MB** | CPU (+ CoreML en macOS) | ninguna |
| `onnxruntime-directml` | 1.24.4 | **25.1 MB** | **DirectML + CPU** | **ninguna** — DirectML viene con Windows 10 1903+ / se redistribuye la DLL |
| `onnxruntime-gpu` | 1.27.0 | **213.6 MB** | CUDA + TensorRT + CPU | **CUDA 12.x + cuDNN 9 (~1.5–2.5 GB)** |

- Acelera sobre **cualquier GPU DirectX 12**: NVIDIA, AMD **e Intel iGPU**. En una PC de portería industrial, lo más probable es una integrada Intel/AMD — CUDA no serviría ahí, DirectML sí.
- **Cero redistribuibles.** El paquete CUDA agrega 1.5–2.5 GB al instalador y obliga a validar versión de driver del cliente. Inaceptable para un producto que se instala en plantas.
- Contiene también el CPU EP → una sola build cubre "con y sin GPU", que es literalmente el requisito de PROJECT.md.
- Está en **"sustained engineering"**: Microsoft movió el desarrollo nuevo a Windows ML. No está deprecado y sigue recibiendo releases (1.24.4), pero **va rezagado**: 1.24.x contra 1.27.0 de la línea principal.
- Consecuencia práctica y accionable: **exportar todos los modelos ONNX con opset 17**. Opset 17 es soportado por todos los EPs relevantes (DirectML llega hasta ~20/21) y evita el fallo de "unsupported opset" que aparece cuando se exporta con el opset por defecto de un PyTorch reciente.
- En NVIDIA dedicada, CUDA/TensorRT son bastante más rápidos que DirectML. Por eso la variante CUDA existe — pero como **opt-in**, no como default.

### Matriz de providers por plataforma

| Plataforma | Paquete | Cadena de prioridad de EPs |
|------------|---------|----------------------------|
| **Windows (default, un instalador)** | `onnxruntime-directml` 1.24.4 | `DmlExecutionProvider` → `CPUExecutionProvider` |
| **Windows (variante "GPU NVIDIA", opt-in)** | `onnxruntime-gpu` 1.27.0 | `TensorrtExecutionProvider` → `CUDAExecutionProvider` → `CPUExecutionProvider` |
| **macOS (Apple Silicon e Intel)** | `onnxruntime` 1.27.0 | `CoreMLExecutionProvider` → `CPUExecutionProvider` — **CoreML ya viene en la rueda estándar de macOS, no hay paquete aparte** |
| **Linux (default)** | `onnxruntime` 1.27.0 | `CPUExecutionProvider` |
| **Linux (NVIDIA, opt-in)** | `onnxruntime-gpu` 1.27.0 | `CUDAExecutionProvider` → `CPUExecutionProvider` |
| **Linux (Intel, opcional)** | `onnxruntime-openvino` (distribuido por Intel) | `OpenVINOExecutionProvider` → `CPUExecutionProvider` |
| **ROCm / AMD en Linux** | requiere build desde fuente | **Fuera de alcance** — no hay rueda oficial, el costo de mantenerla no se justifica |

### Cómo detectar disponibilidad sin crashear — el patrón correcto

# core/inference/provider_selector.py  — sin dependencias de UI

- **Calentar** la sesión con un tensor dummy al arrancar. La primera inferencia de DirectML/CUDA compila kernels y tarda 1–3 s; que eso pase durante la captura de evidencia es inaceptable.
- **Persistir el EP elegido** y mostrarlo en la UI ("Motor: GPU DirectML / CPU"). Es información de soporte técnico en campo.
- **Permitir forzar CPU** desde configuración. Los drivers de GPU rotos son una realidad en plantas industriales y necesitás una vía de escape sin reinstalar.
- `intra_op_num_threads` limitado (p. ej. 4) si se corre en CPU, para no dejar sin CPU al hilo de decodificación de video.

## Decisión 3 — Modelo de detección · **LA LICENCIA ESTÁ RESUELTA, SIN AMBIGÜEDAD**

### 🔴 NO usar Ultralytics. Ni YOLOv5, ni v8, ni v11, ni v12. · Confianza HIGH

- Ultralytics publica bajo **AGPL-3.0** *o* licencia Enterprise paga. No hay tercera opción.
- La AGPL-3.0 aplicada por Ultralytics exige **liberar el código fuente completo de la obra derivada — la aplicación entera, no solo el módulo de visión** — incluyendo scripts, archivos de configuración y, cuando corresponde, los pesos del modelo.
- Ultralytics declara explícitamente que la licencia Enterprise **es necesaria si la solución final es propietaria y se usa internamente en una empresa o comercialmente**.
- El uso de **modelos preentrenados** también cae bajo AGPL: no hay excepción por "solo uso de inferencia" ni por "no es un servicio de red". Existe un issue público (`ultralytics#19390`) planteando justamente el caso de modelo on-device sin servicio de red, y la posición del proyecto no habilita la excepción.

| Modelo | Licencia real | Veredicto |
|--------|---------------|-----------|
| YOLOv5 / v8 / v11 / v12 (Ultralytics) | AGPL-3.0 | ❌ Prohibido |
| YOLOv10 | Construido sobre Ultralytics → AGPL-3.0 | ❌ Prohibido |
| YOLOv9 (WongKinYiu) | **GPL-3.0** *(verificado por GitHub API)* | ❌ Prohibido |
| YOLOv7 (WongKinYiu) | GPL-3.0 | ❌ Prohibido |
| YOLO-NAS (Deci / super-gradients) | Código Apache-2.0 pero **pesos bajo licencia de investigación no comercial** | ❌ Prohibido — la trampa es que la gente mira el código y no los pesos |
| DEIM | GitHub reporta `NOASSERTION` (licencia no identificable) | ❌ Evitar — licencia indeterminada es riesgo puro |

### ✅ Usar: **RF-DETR (Apache-2.0)** · Confianza HIGH

| Modelo elegido | Licencia | AP50:95 COCO | Latencia T4 | Rol |
|----------------|----------|--------------|-------------|-----|
| **RF-DETR-Nano** | **Apache-2.0** | 48.4 | 2.3 ms | Default en CPU / iGPU |
| **RF-DETR-Small** | **Apache-2.0** | 53.0 | 3.5 ms | Default con GPU dedicada |
| RF-DETR-Medium | Apache-2.0 | 54.7 | 4.4 ms | Si sobra hardware |
| ~~RF-DETR-XL / 2XL~~ | **PML 1.0 (no Apache)** | 58.6 / 60.1 | 11.5 / 17.2 ms | ⚠️ **No usar** — quedan fuera del paraguas Apache |

- **Apache-2.0 sobre código y sobre los checkpoints base** (Nano→Large). Cero obligaciones copyleft, cero regalías, patente concedida explícitamente por la licencia.
- Estado del arte real en 2026 en el punto de operación tiempo real: RF-DETR-Nano supera en AP a modelos YOLO mucho más pesados.
- **Sin NMS.** Es un DETR: el post-procesamiento es sigmoid + top-k, más simple, más determinista y sin el hiperparámetro `iou_threshold` que suele romper casos borde. Menos código propio que mantener.
- Export a ONNX oficial (`model.export(format="onnx")`), compatible con ONNX Runtime y con `cv2.dnn`.
- Repo vivo: último push 2026-07-24, 8.7k estrellas *(verificado por GitHub API)*.
- Las clases que el proyecto necesita —`person`, `car`, `truck`, `bus`— vienen en COCO. PROJECT.md ya descartó entrenar modelos propios; con COCO alcanza.

| Alternativa | Licencia | Cuándo usarla en vez de RF-DETR |
|-------------|----------|--------------------------------|
| **D-FINE** (N/S/M/L/X) | **Apache-2.0** *(verificado)* — D-FINE-S: 48.5 AP, 3.49 ms | Si RF-DETR da problemas en el export ONNX o si se prefiere un repo con checkpoints Objects365 preentrenados (generaliza mejor fuera de COCO) |
| **YOLOX** (Nano→X) | **Apache-2.0** *(verificado)* | Si se quiere el post-procesamiento YOLO clásico y máxima cantidad de ejemplos de deployment. Costo: es de 2021, YOLOX-x llega a 51.1 mAP con muchísimos más parámetros que RF-DETR-Small |
| **RTMDet** (MMDetection) | **Apache-2.0** | Si ya se usa el toolchain de OpenMMLab. Costo: mmdetection sin push desde 2024 |

### Consecuencia arquitectónica (para el roadmap)

## Decisión 4 — LPR / ANPR

### Veredicto: **fast-alpr (MIT) con reemplazo planificado del detector de placa** · Confianza MEDIUM

| Componente | Paquete | Licencia código | Modelo |
|------------|---------|-----------------|--------|
| Orquestación | `fast-alpr` 0.4.0 | **MIT** *(verificado)* | — |
| Detección de placa | `open-image-models` 0.5.1 | **MIT** *(verificado)* | ⚠️ **arquitectura YOLOv9** |
| OCR | `fast-plate-ocr` 1.1.0 | **MIT** *(verificado)* | CCT, propios del autor |
| Modelo | Cobertura | Precisión | Uso recomendado |
|--------|-----------|-----------|-----------------|
| `cct-s-v2-global-model` | 65+ países, con reconocimiento de región | — (recomendado oficial) | **Default.** Cubre Mercosur `AA123AA` y el formato viejo `ABC123` |
| `cct-xs-v2-global-model` | 65+ países | — | Si el hardware es muy limitado (2144 PPS) |
| `argentinian-plates-cnn-synth-model` | **Argentina** (real + sintético) | **94.19 %** | **Segundo lector.** Especializado en AR |
| `argentinian-plates-cnn-model` | **Argentina pre-2020** | 94.05 % | Solo si la flota es mayoritariamente de patentes viejas |
| `global-plates-mobile-vit-v2-model` | 65+ países | 93.3 % | Legacy, sin ventaja sobre CCT v2 |

### ⚠️ El riesgo de licencia que hay que cerrar antes de vender

### Alternativas de OCR evaluadas y descartadas

| Opción | Licencia | Por qué no |
|--------|----------|-----------|
| **Tesseract** | Apache-2.0 | Diseñado para texto de documentos con layout. En patentes (fuente ancha, ruido, ángulo, reflejos) rinde mal aun con preprocesado agresivo. No es el problema para el que fue hecho |
| **EasyOCR** | Apache-2.0 | Arrastra **PyTorch (~2–2.5 GB)** al instalador. OCR genérico, sin especialización en patentes. Duplicaría el tamaño del producto por peor resultado |
| **PaddleOCR** | Apache-2.0 | Excelente OCR, pero es genérico y el runtime PaddlePaddle es enorme. Vía ONNX exportado sería viable, pero sigue siendo mucho más pesado y menos preciso que un modelo específico de patentes |
| **OpenALPR (original)** | **AGPL-3.0** | Misma trampa comercial que Ultralytics. Además el proyecto abierto está discontinuado |
| **Plate Recognizer / Rekor cloud** | Comercial SaaS | **Viola el requisito de operación offline** de PROJECT.md |

## Decisión 5 — Captura RTSP

### Veredicto: **PyAV para IP, OpenCV para USB y archivos** · Confianza MEDIUM-HIGH

| Opción | Veredicto | Razón |
|--------|-----------|-------|
| **PyAV 18.0.0** (BSD-3, FFmpeg LGPL embebido) | ✅ **Primaria para RTSP** | Control real sobre las opciones de FFmpeg, timeouts, acceso a paquetes y timestamps, y **excepciones Python limpias** cuando el stream muere — que es lo que la lógica de reconexión necesita |
| **`cv2.VideoCapture(url)`** | ⚠️ **Solo webcam USB y archivos** | Envuelve FFmpeg pero no expone casi nada. `CAP_PROP_BUFFERSIZE` es **ignorado** por el backend FFmpeg (de ahí la latencia creciente clásica). Los timeouts solo se configuran por la variable de entorno global `OPENCV_FFMPEG_CAPTURE_OPTIONS`, que es proceso-global y no por cámara. Y ante fallo devuelve `False`, sin causa: no se puede distinguir "frame perdido" de "cámara caída" |
| **GStreamer** | ❌ No | Es la opción más potente y la de menor latencia con pipelines afinados, pero exige **instalar y redistribuir el runtime GStreamer en cada plataforma** y OpenCV con GStreamer habilitado (las ruedas de PyPI no lo traen: hay que compilar OpenCV). Ese costo se justifica con decenas de streams — escala que PROJECT.md descartó explícitamente |
| **FFmpeg CLI por subproceso** | ❌ No | Parsear stdout de un proceso hijo, gestionar zombies y sincronizar timestamps es reimplementar peor lo que PyAV ya hace enlazado |

### Patrón de captura robusta

# core/video/rtsp_source.py — sin dependencias de UI

- **Un hilo por cámara, aislado.** Una excepción en una cámara nunca puede tumbar a las otras ni a la UI.
- **Reconexión con backoff exponencial + jitter** (1 s → 2 s → 4 s → … tope 30 s). Sin jitter, N cámaras caídas por un corte de switch reconectan en fase y golpean la red a la vez.
- **Watchdog por keyframe**, no por excepción. Muchas cámaras IP no cierran el socket cuando se cuelgan: siguen abiertas y dejan de mandar. Si pasan >5 s sin frame nuevo, cerrar y reconectar aunque no haya habido error.
- **Buffer de profundidad 1 con drop-oldest.** Nunca acumular frames: para evidencia importa el frame *actual*, no la secuencia completa.
- **Frame de captura ≠ frame de preview.** El preview puede ir a 10–15 fps decimados; en el momento del botón de captura hay que tomar el frame **más reciente** de cada fuente y sellar el timestamp común. La "sincronización" que pide el negocio es *un único instante de disparo con tolerancia declarada*, no genlock de hardware. Registrar en la base el delta real entre cámaras (p. ej. ±80 ms) — eso es lo que hace la evidencia auditable.

## Decisión 6 — Persistencia local

### Veredicto: **SQLite + imágenes en filesystem con hash** · Confianza HIGH

- Un puesto de portería = un proceso escritor. Postgres/MySQL embebidos serían operaciones que el cliente no puede administrar.
- DuckDB es analítico (OLAP): mal encaje para escrituras transaccionales de eventos.
- Copia de seguridad = copiar un archivo. Para un cliente industrial sin IT dedicado, eso vale oro.

### Estrategia de imágenes: **filesystem, no BLOBs**

| Opción | Veredicto |
|--------|-----------|
| BLOB en SQLite | ❌ La base crece a cientos de GB: el backup por copia de archivo deja de ser viable, `VACUUM` se vuelve una operación de horas, y una corrupción de página se lleva la evidencia **y** los metadatos juntos |
| **Filesystem + ruta relativa en la base** | ✅ **Elegido.** Backup incremental estándar, la base queda en decenas de MB, y evidencia y metadatos fallan por separado |
| Thumbnails (~15 KB) como BLOB | ✅ **Sí, en la base.** Para blobs pequeños SQLite es más rápido que el filesystem; y así la grilla de la UI se pinta con una sola query, sin miles de `open()` |
| Columna | Por qué |
|---------|---------|
| `relative_path` | **Relativa**, nunca absoluta: permite mover el archivo de datos a otro disco sin migrar la base |
| `sha256` | **Tamper-evidence.** Es un producto de auditoría: hay que poder demostrar que la foto no se cambió después. Sin esto, el valor probatorio de la evidencia es débil |
| `captured_at_utc` | UTC ISO-8601 + offset guardado aparte. Nunca hora local suelta |
| `capture_group_id` | Agrupa todas las fotos del mismo disparo. Es la representación de "captura sincronizada" en el modelo de datos |
| `sync_delta_ms` | Desviación real de esa cámara respecto del instante de disparo. Honestidad auditable |
| `camera_id`, `engine`, `model_sha256` | Trazabilidad: qué cámara, qué motor (IA/clásico) y qué modelo exacto produjeron las detecciones |

## Decisión 7 — Empaquetado y distribución

### Veredicto: **PyInstaller `--onedir` + Inno Setup** · Confianza MEDIUM (tamaños estimados, no medidos)

### Tamaño esperado (Windows x64, Python 3.12)

| Componente | Rueda | Instalado (aprox.) |
|------------|-------|--------------------|
| Runtime Python 3.12 | — | ~18 MB |
| PySide6-Essentials (podado a los módulos usados) | 77.5 MB | ~110 MB |
| opencv-python-headless | 43.8 MB | ~110 MB |
| onnxruntime-directml | 25.1 MB | ~110 MB |
| PyAV (FFmpeg embebido) | 27.6 MB | ~70 MB |
| NumPy | 12.4 MB | ~40 MB |
| Modelos ONNX (detector + placa + OCR) | — | ~50–90 MB |
| Resto (SQLAlchemy, Pydantic, etc.) | — | ~25 MB |
| **Total instalado** | | **≈ 530–580 MB** |
| **Instalador comprimido (LZMA2)** | | **≈ 190–260 MB** |

## Installation

# Entorno reproducible

# pyproject.toml

# EXCLUYENTES ENTRE SÍ: exactamente uno por entorno.

# Exportar el detector UNA vez, en la máquina de build (opset 17 por compatibilidad con DirectML)

# Build del producto

## Alternatives Considered

| Recomendado | Alternativa | Cuándo usar la alternativa |
|-------------|-------------|----------------------------|
| Python + PySide6 | C# + Avalonia + OpenCvSharp + `Microsoft.ML.OnnxRuntime` | Si el equipo es .NET-first. Instalador mucho más chico y self-contained; se paga reimplementando todo el pipeline de ALPR |
| Python + PySide6 | C++ + Qt | Si el alcance vuelve a incluir 16+ cámaras con decodificación por hardware e inferencia por lotes. Hoy ese requisito está descartado |
| RF-DETR-Nano | D-FINE-S (Apache-2.0) | Si el export ONNX de RF-DETR da problemas, o si se necesitan checkpoints Objects365 por mejor generalización fuera de COCO |
| RF-DETR-Nano | YOLOX-S (Apache-2.0) | Si se prefiere post-procesamiento YOLO clásico con máxima cantidad de ejemplos de referencia |
| `onnxruntime-directml` | `onnxruntime-gpu` (CUDA/TensorRT) | Cliente con GPU NVIDIA dedicada y necesidad real de throughput. Distribuir como pack separado, nunca como default |
| PyAV | GStreamer | Si en el futuro se suben a >8 streams simultáneos y hace falta pipeline con decodificación por hardware de punta a punta |
| PyInstaller | Nuitka 4.1.3 | Arranque más rápido y binario más difícil de revertir. Licencia AGPL-3.0 **con excepción explícita para los binarios generados** → legalmente usable en producto comercial. Costo: empaquetar PySide6 + OpenCV + ORT es más frágil. Optimización de fase posterior |
| Inno Setup (con licencia paga) | NSIS (zlib) | Si el requisito es costo cero absoluto de herramientas |
| fast-plate-ocr | PaddleOCR exportado a ONNX | Si hay que leer también texto libre de remitos con layout (la digitalización de documentos por webcam podría necesitarlo — evaluar en la fase correspondiente) |
| SQLite + FS | SQLite + FS + réplica a red | Si el cliente exige que la evidencia se replique a un NAS. Agregar como job de sincronización, sin cambiar el modelo |

## What NOT to Use

| Evitar | Por qué | Usar en su lugar |
|--------|---------|------------------|
| **Ultralytics YOLOv5/v8/v11/v12** | **AGPL-3.0**: obliga a publicar el código fuente de la aplicación completa, o a comprar licencia Enterprise por cotización. Incompatible con un producto comercial cerrado | **RF-DETR-Nano/Small (Apache-2.0)** |
| **YOLOv9 (WongKinYiu), YOLOv7** | GPL-3.0 *(verificado)* | RF-DETR / D-FINE / YOLOX |
| **YOLO-NAS / super-gradients** | Código Apache pero **pesos con licencia de investigación no comercial**. Trampa frecuente | RF-DETR |
| **RF-DETR-XL / 2XL** | **PML 1.0**, fuera del paraguas Apache-2.0 del resto del repo | RF-DETR Nano/Small/Medium/Large |
| **DEIM** | GitHub reporta `NOASSERTION` — licencia no identificable | D-FINE (Apache-2.0) |
| **PyQt6** | GPL-3.0 o licencia comercial Riverbank paga | **PySide6** (LGPLv3) |
| **Emgu.CV** (en una hipotética ruta C#) | Dual GPL/comercial paga | OpenCvSharp (Apache-2.0) |
| **OpenALPR original** | AGPL-3.0 + proyecto discontinuado | fast-alpr (MIT) |
| **Servicios ALPR cloud** (Plate Recognizer SaaS, Rekor) | **Violan el requisito de operación offline** de PROJECT.md | Modelos ONNX locales |
| **Tesseract para patentes** | Pensado para texto de documento con layout; falla con fuente ancha, ángulo y reflejos | fast-plate-ocr |
| **EasyOCR** | Arrastra PyTorch (~2–2.5 GB) al instalador para un resultado peor en patentes | fast-plate-ocr |
| **`cv2.VideoCapture` para RTSP** | Ignora `CAP_PROP_BUFFERSIZE` (latencia creciente), timeouts solo por variable de entorno global, y no distingue "frame perdido" de "cámara caída" | **PyAV** |
| **`opencv-python` (no headless) junto a PySide6** | Embebe **Qt5** y choca con el Qt6 de PySide6 → crashes de inicio difíciles de diagnosticar | **`opencv-python-headless`** |
| **`cv2.dnn` como motor de inferencia** | Menos EPs, menos optimizado y sin la selección de provider en runtime que el proyecto necesita | **ONNX Runtime** |
| **Instalar dos paquetes de `onnxruntime`** | Comparten el módulo `onnxruntime`: se pisan y producen fallos silenciosos | Un paquete por entorno, elegido en tiempo de build |
| **Imágenes full-size como BLOB en SQLite** | Base de cientos de GB → backup inviable y `VACUUM` catastrófico | Filesystem + ruta relativa + SHA-256 en la base |
| **PyInstaller `--onefile`** | Debilita el cumplimiento LGPL de Qt, arranque lento y falsos positivos de antivirus | **`--onedir`** |
| **UPX en el build** | Falsos positivos de antivirus por un ahorro marginal | `upx=False` |
| **PySide6 (metapaquete completo)** | ~250 MB de Addons sin uso | **PySide6-Essentials** |
| **Python 3.13t (free-threading)** | Ruedas binarias inmaduras; el GIL no es el cuello de botella acá | Python 3.12 estándar |
| **Exportar ONNX con el opset por defecto de PyTorch** | DirectML soporta hasta ~opset 20/21 → error de "unsupported opset" en el cliente | **`opset_version=17`** |

## Stack Patterns by Variant

- Pack separado con `onnxruntime-gpu==1.27.0` + CUDA 12 + cuDNN 9
- La cadena de EPs pasa a `TensorRT → CUDA → CPU`
- Porque: instalador ~2.5 GB, inaceptable como default, pero un salto real de rendimiento donde hace falta
- `onnxruntime-directml` acelera igual — DirectML corre sobre cualquier GPU DX12
- Porque: es exactamente el caso que CUDA no cubre y que hace a DirectML la elección correcta como default
- Modelos **cuantizados a INT8**, RF-DETR-Nano a 384 px, inferencia de preview decimada a 5 fps
- La inferencia en el momento de la captura corre igual a resolución plena: es un evento, no un stream
- Porque: el requisito es evidencia confiable en el disparo, no 30 fps de análisis continuo
- Mensajes ya definidos como modelos **Pydantic** → serializar con **msgspec**, transportar con **pyzmq** sobre `ipc://`/named pipe
- El dominio no cambia: solo se agrega una implementación del puerto de transporte
- Porque: es precisamente la razón de definir los DTOs con Pydantic desde el día uno
- Porque: cambiar de modelo antes de corregir la captura es gastar semanas para nada

## Version Compatibility

| Paquete A | Compatible con | Notas |
|-----------|----------------|-------|
| `onnxruntime` 1.27.0 | Python **≥3.11** | *Verificado en PyPI.* Descarta Python 3.10 para el runtime de producción |
| `onnxruntime-directml` 1.24.4 | Python 3.11–3.14 (`cp312` ✓) | **Va rezagado** respecto de 1.27.0 → **exportar ONNX con opset 17** |
| `onnxruntime` / `-gpu` / `-directml` | **entre sí: INCOMPATIBLES** | Instalan el mismo módulo. Exactamente uno por entorno |
| `PySide6-Essentials` 6.11.1 | Python ≥3.10,<3.15 · rueda `cp310-abi3` | ABI estable: una sola rueda sirve para 3.10–3.14 |
| `opencv-python-headless` 5.0.0.93 | NumPy 2.x · Python ≥3.6 | OpenCV 5.0 (jun-2026): la API `cv2` es retrocompatible; lo que rompió fue la C API de OpenCV 1.x y módulos contrib. Seguro para Python/CPU |
| `PyAV` 18.0.0 | Python ≥3.11 · rueda `cp311-abi3` | FFmpeg LGPL embebido, sin FFmpeg del sistema |
| `NumPy` 2.5.1 | cv2, ORT, PyAV | Todo el stack está en el ABI de NumPy 2.x. **Verificar que ninguna dependencia transitiva pinee `numpy<2`** antes de congelar el lockfile |
| `fast-alpr` 0.4.0 / `fast-plate-ocr` 1.1.0 / `open-image-models` 0.5.1 | Python ≥3.10 · ORT como backend | No declaran ORT como dependencia dura: se instala vía extras. Coordinar con el EP elegido para no traer una segunda distribución de ORT |
| `PyInstaller` 6.21.0 | Python ≥3.8,<3.16 | Cubre 3.12 sin problema |
| **Versión pinneada de Python** | **3.12.x** | Único punto donde todas las ruedas de arriba tienen build verificado |

## Sources

- https://www.ultralytics.com/license y https://www.ultralytics.com/legal/agpl-3-0-software-license — términos AGPL-3.0 y cuándo se exige Enterprise
- https://github.com/ultralytics/ultralytics/issues/19390 — caso "modelo on-device, sin servicio de red"
- https://onnxruntime.ai/docs/install/ — paquetes disponibles, requisito CUDA 12 + cuDNN 9 separado
- https://onnxruntime.ai/docs/execution-providers/ — registro de EPs y fallback por lista de prioridad
- https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html — DirectML en sustained engineering, opset soportado
- https://github.com/microsoft/onnxruntime/issues/17631 — `providers=` obligatorio desde 1.9/1.16
- https://ankandrew.github.io/fast-plate-ocr/latest/inference/model_zoo/ — model zoo completo, incluidos `argentinian-plates-cnn-model` (94.05 %) y `argentinian-plates-cnn-synth-model` (94.19 %)
- https://rfdetr.roboflow.com/latest/learn/export/ — export ONNX de RF-DETR
- https://github.com/opencv/opencv/wiki/OpenCV-4-to-5-migration — alcance real de los breaking changes de OpenCV 5
- https://jrsoftware.org/isorder.php — licencia comercial de Inno Setup desde 6.5.0
- https://blog.roboflow.com/best-object-detection-models/ — benchmarks RF-DETR/D-FINE (fuente con interés propio en RF-DETR; los números de licencia sí se verificaron aparte)
- https://roboflow.com/models-by-license/apache-2-0-licensed-object-detection · https://www.libreyolo.com/articles/best-ultralytics-alternatives — panorama de alternativas permisivas
- https://www.pythonguis.com/faq/licensing-differences-between-pyqt6-and-pyside6/ — requisitos prácticos de cumplimiento LGPLv3
- https://answers.opencv.org/question/234908/rtsp-streaming-gstreamer-or-ffmpeg/ y foros NVIDIA — latencia RTSP y limitaciones de `VideoCapture`
- Tamaños de instalación y del instalador (derivados de tamaños de rueda × factor de descompresión típico). **Medir en el primer build real y corregir esta tabla.**
- Precisión efectiva del LPR en patentes argentinas en condiciones de la planta: los 94 % son del autor del modelo, en su dataset. **Validar en campo.**

## Riesgos abiertos que el roadmap debe absorber

| # | Riesgo | Impacto | Mitigación / fase |
|---|--------|---------|-------------------|
| 1 | **Pesos del detector de placa derivados de YOLOv9 (GPL-3.0)** pese al código MIT | Alto — legal, bloqueante para vender | Entrenar detector propio de una clase con RF-DETR-Nano/D-FINE-N. **Tarea explícita antes del release comercial** |
| 2 | Precisión real del LPR con patentes AR sucias, mojadas o en ángulo | Alto — es funcionalidad adelantada a v1 por decisión del usuario | Doble lector + validación por regex + votación temporal + confirmación del portero. Especificar óptica e iluminación IR |
| 3 | DirectML en sustained engineering | Medio — a 2–4 años | El puerto `InferenceEngine` aísla el EP. Migrar a Windows ML cuando ORT lo requiera |
| 4 | Tamaño del instalador (~200–260 MB) | Bajo-medio — fricción de venta | Cuantización INT8, poda agresiva de Qt, y CDN para la descarga |
| 5 | Notarización y firma en macOS con PyInstaller | Medio — solo cuando se active macOS | Presupuestar tiempo real; firmar cada `.dylib` embebida |
| 6 | OpenCV 5.0 es reciente (jun-2026) | Bajo | La API `cv2` es retrocompatible. Si aparece algún bug bloqueante, bajar a la última 4.x sin cambios de código |
| 7 | Costo de licencia de Inno Setup | Muy bajo | Comprar (pago único) o usar NSIS |
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:

- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
