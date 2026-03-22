# Estado de Observaciones — Plan de Simplificacion V2

Fecha: 2026-03-22
Referencia: `02_OBSERVACIONES_PLAN_SIMPLIFICACION_V2.md`

---

## Tabla resumen

| # | Observacion | Resuelto | Proyecto responsable | Notas |
|---|------------|----------|---------------------|-------|
| 1 | Validacion de atributos del LLM vs opciones del catalogo | Pendiente | **api-obralex-py** | Implementar match case-insensitive en `material_analyzer.py` para campos `type: "choice"`. Actualmente acepta cualquier valor sin validar contra `field_options` |
| 2 | Duplicados en opciones de color | Pendiente | **api-adatrack-py** (`scripts/`) | El script de generacion de schemas debe normalizar valores (lowercase/titlecase) antes de generar `field_options`. No es responsabilidad de api-obralex-py |
| 3 | Edge cases conversacionales (Fase 2) | Resuelto | **api-maia** | `DetectedMaterial` incluye `attributes`, prompt cubre acumulacion/actualizacion/no-eliminar. Falta: tests conversacionales automatizados |
| 4 | match_id y precision del match | Pendiente | **api-obralex-py** | Agregar validacion post-match: comparar atributos del LLM contra atributos del inventario retornado por Vertex. Si no coinciden, no asignar `match_id` |
| 5 | Escalabilidad del catalogo en el prompt | Parcial | **api-obralex-py** + **api-maia** | Con 3 subcategorias no es problema. A futuro: filtro por categoria en `/schemas/catalog` (api-obralex-py) y cache de tools en api-maia |
| 6 | Campo `unit` — normalizacion | Pendiente | **api-obralex-py** o **api-maia** | Definir catalogo de unidades validas. Puede ser un endpoint similar a `/materials/attribute-fields` o normalizacion en el prompt del LLM |
| 7 | Status "detected" — siguiente paso | Pendiente | **Producto/UX** | Decision de negocio, no de backend. Definir que pasa con materiales sin schema en el flujo del asesor |

---

## Detalle por proyecto

### api-obralex-py (este proyecto)

| # | Accion | Prioridad | Archivo |
|---|--------|-----------|---------|
| 1 | Match case-insensitive para campos choice en `_analyze_one()` | Media | `src/services/material_analyzer.py` |
| 4 | Validacion post-match: comparar atributos LLM vs inventario Vertex | Alta | `src/services/material_analyzer.py` |
| 5 | Filtro por categoria en `/schemas/catalog` (a futuro) | Baja | `src/services/inventory_schema.py` |
| 6 | Endpoint de unidades validas (si se decide) | Baja | `src/api/materials.py` |

### api-adatrack-py

| # | Accion | Prioridad | Ubicacion |
|---|--------|-----------|-----------|
| 2 | Normalizar valores duplicados (case) al generar schemas | Media | `scripts/` (generacion de schemas) |

### api-maia

| # | Accion | Prioridad | Notas |
|---|--------|-----------|-------|
| 3 | Tests conversacionales automatizados | Baja | Edge cases ya cubiertos por reglas del prompt |
| 5 | Cache de respuestas de tools MCP | Baja | Solo relevante a escala (30+ subcategorias) |
| 6 | Normalizacion de `unit` en el prompt | Media | Alternativa a endpoint de unidades en api-obralex-py |

### Producto/UX

| # | Accion | Prioridad | Notas |
|---|--------|-----------|-------|
| 7 | Definir flujo para materiales con `status: "detected"` | Media | Badge, tooltip, derivacion a asesor, etc. |
