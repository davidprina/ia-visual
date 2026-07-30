---
phase: 01-n-cleo-evidencia-trazable-y-contratos-externos-congelados
plan: 03
subsystem: video
tags: [contrato-de-frescura, slot-capacidad-1, concurrencia, opencv, cli-espanol, anti-vacuidad, tdd]

# Grafo de dependencias
requires:
  - phase: 01-01
    provides: proyecto uv, árbol de paquetes, contrato de descubrimiento de cli/ordenes/, compuerta única, fixtures de ruta hostil y video sintético, maquinaria de invariantes de código
  - phase: 01-02
    provides: "`RelojDelProceso` con `perf_counter_ns`, usado como eje de tiempos de la medición de frescura"
provides:
  - "Contrato de frescura fijado en código verificado: slot de capacidad 1, descarte del más viejo, contador de descartes donde ocurre el descarte"
  - "Puerto `FuenteDeVideo` con `PerfilDeFlujo.MONITOREO` y `PerfilDeFlujo.EVIDENCIA` declarados desde el día uno (D-15)"
  - "`FrameSellado` como DTO del puerto, con `eq=False` para que la igualdad no reviente contra un `ndarray`"
  - "`FuenteDeArchivo` con los dos modos de reproducción y `repetir` para convertir un recorte corto en fuente indefinida"
  - "`MetricasDeFuente` como envoltorio medidor del punto de encuentro: las métricas no pueden divergir de los hechos"
  - "`FuenteFalsa`, doble de NUC-04 y motor del modo demostración de D-48, sin abrir ningún archivo"
  - "Dos órdenes de consola reales y permanentes: `porteria probar-fuente` y `porteria metricas`"
  - "El Criterio de Éxito 5 con instrumento: 60 s en la compuerta, 600 s en la tanda programada, y dos pruebas de la prueba"
  - "`PuntoDeEncuentro` como protocolo, único punto de inyección que permite montar el antipatrón en la prueba sin duplicar el bucle de decodificación"
affects: [01-04-persistencia-de-evidencia, 01-07-rebanada-vertical, 02-camaras-ip]

# Seguimiento técnico
tech-stack:
  added: []
  patterns:
    - "Slot de capacidad 1 con `threading.Condition` en vez de `queue.Queue` o `deque`: el productor nunca bloquea y el descarte se cuenta donde ocurre"
    - "Las métricas envuelven el punto de encuentro en vez de recibir avisos, para que no puedan divergir de los hechos"
    - "Los fps efectivos se derivan de los sellos de captura de los cuadros, no del reloj de quien pregunta: la medición es exacta en cualquier equipo"
    - "El DTO del puerto vive con el puerto, no en el adaptador: el contrato de capas prohíbe que `aplicacion` mire hacia `infraestructura`"
    - "Un protocolo de inyección en el producto cuando —y sólo cuando— es lo que hace verificable una propiedad: montar el antipatrón sin duplicar el código que se juzga"
    - "Umbrales de prueba derivados de una constante de la plataforma (`sys.getswitchinterval()`) en vez de cableados"
    - "Opciones de consola con `typing.Annotated` cuando el tipo no es inmutable"

key-files:
  created:
    - src/porteria/aplicacion/puertos/salida/fuente_de_video.py
    - src/porteria/infraestructura/video/slot_ultimo_valor.py
    - src/porteria/infraestructura/video/metricas.py
    - src/porteria/infraestructura/video/falsa.py
    - src/porteria/infraestructura/video/archivo.py
    - src/porteria/cli/ordenes/probar_fuente.py
    - src/porteria/cli/ordenes/metricas.py
    - tests/integracion/test_slot_ultimo_valor.py
    - tests/integracion/test_fuente_archivo.py
    - tests/integracion/test_frescura.py
    - tests/integracion/test_frescura_anti_vacuidad.py
    - tests/arquitectura/invariantes/inv_01_03.py
  modified: []

