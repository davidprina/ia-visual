# Phase 1: Núcleo, evidencia trazable y contratos externos congelados - Discussion Log

> **Sólo registro de auditoría.** No usar como entrada de los agentes de planificación, investigación ni ejecución.
> Las decisiones están capturadas en `01-CONTEXT.md` — este registro preserva las alternativas que se consideraron.

**Fecha:** 2026-07-25
**Fase:** 1 — Núcleo, evidencia trazable y contratos externos congelados
**Áreas discutidas:** Formato de la evidencia, Autoría y operador, Alcance del esquema, Descubrimiento externo, Atomicidad ante corte de energía, La orden por línea de comandos, Compuerta de integración continua, Zona horaria y límite del día, Nombre y versionado del producto, Ventana de sincronía y gobernanza, Videos de referencia y datos de prueba, Inventario de licencias, Estrategia de pruebas

**Total:** 61 preguntas respondidas en 13 áreas.

---

## Formato de la evidencia

### Formato de imagen

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| JPEG calidad 95 | ~400 KB a 1080p, ~25-45 GB/año. El stream RTSP ya viene con pérdida | |
| PNG sin pérdida | ~3 MB por imagen, ~160-330 GB/año. Frame exacto del decodificador | |
| JPEG configurable por cámara | Calidad ajustable por cámara, sin pérdida donde el detalle importe | ✓ |

**Notas:** Se presentó la escala de volumen (50-100 camiones/día × 3 cámaras = 150-300 imágenes diarias) para dimensionar la decisión.

### Contenido de la imagen

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Frame limpio, overlay al mostrar | Datos dibujados al visualizar desde los metadatos | ✓ |
| Frame limpio + copia con datos quemados | Dos archivos por captura | |
| Fecha y hora quemadas | Estilo videovigilancia clásica | |

### Organización en disco

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Carpeta por fecha + nombre por hash | `evidencia/AAAA/MM/DD/<sha256>.jpg` | ✓ |
| Almacén direccionado por contenido puro | `cas/ab/cd/abcdef….jpg`, base como único índice | |
| Carpeta por movimiento de negocio | `evidencia/2026-07-25/viaje-1842/superior.jpg` | |

**Notas:** Se señaló antes de preguntar que la deduplicación por contenido rinde casi cero en este dominio (cada foto es única), y que el valor real del hash es que el nombre se deriva del contenido.

### Alcance de la integridad

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Hash + manifiesto + bitácora encadenada | Detecta edición, ausencia y borrado de registros completos | ✓ |
| Hash + manifiesto de captura | Detecta edición y foto faltante dentro de una captura | |
| Sólo hash por imagen | Exactamente EVI-05, nada más | |

**Notas:** Se advirtió que el encadenamiento debe arrancar en el registro uno o pierde valor para siempre.

### Verificación fallida

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Marcar comprometida y mostrarla así | Sigue accesible, señalada, con el hallazgo en bitácora | ✓ |
| Bloquear acceso hasta revisión | Exige un rol revisor que no está en v1 | |
| Sólo registrar en bitácora técnica | Nadie se entera | |

### Miniaturas

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| En la ingesta, guardada en SQLite | ~15 KB; la grilla se pinta con una consulta | ✓ |
| En la ingesta, junto al original en disco | Duplica cantidad de archivos | |
| No en la Fase 1 | Obliga a regenerar el histórico después | |

### Perfiles de la fuente de video

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Dos perfiles desde el día uno | Monitoreo y evidencia; la fuente de archivo devuelve el mismo flujo | ✓ |
| Un solo flujo, mejor resolución | Más simple; satura CPU en Fase 2 | |
| Un solo flujo configurable por cámara | Obliga a elegir entre visor fluido y evidencia nítida | |

### Retención y borrado

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Nunca borra solo; purga manual con lápida | Fila con hash, motivo, autor e instante | ✓ |
| Nunca borra en v1 | Sin herramienta cuando el disco se llene | |
| Purga automática por antigüedad | Un producto de auditoría que destruye evidencia sin intervención | |

**Notas:** Se acotó el alcance después de la elección: la Fase 1 fija esquema e invariante; la herramienta operable se difiere.

### Metadatos de procedencia

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Amplios, sólo en la base | La huella cubre píxeles puros | ✓ |
| Amplios + embebidos en el archivo | La huella pasaría a cubrir metadatos escritos por la app | |
| Mínimos del roadmap | No permite distinguir qué versión sacó cada foto | |

