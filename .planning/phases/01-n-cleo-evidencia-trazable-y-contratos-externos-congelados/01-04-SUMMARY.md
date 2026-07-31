---
phase: 01-n-cleo-evidencia-trazable-y-contratos-externos-congelados
plan: 04
subsystem: persistencia-de-evidencia
tags: [sha256, escritura-atomica, windows, max-path, path-traversal, cuarentena, opencv, tdd]

# Grafo de dependencias
requires:
  - phase: 01-01
    provides: proyecto uv, árbol de paquetes, compuerta única, maquinaria de invariantes, fixture de ruta hostil
  - phase: 01-02
    provides: HuellaDeIntegridad, EstadoDeIntegridad, FechaLocal, evaluar()
  - phase: 01-06
    provides: validar_largo_de_raiz_evidencia() y el tope de 170 caracteres
provides:
  - "Escritura atómica de evidencia en el idioma de Windows: `mkstemp` en el directorio de destino, `fsync` del archivo, `os.replace`, y limpieza del temporal ante cualquier fallo"
  - "SHA-256 calculado en la ingesta, en infraestructura, entregado al dominio como `HuellaDeIntegridad` ya construida"
  - "Verificación en streaming con `hashlib.file_digest` que detecta un byte alterado en tres posiciones distintas, el truncamiento y el reemplazo"
  - "Contenido duplicado con comportamiento explícito: misma huella, misma ruta, un solo archivo, sin excepción"
  - "Guardia de path traversal sobre la ruta que vuelve de la base, con seis vectores probados"
  - "Validación de MAX_PATH al construir el almacén, con un mensaje que dice los dos números"
  - "`CodificadorOpenCV` con calidad por cámara, PNG sin pérdida y miniatura de 320 px"
  - "`barrer_huerfanos` y `barrer_en_segundo_plano`: la cuarentena mueve y nunca elimina"
  - "Seis invariantes de código en `inv_01_04.py`"
affects: [01-05-esquema-y-migraciones, 01-07-rebanada-vertical, 01-09-identidad, 03-retencion-y-espacio, 11-despliegue]

# Seguimiento técnico
tech-stack:
  added: []
  patterns:
    - "Escritura atómica: temporal en el mismo directorio de destino, `os.replace` y nunca `os.rename`"
    - "El paso POSIX que no existe en Windows va guardado por plataforma, nunca silenciado con `except`/`pass`"
    - "Prefijo `\\\\?\\` en toda operación de archivo como cinturón adicional sobre MAX_PATH"
    - "La ruta que vuelve de la base es entrada no confiable: se valida antes de leer, no sólo antes de escribir"
    - "Un solo tope y un solo mensaje para el largo de la raíz, reutilizando la validación de configuración"
    - "El barrido de huérfanos recibe las rutas conocidas por parámetro y no consulta la base"

key-files:
  created:
    - src/porteria/aplicacion/puertos/salida/almacen_de_evidencia.py
    - src/porteria/aplicacion/puertos/salida/codificador.py
    - src/porteria/infraestructura/persistencia/evidencia_fs.py
    - src/porteria/infraestructura/persistencia/cuarentena.py
    - src/porteria/infraestructura/imagen/codificador_opencv.py
    - tests/integracion/test_almacen_evidencia.py
    - tests/integracion/test_verificacion_huella.py
    - tests/integracion/test_manipulacion_evidencia.py
    - tests/integracion/test_cuarentena_huerfanos.py
    - tests/integracion/test_ruta_evidencia_hostil.py
    - tests/arquitectura/invariantes/inv_01_04.py
  modified: []

key-decisions:
  - "`RaizDemasiadoLarga` es un **alias** de la excepción que ya declara `configuracion/arranque.py`, y la validación reutiliza `validar_largo_de_raiz_evidencia`: dos validaciones del mismo límite terminan divergiendo, y la que quede corta deja pasar rutas que fallan tres meses después con un `FileNotFoundError` mudo"
  - "La miniatura se codifica a calidad **90 y no 95**: es la única que deja dentro de la banda de 5 a 30 KiB tanto la imagen representativa (7,5 KiB) como el peor caso de ruido puro (21,3 KiB); a 95 el ruido se va a 32,7 KiB"
  - "El piso de 5 KiB de la miniatura **no es una propiedad del codificador**: un frame plano mide 1,55 KiB a cualquier calidad porque no hay información que codificar. Queda escrito en una prueba en vez de escondido detrás de imágenes convenientes"
  - "La cuarentena resuelve las colisiones de nombre con sufijo numérico: `os.replace` sobre un homónimo eliminaría el primero, y no eliminar de forma directa no serviría de nada si se eliminara así"
  - "`ruta_para_el_sistema` es pública y la comparten los dos módulos porque el sufijo de la cuarentena mide 90 caracteres, once más que el de la evidencia: es el primero en toparse con MAX_PATH"
  - "El archivo ausente levanta `FileNotFoundError` y no devuelve `COMPROMETIDA`: una purga con lápida y una fila huérfana son problemas distintos, y confundirlos escondería el segundo bajo el primero"
  - "El barrido en segundo plano corre en hilo **demonio**: cerrar la aplicación es lo que el portero hace al terminar el turno y un barrido a medio camino no puede impedírselo"

