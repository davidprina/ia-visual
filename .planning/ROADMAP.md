# Roadmap: Sistema de Control de Portería con Visión Artificial

## Overview

El proyecto avanza en doce rebanadas verticales. Cada una entrega una capacidad completa de punta a punta que se puede probar de verdad, no una capa técnica aislada. La Fase 1 fija de una vez las decisiones que no se pueden retrofitear —huella SHA-256 en ingesta, viaje con varios remitos, peso teórico ausente, contrato de frescura del frame, reloj único del proceso, escritura atómica— y además ejecuta el descubrimiento de los contratos de PALJET y de la balanza, aunque esas integraciones se construyan recién en la Fase 10: el riesgo no es integrar tarde, es enterarse tarde. Las Fases 2 y 3 construyen el subsistema de visión hasta el Core Value —un botón, todas las cámaras, el mismo instante, evidencia completa o explícitamente parcial— con compuertas de salida medibles y no opinables. Las Fases 4 y 5 suman inteligencia sobre ese video: detección con proveedor de ejecución verificado y reconocimiento de patentes como sugerencia confirmable. Las Fases 6 a 9 arman el flujo operativo de portería completo contra proveedores simulados deliberadamente feos, de modo que la Fase 10 sea sustituir un adaptador y no descubrir el dominio. La Fase 11 convierte el software en producto instalable y firmado. La Fase 12, última de v1, agrega el motor de visión clásica: requisito propio del usuario, sin valor de mercado relevado, y por eso el último en llegar aunque su abstracción se diseñe desde la Fase 4.

**Modo:** MVP con rebanadas verticales
**Granularidad:** fina (12 fases, 5 a 10 planes por fase, tareas de 2 a 4 horas)
**Cobertura:** 79 de 79 requerimientos v1 mapeados

## Phases

**Numeración de fases:**
- Fases enteras (1, 2, 3): trabajo planificado del hito
- Fases decimales (2.1, 2.2): inserciones urgentes (marcadas con INSERTED)

Las fases decimales aparecen entre sus enteros vecinos en orden numérico.

- [ ] **Phase 1: Núcleo, evidencia trazable y contratos externos congelados** - Una captura desde archivo de video queda persistida con huella verificable, en transacción atómica, sobre un esquema que ya admite lo incómodo; y hay un GET real contra PALJET y contra la balanza
- [ ] **Phase 2: Ingesta multi-fuente robusta y visor que no miente** - Cámaras IP, webcam y archivos en vivo con estado honesto por fuente, reconexión sola y ocho horas de cortes cíclicos sin fugas
- [ ] **Phase 3: Captura sincronizada de un botón (Core Value)** - Una orden, todas las cámaras, el mismo instante, el desvío medido y persistido, y la captura incompleta marcada como tal
- [ ] **Phase 4: Detección por IA con proveedor verificado y geometría probada** - Vehículos y personas detectados sobre ONNX Runtime, con el proveedor real expuesto en pantalla y las coordenadas verificadas sub-pixel
- [ ] **Phase 5: Reconocimiento de patentes argentinas como sugerencia confirmable** - Lectura por ráfaga con votación, validada contra las gramáticas locales, propuesta al portero y nunca impuesta
- [ ] **Phase 6: Flujo de egreso: viaje precargado, captura vinculada y liberación** - Logística precarga, el portero elige de una lista, captura y libera, con la evidencia atada al viaje correcto
- [ ] **Phase 7: Auditoría de peso, tolerancias y excepciones registradas** - Veredicto automático contra el peso teórico, bloqueo con ruta de salida, y el estado "peso teórico incompleto" como tercer camino válido
- [ ] **Phase 8: Ingreso de proveedores, documentación y SLA de espera** - Alta de camión de proveedor con su remito digitalizado en segundos, cronómetro que sobrevive al corte de luz y panel semáforo
- [ ] **Phase 9: Consulta, evidencia exportable y vista de solo lectura para Compras** - Encontrar cualquier movimiento, exportarlo como paquete verificable fuera del sistema, y que Compras lo vea sin poder tocar nada
- [ ] **Phase 10: Integraciones reales: balanza, PALJET y recorrido** - Los dobles se sustituyen por los adaptadores reales sin tocar el dominio, y la portería sigue operando si un tercero no responde
- [ ] **Phase 11: Empaquetado, instalador firmado y resiliencia en planta** - Instalación con doble clic en una PC limpia sin que el antivirus la bloquee, y recuperación sola tras un corte de energía
- [ ] **Phase 12: Motor de visión clásica seleccionable en caliente** - Segunda implementación del puerto de motor, intercambiable sin reiniciar, que declara con honestidad lo que no puede hacer

