# Requirements: Sistema de Control de Portería con Visión Artificial

**Defined:** 2026-07-24
**Core Value:** Que la captura de evidencia visual sea confiable, sincronizada y trazable: cuando el portero presiona el botón, el sistema obtiene sí o sí las fotos de todas las cámaras del mismo instante, asociadas al vehículo correcto, y las guarda de forma auditable.

---

## v1 Requirements

### Núcleo y arquitectura (NUC)

- [ ] **NUC-01**: El paquete de dominio se importa correctamente en un entorno donde OpenCV, ONNX Runtime y el toolkit de interfaz no están instalados
- [ ] **NUC-02**: El núcleo expone un puerto de transporte hacia la interfaz, implementado en v1 como canal en memoria y sustituible por IPC sin modificar el dominio
- [ ] **NUC-03**: Los mensajes entre núcleo e interfaz están definidos como contratos tipados y validados, serializables sin cambios en el dominio
- [ ] **NUC-04**: Todos los puertos de salida (fuente de video, motor de detección, almacén de evidencia, proveedor de pesaje, proveedor de datos maestros, reloj) tienen un doble de prueba que permite ejecutar el sistema completo sin hardware ni sistemas externos
- [ ] **NUC-05**: Cada operación que persiste estado, evidencia y eventos lo hace en una única transacción atómica: o se guarda todo, o no se guarda nada
- [ ] **NUC-06**: El sistema registra en bitácora estructurada cada operación relevante, con nivel configurable y rotación automática de archivos

### Captura de video (CAP)

- [ ] **CAP-01**: El sistema captura video desde cámaras IP por RTSP con transporte TCP explícito y tiempo de espera configurable
- [ ] **CAP-02**: El sistema captura video desde webcam USB conectada al equipo
- [ ] **CAP-03**: El sistema reproduce archivos de video locales como fuente, para pruebas deterministas sin hardware
- [ ] **CAP-04**: Cada fuente entrega siempre el frame más reciente disponible, descartando los viejos, de modo que la latencia no crece con el tiempo de ejecución
- [ ] **CAP-05**: El sistema detecta que una fuente dejó de entregar frames nuevos aunque la conexión aparente estar viva, y cambia su estado a caída en menos de 15 segundos
- [ ] **CAP-06**: El sistema reconecta automáticamente una fuente caída sin detener las demás y sin acumular hilos ni memoria
- [ ] **CAP-07**: La interfaz muestra el estado en vivo de cada fuente: conectada, degradada, caída o reconectando
- [ ] **CAP-08**: El sistema opera de forma continua durante 8 horas con cortes de red cíclicos manteniendo estables el consumo de memoria, la cantidad de hilos y los descriptores abiertos

### Captura sincronizada y evidencia (EVI)

- [ ] **EVI-01**: Una única orden de captura obtiene imágenes de todas las cámaras activas referidas al mismo instante objetivo
- [ ] **EVI-02**: El sistema registra, para cada imagen capturada, su desvío temporal respecto del instante objetivo, medido contra un reloj único del proceso
- [ ] **EVI-03**: El sistema declara una ventana de aceptación configurable y marca la captura como sincronizada o estimada según el desvío observado
- [ ] **EVI-04**: Una captura en la que falta alguna cámara se marca explícitamente como incompleta y nunca aparenta estar completa
- [ ] **EVI-05**: El sistema calcula la huella SHA-256 de cada imagen en el momento de la ingesta y la persiste junto a sus metadatos
- [ ] **EVI-06**: Las imágenes se almacenan en el sistema de archivos direccionadas por su contenido, con la base de datos guardando únicamente metadatos y referencia
- [ ] **EVI-07**: El usuario consulta las capturas históricas filtrando por fecha, patente, tipo de movimiento y estado de auditoría
- [ ] **EVI-08**: El usuario exporta un conjunto de evidencia con un manifiesto que incluye las huellas, permitiendo verificar su integridad fuera del sistema
- [ ] **EVI-09**: El sistema registra en bitácora inmutable cada acceso y exportación de evidencia
- [ ] **EVI-10**: El sistema alerta cuando el espacio libre en disco cae por debajo de un umbral configurable, antes de que la escritura falle

