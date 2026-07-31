---
phase: 01-n-cleo-evidencia-trazable-y-contratos-externos-congelados
plan: 06
subsystem: runtime-y-configuracion
tags: [bitacora, structlog, rotacion, redaccion-de-secretos, configuracion-dos-capas, pydantic-settings, cli-espanol, tdd]

# Grafo de dependencias
requires:
  - phase: 01-01
    provides: proyecto uv, árbol de paquetes, contrato de descubrimiento de cli/ordenes/, compuerta única, fixtures de ruta hostil, maquinaria de invariantes de código
  - phase: 01-02
    provides: "`RelojDelProceso` y el puerto `Reloj`, usados como único origen del instante de cada cambio de configuración"
provides:
  - "Bitácora técnica rotativa con nivel configurable (NUC-06), separada de la cadena de custodia por construcción y no por disciplina"
  - "`configurar_bitacora(directorio, nivel, bytes_maximos, respaldos)` y `directorio_de_bitacora_por_defecto()`, listos para que `armar_aplicacion()` del plan 01-07 los enchufe"
  - "Redactor de secretos como procesador de `structlog`, corriendo antes de cualquier handler, con demostración de extremo a extremo"
  - "`CLAVES_SENSIBLES` como lista única de todo el producto, que el anonimizador de cassettes del plan 01-10 reutiliza"
  - "Puerto `Configuracion` con su DTO `ValorDeConfiguracion`"
  - "`ConfiguracionDeArranque`: capa 1 de D-30 con exactamente dos campos y ninguno donde quepa una credencial"
  - "`ConfiguracionEnBase` sobre un `Engine` inyectado, con autoría obligatoria en cada escritura"
  - "`CATALOGO`: las siete claves de la capa 2 que el composition root del plan 01-07 recorre, con tipo, valor por defecto y ayuda"
  - "Orden de consola `porteria configurar` con `--listar`, `--clave`, `--valor`, `--autor` y `--json`"
affects: [01-07-rebanada-vertical, 01-10-contratos-externos, 02-camaras-ip, 11-instalador]

# Seguimiento técnico
tech-stack:
  added: []
  patterns:
    - "La cadena de procesadores de `structlog` corre una sola vez y los handlers sólo eligen el formato: es lo que hace imposible que un destino nuevo esquive el redactor"
    - "Separación estructural por invariante de código en vez de por convención: el módulo de bitácora no puede nombrar a la cadena de custodia"
    - "El adaptador de persistencia recibe el `Engine` inyectado y no es dueño del esquema, lo que permite que dos planes de la misma ola avancen sin acoplarse"
    - "Una herramienta de diagnóstico suelta siempre el recurso que abre: el motor se cierra en un `finally`"
    - "El catálogo como estructura consultable en vez de siete constantes sueltas: la consola y el composition root lo recorren en vez de repetir la lista"
    - "El error que llega a la consola es el mensaje del dominio con sus dos números, no la `ValidationError` de la biblioteca"

key-files:
  created:
    - src/porteria/infraestructura/runtime/bitacora.py
    - src/porteria/infraestructura/runtime/redaccion.py
    - src/porteria/aplicacion/puertos/salida/configuracion.py
    - src/porteria/infraestructura/configuracion/arranque.py
    - src/porteria/infraestructura/configuracion/en_base.py
    - src/porteria/cli/ordenes/configurar.py
    - tests/integracion/test_bitacora.py
    - tests/integracion/test_redaccion_de_secretos.py
    - tests/integracion/test_configuracion_dos_capas.py
    - tests/arquitectura/invariantes/inv_01_06.py
  modified: []