## Phase Details

### Phase 1: Núcleo, evidencia trazable y contratos externos congelados
**Goal**: Desde una orden por línea de comandos sobre un archivo de video, el sistema produce evidencia persistida con huella SHA-256 verificable, en una única transacción, sobre un esquema que ya modela viaje con varios remitos y peso teórico ausente; y los contratos de PALJET y de la balanza quedan congelados con dobles de prueba después de un GET real contra cada uno.
**Mode:** mvp
**Depends on**: Nothing (primera fase)
**Requirements**: NUC-01, NUC-04, NUC-05, NUC-06, CAP-03, CAP-04, EVI-05, EVI-06, VIA-05, INT-04, INT-05, DIS-05, DIS-06
**Success Criteria** (what must be TRUE):
  1. La prueba de arquitectura corre en integración continua e importa el paquete `dominio/` en un entorno donde opencv, onnxruntime y PySide6 no están instalados; si alguien introduce una de esas dependencias, la prueba falla y no se puede fusionar.
  2. Una orden de captura sobre un archivo de video deja la imagen en el almacén direccionado por contenido y su fila de metadatos con la huella SHA-256; recalcular la huella del archivo reproduce el valor persistido, y alterar un solo byte del archivo hace que la verificación reporte la evidencia como comprometida.
  3. Interrumpir el proceso en mitad de la escritura no deja filas apuntando a archivos inexistentes ni archivos sin fila: o está todo, o no está nada, verificado con una prueba que corta la transacción a propósito.
  4. Existe una respuesta real obtenida por GET de PALJET y otra de la balanza, guardadas como cassette junto a su payload crudo, y los dobles de prueba de todos los puertos de salida devuelven datos deliberadamente feos —viaje con tres remitos, remito repartido en dos viajes, peso teórico nulo, patente con guiones y espacios— con los que el sistema completo corre sin hardware ni sistemas externos.
  5. Con un archivo de video reproducido en tiempo real y un consumidor deliberadamente lento, la antigüedad del frame entregado por la fuente se mantiene acotada y no crece durante diez minutos, y la cantidad de frames descartados queda registrada como métrica consultable.
  6. La aplicación opera con la base y el almacén de evidencia en una ruta con espacios y acentos, y una migración de Alembic sobre una base con datos preexistentes los preserva íntegros.
**Pitfalls que ataca**: 1 (contrato de frescura del frame), 2 (modelo de reloj monotónico/UTC y desvío), 14 (escritura atómica y hash), 16 (descubrimiento de contratos, no implementación), 18 (persistencia transaccional con WAL)
**Decisiones no retrofiteables que se fijan acá**: huella SHA-256 en ingesta · relación Viaje↔Remito muchos-a-muchos · peso teórico admitiendo nulo · contrato de frescura del frame (slot de tamaño 1, descarte del más viejo) · reloj único del proceso y desvío por cámara · payload crudo persistido
**Plans**: 10 planes en 5 olas · Walking Skeleton en `SKELETON.md` · modo MVP (rebanadas verticales)

**Ola 1** *(sin dependencias — habilita todo lo demás)*
- `01-01` — Proyecto uv, árbol de paquetes y las cuatro compuertas: import-linter, sonda de aislamiento del dominio, invariantes de código y ruta con espacios y acentos

**Ola 2** *(bloqueada por la ola 1)*
- `01-02` — Vocabulario común del dominio, reloj del proceso y manifiesto con huella
- `01-03` — Slot de capacidad 1 con descarte del más viejo, métricas por fuente y el puerto `FuenteDeVideo`

**Ola 3** *(bloqueada por la ola 2)*
- `01-04` — Escritura atómica con huella SHA-256 y verificación, en el idioma de Windows
- `01-05` — Motor SQLite con PRAGMAs verificados, esquema no retrofiteable y migraciones Alembic
- `01-06` — Bitácora técnica estructurada con rotación, nivel configurable y configuración en base

**Ola 4** *(bloqueada por la ola 3)*
- `01-07` — Unidad de trabajo, repositorios, outbox y el composition root que cablea todo
- `01-08` — Puertos de salida dictados por el dominio y los dos juegos de datos deliberadamente feos

**Ola 5** *(bloqueada por la ola 4)*
- `01-09` — Usuario, cuatro roles fijos, matriz de permisos aislada y autoría en la transacción
- `01-10` — Transporte inyectado, triple barrera de solo lectura, grabador con anonimizador y cassettes ⚠️ `autonomous: false` (requiere credenciales de PALJET y de la balanza)