patterns-established:
  - "La prueba de la prueba se escribe como doble roto en el módulo de prueba: el verificador truncado demuestra que las tres posiciones no son decorativas"
  - "Los límites físicos de un criterio se dejan escritos en una prueba con nombre propio, no se esquivan eligiendo datos de entrada favorables"

requirements-completed: [EVI-05, EVI-06, DIS-06]

# Métricas
duration: 14min
completed: 2026-07-31
---

# Phase 01 Plan 04: Almacén de evidencia, verificación y cuarentena Summary

**La evidencia se escribe de forma atómica en el idioma de Windows, con la huella SHA-256 calculada en la ingesta, una verificación que detecta un byte alterado en tres posiciones distintas, y huérfanos que van a cuarentena en vez de a la papelera.**

## Performance

- **Duration:** 14 min de tramo commiteado (`4c8bef9` → `a3fecdc`). El plan se ejecutó en dos sesiones: un límite de sesión del proveedor cortó la primera, que dejó escritas —sin commitear— las dos primeras suites de la Tarea 1.
- **Completed:** 2026-07-31
- **Tasks:** 3, las tres con ciclo TDD completo (test → feat)
- **Files created:** 11

## Accomplishments

- **La primera decisión no retrofiteable de la fase queda fijada:** el SHA-256 se calcula en el momento de la ingesta, en infraestructura, y el dominio recibe una `HuellaDeIntegridad` ya construida. La invariante que prohíbe `hashlib` en `huella.py` sigue en verde, que es la comprobación de que la responsabilidad quedó donde el plan 01-02 la dejó anotada.
- **La mitad «archivo» del Criterio de Éxito 2 está cumplida y probada por las dos puntas.** Recalcular reproduce exactamente lo persistido, y alterar **un solo byte** en la posición 0, en `len//2` y en `len-1` lo rompe en los tres casos, más el control sin alterar, el truncamiento y el reemplazo del archivo entero.
- **Los tres choques de plataforma se verificaron de primera mano antes de escribir una línea**, no se copiaron del plan: `os.fsync` sobre un descriptor de directorio lanza `PermissionError(13)`; `os.rename` sobre un archivo existente lanza `FileExistsError(17)` / WinError 183; `os.replace` sobre existente deja el destino con el contenido nuevo. El prefijo `\\?\` se comprobó funcionando con `open` y con `mkstemp`.
- **El contenido duplicado tiene comportamiento explícito y probado**, coherente con el esquema sin UNIQUE en `ruta_relativa` que acordó el plan 01-05: dos guardados del mismo contenido dejan **un solo archivo**, devuelven la misma huella y la misma ruta, y el segundo no lanza.
- **Seis vectores de path traversal rechazados sin tocar el disco**, incluidos `..` con las dos barras, la ruta absoluta con letra de unidad, la ruta POSIX y el recurso UNC — los cuatro últimos se validan igual en las dos plataformas porque la ruta se interpreta siempre con la gramática de Windows, que es la más amplia.
- Suite completa: **446 pruebas en verde** (eran 366) más el xfail deliberado de la rebanada vertical, cuatro contratos de arquitectura intactos y 52 pruebas de invariantes.

## Task Commits

1. **Tarea 1: Escritura atómica con huella y verificación** — `4c8bef9` (test) + `f170270` (feat)
2. **Tarea 2: Un byte alterado en tres posiciones distintas** — `e45bf9d` (test; la implementación ya existía, la tarea es la prueba)
3. **Tarea 3: Codificador, miniatura y cuarentena de huérfanos** — `6b426c4` (test) + `a3fecdc` (feat)

## Files Created

**Puertos**

- `aplicacion/puertos/salida/almacen_de_evidencia.py` — `AlmacenDeEvidencia` (Protocol) y `RutaFueraDeLaRaiz` como excepción **del contrato**, no del adaptador
- `aplicacion/puertos/salida/codificador.py` — `CodificadorDeImagen` (Protocol) y `DescripcionDeImagen`

**Infraestructura**

- `infraestructura/persistencia/evidencia_fs.py` — `guardar_atomico`, `verificar`, `ruta_absoluta`, `ruta_para_el_sistema` y `AlmacenDeEvidenciaEnDisco`
- `infraestructura/persistencia/cuarentena.py` — `barrer_huerfanos`, `barrer_en_segundo_plano` y `ArchivoEnCuarentena`
- `infraestructura/imagen/codificador_opencv.py` — `CodificadorOpenCV`, `CalidadInvalida`, `FalloDeCodificacion`

**Pruebas** — 75 nuevas, todas bajo la ruta con espacios y acentos

- `test_almacen_evidencia.py` (14) · `test_verificacion_huella.py` (8) · `test_ruta_evidencia_hostil.py` (19) · `test_manipulacion_evidencia.py` (9) · `test_cuarentena_huerfanos.py` (25)
- `tests/arquitectura/invariantes/inv_01_04.py` — 6 invariantes

## Decisions Made

Las decisiones completas están en el frontmatter. Las tres que más peso tienen hacia adelante:

1. **Un solo tope de largo de ruta, no dos.** El plan pedía una excepción `RaizDemasiadoLarga` propia, pero `configuracion/arranque.py` ya validaba el mismo límite de 170 con el mismo mensaje. Se hizo alias y se reutilizó la función. Dos validaciones del mismo número divergen tarde o temprano, y la consecuencia de que diverjan la paga el cliente con escrituras que empiezan a fallar a los tres meses.
2. **El archivo ausente no es evidencia comprometida.** `verificar` levanta `FileNotFoundError` con la ruta y la explicación. Devolver `COMPROMETIDA` sería más cómodo y escondería una purga con lápida (D-10) o una raíz de evidencia sin montar detrás de un cartel de manipulación.
3. **La cuarentena no puede eliminar ni por accidente.** No alcanza con no llamar a una función de borrado: `os.replace` sobre un homónimo elimina el destino igual. Por eso el barrido busca un nombre libre antes de mover, y hay una prueba con dos huérfanos del mismo nombre que afirma que los dos contenidos sobreviven.

## Deviations from Plan

### Sustitución de criterio reportada para ratificación del usuario

**1. [Sustitución] El piso de 5 KB de la miniatura no es alcanzable para cualquier frame**

- **Criterio del plan:** «Existe una prueba que afirma que `miniatura(frame)` mide entre 5 KB y 30 KB y que su lado mayor es 320 px».
- **Por qué no es medible tal cual:** el tamaño de un JPEG depende del **contenido**, no del codificador. Medido en esta máquina con `opencv-python-headless` 5.0.0.93, a 320 px de lado mayor:

  | Frame | calidad 70 | calidad 85 | calidad 90 | calidad 95 | calidad 100 |
  |---|---|---|---|---|---|
  | Representativo (degradé, formas, patente, ruido de sensor) | 3,96 KiB | 5,60 KiB | **7,49 KiB** | 11,89 KiB | 34,66 KiB |
  | Ruido puro (peor caso) | 8,42 KiB | 15,74 KiB | **21,31 KiB** | 32,75 KiB | 64,10 KiB |
  | Plano (pared de noche, lente tapado) | 1,55 KiB | 1,55 KiB | **1,55 KiB** | 1,55 KiB | 1,55 KiB |

  Un frame uniforme mide 1,55 KiB **a cualquier calidad**: no hay información que codificar. Exigir 5 KiB para cualquier frame sería exigir que el codificador invente bytes.
- **Medición defendible que se implementó:** calidad **90**, que es la que deja dentro de la banda de 5 a 30 KiB tanto el frame representativo como el peor caso de ruido (a 95 el ruido se va a 32,7 KiB, fuera de la banda). Las pruebas afirman la banda sobre tres imágenes representativas distintas y sobre el ruido; el lado mayor de 320 px y la proporción se afirman siempre.
- **El límite queda escrito, no escondido:** `test_un_frame_plano_queda_por_debajo_de_la_banda` afirma explícitamente que un frame plano mide menos de 5 KiB. Esconderlo eligiendo sólo imágenes convenientes habría dejado una compuerta que pasa y una propiedad que no existe.
- **Qué se pide ratificar:** que el criterio se lea como «con detalle de imagen real, la miniatura entra en 5–30 KiB», y no como una garantía para cualquier entrada.

*(Separada a propósito de las tres sustituciones que ya esperan ratificación de fases anteriores.)*

### Corregidas automáticamente

**2. [Rule 2 - Funcionalidad crítica faltante] La cuarentena podía eliminar evidencia sin llamar a ninguna función de borrado**

- **Encontrado en:** Tarea 3.
- **Problema:** el plan especifica mover el huérfano a `cuarentena/AAAA-MM-DD/` «conservando el nombre original», con `os.replace`. Pero el nombre es el hash del contenido, así que dos huérfanos con bytes idénticos guardados en fechas distintas tienen **el mismo nombre**, y `os.replace` sobre un destino existente lo sobrescribe: el segundo movimiento habría eliminado al primero. La invariante de cero `unlink`/`rmtree`/`remove` habría seguido en verde mientras se perdía evidencia.
- **Arreglo:** `_nombre_libre` busca un sufijo numérico antes de mover. Prueba de regresión `test_dos_huerfanos_con_el_mismo_nombre_no_se_pisan`, que afirma que los dos contenidos sobreviven en destinos distintos.
- **Commiteado en:** `a3fecdc`.

**3. [Rule 1 - Defecto] El doble roto de la anti-vacuidad comparaba contra la huella equivocada**

- **Encontrado en:** Tarea 2, al correr la prueba por primera vez.
- **Problema:** el verificador truncado —que hashea sólo el primer bloque para demostrar por qué hacen falta tres posiciones— comparaba su resultado contra la huella del archivo **entero**, así que devolvía `COMPROMETIDA` siempre y no demostraba nada. El defecto estaba en mi prueba, no en el producto: un sistema con la lectura truncada lo estaría también en la ingesta.
- **Arreglo:** el doble compara contra `sha256(CONTENIDO[:64 KiB])`, que es lo que un sistema así habría persistido. Ahora el argumento queda completo y es el que justifica la parametrización: el verificador truncado **sí** detecta el primer byte y **no** detecta el último.
- **Commiteado en:** `e45bf9d`.

**4. [Rule 3 - Corrección de dato] El sufijo de la ruta mide 79 caracteres, no 89**

- **Encontrado en:** Tarea 1.
- **Problema:** el plan afirma que «el sufijo `AAAA/MM/DD/<64hex>.jpg` mide 89 caracteres verificados» y deriva de ahí el tope de 170 (259 − 89). Medido: mide **79**. Los 89 corresponden a `evidencia/AAAA/MM/DD/<64hex>.jpg`, o sea incluyendo el componente `evidencia/` de la organización canónica de D-03.
- **Arreglo:** se conserva el tope de **170**, que es el conservador y el que ya validaba el plan 01-06 — bajar el número habría sido un cambio de contrato sin ganancia. Lo que se corrigió es la explicación: el encabezado de `evidencia_fs.py` dice que el sufijo medido es 79 y que el tope deja además margen para el componente `evidencia/`.
- **Commiteado en:** `f170270`.

**5. [Rule 3 - Bloqueo] `ruta_para_el_sistema` tuvo que pasar de privada a pública**

- **Encontrado en:** Tarea 3.
- **Problema:** el sufijo de la cuarentena, `cuarentena/AAAA-MM-DD/<64hex>.jpg`, mide **90** caracteres: once más que el de la evidencia. O sea que la cuarentena es la primera en toparse con MAX_PATH, y sin el prefijo extendido una raíz cerca del tope produciría un fallo de movimiento justo cuando se está tratando de rescatar un huérfano.
- **Arreglo:** el ayudante pasa a ser público y lo comparten los dos módulos. Único cambio sobre un archivo ya commiteado dentro de este mismo plan.
- **Commiteado en:** `a3fecdc`.

---

**Total:** 1 sustitución de criterio reportada + 4 correcciones automáticas. Ninguna amplía el alcance del plan.

## Issues Encountered

- **Dos docstrings con rutas de Windows rompieron la importación del módulo.** `\\?\` y `\\?\UNC\` dentro de un docstring normal son secuencias de escape: `\U` disparó `SyntaxError: truncated \UXXXXXXXX escape`. Se resolvió con docstrings crudos (`r"""`), que además hacen que el prefijo se lea tal cual es. Es exactamente la clase de detalle que sólo aparece escribiendo sobre la plataforma real.
- **El monkeypatch de `os.fsync` y `os.replace` para inyectar el fallo se aplica sobre el módulo `os` real.** Se deshace explícitamente con `monkeypatch.undo()` antes de las aserciones, para que la comprobación de que no quedó ningún `.tmp` no corra con el sistema de archivos parcheado.

## Known Stubs

Ninguno. `describir` devuelve el códec de origen que se le inyectó al construir el codificador —«desconocido» si nadie lo pasó—, y eso no es un stub sino el modelado correcto: el códec es una propiedad de la fuente y no del cuadro. El plan 01-07 lo toma de las métricas de la fuente.

## Threat Flags

Ninguna superficie nueva fuera del registro del plan. Las seis amenazas con disposición `mitigate` quedan cubiertas y verificables:

| Amenaza | Estado | Verificable con |
|---|---|---|
| T-01-01 (manipulación de evidencia) | mitigada, con el límite tamper-evident declarado en el puerto | `test_manipulacion_evidencia.py` — 3 posiciones + control + truncamiento + reemplazo |
| T-01-02 (path traversal) | mitigada | `test_ruta_evidencia_hostil.py` — 6 vectores × escritura y lectura, sin tocar el disco |
| T-01-08 (temporales acumulados por disco lleno) | mitigada | `test_un_fallo_en_la_escritura_no_deja_temporal_ni_archivo_final`, en `fsync` y en `replace` |
| T-01-17 (MAX_PATH en la raíz configurable) | mitigada | `test_una_raiz_demasiado_larga_se_rechaza_al_construir_el_almacen`, con los dos números |
| T-01-18 (cuarentena que elimina) | mitigada, y reforzada | invariante de cero `unlink`/`rmtree`/`remove` **más** la prueba de homónimos, que es el agujero que la invariante sola no cerraba |
| T-01-06 (permisos del directorio de evidencia) | **parcial, como declara el plan** | `esta_disponible()` reporta si la raíz está y es escribible; la ACL y el diagnóstico completo son de la Fase 11 |

## User Setup Required

Ninguno. Queda anotado para la Fase 11, como recomendación de despliegue y no como requisito: activar `LongPathsEnabled` en el equipo de portería elimina de raíz la clase de fallos de MAX_PATH que hoy se contiene con la validación de los 170 caracteres y el prefijo extendido.

## Next Phase Readiness

- **01-05 (esquema y migraciones)** — el contrato de contenido duplicado está implementado y probado tal como lo acordaron los dos planes: `ruta_relativa` **sin** UNIQUE, índice no único `ix_item_evidencia_ruta_relativa`, y la unicidad real en `uq_item_evidencia_captura_id_camara_id`. La miniatura ya viene como `bytes` lista para la columna blob.
- **01-07 (rebanada vertical)** — tiene los dos puertos para inyectar, `esta_disponible()` para el modo degradado de D-07, `barrer_en_segundo_plano` para agendar al arrancar, y `guardar` como paso 1 del orden archivo-primero de D-12. La calidad por cámara viaja como argumento, lista para la clave `calidad_jpeg_por_camara` de la capa 2.
- **Fase 3 (retención y espacio)** — `barrer_huerfanos` devuelve los bytes ocupados por cada archivo apartado, que es el dato que el aviso por umbral de espacio libre (EVI-10) necesita.

**Sin bloqueos.** Sigue abierta, de 01-01 y sin relación con este plan, la tarea de protección de rama en GitHub.

## Self-Check: PASSED

- 11 archivos declarados como creados: los 11 existen en el árbol.
- 5 hashes de commit declarados (`4c8bef9`, `f170270`, `e45bf9d`, `6b426c4`, `a3fecdc`): los 5 existen en `git log`.
- `uv run python scripts/compuerta.py` → **COMPUERTA EN VERDE**, los cuatro pasos, exit 0, 447 pruebas ejecutadas, 36 dependencias auditadas.
- `uv run pytest -q -m "not lenta"` → 446 pruebas en verde, 1 xfail esperado.
- `uv run lint-imports --no-cache` → 4 contratos intactos, 0 rotos, con `numpy` y `cv2` presentes en infraestructura.
- `uv run ruff check .` → sin hallazgos.
- Los tres comportamientos de Windows del plan, reproducidos de primera mano antes de implementar.

---
*Phase: 01-n-cleo-evidencia-trazable-y-contratos-externos-congelados*
*Completed: 2026-07-31*