### Detección por visión artificial (VIS)

- [ ] **VIS-01**: El sistema detecta vehículos y personas en el video mediante modelo de detección con licencia permisiva ejecutado sobre ONNX Runtime
- [ ] **VIS-02**: El sistema selecciona automáticamente el mejor proveedor de ejecución disponible según el hardware presente
- [ ] **VIS-03**: La interfaz muestra qué proveedor de ejecución está activo realmente, verificado contra la sesión, y no el que fue solicitado
- [ ] **VIS-04**: La interfaz superpone sobre el video las cajas de detección, la clase y el nivel de confianza
- [ ] **VIS-05**: El usuario configura el umbral de confianza y qué clases se muestran
- [ ] **VIS-06**: Las coordenadas de las detecciones se corresponden con el frame original con precisión sub-pixel, verificado por prueba automática de ida y vuelta del escalado
- [ ] **VIS-07**: El sistema ofrece un motor de visión clásica basado en OpenCV, seleccionable por el usuario como alternativa al motor de inteligencia artificial
- [ ] **VIS-08**: El cambio de motor no requiere reiniciar la aplicación ni modificar la configuración de las fuentes

### Reconocimiento de patentes (LPR)

- [ ] **LPR-01**: El sistema detecta la placa de un vehículo y transcribe sus caracteres a partir del video
- [ ] **LPR-02**: El sistema aprovecha que el vehículo está detenido tomando una ráfaga de lecturas y resolviendo por consenso entre ellas
- [ ] **LPR-03**: El sistema valida la lectura contra el formato de patente argentino, incluyendo Mercosur y el formato anterior
- [ ] **LPR-04**: El sistema compara la lectura contra el padrón de viajes del día y propone la coincidencia más cercana por distancia de edición
- [ ] **LPR-05**: La patente reconocida se presenta como sugerencia que el portero confirma o corrige, nunca como identificación automática irrevocable
- [ ] **LPR-06**: El sistema registra cada corrección manual del portero, con la lectura original y la corregida, para poder medir la precisión real en campo
- [ ] **LPR-07**: El detector de placa utilizado en producción tiene licencia permisiva verificada, sin pesos derivados de modelos con licencia contagiosa

### Interfaz del operador (UI)

- [ ] **UI-01**: El portero visualiza las cámaras activas y ejecuta la captura completa con un solo botón
- [ ] **UI-02**: El usuario elige el layout de visualización entre una sola cámara, 2x2, 3x3 y 4x4, y el cambio surte efecto sin reiniciar
- [ ] **UI-03**: La interfaz nunca se congela durante la captura, la inferencia ni la reconexión de fuentes
- [ ] **UI-04**: El usuario configura cámaras, tolerancias, umbrales y rutas desde la propia interfaz, sin editar archivos
- [ ] **UI-05**: Los mensajes de error son comprensibles para un operador no técnico e indican qué hacer a continuación
- [ ] **UI-06**: El flujo completo de captura de un camión se resuelve en menos de 30 segundos de interacción del operador
- [ ] **UI-07**: La aplicación se opera correctamente con pantalla táctil y en monitores con distintas densidades de píxeles

### Flujo de egreso (VIA)

- [ ] **VIA-01**: Logística precarga un viaje vinculando chofer, camión y remitos
- [ ] **VIA-02**: El portero selecciona un viaje precargado desde una lista filtrable
- [ ] **VIA-03**: El sistema asocia la captura de evidencia y la lectura de peso al viaje seleccionado
- [ ] **VIA-04**: El sistema registra la hora de liberación del viaje y su estado final
- [ ] **VIA-05**: El sistema modela la relación entre viaje y remitos como muchos a muchos desde el diseño inicial del esquema

### Flujo de ingreso de proveedores (ING)

- [ ] **ING-01**: El portero da de alta el ingreso de un camión de proveedor capturando la foto de su remito
- [ ] **ING-02**: El sistema asocia el ingreso a una orden de compra
- [ ] **ING-03**: El sistema captura fotos de la carga al ingreso y al egreso del proveedor para auditar qué trajo y qué se lleva
- [ ] **ING-04**: La captura de documentación por webcam produce una imagen legible sin retrasar la fila de camiones