**Restricciones transversales** *(citadas por 2 o más planes)*
- Toda la suite corre bajo una ruta con espacios y acentos; prohibido `pytest.skip` de sesión, y `pytest_sessionfinish` falla si se recolectaron 0 pruebas
- Ningún criterio de aceptación depende de `grep`: las invariantes de código son aserciones de pytest, porque Windows es la única plataforma de compuerta (D-54)
- Acceso de **solo lectura** a sistemas externos (GET y SELECT); el contrato `sin_conexion_cruda` no admite excepciones
- Reloj único del proceso: `time.monotonic_ns()` para deltas y antigüedad, `datetime.now(timezone.utc)` para el sello persistido

### Phase 2: Ingesta multi-fuente robusta y visor que no miente
**Goal**: El operador abre la aplicación y ve en vivo las cámaras IP, la webcam USB y los archivos de video en el layout que elija, y el estado que muestra cada panel es cierto: una fuente caída se declara caída en menos de quince segundos, se reconecta sola y nunca arrastra a las demás.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: NUC-02, NUC-03, CAP-01, CAP-02, CAP-05, CAP-06, CAP-07, CAP-08, UI-02, UI-05
**Success Criteria** (what must be TRUE):
  1. Con la aplicación corriendo, desenchufar el cable de red de una cámara IP hace que su panel pase a estado caída en menos de quince segundos; volver a enchufarlo la restablece sin intervención, y ninguna otra fuente se interrumpe durante el episodio.
  2. Bloquear el tráfico de una cámara por firewall —sin cortar la conexión TCP— produce el mismo cambio de estado: el detector de frames idénticos declara la fuente congelada aunque los datos sigan llegando y aunque la biblioteca siga reportando que todo está bien.
  3. Un cronómetro digital filmado durante diez minutos muestra que la diferencia entre el reloj filmado y el reloj del sistema se mantiene constante y no crece a lo largo de la sesión, con las tres clases de fuente activas.
  4. Una corrida de ocho horas con cortes de red cíclicos termina con la cantidad de hilos, los descriptores abiertos y la memoria residente del proceso en los mismos valores que al empezar, dentro de un diez por ciento.
  5. El usuario da de alta una cámara IP desde la interfaz sin editar ningún archivo, prueba la conexión, ve la vista previa, y si falla lee un mensaje que dice qué revisar y cuándo se reintenta; además alterna entre los layouts de una cámara, 2x2, 3x3 y 4x4 sin reiniciar la aplicación.
**Pitfalls que ataca**: 1 (latencia acumulada, verificada con cronómetro filmado), 3 (stream congelado sin error), 4 (fugas de hilos y memoria en reconexión), 13 (frames retenidos), 18 (reanudación tratada como reconexión total)
**Plans**: TBD
**UI hint**: yes

### Phase 3: Captura sincronizada de un botón (Core Value)
**Goal**: Cuando el portero presiona un único botón, el sistema obtiene imágenes de todas las cámaras activas referidas al mismo instante objetivo, mide y persiste el desvío real de cada una contra el reloj del proceso, y si falta alguna lo dice en pantalla y en el registro: nunca aparenta estar completa.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: EVI-01, EVI-02, EVI-03, EVI-04, EVI-10, UI-01, UI-03, UI-07
**Success Criteria** (what must be TRUE):
  1. Con un cronómetro digital filmado simultáneamente por todas las cámaras, los frames guardados por una misma orden de captura muestran el mismo valor dentro de la ventana de aceptación declarada, y el desvío observado de cada cámara queda persistido junto a su ítem de evidencia.
  2. Con una cámara apagada, la captura se completa igual: la evidencia queda marcada como parcial con el motivo por cada cámara ausente, y ninguna pantalla, listado ni exportación la presenta como completa.
  3. Desde el clic hasta el primer feedback visual pasan menos de doscientos milisegundos, la captura completa termina en menos de dos segundos, la ventana nunca entra en estado "no responde" con tres cámaras activas, y un segundo clic durante la captura no produce un segundo registro.
  4. Al caer el espacio libre del disco por debajo del umbral configurado el sistema avisa antes de que falle la escritura, y superado el umbral crítico bloquea nuevas capturas con un mensaje explícito en lugar de fallar en silencio, verificado llenando la partición a propósito.
  5. La aplicación se opera completa con el dedo sobre pantalla táctil, sin dobles clics ni gestos finos, y mantiene proporciones de video y controles legibles al arrastrar la ventana entre un monitor al cien por ciento y otro al ciento cincuenta por ciento de escala.
**Pitfalls que ataca**: 2 (sincronía real medida y persistida, no nominal), 3 (regla dura: fuente no viva ⇒ evidencia marcada incompleta), 12 (UI que no se congela, botón idempotente), 13 (memoria por frames y miniaturas), 14 (disco lleno)
**Plans**: TBD
**UI hint**: yes

