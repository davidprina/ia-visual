# Sistema de Control de Portería con Visión Artificial

## What This Is

Aplicación de escritorio para el puesto de portería de una planta industrial que automatiza el control de ingreso y egreso de camiones. Con la menor interacción manual posible (idealmente un solo botón) captura de forma sincronizada el peso de la balanza, fotografías de la carga desde múltiples cámaras y los datos del viaje provenientes del ERP, y audita automáticamente las diferencias entre el peso real y el peso teórico del remito.

El usuario directo es el **portero** (operación diaria); los usuarios indirectos son **Logística** (precarga de viajes), **Compras** (trazabilidad de proveedores en tiempo real) y **Administración** (auditoría posterior). Es un producto destinado a comercializarse, no de uso interno exclusivo.

El proyecto se construye en dos grandes bloques: primero el **subsistema de visión** (captura multi-cámara, evidencia y reconocimiento de patentes), después las **integraciones externas** (ERP PALJET, balanza, Geomov).

## Core Value

Que la captura de evidencia visual sea confiable, sincronizada y trazable: cuando el portero presiona el botón, el sistema debe obtener sí o sí las fotos de todas las cámaras del mismo instante, asociadas al vehículo correcto, y guardarlas de forma que puedan auditarse después. Si esto falla, el sistema no elimina el error humano, lo traslada.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

(Ninguno todavía — se valida al entregar)

### Active

<!-- Current scope. Building toward these. -->

**Bloque 1 — Subsistema de visión (prioridad actual)**

- [ ] Capturar imágenes de forma sincronizada desde múltiples cámaras al recibir una única orden de captura
- [ ] Soportar cámaras IP por RTSP/ONVIF como fuente principal de las tomas de carga (superior y lateral)
- [ ] Soportar webcam USB para la digitalización ágil de documentación física (remitos de proveedor, DNI)
- [ ] Soportar archivos de video como fuente, para pruebas deterministas sin hardware
- [ ] Almacenar la evidencia capturada con metadatos completos (timestamp, cámara, viaje asociado) y consultarla después
- [ ] Detectar y reconocer patentes de vehículos (LPR) para identificar automáticamente el camión
- [ ] Detectar vehículos y personas mediante motor de IA (YOLO sobre ONNX Runtime)
- [ ] Ofrecer un motor de visión clásica basado en OpenCV, seleccionable por el usuario como alternativa al motor de IA
- [ ] Seleccionar automáticamente el mejor proveedor de ejecución disponible (GPU si existe, CPU si no)
- [ ] Configurar el layout de visualización de cámaras (1, 2x2, 3x3, 4x4) según necesidad del operador
- [ ] Reconectar automáticamente ante caída de una cámara sin detener el resto del sistema

**Bloque 2 — Flujo operativo de portería**

- [ ] Precargar viajes de egreso vinculando chofer, camión y remitos
- [ ] Registrar el ingreso de camiones de proveedor con captura de su documentación
- [ ] Contrastar automáticamente peso real contra peso teórico y aplicar tolerancias configurables
- [ ] Bloquear la salida y emitir alerta cuando la diferencia de peso supera la tolerancia máxima
- [ ] Contemplar el estado "peso teórico incompleto" cuando el ERP no tiene cargado el peso de un artículo, apoyando la auditoría en la evidencia fotográfica
- [ ] Cronometrar el tiempo de espera de cada camión de proveedor
- [ ] Mostrar un panel tipo semáforo que alerte cuando un proveedor lleva más de una hora esperando (SLA)

**Bloque 3 — Integraciones externas (al final)**

- [ ] Leer del ERP PALJET los datos maestros: chofer, camión, transportista, remitos, artículos y peso teórico
- [ ] Leer el peso real desde la API de la aplicación de balanza
- [ ] Leer de Geomov los kilómetros recorridos y los horarios de salida y regreso
- [ ] Permitir carga manual rápida de los datos de Geomov cuando su API no esté disponible

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- **Escribir en sistemas externos (ERP, balanza, Geomov)** — Regla global del usuario: solo GET en APIs y solo SELECT en bases de datos. La aplicación publica sus eventos únicamente en su propia base local; ningún dato de terceros se modifica.
- **Videovigilancia continua 24/7 con grabación permanente** — El flujo es por evento, disparado por el portero. Grabar de forma continua multiplicaría el costo de almacenamiento sin aportar al objetivo de auditar la carga.
- **Escala de 16 o más cámaras simultáneas** — Se descartó tras leer los requerimientos: el documento pide un mínimo de 2 cámaras HD más una webcam. La arquitectura admite N fuentes, pero el objetivo de escala se fija en el orden de las unidades, no de las decenas.
- **Cámaras industriales GigE Vision / USB3 Vision** — Requieren SDK propietario por fabricante y encarecen el empaquetado multiplataforma. El puerto de fuente de video queda abierto para incorporarlas sin refactorizar el dominio.
- **Entrenamiento de modelos propios y flujo de etiquetado de datasets** — Las clases necesarias (persona, vehículo) ya están cubiertas por modelos YOLO preentrenados. Sumar entrenamiento agregaría un proyecto de datos completo que hoy nadie pidió.
- **Aplicación móvil o interfaz web** — El puesto de portería es un equipo fijo de escritorio. Nada en los requerimientos justifica un segundo canal.