key-decisions:
  - "`FrameSellado` va con `eq=False`: el `__eq__` que genera `dataclass` compara `datos == datos`, y comparar dos `ndarray` devuelve un arreglo — cualquier `frame_a == frame_b` o `frame in lista` habría levantado `ValueError: truth value of an array is ambiguous`"
  - "`FrameSellado` vive en el módulo del puerto y no en `slot_ultimo_valor.py` como pedía el plan: el puerto lo nombra en su firma y el contrato de capas prohíbe que `aplicacion` importe de `infraestructura`. El slot lo reexporta, así que todo importador sigue funcionando"
  - "`MetricasDeFuente` envuelve el punto de encuentro en vez de recibir avisos: con dos llamadas separadas bastaba con que un camino olvidara el aviso para que las métricas mintieran, y mentirían **hacia abajo**, mostrando todo sano"
  - "El tope del máximo de `publicar` se deriva de `sys.getswitchinterval()` y no es el 1 ms del plan: ese máximo está acotado por el planificador de CPython, no por el diseño del slot. La mediana y el p99 sí conservan el milisegundo del plan"
  - "`FuenteDeArchivo` rebobina reabriendo el contenedor y no con `CAP_PROP_POS_FRAMES = 0`: el posicionamiento por búsqueda deja `CAP_PROP_POS_MSEC` sin reiniciar en varios contenedores, y eso corrompería la cadencia del modo tiempo real sin ninguna señal"
  - "En `TIEMPO_REAL` el cuadro se sella **después** de la espera de cadencia: la espera es la simulación del momento en que una cámara habría entregado ese cuadro, y sellar antes le atribuiría un período completo de antigüedad que no tuvo"
  - "La ruta se valida con Python antes de dársela a OpenCV: `cv2.VideoCapture` devuelve `False` sin causa y no distingue «no está» de «no tengo permiso» de «falta el códec», que son tres cosas distintas para quien tiene que arreglarlo"
  - "La salida estructurada de `probar-fuente` nombra el archivo y no la ruta absoluta (T-01-02); la legible sí muestra la ruta, porque la lee quien está sentado frente al equipo"
  - "`porteria metricas` sin fuentes explica por qué está vacío en vez de mostrar una fila de ceros: un cero que se lee como «todo bien» cuando significa «no estoy mirando nada» es una herramienta de diagnóstico que miente hacia abajo"
  - "`evaluar_frescura` levanta con menos de 20 muestras: aprobar sobre cuatro puntos sería la peor forma de pasar en verde, sin haber medido"

patterns-established:
  - "Cuando un criterio de aceptación mide la plataforma y no el código, se sustituye por la medición defendible más cercana **y se agrega la contraprueba** que demuestra que la medición sustituta sigue detectando el fallo original"
  - "El antipatrón se monta dentro del archivo de prueba y nunca en `src/`; el producto sólo aporta el punto de inyección"

requirements-completed: [CAP-03, CAP-04]

# Métricas
duration: 76min
completed: 2026-07-30
---

# Phase 01 Plan 03: Contrato de frescura y fuente de archivo Summary

**El slot de capacidad 1 con descarte del más viejo queda fijado como código verificado, con la fuente de archivo que lo ejercita en dos modos, sus métricas consultables desde dos órdenes de consola nuevas, y el Criterio de Éxito 5 demostrado por partida doble más dos pruebas de la prueba.**

## Performance

- **Duration:** 76 min
- **Started:** 2026-07-30T02:23:39Z
- **Completed:** 2026-07-30T21:46:04Z (con un corte de sesión del proveedor en el medio)
- **Tasks:** 3
- **Files modified:** 12 (12 creados, 0 modificados)

## Accomplishments

- **La cuarta decisión no retrofiteable de la fase queda fijada, y las mediciones de la investigación se reproducen en este equipo casi exactamente.** Corrida propia de 20 s, mismo video, consumidor a 5 Hz:

  | | **Slot** (medido acá) | **Cola ilimitada** (medido acá) | Cola, según RESEARCH |
  |---|---|---|---|
  | Pendiente de la antigüedad | **−0,099 ms/s** | **+800,884 ms/s** | +806,6 ms/s |
  | Mediana 1.ª mitad | 20,1 ms | 3 942,3 ms | 4 152,7 ms |
  | Mediana 2.ª mitad | **12,7 ms** (baja) | **11 993,8 ms** (sube) | 12 218,7 ms |
  | Frames descartados | **402** | **0** | 0 |

  El antipatrón no es una hipótesis heredada de un documento: es un fallo que se reproduce en esta máquina, con este código, y que la evaluación detecta.