### Phase 4: Detección por IA con proveedor verificado y geometría probada
**Goal**: El sistema detecta vehículos y personas sobre el video con un modelo de licencia permisiva ejecutado en ONNX Runtime, dice en la interfaz qué proveedor de ejecución está usando realmente y no cuál pidió, y las cajas que dibuja se corresponden con el frame original con precisión sub-pixel.
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: VIS-01, VIS-02, VIS-03, VIS-04, VIS-05, VIS-06
**Success Criteria** (what must be TRUE):
  1. La interfaz muestra el proveedor de ejecución obtenido de `session.get_providers()` comparado contra el solicitado; cuando difieren lo informa con el motivo en lenguaje comprensible, y en una máquina sin GPU el panel dice CPU en lugar de sostener la promesa equivocada.
  2. La prueba automática de ida y vuelta de letterbox y unletterbox devuelve una caja conocida a su posición original con tolerancia sub-pixel, y las fixtures de regresión visual en integración continua detectan cualquier cambio de preprocesamiento que rompa la geometría.
  3. Las detecciones sobre el conjunto de imágenes de referencia coinciden con una implementación de referencia con IoU mayor a 0,9 y confianzas equivalentes, lo que descarta errores silenciosos de orden de canales, normalización y layout.
  4. El usuario ajusta el umbral de confianza y elige qué clases se superponen sobre el video, y el overlay responde sin reiniciar la aplicación; una corrida de ocho horas con inferencias periódicas deja la memoria residente en meseta porque las sesiones se crean una sola vez y no se destruyen.
  5. El trámite de compra del certificado de firma de código está iniciado con comprobante, y un instalador de humo generado con PyInstaller en modo `--onedir` arranca en una máquina virtual Windows recién instalada, sin Python y sin Visual C++ Redistributable.
**Pitfalls que ataca**: 5 (fallback silencioso a CPU), 6 (fugas de sesiones ONNX Runtime), 7 (letterbox y desescalado), 8 (BGR/RGB, normalización y layout), 9 (NMS), 12 (warm-up e hilos de inferencia acotados), 15 (certificado y prueba en VM limpia arrancados temprano)
**Plans**: TBD
**UI hint**: yes

### Phase 5: Reconocimiento de patentes argentinas como sugerencia confirmable
**Goal**: El sistema lee la patente del camión detenido aprovechando que está quieto sobre la balanza, valida la lectura contra los formatos argentinos, la propone al portero junto al recorte de la placa para que confirme o corrija con un toque, y registra cada corrección para poder medir la precisión real en campo.
**Mode:** mvp
**Depends on**: Phase 4
**Requirements**: LPR-01, LPR-02, LPR-03, LPR-04, LPR-05, LPR-06, LPR-07
**Success Criteria** (what must be TRUE):
  1. Sobre un conjunto de evaluación propio de al menos doscientas capturas reales que incluye noche, contraluz, suciedad y placas deterioradas, la ráfaga con votación por consenso supera de forma medida a la lectura de un solo frame, y el objetivo de acierto está escrito, medido y publicado en el propio panel del sistema.
  2. Ninguna patente sintácticamente imposible llega a la base: toda lectura se valida contra las tres gramáticas argentinas —Mercosur de auto, formato anterior y moto Mercosur— con desambiguación posicional de los pares ambiguos, y lo que no valida se marca de baja confianza y exige confirmación manual.
  3. La patente se presenta junto al recorte de la placa como sugerencia con su nivel de confianza y hasta tres alternativas ordenadas por distancia de edición contra el padrón de viajes del día; un solo toque confirma, y toda corrección manual queda registrada con la lectura original, la corregida, el operador y el instante.
  4. Existe un documento de especificación de la instalación física de la cámara de patentes con los números exigibles —ancho en píxeles sobre la placa en la posición real de detención, ángulo horizontal, velocidad de obturador por nivel de luz e iluminación infrarroja nocturna— verificado con una medición en campo o declarado explícitamente como insumo del pliego de compra mientras el hardware no exista.
  5. El detector de placa que se usa en producción tiene licencia permisiva verificada y sin pesos derivados de modelos con licencia contagiosa; si todavía se usa el de desarrollo, la sustitución está agendada como bloqueante de la primera venta con su plan escrito y su fecha.
**Pitfalls que ataca**: 6 (revalidar perfil de memoria al sumar dos modelos más), 7 y 9 (la geometría de la Fase 4 es crítica para el recorte de placa), 10 (expectativa de precisión desconectada de la realidad de campo), 11 (confusión de caracteres sin validación de formato argentino)
**Plans**: TBD
**UI hint**: yes