### Auditoría de pesos (AUD)

- [ ] **AUD-01**: El sistema contrasta el peso real informado por la balanza contra el peso teórico de los remitos
- [ ] **AUD-02**: El usuario configura dos umbrales de tolerancia: uno de aceptación automática y otro de bloqueo
- [ ] **AUD-03**: El sistema emite alerta y bloquea la liberación cuando la diferencia supera el umbral de bloqueo
- [ ] **AUD-04**: El sistema contempla el estado de peso teórico incompleto cuando el ERP no tiene cargado el peso de un artículo, y habilita una auditoría apoyada en la evidencia fotográfica
- [ ] **AUD-05**: El sistema produce un reporte de artículos sin peso maestro cargado, para que el cliente corrija su ERP
- [ ] **AUD-06**: Toda excepción u omisión forzada por el operador queda registrada con su motivo, en lugar de ser impedida

### Tiempos de espera y SLA (SLA)

- [ ] **SLA-01**: El sistema cronometra el tiempo de espera de cada camión de proveedor desde su arribo
- [ ] **SLA-02**: La interfaz muestra un panel tipo semáforo con el estado de espera de cada camión presente
- [ ] **SLA-03**: El sistema notifica cuando un camión de proveedor supera el umbral de espera configurado

### Consulta y visibilidad (CON)

- [ ] **CON-01**: Compras accede desde la red local a una vista de solo lectura con las capturas y los remitos del momento
- [ ] **CON-02**: La vista de consulta no permite editar, configurar ni eliminar nada
- [ ] **CON-03**: El usuario exporta los movimientos de un período a un formato tabular abierto

### Integraciones externas (INT)

- [ ] **INT-01**: El sistema lee del ERP los datos maestros de chofer, camión, transportista y remitos con sus artículos y pesos teóricos
- [ ] **INT-02**: El sistema lee el peso real desde la interfaz de la aplicación de balanza
- [ ] **INT-03**: El sistema registra los kilómetros recorridos y los horarios de salida y regreso, con carga manual rápida como camino principal
- [ ] **INT-04**: Toda comunicación con sistemas externos es de solo lectura; el sistema nunca escribe en ellos
- [ ] **INT-05**: El sistema persiste el payload crudo de cada consulta externa, para poder diagnosticar discrepancias posteriores
- [ ] **INT-06**: El sistema opera de forma degradada pero funcional cuando un sistema externo no responde, sin perder la captura de evidencia

### Distribución y operación (DIS)

- [ ] **DIS-01**: La aplicación se instala en Windows mediante un instalador con firma digital válida
- [ ] **DIS-02**: El instalador incluye el texto de las licencias de terceros y la aplicación las muestra desde su interfaz
- [ ] **DIS-03**: El empaquetado deja las bibliotecas del toolkit de interfaz sustituibles por el usuario, cumpliendo su licencia
- [ ] **DIS-04**: La aplicación se recupera automáticamente tras un corte de energía, restaurando su estado sin intervención
- [ ] **DIS-05**: El esquema de base de datos se actualiza mediante migraciones versionadas, preservando los datos existentes
- [ ] **DIS-06**: La aplicación funciona correctamente en rutas con espacios y caracteres acentuados

---

## v2 Requirements

### Escalado y hardware

- **V2-01**: Autodescubrimiento de cámaras en la red local mediante ONVIF
- **V2-02**: Soporte de cámaras industriales GigE Vision y USB3 Vision
- **V2-03**: Extracción del núcleo a un proceso separado con transporte por comunicación entre procesos
- **V2-04**: Empaquetado y validación en Linux y macOS

### Automatización

- **V2-05**: Disparo automático del flujo de viaje por reconocimiento de patente, sin selección manual del portero
- **V2-06**: Integración con la interfaz de rastreo satelital cuando exista acceso documentado
- **V2-07**: Detección automática de que el vehículo está correctamente posicionado sobre la plataforma de la balanza

