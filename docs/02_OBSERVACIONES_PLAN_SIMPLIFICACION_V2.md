# Observaciones al Plan de Simplificacion del Agente (V2)

Fecha: 2026-03-22 (actualizado post-implementacion Fase 2)
Documento revisado: `10_PLAN_AGENT_SIMPLIFICATION_V2.md`

---

## 1. Validacion de atributos del LLM vs opciones del catalogo

**Estado:** Parcialmente mitigado

El prompt de `ANALYZE_SYSTEM_INSTRUCTION` ahora instruye a Gemini a mapear valores del usuario a las opciones validas del catalogo (`get_schemas_catalog`). Esto reduce la probabilidad de valores incorrectos.

**Pendiente (api-obralex-py):** Definir que hace `analyze_materials` cuando recibe un valor que no coincide exactamente con las opciones del schema:

- Acepta tal cual (actual)
- Rechaza y lo marca como missing
- Fuzzy matching ligero (lowercase + strip + case-insensitive)

**Recomendacion:** Implementar match case-insensitive en api-obralex-py para campos `type: "choice"`.

---

## 2. Duplicados en opciones de color

**Estado:** Vigente (api-obralex-py)

En el schema actual de Cables, `color` tiene opciones duplicadas con diferente case (`"NEGRO"` y `"Negro"`). Se deberia normalizar en el schema o en `generate_schemas.py` de api-obralex-py.

---

## 3. Fase 2 (api-maia) — Edge cases conversacionales

**Estado:** Implementacion completada, edge cases cubiertos por reglas del prompt

Cambios implementados:
- `DetectedMaterial` ahora incluye `attributes: dict[str, str]`
- Prompt actualizado con flujo de analisis: `get_attribute_fields` + `get_schemas_catalog` + cruce + extraccion
- Campo `original` inyectado desde `detection.materials[]` antes de enviar al MCP (fix del bug de "fierro corrugado" para todos)

Las reglas del prompt cubren los edge cases:
- **Acumulacion**: "SIEMPRE acumula materiales de mensajes anteriores"
- **Actualizacion parcial**: "Si el mensaje actual actualiza informacion de un material existente, ACTUALIZA en ambas listas"
- **No eliminar**: "NUNCA elimines materiales previamente detectados a menos que el cliente lo pida"

**Pendiente:** No hay tests conversacionales formales para validar estos edge cases de forma automatizada.

---

## 4. match_id y precision del match

**Estado:** Vigente (api-obralex-py)

El `match_id` viene del resultado de Vertex AI Search (match semantico). Si el inventario no tiene el item exacto, Vertex retorna el mas cercano, lo cual puede no coincidir con los atributos del usuario.

**Recomendacion:** Validacion post-match en api-obralex-py que verifique coincidencia de atributos entre el inventario retornado y los atributos enviados por el LLM.

---

## 5. Escalabilidad del catalogo en el prompt

**Estado:** Parcialmente mitigado

El prompt indica que los pasos 1 y 2 (get_attribute_fields, get_schemas_catalog) "se pueden omitir si ya los llamaste en esta conversacion". Sin embargo, esto depende de que Gemini decida no re-llamarlos — no hay un cache a nivel de backend para las respuestas de estas herramientas.

Con 3 subcategorias actuales no es problema. A escala (30+ subcategorias), considerar:
- Filtro por categoria en `get_schemas_catalog`
- Cache de respuestas en api-maia (no solo cache de tools MCP)
- Flujo en 2 pasos: detectar descripcion primero, luego pedir schema de la subcategoria relevante

---

## 6. Campo `unit` — normalizacion

**Estado:** Vigente

No existe un catalogo de unidades validas. El LLM normaliza libremente ("rollos", "rll", "rollo" -> ?). Si `unit` se usa downstream para calculo de precios o logistica, considerar definir una lista de unidades aceptadas.

---

## 7. Status "detected" — siguiente paso no definido

**Estado:** Vigente

Materiales con `schema_source: "default"` y `status: "detected"` se persisten pero no queda definido el flujo para el usuario/asesor:
- Se incluyen en la cotizacion con datos minimos?
- Se marcan como "pendiente de clasificacion"?
- El asesor debe buscarlos manualmente?

**Recomendacion:** Definir UX para materiales "detected" en el frontend (ej. badge gris con tooltip "Material fuera de inventario — consultar con proveedor externo").