key-decisions:
  - "La bitácora usa `ProcessorFormatter` con la cadena compartida en `structlog.configure` y el renderizador por handler: es la única disposición que deja el redactor **antes** de todo destino y a la vez permite JSON al archivo y formato legible a consola"
  - "El archivo se renderiza como JSON por línea y no como pares clave-valor: es lo que hace que las pruebas afirmen sobre datos y no sobre texto libre, y que una `ñ` se pueda comparar por igualdad exacta"
  - "`configurar_bitacora` reemplaza su configuración anterior en vez de sumarse: acumular handlers duplicaría cada línea y dejaría archivos abiertos que en Windows no se pueden borrar"
  - "La redacción compara el nombre de la clave **por subcadena, sin acentos y sin distinguir mayúsculas**: los nombres los eligen los sistemas ajenos, y `hash_credencial` tiene que caer igual que `token`"
  - "Más allá del tope de profundidad se redacta entero: no poder inspeccionar una estructura no es motivo para dejar pasar lo que tenga adentro"
  - "El redactor devuelve una estructura nueva y nunca muta la del llamador: un procesador que destruye el objeto que le pasan es una bomba de tiempo"
  - "`ConfiguracionDeArranque` usa el prefijo de entorno `PORTERIA_ARRANQUE_` y no `PORTERIA_`: con `extra=\"forbid\"`, un prefijo genérico habría chocado con `PORTERIA_RAIZ_PRUEBAS`, que es de la suite"
  - "El largo de la raíz de evidencia se valida en el cargador **antes** de construir el modelo, porque pydantic envuelve todo error de validador en `ValidationError` y lo que tiene que llegar a la consola es el mensaje con los dos números"
  - "`ConfiguracionEnBase` no es dueño del esquema: nombra la tabla y declara `COLUMNAS_REQUERIDAS` como contrato con el plan 01-05, y las pruebas crean el esquema mínimo"
  - "El valor se persiste como JSON en una sola columna y el tipo lo declara el catálogo: evita una columna de tipo que podría contradecir al catálogo"
  - "`porteria configurar --listar` funciona sin archivo de arranque y sin base, mostrando el catálogo y diciendo de dónde salen los valores: quien instala necesita ver qué claves existen justo cuando todavía no configuró nada"
  - "La orden suelta el motor en un `finally`: sin eso, `--listar` dejaba tomado el archivo de la base y en Windows nadie podía borrarlo ni moverlo"

patterns-established:
  - "Cuando una separación importa de verdad, se declara como invariante de ausencia sobre el texto del módulo: la disciplina se olvida, la invariante corre en cada empujón"
  - "Un control de seguridad se prueba dos veces: una sobre la función y otra de extremo a extremo sobre el archivo real, porque una función perfecta que nadie invoca no protege nada"

requirements-completed: [NUC-06, DIS-06]

# Métricas
duration: 312min
completed: 2026-07-31
---

# Phase 01 Plan 06: Bitácora técnica y configuración en dos capas Summary

**La bitácora técnica queda separada de la cadena de custodia por una invariante de código y no por disciplina, ningún valor que se parezca a una credencial puede llegar a un archivo —demostrado de extremo a extremo—, y la configuración vive en dos capas con la frontera correcta: dos rutas en el archivo y las siete claves restantes en la base, cada cambio con quién y cuándo.**

## Performance

- **Duration:** 312 min de reloj de pared
- **Started:** 2026-07-30T21:58:28Z
- **Completed:** 2026-07-31T03:10:37Z
- **Tasks:** 3
- **Files modified:** 10 (10 creados, 0 modificados)

> **Advertencia sobre esta métrica.** Los 312 minutos son reloj de pared e incluyen un **corte de sesión del proveedor** en medio de la Tarea 1, con la fase RED escrita y sin commitear. El tiempo de trabajo efectivo es una fracción de ese número. Conviene descontarlo al mirar la velocidad promedio, igual que se hizo con el corte del plan 01-03.

## Accomplishments

- **La separación entre las dos bitácoras dejó de depender de que alguien se acuerde.** El antipatrón que el catálogo de pitfalls marca como señal de alerta —un solo `logger` con un parámetro `es_auditoria=True`— es ahora **imposible de escribir sin romper la compuerta**: hay una invariante de ausencia sobre el texto de `runtime/bitacora.py` que corre en el paso 1 de `scripts/compuerta.py`. Los dos módulos comparten cero líneas: la técnica es `structlog` sobre `RotatingFileHandler`, la cadena de custodia es `dominio/auditoria/registro.py` sobre la tabla encadenada.

