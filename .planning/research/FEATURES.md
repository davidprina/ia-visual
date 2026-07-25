# Feature Research

**Domain:** Control de portería y pesaje de camiones en planta industrial, con visión artificial y auditoría de carga
**Researched:** 2026-07-24
**Confidence:** MEDIUM-HIGH

## Alcance de la investigación

Se relevaron cuatro familias de producto que se solapan sobre este problema, porque ninguna sola lo cubre entero:

| Familia | Productos relevados | Qué aporta al mapa |
|---------|--------------------|--------------------|
| Weighbridge / truck scale software | Mettler Toledo DataBridge (MS/SS/AP), Rice Lake OnTrak + ATK, Amity, Endel WeighMAST, UniWin, Imagic, Mandalay Image Capture | Transacción de pesaje, tickets, tolerancias, CCTV ligado al pesaje, antifraude |
| Yard Management Systems | YardView, Kaleris, project44, DataDocks | Check-in/check-out, dwell time, alertas por umbral, KPIs de portería |
| Control de acceso vehicular / LPR | Nedap ANPR Lumo, Survision, TagMaster, Avutec, Nortech | Precisión real de LPR, umbral de confianza, revisión manual, listas |
| Gate pass / visitor management industrial | FacilityOS, Frenzin, Entry2Exit, VelocityEHS | Digitalización de documentación, listas negras, logs auditables |
| Mercado argentino | Balser, Latorre Pesaje, KYASERV, Básculas Casilda, Ingelsoft, Fulcrum (DataBridge) | Expectativa local: ticket, AFIP RG 3890/2016 y 271/1998, antifraude a nivel base, permisos por usuario |

**Hallazgo transversal:** el mercado local argentino de software de balanza es notablemente más básico que el internacional. Los productos de Balser, Latorre, KYASERV y Casilda venden esencialmente *registro de pesadas + ticket + permisos por usuario + cumplimiento AFIP*. Ninguno de los sitios relevados documenta captura fotográfica, tolerancias configurables ni integración ERP como característica destacada. Eso define la barra competitiva local: es baja, y el diferencial de este producto es la evidencia visual auditable. (Confianza MEDIUM — sitios de vendor escuetos; no descarta que lo tengan sin publicarlo.)

---

## Feature Landscape

### Table Stakes (Imprescindibles)

Sin esto el producto no es usable en una portería real ni competitivo frente a lo que ya existe.