## Context

**Origen de los requerimientos.** El documento fuente es `Requerimientos App logista.docx`, ubicado en la raíz del proyecto. Define el objetivo, el mapa de integraciones, los dos flujos operativos (egreso e ingreso) y las reglas de negocio.

**Correcciones al documento fuente detectadas en el relevamiento:**

- El ERP en uso es **PALJET**, no Calipso/Actual como figura en el documento. Existe documentación de su API.
- La aplicación de balanza también expone API.
- De **Geomov no hay acceso ni documentación** por el momento. El propio documento anticipa este riesgo y pide prever carga manual como alternativa.

**Estado del hardware.** El tipo de cámaras todavía no está cerrado. Se contemplan cámaras IP RTSP para las tomas de carga, webcam USB para documentos y una cámara dedicada a la lectura de patentes. Mientras el hardware no esté definido, el desarrollo se valida contra archivos de video y webcam, sin bloquearse.

**Flujo de egreso (salida de mercadería).** Logística precarga el viaje vinculando chofer, camión y remitos. El camión se posiciona sobre la balanza. El portero selecciona el viaje y presiona capturar. El sistema consulta el peso y toma las fotos en simultáneo. Contrasta peso real contra teórico. Si la diferencia excede la tolerancia, alerta y bloquea; si no, registra la hora y libera.

**Flujo de ingreso (entrada de proveedores).** El camión llega y presenta documentación. Se registra el ingreso capturando fotos del remito del proveedor y asociándolo a la orden de compra del ERP. Arranca el cronómetro de espera. Al ingresar o salir se repite balanza y cámaras para auditar qué trajo o qué se lleva.

**Problema de negocio que se ataca.** Error humano en la carga de datos, diferencias de peso y volumen no detectadas, robo de mercadería, y falta de visibilidad de Compras sobre camiones de proveedor esperando en portería.

## Constraints

- **Seguridad / Acceso a datos**: La aplicación solo puede leer de APIs y bases de datos externas (GET y SELECT). Escribe exclusivamente en su propia persistencia local — Regla global del usuario, sin excepciones para este proyecto.
- **Plataforma**: Windows es la plataforma primaria de desarrollo y validación; Linux y macOS se sostienen por diseño multiplataforma pero se validan después — El puesto de portería es una PC con Windows.
- **Hardware de ejecución**: Debe funcionar tanto con GPU como sin ella, seleccionando el proveedor de ejecución en runtime — El equipo destino no está garantizado y el producto se comercializa a distintos clientes.
- **Dependencias externas**: Las integraciones con ERP PALJET, balanza y Geomov se desarrollan al final del proyecto — Decisión del usuario para no bloquear el avance esperando accesos y documentación de terceros.
- **Calidad de producto**: Instalador, mensajes de error comprensibles y configuración sin editar archivos son obligatorios — Es un producto para vender, no de uso interno.
- **Dato faltante crítico**: No hay acceso ni documentación de la API de Geomov — El propio documento fuente marca que hay que evaluar su factibilidad y prever carga manual como plan B.

## Key Decisions

<!-- Decisions that constrain future work. Add throughout project lifecycle. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Núcleo headless desacoplado de la UI, con el transporte como puerto abstracto: canal en memoria en v1, extraíble a proceso separado después | La operación mixta (procesamiento continuo más operador que se conecta cuando quiere) es incompatible con un monolito puro, pero construir IPC completo en v1 es sobre-ingeniería. Diseñar la frontera desde el día uno permite pagar esa complejidad recién cuando la escala la exija, sin tocar el dominio | — Pendiente |
| Construir la aplicación completa de portería, empezando por el subsistema de visión | El subsistema de visión es el único que se puede desarrollar y probar sin depender de accesos a sistemas de terceros. Arrancar por ahí evita que el proyecto quede bloqueado esperando credenciales | — Pendiente |
| Mantener el motor dual (YOLO por IA + OpenCV clásico) pese a que ningún requerimiento del negocio lo pide | Requisito propio del usuario, no derivado del documento fuente. Se documenta explícitamente como tal para que no se confunda con una necesidad del cliente en revisiones futuras | ⚠️ Revisar |
| Adelantar LPR (reconocimiento de patentes) a v1 | El documento fuente lo ubica en Fase 2, pero el usuario lo definió como imprescindible. Implica sumar al alcance: modelo de detección de placa, OCR, cámara e iluminación dedicadas y validación del formato de patente local | ⚠️ Revisar |
| Integraciones externas al final del roadmap | Reduce el riesgo de bloqueo por dependencias de terceros y permite entregar valor verificable antes. Contrapartida: la auditoría de pesos, que es el corazón del negocio, se valida tarde | — Pendiente |
| Solo lectura sobre sistemas externos, escritura únicamente en la base local | Regla global del usuario, ratificada explícitamente para este proyecto. Elimina el riesgo de corromper datos productivos del ERP o de la balanza | — Pendiente |
| Descartar la escala de 16 o más cámaras planteada al inicio del relevamiento | El documento fuente pide un mínimo de 2 cámaras HD más una webcam. Dimensionar para decenas de streams habría impuesto decodificación por hardware e inferencia por lotes sin ninguna necesidad real | — Pendiente |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-07-24 after initialization*
