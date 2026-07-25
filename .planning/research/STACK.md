# Stack Research

**Domain:** Aplicación de escritorio multiplataforma de visión artificial (multi-cámara + detección de objetos + LPR/ANPR offline) para control de portería logística
**Researched:** 2026-07-24
**Confidence:** HIGH en licencias, versiones y arquitectura de inferencia · MEDIUM en estimaciones de tamaño de instalador y precisión real de LPR sobre patentes argentinas

> **Nota metodológica.** El seam `gsd-tools query research-plan` no está disponible en este entorno (`command not found`), por lo que la investigación se hizo con búsqueda web + fetch directo a PyPI/GitHub API/documentación oficial. Todas las versiones y licencias de esta página fueron verificadas contra la API de PyPI y la API de GitHub el 2026-07-24, no contra datos de entrenamiento. Los niveles de confianza están declarados por afirmación.

---

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

---

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

---

## Decisión 1 — Lenguaje y framework de UI

### Veredicto: **Python 3.12 + PySide6** · Confianza HIGH

La pregunta real no es "qué lenguaje es mejor" sino **dónde vive el ecosistema de ALPR y de post-procesamiento de detección**. La respuesta es Python, y no está cerca.

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

**Por qué gana Python pese a ser el más pesado de empaquetar:**

1. **El GIL no es el problema que la gente cree acá.** Decodificación (PyAV/FFmpeg), operaciones OpenCV y `InferenceSession.run()` **liberan el GIL**. El código Python solo orquesta. Con 2–3 cámaras HD y captura por evento, el intérprete está ocioso el 95 % del tiempo.
2. **La escala descartada en PROJECT.md lo confirma.** Se descartó explícitamente el escenario de 16+ cámaras. El único argumento fuerte a favor de C++/Rust —decenas de streams con decodificación por hardware e inferencia por lotes— fue eliminado del alcance por decisión de negocio.
3. **El costo de irse de Python es el LPR.** En C#, Rust o C++ hay que reimplementar a mano el pre/post-procesamiento de detección de placa y el decodificador CTC del OCR, y no existen modelos ONNX de patentes empaquetados y listos. Eso son semanas contra horas.
4. **LGPLv3 de PySide6 es compatible con producto comercial cerrado**, siempre que se cumplan tres cosas concretas (ver "Cumplimiento LGPL" abajo).

**Segunda opción explícita:** si el equipo es fuerte en .NET y débil en Python, la ruta viable es **C# + Avalonia + `Microsoft.ML.OnnxRuntime` + OpenCvSharp (Apache-2.0)**. Se paga con el ALPR, que habría que construir desde cero. **No usar Emgu.CV** en esa ruta: es dual GPL/comercial y su licencia paga es un costo recurrente por producto.

**Descartadas sin ambigüedad:**
- **Rust + Tauri** — mover frames de video a un webview es la peor arquitectura posible para esta app; además `opencv-rust` en Windows es un dolor de build y no hay ecosistema ALPR.
- **Rust + egui/slint** — inmaduros para superficies de video multi-panel; slint además es GPL/comercial/Royalty-free-con-condiciones, no una licencia permisiva simple.
- **Electron / interfaz web** — descartado también por PROJECT.md ("Aplicación móvil o interfaz web" está en Out of Scope).
- **Tkinter, Kivy, wxPython** — no producen una UI de calidad de producto vendible con layouts de video configurables.

### Render de múltiples streams en Qt — patrón concreto

No usar `QLabel.setPixmap` en un loop: recrea texturas y satura el main thread.

- Un `QWidget` por cámara con `paintEvent` que dibuja un `QImage` construido **sin copia** sobre el buffer del `numpy.ndarray` BGR: `QImage(buf.data, w, h, buf.strides[0], QImage.Format_BGR888)`. Qt tiene formato BGR888 nativo → **cero `cv2.cvtColor` por frame**.
- Un `QThread`/`threading.Thread` por cámara para decodificar, y una `queue.Queue(maxsize=1)` con política *drop-oldest*: si la UI no alcanza, se descartan frames viejos en vez de acumular latencia. Este es el mecanismo que evita el clásico "el video se atrasa cada vez más".
- Señal Qt (`Signal(object)`) del hilo de captura al widget. Nunca tocar widgets desde hilos que no son el main.
- La grilla 1 / 2x2 / 3x3 / 4x4 se implementa con `QGridLayout` reconfigurable, no con widgets distintos por layout.

### Cumplimiento LGPLv3 de PySide6 (obligatorio para vender)

1. **Enlace dinámico** — se cumple solo: Python importa `PySide6` como paquete con DLLs separadas.
2. **El usuario debe poder reemplazar las DLLs de Qt** — por eso **`--onedir` de PyInstaller, no `--onefile`**. En `onedir` las `Qt6*.dll` quedan visibles y sustituibles; en `onefile` se extraen a un temporal y el argumento de "relinkeo" se vuelve muy débil legalmente.
3. **Incluir el texto de la LGPLv3, avisar qué componentes la usan y ofrecer el fuente de PySide6/Qt** (basta un enlace/oferta escrita a `download.qt.io`). Poner un `THIRD-PARTY-LICENSES.txt` en el instalador y un diálogo "Acerca de → Licencias" en la UI.
4. No modificar PySide6/Qt. Si se modifican, hay que publicar esas modificaciones (solo esas, no la app).

