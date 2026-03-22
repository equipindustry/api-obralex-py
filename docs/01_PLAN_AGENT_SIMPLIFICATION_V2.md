# Plan: Simplificacion del Agente — Deteccion vs Calculo

## Objetivo

Separar responsabilidades entre el agente (Gemini) y el servidor MCP:

- **Agente (api-maia)**: cerebro de deteccion — identifica materiales del mensaje del cliente
- **MCP Server (mcp-hub-equip)**: cerebro de calculo — enriquece productos con schema, atributos, completitud

## Problema actual

Hoy el agente hace demasiado:

```
Gemini detecta material
  → Gemini llama get_inventory_schema
  → Gemini interpreta required_fields
  → Gemini mapea atributos a campos tipados
  → Gemini llama search_construction_materials
  → Backend calcula missing_attributes, completion_percentage, status
  → Backend persiste en Firestore + BigQuery
```

El agente mezcla deteccion con analisis de schema, lo cual genera:

- Inconsistencias (brand asumido, atributos perdidos, missing_attributes erroneo)
- Prompt largo y fragil (muchas reglas para que Gemini no se equivoque)
- Dificil de escalar (cada nuevo campo requiere cambio en prompt + backend)

## Arquitectura propuesta

```
┌─────────────────────────────────┐     ┌──────────────────────────────────────┐
│        AGENTE (api-maia)        │     │       MCP SERVER (mcp-hub-equip)     │
│                                 │     │                                      │
│  Gemini detecta del mensaje:    │     │  Recibe materials_structured[]       │
│  - materials: string[]          │     │  Por cada material:                  │
│    (para persistir en BD)       │     │    1. Vertex search(description)     │
│  - materials_structured: [      │     │    2. Schema lookup → required_fields│
│      { description, quantity,   │     │    3. Leer attributes de Vertex      │
│        unit, brand }            │     │    4. Calcular missing_attributes    │
│    ]                            │     │    5. Calcular completion_%          │
│  - delivery_location            │     │    6. Calcular status                │
│  - delivery_date                │     │                                      │
│  - tax_id                       │     │  Retorna: products[] enriquecidos    │
│  - email                        │     │    con original, product, brand,     │
│  - suggested_question           │     │    attributes, required_fields,      │
│                                 │     │    con original, product, brand,     │
│                                 │     │    missing_attributes, status,       │
│  Llama: analyze_materials(      │     │    completion_%, match_id            │
│    materials_structured=[       │     │                                      │
│      {description:              │     │                                      │
│       "fierros corrugados 1/2", │     │                                      │
│       quantity: 10,             │     │                                      │
│       unit: "varilla",          │     │                                      │
│       brand: null}, ...]        │     │                                      │
│  )                              │     │                                      │
│                                 │     │                                      │
│  Recibe products[] del MCP      │     │                                      │
│  Persiste en Firebase + BQ      │     │                                      │
└─────────────────────────────────┘     └──────────────────────────────────────┘
```

## Flujo del agente (orden de llamado de tools)

El agente debe seguir este orden para analizar materiales correctamente:

```
┌─────────────────────────────────────────────────────────────────────┐
│  PASO 1: get_attribute_fields                                       │
│  GET /api/v1/materials/attribute-fields                             │
│                                                                     │
│  Retorna la lista de campos atributo posibles:                      │
│  ["color","presentation","type","model","size","measure",           │
│   "thickness","weight","volume","angle","fabrication",              │
│   "material","reference","cluster","compilation"]                   │
│                                                                     │
│  → El LLM sabe QUE campos buscar en el texto del usuario           │
│  → Se puede cachear (no cambia frecuentemente)                      │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────┐
│  PASO 2: get_schemas_catalog                                        │
│  GET /api/v1/schemas/catalog                                        │
│                                                                     │
│  Retorna categorias/subcategorias con required_fields y             │
│  field_options (incluyendo opciones validas para campos como        │
│  cluster, compilation, presentation, etc.)                          │
│                                                                     │
│  → El LLM sabe QUE VALORES son validos para cada campo             │
│  → Clave para campos como cluster/compilation donde el LLM         │
│    no puede inferir el valor sin conocer las opciones               │
│  → Se puede cachear (cambia solo cuando se hace POST /reload)       │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────┐
│  PASO 3: El LLM extrae atributos del texto del usuario              │
│                                                                     │
│  Con la lista de campos (paso 1) y las opciones validas (paso 2),   │
│  el LLM analiza el mensaje del usuario y extrae:                    │
│  - description, quantity, unit, brand (campos basicos)              │
│  - attributes: dict con los campos que pudo identificar             │
│                                                                     │
│  Ejemplo: "100 clavos de acero de 2 pulgadas negros"               │
│  → description: "clavos de acero de 2 pulgadas negros"             │
│  → quantity: 100                                                    │
│  → attributes: {measure: "2 pulgadas", color: "negro",             │
│                  material: "acero"}                                  │
│                                                                     │
│  Ejemplo: "cable thw 14 rojo rollo 100m"                            │
│  → description: "cable thw 14 rojo"                                 │
│  → attributes: {cluster: "THW-90 BH", color: "Rojo",               │
│                  presentation: "Rollo x 100mts"}                    │
│    (cluster y presentation mapeados usando field_options del paso 2) │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────┐
│  PASO 4: analyze_materials                                          │
│  POST /api/v1/materials/analyze                                     │
│                                                                     │
│  Envia materials_structured[] con los atributos detectados:         │
│  {                                                                  │
│    "materials_structured": [                                        │
│      {                                                              │
│        "description": "clavos de acero de 2 pulgadas negros",      │
│        "quantity": 100,                                             │
│        "unit": "unidad",                                            │
│        "brand": null,                                               │
│        "attributes": {                                              │
│          "measure": "2 pulgadas",                                   │
│          "color": "negro",                                          │
│          "material": "acero"                                        │
│        }                                                            │
│      }                                                              │
│    ]                                                                │
│  }                                                                  │
│                                                                     │
│  api-obralex:                                                       │
│  1. Busca en Vertex AI Search → category, subcategory, product      │
│  2. Obtiene required_fields del schema                              │
│  3. Compara attributes del LLM vs required_fields                   │
│  4. Calcula missing_attributes, completion_%, status                │
│  5. Si complete → asigna match_id                                   │
│                                                                     │
│  Retorna: products[] con status complete/incomplete/detected        │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────┐
│  PASO 5: Si hay productos con status "incomplete"                   │
│                                                                     │
│  El LLM le pregunta al usuario los missing_attributes               │
│  usando las questions del schema (paso 2)                           │
│                                                                     │
│  Cuando el usuario responde, el LLM re-envia a analyze_materials    │
│  con los atributos actualizados → repite desde PASO 3               │
└─────────────────────────────────────────────────────────────────────┘
```