### Ubicación de base y evidencia

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Dos raíces independientes | Base en disco rápido, evidencia donde el cliente elija | ✓ |
| Una sola raíz de datos | Copia de seguridad más simple; SQLite en disco lento | |
| Dos raíces + réplica a red | Capacidad nueva, fuera de la Fase 1 | |

### Raíz de evidencia no disponible al arrancar

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Arranca degradado y bloquea capturas | Estado en rojo, permite consultar y reparar | ✓ |
| No arranca | Deja al portero sin herramienta ni salida | |
| Ruta local de respaldo | Evidencia partida en dos con reconciliación por construir | |

### Separación de bitácoras

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Dos cosas separadas | Técnica en archivos rotativos; auditoría en base, encadenada | ✓ |
| Una sola en la base | Depuración inflaría la cadena | |
| Una sola en archivos | La rotación borraría evidencia | |

### Exposición de métricas

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Memoria + volcado por comando | Sin costo en el camino crítico | ✓ |
| Memoria + muestreo a la base | Permite diagnóstico retrospectivo | |
| Memoria + vuelco al log técnico | Obliga a parsear texto | |

### Modo de reproducción de la fuente de archivo

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Los dos modos, elegibles | Tiempo real para frescura, velocidad máxima para CI | ✓ |
| Sólo tiempo real | CI tarda lo que duran los videos | |
| Sólo velocidad máxima | Imposible verificar el contrato de frescura | |

---

## Autoría y operador

### Tipo de identidad

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Perfiles locales sin contraseña | Selección de turno con un toque; cero fricción | |
| Usuarios con contraseña | Subsistema completo; no está en ningún requerimiento v1 | ✓ |
| Sin identidad | Obligaría a migrar el histórico después | |

**Notas:** Decisión del usuario por encima de la recomendación. Se señaló una vez que es alcance nuevo no derivado de los requerimientos y se procedió a ubicarlo correctamente en el tiempo.

### Alcance del subsistema en la Fase 1

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Modelo, credenciales y sellado de autoría | Pantalla de login llega con la interfaz | ✓ |
| Sólo el modelo de datos | Columnas nunca ejercitadas | |
| Subsistema completo | Desplazaría el objetivo real de la fase | |

### Roles

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Cuatro roles fijos del negocio | Portero, Logística, Compras, Administración | ✓ |
| Operador y administrador | La vista de Compras no encaja en ninguno | |
| Permisos configurables por usuario | Motor de autorización completo | |

### Captura sin sesión iniciada

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Se captura igual, firmada como no identificada | Misma regla que la captura parcial | ✓ |
| No se puede capturar | La portería dejaría de registrar evidencia | |
| Sesión permanente del equipo | La firma perdería significado | |

### Protección de la contraseña

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Argon2id + política mínima | Sólo longitud mínima; sin caducidad ni complejidad | ✓ |
| Argon2id + política corporativa completa | Argumento de pliego; mucha superficie | |
| bcrypt | Más débil ante hardware dedicado; límite de 72 bytes | |

### Primer usuario administrador

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Asistente de primer arranque | Sin credenciales por defecto en el producto | ✓ |
| Credenciales por defecto documentadas | Hallazgo directo en auditoría de seguridad | |
| Contraseña aleatoria mostrada por el instalador | Exige procedimiento de recuperación igual | |

### Relación con el usuario de Windows

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Identidad propia y aparte | El usuario de Windows sólo como diagnóstico | ✓ |
| Usuario de Windows como identidad | Contradice la decisión de credenciales | |
| Identidad propia con inicio de sesión único opcional | Capacidad entera, no v1 | |

### Baja de un usuario que ya firmó

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Desactivar y conservar historia | Único camino coherente con la cadena | ✓ |
| Eliminar y marcar firmas como usuario eliminado | Pérdida retroactiva de autoría | |
| Eliminar sólo si nunca firmó | Dos caminos de baja que sostener | |

### Cierre de sesión

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Sin cierre automático, cambio explícito y visible | Operador activo siempre en pantalla | ✓ |
| Cierre por inactividad configurable | Fricción en el peor momento | |
| Cierre al final del turno configurado | Exige modelar turnos | |

---

## Alcance del esquema