| # | Feature | Por qué es imprescindible | Complejidad | Notas de implementación |
|---|---------|---------------------------|-------------|------------------------|
| T1 | **Transacción de pesaje en dos tiempos con estado abierto persistente** (ingreso→egreso, bruto/tara) | Es el modelo universal de todo weighbridge software relevado. Un camión genera dos eventos separados por horas. Si la transacción no sobrevive al cierre de la app, al cambio de turno o a un corte de energía, el sistema es inutilizable | MEDIUM | Estado en la base local, no en memoria. Recuperación automática al arrancar con lista de "transacciones abiertas". Es la estructura que sostiene todo lo demás |
| T2 | **Ticket/comprobante de pesaje numerado, imprimible y reimprimible** | Todos los productos argentinos relevados lo ponen como característica central (impresión en cualquier impresora, membrete y logo, envío por email). El chofer y el archivo de portería necesitan un papel | LOW | Numeración correlativa sin huecos. Reimpresión marcada como copia. Plantilla configurable con logo del cliente (es producto para vender a varios clientes) |
| T3 | **Captura automática y sincronizada de fotos en el instante del pesaje, ligada al ticket** | Estándar de facto: Imagic y Mandalay capturan automáticamente al guardar/imprimir el ticket. Mandalay soporta hasta 4 cámaras por balanza/portería, con hasta 8 imágenes por transacción completa (entrada + salida) — coincide exactamente con el requerimiento de 2 HD + webcam + LPR | HIGH | Es el Core Value declarado del proyecto. La sincronía debe ser verificable: si una cámara no responde, la transacción debe quedar marcada como evidencia incompleta, nunca silenciosamente parcial |
| T4 | **Overlay de datos sobre la imagen** (fecha, hora, identificador de cámara, patente, número de ticket, peso) | Text overlay es práctica documentada en la industria para identificar la posición de cámara. Una foto exportada sin contexto no sirve como evidencia | LOW | Quemar en la imagen Y guardar en metadatos. El overlay hace la foto autodescriptiva fuera del sistema; los metadatos la hacen buscable dentro |
| T5 | **Búsqueda y recuperación de evidencia por ticket, patente, fecha/rango, proveedor, operador** | Mandalay: búsqueda de transacción filtrando por número de ticket, sitio, fecha, hora. Es *la* función de auditoría. Guardar fotos que no se pueden encontrar equivale a no guardarlas | MEDIUM | Índices por patente y por rango de fecha desde el día uno. Visor de fotos integrado (Imagic lo destaca explícitamente para "análisis de pesadas viejas por gerencia") |
| T6 | **Retención configurable con política de archivado y dimensionamiento de almacenamiento** | Mandalay retiene 7 años. La referencia técnica de la industria es 720p mínimo y compresión a ≤500 KB por imagen | MEDIUM | Con 4 cámaras × 2 eventos × 500 KB ≈ 4 MB por camión. A 100 camiones/día son ~145 GB/año. El cálculo debe estar en la UI, no en la cabeza del instalador. Purga automática con confirmación explícita |
| T7 | **Usuarios, roles y permisos, con override de excepciones restringido a supervisor** | Universal en la industria: operadores capturan, supervisores autorizan excepciones, administradores configuran. Los productos argentinos (Latorre) venden "control de acceso y permisos por usuario" como característica principal | MEDIUM | Mínimo tres roles: Portero, Supervisor/Administración, Configurador. Sin esto, "bloquear la salida" no significa nada porque el propio portero se lo destraba |
| T8 | **Cambio de turno y sesión de operador** | Requisito de robustez operativa que la industria da por sentado: los reportes se filtran por operador y por turno. Toda acción debe atribuirse a una persona | LOW | Login rápido (PIN o tarjeta, no contraseña larga con guantes puestos). Cierre de turno que deje transacciones abiertas visibles al siguiente. Nunca cerrar sesión perdiendo una captura en curso |
| T9 | **Log de auditoría inmutable de acciones** (quién, qué, cuándo, desde dónde) | Latorre publica "amplias protecciones ANTIFRAUDE a nivel programa y base de datos". La industria coincide: audit trails obligatorios | MEDIUM | Append-only. Registra especialmente: overrides, anulaciones, cambios de tolerancia, correcciones manuales de patente, ediciones de peso manual |
| T10 | **Tolerancias configurables con umbrales escalonados** (aceptar / alertar / bloquear) | El documento fuente da los números concretos: <50 kg aceptado, >2.000 kg bloquea. La industria valida tolerancias contra la orden y dispara investigación fuera de rango | LOW | Tolerancia en kg y en %, la que sea más restrictiva. Configurable por artículo/rubro, no solo global — un remito de tornillos y uno de chapas no toleran lo mismo |
| T11 | **Manejo de excepciones con motivo obligatorio y autorización** | "Los supervisores autorizan excepciones" es el patrón estándar. Sin motivo tipificado, la excepción no es auditable | MEDIUM | Catálogo de motivos configurable + campo libre. La excepción autorizada NO borra la alerta: queda en el registro con quién la autorizó |
| T12 | **LPR con score de confianza, umbral configurable y confirmación/corrección del operador** | Ver sección dedicada abajo. Ningún sistema serio de LPR opera sin umbral y sin ruta de revisión manual | HIGH | La patente propuesta se muestra junto a la foto del recorte de placa. El operador confirma con un toque o corrige. Nunca dispara el flujo sin confirmación en v1 |
| T13 | **Soporte de formato Mercosur y formato anterior argentino, ambos** | El parque vehicular argentino es mixto. El formato Mercosur es LL-NNN-LL (7 caracteres); el anterior LLL-NNN | LOW | Validación de formato como red de seguridad post-OCR: descarta lecturas que no matchean ningún patrón válido y las manda a corrección manual |
| T14 | **Digitalización ágil de documentación física** (remito de proveedor, DNI) | Los sistemas de gate pass exigen captura de documento con campos obligatorios. El documento fuente lo pide explícitamente y advierte que no debe retrasar la fila | MEDIUM | Webcam, no escáner (el propio requerimiento marca la lentitud del calentamiento del multifunción). Foto → verificación de legibilidad → confirmar, en menos de 10 segundos. Recorte y enderezado automático de la hoja |
| T15 | **Cronómetro de espera del camión de proveedor** | Dwell time tracking es table stakes en todo YMS relevado | LOW | Arranca en el registro de ingreso. Debe sobrevivir al reinicio de la app |
| T16 | **Panel semáforo de SLA con umbrales configurables** | Los YMS usan alertas por color cuando un trailer se acerca al umbral de detention. El requerimiento pide rojo a la hora | LOW | Verde/amarillo/rojo con umbrales configurables (el "1 hora" no debe estar hardcodeado). Ordenado por tiempo de espera descendente |
| T17 | **Maestro local de vehículos, choferes y transportistas, alimentado por caché del ERP** | Sin esto, si el ERP se cae, la portería se para. Con la restricción de solo-lectura, la caché local es la única defensa | MEDIUM | Sincronización periódica en background. Indicar antigüedad del dato en pantalla ("sincronizado hace 4 min") |
| T18 | **Modo contingencia: operar con ERP, balanza o red caídos** | Resiliencia offline es expectativa documentada del software de portería. La portería no puede parar porque se cayó un tercero | HIGH | Peso manual con marca indeleble de "ingresado manualmente" + foto obligatoria del display de la balanza. Viaje manual sin remito precargado, a conciliar después. Cola de pendientes de conciliación visible |
| T19 | **Reportes y exportación en PDF, Excel y CSV, con filtros operativos** | Estándar de la industria: exportación diaria en PDF/Excel/CSV/texto, filtrable por fecha, sitio, cliente, vehículo, transportista, material, operador y turno | MEDIUM | Ver sección "Reportes esperados" abajo |
| T20 | **Reconexión automática de cámaras sin detener el sistema** | Ya está en el alcance activo. Una cámara caída no puede tumbar la portería | MEDIUM | Indicador de estado por cámara siempre visible. Alerta sonora/visual si se intenta capturar con una cámara caída |
| T21 | **Instalador, configuración por UI y mensajes de error comprensibles** | Restricción de producto: se comercializa. Configurar cámaras editando un YAML es descalificatorio en una venta | MEDIUM | Asistente de alta de cámara con prueba de conexión y vista previa. Ningún error debe mostrar un stack trace al portero |
| T22 | **UI operable en pantalla táctil con guantes y con poca luz** | Requisito de robustez que la industria da por sentado; los productos de guardhouse advierten que "el software de escritorio metido en una tablet es doloroso para el guardia" | MEDIUM | Targets táctiles ≥ 60 px, botón de captura dominante, alto contraste, sin hover, sin menús anidados profundos, sin dobles clics. Teclado numérico en pantalla para patente y remito |
| T23 | **Arranque automático y recuperación tras corte de energía** | Corte de energía en planta industrial es rutina, no excepción | LOW | Autostart con Windows, sin login de SO manual. Al arrancar: recuperar transacciones abiertas y avisar si la última captura quedó incompleta |

### Diferenciadores (Ventaja competitiva)