### Resumen de tools MCP necesarios

| #   | Tool                   | Endpoint                                 | Cuando          | Cacheable |
| --- | ---------------------- | ---------------------------------------- | --------------- | --------- |
| 1   | `get_attribute_fields` | `GET /api/v1/materials/attribute-fields` | Al inicio       | Si        |
| 2   | `get_schemas_catalog`  | `GET /api/v1/schemas/catalog`            | Al inicio       | Si        |
| 3   | `analyze_materials`    | `POST /api/v1/materials/analyze`         | Por cada pedido | No        |

Los pasos 1 y 2 se pueden ejecutar una sola vez al inicio de la conversacion y cachearse. El paso 3 se ejecuta cada vez que el usuario menciona materiales.

## Cambios por capa

### Capa 1 — MCP tools en api-obralex-py

**Servidor:** mcp-hub-equip
**Endpoint destino:** api-obralex-py

#### Tool 1: `get_attribute_fields` (NUEVO)

```
GET /api/v1/materials/attribute-fields

Response:
{
  "attribute_fields": [
    "color", "presentation", "type", "model", "size",
    "measure", "thickness", "weight", "volume", "angle",
    "fabrication", "material", "reference", "cluster", "compilation"
  ]
}
```

#### Tool 2: `get_schemas_catalog` (existente)

```
GET /api/v1/schemas/catalog

Response:
{
  "total_categories": 2,
  "total_subcategories": 3,
  "categories": [
    {
      "category": "Acero",
      "subcategories": [
        {
          "subcategory": "Barras de Acero",
          "required_fields": ["measure"],
          "field_options": {
            "measure": {
              "type": "choice",
              "options": ["6 mm x 9 mts", "8 mm x 9 mts", ...],
              "question": "¿Qué medida necesitas?"
            }
          }
        }
      ]
    }
  ]
}
```

#### Tool 3: `analyze_materials` (actualizado)

```
POST /api/v1/materials/analyze

Input:
  materials_structured: [
    {
      "description": "fierros corrugados 1/2",
      "quantity": 10,
      "unit": "varilla",
      "brand": null,
      "attributes": {            ← NUEVO: atributos detectados por el LLM
        "measure": "1/2"
      }
    }
  ]

Output:
  products: [
    {
      "original": "fierros corrugados 1/2",
      "product": "fierro corrugado",
      "brand": null,
      "unit": "varilla",
      "quantity": 10,
      "category": "Acero",
      "subcategory": "Barras de Acero",
      "schema_source": "subcategory",
      "required_fields": ["measure"],
      "attributes": {
        "measure": "1/2"
      },
      "missing_attributes": [],
      "total_required_fields": 1,
      "completion_percentage": 100.0,
      "status": "complete",
      "match_id": "INV-042"
    }
  ]
```

**Separacion de responsabilidades en el input:**

