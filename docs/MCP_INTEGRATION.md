# Integracion de Endpoints de Schema en mcp-hub-equip

## Contexto

Los endpoints de schema de api-obralex permiten que el agente (api-maia) sepa que campos preguntar al cliente antes de buscar inventarios especificos. Esta guia describe como integrarlos como tools MCP en mcp-hub-equip.

---

## Tools a agregar

### Tool 1: `get_inventory_schema`

El tool principal. Dado un query del cliente, identifica la categoria/subcategoria y retorna los campos requeridos con sus opciones.

**Definicion del Tool:**

```python
Tool(
    name="get_inventory_schema",
    description="Obtiene los campos requeridos (required_fields) y opciones (field_options) que el cliente debe especificar para buscar un material de construccion. Usar ANTES de buscar inventarios, cuando el cliente no ha dado suficientes detalles.",
    inputSchema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Nombre del material que busca el cliente (ej: clavos, cable electrico, cemento, pintura)",
            },
        },
        "required": ["query"],
    },
)
```

**Handler:**

```python
async def _get_inventory_schema(arguments: dict) -> list[TextContent]:
    query = arguments["query"]
    url = f"{Config.OBRALEX_API_URL}/inventories/schema"
    params = {"query": query}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2))]
```

**Endpoint que consume:**

```
GET {OBRALEX_API_URL}/inventories/schema?query=cable electrico
```

**Respuesta ejemplo:**

```json
{
  "category": "Electricidad",
  "subcategory": "Cables",
  "inventory_hint": "Cable THW 14 AWG Rojo",
  "required_fields": ["color"],
  "field_options": {
    "color": {
      "type": "choice",
      "question": "De que color?",
      "options": ["Amarillo", "Azul", "Blanco", "Negro", "Rojo", "Verde"]
    }
  },
  "schema_source": "subcategory"
}
```

---

## Donde agregar el codigo en mcp-hub-equip

### 1. `src/tools/obralex.py`

Agregar el Tool a `OBRALEX_TOOLS` y el handler:

```python
# En OBRALEX_TOOLS, agregar:
Tool(
    name="get_inventory_schema",
    description="Obtiene los campos requeridos y opciones que el cliente debe especificar para buscar un material de construccion. Usar ANTES de buscar inventarios.",
    inputSchema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Nombre del material (ej: clavos, cable electrico, cemento)",
            },
        },
        "required": ["query"],
    },
)

# En handle_obralex_tool(), agregar el case:
if name == "get_inventory_schema":
    return await _get_inventory_schema(arguments)

# Handler:
async def _get_inventory_schema(arguments: dict) -> list[TextContent]:
    query = arguments["query"]
    url = f"{Config.OBRALEX_API_URL}/inventories/schema"
    params = {"query": query}

    logger.info("get_inventory_schema: query='%s'", query)

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    logger.info(
        "get_inventory_schema: category=%s, subcategory=%s, source=%s",
        data.get("category"),
        data.get("subcategory"),
        data.get("schema_source"),
    )

    return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2))]
```

### 2. No se requieren cambios en `src/tools/__init__.py`

El tool se agrega a `OBRALEX_TOOLS` que ya se importa y registra automaticamente.

### 3. No se requieren nuevas variables de entorno

El tool usa la misma `OBRALEX_API_URL` que ya existe.

---

## Flujo esperado

```
Cliente: "Necesito clavos"
    |
api-maia -> Gemini decide llamar get_inventory_schema("clavos")
    |
    v  MCP tool call
mcp-hub-equip -> GET /api/v1/inventories/schema?query=clavos -> api-obralex
    |
    v  api-obralex internamente:
    1. Vertex AI Search: "clavos" -> category="Ferreteria", subcategory="Clavos"
    2. Cache GCS: schema para "Clavos" -> required_fields=["presentation"]
    |
    ^ respuesta
mcp-hub-equip <- { category, subcategory, required_fields, field_options }
    |
api-maia <- tool result -> Gemini formula preguntas
    |
Cliente recibe: "Para los clavos, en que presentacion? (Caja 25kg)"
```

---

## Valores de schema_source

| Valor | Significado |
|-------|-------------|
| `subcategory` | Se encontro schema especifico para la subcategoria |
| `category` | No habia schema de subcategoria, se uso el de categoria (fallback) |
| `default` | No habia schema ni de subcategoria ni de categoria, se usan campos genericos |

---

## Endpoints auxiliares (no son tools MCP)

Estos endpoints son para debug/admin, no necesitan ser tools:

| Endpoint | Uso |
|----------|-----|
| `GET /api/v1/schemas/status` | Verificar estado del cache (loaded, TTL, conteos) |
| `POST /api/v1/schemas/reload` | Forzar recarga del JSON desde Cloud Storage |