- **El Criterio de Éxito 5 tiene instrumento y bloquea la fusión.** `test_frescura_acotada` corre 60 s dentro de la compuerta rápida (medido: 60,65 s los dos archivos con `-m "not lenta"`, dentro del rango 55–90 s del plan). La versión de 600 s corrió completa y en verde: **2 pruebas en 620,78 s**, exit 0.

- **Dos pruebas de la prueba impiden que los umbrales pasen en silencio.** La de cero descartes es instantánea y protege el criterio 3 en cada empujón; la de la cola ilimitada monta el antipatrón sobre video real y exige que los **tres** criterios fallen. Verificado: falla los tres.

- **El operador gana dos órdenes que antes no existían.** Ejecutadas desde la consola real de Windows, con acentos intactos (Pitfall 8):

  ```
  Fuente             C:\p\demo porteria\sintetico ñandú.mp4
  Backend            FFMPEG
  Resolución         320x240
  Códec              FMP4
  Fps declarados     25.0
  Fps efectivos      25.01
  Frames publicados  76
  Frames descartados 60
  Antigüedad mediana 3.4 ms
  ```

- **Un defecto latente del patrón copiado, corregido antes de que existiera.** `FrameSellado` como `dataclass(frozen=True)` habría hecho `ValueError: truth value of an array with more than one element is ambiguous` en el primer `frame_a == frame_b`. Ver desviación 1.

- Suite completa: **293 pruebas rápidas en verde** (eran 242 al empezar) más 2 marcadas `lenta` en verde, 1 xfail deliberado, 4 contratos de arquitectura intactos y 10 invariantes de código nuevas.

## Task Commits

1. **Tarea 1: Slot, métricas y puerto `FuenteDeVideo`** — `e9b4514` (test) + `9e62bc6` (feat)
2. **Tarea 2: Fuente de archivo y las dos órdenes de consola** — `dba2556` (test) + `d6c844b` (feat)
3. **Tarea 3: Pruebas de frescura y las dos anti-vacuidad** — `317a24b`

## Files Created

**El contrato de frescura**

- `src/porteria/aplicacion/puertos/salida/fuente_de_video.py` — `PerfilDeFlujo`, `FrameSellado` y el `Protocol` `FuenteDeVideo`
- `src/porteria/infraestructura/video/slot_ultimo_valor.py` — `SlotUltimoValor` y el protocolo `PuntoDeEncuentro`
- `src/porteria/infraestructura/video/metricas.py` — `MetricasDeFuente`, `RegistroDeMetricas` y `CLAVES_DE_METRICAS`

**Las fuentes**

- `src/porteria/infraestructura/video/archivo.py` — `Modo`, `FuenteDeArchivo`, `FuenteNoDisponible`
- `src/porteria/infraestructura/video/falsa.py` — `FuenteFalsa` con cuadros deterministas por número de secuencia

**La consola**

- `src/porteria/cli/ordenes/probar_fuente.py` — `porteria probar-fuente` con `--archivo`, `--segundos`, `--modo`, `--json`
- `src/porteria/cli/ordenes/metricas.py` — `porteria metricas` con `--json`

**Las pruebas**

- `tests/integracion/test_slot_ultimo_valor.py` — 23 pruebas: conservación del contador, descarte exacto, determinismo de la fuente falsa, fórmula de la antigüedad
- `tests/integracion/test_fuente_archivo.py` — 15 pruebas: los dos modos cronometrados, ruta hostil, backend, errores que dicen qué revisar, las dos órdenes
- `tests/integracion/test_frescura.py` — `evaluar_frescura` y las dos pruebas del criterio
- `tests/integracion/test_frescura_anti_vacuidad.py` — `ColaIlimitadaDeMentira` y las dos pruebas de la prueba
- `tests/arquitectura/invariantes/inv_01_03.py` — 10 invariantes de este plan

## Decisions Made

Las decisiones completas están en el frontmatter. Las tres con más peso sobre los planes siguientes:

1. **`FrameSellado` vive en el módulo del puerto.** El plan lo ubicaba en `slot_ultimo_valor.py`, pero el puerto lo nombra en la firma de `tomar_mas_reciente` y el contrato `capas` prohíbe que `aplicacion` importe de `infraestructura` — y no sirve esconderlo bajo `TYPE_CHECKING`, porque `pyproject.toml` deja explícitamente sin activar `exclude_type_checking_imports` justamente para que esa vía no exista. El slot lo reexporta, así que `from ...slot_ultimo_valor import FrameSellado` sigue funcionando y el plan 01-07 no tiene que enterarse.

2. **Las métricas envuelven el punto de encuentro.** Es lo que hace imposible que `frames_publicados` y la antigüedad se desincronicen de lo que realmente pasó por la cañería. Para la Fase 2 esto significa que el adaptador PyAV hereda las métricas gratis: publica en el mismo envoltorio y no tiene que acordarse de avisar nada.

3. **`repetir` en la fuente de archivo.** Sin él, la prueba de 600 s habría necesitado un video de diez minutos versionado en el repositorio, que es exactamente lo que D-59 no quiere. Con él, un recorte de 30 s sostiene diez minutos de medición dando vueltas, y el rebobinado se hace reabriendo el contenedor para no corromper la cadencia.

## Deviations from Plan

### Criterios de aceptación sustituidos

**1. [Rule 1 - Bug] El tope de 1 ms como máximo absoluto de `publicar` mide el planificador de CPython, no el slot**

- **Found during:** Tarea 1
- **Issue:** El plan exigía que «ninguna llamada a `publicar` tardó más de 1 ms» durante la prueba concurrente. Con el slot funcionando perfectamente, la prueba falló **tres de tres** con máximos de hasta **4,358 ms**. La causa no es el slot: `sys.getswitchinterval()` es de **5,000 ms** en este equipo, y cuando el consumidor cede el GIL el productor puede quedar demorado hasta un intervalo completo aunque el lock esté libre. El criterio, tomado literalmente, sólo se podría satisfacer bajando el intervalo de conmutación del intérprete — es decir, cambiando la plataforma, no el código.
- **Fix:** Se midió el comportamiento real bajo la misma carga (200 Hz contra 5 Hz, 3 s) para el slot y para el antipatrón, y se sustituyó por tres aserciones que sí discriminan:

  | | Slot | `queue.Queue(maxsize=1)` |
  |---|---|---|
  | Publicaciones en 3 s | **557** | **16** |
  | Mediana | **0,0158 ms** | **195,01 ms** |
  | p99 | 0,042–0,101 ms | 197,67 ms |
  | Máximo | 0,156–0,697 ms | 197,67 ms |

  - `mediana < 1 ms` — el número del plan, con 60× de margen.
  - `p99 < 1 ms` — el número del plan, con 10× de margen.
  - `máximo < 5 × sys.getswitchinterval()` — derivado de la plataforma, no cableado. Un productor realmente bloqueado mide **195 ms**, ocho veces por encima de este tope, así que la separación entre ruido del planificador y bloqueo real es limpia.
- **Y se agregó la contraprueba que el plan no pedía:** `test_la_medicion_detecta_un_productor_bloqueado_por_el_consumidor` corre la **misma** función de medición contra `queue.Queue(maxsize=1)` y exige que falle. Sin ella, la sustitución habría sido un debilitamiento sin demostrar; con ella, la medición está probada como no vacua.
- **Files modified:** `tests/integracion/test_slot_ultimo_valor.py`
- **Committed in:** `9e62bc6`

**2. [Rule 1 - Bug] «Al llegar al fin del archivo `tomar_mas_reciente` devuelve `None`» descartaría un cuadro real**