| Campo                  | Quien lo extrae          | Por que                                                                                                                                                                                         |
| ---------------------- | ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `description`          | LLM (Gemini)             | Es la descripcion del producto tal como lo menciona el cliente, sin cantidad/unidad/marca. El backend usa esto para buscar en schema + Vertex                                                   |
| `quantity`             | LLM (Gemini)             | Es dato conversacional ("necesito 10...", "dame 50..."), trivial para un LLM                                                                                                                    |
| `unit`                 | LLM (Gemini)             | Es dato conversacional ("bolsas", "rollos", "varillas"), trivial para un LLM                                                                                                                    |
| `brand`                | LLM (Gemini)             | Solo si el cliente la menciona explicitamente. Trivial para un LLM, dificil con regex                                                                                                           |
| `attributes`           | LLM (Gemini)             | El LLM extrae atributos usando la lista de campos (paso 1) y las opciones validas del schema (paso 2). Campos como cluster/compilation requieren conocer las opciones para mapear correctamente |
| `category/subcategory` | api-obralex (via Vertex) | Vertex AI Search identifica categoria/subcategoria del inventario mas cercano                                                                                                                   |
| `completion_%/status`  | api-obralex              | Compara attributes del LLM vs required_fields del schema. Solo los atributos explicitamente enviados cuentan como "filled"                                                                      |

El endpoint `POST /api/v1/materials/analyze` (api-obralex-py) internamente:

1. Por cada material en `materials_structured[]`, usa `description` para una **unica busqueda en Vertex AI Search** que retorna:
   - La `category` y `subcategory` del inventario mas cercano
   - El `product` (nombre normalizado del inventario)
2. Con la subcategoria/categoria, obtiene el schema (`required_fields`) via `InventorySchemaService`
3. Compara los `attributes` enviados por el LLM contra los `required_fields` del schema
4. Solo los atributos explicitamente enviados por el LLM cuentan como "filled" — **NO se usan atributos del resultado de Vertex AI Search** (esos pertenecen al inventario, no a lo que el usuario pidio)
5. Calcula `missing_attributes` = required_fields sin valor en los attributes del LLM
6. Calcula `completion_percentage` y `status`
7. Si completo → el `match_id` viene del resultado de Vertex (sin busqueda adicional)
8. Retorna array de products enriquecidos

### Capa 2 — Prompt simplificado (api-maia)

El prompt de analisis se reduce drasticamente. Gemini solo necesita:

```
FORMATO DE RESPUESTA:
{
  "delivery_location": "string o null",
  "delivery_date": "string o null",
  "tax_id": "string o null",
  "email": "string o null",
  "materials": ["10 varillas de fierro corrugado de 1/2", "cable thw 14 rojo"],
  "materials_structured": [
    {
      "description": "descripcion del producto y sus atributos tecnicos",
      "quantity": number o null,
      "unit": "string o null",
      "brand": "string o null",
      "attributes": {
        "campo": "valor detectado"
      }
    }
  ],
  "suggested_question": "string o null"
}

REGLAS:
- materials = lista de strings, uno por cada material tal como lo menciona el cliente (para persistencia en BD)
- materials_structured = mismos materiales pero desestructurados en campos:
  - description = SOLO la descripcion del producto y sus atributos tecnicos (ej. "fierros corrugados 1/2", "cable thw 14 rojo")
  - quantity = cantidad numerica (ej. 10, 50). null si no se menciono
  - unit = unidad de medida (ej. "bolsa", "rollo", "varilla", "metro"). null si no se menciono
  - brand = marca SOLO si el cliente la menciono explicitamente. null si no la menciono
  - attributes = dict con los atributos detectados del producto. Usar la lista de campos de
    get_attribute_fields y las opciones validas de get_schemas_catalog para mapear correctamente.
    Solo incluir atributos que se puedan inferir del texto del usuario.
- NO incluir cantidad, unidad ni marca dentro de description
- materials y materials_structured deben tener el mismo orden y cantidad de elementos
- SIEMPRE acumular materiales de mensajes anteriores
- Si el cliente actualiza info de un material existente, actualizar en ambas listas
```

**Se eliminan del prompt:**

- JSON complejo de MaterialItem con attributes, required_fields, missing_attributes
- Reglas de status, completion_percentage
- Reglas de brand "asumido" (Gemini solo reporta si el cliente lo dijo)
- Instrucciones de get_inventory_schema y search_construction_materials
- Reglas de categorias activas (el MCP server maneja)

### Capa 3 — Agent service simplificado (api-maia)

```python
# Flujo actual (complejo)
result = await self.chat(message, history, system_instruction)  # Gemini + tools
analysis = self._parse_analysis_response(result["response"])    # Parse JSON complejo
self._calculate_completeness(material)                          # Backend calcula
await firestore_service.update_analysis_obralex(...)            # Persistir
await bigquery_service.insert_analysis(...)                     # Persistir

# Flujo propuesto (simple)
result = await self.chat(message, history, system_instruction)  # Gemini detecta materials + materials_structured
detection = self._parse_detection_response(result["response"])  # Parse JSON simple
products = await self.mcp_client.call_tool(                     # MCP enriquece
    "analyze_materials",
    {"materials_structured": [m.dict() for m in detection.materials_structured]}
)
# detection.materials (strings) se persiste directo en BD
await firestore_service.update_analysis_obralex(...)            # Persistir
await bigquery_service.insert_analysis(...)                     # Persistir
```

**Se eliminan de agent.py:**

- `_calculate_completeness()` → se mueve al MCP server
- Guardrail de schema-first → ya no aplica (Gemini no llama schema)
- Logica de `schema_called_for` → innecesaria

### Capa 4 — Modelo simplificado (api-maia)