- **NUC-06 está cumplido con las dos propiedades medidas, no declaradas.** Rotación verificada escribiendo hasta pasar el tope (aparece `porteria.log.1`, el archivo activo vuelve a crecer desde cero y nunca supera `bytes_maximos`), respaldos acotados verificados con 200 eventos contra `respaldos=3` exigiendo que `porteria.log.4` no aparezca nunca, y nivel configurable verificado en los dos sentidos: con `WARNING` el evento `info` no está, y bajando el nivel **en caliente** el mismo evento pasa a estar.

- **Ninguna credencial puede llegar a un archivo, y está demostrado donde importa.** La prueba de extremo a extremo emite en una sola llamada una contraseña, una cabecera `Authorization: Basic …`, un hash en formato PHC, un secreto anidado a tres niveles dentro de listas y diccionarios, y una URL con `token=`; después lee el archivo real y exige que el secreto no aparezca en **ninguna** de sus líneas — y que sí aparezca la marca de redacción y el contexto ligado, para que la prueba no pueda pasar por no haber escrito nada. La redacción de URL es parcial a propósito: `desde=2026-01-01` sobrevive y el token no.

- **La capa 1 no tiene dónde poner una credencial.** Dos campos, los dos obligatorios, y una prueba que recorre `model_fields` contrastándolos contra el **mismo** patrón `CLAVES_SENSIBLES` del módulo de redacción. Es el control (a) de T-01-04 convertido en regresión permanente en vez de una revisión de una sola vez.

- **El catálogo de las siete claves quedó listo para que el plan 01-07 lo enchufe**, con tipo, valor por defecto y ayuda por clave. `ventana_aceptacion_ms` vale 150 y su ayuda dice, en el código y en la salida de la consola, que el número **no está validado con el cliente ni medido en campo** (D-39) — y hay dos invariantes que exigen que las dos cosas sigan estando en el archivo.

- **El operador gana una orden más.** Ejecutada en la consola real de Windows, con acentos intactos:

  ```
  ventana_aceptacion_ms
    Valor            150
    Cambiado por     — (nunca se cambió)
    Qué es           Tolerancia, en milisegundos, dentro de la cual dos fotos de la misma
                     captura se consideran sincronizadas. ATENCIÓN: el valor por defecto es
                     no validado con el cliente ni medido en campo (D-39)...
  ```

  Y los tres caminos de error verificados con su código de salida real: clave desconocida → **exit 2** enumerando las siete válidas; sin `--autor` → **exit 2** explicando por qué hace falta; valor del tipo equivocado → **exit 2** diciendo «espera un valor de tipo entero». Ningún traceback.

- **Compuerta en verde y sin costo de latencia.** **365 pruebas rápidas** (eran 293) más 1 xfail deliberado, 4 contratos de arquitectura intactos, 46 pruebas de invariantes (5 declaradas por este plan) y 36 dependencias auditadas. La compuerta rápida **bajó** de 1 min 47 s a **1 min 41 s**: las 68 pruebas nuevas corren en menos de 3 s en total, así que el presupuesto de latencia que dejó el plan 01-03 sigue intacto.

## Task Commits

1. **Tarea 1: Bitácora técnica estructurada con rotación y nivel configurable** — `6a0c604` (test) + `cef8596` (feat)
2. **Tarea 2: Redacción de secretos antes de cualquier destino** — `b5f6abf` (test) + `bc0a056` (feat)
3. **Tarea 3: Configuración en dos capas con autoría y la orden `configurar`** — `07e2fac` (test) + `b0ec200` (feat)

## Files Created

**La bitácora técnica**

- `src/porteria/infraestructura/runtime/bitacora.py` — `configurar_bitacora`, `obtener_bitacora`, `cerrar_bitacora`, `directorio_de_bitacora_por_defecto`, `procesadores_compartidos`
- `src/porteria/infraestructura/runtime/redaccion.py` — `CLAVES_SENSIBLES`, `PATRON_EN_URL`, `REDACTADO`, `PROFUNDIDAD_MAXIMA`, `redactar`

**La configuración en dos capas**