- **Found during:** Tarea 2
- **Issue:** La prueba escrita al pie de la letra falló: terminado el archivo, el último cuadro publicado sigue en el slot y `tomar_mas_reciente` lo devuelve. Cumplir el criterio literal habría exigido **tirar** ese cuadro al detectar el fin del archivo — perder evidencia válida justo en el borde, que para la ruta de evidencia es el defecto y no la corrección.
- **Fix:** El contrato se precisó a lo que garantiza de verdad: la fuente **se vacía y no se repone**. La primera toma después del fin puede devolver el último cuadro; de ahí en adelante siempre `None`, sin excepción y sin quedarse esperando. La prueba afirma las tres cosas.
- **Files modified:** `tests/integracion/test_fuente_archivo.py`
- **Committed in:** `d6c844b`

### Auto-fixed Issues

**3. [Rule 1 - Bug] `FrameSellado` con la igualdad generada habría reventado contra `numpy`**

- **Found during:** Tarea 1
- **Issue:** El patrón verificado de RESEARCH declara `FrameSellado` como `@dataclasses.dataclass(frozen=True)`. Ese `__eq__` compara `datos == datos`; con un `ndarray` eso devuelve un arreglo de booleanos y `bool()` de ese arreglo levanta `ValueError: truth value of an array with more than one element is ambiguous`. Habría aparecido en el primer `frame_a == frame_b`, `frame in lista` o `assert frame == esperado` — es decir, en la primera prueba que alguien escribiera en la Fase 2.
- **Fix:** `eq=False`, con la igualdad por identidad, que además es la semántica correcta: dos capturas del mismo instante nominal no son «el mismo cuadro». Prueba de regresión `test_comparar_dos_frames_no_revienta_por_el_arreglo_de_numpy`.
- **Files modified:** `src/porteria/aplicacion/puertos/salida/fuente_de_video.py`, `tests/integracion/test_slot_ultimo_valor.py`
- **Committed in:** `9e62bc6`

**4. [Rule 3 - Blocking] `FrameSellado` no podía vivir en `infraestructura` sin romper el contrato de capas**

- **Found during:** Tarea 1
- **Issue:** El plan pedía `FrameSellado` en `slot_ultimo_valor.py` **y** que el puerto declarara `tomar_mas_reciente(...) -> FrameSellado | None`. Las dos cosas juntas violan el contrato `capas` de import-linter, que prohíbe `aplicacion → infraestructura`. Esconderlo bajo `TYPE_CHECKING` tampoco servía: `pyproject.toml` deja `exclude_type_checking_imports` sin activar a propósito, porque es una de las cuatro vías de evasión verificadas.
- **Fix:** El DTO se define en el módulo del puerto —que es su dueño natural— y `slot_ultimo_valor.py` lo importa y lo reexporta en su `__all__`. Todo importador que siga el plan al pie de la letra funciona igual. `datos` se declara `Any` para que `aplicacion` no necesite `numpy`.
- **Verification:** `uv run lint-imports --no-cache` → 4 contratos intactos.
- **Committed in:** `9e62bc6`

**5. [Rule 3 - Blocking] Un video de 30 s no alcanza para medir 60 s ni 600 s**

- **Found during:** Tarea 2
- **Issue:** El plan exige pruebas de frescura de 60 s y de 600 s sobre la fuente de archivo, pero la fixture `video_sintetico` de 01-01 genera **30 s**. Y D-59 no quiere videos largos versionados en el repositorio.
- **Fix:** `FuenteDeArchivo(..., repetir=True)`, que al llegar al fin reabre el contenedor y reancla la cadencia. Por defecto queda en `False`, así que el comportamiento que el plan describe —fin de archivo como estado normal— es el de siempre. Prueba propia: `test_la_fuente_repite_el_archivo_cuando_se_le_pide`.
- **Committed in:** `d6c844b`

**6. [Rule 3 - Blocking] `PuntoDeEncuentro` como protocolo para que la anti-vacuidad sea posible**

- **Found during:** Tarea 1
- **Issue:** `test_la_prueba_de_frescura_detecta_la_cola` tiene que reproducir video real contra una cola ilimitada. Sin un punto de inyección en el producto, la prueba habría tenido que duplicar el bucle de decodificación — y entonces estaría midiendo su propia copia, no el código que juzga la compuerta.
- **Fix:** `PuntoDeEncuentro` como `Protocol` en `slot_ultimo_valor.py` y el parámetro `destino` en `FuenteDeArchivo`, con valor por defecto el slot del contrato. El antipatrón vive **sólo** en `test_frescura_anti_vacuidad.py`; el producto no lo nombra.
- **Committed in:** `9e62bc6`, `d6c844b`