---

## Decisión 2 — ONNX Runtime y execution providers

### Veredicto Windows: **una sola build, `onnxruntime-directml`** · Confianza HIGH

Este es el hallazgo con más impacto en el instalador.

**Hecho estructural verificado:** `onnxruntime`, `onnxruntime-gpu` y `onnxruntime-directml` **instalan el mismo módulo `onnxruntime` y son mutuamente excluyentes**. No se pueden combinar. Por lo tanto, "GPU si existe, CPU si no" **no** se resuelve instalando dos paquetes: se resuelve eligiendo **una** distribución que contenga ambos EPs.

| Paquete | Versión | Rueda `cp312-win_amd64` | EPs incluidos | Dependencias externas |
|---------|---------|------------------------|---------------|-----------------------|
| `onnxruntime` | 1.27.0 | **13.4 MB** | CPU (+ CoreML en macOS) | ninguna |
| `onnxruntime-directml` | 1.24.4 | **25.1 MB** | **DirectML + CPU** | **ninguna** — DirectML viene con Windows 10 1903+ / se redistribuye la DLL |
| `onnxruntime-gpu` | 1.27.0 | **213.6 MB** | CUDA + TensorRT + CPU | **CUDA 12.x + cuDNN 9 (~1.5–2.5 GB)** |

**Por qué DirectML es la elección correcta para el instalador principal de Windows:**

- Acelera sobre **cualquier GPU DirectX 12**: NVIDIA, AMD **e Intel iGPU**. En una PC de portería industrial, lo más probable es una integrada Intel/AMD — CUDA no serviría ahí, DirectML sí.
- **Cero redistribuibles.** El paquete CUDA agrega 1.5–2.5 GB al instalador y obliga a validar versión de driver del cliente. Inaceptable para un producto que se instala en plantas.
- Contiene también el CPU EP → una sola build cubre "con y sin GPU", que es literalmente el requisito de PROJECT.md.

**Costos honestos de DirectML:**
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

Hay dos trampas verificadas y hay que cubrir las dos:

1. Desde ORT 1.9 es **obligatorio** pasar `providers=`. Y si se pasa un provider que **no está compilado** en la build, `InferenceSession` lanza `ValueError: ... is not in available provider names`. → Hay que **intersectar** con `get_available_providers()`.
2. `get_available_providers()` informa qué está **compilado**, no qué está **funcional**. `CUDAExecutionProvider` puede aparecer listado y fallar igual porque falta el driver o la cuDNN. → Hay que **probar de verdad** con una sesión de calentamiento y verificar qué provider quedó activo.

```python
# core/inference/provider_selector.py  — sin dependencias de UI
import logging
import onnxruntime as ort

log = logging.getLogger(__name__)

PREFERENCE = [
    "TensorrtExecutionProvider",
    "CUDAExecutionProvider",
    "DmlExecutionProvider",       # Windows, cualquier GPU DX12
    "CoreMLExecutionProvider",    # macOS
    "OpenVINOExecutionProvider",  # Intel en Linux
    "CPUExecutionProvider",       # último recurso, siempre presente
]

def build_session(model_path: str, forced: str | None = None) -> ort.InferenceSession:
    """Devuelve una sesión sobre el mejor EP que REALMENTE funcione.

    Trampa 1: filtrar contra get_available_providers() -> evita ValueError.
    Trampa 2: get_available_providers() dice 'compilado', no 'funcional'
              -> se valida creando la sesión y confirmando el EP activo.
    """
    compiled = set(ort.get_available_providers())
    candidates = [forced] if forced in compiled else [p for p in PREFERENCE if p in compiled]

    opts = ort.SessionOptions()
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    opts.log_severity_level = 3  # silencia el ruido de EPs que no enganchan

    for provider in candidates:
        try:
            sess = ort.InferenceSession(model_path, sess_options=opts, providers=[provider])
            active = sess.get_providers()[0]
            if active != provider:
                log.info("EP %s degradó a %s, se prueba el siguiente", provider, active)
                continue
            log.info("Execution provider activo: %s", active)
            return sess
        except Exception as exc:                      # noqa: BLE001 — la falla de un EP nunca debe matar la app
            log.warning("EP %s no utilizable (%s), se prueba el siguiente", provider, exc)

    raise RuntimeError("Ningún execution provider utilizable, ni siquiera CPU")
```