### Análisis

- **V2-08**: Estimación de volumen ocupado en la caja para detectar espacios vacíos
- **V2-09**: Reportes analíticos de tendencias de diferencias de peso por transportista y por artículo
- **V2-10**: Panel de indicadores de operación de portería

---

## Out of Scope

| Feature | Reason |
|---------|--------|
| Escritura en ERP, balanza o rastreo satelital | Regla global del usuario: solo lectura sobre sistemas externos. La aplicación escribe únicamente en su propia base |
| Ultralytics YOLO en cualquier versión | Licencia AGPL-3.0: obligaría a publicar el código fuente de un producto comercial |
| Videovigilancia continua con grabación permanente | El flujo es por evento. Grabar de continuo multiplicaría el almacenamiento sin aportar a la auditoría de carga |
| Escala de 16 o más cámaras simultáneas | El documento fuente pide un mínimo de 2 cámaras HD más una webcam |
| Aplicación móvil | El puesto de portería es un equipo fijo de escritorio |
| Aplicación web completa con edición y configuración | Solo se admite una vista de consulta de solo lectura en red local |
| Entrenamiento de modelos de detección de objetos | Las clases necesarias ya están cubiertas por modelos preentrenados permisivos. Excepción acotada: el detector de placa propio |
| Reconocimiento facial o identificación biométrica de choferes | No lo pide ningún requerimiento y agrega obligaciones de protección de datos personales desproporcionadas |
| Control de barrera o semáforo físico por hardware | Ningún requerimiento lo menciona. Requeriría interfaz con automatismos industriales y responsabilidad sobre seguridad física |

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| NUC-01 | Phase 1 | Pending |
| NUC-02 | Phase 2 | Pending |
| NUC-03 | Phase 2 | Pending |
| NUC-04 | Phase 1 | Pending |
| NUC-05 | Phase 1 | Pending |
| NUC-06 | Phase 1 | Pending |
| CAP-01 | Phase 2 | Pending |
| CAP-02 | Phase 2 | Pending |
| CAP-03 | Phase 1 | Pending |
| CAP-04 | Phase 1 | Pending |
| CAP-05 | Phase 2 | Pending |
| CAP-06 | Phase 2 | Pending |
| CAP-07 | Phase 2 | Pending |
| CAP-08 | Phase 2 | Pending |
| EVI-01 | Phase 3 | Pending |
| EVI-02 | Phase 3 | Pending |
| EVI-03 | Phase 3 | Pending |
| EVI-04 | Phase 3 | Pending |
| EVI-05 | Phase 1 | Pending |
| EVI-06 | Phase 1 | Pending |
| EVI-07 | Phase 9 | Pending |
| EVI-08 | Phase 9 | Pending |
| EVI-09 | Phase 9 | Pending |
| EVI-10 | Phase 3 | Pending |
| VIS-01 | Phase 4 | Pending |
| VIS-02 | Phase 4 | Pending |
| VIS-03 | Phase 4 | Pending |
| VIS-04 | Phase 4 | Pending |
| VIS-05 | Phase 4 | Pending |
| VIS-06 | Phase 4 | Pending |
| VIS-07 | Phase 12 | Pending |
| VIS-08 | Phase 12 | Pending |
| LPR-01 | Phase 5 | Pending |
| LPR-02 | Phase 5 | Pending |
| LPR-03 | Phase 5 | Pending |
| LPR-04 | Phase 5 | Pending |
| LPR-05 | Phase 5 | Pending |
| LPR-06 | Phase 5 | Pending |
| LPR-07 | Phase 5 | Pending |
| UI-01 | Phase 3 | Pending |
| UI-02 | Phase 2 | Pending |
| UI-03 | Phase 3 | Pending |
| UI-04 | Phase 7 | Pending |
| UI-05 | Phase 2 | Pending |
| UI-06 | Phase 6 | Pending |
| UI-07 | Phase 3 | Pending |
| VIA-01 | Phase 6 | Pending |
| VIA-02 | Phase 6 | Pending |
| VIA-03 | Phase 6 | Pending |
| VIA-04 | Phase 6 | Pending |
| VIA-05 | Phase 1 | Pending |
| ING-01 | Phase 8 | Pending |
| ING-02 | Phase 8 | Pending |
| ING-03 | Phase 8 | Pending |
| ING-04 | Phase 8 | Pending |
| AUD-01 | Phase 7 | Pending |
| AUD-02 | Phase 7 | Pending |
| AUD-03 | Phase 7 | Pending |
| AUD-04 | Phase 7 | Pending |
| AUD-05 | Phase 7 | Pending |
| AUD-06 | Phase 7 | Pending |
| SLA-01 | Phase 8 | Pending |
| SLA-02 | Phase 8 | Pending |
| SLA-03 | Phase 8 | Pending |
| CON-01 | Phase 9 | Pending |
| CON-02 | Phase 9 | Pending |
| CON-03 | Phase 9 | Pending |
| INT-01 | Phase 10 | Pending |
| INT-02 | Phase 10 | Pending |
| INT-03 | Phase 10 | Pending |
| INT-04 | Phase 1 | Pending |
| INT-05 | Phase 1 | Pending |
| INT-06 | Phase 10 | Pending |
| DIS-01 | Phase 11 | Pending |
| DIS-02 | Phase 11 | Pending |
| DIS-03 | Phase 11 | Pending |
| DIS-04 | Phase 11 | Pending |
| DIS-05 | Phase 1 | Pending |
| DIS-06 | Phase 1 | Pending |