### Cuánto se modela en la Fase 1

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Lo no retrofiteable, completo y ejercitado | Lo demás llega en su fase con su migración | ✓ |
| Esquema completo de v1 | Tablas diseñadas sin entender aún el flujo | |
| Sólo evidencia y captura | Postergaría decisiones no retrofiteables | |

### Captura sin viaje asociado

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Autónoma, se asocia después | El portero fotografía primero y busca el viaje después | ✓ |
| Exige movimiento | Obligaría a inventar un movimiento ficticio | |
| Autónoma pero marcada como pendiente | Cola de trabajo con su pantalla y vencimiento | |

### Identificadores

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Opaco interno + número legible por año | `2026-001842` para referencia humana | ✓ |
| Sólo opaco | Imposible de dictar por teléfono | |
| Sólo secuencial | Colisiona entre instalaciones | |

### Ubicación de la configuración

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Dos capas: arranque en archivo, resto en la base | Auditoría aplicada también a la configuración | ✓ |
| Todo en archivos validados | Cambio de tolerancia dejaría de ser auditable | |
| Todo en la base, incluidas las rutas | Imposible: hay que saber dónde está la base | |

### Modelado del peso teórico ausente

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Nulo por artículo + estado derivado | Estado y datos no pueden contradecirse | ✓ |
| Nulo + estado persistido en el remito | Dos fuentes de verdad | |
| Sólo nulo | La regla quedaría escrita en varios lugares | |

### Idioma del código

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Dominio en español, infraestructura en inglés | Coincide con la investigación de arquitectura | ✓ |
| Todo en inglés | Traducir remito, portería, peso teórico | |
| Todo en español | Choca con bibliotecas y convenciones | |

### Prueba de migración

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Sembrar, migrar y comparar fila por fila | Con los casos feos incluidos | ✓ |
| Ida y vuelta con reversión | Reversión a veces imposible con honestidad | |
| Sólo copia de seguridad previa | No verifica nada | |

### Copia de seguridad antes de migrar

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Sí, además de la prueba | Defensas de capas distintas | ✓ |
| No, alcanza la prueba | Los datos reales tienen formas no anticipadas | |
| Sí, más copia periódica programada | Corresponde a la fase de resiliencia | |

### Dobles como modo demostración

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Mismo doble para pruebas y demo | Mostrar el producto sin hardware; no se pudre | ✓ |
| Dobles sólo para pruebas | Exigiría construir la demostración aparte | |
| Demo como paquete separado | Dos artefactos que firmar y validar | |

---

## Descubrimiento externo

### Profundidad del descubrimiento

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Todo lo que el dominio necesita | Responde si el modelo encaja con la realidad | ✓ |
| Un endpoint de cada uno | Confirma que el teléfono suena, no la conversación | |
| Todo lo del dominio más exploración abierta | Riesgo de que el ERP dicte el modelo | |

### Datos personales en los cassettes

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Anonimizados al grabar, forma intacta | Estructura, tipos, largos, nulos y rarezas preservados | ✓ |
| Crudos, con repositorio privado | El historial de git no se borra | |
| Crudos fuera del repositorio | CI no puede correr contra ellos | |

### Sin acceso a PALJET o balanza

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| La fase se completa; deuda con fecha | Coherente con no bloquear por terceros | ✓ |
| No se cierra sin los dos GET | Una gestión administrativa frenaría el trabajo técnico | |
| Reemplazar por documentación del proveedor | La documentación y la realidad rara vez coinciden | |

### Payload crudo

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Crudo íntegro comprimido, purga configurable | Purga separada de la de evidencia | ✓ |
| Crudo íntegro sin purga | Crece más rápido de lo que se supone | |
| Sólo lo interpretado más resumen | Sin nada contra qué reprocesar | |

### Garantía de solo lectura

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Doble barrera + prueba que falla la construcción | Escribir exige romper dos capas a propósito | ✓ |
| Sólo prueba de arquitectura | Sólo ve los caminos que ejercita | |
| Doble barrera + credenciales de solo lectura exigidas | Depende del cliente, no verificable por prueba | |

### Camino de acceso a PALJET

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Sólo interfaz de programación | Contrato que el proveedor sostiene entre versiones | |
| Directo contra la base con SELECT | Esquema interno cambia sin aviso | |
| Los dos según el dato | Dos mecanismos, dos formas de fallar, dos superficies a auditar | ✓ |