Complementos obligatorios:
- **Calentar** la sesión con un tensor dummy al arrancar. La primera inferencia de DirectML/CUDA compila kernels y tarda 1–3 s; que eso pase durante la captura de evidencia es inaceptable.
- **Persistir el EP elegido** y mostrarlo en la UI ("Motor: GPU DirectML / CPU"). Es información de soporte técnico en campo.
- **Permitir forzar CPU** desde configuración. Los drivers de GPU rotos son una realidad en plantas industriales y necesitás una vía de escape sin reinstalar.
- `intra_op_num_threads` limitado (p. ej. 4) si se corre en CPU, para no dejar sin CPU al hilo de decodificación de video.

---

## Decisión 3 — Modelo de detección · **LA LICENCIA ESTÁ RESUELTA, SIN AMBIGÜEDAD**

### 🔴 NO usar Ultralytics. Ni YOLOv5, ni v8, ni v11, ni v12. · Confianza HIGH

**Los hechos, verificados en la documentación legal de Ultralytics:**

- Ultralytics publica bajo **AGPL-3.0** *o* licencia Enterprise paga. No hay tercera opción.
- La AGPL-3.0 aplicada por Ultralytics exige **liberar el código fuente completo de la obra derivada — la aplicación entera, no solo el módulo de visión** — incluyendo scripts, archivos de configuración y, cuando corresponde, los pesos del modelo.
- Ultralytics declara explícitamente que la licencia Enterprise **es necesaria si la solución final es propietaria y se usa internamente en una empresa o comercialmente**.
- El uso de **modelos preentrenados** también cae bajo AGPL: no hay excepción por "solo uso de inferencia" ni por "no es un servicio de red". Existe un issue público (`ultralytics#19390`) planteando justamente el caso de modelo on-device sin servicio de red, y la posición del proyecto no habilita la excepción.

**Traducción a este proyecto:** PROJECT.md dice, textualmente, *"Es un producto destinado a comercializarse, no de uso interno exclusivo."* Usar Ultralytics obliga a **publicar el código de la aplicación de portería completa bajo AGPL-3.0** (destruye el modelo de negocio) **o** a comprar una licencia Enterprise (precio por cotización, no publicado, y con riesgo de renegociación con el crecimiento del producto). **Ambas son inaceptables. La decisión es no usarlo.**

**También prohibidos por la misma razón:**

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

**Por qué RF-DETR:**
- **Apache-2.0 sobre código y sobre los checkpoints base** (Nano→Large). Cero obligaciones copyleft, cero regalías, patente concedida explícitamente por la licencia.
- Estado del arte real en 2026 en el punto de operación tiempo real: RF-DETR-Nano supera en AP a modelos YOLO mucho más pesados.
- **Sin NMS.** Es un DETR: el post-procesamiento es sigmoid + top-k, más simple, más determinista y sin el hiperparámetro `iou_threshold` que suele romper casos borde. Menos código propio que mantener.
- Export a ONNX oficial (`model.export(format="onnx")`), compatible con ONNX Runtime y con `cv2.dnn`.
- Repo vivo: último push 2026-07-24, 8.7k estrellas *(verificado por GitHub API)*.
- Las clases que el proyecto necesita —`person`, `car`, `truck`, `bus`— vienen en COCO. PROJECT.md ya descartó entrenar modelos propios; con COCO alcanza.

**Alternativas permisivas de respaldo (todas Apache-2.0, todas comercialmente seguras):**

| Alternativa | Licencia | Cuándo usarla en vez de RF-DETR |
|-------------|----------|--------------------------------|
| **D-FINE** (N/S/M/L/X) | **Apache-2.0** *(verificado)* — D-FINE-S: 48.5 AP, 3.49 ms | Si RF-DETR da problemas en el export ONNX o si se prefiere un repo con checkpoints Objects365 preentrenados (generaliza mejor fuera de COCO) |
| **YOLOX** (Nano→X) | **Apache-2.0** *(verificado)* | Si se quiere el post-procesamiento YOLO clásico y máxima cantidad de ejemplos de deployment. Costo: es de 2021, YOLOX-x llega a 51.1 mAP con muchísimos más parámetros que RF-DETR-Small |
| **RTMDet** (MMDetection) | **Apache-2.0** | Si ya se usa el toolchain de OpenMMLab. Costo: mmdetection sin push desde 2024 |

### Consecuencia arquitectónica (para el roadmap)

Definir un puerto `ObjectDetector` en el núcleo con implementaciones intercambiables (`RfDetrOnnxDetector`, `YoloxOnnxDetector`, `OpenCvClassicDetector`). El motor dual IA/clásico que pide PROJECT.md **es exactamente esta interfaz**, y además convierte una eventual sustitución de modelo en un cambio de una línea de configuración. Los archivos `.onnx` van versionados y hasheados (SHA-256) para poder auditar qué modelo generó qué evidencia.

---

## Decisión 4 — LPR / ANPR

### Veredicto: **fast-alpr (MIT) con reemplazo planificado del detector de placa** · Confianza MEDIUM

**El stack elegido:**

```
frame → detector de placa (ONNX) → recorte + rectificación → OCR (ONNX) → validación de formato AR
```