### Phase 6: Flujo de egreso: viaje precargado, captura vinculada y liberación
**Goal**: Logística precarga un viaje vinculando chofer, camión y varios remitos; el portero lo encuentra en una lista filtrable, presiona capturar, y la evidencia junto con la lectura de peso quedan atadas a ese viaje, que se libera con hora y estado final registrados.
**Mode:** mvp
**Depends on**: Phase 5
**Requirements**: VIA-01, VIA-02, VIA-03, VIA-04, UI-06
**Success Criteria** (what must be TRUE):
  1. Un viaje precargado con tres remitos, uno de ellos compartido con otro viaje, se guarda y se recupera correctamente, lo que demuestra que la relación muchos a muchos fijada en la Fase 1 sostiene el caso real.
  2. El portero encuentra el viaje del camión que tiene enfrente filtrando por patente, chofer o transportista, y la sugerencia de patente de la Fase 5 lo deja preseleccionado sin decidir por él.
  3. La captura ejecutada desde la pantalla de egreso queda vinculada al viaje seleccionado junto con la lectura de peso obtenida del proveedor simulado, todo bajo el mismo identificador de captura y en la misma transacción.
  4. El flujo completo de un camión —encontrar el viaje, capturar, ver el resultado y liberar— se resuelve en menos de treinta segundos de interacción del operador, medido con cronómetro sobre el recorrido real de la pantalla.
  5. Al liberar, el viaje registra hora y estado final, y el registro no admite edición posterior: cualquier corrección entra como un evento nuevo que apunta al original.
**Pitfalls que ataca**: 16 (el flujo se construye contra dobles feos, no contra datos lindos), 17 (el camino correcto tiene que ser el más rápido, o el operador lo elude)
**Plans**: TBD
**UI hint**: yes

### Phase 7: Auditoría de peso, tolerancias y excepciones registradas
**Goal**: El sistema contrasta el peso real contra el peso teórico de los remitos, libera o bloquea según dos umbrales configurables desde la interfaz, contempla el peso teórico incompleto como un tercer camino de trabajo válido apoyado en la evidencia fotográfica, y registra toda excepción del operador en lugar de impedirla.
**Mode:** mvp
**Depends on**: Phase 6
**Requirements**: AUD-01, AUD-02, AUD-03, AUD-04, AUD-05, AUD-06, UI-04
**Success Criteria** (what must be TRUE):
  1. Una diferencia dentro de la tolerancia de aceptación libera el viaje sin fricción; una diferencia intermedia advierte y permite liberar dejando motivo; una diferencia mayor al umbral de bloqueo impide la salida con alerta visible y una ruta de resolución explícita en pantalla, no un callejón sin salida.
  2. Los dos umbrales de tolerancia se configuran desde la propia interfaz, en kilogramos y en porcentaje aplicando el más restrictivo, junto con cámaras, rutas de almacenamiento y umbrales de confianza; ninguna de esas configuraciones requiere editar un archivo.
  3. Un remito con al menos un artículo sin peso maestro produce el estado "peso teórico incompleto" como tercer veredicto y no como error, no compara contra un número inventado, y habilita una auditoría apoyada en la evidencia fotográfica que queda firmada por el usuario que la realizó.
  4. El reporte de artículos sin peso maestro lista exactamente los artículos afectados del período en un formato que el cliente puede llevar a su ERP para corregirlo.
  5. Toda excepción u omisión forzada por el operador —capturar sin una cámara, liberar en zona de alerta, corregir una patente— queda registrada con motivo y autor, sin ser impedida, y aparece agregada en un panel de calidad de registro que muestra el porcentaje de capturas completas y de liberaciones con excepción por turno.
**Pitfalls que ataca**: 17 (lo que se prohíbe se elude, lo que se registra se corrige), 16 (peso teórico nulo tratado como caso normal desde el modelo)
**Plans**: TBD
**UI hint**: yes