**Notas:** Decisión del usuario. El descubrimiento debe documentar qué dato viene por cada camino; la doble barrera ya cubre ambos.

### Geomov

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Puerto con carga manual como implementación de referencia | Camino principal, no parche | ✓ |
| Además averiguar si existe interfaz | Gestión con tercero que puede no responder | |
| No declarar el puerto todavía | Obligaría a migrar el modelo de viaje | |

---

## Atomicidad ante corte de energía

### Orden de escritura

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Archivo primero con temporal y renombrado atómico; la fila confirma | Sólo puede quedar archivo sin fila, nunca al revés | ✓ |
| Fila pendiente, archivo, confirmación | Dos transacciones; pendientes irresolubles | |
| Todo sin ceremonia, aceptar huérfanos | Contradice el criterio de éxito 3 | |

### Archivos huérfanos al arrancar

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Mover a cuarentena y reportar | Puede ser la foto del camión del corte de luz | ✓ |
| Eliminar directamente | Único lugar donde el sistema destruiría una imagen sola | |
| Dejar donde están y reportar | Se acumulan mezclados con la evidencia buena | |

### Durabilidad de SQLite

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| WAL con sincronización completa | Sobrevive a corte de energía, no sólo al cierre | ✓ |
| WAL con sincronización normal | Puede perderse la última transacción confirmada | |
| Completa sólo para evidencia | Dos configuraciones por conexión que sostener | |

---

## La orden por línea de comandos

### Rol de la herramienta

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Diagnóstico permanente del producto | Soporte por teléfono en planta sin área de sistemas | ✓ |
| Andamio de prueba que se descarta | Habría que construir diagnóstico igual en la Fase 11 | |
| Dos herramientas separadas | Duplicación de lógica | |

### Idioma

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Órdenes en inglés, mensajes en español | Convención de consola + UI-05 | |
| Todo en español, órdenes incluidas | Máxima accesibilidad; rompe la convención universal | ✓ |
| Todo en inglés | Quien lee por teléfono probablemente no lee inglés técnico | |

**Notas:** Decisión del usuario. Convive con la decisión de nombrar la infraestructura en inglés.

### Formato de salida

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Texto para personas por defecto, estructurado bajo bandera | Un comando sirve a los dos públicos | ✓ |
| Sólo texto para personas | Las pruebas parsearían frases en español | |
| Sólo estructurado | Nadie resuelve por teléfono leyendo estructuras | |

---

## Compuerta de integración continua

### Aislamiento del dominio

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Entorno separado con sólo las dependencias del dominio | Prueba real, no simulación | ✓ |
| Bloquear los módulos desde la propia prueba | Un import diferido la sortea | |
| Analizar imports sin ejecutar | No detecta dependencias transitivas | |

### Qué bloquea la fusión

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Rápidas y de arquitectura bloquean; lentas programadas | Compuerta rápida que nadie saltea | ✓ |
| Todo bloquea en cada fusión | Empuja a agrupar cambios grandes | |
| Sólo la de arquitectura bloquea | Solo-lectura y migración pasarían a ser sugerencias | |

### Plataforma de ejecución

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Windows como única plataforma | Rutas, acentos, sistema de archivos y renombrado atómico | ✓ |
| Rápidas en Linux, Windows para lo específico | Clasificación que hay que mantener al día | |
| Windows y Linux en paralelo | Duplica costo por una plataforma de v2 | |

---

## Zona horaria y límite del día

### Zona de agrupación

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Zona de la planta declarada en configuración | No depende del reloj del equipo | |
| Zona local del equipo | Coincide con el reloj que ve el operador | ✓ |
| Día universal para todo | El turno noche aparecería con fecha del día siguiente | |

**Notas:** Decisión del usuario. Costo señalado y aceptado: cambiar la zona de Windows reagrupa el histórico.

### Límite del día

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Medianoche local | Como el ERP y la contabilidad | ✓ |
| Inicio de jornada configurable | Reportes dejarían de coincidir con consultas externas | |
| Agrupar por turno declarado | Exige modelar turnos | |

---

## Nombre y versionado del producto

### Nombre del producto

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Nombre comercial propio a definir por el usuario | Decisión de negocio que condiciona instalador y firma | |
| Nombre provisional y decisión diferida | `porteria` como identificador técnico neutro | ✓ |
| El nombre descriptivo actual | Genérico e irregistrable | |