| Componente | Paquete | Licencia código | Modelo |
|------------|---------|-----------------|--------|
| Orquestación | `fast-alpr` 0.4.0 | **MIT** *(verificado)* | — |
| Detección de placa | `open-image-models` 0.5.1 | **MIT** *(verificado)* | ⚠️ **arquitectura YOLOv9** |
| OCR | `fast-plate-ocr` 1.1.0 | **MIT** *(verificado)* | CCT, propios del autor |

**Modelos OCR disponibles y cuál elegir** *(verificado en el model zoo oficial)*:

| Modelo | Cobertura | Precisión | Uso recomendado |
|--------|-----------|-----------|-----------------|
| `cct-s-v2-global-model` | 65+ países, con reconocimiento de región | — (recomendado oficial) | **Default.** Cubre Mercosur `AA123AA` y el formato viejo `ABC123` |
| `cct-xs-v2-global-model` | 65+ países | — | Si el hardware es muy limitado (2144 PPS) |
| `argentinian-plates-cnn-synth-model` | **Argentina** (real + sintético) | **94.19 %** | **Segundo lector.** Especializado en AR |
| `argentinian-plates-cnn-model` | **Argentina pre-2020** | 94.05 % | Solo si la flota es mayoritariamente de patentes viejas |
| `global-plates-mobile-vit-v2-model` | 65+ países | 93.3 % | Legacy, sin ventaja sobre CCT v2 |

**Estrategia prescriptiva para patentes argentinas:**

1. Correr **`cct-s-v2-global-model`** como lector primario.
2. Correr en paralelo **`argentinian-plates-cnn-synth-model`** (es barato: 476 PPS) y **cruzar los resultados**. Si coinciden → confianza alta, autoselección del viaje. Si difieren → mostrar ambos al portero y pedir confirmación.
3. **Validar el formato con regex de dominio** — esto sube la precisión efectiva muy por encima del 94 % bruto del OCR, porque descarta lecturas imposibles:
   - Mercosur (desde 2016): `^[A-Z]{2}\d{3}[A-Z]{2}$`
   - Formato anterior: `^[A-Z]{3}\d{3}$`
   - Aplicar corrección de confusiones posicionales típicas: `0↔O`, `1↔I`, `8↔B`, `5↔S`, `2↔Z` — **según la posición**, ya que en cada posición el formato ya dice si toca letra o dígito. Esto es determinista y sin IA.
4. **Nunca autoconfirmar en base a una sola lectura.** El LPR asiste al portero, no lo reemplaza: acumular N lecturas del stream en una ventana de ~2 s y usar votación por mayoría antes de proponer el viaje.

### ⚠️ El riesgo de licencia que hay que cerrar antes de vender

El código de `open-image-models` es **MIT**, pero sus modelos de detección de placa son **arquitectura YOLOv9**, y el repositorio original de YOLOv9 (WongKinYiu) es **GPL-3.0** *(verificado por GitHub API)*. El repo no publica una licencia separada para los pesos.

Si los pesos se derivan de la implementación GPL-3.0 es una zona legal gris: la doctrina sobre si los pesos entrenados son obra derivada del código de entrenamiento no está saldada. **Para un producto que se vende, la zona gris no es una posición defendible.**

**Plan de mitigación, en orden:**

1. **v1 / prototipo:** usar `open-image-models` tal cual. Acelera la validación funcional y el riesgo es nulo mientras no haya distribución comercial.
2. **Antes del release comercial (tarea explícita del roadmap):** entrenar un detector de placa propio con **RF-DETR-Nano o D-FINE-N (Apache-2.0)** sobre un dataset abierto de patentes (hay varios en Roboflow Universe bajo CC BY 4.0; verificar la licencia de cada dataset). Es un detector de **una sola clase** sobre un objeto muy regular: unas pocas miles de imágenes alcanzan y el entrenamiento es de horas, no semanas. Esto deja la cadena de procedencia **100 % permisiva y auditable**.
3. **Plan B si la precisión propia no alcanza:** SDK on-premise comercial (Plate Recognizer Snapshot on-prem, licencia por cámara). Cumple el requisito offline pero introduce costo recurrente y una dependencia de proveedor. Solo si 1 y 2 fallan.

El OCR (`fast-plate-ocr`) **no tiene este problema**: los modelos CCT fueron entrenados y publicados por el propio autor bajo MIT, y el proyecto además permite entrenar desde cero — vía limpia para fine-tunear con imágenes reales de la portería si la precisión en campo lo exige.

### Alternativas de OCR evaluadas y descartadas

| Opción | Licencia | Por qué no |
|--------|----------|-----------|
| **Tesseract** | Apache-2.0 | Diseñado para texto de documentos con layout. En patentes (fuente ancha, ruido, ángulo, reflejos) rinde mal aun con preprocesado agresivo. No es el problema para el que fue hecho |
| **EasyOCR** | Apache-2.0 | Arrastra **PyTorch (~2–2.5 GB)** al instalador. OCR genérico, sin especialización en patentes. Duplicaría el tamaño del producto por peor resultado |
| **PaddleOCR** | Apache-2.0 | Excelente OCR, pero es genérico y el runtime PaddlePaddle es enorme. Vía ONNX exportado sería viable, pero sigue siendo mucho más pesado y menos preciso que un modelo específico de patentes |
| **OpenALPR (original)** | **AGPL-3.0** | Misma trampa comercial que Ultralytics. Además el proyecto abierto está discontinuado |
| **Plate Recognizer / Rekor cloud** | Comercial SaaS | **Viola el requisito de operación offline** de PROJECT.md |