```python
# Material estructurado por Gemini (input para el MCP)
class DetectedMaterial(BaseModel):
    description: str                          # "fierros corrugados 1/2"
    quantity: Optional[float] = None          # 10
    unit: Optional[str] = None                # "varilla"
    brand: Optional[str] = None               # null (solo si el cliente lo dijo)

# Modelo de deteccion (lo que retorna Gemini)
class DetectionResult(BaseModel):
    delivery_location: Optional[str] = None
    delivery_date: Optional[str] = None
    tax_id: Optional[str] = None
    email: Optional[str] = None
    materials: list[str] = []                         # strings raw para persistir en BD
    materials_structured: list[DetectedMaterial] = []  # objetos para enviar al MCP
    suggested_question: Optional[str] = None

# MaterialItem sigue igual (lo que retorna el MCP)
# Se conserva para persistencia en Firebase/BigQuery
```

### Capa 5 — MCP server: logica de enriquecimiento

**Nuevo endpoint en api-obralex-py:**

```
POST /materials/analyze
Body: {
  "materials_structured": [
    { "description": "fierros corrugados 1/2", "quantity": 10, "unit": "varilla", "brand": null },
    { "description": "cable thw 14 rojo", "quantity": 1, "unit": "rollo", "brand": null }
  ]
}

Response: {
  "products": [
    { "original": "fierros corrugados 1/2", "product": "...", "quantity": 10, "unit": "varilla", "attributes": {...}, ... }
  ]
}
```

**Logica interna (implementada en `MaterialAnalyzerService`):**

1. Por cada material objeto:
   - `get_schema_and_inventory(description)` → una unica llamada a Vertex AI Search que retorna el schema + el `InventorySearchResult`
   - Los `attributes` se leen directamente del resultado de Vertex (match semantico, no regex)
   - `quantity`, `unit`, `brand` se pasan directamente (vienen de Gemini)
   - Calcula `missing_attributes`, `completion_percentage`, `status` contra `required_fields` del schema
   - Si completo → `match_id` ya viene del mismo resultado de Vertex (sin busqueda adicional)
   - Si `schema_source == "default"` → retorna `status: "detected"` sin calcular completitud
2. Retornar array de productos enriquecidos

---

## Diagrama de flujo propuesto

```
Cliente: "necesito 10 fierros corrugados 1/2, cable thw 14 rojo y 5 galones de pintura"
                │
        ┌───────┴─────────────────────────────────────────┐
        │   PASO 1-2: LLM obtiene metadata (cacheable)    │
        │                                                  │
        │   GET /materials/attribute-fields                │
        │   → ["color","measure","cluster",...]            │
        │                                                  │
        │   GET /schemas/catalog                           │
        │   → {Cables: {cluster: {options: [...]}}, ...}   │
        └───────┬─────────────────────────────────────────┘
                │
        ┌───────┴─────────────────────────────────────────┐
        │   PASO 3: LLM extrae atributos del texto         │
        │                                                  │
        │   "fierros corrugados 1/2"                       │
        │   → attrs: {measure: "1/2"}                      │
        │                                                  │
        │   "cable thw 14 rojo"                            │
        │   → attrs: {cluster:"THW-90 BH", color:"Rojo"}  │
        │     (cluster mapeado usando options del catalogo) │
        │                                                  │
        │   "pintura latex blanca"                         │
        │   → attrs: {color: "blanco"}                     │
        └───────┬─────────────────────────────────────────┘
                │
        ┌───────┴─────────────────────────────────────────┐
        │   PASO 4: POST /materials/analyze                │
        │   MCP Server valida atributos del LLM            │
        │                                                  │
        │   Por cada material:                             │
        │   1. Vertex search → category, subcategory       │
        │   2. Schema lookup → required_fields             │
        │   3. Compara attrs del LLM vs required_fields    │
        ├─────────────────────────────────────────────────┤
        │ "fierros corrugados 1/2"                         │
        │  → required: [measure]                           │
        │  → LLM envio: {measure: "1/2"} ✓                │
        │  → missing: [] → completion: 100%                │
        │  → status: "complete", match_id: "<id>"          │
        ├─────────────────────────────────────────────────┤
        │ "cable thw 14 rojo"                              │
        │  → required: [cluster,compilation,color,         │
        │     presentation,weight]                         │
        │  → LLM envio: {cluster:✓, color:✓}              │
        │  → missing: [compilation, presentation, weight]  │
        │  → completion: 40% → status: "incomplete"        │
        ├─────────────────────────────────────────────────┤
        │ "pintura latex blanca"                           │
        │  → schema_source: "default" (sin schema)         │
        │  → status: "detected"                            │
        └───────┬─────────────────────────────────────────┘
                │
        ┌───────┴─────────────────────────────────────────┐
        │   PASO 5: Si hay "incomplete"                    │
        │   LLM pregunta al usuario los missing_attributes │
        │   → Usuario responde → re-enviar PASO 3-4       │
        └───────┬─────────────────────────────────────────┘
                │
        ┌───────┴────────┐
        │   api-maia      │
        │   (persistir)   │
        │  Firebase + BQ  │
        └────────────────┘
```

## Implementacion Fase 1 (api-obralex-py) — COMPLETADA (v2: atributos del LLM)

