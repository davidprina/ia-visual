# Cómo continuar la Fase 01

> Documento de traspaso. Escrito por adelantado porque el límite de sesión viene cortando
> a los ejecutores a mitad de plan y no hay forma de anticiparlo desde adentro.
> **Este archivo es una foto, no la verdad.** La verdad está en git y en los SUMMARY.
> Empezá siempre por el bloque "Verificar el estado real".

---

## Verificar el estado real (hacer esto primero, siempre)

```bash
cd "C:\Users\Hogar\Documents\Deesarrollo\.PROYECTO PAGOS\IA visual"
git log --oneline -10
git status --porcelain
ls .planning/phases/01-*/ | grep SUMMARY
```

Regla de lectura:

- **Un plan está completo** si existe su `01-0N-SUMMARY.md`. Nada más cuenta como completo.
- **Un plan está a medias** si tiene commits (`git log --grep="01-0N"`) pero no tiene SUMMARY.
- Archivos sin commitear bajo `src/` o `tests/` son trabajo a medias de un ejecutor cortado.
- `.planning/config.json` modificado y `.planning/research/.cache/` sin versionar son **preexistentes**. Dejalos así.

---

## Retomar la ejecución

En una sesión nueva, después de `/clear`:

```
/gsd-execute-phase 1
```

El flujo descubre los SUMMARY en disco, saltea los planes completos y arranca desde el
primer plan incompleto. No hace falta indicarle nada más.

### Si se traba en la compuerta de reanudación segura

Va a pasar cuando un plan tenga commits pero no tenga SUMMARY — que es exactamente lo que
deja un corte por límite de sesión. El flujo se detiene y ofrece tres caminos.
**La respuesta correcta casi siempre es `close out manually`... salvo una excepción
importante:** si el ejecutor original todavía figura como agente reanudable en esa sesión,
retomarlo con su contexto intacto es mejor que empezar de cero, porque ya conoce las
decisiones que tomó. Entre sesiones distintas eso se pierde y hay que ir por
`re-execute from scratch` sobre las tareas que quedaron sin commitear.

Nunca elijas `mark-and-skip` acá: marcaría un plan como hecho sin estarlo.

---

## Modo de ejecución fijado para esta fase

| Ajuste | Valor | Por qué |
|--------|-------|---------|
| Worktrees | **desactivados** | El repo no tiene remoto, `origin/HEAD` no resuelve y GSD degrada solo |
| Paralelismo | **secuencial** | Consecuencia de lo anterior: un ejecutor por vez sobre el árbol principal |
| Branching | `none` | Todo va sobre `main` |
| Commits | con hooks | Nunca `--no-verify` |
| Idioma | español | D-32 — código, comentarios, commits y documentos |

Elegido a conciencia. Si alguna vez querés volver a worktrees en paralelo, hay que darle
un remoto al repo o setear `worktree.baseRef:"head"` en `.claude/settings.local.json`.

---

## La compuerta

```bash
uv run python scripts/compuerta.py    # tiene que salir con exit 0
uv run ruff check .
```

Encadena cuatro pasos y propaga el peor código de salida. Ningún plan puede cerrarse
dejándola en rojo. `tests/aceptacion/test_rebanada_captura.py` está en `xfail` **a
propósito** hasta el plan 01-07 — no es un fallo.

---

## Estado de los planes

Foto al momento de escribir esto. Reconfirmar con el bloque de arriba.

| Plan | Wave | Estado |
|------|------|--------|
| 01-01 | 1 | Tareas 1-3 commiteadas, compuerta en verde. **Tarea 4 bloqueada** (ver abajo) |
| 01-02 | 2 | Completo — 7 commits, SUMMARY en disco. Cierra NUC-01, EVI-05, VIA-05 |
| 01-03 | 2 | Completo — 6 commits, SUMMARY en disco |
| 01-04 | 3 | Completo — 6 commits, SUMMARY en disco. Cierra EVI-05 |
| 01-05 | 3 | Pendiente |
| 01-06 | 2 | Completo — 7 commits, SUMMARY en disco. Cierra NUC-06, D-30 |
| 01-07 | 4 | Pendiente |
| 01-08 | 4 | Pendiente |
| 01-09 | 5 | Pendiente |
| 01-10 | 5 | Pendiente |

Orden de waves: `1` → `2` (01-02, 01-03, 01-06) → `3` (01-04, 01-05) → `4` (01-07, 01-08) → `5` (01-09, 01-10).

**Wave 2 cerrada.** Compuerta corrida de forma independiente por el orquestador al cerrarla:
exit 0, 366 pruebas, 4 contratos, 17 módulos de dominio, 36 dependencias auditadas.
Siguiente: wave 3 (01-04, 01-05).

---

## Pendientes que dependen de vos

### 1. Protección de rama — cierra la Tarea 4 de 01-01

El plan pide que la compuerta en rojo bloquee la fusión. Eso es configuración de GitHub,
no código, y **el repo hoy no tiene remoto**. Lo automatizable ya está entregado:
`scripts/compuerta.py` y `.github/workflows/compuerta.yml` sobre `windows-latest`.