**Nota de hardware que impacta más que el modelo:** en LPR, la iluminación y la óptica pesan más que el algoritmo. PROJECT.md ya contempla una cámara dedicada. Especificar: **iluminador IR 850 nm + obturador rápido (1/1000 s o menos) + lente que dé ≥ 100 px de ancho de placa** en el punto de lectura. Ninguna elección de modelo compensa una placa de 40 px movida.

---

## Decisión 5 — Captura RTSP

### Veredicto: **PyAV para IP, OpenCV para USB y archivos** · Confianza MEDIUM-HIGH

| Opción | Veredicto | Razón |
|--------|-----------|-------|
| **PyAV 18.0.0** (BSD-3, FFmpeg LGPL embebido) | ✅ **Primaria para RTSP** | Control real sobre las opciones de FFmpeg, timeouts, acceso a paquetes y timestamps, y **excepciones Python limpias** cuando el stream muere — que es lo que la lógica de reconexión necesita |
| **`cv2.VideoCapture(url)`** | ⚠️ **Solo webcam USB y archivos** | Envuelve FFmpeg pero no expone casi nada. `CAP_PROP_BUFFERSIZE` es **ignorado** por el backend FFmpeg (de ahí la latencia creciente clásica). Los timeouts solo se configuran por la variable de entorno global `OPENCV_FFMPEG_CAPTURE_OPTIONS`, que es proceso-global y no por cámara. Y ante fallo devuelve `False`, sin causa: no se puede distinguir "frame perdido" de "cámara caída" |
| **GStreamer** | ❌ No | Es la opción más potente y la de menor latencia con pipelines afinados, pero exige **instalar y redistribuir el runtime GStreamer en cada plataforma** y OpenCV con GStreamer habilitado (las ruedas de PyPI no lo traen: hay que compilar OpenCV). Ese costo se justifica con decenas de streams — escala que PROJECT.md descartó explícitamente |
| **FFmpeg CLI por subproceso** | ❌ No | Parsear stdout de un proceso hijo, gestionar zombies y sincronizar timestamps es reimplementar peor lo que PyAV ya hace enlazado |

**Licencias:** PyAV es **BSD-3-Clause** y sus ruedas embeben **FFmpeg bajo LGPL** (build sin `--enable-gpl`, es decir sin x264/x265). Para *decodificar* H.264/H.265 alcanza con los decodificadores nativos LGPL de libavcodec. Cumple con producto comercial cerrado siempre que se enlace dinámicamente y se incluya el aviso LGPL. Las ruedas de `opencv-python` también embeben **FFmpeg LGPLv2.1** *(verificado en la descripción del paquete)*.

### Patrón de captura robusta

```python
# core/video/rtsp_source.py — sin dependencias de UI
import av

OPTS = {
    "rtsp_transport": "tcp",   # UDP pierde paquetes y H.264 corrupto tira el stream entero
    "stimeout":       "5000000",  # 5 s en microsegundos: timeout de socket
    "max_delay":      "500000",   # 0.5 s
    "fflags":         "nobuffer",
    "flags":          "low_delay",
    "reorder_queue_size": "0",
}

container = av.open(url, options=OPTS, timeout=(5.0, 5.0))
stream = container.streams.video[0]
stream.thread_type = "AUTO"   # decodificación multi-hilo, libera el GIL
```

Reglas de operación, todas derivadas del requisito "reconectar sin detener el resto del sistema":

- **Un hilo por cámara, aislado.** Una excepción en una cámara nunca puede tumbar a las otras ni a la UI.
- **Reconexión con backoff exponencial + jitter** (1 s → 2 s → 4 s → … tope 30 s). Sin jitter, N cámaras caídas por un corte de switch reconectan en fase y golpean la red a la vez.
- **Watchdog por keyframe**, no por excepción. Muchas cámaras IP no cierran el socket cuando se cuelgan: siguen abiertas y dejan de mandar. Si pasan >5 s sin frame nuevo, cerrar y reconectar aunque no haya habido error.
- **Buffer de profundidad 1 con drop-oldest.** Nunca acumular frames: para evidencia importa el frame *actual*, no la secuencia completa.
- **Frame de captura ≠ frame de preview.** El preview puede ir a 10–15 fps decimados; en el momento del botón de captura hay que tomar el frame **más reciente** de cada fuente y sellar el timestamp común. La "sincronización" que pide el negocio es *un único instante de disparo con tolerancia declarada*, no genlock de hardware. Registrar en la base el delta real entre cámaras (p. ej. ±80 ms) — eso es lo que hace la evidencia auditable.

