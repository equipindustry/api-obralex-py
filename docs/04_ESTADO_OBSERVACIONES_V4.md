# Estado de Observaciones — Plan de Simplificacion V4

Fecha: 2026-03-22
Referencia: `04_OBSERVACIONES_PLAN_SIMPLIFICACION.md`, `08_ESTADO_OBSERVACIONES_V3.md`

---

## Tabla resumen

| #   | Observacion                                              | Estado       | Proyecto responsable              | Notas                                                                                                           |
| --- | -------------------------------------------------------- | ------------ | --------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| 1   | Validacion de atributos del LLM vs opciones del catalogo | Pendiente    | **api-obralex-py**                | Implementar match case-insensitive en `material_analyzer.py` para campos `type: "choice"`                       |
| 2   | Duplicados en opciones de color                          | **Resuelto** | **api-adatrack-py**               | `build_field_options()` ahora agrupa por lowercase y conserva la variante mas frecuente. Schema v3 subido a GCS |
| 3   | Edge cases conversacionales (Fase 2)                     | **Resuelto** | **api-maia**                      | Casos documentados en `05_CASOS_CONVERSACIONALES_AGENTE.md`                                                     |
| 4   | match_id y precision del match                           | Pendiente    | **api-obralex-py**                | Validacion post-match: comparar atributos LLM vs inventario Vertex                                              |
| 5   | Escalabilidad del catalogo en el prompt                  | Parcial      | **api-obralex-py** + **api-maia** | Con 8 subcategorias no es problema. Monitorear cuando crezca                                                    |
| 6   | Campo `unit` — normalizacion                             | **Resuelto** | **api-adatrack-py**               | `unit_catalog.py` + `build_unit_options()`. Schema v2+ incluye `unit_options` por subcategoria                  |
| 7   | Status "detected" — siguiente paso                       | Pendiente    | **Producto/UX**                   | Decision de negocio pendiente                                                                                   |

---

## Cambios respecto a V3

### Observacion #2 — Duplicados de color: Pendiente → **Resuelto**

**Problema:** En Cables, `field_options.color` contenia duplicados con diferente case: "NEGRO"/"Negro" (17 vs 173) y "ROJO"/"Rojo" (1 vs 97).

**Fix aplicado en `scripts/02_generate_schemas.py`:**

`build_field_options()` ahora agrupa valores por `lower()` y conserva la variante con mayor frecuencia en la data:

```python
# Antes: tomaba todos los valores unicos tal cual
clean = sorted({str(v).strip() for v in values.unique()})

# Despues: agrupa por lowercase, conserva el mas frecuente
raw = [str(v).strip() for v in values if v and str(v).strip()]
freq = Counter(raw)
by_lower = {}
for val in freq:
    key = val.lower()
    if key not in by_lower or freq[val] > freq[by_lower[key]]:
        by_lower[key] = val
clean = sorted(by_lower.values())
```

**Resultado:** "NEGRO" se fusiono en "Negro", "ROJO" se fusiono en "Rojo". El fix es generico — si aparecen mas duplicados de case en el futuro, se resuelven automaticamente.

**Schema regenerado:** `inventory_schemas_sanitized_22_mar_2026_v3.json`, subido a GCS.

---

## Resumen de progreso

| Estado       | Cantidad | Observaciones |
| ------------ | -------- | ------------- |
| **Resuelto** | 3        | #2, #3, #6    |
| Parcial      | 1        | #5            |
| Pendiente    | 3        | #1, #4, #7    |

---

## Pendientes por proyecto

### api-obralex-py

| #   | Accion                                                             | Prioridad | Archivo                             |
| --- | ------------------------------------------------------------------ | --------- | ----------------------------------- |
| 1   | Match case-insensitive para campos choice en `_analyze_one()`      | Media     | `src/services/material_analyzer.py` |
| 4   | Validacion post-match: comparar atributos LLM vs inventario Vertex | Alta      | `src/services/material_analyzer.py` |
| 5   | Filtro por categoria en `/schemas/catalog` (a futuro)              | Baja      | `src/services/inventory_schema.py`  |

### api-maia

| #   | Accion                           | Prioridad | Notas                                       |
| --- | -------------------------------- | --------- | ------------------------------------------- |
| 5   | Cache de respuestas de tools MCP | Baja      | Solo relevante a escala (30+ subcategorias) |

### Producto/UX

| #   | Accion                                                 | Prioridad | Notas                                               |
| --- | ------------------------------------------------------ | --------- | --------------------------------------------------- |
| 7   | Definir flujo para materiales con `status: "detected"` | Media     | Que pasa con materiales sin schema en la cotizacion |