- `src/porteria/aplicacion/puertos/salida/configuracion.py` — el `Protocol` `Configuracion` y el DTO `ValorDeConfiguracion`
- `src/porteria/infraestructura/configuracion/arranque.py` — `ConfiguracionDeArranque`, `cargar_configuracion_de_arranque`, `validar_largo_de_raiz_evidencia` y sus tres excepciones
- `src/porteria/infraestructura/configuracion/en_base.py` — `CATALOGO`, `ClaveDeConfiguracion`, `ConfiguracionEnBase`, `convertir_desde_texto`, `catalogo_como_valores`

**La consola**

- `src/porteria/cli/ordenes/configurar.py` — `porteria configurar` con `--listar`, `--clave`, `--valor`, `--autor` y `--json`

**Las pruebas**

- `tests/integracion/test_bitacora.py` — 12 pruebas: rotación, respaldos acotados, nivel en los dos sentidos, contexto ligado, UTF-8, higiene de handlers
- `tests/integracion/test_redaccion_de_secretos.py` — 28 pruebas: una por clave sensible con y sin mayúsculas, anidamiento, cabeceras, PHC, URL, ciclos, tope de profundidad, el enchufe y el extremo a extremo
- `tests/integracion/test_configuracion_dos_capas.py` — 28 pruebas: las dos capas y los seis caminos de la orden de consola
- `tests/arquitectura/invariantes/inv_01_06.py` — 5 invariantes de este plan

## Decisions Made

Las decisiones completas están en el frontmatter. Las cuatro con más peso sobre los planes siguientes:

1. **La cadena de procesadores es compartida y los handlers sólo eligen el formato.** Es lo que hace que «el redactor corre antes de cualquier destino» sea una propiedad de la estructura y no una promesa. Para el plan 01-07 significa que agregar un destino nuevo a la bitácora no requiere acordarse de nada; para el 01-10, que el anonimizador de cassettes puede importar `CLAVES_SENSIBLES` y quedar sincronizado con la bitácora por construcción.

2. **`ConfiguracionEnBase` no es dueña del esquema.** Nombra la tabla, declara `COLUMNAS_REQUERIDAS` como contrato explícito con el plan 01-05 y recibe el `Engine` inyectado. El plan 01-07 le pasa el motor real **sin modificar la clase**. Si el esquema real nombra las columnas distinto, las pruebas de este plan lo dicen antes que el cliente.

3. **El valor se persiste como JSON y el tipo lo declara el catálogo.** Una columna `tipo` en la tabla podría contradecir al catálogo, y entonces habría dos verdades sobre el mismo dato. Con una sola verdad, `leer` valida contra el catálogo al deserializar y un `"doscientos"` guardado a mano se detecta al leerlo, no seis meses después.

4. **`porteria configurar --listar` no depende de que haya base.** Es la decisión que reconcilia dos exigencias del propio plan; está explicada en detalle más abajo, en «Criterios reconciliados».

## Deviations from Plan

### Criterios reconciliados

**1. `--listar` sin base: dos criterios del mismo plan que no se podían cumplir a la vez tal como estaban escritos**

- **Found during:** Tarea 3
- **Tensión:** el plan exige, por un lado, que «si el archivo no existe, la aplicación no inventa valores: informa la ruta donde lo buscó y qué orden lo crea», y por el otro que `uv run porteria configurar --listar --json` **devuelva exit 0 y JSON parseable**. En este equipo no hay archivo de arranque, así que las dos cosas juntas son contradictorias si el listado depende del arranque.
- **Resolución, sin debilitar ninguno de los dos:**
  - `cargar_configuracion_de_arranque()` cumple el primero **literalmente**: levanta `ConfiguracionDeArranqueAusente` con la ruta exacta donde buscó, qué orden lo crea y un ejemplo del contenido del archivo. Hay una prueba que afirma las tres cosas.
  - La **orden de consola** distingue entre mostrar y cambiar. Mostrar cae al catálogo y **declara el origen** (`"origen": "catalogo"`, más una nota que dice que todavía no hay base donde se haya guardado un cambio). Cambiar **sí** exige la base y termina en exit 2 explicando por qué.
- **Por qué esta resolución y no fallar:** quien está instalando el producto necesita ver qué claves existen justo en el momento en que todavía no configuró nada. Fallar ahí sería lo peor de los dos mundos. Y el listado no miente: dice de dónde sale cada número.
- **Verificado:** `uv run porteria configurar --listar --json` → **exit 0**, JSON parseable, 7 claves, `origen: catalogo`.
- **Committed in:** `b0ec200`