**Decodificación por hardware (D3D11VA/DXVA2 en Windows, VideoToolbox en macOS, VAAPI en Linux):** **dejarla desactivada por defecto**, expuesta como opción. Con 2–3 streams 1080p H.264, la decodificación por software consume un porcentaje bajo de un CPU moderno, y el hardware decode obliga a copiar el frame de VRAM a RAM para poder procesarlo con OpenCV/ORT-CPU — copia que se come buena parte del ahorro y agrega una fuente de bugs específicos por driver. Es una optimización de fase posterior, con métrica que la justifique.

---

## Decisión 6 — Persistencia local

### Veredicto: **SQLite + imágenes en filesystem con hash** · Confianza HIGH

**Motor: SQLite** (dominio público, sin licencia que gestionar), vía `sqlite3` de la stdlib, con `SQLAlchemy 2.0.51` (MIT) encima y `Alembic` para migraciones.

Configuración obligatoria al abrir la conexión:

```sql
PRAGMA journal_mode = WAL;      -- lectores concurrentes sin bloquear al escritor
PRAGMA synchronous = NORMAL;    -- durabilidad correcta con WAL, mucho más rápido que FULL
PRAGMA foreign_keys = ON;       -- SQLite las tiene APAGADAS por defecto (trampa clásica)
PRAGMA busy_timeout = 5000;
```

**Por qué SQLite y no otra cosa:**
- Un puesto de portería = un proceso escritor. Postgres/MySQL embebidos serían operaciones que el cliente no puede administrar.
- DuckDB es analítico (OLAP): mal encaje para escrituras transaccionales de eventos.
- Copia de seguridad = copiar un archivo. Para un cliente industrial sin IT dedicado, eso vale oro.

### Estrategia de imágenes: **filesystem, no BLOBs**

**Dimensionamiento:** 50 camiones/día × 3 fotos × ~600 KB (JPEG 1080p q85) ≈ **90 MB/día ≈ 33 GB/año ≈ 165 GB a 5 años**, con ~275.000 archivos.

| Opción | Veredicto |
|--------|-----------|
| BLOB en SQLite | ❌ La base crece a cientos de GB: el backup por copia de archivo deja de ser viable, `VACUUM` se vuelve una operación de horas, y una corrupción de página se lleva la evidencia **y** los metadatos juntos |
| **Filesystem + ruta relativa en la base** | ✅ **Elegido.** Backup incremental estándar, la base queda en decenas de MB, y evidencia y metadatos fallan por separado |
| Thumbnails (~15 KB) como BLOB | ✅ **Sí, en la base.** Para blobs pequeños SQLite es más rápido que el filesystem; y así la grilla de la UI se pinta con una sola query, sin miles de `open()` |

**Layout y esquema:**

```
%PROGRAMDATA%/PorteriaVision/evidence/2026/07/24/<trip_id>/<camera_id>_<utc_ts>.jpg
```

| Columna | Por qué |
|---------|---------|
| `relative_path` | **Relativa**, nunca absoluta: permite mover el archivo de datos a otro disco sin migrar la base |
| `sha256` | **Tamper-evidence.** Es un producto de auditoría: hay que poder demostrar que la foto no se cambió después. Sin esto, el valor probatorio de la evidencia es débil |
| `captured_at_utc` | UTC ISO-8601 + offset guardado aparte. Nunca hora local suelta |
| `capture_group_id` | Agrupa todas las fotos del mismo disparo. Es la representación de "captura sincronizada" en el modelo de datos |
| `sync_delta_ms` | Desviación real de esa cámara respecto del instante de disparo. Honestidad auditable |
| `camera_id`, `engine`, `model_sha256` | Trazabilidad: qué cámara, qué motor (IA/clásico) y qué modelo exacto produjeron las detecciones |

Reglas adicionales: escritura **atómica** (escribir `.tmp` + `os.replace()`), retención configurable con purga (la evidencia vieja se archiva o borra según política del cliente), y `PRAGMA integrity_check` al arrancar con aviso claro al usuario si falla.

---

## Decisión 7 — Empaquetado y distribución

### Veredicto: **PyInstaller `--onedir` + Inno Setup** · Confianza MEDIUM (tamaños estimados, no medidos)

**Cadena:** `uv` (lockfile) → `PyInstaller 6.21.0 --onedir` → firma Authenticode → `Inno Setup 7`.

**Licencia de PyInstaller:** GPLv2-or-later **con una excepción explícita** que permite empaquetar aplicaciones propietarias sin que el bootloader contamine la app *(verificado en el clasificador de PyPI)*. Es la excepción que hace legal usarlo comercialmente.

**`--onedir`, no `--onefile`.** Tres razones, en orden de peso:
1. **Cumplimiento LGPL de PySide6** — las DLLs de Qt tienen que quedar reemplazables por el usuario.
2. **Arranque** — `onefile` descomprime ~500 MB a un directorio temporal en cada ejecución: segundos de espera y desgaste de disco.
3. **Antivirus** — los ejecutables `onefile` autoextraíbles son un patrón que los EDR corporativos marcan como sospechoso.

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

