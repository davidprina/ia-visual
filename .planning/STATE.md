---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: planning
last_updated: "2026-07-25T22:05:13.212Z"
last_activity: 2026-07-25 — ROADMAP.md creado con 12 fases y 79/79 requerimientos v1 mapeados
progress:
  total_phases: 12
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

Ver: .planning/PROJECT.md (actualizado 2026-07-24)

**Core value:** Que la captura de evidencia visual sea confiable, sincronizada y trazable: cuando el portero presiona el botón, el sistema obtiene sí o sí las fotos de todas las cámaras del mismo instante, asociadas al vehículo correcto, y las guarda de forma auditable.
**Current focus:** Fase 1 — Núcleo, evidencia trazable y contratos externos congelados

## Current Position

Phase: 1 de 12 (Núcleo, evidencia trazable y contratos externos congelados)
Plan: 0 de TBD en la fase actual
Status: Ready to plan
Last activity: 2026-07-25 — ROADMAP.md creado con 12 fases y 79/79 requerimientos v1 mapeados

Progress: [░░░░░░░░░░] 0%

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

## Accumulated Context

### Decisions

Las decisiones se registran en la tabla Key Decisions de PROJECT.md.
Decisiones recientes que afectan el trabajo actual:

- [Roadmap]: Doce fases en rebanadas verticales; cada una entrega una capacidad probable de punta a punta, no una capa técnica.
- [Roadmap]: La Fase 1 absorbe todo lo que no es retrofiteable (huella SHA-256 en ingesta, Viaje↔Remito N:M, peso teórico nulo, contrato de frescura del frame, reloj único y desvío, escritura atómica) más el descubrimiento de los contratos de PALJET y balanza con un GET real.
- [Roadmap]: El certificado de firma de código se compra a partir de la Fase 4, junto con un instalador de humo probado en VM limpia. Es plazo administrativo bloqueante.
- [Roadmap]: El motor de visión clásica (VIS-07, VIS-08) queda en la Fase 12, la última de v1. La abstracción de motor se diseña en la Fase 4.
- [Investigación]: Ultralytics YOLO prohibido (AGPL-3.0). Detector: RF-DETR-Nano/Small sobre ONNX Runtime.

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

Última sesión: 2026-07-25
Se detuvo en: ROADMAP.md y STATE.md creados; traceability de REQUIREMENTS.md actualizada
Archivo de reanudación: Ninguno