### Archivos creados

| Archivo                             | Proposito                                                                                                                                      |
| ----------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/models/materials.py`           | `DetectedMaterial` (input con `attributes`), `EnrichedProduct` (output), request/response models                                               |
| `src/services/material_analyzer.py` | `MaterialAnalyzerService` — orquesta: Vertex search → schema lookup → validacion de atributos del LLM → completitud. Expone `ATTRIBUTE_FIELDS` |
| `src/api/materials.py`              | Router con `POST /api/v1/materials/analyze` y `GET /api/v1/materials/attribute-fields`                                                         |

### Archivos modificados

| Archivo                            | Cambio                                                                                                                              |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `main.py`                          | Registro del router `materials_router`                                                                                              |
| `src/services/__init__.py`         | Export de `MaterialAnalyzerService`                                                                                                 |
| `src/services/inventory_schema.py` | Nuevo metodo `get_schema_and_inventory()` que retorna schema + `InventorySearchResult` (antes se descartaba el resultado de Vertex) |

### Cambios v2 (atributos del LLM en vez de Vertex)

| Cambio                              | Archivo                             | Detalle                                                                                                                                       |
| ----------------------------------- | ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Nuevo campo `attributes` en input   | `src/models/materials.py`           | `DetectedMaterial.attributes: dict[str, str] \| None` — atributos detectados por el LLM                                                       |
| Nuevo endpoint `attribute-fields`   | `src/api/materials.py`              | `GET /materials/attribute-fields` — lista de campos atributo para que el LLM sepa que extraer                                                 |
| Validacion contra atributos del LLM | `src/services/material_analyzer.py` | `_analyze_one()` ahora usa `material["attributes"]` en vez de extraer de Vertex. Solo atributos explicitamente enviados cuentan como "filled" |

### Como funciona la validacion de attributes

El endpoint **no extrae atributos de Vertex AI Search**. Los atributos vienen del LLM:

1. El LLM consulta `get_attribute_fields` y `get_schemas_catalog` para saber que campos y opciones existen
2. El LLM extrae atributos del texto del usuario y los envia en `attributes`
3. `get_schema_and_inventory(description)` busca en Vertex AI Search para obtener `category`, `subcategory` y `product`
4. Con la subcategoria, obtiene `required_fields` del schema
5. Compara los `attributes` del LLM contra `required_fields` — solo los enviados explicitamente cuentan como "filled"
6. Si un required_field no esta en `attributes` → se considera `missing`

**Importante:** Los atributos del resultado de Vertex AI Search pertenecen al inventario matcheado, NO a lo que el usuario pidio. Por eso no se usan para calcular completitud.

### Uso desde mcp-hub-equip

El flujo completo desde el MCP server requiere 3 tools en orden:

```bash
# PASO 1 — Obtener lista de campos atributo (cacheable)
GET {API_OBRALEX_URL}/api/v1/materials/attribute-fields

# PASO 2 — Obtener catalogo de schemas con opciones validas (cacheable)
GET {API_OBRALEX_URL}/api/v1/schemas/catalog

# PASO 3 — Analizar materiales (con atributos detectados por el LLM)
POST {API_OBRALEX_URL}/api/v1/materials/analyze
Content-Type: application/json

{
  "materials_structured": [
    {
      "description": "fierros corrugados 1/2",
      "quantity": 10,
      "unit": "varilla",
      "brand": null,
      "attributes": { "measure": "1/2" }
    },
    {
      "description": "clavos de 2 pulgadas",
      "quantity": 5,
      "unit": "kg",
      "brand": null,
      "attributes": { "measure": "2 pulgadas" }
    }
  ]
}
```

Response:

```json
{
  "products": [
    {
      "original": "fierros corrugados 1/2",
      "product": "fierro corrugado",
      "brand": null,
      "unit": "varilla",
      "quantity": 10,
      "category": "Acero",
      "subcategory": "Barras de Acero",
      "schema_source": "subcategory",
      "required_fields": ["measure"],
      "attributes": { "measure": "1/2" },
      "missing_attributes": [],
      "total_required_fields": 1,
      "completion_percentage": 100.0,
      "status": "complete",
      "match_id": "abc123"
    },
    {
      "original": "clavos de 2 pulgadas",
      "product": "clavo",
      "brand": null,
      "unit": "kg",
      "quantity": 5,
      "category": "Acero",
      "subcategory": "Clavos",
      "schema_source": "subcategory",
      "required_fields": ["measure"],
      "attributes": { "measure": "2 pulgadas" },
      "missing_attributes": [],
      "total_required_fields": 1,
      "completion_percentage": 100.0,
      "status": "complete",
      "match_id": "def456"
    }
  ]
}
```

### Casos de prueba

#### Test 1 — Barras de Acero (complete: LLM detecto measure)

```bash
curl -X POST http://localhost:8000/api/v1/materials/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "materials_structured": [
      {
        "description": "fierro corrugado de 1/2",
        "quantity": 10,
        "unit": "varilla",
        "brand": null,
        "attributes": { "measure": "1/2" }
      }
    ]
  }'