*(Ninguna de las tres sustituciones pendientes de ratificación de esta fase se toca acá, y ésta no es una sustitución: no se reemplazó ninguna medición por otra más débil. Se resolvió una contradicción interna del plan cumpliendo los dos criterios en el lugar que le corresponde a cada uno.)*

### Auto-fixed Issues

**2. [Rule 1 - Bug] La orden `configurar` dejaba tomado el archivo de la base**

- **Found during:** Tarea 3
- **Issue:** la orden construía su propio `Engine` y nunca lo soltaba. En una corrida suelta el proceso termina y no se nota; en la suite, **cuatro pruebas fallaron en el desmontaje** con `PermissionError: [WinError 32] El proceso no tiene acceso al archivo porque está siendo utilizado por otro proceso`. No es un problema de las pruebas: es el comportamiento real en Windows, donde mientras el pool tenga una conexión abierta nadie puede borrar ni mover la base. Una herramienta de diagnóstico que traba la base que diagnostica —justo cuando alguien intenta copiarla para mandarla a soporte, o restaurar un respaldo— es un defecto de producto.
- **Fix:** el motor viaja aparte de la configuración en un `_Entorno`, el cuerpo de la orden se extrajo a `_ejecutar` y la orden lo envuelve en `try/finally` con `motor.dispose()`. Se suelta pase lo que pase, incluidas las salidas por error.
- **Files modified:** `src/porteria/cli/ordenes/configurar.py`
- **Committed in:** `b0ec200`

**3. [Rule 3 - Blocking] pydantic envuelve todo error de validador, así que el mensaje útil no llegaba a la consola**

- **Found during:** Tarea 3
- **Issue:** el plan pide que configurar una raíz de evidencia demasiado larga produzca un error **que diga el máximo y el largo elegido** (Pitfall 3). Con la validación puesta sólo en un `field_validator`, pydantic la convierte en `ValidationError` y el tipo propio se pierde. Verificado empíricamente antes de decidir: un `ValueError` propio levantado en `model_post_init` sale como `ValidationError | 1 validation error for M / Value error, ...`. En una planta sin área de sistemas, eso no le dice nada a nadie.
- **Fix:** la comprobación vive en `validar_largo_de_raiz_evidencia()`, que es una función propia y levanta `RaizDeEvidenciaDemasiadoLarga` con los dos números. `cargar_configuracion_de_arranque` la llama **antes** de construir el modelo —así el camino real de carga entrega el error limpio— y el `field_validator` la llama también, para que el tipo tampoco pueda sostener un valor inválido si alguien lo construye a mano.
- **Y la prueba afirma las dos cosas:** que el cargador levanta el error tipado con los dos números, y que el modelo **también** rechaza el valor con los dos números en el mensaje. Sin la segunda, la validación podría haberse quedado sólo en el borde.
- **Files modified:** `src/porteria/infraestructura/configuracion/arranque.py`, `tests/integracion/test_configuracion_dos_capas.py`
- **Committed in:** `07e2fac`, `b0ec200`

**4. [Rule 3 - Blocking] `extra="forbid"` con el prefijo de entorno `PORTERIA_` habría chocado con la propia suite**

- **Found during:** Tarea 3
- **Issue:** el uso idiomático de `pydantic-settings` sería `env_prefix="PORTERIA_"`. Pero `tests/conftest.py` ya usa `PORTERIA_RAIZ_PRUEBAS` para fijar la base de las pruebas, y este mismo plan agrega `PORTERIA_DIRECTORIO_CONFIGURACION`. Con `extra="forbid"` —que es lo que hace que la capa 1 no pueda tener un tercer campo por descuido— una variable de entorno prefijada y no declarada es un fallo de arranque.
- **Fix:** prefijo propio y específico, `PORTERIA_ARRANQUE_`, que no puede chocar con ninguna otra variable del proyecto. El control que importa —`extra="forbid"`, que es lo que impide que la capa 1 crezca— queda intacto.
- **Committed in:** `b0ec200`

**5. [Rule 3 - Blocking] Las invariantes de la Tarea 3 se agregaron de forma incremental**