```bash
# 1. Crear el repo en github.com/new (decidí público o privado a conciencia)
git remote add origin https://github.com/<usuario>/<repo>.git
git push -u origin main
```

3. `Settings → Branches → Add branch protection rule`, patrón `main`
4. **Require status checks to pass before merging** → marcar **sólo** `compuerta (rapida, bloqueante)`
5. **No** marcar `tanda lenta (agendada, no bloqueante)` — D-53 es explícito
6. Comprobarlo de verdad: rama con `import cv2` dentro de `src/porteria/dominio/`, abrir el
   PR, confirmar que el botón de fusión queda bloqueado, cerrar sin fusionar

Después pasá **el nombre exacto del check requerido** y la lista completa de checks
obligatorios, para cerrar 01-01 con su SUMMARY.

> Nota: crear el repo por API es un `POST`, y tu regla global prohíbe métodos de escritura
> contra APIs externas sin excepción. Por eso este paso queda de tu lado, no del mío.

### 2. Ratificar cuatro criterios de aceptación sustituidos

Los ejecutores **reemplazaron criterios escritos en los planes**. En los tres casos el
criterio original era inmedible o contraproducente, y en los tres la sustitución agrega
verificación en vez de aflojarla. Aun así son cambios a la especificación y la decisión
de aceptarlos es tuya. Si rechazás alguno, hay que replanificarlo **antes** de que la fase
se verifique.

**a) 01-02 — el reloj no puede dar 100/100 lecturas distintas**

- **El plan pedía:** dos llamadas consecutivas a `RelojDelProceso().instante()` dan valores
  distintos, 100 de 100 veces.
- **Lo medido:** 7 de 100 pares coinciden. No por un defecto del reloj sino por lo
  contrario — `QueryPerformanceCounter` tiene paso de 100 ns y dos llamadas de CPython
  entran en un mismo tick. Tomado literal, el criterio sólo se cumpliría con un reloj *peor*.
- **Lo que quedó:** >50.000 instantes distintos en 100 ms (contra los ~7 que daría
  `monotonic`), más 100/100 con trabajo real intercalado, sin esperar consultando el propio
  reloj, que sería circular.

**b) 01-03 — «ninguna llamada a `publicar` tarda más de 1 ms» medía el planificador**

- **Lo medido:** falló 3 de 3, con máximos de 4,358 ms, **con el slot funcionando bien**.
  `sys.getswitchinterval()` es de 5 ms y el productor puede quedar demorado un intervalo
  completo aunque el lock esté libre.
- **Lo que quedó:** mediana < 1 ms (medido 0,0158 — 60× de margen), p99 < 1 ms
  (0,042–0,101) y máximo < 5 × el intervalo de conmutación, derivado de la plataforma.
  Además agregó una contraprueba que el plan no pedía: la misma medición contra
  `queue.Queue(maxsize=1)` da mediana 195,01 ms y 16 publicaciones en 3 s contra 557 del
  slot, y la prueba **exige que falle**.

**c) 01-03 — «al terminar el archivo `tomar_mas_reciente` devuelve `None`» tiraba evidencia**

- **El problema:** terminado el archivo, el último cuadro publicado sigue en el slot.
  Cumplir el criterio literal significaba descartarlo — perder un cuadro válido justo en
  el borde.
- **Lo que quedó:** el contrato se precisó a lo que garantiza de verdad — la fuente se
  vacía y no se repone. La prueba afirma tres propiedades donde el plan pedía una.

**d) 01-04 — el piso de 5 KB de la miniatura no es alcanzable para cualquier frame**

- **El problema:** el tamaño de un JPEG lo fija el contenido, no el codificador. Medido a
  320 px de lado mayor: un frame plano (pared de noche, lente tapado) pesa 1,55 KiB a
  cualquier calidad, porque no hay información que codificar.
- **Lo que quedó:** calidad 90, la única que deja dentro de la banda de 5–30 KiB tanto la
  imagen representativa (7,49 KiB) como el peor caso de ruido puro (21,31 KiB; a calidad
  95 se iría a 32,75 KiB). El límite quedó **escrito como prueba**
  (`test_un_frame_plano_queda_por_debajo_de_la_banda`) en vez de esconderse eligiendo sólo
  imágenes convenientes.

---

## Después de que cierren los diez planes

El flujo corre solo estas compuertas, en orden: revisión de código, regresión de fases
previas, deriva de esquema, y verificación del objetivo de fase contra el código real.
La fase **no** se marca completa si `01-01` sigue abierto por la Tarea 4.

---

## Qué NO hacer

- No crear `01-01-SUMMARY.md` a mano para "destrabar" la fase. Marca como hecho algo que no lo está.
- No tocar `tests/aceptacion/test_rebanada_captura.py` para sacarle el `xfail` antes de 01-07.
- No commitear `.planning/research/.cache/`.
- No usar `--no-verify` para saltear hooks.