```

Resultado esperado:

```json
{
  "products": [
    {
      "original": "fierro corrugado de 1/2",
      "product": "fierro corrugado",
      "brand": null,
      "unit": "varilla",
      "quantity": 10,
      "category": "Acero",
      "subcategory": "Barras de Acero",
      "schema_source": "subcategory",
      "required_fields": ["measure"],
      "attributes": { "measure": "1/2" },
      "missing_attributes": [],
      "total_required_fields": 1,
      "completion_percentage": 100.0,
      "status": "complete",
      "match_id": "<id del inventario>"
    }
  ]
}
```

#### Test 2 — Barras de Acero (incomplete: LLM no detecto measure)

```bash
curl -X POST http://localhost:8000/api/v1/materials/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "materials_structured": [
      {
        "description": "fierros corrugados",
        "quantity": 0,
        "unit": null,
        "brand": null,
        "attributes": {}
      }
    ]
  }'
```

Resultado esperado:

```json
{
  "products": [
    {
      "original": "fierros corrugados",
      "product": "Barra Corrugada 6mm x 9m",
      "brand": null,
      "unit": null,
      "quantity": 0,
      "category": "Acero",
      "subcategory": "Barras de Acero",
      "schema_source": "subcategory",
      "required_fields": ["measure"],
      "attributes": { "measure": null },
      "missing_attributes": ["measure"],
      "total_required_fields": 1,
      "completion_percentage": 0.0,
      "status": "incomplete",
      "match_id": null
    }
  ]
}
```

#### Test 3 — Cables (incomplete: LLM detecto algunos atributos)

```bash
curl -X POST http://localhost:8000/api/v1/materials/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "materials_structured": [
      {
        "description": "cable thw 14 rojo",
        "quantity": 1,
        "unit": "rollo",
        "brand": null,
        "attributes": {
          "cluster": "THW-90 BH",
          "color": "Rojo"
        }
      }
    ]
  }'
```

Resultado esperado:

```json
{
  "products": [
    {
      "original": "cable thw 14 rojo",
      "product": "cable",
      "brand": null,
      "unit": "rollo",
      "quantity": 1,
      "category": "Electricidad",
      "subcategory": "Cables",
      "schema_source": "subcategory",
      "required_fields": [
        "cluster",
        "compilation",
        "color",
        "presentation",
        "weight"
      ],
      "attributes": {
        "cluster": "THW-90 BH",
        "compilation": null,
        "color": "Rojo",
        "presentation": null,
        "weight": null
      },
      "missing_attributes": ["compilation", "presentation", "weight"],
      "total_required_fields": 5,
      "completion_percentage": 40.0,
      "status": "incomplete",
      "match_id": null
    }
  ]
}
```

#### Test 4 — Material sin schema (detected)

```bash
curl -X POST http://localhost:8000/api/v1/materials/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "materials_structured": [
      {
        "description": "pintura latex blanca",
        "quantity": 5,
        "unit": "galon",
        "brand": null,
        "attributes": { "color": "blanco" }
      }
    ]
  }'
```

Resultado esperado:

```json
{
  "products": [
    {
      "original": "pintura latex blanca",
      "product": null,
      "brand": null,
      "unit": "galon",
      "quantity": 5,
      "category": null,
      "subcategory": null,
      "schema_source": "default",
      "required_fields": [],
      "attributes": {},
      "missing_attributes": [],
      "total_required_fields": 0,
      "completion_percentage": null,
      "status": "detected",
      "match_id": null
    }
  ]
}
```

#### Test 5 — Batch mixto con atributos del LLM

```bash
curl -X POST http://localhost:8000/api/v1/materials/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "materials_structured": [
      {
        "description": "fierro corrugado de 3/8",
        "quantity": 20,
        "unit": "varilla",
        "brand": null,
        "attributes": { "measure": "3/8" }
      },
      {
        "description": "cable thw rojo rollo 100m",
        "quantity": 2,
        "unit": "rollo",
        "brand": "Indeco",
        "attributes": {
          "cluster": "THW-90 BH",
          "color": "Rojo",
          "presentation": "Rollo x 100mts"
        }
      },
      {
        "description": "clavos de 3 pulgadas",
        "quantity": 10,
        "unit": "kg",
        "brand": null,
        "attributes": { "measure": "3 pulgadas" }
      },
      {
        "description": "cemento portland",
        "quantity": 50,
        "unit": "bolsa",
        "brand": "Sol",
        "attributes": {}
      }
    ]
  }'