- **Found during:** Tarea 1
- **Issue:** igual que en 01-02 y 01-03: `test_invariantes_de_codigo.py` falla —correctamente— cuando una invariante nombra un archivo que todavía no existe.
- **Fix:** cada tarea agrega a `inv_01_06.py` las invariantes de los archivos que ella misma crea. Las 5 quedan declaradas al cerrar el plan, exactamente como el plan pedía.
- **Committed in:** `6a0c604`, `07e2fac`

---

**Total deviations:** 5 — 1 contradicción interna del plan reconciliada, 1 defecto real corregido, 3 bloqueos resueltos.
**Impact on plan:** ninguna amplía el alcance y ninguna debilita una verificación. La reconciliación de `--listar` **agrega** un camino probado (el listado sin base, con su origen declarado) en lugar de quitar el mensaje que el plan pedía, que sigue existiendo y sigue probado. Los cinco criterios de éxito del plan se cumplen sin excepción.

## Issues Encountered

- **`ruff` reordena los imports según si el módulo importado existe o no.** Escribir la prueba antes que el código —que es el punto de TDD— hace que `porteria.…` se clasifique como paquete de terceros mientras el módulo no existe, y como propio en cuanto aparece. La consecuencia práctica: el commit RED y el GREEN tocan el bloque de imports del mismo archivo de prueba. No es un problema, pero explica por qué los commits `feat` incluyen un cambio de dos líneas en el archivo de prueba.
- **Un `RotatingFileHandler` mide el tope en caracteres del mensaje formateado, no en bytes del archivo.** Con mensajes ASCII coinciden; con acentos, un archivo puede pasar unos bytes del tope. Las pruebas de rotación usan relleno ASCII a propósito para que la aserción sobre el tamaño sea exacta y no aproximada.
- **`KeyError` agrega comillas al convertirse a texto.** `ClaveDesconocida` hereda de `KeyError` —que es el tipo semánticamente correcto—, así que la orden imprime `error.args[0]` y no `str(error)`, para que el mensaje del operador no salga entre comillas sueltas.

## Known Stubs

Ninguno. Hay dos comportamientos que podrían confundirse con un stub y no lo son:

- **`--listar` mostrando el catálogo cuando no hay base.** No es un valor de relleno: la salida **declara** su origen (`"origen": "catalogo"`) y explica en una nota que todavía no hay base donde se haya guardado un cambio. Está probado en los dos estados, con base y sin ella.
- **`cambiado_por` en `None` para una clave que nadie tocó.** Es deliberado y está probado: inventar un autor para un valor por defecto sería fabricar un rastro que nadie dejó, y un rastro fabricado es peor que ninguno.

La orden `porteria primer-arranque` que los mensajes de error mencionan **todavía no existe** — corresponde a D-23 y llega con el asistente de primer arranque. El mensaje no promete que exista hoy: da además el contenido exacto del archivo para crearlo a mano, que es el camino que funciona ahora mismo.

## Threat Flags

Ninguna superficie nueva fuera de la que el plan ya modeló. Las cinco amenazas con disposición `mitigate` quedan cubiertas y verificables:

| Amenaza | Estado | Verificable con |
|---------|--------|-----------------|
| T-01-04 (secretos en la bitácora y en el archivo de arranque) | mitigada, con los tres controles | (a) `test_ninguna_clave_de_la_capa_1_se_parece_a_una_credencial`; (b) `test_el_redactor_esta_en_la_cadena_antes_del_renderizador`; (c) `test_ningun_secreto_llega_al_archivo_de_bitacora` |
| T-01-22 (cambio de configuración sin autor) | mitigada | `test_escribir_sin_autor_falla` y `test_listar_devuelve_el_valor_con_quien_lo_cambio_y_cuando` |
| T-01-23 (bitácora técnica confundida con la cadena de custodia) | mitigada, **estructuralmente** | Invariante de ausencia sobre `bitacora.py`, corriendo en el paso 1 de la compuerta en cualquier plataforma |
| T-01-17 (raíz de evidencia que no entra en `MAX_PATH`) | mitigada | `test_una_raiz_de_evidencia_demasiado_larga_dice_el_maximo_y_el_largo_elegido` y su gemela sobre el modelo |
| T-01-24 (la bitácora llenando el disco de la evidencia) | mitigada | `test_nunca_hay_mas_respaldos_que_los_configurados` (200 eventos, `respaldos=3`, `porteria.log.4` nunca aparece) |