### Phase 8: Ingreso de proveedores, documentación y SLA de espera
**Goal**: El portero da de alta el ingreso de un camión de proveedor capturando su remito con la webcam en segundos y asociándolo a una orden de compra, el cronómetro de espera arranca solo y sobrevive a un corte de energía, y el panel semáforo muestra quién lleva esperando de más.
**Mode:** mvp
**Depends on**: Phase 7
**Requirements**: ING-01, ING-02, ING-03, ING-04, SLA-01, SLA-02, SLA-03
**Success Criteria** (what must be TRUE):
  1. Capturar el remito de un proveedor con la webcam produce una imagen en la que se lee el número de remito a simple vista, en menos de diez segundos de operación, con recorte automático de la hoja y opción de volver a tomarla sin salir de la pantalla.
  2. El ingreso queda asociado a una orden de compra, y las capturas de carga del ingreso y del egreso del mismo camión se recuperan juntas en una sola pantalla para comparar qué trajo contra qué se lleva.
  3. El cronómetro de espera arranca en el registro de ingreso, se deriva del instante de arribo persistido y no de un contador en memoria, y sobrevive tanto al cierre y reapertura de la aplicación como a un corte de energía del equipo.
  4. El panel semáforo ordena los camiones presentes por tiempo de espera descendente con umbrales configurables, y al superarse el umbral el sistema notifica una sola vez por camión y por umbral —no en cada evaluación— dejando en la bitácora el instante exacto del vencimiento.
**Pitfalls que ataca**: 17 (la digitalización no puede frenar la fila), 18 (el cronómetro y el estado abierto sobreviven al corte de energía)
**Plans**: TBD
**UI hint**: yes

### Phase 9: Consulta, evidencia exportable y vista de solo lectura para Compras
**Goal**: Quien tenga permiso encuentra la evidencia de cualquier movimiento por fecha, patente, tipo o estado de auditoría, la exporta como un paquete cuya integridad se verifica fuera del sistema, y Compras la consulta desde su propio puesto de la red local sin poder editar, configurar ni borrar nada.
**Mode:** mvp
**Depends on**: Phase 8
**Requirements**: EVI-07, EVI-08, EVI-09, CON-01, CON-02, CON-03
**Success Criteria** (what must be TRUE):
  1. Buscar por fecha, patente, tipo de movimiento y estado de auditoría devuelve el movimiento correcto con sus miniaturas en menos de dos segundos sobre una base sembrada con cincuenta mil registros, con paginación e índices desde el primer día.
  2. El paquete exportado contiene las imágenes originales sin modificar y un manifiesto con la huella de cada una; un tercero verifica la integridad del paquete fuera del sistema, y alterar un solo archivo hace fallar esa verificación señalando cuál.
  3. Cada acceso y cada exportación de evidencia queda en una bitácora que solo agrega y nunca modifica, con quién, cuándo y qué, y esa bitácora se exporta pero no se edita.
  4. Desde otro equipo de la red local, Compras abre la vista y ve las capturas y los remitos del camión que está en portería en ese momento; una prueba automática demuestra que ningún camino de esa vista permite editar, configurar ni eliminar.
  5. Los movimientos de un período se exportan a un formato tabular abierto que se abre sin pérdida ni corrupción de acentos en una planilla de cálculo.
**Pitfalls que ataca**: 14 (consulta con índices y miniaturas precalculadas), 17 (el panel de calidad se vuelve auditable por Administración)
**Plans**: TBD
**UI hint**: yes

### Phase 10: Integraciones reales: balanza, PALJET y recorrido
**Goal**: Los proveedores simulados se sustituyen por los adaptadores reales sin tocar una línea del dominio: el peso viene de la balanza, los datos maestros de PALJET y el recorrido se carga a mano como camino principal; y si un tercero no responde, la portería sigue operando y capturando evidencia.
**Mode:** mvp
**Depends on**: Phase 9
**Requirements**: INT-01, INT-02, INT-03, INT-06
**Success Criteria** (what must be TRUE):
  1. La misma suite de contrato que corre contra los dobles corre sin modificaciones contra los adaptadores reales de balanza y de PALJET, y pasa en ambos: la sustitución es de implementación, no de dominio.
  2. El peso que se audita es una lectura estable de la balanza, con su propio instante registrado y su desvío respecto de las fotos persistido; una lectura tomada mientras el camión se acomoda no se acepta como peso de auditoría y el sistema lo dice.
  3. Desconectar la balanza o el ERP en mitad de la jornada no impide capturar evidencia: la captura se completa, el dato faltante entra en una cola de conciliación visible, y la interfaz indica qué falta y desde cuándo, incluyendo la antigüedad del último dato maestro sincronizado.
  4. Los kilómetros recorridos y los horarios de salida y regreso se cargan a mano en menos de quince segundos como camino principal, sin ningún campo de la interfaz esperando una API que puede no existir nunca.
  5. La prueba automática de solo lectura demuestra que ningún adaptador externo emitió un verbo distinto de GET, HEAD u OPTIONS, ni ninguna sentencia que no empiece por SELECT o WITH, y falla la construcción si alguien introduce uno.
**Pitfalls que ataca**: 16 (implementación tardía sobre contratos descubiertos temprano; el modelo de datos ya absorbió lo incómodo en la Fase 1)
**Plans**: TBD