```

Resultado esperado:

```json
{
  "products": [
    {
      "original": "fierro corrugado de 3/8",
      "product": "fierro corrugado",
      "brand": null,
      "unit": "varilla",
      "quantity": 20,
      "category": "Acero",
      "subcategory": "Barras de Acero",
      "schema_source": "subcategory",
      "required_fields": ["measure"],
      "attributes": { "measure": "3/8" },
      "missing_attributes": [],
      "total_required_fields": 1,
      "completion_percentage": 100.0,
      "status": "complete",
      "match_id": "<id>"
    },
    {
      "original": "cable thw rojo rollo 100m",
      "product": "cable",
      "brand": "Indeco",
      "unit": "rollo",
      "quantity": 2,
      "category": "Electricidad",
      "subcategory": "Cables",
      "schema_source": "subcategory",
      "required_fields": [
        "cluster",
        "compilation",
        "color",
        "presentation",
        "weight"
      ],
      "attributes": {
        "cluster": "THW-90 BH",
        "compilation": null,
        "color": "Rojo",
        "presentation": "Rollo x 100mts",
        "weight": null
      },
      "missing_attributes": ["compilation", "weight"],
      "total_required_fields": 5,
      "completion_percentage": 60.0,
      "status": "incomplete",
      "match_id": null
    },
    {
      "original": "clavos de 3 pulgadas",
      "product": "clavo",
      "brand": null,
      "unit": "kg",
      "quantity": 10,
      "category": "Acero",
      "subcategory": "Clavos",
      "schema_source": "subcategory",
      "required_fields": ["measure"],
      "attributes": { "measure": "3 pulgadas" },
      "missing_attributes": [],
      "total_required_fields": 1,
      "completion_percentage": 100.0,
      "status": "complete",
      "match_id": "<id>"
    },
    {
      "original": "cemento portland",
      "product": null,
      "brand": "Sol",
      "unit": "bolsa",
      "quantity": 50,
      "category": null,
      "subcategory": null,
      "schema_source": "default",
      "required_fields": [],
      "attributes": {},
      "missing_attributes": [],
      "total_required_fields": 0,
      "completion_percentage": null,
      "status": "detected",
      "match_id": null
    }
  ]
}
```

> **Nota:** Los valores de `product` y `match_id` dependen de lo que Vertex AI Search retorne. Los `attributes` ahora reflejan exactamente lo que el LLM envio, no lo que tiene el inventario. Los campos `quantity`, `unit` y `brand` siempre son pass-through de lo que envio el LLM.

---

## Migracion por fases

### Fase 1 — Endpoint `analyze_materials` en api-obralex-py ✅

| Que                                        | Donde          | Estado     |
| ------------------------------------------ | -------------- | ---------- |
| Endpoint `POST /materials/analyze`         | api-obralex-py | Completado |
| `MaterialAnalyzerService`                  | api-obralex-py | Completado |
| `get_schema_and_inventory()` method        | api-obralex-py | Completado |
| Tool `analyze_materials` en MCP config     | mcp-hub-equip  | Pendiente  |
| Tests con materials_structured[] de prueba | api-obralex-py | Pendiente  |

**Entregable:** endpoint funcional que recibe materials_structured[] y retorna products enriquecidos.

### Fase 2 — Simplificar prompt y agent (api-maia)

| Que                                  | Donde      | Esfuerzo |
| ------------------------------------ | ---------- | -------- |
| Nuevo prompt simplificado            | prompts.py | Bajo     |
| Nuevo modelo `DetectionResult`       | analyze.py | Bajo     |
| Refactor agent: deteccion + MCP call | agent.py   | Medio    |
| Eliminar `_calculate_completeness()` | agent.py   | Bajo     |
| Eliminar guardrail schema-first      | agent.py   | Bajo     |
| Actualizar persistencia              | agent.py   | Bajo     |

**Entregable:** agente que solo detecta + delega calculo al MCP.

### Fase 3 — Limpieza

| Que                                       | Donde      | Esfuerzo |
| ----------------------------------------- | ---------- | -------- |
| Remover tools innecesarios del prompt     | prompts.py | Bajo     |
| Simplificar SYSTEM_INSTRUCTION (Maia web) | prompts.py | Bajo     |
| Actualizar docs                           | docs/      | Bajo     |

---

## Beneficios

| Aspecto         | Actual                                | Propuesto                              |
| --------------- | ------------------------------------- | -------------------------------------- |
| Prompt          | ~100 lineas con reglas de calculo     | ~20 lineas, solo deteccion             |
| Inconsistencias | Gemini se equivoca en calculos        | MCP server calcula deterministicamente |
| Escalabilidad   | Nuevo campo = cambio prompt+backend   | Nuevo campo = cambio solo en MCP       |
| Testabilidad    | Dificil testear calculo (depende LLM) | Facil testear MCP endpoint aislado     |
| Tokens          | Prompt largo + JSON complejo          | Prompt corto + JSON simple             |
| Latencia        | Gemini hace N tool calls secuenciales | 1 sola llamada MCP batch               |

## Cobertura gradual de categorias

### Estado actual del schema (MVP)

El archivo de referencia es `inventory_schemas_sanitized_19_mar_2026.json` (fuente: BigQuery `inventories-sanitized-prod`). Contiene solo **3 subcategorias** en **2 categorias**:

| Subcategoria    | Categoria    | required_fields                                             |
| --------------- | ------------ | ----------------------------------------------------------- |
| Barras de Acero | Acero        | `measure`                                                   |
| Clavos          | Acero        | `measure`                                                   |
| Cables          | Electricidad | `cluster`, `compilation`, `color`, `presentation`, `weight` |

**Categorias objetivo del MVP:** Acero, Electricidad y Tuberias, Valvulas y Conexiones (pendiente de agregar schema).

Total inventarios indexados: **251 items**.

### No se necesita allowlist de categorias

El filtro de categorias es **implicito** — no se requiere un allowlist hardcodeado. El `InventorySchemaService` ya maneja esto con un fallback de 3 niveles:

1. **Subcategory match** (`schema_source: "subcategory"`) → analisis completo con required_fields especificos del schema
2. **Category match** (`schema_source: "category"`) → analisis con required_fields agregados (union de subcategorias de esa categoria)
3. **Default fallback** (`schema_source: "default"`) → deteccion basica sin required_fields especificos

Para materiales fuera de las 3 subcategorias con schema, el servicio retorna el default. Esto significa que el endpoint `analyze_materials` funciona para **cualquier material** — solo varia el nivel de profundidad del analisis.

### Comportamiento del endpoint `analyze_materials` segun cobertura

| Escenario                                                                             | schema_source | Resultado                                                                                                                                  |
| ------------------------------------------------------------------------------------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Material con subcategoria en schema (ej. "fierro corrugado" → Barras de Acero)        | `subcategory` | Analisis completo: category, subcategory, required*fields especificos, attributes, completion*%, status, match_id                          |
| Material con categoria en schema pero sin subcategoria exacta (ej. "alambre" → Acero) | `category`    | Analisis parcial: category, subcategory (de Vertex), required*fields agregados de la categoria, attributes, completion*%                   |
| Material sin schema (ej. "pintura latex", "escalera")                                 | `default`     | Deteccion basica: product, quantity, unit, brand, category (si Vertex lo identifica). Sin required_fields especificos, status = "detected" |

### Escalabilidad

Para agregar cobertura de una nueva categoria/subcategoria:

1. Agregar schema en el JSON de schemas (via Colab de analisis BigQuery)
2. Subir a GCS y recargar cache (`POST /schemas/reload`)
3. El endpoint `analyze_materials` automaticamente usa los nuevos schemas — **sin cambios en codigo**

Proximas categorias a agregar: Tuberias, Valvulas y Conexiones → luego expandir gradualmente.

### Response incluye `schema_source`

Cada producto en la respuesta incluye el campo `schema_source` para que el consumidor (api-maia) sepa el nivel de profundidad del analisis:

```json
{
  "original": "fierros corrugados 1/2",
  "product": "fierro corrugado",
  "category": "Acero",
  "subcategory": "Barras de Acero",
  "schema_source": "subcategory",
  "required_fields": ["measure"],
  "attributes": { "measure": "1/2" },
  "missing_attributes": [],
  "completion_percentage": 100.0,
  "status": "complete"
}
```

```json
{
  "original": "cable thw 14 rojo",
  "product": "cable thw",
  "category": "Electricidad",
  "subcategory": "Cables",
  "schema_source": "subcategory",
  "required_fields": [
    "cluster",
    "compilation",
    "color",
    "presentation",
    "weight"
  ],
  "attributes": {
    "cluster": "THW-90 BH",
    "compilation": "THW-90 BH",
    "color": "Rojo",
    "presentation": "Rollo x 100mts",
    "weight": null
  },
  "missing_attributes": ["weight"],
  "completion_percentage": 80.0,
  "status": "incomplete"
}
```

```json
{
  "original": "pintura latex blanca",
  "product": "pintura latex",
  "category": "Pinturas",
  "subcategory": null,
  "schema_source": "default",
  "required_fields": [],
  "attributes": {},
  "missing_attributes": [],
  "completion_percentage": null,
  "status": "detected"
}
```

---

## Riesgos

- **Calidad de datos en Vertex AI Search**: la identificacion de categoria/subcategoria depende de los datos indexados y los keywords/sinonimos configurados en `api-adatrack`. Si un material no esta bien indexado, cae al default. Mitigacion: mejorar el diccionario de sinonimos peruanos y expandir inventarios indexados de forma gradual

## Consideraciones

- **Fase 1 es independiente**: se puede desarrollar y testear sin tocar api-maia
- **Rollback facil**: si el MCP tool falla, se puede volver al flujo actual sin cambios
- **Doble campo materials**: Gemini retorna `materials` (strings raw para persistencia en BD) y `materials_structured` (objetos `{description, quantity, unit, brand}` para enviar al MCP). Ambas listas deben tener el mismo orden y cantidad
- **materials_structured como contrato del endpoint**: el formato objeto es simple y estable. Gemini extrae los campos no-producto (quantity, unit, brand) que son triviales para un LLM pero dificiles con regex. El backend solo se enfoca en `description` para schema + atributos
- **suggested_question**: sigue en el agente ya que depende del contexto conversacional
- **Memoria de materiales**: Gemini sigue acumulando materials[] entre mensajes via historial

## Compatibilidad

- **Firebase `analysis_obralex`**: sigue recibiendo el mismo `AnalysisObralex` (materials con MaterialItem[])
- **Firebase `products_obralex`**: sigue recibiendo el mismo array de productos
- **BigQuery**: sin cambios, sigue recibiendo `materials` (strings) y `products` (JSON)
- **Frontend**: sin cambios, sigue leyendo `products_obralex` con la misma estructura
- **Endpoint `/compare`**: sin cambios