**Variante CUDA (opt-in), como contraste:** `onnxruntime-gpu` es una rueda de **213.6 MB** y además **requiere CUDA 12.x + cuDNN 9 instalados aparte** *(verificado en la doc oficial de ORT)*, lo que agrega **1.5–2.5 GB**. Un instalador de ~2.5 GB para plantas industriales es inaceptable como default. Publicarlo como descarga separada "PorteriaVision – NVIDIA GPU Pack" para los clientes que tengan hardware NVIDIA y lo pidan.

**Reducciones concretas de tamaño, en orden de retorno:**
1. `PySide6-Essentials` en lugar de `PySide6` — ahorra ~250 MB.
2. `--exclude-module` para QtWebEngine, QtQuick3D, QtCharts, QtDataVisualization, QtBluetooth, QtNfc, QtSql (no se usa: SQLite entra por Python), QtTest, QtDesigner.
3. `opencv-python-headless` en lugar de `opencv-python` — evita duplicar Qt5 y ahorra conflictos además de MB.
4. Cuantizar los modelos ONNX a **INT8** con `onnxruntime.quantization` — reduce ~4× el tamaño de modelo y acelera el CPU EP. Validar la caída de precisión antes de adoptarlo, sobre todo en OCR de patentes.
5. `upx=False` en PyInstaller: UPX dispara falsos positivos de antivirus. El ahorro no compensa el ticket de soporte.

**Inno Setup 7.0.2** — desde 6.5.0 los autores **piden licencia comercial paga** para uso comercial (perpetua, pago único, incluye 2 años de actualizaciones). El costo es bajo y la DX es muy superior a las alternativas: **comprarla**. Si el presupuesto tiene que ser cero, la alternativa es **NSIS** (licencia zlib, comercial sin restricciones ni costo) a cambio de un lenguaje de scripting bastante más áspero.

**Firma de código: no opcional.** Sin Authenticode, SmartScreen muestra "aplicación no reconocida" y el instalador de un producto comercial pierde toda credibilidad frente al IT del cliente. Los certificados OV exigen token de hardware/HSM desde 2023; **Azure Trusted Signing** evita el hardware y es la vía más práctica hoy. Firmar el `.exe` de la app **y** el instalador.

**Linux/macOS (fase posterior):** Linux → AppImage o Flatpak (Flatpak simplifica las dependencias de FFmpeg/Qt). macOS → `.app` + `.dmg`, **con notarización obligatoria de Apple**, y firmar todas las `.dylib` embebidas (PyInstaller y la firma de macOS conviven mal; presupuestar tiempo real para esto, no un día).

---

## Installation

```bash
# Entorno reproducible
uv init && uv venv --python 3.12
```

```toml
# pyproject.toml
[project]
requires-python = ">=3.12,<3.13"
dependencies = [
  "PySide6-Essentials==6.11.1",   # LGPLv3 — UI
  "opencv-python-headless==5.0.0.93",  # Apache-2.0 — visión clásica (headless: no arrastra Qt5)
  "av==18.0.0",                   # BSD-3 — RTSP
  "numpy==2.5.1",                 # BSD-3
  "SQLAlchemy==2.0.51",           # MIT
  "alembic~=1.16",                # MIT
  "pydantic==2.13.4",             # MIT
  "pydantic-settings~=2.0",       # MIT
  "fast-alpr==0.4.0",             # MIT — pipeline ALPR
]

[project.optional-dependencies]
# EXCLUYENTES ENTRE SÍ: exactamente uno por entorno.
win-default = ["onnxruntime-directml==1.24.4"]  # CPU + cualquier GPU DX12. Default de Windows
nvidia      = ["onnxruntime-gpu==1.27.0"]       # requiere CUDA 12 + cuDNN 9 aparte
posix       = ["onnxruntime==1.27.0"]           # Linux CPU / macOS (CoreML incluido)

[dependency-groups]
dev = [
  "rfdetr==1.8.3",        # solo para exportar el .onnx — NO va al instalador
  "pyinstaller==6.21.0",
  "pytest", "pytest-qt==4.5.0", "ruff==0.16.0",
]
```

```bash
uv sync --extra win-default --group dev

# Exportar el detector UNA vez, en la máquina de build (opset 17 por compatibilidad con DirectML)
uv run python -c "
from rfdetr import RFDETRNano
RFDETRNano().export(format='onnx', opset_version=17, output_dir='assets/models')
"
```

```powershell
# Build del producto
uv run pyinstaller porteria.spec --noconfirm    # spec con onedir, excludes y datas
signtool sign /fd SHA256 /tr http://timestamp.acs.microsoft.com dist\PorteriaVision\PorteriaVision.exe
iscc installer\porteria.iss
```

---

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

---

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

---

## Stack Patterns by Variant