### Versionado

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Producto y esquema separados con compatibilidad declarada | Se niega a abrir si la base es más nueva | ✓ |
| Una sola versión para todo | Se pierde la señal de cuándo se tocan los datos | |
| Producto más fecha de compilación | Sin defensa ante instalación de versión vieja | |

---

## Ventana de sincronía y gobernanza

### Valor por defecto

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| ±150 ms marcado como no validado | Con medición en campo agendada | ✓ |
| Valor estricto de 50 ms | Casi todo quedaría marcado como estimado | |
| Sin valor hasta la Fase 3 | La Fase 3 lo necesita igual | |

### Quién puede cambiarlo

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Sólo Administración, con registro, y la captura guarda el valor vigente | Impide reclasificar evidencia vieja retroactivamente | ✓ |
| Cualquiera con acceso a configuración, con registro | Junto a ajustes triviales | |
| No configurable en v1 | Sin salida para el cliente con peor hardware | |

---

## Videos de referencia y datos de prueba

### Origen del material

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Filmados en la portería real, con acuerdo y uso restringido | Luz, contraluz, suciedad y maniobra reales | ✓ |
| Genéricos de fuentes libres | No se parecen a la portería del cliente | |
| Sintéticos generados a propósito | Prueban sólo lo que se anticipó | |

### Dónde viven

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Recortes cortos versionados, originales aparte | CI reproducible sin multiplicar material sensible | ✓ |
| Todo en almacenamiento de archivos grandes | Gigabytes en cada copia, para siempre | |
| Fuera del repositorio con descarga bajo demanda | CI dependiente de servicio externo con credenciales | |

---

## Inventario de licencias

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Desde el día uno, generado y verificado en cada fusión | Falla ante licencia contagiosa o no identificable | ✓ |
| Desde el día uno pero informativo | Un informe que nadie mira no existe | |
| Se arma al llegar el instalador | Reemplazar una pieza con once fases encima | |

---

## Estrategia de pruebas

### Cuándo se escriben

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Antes para lo que la fase promete demostrar; después para el resto | Los criterios de éxito se escriben primero, fallando | ✓ |
| Siempre antes sin excepciones | En adaptadores verifica lo imaginado, no lo real | |
| Después, cubriendo lo entregado | Confirmarían lo que el código hace, no lo que debería | |

### Cobertura

| Opción | Descripción | Elegida |
|--------|-------------|---------|
| Medida y visible, nunca como compuerta | Lo que bloquea es que pasen las pruebas de los criterios | ✓ |
| Mínima exigida sobre el dominio | Satisfacible sin verificar nada real | |
| Mínima global | Desvía esfuerzo a adaptadores caros de probar | |

---

## Claude's Discretion

El usuario no delegó ninguna decisión con un "vos decidís" explícito. Todas las preguntas recibieron una elección concreta. Lo que queda a criterio de investigación y planificación está enumerado en la sección correspondiente de `01-CONTEXT.md` y es materia técnica, no de negocio.

## Decisiones donde el usuario se apartó de la recomendación

Cuatro, todas deliberadas y documentadas como suyas en CONTEXT.md:

1. **Usuarios con contraseña** en lugar de perfiles sin credencial — alcance nuevo, no derivado de ningún requerimiento v1.
2. **PALJET por los dos caminos** (interfaz de programación y consulta directa) en lugar de sólo la interfaz.
3. **Zona local del equipo** en lugar de zona de planta declarada — con el costo de reagrupación del histórico señalado y aceptado.
4. **Línea de comandos íntegramente en español**, órdenes incluidas, en lugar de órdenes en inglés con mensajes en español.

## Deferred Ideas

Lista completa en la sección `<deferred>` de `01-CONTEXT.md`. Resumen:

**Fases posteriores del roadmap:** pantalla de inicio de sesión y cambio de operador · gestión de usuarios desde la interfaz · herramienta operable de purga con lápida · política concreta de retención · medición en campo de la ventana de sincronía · nombre comercial del producto.

**Capacidades nuevas fuera de v1:** réplica de evidencia a NAS · inicio de sesión único contra dominio corporativo · política corporativa de contraseñas · muestreo periódico de métricas a la base · copia de seguridad periódica programada · modelado de turnos y horarios (descartado dos veces) · gestión formal con Geomov para averiguar si expone alguna interfaz.