| # | Feature | Propuesta de valor | Complejidad | Notas |
|---|---------|--------------------|-------------|-------|
| D1 | **Auditoría automática peso real vs. peso teórico del remito, con la evidencia fotográfica del mismo instante vinculada al veredicto** | El mercado compara peso contra tolerancia de orden. Casi nadie liga en un solo registro auditable: líneas de remito del ERP + peso de balanza + fotos sincronizadas + veredicto. Este es el Core Value | HIGH | Es lo que se vende. Requiere T1, T3, T10 y la integración ERP |
| D2 | **Estado explícito "peso teórico incompleto"** con auditoría apoyada en la evidencia visual | Ningún producto relevado modela la realidad de un ERP con datos maestros incompletos. Los sistemas asumen que el peso teórico existe. Este estado convierte un dato faltante en una ruta de trabajo válida en vez de un bloqueo | MEDIUM | Tercer veredicto además de OK/BLOQUEADO. Marca el registro como "auditado visualmente por [usuario]" y lista los artículos sin peso maestro, lo que además genera un reporte accionable para que el cliente corrija su ERP |
| D3 | **Captura de todo con un solo botón** | El mercado va hacia lo desatendido (kiosco + ANPR + barrera). Acá el diferencial es lo opuesto y más honesto para una portería argentina real: operación atendida con interacción mínima. Un botón dispara peso + N cámaras + asociación al viaje | HIGH | Latencia percibida < 2 s. Feedback inequívoco de éxito/fallo por cámara |
| D4 | **Paquete de evidencia exportable para reclamo** (ZIP con fotos originales + manifiesto + hashes SHA-256 + PDF resumen firmado) | Los weighbridge software guardan fotos y dejan verlas; ninguno de los relevados exporta un paquete defendible. NIST recomienda SHA-256 como estándar de verificación de evidencia digital, y la práctica forense exige hash en ingesta + log de accesos a prueba de manipulación | MEDIUM | Hash calculado al momento de la captura, no al exportar. El manifiesto lista cada archivo con su hash, timestamp, cámara y operador. Verificador incluido para que un tercero valide el ZIP. Alto valor comercial, costo moderado |
| D5 | **Modo simulación con archivos de video como fuente** | Permite demostrar el producto en una reunión comercial sin hardware, y correr pruebas de aceptación deterministas. Es diferencial de venta y de calidad | LOW | Ya está en el alcance activo. Vale explotarlo también como argumento comercial, no solo como andamio de desarrollo |
| D6 | **Trazabilidad en tiempo real para Compras** (ver el remito y la carga del proveedor en el instante) | Pedido explícito del documento fuente y el argumento que justifica el proyecto ante Compras | MEDIUM | ⚠️ **Conflicto de alcance**: PROJECT.md excluye interfaz web y móvil. Ver "Conflictos a resolver" |
| D7 | **Detección de espacio vacío / utilización de la carga por visión** | El documento fuente pide "auditar espacios vacíos" — es el complemento visual del control de peso. Existe mercado probado (CargoSight de Fraunhofer IML estima área libre y volumen restante desde una sola foto; SkyBitz SkyCamera reporta ocupación de piso y cubicaje) | HIGH | Alto valor, alto riesgo. Un porcentaje de ocupación mal estimado destruye la confianza en todo el sistema. Diferir a v2. Interín: la foto cenital cruda ya deja auditar a ojo |
| D8 | **Alertas de calidad de la propia evidencia** (foto borrosa, sobreexpuesta, obstruida, cámara desalineada) | Una foto ilegible se descubre meses después, cuando ya no sirve. Ningún producto relevado lo hace | MEDIUM | Chequeos baratos con OpenCV: varianza del Laplaciano para foco, histograma para exposición. Alerta al portero en el momento, cuando todavía puede repetir la toma |
| D9 | **Autoselección del viaje por patente** (LPR dispara la búsqueda y precarga el viaje, el operador confirma) | El documento fuente lo ubica en Fase 2; el usuario lo adelantó a v1. Es el salto real de productividad en la fila de camiones | HIGH | Requiere D1 y T12. Diseñar como *sugerencia*, jamás como acción automática |
| D10 | **Reporte de discrepancias recurrentes por transportista / chofer / proveedor** | Convierte el dato de auditoría en inteligencia de negocio: "este transportista tiene 8 desvíos negativos en 3 meses". Es el argumento con el que Administración justifica el sistema | LOW | Solo agregación sobre datos que ya se capturan. Costo bajo, valor percibido muy alto |

### Anti-Features (No construir)

| # | Anti-feature | Por qué la piden | Por qué es problemática | Alternativa |
|---|--------------|------------------|-------------------------|-------------|
| A1 | **Operación desatendida con control automático de barrera y semáforo** | Es la tendencia del mercado de básculas (DataBridge MS gestiona luces, lazos y barreras; kioscos con intercomunicador y voz) | Exige I/O físico, PLC, lazos inductivos, fotocélulas y una responsabilidad de seguridad enorme. Multiplica el hardware y el riesgo de un producto que hoy es de software. La portería relevada es atendida | El sistema emite el veredicto "APTO PARA SALIR / BLOQUEADO" en pantalla grande; el portero acciona la barrera. Dejar un puerto de salida de señal para agregarlo si un cliente lo paga |
| A2 | **Escritura en ERP, balanza o Geomov** | Parece natural cerrar el viaje o marcar el remito como despachado | Restricción dura del proyecto (solo GET/SELECT). Además, escribir en un ERP productivo desde una app de portería es un riesgo de corrupción de datos que ningún cliente va a aceptar en la primera venta | Publicar eventos solo en la base local. Exportar archivos de conciliación (CSV/XML) que el ERP importe bajo su propio control |
| A3 | **Edición o retoque de las fotos capturadas** | "Recortar", "aclarar", "girar" parecen ayudas inocentes | Destruye el valor probatorio. Si la imagen es editable, la contraparte del reclamo la impugna y todo el sistema de evidencia se cae | Original inmutable con hash. Anotaciones y recortes como capa derivada separada, con la original siempre recuperable |
| A4 | **Borrado de transacciones o de evidencia por el operador** | "Me equivoqué de viaje", "se cargó dos veces" | Es exactamente el agujero por donde entra el fraude que el sistema pretende detectar | Anulación lógica con motivo obligatorio, autorización de supervisor y registro en el log. La transacción anulada sigue existiendo y visible en reportes |
| A5 | **LPR como identificador único que dispara el flujo sin confirmación** | Es el argumento de venta de todo proveedor de ANPR | Con 90-98% de acierto en condiciones reales argentinas, entre 2 y 10 camiones de cada 100 quedan mal identificados. En un sistema cuyo propósito es auditar carga, asociar la evidencia al camión equivocado es peor que no tener LPR | LPR propone, operador dispone. Umbral de confianza configurable; por debajo del umbral, corrección manual obligatoria (ver sección LPR) |
| A6 | **OCR automático del remito de proveedor con extracción de artículos y cantidades** | "Ya que sacamos la foto, que lea el remito" | Los remitos de proveedores argentinos son heterogéneos: preimpresos, manuscritos, térmicos borroneados, con carbónico. La precisión sería baja y errática, y un dato extraído mal genera *más* confianza indebida que un campo vacío | Capturar imagen legible + tipear solo el número de remito (un campo, con validación). El OCR queda como sugerencia opcional a evaluar en v2 sobre la evidencia ya acumulada |
| A7 | **Videovigilancia continua 24/7** | "Si ya tenemos las cámaras..." | Ya excluido en PROJECT.md, y bien excluido: multiplica almacenamiento y no aporta a auditar la carga. Además cambia el encuadre legal (pasa a ser videovigilancia, con obligaciones de cartelería y protección de datos) | Captura por evento. Opcionalmente, un clip corto (5-10 s) alrededor del instante de captura, que es donde está el valor |
| A8 | **Facturación, liquidación de fletes o gestión de stock** | Aparece apenas se ven los pesos y los remitos juntos | Es el dominio del ERP. Entrar ahí multiplica el alcance, obliga a cumplimiento fiscal AFIP y compite con el sistema que el cliente ya pagó | Exportar los datos que el ERP necesita. Ser el mejor sistema de evidencia, no un ERP mediocre |
| A9 | **Pesaje por ejes y clasificación automática de vehículo** | Suena a control de sobrecarga vial | Requiere balanza multi-plataforma con celdas por eje. Hardware que el cliente no tiene y que no resuelve el problema de negocio (diferencia contra remito, no sobrecarga legal) | Peso total, que es lo que la balanza existente entrega |
| A10 | **Multi-planta / multi-balanza con consolidación central en v1** | Los competidores lo listan (Latorre gestiona hasta 4 balanzas por PC) | Complejidad de sincronización, red y conflictos que no compra ningún valor en la primera instalación | Modelar `sitio_id` y `balanza_id` en el esquema desde el día uno para no refactorizar, pero implementar y validar un solo puesto |
| A11 | **Entrenamiento de modelos propios y etiquetado de datasets** | "Nuestros camiones son distintos" | Ya excluido en PROJECT.md. Es un proyecto de datos completo dentro del proyecto | Modelos preentrenados. Si aparece una necesidad real, se resuelve con un motor LPR comercial |
| A12 | **Notificaciones push / email masivas a toda la organización** | "Que le avise a Compras" | Se convierte en ruido y en soporte técnico de servidores SMTP en el primer mes | Panel semáforo consultable + un digest diario. Alertas puntuales solo para el bloqueo por tolerancia |

