---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
last_updated: "2026-07-31T21:20:10.312Z"
last_activity: 2026-07-31
progress:
  total_phases: 12
  completed_phases: 0
  total_plans: 10
  completed_plans: 4
  percent: 0
---

# Project State

## Project Reference

Ver: .planning/PROJECT.md (actualizado 2026-07-24)

**Core value:** Que la captura de evidencia visual sea confiable, sincronizada y trazable: cuando el portero presiona el botón, el sistema obtiene sí o sí las fotos de todas las cámaras del mismo instante, asociadas al vehículo correcto, y las guarda de forma auditable.
**Current focus:** Phase 01 — n-cleo-evidencia-trazable-y-contratos-externos-congelados

## Current Position

Phase: 01 (n-cleo-evidencia-trazable-y-contratos-externos-congelados) — EXECUTING
Plan: 6 of 10
Status: Ready to execute
Last activity: 2026-07-31

Progress: [████░░░░░░] 40%

## Performance Metrics

**Velocity:**

- Planes completados: 0
- Duración promedio: —
- Tiempo total de ejecución: 0 h

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Últimos 5 planes: —
- Tendencia: —

*Se actualiza al completar cada plan*
| Phase 01 P02 | 41min | 3 tasks | 21 files |
| Phase 01 P03 | 76min | 3 tasks | 12 files |
| Phase 01 P06 | 312min | 3 tasks | 10 files |

## Accumulated Context

### Decisions

Las decisiones se registran en la tabla Key Decisions de PROJECT.md.
Decisiones recientes que afectan el trabajo actual:

- [Roadmap]: Doce fases en rebanadas verticales; cada una entrega una capacidad probable de punta a punta, no una capa técnica.
- [Roadmap]: La Fase 1 absorbe todo lo que no es retrofiteable (huella SHA-256 en ingesta, Viaje↔Remito N:M, peso teórico nulo, contrato de frescura del frame, reloj único y desvío, escritura atómica) más el descubrimiento de los contratos de PALJET y balanza con un GET real.
- [Roadmap]: El certificado de firma de código se compra a partir de la Fase 4, junto con un instalador de humo probado en VM limpia. Es plazo administrativo bloqueante.
- [Roadmap]: El motor de visión clásica (VIS-07, VIS-08) queda en la Fase 12, la última de v1. La abstracción de motor se diseña en la Fase 4.
- [Investigación]: Ultralytics YOLO prohibido (AGPL-3.0). Detector: RF-DETR-Nano/Small sobre ONNX Runtime.
- [Phase 01]: 01-02: la huella rechaza mayusculas en vez de normalizarlas; hexdigest() siempre da minusculas, asi que una mayuscula solo puede venir de una edicion a mano
- [Phase 01]: 01-02: el orden de hasheo del manifiesto se deriva de (camara_id, instante_monotono_ns), nunca del orden de insercion
- [Phase 01]: 01-02: Viaje y Remito son entidades con igualdad por identificador; la comparacion campo por campo recursaba por la relacion N:M
- [Phase ?]: El tope del maximo de publicar se deriva de sys.getswitchinterval() y no del 1 ms del plan: ese maximo lo acota el planificador de CPython, no el diseno del slot. Mediana y p99 conservan el milisegundo, con contraprueba contra queue.Queue (0,016 ms contra 195 ms)
- [Phase ?]: FrameSellado vive en el modulo del puerto y no en el adaptador: el contrato de capas prohibe que aplicacion importe de infraestructura, y TYPE_CHECKING no es salida porque exclude_type_checking_imports esta deliberadamente sin activar
- [Phase ?]: 01-06: la separacion entre bitacora tecnica y cadena de custodia es una invariante de codigo sobre el texto del modulo, no una convencion: el antipatron del logger con es_auditoria=True es imposible de escribir sin romper la compuerta
- [Phase ?]: 01-06: la cadena de procesadores de structlog corre una sola vez y los handlers solo eligen el formato; es lo que hace que el redactor de secretos no pueda ser esquivado por un destino agregado despues
- [Phase ?]: 01-06: ConfiguracionEnBase no es duena del esquema: recibe el Engine inyectado y declara COLUMNAS_REQUERIDAS como contrato con el plan 01-05, lo que permitio cerrar este plan sin depender de aquel
- [Phase ?]: 01-06: el largo de la raiz de evidencia se valida en el cargador antes de construir el modelo, porque pydantic envuelve todo error de validador en ValidationError y a la consola tiene que llegar el mensaje con el maximo y el largo elegido

### Pending Todos

Ninguno todavía.

### Blockers/Concerns

- **Contratos de integración sin leer.** La documentación de la API de PALJET y de la balanza existe y el usuario la tiene, pero todavía no se leyó ni se ejecutó un GET real. Es compuerta de salida de la Fase 1: sin eso, el modelo de datos se construye sobre supuestos.
- **Sin acceso ni documentación de Geomov.** La carga manual se diseña como camino principal (Fase 10); la API queda como segunda implementación del mismo puerto si aparece.
- **Hardware de cámaras sin definir.** No se puede confirmar píxeles sobre placa, GOP ni soporte RTCP para sincronía. Los números de PITFALLS.md se usan como insumo del pliego de compra, no como validación posterior.
- **Riesgo legal abierto en el detector de placa.** Los pesos de `open-image-models` derivan de YOLOv9 (GPL-3.0) aunque el código sea MIT. Sustitución agendada como bloqueante de la primera venta (Fase 5).
- **Datos de negocio faltantes:** volumen de camiones por día (dimensiona el almacenamiento) y política de retención de evidencia. Necesarios antes de la Fase 11.

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(ninguno)* | | | |

## Session Continuity

Última sesión: 2026-07-31
Se detuvo en: Completado 01-06-PLAN.md (bitácora técnica, redacción de secretos y configuración en dos capas). Compuerta en verde, 365 pruebas rápidas.
Archivo de reanudación: Ninguno

**Nota sobre la métrica de 01-06:** los 312 min son reloj de pared e incluyen un corte de
sesión del proveedor con la fase RED sin commitear. El trabajo efectivo es una fracción de
ese número; conviene descontarlo al mirar la velocidad promedio.
