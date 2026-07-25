# Research Summary

**Domain:** Sistema de control de portería con visión artificial para planta industrial
**Researched:** 2026-07-24
**Sources:** STACK.md · FEATURES.md · ARCHITECTURE.md · PITFALLS.md
**Confidence:** HIGH en stack, licencias y patrones de arquitectura · MEDIUM en precisión real de LPR y en contratos de integración (sin documentación accesible al momento de investigar)

---

## Las diez conclusiones que cambian el plan

1. **Ultralytics YOLO está prohibido en este proyecto.** Su licencia AGPL-3.0 obliga a liberar el código fuente de cualquier producto que lo use en red o se distribuya. El producto es comercial, así que se usa **RF-DETR-Nano/Small (Apache-2.0)** exportado a ONNX. Esto contradice el enunciado original del proyecto («YOLO mediante ONNX Runtime») y debe corregirse en la constitución.

2. **El stack es Python 3.12 + PySide6.** No porque Python sea el más rápido, sino porque es el único ecosistema donde ONNX Runtime, OpenCV, PyAV y el stack completo de ALPR abierto conviven con bindings de primera clase. El argumento fuerte a favor de C++/Rust —decenas de streams con inferencia por lotes— desapareció cuando se descartó la escala de 16+ cámaras.

3. **`cv2.VideoCapture` no sirve para RTSP en este contexto.** `CAP_PROP_BUFFERSIZE` se ignora con el backend FFMPEG (issue OpenCV #23430), así que la latencia crece de forma monótona. Se usa **PyAV** para cámaras IP y OpenCV solo para webcam USB y archivos.

4. **El fallo más peligroso del sistema es silencioso.** Cuando una cámara IP se cae y vuelve, `isOpened()` sigue devolviendo `True` y `read()` entrega el último frame para siempre (issue OpenCV #22677). Sin watchdog y detector de frames idénticos, el sistema archiva evidencia falsa con timestamps nuevos y apariencia legítima. Para un sistema de auditoría esto es catastrófico.

5. **La captura parcial silenciosa destruye el valor de todo el archivo histórico.** Una transacción con 3 de 4 fotos que aparenta estar completa invalida retroactivamente la confianza en toda la evidencia acumulada. La regla de diseño es: **todo o marcado explícitamente como incompleto**, nunca a medias sin avisar.

6. **El hash SHA-256 en ingesta no es retrofiteable.** Es la base de la cadena de custodia y el diferencial real frente a la competencia. Si no se implementa desde el primer día, todo el histórico previo pierde valor probatorio. Decisión de arquitectura, no feature.

7. **ONNX Runtime cae a CPU en silencio** cuando el provider de GPU no inicializa, y `get_available_providers()` miente (lista lo compilado, no lo activo). Hay que comparar `session.get_providers()` contra lo solicitado y exponerlo en la interfaz. El requisito de «elegir el mejor proveedor automáticamente» es exactamente donde este fallo se esconde.

8. **Planificar el LPR contra ~90% de acierto, no contra 95-99%.** Las cifras altas son de fabricantes en condiciones favorables. Pero este proyecto tiene una ventaja enorme sin explotar: **el camión está detenido sobre la balanza**, lo que habilita ráfaga, votación por consenso, validación del formato Mercosur y matching contra el padrón de viajes del día. Con eso, y con una interfaz de «sugerencia confirmable» en vez de «autodetección total», 70% de acierto crudo ya aporta valor.

9. **El riesgo de diferir las integraciones no es implementarlas tarde: es enterarse tarde.** Aunque el desarrollo de ERP, balanza y Geomov quede para el final, hay seis acciones que deben ejecutarse en la Fase 1: leer los contratos de datos, hacer un GET real contra cada sistema, congelar los puertos con dobles de prueba, modelar la relación Viaje↔Remito y el peso teórico nulo, persistir el payload crudo, y tratar la carga manual de Geomov como camino principal.

10. **El motor dual YOLO/OpenCV no tiene valor de mercado.** Ningún producto del rubro ofrece elegir motor de visión. Es un requisito propio del usuario, ya marcado como «⚠️ Revisar» en PROJECT.md. Desde la perspectiva de producto debería ser lo último de v1, o salir de v1.

---

## Stack recomendado

| Eje | Decisión | Licencia | Confianza |
|-----|----------|----------|-----------|
| Lenguaje + UI | **Python 3.12 + PySide6-Essentials 6.11.1** | LGPL-3.0 (compatible con producto cerrado si se enlaza dinámicamente) | HIGH |
| Inferencia | **ONNX Runtime**: `onnxruntime-directml` 1.24.4 como build único de Windows (CPU + cualquier GPU DX12); `onnxruntime` 1.27.0 en Linux/macOS | MIT | HIGH |
| Detector de objetos | **RF-DETR-Nano/Small**, exportado a ONNX opset 17. **Prohibido Ultralytics** | Apache-2.0 | HIGH |
| LPR / ANPR | **fast-alpr** + **fast-plate-ocr** (`cct-s-v2-global-model` + `argentinian-plates-cnn-synth-model` como segundo lector) | MIT | MEDIUM |
| Ingesta RTSP | **PyAV 18.0.0** para cámaras IP; **OpenCV VideoCapture** solo para USB y archivos | BSD-3 / Apache-2.0 | MEDIUM-HIGH |
| Visión clásica | **opencv-python-headless 5.0.0.93** (headless evita el choque Qt5/Qt6, causa clásica de crashes al inicio) | Apache-2.0 | HIGH |
| Persistencia | **SQLite + SQLAlchemy 2.0.51 + Alembic**; imágenes en filesystem direccionadas por hash SHA-256 | Dominio público / MIT | HIGH |
| Contratos | **Pydantic 2.13.4** para los mensajes núcleo↔UI: objetos en memoria en v1, serializables a JSON el día que el transporte sea IPC | MIT | HIGH |
| Empaquetado | **PyInstaller 6.21.0 `--onedir`** (obligatorio `onedir`, no `onefile`, por cumplimiento LGPL) **+ Inno Setup 7** | GPLv2 con excepción / comercial | MEDIUM |

**Peso esperado:** instalador 180-280 MB, instalado 450-650 MB.

**Riesgo legal abierto:** los pesos del detector de placa de `open-image-models` derivan de YOLOv9 (GPL-3.0) pese a que el código es MIT. **Hay que entrenar un detector propio de una clase antes del release comercial.** Es tarea explícita del roadmap, no una nota al pie.

---

## Regla rectora de la arquitectura

> **Hay dos altitudes de datos, y solo una es dominio.**
>
> - **Zona caliente:** frames, tensores, buffers, sesiones de inferencia. Alta frecuencia, efímera, pérdidas aceptables, acoplada a librerías. **Es infraestructura, siempre.**
> - **Zona fría:** observaciones, hechos, decisiones. Baja frecuencia, persistente, sin pérdidas, en lenguaje del negocio. **Es dominio.**
>
> La frontera no está en el frame: está en la **observación**. Un frame nunca entra al dominio; entra una `Detección` con caja normalizada, instante y procedencia.

**Prueba objetiva del límite, ejecutable en integración continua:**

> El paquete `dominio/` debe importarse correctamente en un entorno donde `opencv-python`, `onnxruntime` y el toolkit de interfaz **no están instalados**.

Si esa prueba pasa, la arquitectura hexagonal es real. Si no pasa, es decorativa. Reemplaza mil revisiones de código por un guardián barato y automático.

**Puertos de salida identificados:** `FuenteDeVideo` · `MotorDeDetección` · `MotorDePatente` · `AlmacénDeEvidencia` · `RepositorioDeViajes` · `ProveedorDePesaje` · `ProveedorDeDatosMaestros` · `ProveedorDeTelemetría` · `PublicadorDeEventos` · `Reloj` · `TransporteUI`

---

## Features: qué espera el mercado

**Hallazgo competitivo clave:** el mercado argentino de software de balanza (Balser, Latorre, KYASERV, Casilda) es notablemente más básico que el internacional — registro de pesadas, ticket, permisos y cumplimiento AFIP. Ninguno documenta captura fotográfica, tolerancias configurables ni integración ERP. **La barra local es baja y el diferencial es la evidencia visual auditable.**

**Posicionamiento correcto:** no es «software de balanza», es **«sistema de auditoría de carga con evidencia visual, que además usa la balanza»**. Contra Mettler Toledo o Rice Lake se pierde en integración de hardware; se gana en profundidad de evidencia.

**Imprescindible (table stakes internacional):** captura fotográfica automática ligada al pesaje (Imagic y Mandalay soportan hasta 4 cámaras por balanza, 8 imágenes por transacción completa, retención de 7 años, 720p mínimo, ≤500 KB por imagen — el requerimiento de 2 HD + webcam + LPR coincide exactamente con el estándar).

**Diferenciadores genuinos:**
- **Cadena de custodia** (hash en ingesta, manifiesto de exportación, log append-only de accesos). Ningún producto relevado lo ofrece.
- **Estado «peso teórico incompleto»** como ruta de trabajo válida. Todos los productos del mercado asumen maestros completos; convertir un dato faltante en auditoría visual firmada más un reporte de artículos sin peso para que el cliente corrija su ERP es valor real.

**Totales:** 23 imprescindibles, 10 diferenciadores, 12 anti-features. Detalle completo en `FEATURES.md`.

---

## Los cinco pitfalls que hay que atacar desde la Fase 1

| # | Pitfall | Por qué es crítico | Mitigación |
|---|---------|--------------------|------------|
| 1 | **Buffer RTSP acumulando latencia** | `CAP_PROP_BUFFERSIZE` no funciona con FFMPEG; la solución que todos copian no hace nada | Hilo lector dedicado con slot de tamaño 1 y política de descarte del más viejo |
| 2 | **Cámara caída que sigue reportando OK** | Archiva evidencia falsa con timestamps nuevos y apariencia legítima | Watchdog por fuente + detector de frames idénticos + estado explícito en la interfaz |
| 3 | **«Sincronizado» implementado como un bucle sobre cámaras** | No es sincronía; los relojes de las cámaras IP derivan y la evidencia se vuelve impugnable | Persistir el desvío por cámara contra un reloj único del proceso y declarar una ventana de aceptación |
| 4 | **ONNX Runtime cayendo a CPU en silencio** | El requisito de selección automática de proveedor esconde exactamente este fallo | Comparar `session.get_providers()` contra lo solicitado y exponerlo en la interfaz |
| 5 | **Enterarse tarde de los contratos de integración** | Descubrir en la fase final que el modelo de datos no encaja obliga a rehacer el dominio | Leer documentación y hacer un GET real contra cada sistema **en la Fase 1**, aunque la integración se construya al final |

**Errores geométricos silenciosos:** dos tests unitarios baratos evitan semanas de depuración — round-trip de letterbox/unletterbox con tolerancia sub-pixel, y comparación contra implementación de referencia con IoU > 0.9. Sin ellos, los errores de escalado aparecen mucho después disfrazados de «el OCR anda mal».

**Plazo administrativo bloqueante:** la compra del certificado de firma de código debe iniciarse en la primera mitad del proyecto. Sin firma Authenticode, SmartScreen bloquea el instalador y el producto parece malware. No es una tarea técnica, es un trámite con plazos propios.

**Riesgo humano:** si el sistema agrega más de ~30 segundos por camión, el operador lo va a eludir para no frenar la cola. La regla de diseño no es prohibir la excepción, es **registrarla**.

---

## Implicancias directas sobre el roadmap

1. **La Fase 1 carga más de lo que parece.** No es solo «núcleo headless»: debe fijar el contrato de frescura del frame, el modelo de reloj y desvío, la persistencia transaccional con hashes y escritura atómica, y el descubrimiento de los contratos de integración.

2. **La fase de captura necesita compuertas de salida medibles**, no un «funciona»: cronómetro filmado de 10 minutos con deriva que no crece, prueba del cable desenchufado con cambio de estado en menos de 15 segundos, y prueba de resistencia de 8 horas con cortes cíclicos y consumo de memoria plano.

3. **El LPR no es solo software.** Necesita una tarea explícita de especificación y validación de instalación física: píxeles sobre placa medidos en campo, ángulo de 15° a 30°, obturador, iluminación infrarroja nocturna. Y una decisión de interfaz: sugerencia confirmable, nunca autodetección total.

4. **La auditoría de pesos —el corazón del negocio— queda al final** por depender de balanza y ERP. Mitigación obligatoria: construirla completa contra adaptadores simulados desde temprano, para que la integración final sea sustituir un adaptador y no descubrir el dominio.

---

## Preguntas abiertas que el roadmap debe absorber

| Tema | Qué falta | Cuándo se resuelve |
|------|-----------|--------------------|
| **PALJET** | Cardinalidad Viaje↔Remito, granularidad del peso teórico (por remito o por línea), formato del campo patente, existencia de ambiente de pruebas | Fase 1 — leer la documentación de API que ya existe |
| **Balanza** | Si la API expone timestamp de la lectura y un indicador de estabilidad del peso. Sin eso, correlacionar peso con fotos es una suposición | Fase 1 |
| **Geomov** | Sin acceso ni documentación. Se asume carga manual como camino principal | Cuando haya acceso |
| **Cámaras** | Hardware sin definir: no se puede confirmar píxeles sobre placa, GOP ni soporte RTCP para sincronía | Los requisitos numéricos de PITFALLS.md deben usarse como **insumo del pliego de compra**, no validarse después |
| **Precisión de LPR con patentes argentinas** | No hay benchmark público local | Construir un conjunto de evaluación propio (~200 capturas reales, con noche, suciedad y contraluz) durante la fase de LPR |
| **Volumen de camiones/día** | Define el dimensionamiento de almacenamiento (~4 MB por camión con 4 cámaras y 2 eventos) | Preguntar al cliente |
| **Retención de evidencia** | Cuánto tiempo se conservan las imágenes y qué se hace al llenarse el disco | Antes del instalador |

---

## Conflictos que el roadmap debe resolver explícitamente

1. **Visibilidad en tiempo real para Compras choca con el «sin interfaz web» de PROJECT.md.** El documento fuente lo pide explícitamente y Compras es parte de quien financia el proyecto. Recomendación: vista de solo lectura en la red local — no es «una aplicación web» en el sentido que la exclusión quiso evitar.

2. **El motor dual es costo sin valor de mercado.** Mantenerlo como requisito propio del usuario, pero ubicarlo al final de v1.

3. **LPR adelantado a v1 contra lo que indica el documento fuente.** Decisión del usuario ya tomada; el roadmap debe reflejar su costo real (modelo, cámara dedicada, iluminación, validación de campo) y no subestimarlo.

---
*Synthesis of: STACK.md · FEATURES.md · ARCHITECTURE.md · PITFALLS.md*