---

## Profundizaciones solicitadas

### 1. Robustez operativa que se da por sentada en una portería

Estas no aparecen en los folletos porque nadie las publicita — aparecen en la primera semana de uso, y su ausencia mata la adopción.

| Aspecto | Expectativa implícita | Feature que la cubre |
|---------|----------------------|---------------------|
| Corte de energía | La app vuelve sola, sin login de Windows, y recupera el estado exacto | T23 + T1 |
| Cambio de turno | El turno entrante ve qué quedó abierto y de quién era | T8 + T1 |
| Cola de camiones | La operación completa por camión no puede superar el tiempo en que el próximo llega a la balanza. Los YMS venden check-in en <30-45 s; ese es el benchmark | T14, T22, D3 |
| Guantes y frío | Botones grandes, sin gestos finos, sin doble clic | T22 |
| Contraluz y noche | Pantalla legible con sol de frente y de noche; foto usable con iluminación pobre | T22 + D8 |
| Se cayó el ERP / la balanza / la red | Se sigue operando y se concilia después | T18 |
| Se cayó una cámara | El resto sigue; la transacción queda marcada como evidencia parcial | T20 + T3 |
| El portero no es informático | Ningún error técnico visible; nada que configurar por archivo | T21 |

**Nota crítica de diseño:** el fallo más caro no es que el sistema se caiga, es que capture *parcialmente* sin avisar. Una transacción con 3 de 4 fotos que aparenta estar completa es peor que una transacción fallida, porque destruye la confianza en todo el archivo de evidencia retroactivamente. La sincronía debe ser todo-o-marcado-como-incompleto.

### 2. Gestión de evidencia fotográfica para auditoría

Lo que efectivamente hacen los productos relevados (barra actual del mercado):

- Captura automática al guardar/imprimir el ticket, hasta 4 cámaras por balanza (Imagic, Mandalay)
- Almacenamiento en disco indexado por número de ticket, fecha, hora y tipo de pesada (primera/segunda)
- Impresión de las fotos en el ticket, incluso 4+4 imágenes en un solo PDF (Imagic)
- Visor histórico para revisión gerencial
- Búsqueda por ticket/sitio/fecha/hora (Mandalay)
- Retención de 7 años (Mandalay), 720p mínimo, ≤500 KB por imagen
- Envío automático del PDF con imágenes por email

Lo que **no** hace ninguno de los relevados, y es donde está el diferencial (D4):

- Hash criptográfico en ingesta (SHA-256, estándar recomendado por NIST para evidencia digital)
- Manifiesto de exportación con cadena de custodia
- Log a prueba de manipulación de cada acceso, descarga y exportación (quién, cuándo, para qué)
- Almacenamiento WORM o equivalente para el log

**Recomendación práctica y proporcionada:** no construir un DEMS forense. Construir tres cosas concretas — hash SHA-256 al capturar, log append-only de accesos y exportaciones, y un exportador de paquete verificable. Cubre el 90% del valor probatorio en un reclamo comercial (que se resuelve por negociación, no en tribunales) a una fracción del costo.

### 3. Precisión de LPR y mecanismos de respaldo

| Fuente | Precisión reportada | Contexto |
|--------|--------------------|-----------| 
| Cámaras ANPR dedicadas (Nortech, industria) | 95-99% | Condiciones normales, hardware dedicado con IR y obturador rápido |
| Puertos y terminales (visionplatform.ai) | >95% | Con obturador, iluminación IR y sensor correctamente elegidos |
| Sistema LPR Microcentro CABA | ~90% | Despliegue urbano real argentino |
| Investigación académica sobre patentes Mercosur | 95-98% | Software libre, condiciones controladas |

**Interpretación honesta:** 95% en producción significa 1 de cada 20 camiones mal leído. En un turno de 60 camiones son 3 errores diarios. Sin ruta de corrección, el portero abandona el LPR en la primera semana.

Mecanismos de respaldo que la industria considera obligatorios:

1. **Score de confianza por lectura** y umbral configurable. Los operadores calibran el umbral según su tolerancia: umbral alto = más revisión manual, cero falsos positivos; umbral bajo = menos trabajo manual, algunos falsos positivos (Survision, TagMaster)
2. **Reintento con frame adicional** antes de declarar fallo
3. **Marcado automático para revisión del operador** cuando la confianza cae bajo el umbral o la placa es ilegible
4. **Corrección manual siempre disponible**, incluso con confianza alta
5. **Validación de formato** (Mercosur LL-NNN-LL / anterior LLL-NNN) como filtro post-OCR
6. **Recorte de la placa visible junto a la lectura** para que el operador verifique en un vistazo, sin abrir la foto completa