### Phase 11: Empaquetado, instalador firmado y resiliencia en planta
**Goal**: Un cliente instala el producto en una PC Windows limpia con doble clic, sin que el antivirus ni SmartScreen lo bloqueen, y la portería vuelve sola y sana después de un corte de energía sin que nadie tenga que saber reiniciar nada.
**Mode:** mvp
**Depends on**: Phase 10
**Requirements**: DIS-01, DIS-02, DIS-03, DIS-04
**Success Criteria** (what must be TRUE):
  1. El instalador firmado con certificado válido se instala en una máquina virtual Windows recién instalada, sin Python, sin Visual C++ Redistributable y con Defender y SmartScreen activos en modo estándar, sin advertencias de reputación ni detección en VirusTotal.
  2. La instalación funciona en una ruta con espacios y acentos, con un usuario de Windows cuyo nombre lleva ñ o tilde, y permite elegir el disco de almacenamiento de evidencia durante la instalación sin editar archivos después.
  3. Tras cortar la alimentación del equipo con una captura en curso, al volver la luz la aplicación arranca sola, muestra una pantalla de estado del sistema en verde y rojo sin jerga técnica, recupera las transacciones abiertas y todas las fuentes —incluida la webcam USB— reconectan sin intervención; lo mismo tras suspender el equipo diez minutos.
  4. El instalador incluye el texto de las licencias de terceros, la aplicación las muestra desde su propio menú, y las bibliotecas del toolkit de interfaz quedan visibles y sustituibles por el usuario en la carpeta de instalación, cumpliendo la LGPL de forma verificable.
**Pitfalls que ataca**: 5 (política de distribución CPU por defecto, GPU como paquete opcional), 14 (ruta de evidencia configurable en el instalador), 15 (antivirus, firma, rutas hostiles, VM limpia), 18 (arranque automático, plan de energía, requisitos de despliegue documentados)
**Plans**: TBD

### Phase 12: Motor de visión clásica seleccionable en caliente
**Goal**: El usuario alterna entre el motor de inteligencia artificial y un motor de visión clásica basado en OpenCV sin reiniciar la aplicación ni reconfigurar las fuentes, y la interfaz le dice con honestidad qué puede y qué no puede cada motor en lugar de degradar en silencio.
**Mode:** mvp
**Depends on**: Phase 11
**Requirements**: VIS-07, VIS-08
**Success Criteria** (what must be TRUE):
  1. Con el sistema corriendo y las fuentes activas, cambiar de motor surte efecto sin reiniciar la aplicación y sin volver a configurar ninguna fuente; las fuentes no se reconectan ni pierden frames por el cambio.
  2. El motor clásico emite detecciones de movimiento sin confianza numérica —no inventa un valor falso— y la interfaz avisa antes de que el usuario active una función que ese motor no puede sostener, consultando las capacidades declaradas en lugar de fallar después.
  3. La misma suite de contrato del puerto de motor corre contra las dos implementaciones y pasa en ambas, y no existe en la aplicación ningún condicional por tipo de motor: la política se construye una sola vez a partir de las capacidades declaradas.
  4. Alternar de motor cien veces seguidas deja la memoria residente en meseta, porque ninguna sesión de inferencia se destruye ni se recrea: el cambio enruta entre motores ya instanciados.
  5. El instalador firmado se regenera con el motor clásico incluido y se revalida en la máquina virtual Windows limpia, cerrando v1 con un artefacto entregable completo.
**Pitfalls que ataca**: 6 (fugas por recrear sesiones al alternar motores), 10 del catálogo de anti-patrones de arquitectura (condicionales por tipo de motor dispersos)
**Plans**: TBD

## Cobertura de requerimientos

**79 de 79 requerimientos v1 mapeados. Ningún huérfano, ninguno duplicado.**

| Categoría | Total | Fases |
|-----------|-------|-------|
| NUC — Núcleo y arquitectura | 6 | 1 (×4), 2 (×2) |
| CAP — Captura de video | 8 | 1 (×2), 2 (×6) |
| EVI — Captura sincronizada y evidencia | 10 | 1 (×2), 3 (×5), 9 (×3) |
| VIS — Detección por visión artificial | 8 | 4 (×6), 12 (×2) |
| LPR — Reconocimiento de patentes | 7 | 5 (×7) |
| UI — Interfaz del operador | 7 | 2 (×2), 3 (×3), 6 (×1), 7 (×1) |
| VIA — Flujo de egreso | 5 | 1 (×1), 6 (×4) |
| ING — Flujo de ingreso de proveedores | 4 | 8 (×4) |
| AUD — Auditoría de pesos | 6 | 7 (×6) |
| SLA — Tiempos de espera | 3 | 8 (×3) |
| CON — Consulta y visibilidad | 3 | 9 (×3) |
| INT — Integraciones externas | 6 | 1 (×2), 10 (×4) |
| DIS — Distribución y operación | 6 | 1 (×2), 11 (×4) |