**Si el cliente tiene GPU NVIDIA dedicada y exige throughput:**
- Pack separado con `onnxruntime-gpu==1.27.0` + CUDA 12 + cuDNN 9
- La cadena de EPs pasa a `TensorRT → CUDA → CPU`
- Porque: instalador ~2.5 GB, inaceptable como default, pero un salto real de rendimiento donde hace falta

**Si el equipo destino solo tiene iGPU Intel/AMD (el escenario más probable en portería):**
- `onnxruntime-directml` acelera igual — DirectML corre sobre cualquier GPU DX12
- Porque: es exactamente el caso que CUDA no cubre y que hace a DirectML la elección correcta como default

**Si el equipo destino es CPU pura y vieja:**
- Modelos **cuantizados a INT8**, RF-DETR-Nano a 384 px, inferencia de preview decimada a 5 fps
- La inferencia en el momento de la captura corre igual a resolución plena: es un evento, no un stream
- Porque: el requisito es evidencia confiable en el disparo, no 30 fps de análisis continuo

**Si más adelante el núcleo se extrae a proceso separado (decisión ya prevista en PROJECT.md):**
- Mensajes ya definidos como modelos **Pydantic** → serializar con **msgspec**, transportar con **pyzmq** sobre `ipc://`/named pipe
- El dominio no cambia: solo se agrega una implementación del puerto de transporte
- Porque: es precisamente la razón de definir los DTOs con Pydantic desde el día uno

**Si el LPR no alcanza la precisión requerida en campo:**
1. Primero: revisar iluminación IR, obturador y píxeles por placa — casi siempre el problema es óptico
2. Segundo: fine-tune de `fast-plate-ocr` (MIT, entrenable) con imágenes reales de la portería
3. Último recurso: SDK comercial on-premise
- Porque: cambiar de modelo antes de corregir la captura es gastar semanas para nada

---

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

---

## Sources

Todo verificado el **2026-07-24**.

**HIGH — API oficial de PyPI (`pypi.org/pypi/<pkg>/json`), versiones, licencias y tamaños de rueda:**
`PySide6` 6.11.1 · `PySide6-Essentials` 6.11.1 (77.5 MB) · `onnxruntime` 1.27.0 (13.4 MB, MIT, py≥3.11) · `onnxruntime-directml` 1.24.4 (25.1 MB) · `onnxruntime-gpu` 1.27.0 (213.6 MB) · `opencv-python` / `-headless` 5.0.0.93 (Apache-2.0, FFmpeg LGPLv2.1) · `av` 18.0.0 (BSD-3) · `numpy` 2.5.1 · `fast-alpr` 0.4.0 (MIT) · `fast-plate-ocr` 1.1.0 (MIT) · `open-image-models` 0.5.1 (MIT) · `rfdetr` 1.8.3 (Apache-2.0) · `pyinstaller` 6.21.0 · `Nuitka` 4.1.3 · `SQLAlchemy` 2.0.51 · `pydantic` 2.13.4 · `pyzmq` 27.1.0 · `msgspec` 0.21.1 · `onvif-zeep-async` 4.2.1 · `pytest-qt` 4.5.0 · `ruff` 0.16.0

**HIGH — API oficial de GitHub (licencia SPDX + última actividad):**
`roboflow/rf-detr` Apache-2.0, push 2026-07-24 · `Peterande/D-FINE` Apache-2.0, push 2026-07-09 · `Megvii-BaseDetection/YOLOX` Apache-2.0 · `WongKinYiu/yolov9` **GPL-3.0** · `Intellindust-AI-Lab/DEIM` **NOASSERTION** · `ankandrew/{fast-alpr,fast-plate-ocr,open-image-models}` MIT · `open-mmlab/mmdetection` Apache-2.0

**HIGH — documentación oficial:**
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

**MEDIUM — análisis y comparativas de terceros:**
- https://blog.roboflow.com/best-object-detection-models/ — benchmarks RF-DETR/D-FINE (fuente con interés propio en RF-DETR; los números de licencia sí se verificaron aparte)
- https://roboflow.com/models-by-license/apache-2-0-licensed-object-detection · https://www.libreyolo.com/articles/best-ultralytics-alternatives — panorama de alternativas permisivas
- https://www.pythonguis.com/faq/licensing-differences-between-pyqt6-and-pyside6/ — requisitos prácticos de cumplimiento LGPLv3
- https://answers.opencv.org/question/234908/rtsp-streaming-gstreamer-or-ffmpeg/ y foros NVIDIA — latencia RTSP y limitaciones de `VideoCapture`

**LOW — estimado, no medido:**
- Tamaños de instalación y del instalador (derivados de tamaños de rueda × factor de descompresión típico). **Medir en el primer build real y corregir esta tabla.**
- Precisión efectiva del LPR en patentes argentinas en condiciones de la planta: los 94 % son del autor del modelo, en su dataset. **Validar en campo.**

---

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

---
*Stack research for: aplicación de escritorio multiplataforma de visión artificial para control de portería logística*
*Researched: 2026-07-24*