**Decisión recomendada para v1:** LPR pre-selecciona el viaje y muestra el recorte de placa; el operador confirma con un toque. Registrar la tasa de aciertos en producción para poder, más adelante y con datos, subir el nivel de automatización. Registrar cada corrección manual: es el dataset de calidad del propio sistema y el argumento para justificar (o descartar) mejor hardware de cámara.

### 4. Tolerancias y excepciones

Patrón consolidado en la industria:

- Validación de tolerancia contra la orden/remito antes de aprobar la transacción
- Alerta cuando la diferencia entre pesada llena y vacía cae fuera de rango esperado
- Cruce del peso neto contra la cantidad de la orden, con investigación disparada si excede la tolerancia de empaque
- Override disponible pero condicionado al rol (operador captura, supervisor autoriza)
- Detección de patrones sospechosos: pesadas repetidas sin motivo válido, sobrepeso

Diseño recomendado para este producto:

| Banda | Regla | Acción |
|-------|-------|--------|
| Dentro de tolerancia | \|Δ\| ≤ tolerancia_aceptación (ej. 50 kg) | Aprobar y liberar. Registrar sin alerta |
| Zona de alerta | tolerancia_aceptación < \|Δ\| ≤ tolerancia_bloqueo | Advertir. Permitir liberar con motivo. Notificar a Administración |
| Bloqueo | \|Δ\| > tolerancia_bloqueo (ej. 2.000 kg) | Bloquear. Solo un supervisor libera, con motivo obligatorio y foto adicional |
| Peso teórico incompleto | Faltan pesos maestros de uno o más artículos | Tercer estado (D2). No comparar. Exigir auditoría visual explícita con firma de usuario |
| Sin peso real | Balanza no disponible | Peso manual marcado + foto del display obligatoria. Cola de conciliación |

Detalles que importan y suelen olvidarse:

- Tolerancia en kg **y** en porcentaje, aplicando la más restrictiva. Un remito de 200 kg y uno de 28 toneladas no se auditan con el mismo criterio absoluto
- Configurable por rubro de artículo, no solo global
- El signo importa: faltante y sobrante son excepciones distintas con implicancias distintas (robo vs. error de carga). Reportarlos por separado
- Un override **nunca** borra la alerta original; la deja con autorización adjunta

### 5. Reportes y exportaciones esperados

Estándar del mercado: exportación en PDF, Excel, CSV, texto (y XML / SAP IDoc en gama alta), filtrable por fecha, sitio, cliente, vehículo, transportista, material, operador y turno; envío programado por email a supervisores y auditores.

| Reporte | Consumidor | Prioridad | Contenido |
|---------|-----------|-----------|-----------|
| Movimientos del día (ingresos y egresos) | Portería / Supervisor | P1 | Hora, patente, chofer, transportista, tipo, peso, veredicto, operador |
| Detalle de transacción con evidencia | Administración | P1 | Ficha completa + fotos + remitos + log de la transacción |
| Excepciones y bloqueos | Administración / Compras | P1 | Solo desvíos, con Δ, motivo, quién autorizó |
| Tiempos de espera de proveedores (SLA) | Compras | P1 | Ingreso, atención, egreso, tiempo total, incumplimientos de umbral |
| Conciliación remito vs. balanza | Administración | P2 | Por remito: teórico, real, Δ, estado |
| Artículos sin peso maestro | Administración / Sistemas | P2 | Salida accionable para que el cliente corrija su ERP (D2) |
| Discrepancias recurrentes por transportista/chofer/proveedor | Administración / Compras | P2 | Agregación histórica (D10) |
| Paquete de evidencia para reclamo | Administración / Legales | P2 | ZIP con fotos, manifiesto y hashes (D4) |
| Actividad por operador y turno | Supervisor | P3 | Volumen, tiempos, correcciones manuales, overrides |
| Log de auditoría | Auditoría interna | P3 | Exportable, filtrable, no editable |

Formatos mínimos: **PDF** (para presentar e imprimir), **CSV/Excel** (para que Administración lo trabaje). El envío programado por email es P3 — trae dependencia de SMTP y soporte.

---

## Feature Dependencies

```
[T1 Transacción en dos tiempos]
    └──requires──> [Persistencia local con recuperación al arranque]

[D1 Auditoría peso real vs teórico]
    └──requires──> [T1 Transacción en dos tiempos]
    └──requires──> [T10 Tolerancias configurables]
    └──requires──> [Integración balanza (peso real)]
    └──requires──> [Integración ERP PALJET (peso teórico)]
    └──requires──> [T3 Captura sincronizada]  (el veredicto sin evidencia no sirve)

[D2 Peso teórico incompleto]
    └──requires──> [D1 Auditoría]
    └──requires──> [T3 Captura sincronizada]   (la evidencia visual ES la auditoría)
    └──requires──> [T7 Roles]                   (alguien firma la auditoría visual)

[T3 Captura sincronizada multi-cámara]
    └──requires──> [Abstracción de fuente de video (RTSP / USB / archivo)]
    └──requires──> [T20 Reconexión automática]

[T4 Overlay] ──requires──> [T3]  (metadatos disponibles en el instante de captura)
[T5 Búsqueda de evidencia] ──requires──> [T3 + T4]
[T6 Retención] ──requires──> [T5]  (no se purga lo que no se sabe encontrar)

[D4 Paquete de evidencia exportable]
    └──requires──> [T5 Búsqueda]
    └──requires──> [Hash SHA-256 en ingesta]  ← decisión temprana, no retrofiteable
    └──requires──> [T9 Log de auditoría]

[T12 LPR con umbral y corrección]
    └──requires──> [T3 Captura]
    └──requires──> [T13 Validación de formato Mercosur/anterior]

[D9 Autoselección de viaje por patente]
    └──requires──> [T12 LPR]
    └──requires──> [Precarga de viajes]
    └──requires──> [T17 Maestro local de vehículos]

[T16 Semáforo SLA] ──requires──> [T15 Cronómetro] ──requires──> [Registro de ingreso]

[T18 Modo contingencia] ──requires──> [T17 Maestro local cacheado]
[T18 Modo contingencia] ──requires──> [T9 Log]  (todo lo manual debe quedar marcado)

[T11 Excepciones] ──requires──> [T7 Roles] + [T9 Log]
[T19 Reportes] ──requires──> [T1 + T9]

[D8 Calidad de evidencia] ──enhances──> [T3]
[D10 Discrepancias recurrentes] ──enhances──> [D1]
[D5 Modo simulación] ──enhances──> [T3]  (y habilita pruebas deterministas de todo)

[A1 Barrera automática] ──conflicts──> [T7 Autorización humana de excepciones]
[D6 Visibilidad Compras] ──conflicts──> [Out of Scope: sin interfaz web/móvil]
[A6 OCR de remitos] ──conflicts──> [Confianza en el dato: mejor vacío que erróneo]
```