## User Setup Required

Ninguno para que la fase siga. Para operar el producto en un equipo real hará falta el archivo de arranque `porteria.toml`, que hoy se crea a mano con las dos claves que el mensaje de error indica y que a partir de D-23 creará el asistente de primer arranque.

## Next Phase Readiness

**Listo para los planes que dependen de este:**

- **01-07 (rebanada vertical)** — tiene las cinco piezas del contrato de consumo que el plan declaró: `configurar_bitacora(directorio, nivel, bytes_maximos, respaldos)` y `directorio_de_bitacora_por_defecto()` para la bitácora; `ConfiguracionEnBase(motor, reloj)` para enchufar sobre el `Engine` real del plan 01-05 sin tocar la clase; y `CATALOGO` con las siete claves —`ventana_aceptacion_ms` y `calidad_jpeg_por_camara` para el caso de uso de captura, `nivel_bitacora`, `bytes_maximos_bitacora` y `respaldos_bitacora` como argumentos de `configurar_bitacora`—. La orden `configurar` no toca `cli/app.py`, verificado: `git log ded03f9..HEAD -- src/porteria/cli/app.py` está vacío.
- **01-05 (persistencia)** — el contrato de la tabla está escrito y es corto: `configuracion` con las columnas `clave` (clave primaria, porque la escritura usa `ON CONFLICT(clave)`), `valor`, `cambiado_por` y `cambiado_en_utc_iso`, todas de texto. Está declarado en `COLUMNAS_REQUERIDAS`.
- **01-10 (contratos externos)** — el anonimizador de cassettes importa `CLAVES_SENSIBLES` y `redactar` de `runtime/redaccion.py` en vez de escribir su propia lista. La redacción ya alcanza a las cabeceras, que es el control (d) de T-01-04, y ya es recursiva, que es la forma real de un payload.
- **Fase 2 (cámaras IP)** — `obtener_bitacora(__name__).bind(camara=…)` es lo que va a hacer legible una bitácora de N fuentes concurrentes; el contexto acumulado por hilo está probado.

**Sin bloqueos.** Sigue abierta, de 01-01 y sin relación con este plan, la Tarea 4 de protección de rama en GitHub.

**Dato para el planificador:** la compuerta rápida quedó en **1 min 41 s**, seis segundos por debajo de donde la dejó el plan 01-03. Las 68 pruebas de este plan suman menos de 3 s: ninguna toca la red, ninguna duerme y ninguna mide tiempo real. El presupuesto de latencia sigue dominado por los 60 s de la prueba de frescura.

## Self-Check: PASSED

- 10 archivos declarados como creados: los 10 existen en el árbol.
- 6 hashes de commit declarados: los 6 existen en `git log`.
- `uv run python scripts/compuerta.py` → **COMPUERTA EN VERDE**, los cuatro pasos, exit 0, en 1 min 41 s.
- `uv run pytest -q -m "not lenta"` → **365 pruebas en verde**, 1 xfail esperado (`test_rebanada_captura.py`, que cierra en 01-07 y no se tocó).
- `uv run lint-imports --no-cache` → 4 contratos intactos, 0 rotos.
- `uv run ruff check .` → sin hallazgos.
- `uv run pytest tests/arquitectura/test_invariantes_de_codigo.py -q` → 46 en verde, 5 invariantes de este plan.
- `src/porteria/cli/app.py` sin modificar por este plan: `git log ded03f9..HEAD -- src/porteria/cli/app.py` → vacío.
- Las cuatro corridas de la orden verificadas en la consola real de Windows, con acentos intactos: `configurar --listar` (exit 0), `--listar --json` (exit 0, parseable, 7 claves), clave desconocida (exit 2), sin `--autor` (exit 2), tipo equivocado (exit 2). Ningún traceback.

---
*Phase: 01-n-cleo-evidencia-trazable-y-contratos-externos-congelados*
*Completed: 2026-07-31*
