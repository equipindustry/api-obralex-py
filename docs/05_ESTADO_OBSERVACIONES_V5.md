# Estado de Observaciones — Plan de Simplificacion V5

Fecha: 2026-03-22
Referencia: `04_ESTADO_OBSERVACIONES_V4.md`

---

## Tabla resumen

| #   | Observacion                                              | Estado       | Proyecto responsable              | Notas                                                                                                                                    |
| --- | -------------------------------------------------------- | ------------ | --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Validacion de atributos del LLM vs opciones del catalogo | **Resuelto** | **api-obralex-py**                | `_normalize_choice_value()` implementado: match case-insensitive para campos `type: "choice"`, valores invalidos se tratan como missing  |
| 2   | Duplicados en opciones de color                          | **Resuelto** | **api-adatrack-py**               | `build_field_options()` agrupa por lowercase y conserva variante mas frecuente. Schema v3 subido a GCS                                   |
| 3   | Edge cases conversacionales (Fase 2)                     | **Resuelto** | **api-maia**                      | Casos documentados en `05_CASOS_CONVERSACIONALES_AGENTE.md`                                                                              |
| 4   | match_id y precision del match                           | **Resuelto** | **api-obralex-py**                | `_validate_match()` implementado: compara atributos del LLM vs inventario Vertex. Si no coinciden → `status: "review"`, `match_id: null` |
| 5   | Escalabilidad del catalogo en el prompt                  | Parcial      | **api-obralex-py** + **api-maia** | Con 8 subcategorias no es problema. Monitorear cuando crezca                                                                             |
| 6   | Campo `unit` — normalizacion                             | **Resuelto** | **api-adatrack-py**               | `unit_catalog.py` + `build_unit_options()`. Schema v2+ incluye `unit_options` por subcategoria                                           |
| 7   | Status "detected" — siguiente paso                       | Pendiente    | **Producto/UX**                   | Decision de negocio pendiente                                                                                                            |

---

## Cambios respecto a V4

### Observacion #1 — Validacion case-insensitive: Pendiente → **Resuelto**

**Problema:** `_analyze_one()` aceptaba cualquier valor del LLM sin validar contra las opciones del schema. Si el LLM enviaba `"negro"` pero la opcion canonica era `"Negro"`, se aceptaba tal cual sin normalizar.

**Fix aplicado en `src/services/material_analyzer.py`:**

Nuevo metodo `_normalize_choice_value()`:

```python
def _normalize_choice_value(self, value, field_options, field_name):
    # Para campos type: "choice", busca match exacto primero,
    # luego case-insensitive. Retorna la opcion canonica del schema.
    # Si no matchea ninguna opcion, retorna None (se trata como missing).
    # Para campos type: "text", retorna el valor tal cual.
```

**Comportamiento:**

- `color: "negro"` → normalizado a `"Negro"` (opcion canonica del schema)
- `color: "NEGRO"` → normalizado a `"Negro"`
- `color: "verde"` → `None` (no existe en opciones, se marca como missing)
- `measure: "1/2"` → `"1/2"` (campo tipo text, se acepta tal cual)

### Observacion #4 — Validacion post-match: Pendiente → **Resuelto**

**Problema:** El `match_id` se asignaba automaticamente cuando `status == "complete"`, sin verificar que el inventario retornado por Vertex AI Search realmente coincidiera con los atributos del usuario. Si el usuario pedia "cable rojo" pero Vertex retornaba un cable azul, el `match_id` seria incorrecto.

**Fix aplicado en `src/services/material_analyzer.py`:**

Nuevo metodo `_validate_match()`:

```python
def _validate_match(self, inventory, user_attrs, required_fields):
    # Compara cada atributo del usuario contra el inventario.
    # Usa "in" case-insensitive (ej: "1/2" matchea "1/2\" x 9 mts").
    # Retorna False si algun atributo contradice al inventario.
```

**Nuevo status `"review"`:**

Cuando los atributos estan completos pero el inventario de Vertex no coincide:

```json
{
  "status": "review",
  "match_id": null,
  "completion_percentage": 100.0,
  "missing_attributes": []
}
```

**Los 4 status posibles ahora son:**

| Status       | Significado                                                        | match_id |
| ------------ | ------------------------------------------------------------------ | -------- |
| `detected`   | Sin schema (categoria no cubierta)                                 | null     |
| `incomplete` | Faltan atributos requeridos                                        | null     |
| `complete`   | Atributos completos + inventario Vertex coincide                   | asignado |
| `review`     | Atributos completos pero inventario Vertex no coincide exactamente | null     |

---

## Resumen de progreso

| Estado       | Cantidad | Observaciones      |
| ------------ | -------- | ------------------ |
| **Resuelto** | 5        | #1, #2, #3, #4, #6 |
| Parcial      | 1        | #5                 |
| Pendiente    | 1        | #7                 |

---

## Pendientes por proyecto

### api-obralex-py

| #   | Accion                                                | Prioridad | Archivo                            |
| --- | ----------------------------------------------------- | --------- | ---------------------------------- |
| 5   | Filtro por categoria en `/schemas/catalog` (a futuro) | Baja      | `src/services/inventory_schema.py` |

### api-maia

| #   | Accion                           | Prioridad | Notas                                       |
| --- | -------------------------------- | --------- | ------------------------------------------- |
| 5   | Cache de respuestas de tools MCP | Baja      | Solo relevante a escala (30+ subcategorias) |

### Producto/UX

| #   | Accion                                                 | Prioridad | Notas                                               |
| --- | ------------------------------------------------------ | --------- | --------------------------------------------------- |
| 7   | Definir flujo para materiales con `status: "detected"` | Media     | Que pasa con materiales sin schema en la cotizacion |