### Notas de dependencia

- **El hash en ingesta (D4) es una decisión de arquitectura temprana, no una feature tardía.** Si la evidencia acumulada durante meses no fue hasheada al capturarse, el paquete probatorio pierde su valor para todo ese histórico. Debe estar desde la primera captura persistida, aunque el exportador se construya después.
- **T3 es la raíz del árbol.** Casi todo el valor diferencial cuelga de que la captura sincronizada sea confiable. Es coherente que el Bloque 1 del proyecto sea el subsistema de visión.
- **D1 (el corazón del negocio) depende de las dos integraciones que están planificadas al final.** Es el riesgo estructural del roadmap: se valida tarde lo que más importa. Mitigación: construir D1 completo contra adaptadores simulados de balanza y ERP con datos realistas, de modo que la integración final sea sustituir el adaptador y no descubrir el dominio.
- **T18 (contingencia) parece secundaria y no lo es.** Con integraciones al final, todo el desarrollo intermedio *es* modo contingencia. Conviene construirla primero, como camino normal, y tratar las integraciones como el camino optimizado.
- **A1 y T7 son incompatibles por diseño.** Automatizar la barrera vacía de sentido el bloqueo por tolerancia, que necesita una decisión humana registrada.

---

## MVP Definition

### Launch With (v1)

- [ ] T3 Captura sincronizada multi-cámara con un botón — es el Core Value; sin esto no hay producto
- [ ] T4 Overlay de datos sobre la imagen — sin contexto embebido la foto no es evidencia
- [ ] Hash SHA-256 en ingesta — decisión no retrofiteable, aunque el exportador venga después
- [ ] T5 Búsqueda y recuperación de evidencia — guardar sin poder encontrar equivale a no guardar
- [ ] T1 Transacción en dos tiempos con estado persistente — modelo base de todo el dominio
- [ ] T12 + T13 LPR con umbral, recorte de placa, confirmación y corrección manual — adelantado a v1 por decisión del usuario
- [ ] T7 + T8 Roles, permisos y sesión de operador con cambio de turno
- [ ] T9 Log de auditoría append-only
- [ ] T22 + T23 UI táctil operable con guantes + recuperación tras corte de energía
- [ ] T20 Reconexión automática de cámaras con estado visible
- [ ] T21 Instalador y configuración por UI
- [ ] D5 Modo simulación con archivos de video — habilita desarrollo y demo sin hardware
- [ ] T14 Digitalización de documentación por webcam
- [ ] T10 + T11 Tolerancias configurables y excepciones con motivo y autorización
- [ ] T18 Modo contingencia (que en v1 es el camino normal)
- [ ] T2 Ticket numerado imprimible
- [ ] T19 Reportes P1 con exportación PDF/CSV

### Add After Validation (v1.x)

- [ ] D1 Auditoría automática peso real vs teórico — al conectar balanza y ERP PALJET
- [ ] D2 Estado "peso teórico incompleto" — junto con D1
- [ ] T15 + T16 Cronómetro y semáforo SLA — al estar operativo el flujo de ingreso
- [ ] T17 Maestro local sincronizado del ERP — al tener acceso a PALJET
- [ ] D4 Paquete de evidencia exportable — cuando exista histórico que valga la pena exportar
- [ ] T6 Retención y archivado — cuando el volumen acumulado lo justifique (~3-6 meses de uso)
- [ ] D8 Alertas de calidad de evidencia — tras ver qué falla realmente en campo
- [ ] D9 Autoselección de viaje por patente — cuando haya tasa de acierto medida de T12
- [ ] D10 Reporte de discrepancias recurrentes — necesita histórico
- [ ] Integración Geomov o carga manual rápida — sujeto a acceso

### Future Consideration (v2+)

- [ ] D7 Detección de espacio vacío / utilización por visión — alto valor, alto riesgo; requiere validación con datos reales antes de prometerlo
- [ ] Clip de video corto alrededor del instante de captura
- [ ] Multi-balanza / multi-planta (esquema preparado desde v1, implementación diferida)
- [ ] Listas blancas/negras de vehículos y choferes
- [ ] Vista de solo lectura en red para Compras — resolver antes el conflicto de alcance
- [ ] OCR asistido de remitos, evaluado sobre la evidencia ya acumulada

---

## Feature Prioritization Matrix

| Feature | Valor para el usuario | Costo de implementación | Prioridad |
|---------|----------------------|------------------------|-----------|
| T3 Captura sincronizada multi-cámara | HIGH | HIGH | P1 |
| T1 Transacción en dos tiempos persistente | HIGH | MEDIUM | P1 |
| T5 Búsqueda de evidencia | HIGH | MEDIUM | P1 |
| T4 Overlay sobre imagen | HIGH | LOW | P1 |
| Hash SHA-256 en ingesta | MEDIUM | LOW | P1 (no retrofiteable) |
| T12 LPR con umbral y corrección manual | HIGH | HIGH | P1 (decisión del usuario) |
| T7/T8 Roles, permisos, turno | HIGH | MEDIUM | P1 |
| T9 Log de auditoría | HIGH | LOW | P1 |
| T22 UI táctil con guantes | HIGH | MEDIUM | P1 |
| T23 Recuperación tras corte | HIGH | LOW | P1 |
| T10/T11 Tolerancias y excepciones | HIGH | LOW | P1 |
| T18 Modo contingencia | HIGH | HIGH | P1 |
| T20 Reconexión de cámaras | HIGH | MEDIUM | P1 |
| T21 Instalador y config por UI | HIGH | MEDIUM | P1 |
| T2 Ticket imprimible | MEDIUM | LOW | P1 |
| T14 Digitalización de documentos | HIGH | MEDIUM | P1 |
| D5 Modo simulación por video | MEDIUM | LOW | P1 |
| T19 Reportes P1 | HIGH | MEDIUM | P1 |
| D1 Auditoría peso real vs teórico | HIGH | HIGH | P2 (bloqueado por integraciones) |
| D2 Peso teórico incompleto | HIGH | MEDIUM | P2 |
| T15/T16 Cronómetro y semáforo SLA | HIGH | LOW | P2 |
| T17 Maestro local cacheado | HIGH | MEDIUM | P2 |
| D4 Paquete de evidencia exportable | HIGH | MEDIUM | P2 |
| T6 Retención y archivado | MEDIUM | MEDIUM | P2 |
| D10 Discrepancias recurrentes | MEDIUM | LOW | P2 |
| D8 Calidad de evidencia | MEDIUM | MEDIUM | P2 |
| D9 Autoselección por patente | HIGH | MEDIUM | P2 |
| T13 Validación formato Mercosur | MEDIUM | LOW | P2 |
| D6 Visibilidad Compras tiempo real | HIGH | MEDIUM | P2 (conflicto de alcance) |
| D7 Detección de espacio vacío | HIGH | HIGH | P3 |
| Motor dual YOLO/OpenCV | LOW (mercado) | MEDIUM | P3 — requisito propio del usuario, no del negocio |
| Multi-balanza / multi-planta | LOW | HIGH | P3 |
| Listas blancas/negras | LOW | LOW | P3 |