**7. [Rule 3 - Blocking] `typer.Option` como valor por defecto rompe `ruff B008` con tipos no inmutables**

- **Found during:** Tarea 2
- **Issue:** `--archivo` es un `Path` y `--modo` un enum; con el estilo de `version.py` ruff marca B008 («llamada a función en el valor por defecto»), que con `bool` no dispara. No es una formalidad: ese valor se evalúa una sola vez al importar y es una fuente clásica de estado compartido.
- **Fix:** `probar-fuente` declara sus opciones con `typing.Annotated`, que es el idioma actual de Typer. `metricas` conserva el estilo de `version.py` porque su única opción es el mismo `--json` booleano, y mantenerlas idénticas ayuda a quien compare las dos órdenes.
- **Committed in:** `d6c844b`

**8. [Rule 3 - Blocking] Las invariantes de las tareas 2 y 3 se agregaron de forma incremental**

- **Found during:** Tarea 1
- **Issue:** Igual que en 01-02: `test_invariantes_de_codigo.py` falla —correctamente— cuando una invariante nombra un archivo que todavía no existe.
- **Fix:** Cada tarea agrega a `inv_01_03.py` las invariantes de los archivos que ella misma crea. Las 10 quedan declaradas al cerrar el plan, exactamente como el plan pedía.
- **Committed in:** `e9b4514`, `d6c844b`, `317a24b`

---

**Total deviations:** 8 — 2 criterios de aceptación sustituidos con su medición y su contraprueba, 1 defecto latente corregido, 5 bloqueos resueltos.
**Impact on plan:** Ninguna amplía el alcance. Las dos sustituciones están reportadas arriba con los números que las justifican y **ambas agregan verificación en vez de quitarla**: la del tope de `publicar` trae una contraprueba nueva contra `queue.Queue`, y la del fin de archivo afirma tres propiedades donde el plan pedía una. Los cinco criterios de éxito del plan se cumplen sin excepción.

## Issues Encountered

- **La consola de Windows y el `-k` de pytest cambian el resultado de una prueba de tiempos.** La prueba de concurrencia pasaba al correr el archivo completo y fallaba al correrla filtrada con `-k`. No era azar: con menos pruebas por delante el intérprete está en otro estado de calentamiento y la conmutación del GIL cae distinto. Es la razón por la que el tope se derivó de `sys.getswitchinterval()` en vez de calibrarlo contra la corrida que casualmente pasaba.
- **`queue.Queue(maxsize=1)` cuelga el intérprete al salir si el productor quedó bloqueado en `put()`.** Apareció midiendo el antipatrón: el proceso no terminaba. Es la demostración más directa del problema —el productor está esperando, no lento— y obligó a que los hilos de la medición vayan como `daemon`. Que haga falta esa precaución para la cola y no para el slot ya dice todo.
- **El códec efectivo del video sintético es `FMP4` y no `mp4v`.** OpenCV normaliza el fourcc al escribir. No afecta a nada —la prueba afirma que el códec no está vacío, no cuál es— pero conviene saberlo antes de escribir una aserción sobre esa cadena.

## Known Stubs

Ninguno. Hay dos huecos declarados que **no** son stubs:

- `reconexiones` queda en 0 durante toda la Fase 1. No es un valor de mentira: la fuente de archivo no reconecta porque el fin de archivo es un estado normal y no una caída. El contador existe desde hoy para que el volcado de métricas no cambie de forma cuando la Fase 2 traiga el backoff exponencial de las cámaras IP. Está probado en su estado cero y en su incremento.
- Los dos perfiles de flujo devuelven el mismo cuadro. Es D-15 explícito, está escrito en el docstring de las dos fuentes, probado, y declarado como invariante de código.

## Threat Flags

Ninguna superficie nueva fuera de la que el plan ya modeló. Las cuatro amenazas con disposición `mitigate` quedan cubiertas y verificables:

| Amenaza | Estado | Verificable con |
|---------|--------|-----------------|
| T-01-15 (memoria del punto de encuentro sin techo) | mitigada | `test_productor_a_200_hz_...` (conservación del contador, mediana 0,016 ms) y `test_las_metricas_no_escriben_nada_en_el_camino_critico` (ventana acotada tras 1000 publicaciones) |
| T-01-08 (archivo corrupto o fin de archivo tumbando el proceso) | mitigada | `test_un_archivo_que_no_es_video_no_tumba_el_proceso` y `test_al_terminar_el_archivo_la_fuente_no_esta_viva_y_no_lanza` |
| T-01-02 (ruta desde la línea de comandos) | mitigada | `Path(...).resolve()` en la construcción, validación con Python antes de OpenCV, y `test_probar_fuente_en_json_no_filtra_la_ruta_absoluta` |
| T-01-11 (umbrales de la prueba de frescura que pasan siempre) | mitigada | `test_cero_descartes_con_consumidor_lento_es_fallo` (instantánea, bloquea la fusión) y `test_la_prueba_de_frescura_detecta_la_cola` (20 s, tanda programada) |

T-01-16 (métricas en memoria que se pierden al cerrar el proceso) sigue **aceptada**, y el hecho quedó escrito en la propia salida de `porteria metricas` en vez de callado.

## User Setup Required

Ninguno.

## Next Phase Readiness

**Listo para los planes que dependen de este:**

- **01-04 (persistencia de evidencia)** — tiene `FrameSellado` con su `instante_captura_ns` para calcular el desvío contra el instante del disparo, y `datos` como el `ndarray` que hay que codificar a JPEG y hashear. Recordá que `datos` **no** cruza al dominio.
- **01-07 (rebanada vertical)** — la orden `capturar` puede construirse sobre `FuenteDeArchivo` sin tocar `cli/app.py`: alcanza con un módulo nuevo en `cli/ordenes/` con su `registrar(app)`. `tests/aceptacion/test_rebanada_captura.py` sigue en `xfail` a propósito.
- **Fase 2 (cámaras IP)** — el adaptador PyAV implementa el mismo puerto y publica en el mismo `MetricasDeFuente`: hereda métricas y contrato de frescura sin escribir una línea de ninguno de los dos. Lo único suyo es la reconexión con backoff exponencial y jitter, y el watchdog por keyframe.

**Sin bloqueos.** Sigue abierta, de 01-01 y sin relación con este plan, la Tarea 4 de protección de rama en GitHub.

**Dato para el planificador de la Fase 2:** la compuerta rápida pasó de ~25 s a **1 min 47 s**, y 60 de esos segundos son la prueba de frescura. Es un costo consciente —D-53 elige la versión de 60 s justamente para que la de 600 s no bloquee—, pero conviene no sumarle otra prueba de un minuto sin discutirlo: el presupuesto de latencia de la compuerta ya está comprometido.

## Self-Check: PASSED

- 12 archivos declarados como creados: los 12 existen en el árbol.
- 5 hashes de commit declarados: los 5 existen en `git log`.
- `uv run python scripts/compuerta.py` → **COMPUERTA EN VERDE**, los cuatro pasos, exit 0, en 1 min 47 s.
- `uv run pytest -q -m "not lenta"` → **293 pruebas ejecutadas**, 1 xfail esperado.
- `uv run pytest -m lenta tests/integracion/test_frescura*.py` → 2 pruebas en verde en 620,78 s.
- `uv run lint-imports --no-cache` → 4 contratos intactos, 0 rotos.
- `uv run ruff check .` → sin hallazgos.
- `uv run pytest tests/arquitectura/test_invariantes_de_codigo.py -q` → 41 en verde (10 de este plan).
- `src/porteria/cli/app.py` sin modificar por este plan: `git log 53c5e6b..HEAD -- src/porteria/cli/app.py` → vacío.
- Las cuatro órdenes verificadas en la consola real de Windows: `probar-fuente` legible (exit 0), `--json` parseable, archivo inexistente (exit 2, sin traceback), `metricas --json` (exit 0).

---
*Phase: 01-n-cleo-evidencia-trazable-y-contratos-externos-congelados*
*Completed: 2026-07-30*