**Requerimientos por fase:**

| Fase | Requerimientos | Cantidad |
|------|----------------|----------|
| Phase 1 — Núcleo, evidencia trazable y contratos externos | NUC-01, NUC-04, NUC-05, NUC-06, CAP-03, CAP-04, EVI-05, EVI-06, VIA-05, INT-04, INT-05, DIS-05, DIS-06 | 13 |
| Phase 2 — Ingesta multi-fuente robusta y visor que no miente | NUC-02, NUC-03, CAP-01, CAP-02, CAP-05, CAP-06, CAP-07, CAP-08, UI-02, UI-05 | 10 |
| Phase 3 — Captura sincronizada de un botón (Core Value) | EVI-01, EVI-02, EVI-03, EVI-04, EVI-10, UI-01, UI-03, UI-07 | 8 |
| Phase 4 — Detección por IA con proveedor verificado | VIS-01, VIS-02, VIS-03, VIS-04, VIS-05, VIS-06 | 6 |
| Phase 5 — Reconocimiento de patentes como sugerencia confirmable | LPR-01, LPR-02, LPR-03, LPR-04, LPR-05, LPR-06, LPR-07 | 7 |
| Phase 6 — Flujo de egreso: viaje, captura y liberación | VIA-01, VIA-02, VIA-03, VIA-04, UI-06 | 5 |
| Phase 7 — Auditoría de peso, tolerancias y excepciones | AUD-01, AUD-02, AUD-03, AUD-04, AUD-05, AUD-06, UI-04 | 7 |
| Phase 8 — Ingreso de proveedores, documentación y SLA | ING-01, ING-02, ING-03, ING-04, SLA-01, SLA-02, SLA-03 | 7 |
| Phase 9 — Consulta, evidencia exportable y vista para Compras | EVI-07, EVI-08, EVI-09, CON-01, CON-02, CON-03 | 6 |
| Phase 10 — Integraciones reales: balanza, PALJET y recorrido | INT-01, INT-02, INT-03, INT-06 | 4 |
| Phase 11 — Empaquetado, instalador firmado y resiliencia | DIS-01, DIS-02, DIS-03, DIS-04 | 4 |
| Phase 12 — Motor de visión clásica seleccionable en caliente | VIS-07, VIS-08 | 2 |

**Coverage:**
- Requerimientos v1: 79 en total
- Mapeados a fases: 79
- Sin mapear: 0 ✓
- Duplicados (asignados a más de una fase): 0 ✓

---
*Requirements defined: 2026-07-24*
*Last updated: 2026-07-25 — traceability completada al crear ROADMAP.md (12 fases)*