---

## Competitor Feature Analysis

| Feature | Mettler Toledo DataBridge MS | Software de balanza argentino (Balser / Latorre / KYASERV / Casilda) | YMS (YardView / Kaleris) | Nuestro enfoque |
|---------|------------------------------|--------------------------------------------------------------------|--------------------------|-----------------|
| Registro de pesadas y ticket | Sí, núcleo | Sí, núcleo. Ticket personalizable, envío por email, cumplimiento AFIP RG 3890/2016 y 271/1998 | No (no pesan) | Sí, pero el ticket es subproducto: el registro central es la transacción auditada con evidencia |
| Captura fotográfica ligada al pesaje | Sí, cámaras como parte del paquete antifraude | No documentado en ninguno de los sitios relevados | Cámaras con IA en portería | **Núcleo del producto**, multi-cámara sincronizada, no accesorio |
| Multi-cámara | Sí | No documentado | Parcial | Sí: 2 HD (superior + lateral) + webcam de documentos + cámara LPR |
| ANPR / LPR | Sí, integrado con terminales de chofer | No documentado | Sí, cámaras con IA | Sí, con umbral de confianza y confirmación del operador |
| Tolerancias configurables | Sí, criterios personalizables de transacción | No documentado | N/A | Sí, escalonadas (aceptar / alertar / bloquear), en kg y %, por rubro |
| Peso teórico incompleto | No — asume que el maestro está completo | No | N/A | **Estado de primera clase.** Diferencial claro |
| Antifraude | Curva de peso, celdas POWERCELL PDX con detección de manipulación, fotocélulas de posición | "Protecciones antifraude a nivel programa y base de datos" (Latorre) | N/A | A nivel software y evidencia: log append-only, hash en ingesta, sin borrado, fotos inmutables. No compite en hardware antifraude |
| Operación desatendida / barrera | Sí: luces, lazos, barreras, terminales de chofer, kiosco | Parcial (KYASERV ofrece pesaje automatizado para balanza pública) | Sí, portería no atendida | **Deliberadamente no** (A1). Portería atendida con interacción mínima |
| Dwell time / SLA de proveedores | No | No | Sí, núcleo: alertas por color al acercarse al umbral de detention | Sí, semáforo configurable — trae el patrón del YMS al mundo de la balanza |
| Cadena de custodia / exportación probatoria | No documentado | No | No | **Diferencial** (D4): hash SHA-256, manifiesto, log de accesos |
| Escritura en ERP | Sí, bidireccional | Parcial | Sí | **No, por diseño.** Solo lectura + export de conciliación |
| Plataforma | Escritorio + cloud | Escritorio Windows | Cloud + móvil | Escritorio Windows, local |

**Lectura estratégica:** contra los productos internacionales este proyecto pierde en integración de hardware y en operación desatendida, y gana en profundidad de evidencia visual y en modelar la realidad de un ERP incompleto. Contra el mercado argentino de software de balanza gana en casi todo, porque esos productos son registros de pesadas con ticket. **El posicionamiento correcto no es "software de balanza" — es "sistema de auditoría de carga con evidencia visual, que además usa la balanza".**

---

## Conflictos a resolver antes del roadmap

1. **D6 (visibilidad en tiempo real para Compras) vs. Out of Scope "sin interfaz web ni móvil".** El documento fuente lo pide explícitamente y es un argumento de venta fuerte. Opciones: (a) vista de solo lectura en LAN servida por la misma app; (b) reporte/digest automático; (c) reconocer que Compras entra al mismo escritorio; (d) reafirmar la exclusión y bajar el requerimiento. **Recomendación: (a) más adelante** — una vista de solo lectura no es "una aplicación web" en el sentido que la exclusión quiso evitar, y desbloquea el valor para el usuario que financia el proyecto.

2. **Motor dual YOLO/OpenCV.** Ningún producto del rubro ofrece elegir motor de visión, y ningún requerimiento de negocio lo pide. Ya está marcado como "⚠️ Revisar" en PROJECT.md. Desde la perspectiva de features es costo sin valor de mercado; su justificación es del usuario, no del cliente. Debería tener la prioridad más baja de v1 o salir de v1.

3. **D1 (el corazón del negocio) queda al final del roadmap.** Riesgo de validar tarde lo que más importa. Mitigar construyendo D1 completo contra adaptadores simulados desde temprano.

---

## Sources