El detalle requerimiento por requerimiento está en la sección Traceability de `.planning/REQUIREMENTS.md`.

## Decisiones no retrofiteables y dónde se fijan

| Decisión | Fase que la fija | Por qué no se puede posponer |
|----------|------------------|------------------------------|
| Huella SHA-256 calculada en el momento de ingesta | 1 | Sin ella desde la primera captura, todo el histórico previo pierde valor probatorio |
| Relación Viaje↔Remito muchos a muchos | 1 | Cambiarla después obliga a migrar un esquema con datos productivos |
| Peso teórico admitiendo valor nulo o incompleto | 1 | Es un estado de negocio de primera clase, no un caso de error |
| Contrato de frescura del frame (slot de tamaño 1, descarte del más viejo) | 1 | Retro-imponerlo obliga a tocar UI, dominio y captura a la vez |
| Reloj único del proceso y desvío por cámara persistido | 1 | Sin el número, "sincronizado" es una afirmación sin prueba y la evidencia es impugnable |
| Prueba de arquitectura: `dominio/` importable sin opencv, onnxruntime ni PySide6 | 1 | Es el guardián automático que hace real la arquitectura hexagonal en lugar de decorativa |
| Escritura atómica de evidencia y transacción única estado + evidencia + outbox | 1 | Un corte de energía deja filas huérfanas que después no se distinguen de un borrado |
| Descubrimiento de contratos de PALJET y balanza con un GET real | 1 | El riesgo no es integrar tarde: es enterarse tarde de que el modelo de datos no encaja |
| Payload crudo de toda consulta externa persistido | 1 | Permite reprocesar una interpretación errónea sin volver a pedir nada a un tercero |
| Puerto único de motor de detección con capacidades declaradas | 4 | La segunda implementación llega en la Fase 12; si el contrato se moldea a un solo motor, la fuga es inevitable |
| Inicio del trámite de compra del certificado de firma de código | 4 | Es un plazo administrativo bloqueante, no una tarea técnica de última hora |

## Restricciones que este roadmap respeta

- **Ultralytics YOLO está prohibido** en cualquier forma, incluidas pruebas: licencia AGPL-3.0 sobre un producto comercial. El detector es RF-DETR-Nano/Small (Apache-2.0) sobre ONNX Runtime.
- **Solo lectura sobre sistemas externos.** La regla se vuelve una prueba automatizada en la Fase 1 y una compuerta de la Fase 10, no una promesa.
- **Windows es la plataforma primaria.** Linux y macOS quedan en v2 y no aparecen en ninguna fase.
- **Las integraciones se construyen al final** (Fase 10) pero su descubrimiento ocurre en la Fase 1.
- **El motor de visión clásica es la última fase de v1** (Fase 12): requisito propio del usuario, sin valor de mercado relevado.
- **La vista para Compras es de solo lectura en la red local** (Fase 9), no una aplicación web con edición ni configuración.

## Progress

**Orden de ejecución:**
Las fases se ejecutan en orden numérico: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Núcleo, evidencia trazable y contratos externos | 3/10 | In Progress|  |
| 2. Ingesta multi-fuente robusta y visor que no miente | 0/TBD | Not started | - |
| 3. Captura sincronizada de un botón (Core Value) | 0/TBD | Not started | - |
| 4. Detección por IA con proveedor verificado | 0/TBD | Not started | - |
| 5. Reconocimiento de patentes como sugerencia confirmable | 0/TBD | Not started | - |
| 6. Flujo de egreso: viaje, captura y liberación | 0/TBD | Not started | - |
| 7. Auditoría de peso, tolerancias y excepciones | 0/TBD | Not started | - |
| 8. Ingreso de proveedores, documentación y SLA | 0/TBD | Not started | - |
| 9. Consulta, evidencia exportable y vista para Compras | 0/TBD | Not started | - |
| 10. Integraciones reales: balanza, PALJET y recorrido | 0/TBD | Not started | - |
| 11. Empaquetado, instalador firmado y resiliencia | 0/TBD | Not started | - |
| 12. Motor de visión clásica seleccionable en caliente | 0/TBD | Not started | - |

---
*Roadmap creado: 2026-07-25 · Granularidad fina · Modo MVP con rebanadas verticales*