**Weighbridge / truck scale software** (confianza MEDIUM — páginas de producto de vendors; describen features reales pero con sesgo comercial):
- [METTLER TOLEDO DataBridge Vehicle Scale Software](https://www.mt.com/gb/en/home/products/Transport_and_Logistics_Solutions/weighbridge-and-rail-scale-systems/weighbridge-systems/databridge-software-61046589001.html)
- [METTLER TOLEDO DataBridge MS](https://www.mt.com/be/en/home/products/Transport_and_Logistics_Solutions/weighbridge/veh-scale-management-system/DataBridgeMS.html)
- [METTLER TOLEDO — Fraud Prevention at the Weighbridge](https://www.mt.com/us/en/home/library/guides/transport-logistics/vehicle_scale_fraud_prevention.html)
- [Rice Lake OnTrak Truck Scale Data Management Software](https://www.ricelake.com/products/ontrak-truck-scale-data-management-software/)
- [Endel Digital WeighMAST — Enterprise AI Weighbridge Software](https://endel.digital/weighbridge-software/)
- [Amity Advanced Weighbridge Software](https://www.amitysoftware.com/weighbridge-software/)
- [UniWin Weighbridge Automation](https://uniwin.software/weighbridge-automation/)
- [Mandalay Technologies — Weighbridge Image Capture](https://www.mandalaytech.com.au/products/image-capture/)
- [Imagic Solution — CCTV with Weighbridge Software](https://www.imagicsolution.com/CCTV_With_Weighbridge_Solution.php)
- [Weigherps — What is an unattended terminal for a weighbridge?](https://weigherps.com/what-is-an-unattended-terminal-for-a-weighbridge/)
- [Racklify — Weighbridge Software Integration Guide](https://racklify.com/encyclopedia/automation-in-action-integrating-software-with-your-weighbridge-truck-scale/)
- [Weightru — Weighbridge Fraud: 5 Crafty Ways Truck Scales Can Be Tricked](https://www.weightru.co.uk/weighbridge-fraud/)

**Mercado argentino** (confianza MEDIUM — sitios escuetos; la ausencia de una feature en el sitio no prueba su ausencia en el producto):
- [Balser — Software de pesaje de camiones](https://balser.com.ar/productos/software-de-pesaje/software-de-pesaje-de-camiones/)
- [Latorre Pesaje — Software de Pesaje](https://www.latorrepesaje.com.ar/web/productos/software-de-pesaje/)
- [KYASERV — Software Pesaje Camiones](https://kyaserv.com.ar/web/software-pesaje-camiones-kyaserv/)
- [Fulcrum — DataBridge software de básculas de camiones](https://www.fulcrum.com.ar/pesajeindustrial/software-de-balanza/databridge-software-de-basculas-de-camiones-3047)
- [Ingelsoft — Software para control en balanza de camiones](https://www.ingelsoft.com/products/balanzas/balanzas-camioneras/software-para-control-en-balanza-de-camiones/)

**Yard Management Systems** (confianza MEDIUM-HIGH — coincidencia entre múltiples vendors independientes):
- [YardView — Features](https://www.yardview.com/features)
- [project44 — What is yard check-in and check-out?](https://www.project44.com/resources/what-is-yard-check-in-and-check-out/)
- [Kaleris — Yard Management](https://kaleris.com/solutions/yard-management/)
- [Mobisoft — Yard Management System Guide](https://mobisoftinfotech.com/resources/blog/transportation-logistics/yard-management-system-guide)

**LPR / ANPR** (confianza MEDIUM-HIGH — cifras de precisión de vendors, contrastadas con fuentes académicas y con un despliegue público argentino):
- [Survision — LPR Confidence Level: A Closer Look](https://survisiongroup.com/post-lpr-confidence-level:-a-closer-look)
- [Avutec — Understanding ANPR accuracy metrics that matter](https://avutec.com/understanding-anpr-accuracy-metrics-that-matter/)
- [Nortech — ANPR for Gates & Barriers](https://blog.nortechcontrol.com/anpr-for-gates/)
- [Nedap ANPR Lumo](https://www.nedapidentification.com/products/anpr/anpr-lumo/)
- [visionplatform.ai — ANPR/LPR in manufacturing](https://visionplatform.ai/anpr-lpr-in-manufacturing/)
- [Ciudad de Buenos Aires — Sistema de reconocimiento de patentes en el Microcentro](https://buenosaires.gob.ar/noticias/las-ventajas-de-la-nueva-tecnologia)
- [Software libre para reconocimiento automático de las nuevas patentes del Mercosur (Congreso de Vialidad)](https://congresodevialidad.org.ar/congreso2016/TRA/TRA-147.pdf)

**Evidencia digital y cadena de custodia** (confianza MEDIUM — fuentes legales/forenses generales, no específicas de logística):
- [Truescreen — Digital Chain of Custody: ISO 27037 and Best Practices](https://truescreen.io/articles/digital-chain-of-custody-guide/)
- [DigitalEvidence.ai — Video Evidence Authentication: Legal Standards](https://digitalevidence.ai/blog/video-evidence-authentication-standards-courts)
- [Focal Forensics — Video Evidence Chain of Custody Checklist](https://focalforensics.com/blog/video-evidence-chain-of-custody-checklist)

**Gate pass / visitor management industrial** (confianza MEDIUM):
- [FacilityOS — Audit-Ready Visitor Logs for Industrial Safety Cases](https://www.facilityos.com/blog/audit-ready-visitor-logs-for-industrial-safety-cases)
- [GateSentry — Guardhouse Software](https://gatesentry.com/blog/guardhouse-software/)
- [Entry2Exit — What is a Gate Pass?](https://entry2exit.com/blog/what-is-a-gate-pass/)

**Visión de carga / utilización de espacio** (confianza MEDIUM-HIGH — incluye una fuente de investigación aplicada):
- [Fraunhofer IML — CargoSight](https://www.iml.fraunhofer.de/en/fields_of_activity/material-flow-systems/software_engineering/cargosight.html)
- [SkyBitz SkyCamera — Real Time Cargo Visibility with AI Cameras](https://www.skybitz.com/ai-powered-skycamera)

**Fuentes internas del proyecto** (confianza HIGH):
- `.planning/PROJECT.md`
- `Requerimientos App logista.docx`

### Nota sobre confianza

No había proveedores de búsqueda curados configurados (`brave_search`, `exa_search`, `tavily_search`, `firecrawl`, `ref_search`, `perplexity`, `jina` todos en `false`, y `gsd-tools` no disponible en PATH). Toda la investigación externa se hizo con WebSearch/WebFetch integrados. Consecuencias:

- **Confianza HIGH** en el mapa general de features: hay convergencia entre múltiples vendors independientes de cuatro familias de producto distintas.
- **Confianza MEDIUM** en detalles concretos (retención de 7 años, 4 cámaras por balanza, ≤500 KB por imagen): provienen de una o dos fuentes de vendor. Sirven como referencia de orden de magnitud, no como especificación.
- **Confianza MEDIUM-LOW** en el detalle del mercado argentino: los sitios locales son muy escuetos y no permiten distinguir "no lo tiene" de "no lo publica". Si hay oportunidad de acceder a demos o pliegos de esos productos, conviene verificarlo antes de fijar el posicionamiento competitivo.
- Las cifras de precisión de LPR provienen de material comercial y describen condiciones favorables. **Planificar contra el extremo bajo del rango (~90%), no contra el alto.**

---
*Feature research for: control de portería y pesaje de camiones con visión artificial*
*Researched: 2026-07-24*
