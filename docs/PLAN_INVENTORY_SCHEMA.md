# Plan: Esquemas de Inventario desde Cloud Storage

## Objetivo

Exponer metadata de `required_fields` y `field_options` por categoria/subcategoria desde api-obralex, usando un JSON almacenado en Cloud Storage como fuente de verdad. Esto permite que el agente (api-maia) sepa que preguntar al cliente antes de buscar inventarios especificos.

## Glosario

| Termino | Significado |
|---------|------------|
| **Inventory** | Material de la startup (lo que tenemos en stock). Coleccion `inventories` en MongoDB, indexado en Vertex AI Search |
| **Product** | Material que el cliente solicita. Cada product se enlaza con 1 inventory |
| **Inventory Schema** | Metadata (`required_fields`, `field_options`) que define que campos necesita el cliente especificar para encontrar un inventory |

## Problema

Cuando un cliente dice "Necesito clavos y cemento", el agente necesita saber:
- **Clavos**: falta medida, tipo de proyecto, material
- **Cemento**: falta peso, tipo, cantidad

Actualmente Vertex AI Search tiene los datos del producto (`size`, `material`, etc.) pero **no tiene metadata que indique que campos son obligatorios ni que opciones validas existen**.

## Por que Cloud Storage (y no MongoDB ni archivo local)

| Opcion | Descartada porque |
|--------|------------------|
| MongoDB (categories/subcategories) | Las colecciones no siempre reflejan los campos categories/subcategories de inventories. La creacion es manual por Supply y no esta sincronizada |
| JSON local en el repo | Los inventarios se actualizan hasta cada hora. Requeriria deploy para cada actualizacion de schemas |
| **Cloud Storage** | **Elegida**: el service account ya tiene permisos, se actualiza subiendo un archivo sin deploy, api-obralex lo cachea en memoria con TTL |

---

## Arquitectura

### Fuentes de datos

| Fuente | Que aporta |
|--------|-----------|
| **Cloud Storage** (inventory_schemas.json) | Esquemas: `required_fields`, `field_options` por categoria y subcategoria |
| **Vertex AI Search** (datastore productos) | Identificacion de producto: `category`, `subcategory`, `price`, `stock`, etc. |

### Flujo completo

```
Cliente (Telegram): "Necesito clavos"
    |
api-maia -> AgentService -> Gemini decide llamar get_product_schema("clavos")
    |
    v MCP tool call
equip-mcp-hub -> GET /products/schema?query=clavos -> api-obralex
    |
    v api-obralex internamente:
    1. Vertex AI Search: busca "clavos" (page_size=1)
       -> identifica category="Ferreteria", subcategory="Clavos"
    2. Cache en memoria: busca schema para subcategory="Clavos"
       -> obtiene required_fields + field_options
       (el cache se recarga desde Cloud Storage cada TTL)
    3. Si subcategory no tiene esquema -> busca en category (fallback)
    4. Si category tampoco tiene -> retorna esquema default generico
    |
    ^ respuesta sube por la misma cadena
equip-mcp-hub <- { category, subcategory, required_fields, field_options }
    |
api-maia <- tool result -> Gemini formula preguntas al cliente
    |
Cliente recibe: "Para los clavos necesito algunos detalles. De que medida? (1", 2", 3", 4")"
```

### Flujo de actualizacion de schemas

```
1. Colab: re-ejecutar analisis de inventarios
2. Descargar inventory_schemas_clean.json
3. Subir a Cloud Storage:
   gsutil cp inventory_schemas_clean.json gs://BUCKET/schemas/inventory_schemas.json
4. api-obralex recarga automaticamente en el proximo ciclo de TTL (sin deploy)
```

---

## Cloud Storage: estructura del bucket

```
gs://BUCKET_NAME/
  schemas/
    inventory_schemas.json     <- el archivo generado por Colab
```

### Formato del JSON (inventory_schemas.json)

Es el output de PLAN_INVENTORY_ANALYSIS.md (inventory_schemas_clean.json):

```json
{
  "metadata": {
    "threshold": 0.9,
    "min_products": 10,
    "min_unique_options": 2,
    "analysis_date": "2026-03-07T23:48:07"
  },
  "subcategory_schemas": {
    "Clavos": {
      "required_fields": ["presentation"],
      "field_options": {
        "presentation": {
          "type": "choice",
          "question": "En que presentacion?",
          "options": ["Caja 25kg"]
        }
      }
    },
    "Cables": {
      "required_fields": ["color"],
      "field_options": {
        "color": {
          "type": "choice",
          "question": "De que color?",
          "options": ["Amarillo", "Azul", "Blanco", "Negro", "Rojo", "Verde"]
        }
      }
    }
  },
  "category_schemas": {
    "Pinturas": {
      "required_fields": ["color", "presentation"],
      "field_options": {
        "color": { "type": "text", "question": "De que color?" },
        "presentation": {
          "type": "choice",
          "question": "En que presentacion?",
          "options": ["1 Gl", "1/4 Gl", "4 Gl", "5 Gl"]
        }
      }
    }
  }
}
```

---

## Jerarquia de resolucion de esquemas

```
1. subcategory_schemas[subcategory]  ->  si existe, usar este (mas especifico)
2. category_schemas[category]        ->  si no, usar este (general)
3. DEFAULT_SCHEMA (en codigo)        ->  ultimo recurso
```

El fallback default en codigo (nivel 3):

```python
DEFAULT_SCHEMA = {
    "required_fields": ["especificacion", "cantidad"],
    "field_options": {
        "especificacion": {
            "type": "text",
            "question": "Puedes dar mas detalles sobre lo que necesitas?"
        },
        "cantidad": {
            "type": "number",
            "unit": "unidades",
            "question": "Cuantas unidades necesitas?"
        }
    }
}
```

**Nota**: Los keys de `subcategory_schemas` y `category_schemas` son los nombres tal como aparecen en el campo `subcategories`/`categories` de la coleccion `inventories`, NO los nombres de las colecciones `categories`/`subcategories` de MongoDB (que pueden no coincidir).

---

## Tipos de field_options

| type | Descripcion | Campos | Ejemplo |
|------|-------------|--------|---------|
| `choice` | Opciones predefinidas | `options`, `question` | medida: ["1\"", "2\"", "3\""] |
| `number` | Valor numerico libre | `unit`, `question` | cantidad: unit="bolsas" |
| `text` | Texto libre | `question` | color: "De que color?" |

---

## Implementacion en api-obralex-py

### Dependencias

No se agregan dependencias nuevas. `google-cloud-storage` ya esta disponible via `google-cloud-discoveryengine` (mismo SDK de GCP).

### Archivos a crear/modificar

| Archivo | Accion | Descripcion |
|---------|--------|-------------|
| `src/core/config.py` | MODIFICAR | Agregar `GCS_BUCKET`, `GCS_SCHEMAS_PATH`, `SCHEMAS_TTL_SECONDS` |
| `src/services/schema_store.py` | CREAR | Carga JSON desde Cloud Storage, cache en memoria con TTL |
| `src/services/inventory_schema.py` | CREAR | Servicio que resuelve esquemas usando SchemaStore + Vertex AI Search |
| `src/models/schema.py` | CREAR | Modelos Pydantic para request/response |
| `src/api/schema.py` | CREAR | Router con endpoints |
| `main.py` | MODIFICAR | Registrar nuevo router |

### Paso 1: Configuracion (`src/core/config.py`)

Agregar:

```python
# Cloud Storage - Schemas
GCS_BUCKET: str = os.getenv("GCS_BUCKET", "")
GCS_SCHEMAS_PATH: str = os.getenv("GCS_SCHEMAS_PATH", "schemas/inventory_schemas.json")
SCHEMAS_TTL_SECONDS: int = int(os.getenv("SCHEMAS_TTL_SECONDS", "3600"))  # 1 hora
```

### Paso 2: Schema Store con cache TTL (`src/services/schema_store.py`)

Responsabilidades:
- Descargar JSON desde Cloud Storage
- Cachear en memoria (dict Python)
- Recargar automaticamente cuando el TTL expire
- Thread-safe

```
Pseudocodigo:

class SchemaStore:
    _cache: dict = None
    _loaded_at: float = 0
    _ttl: int = 3600  # segundos

    def _is_expired(self) -> bool:
        return (time.time() - self._loaded_at) > self._ttl

    def _load_from_gcs(self):
        blob = bucket.blob(GCS_SCHEMAS_PATH)
        content = blob.download_as_text()
        self._cache = json.loads(content)
        self._loaded_at = time.time()

    def get_schemas(self) -> dict:
        if self._cache is None or self._is_expired():
            self._load_from_gcs()
        return self._cache

    def get_subcategory_schema(self, subcategory: str) -> dict | None:
        schemas = self.get_schemas()
        return schemas.get("subcategory_schemas", {}).get(subcategory)

    def get_category_schema(self, category: str) -> dict | None:
        schemas = self.get_schemas()
        return schemas.get("category_schemas", {}).get(category)
```

**Comportamiento del cache:**
- Primera request: descarga de GCS (~100-200ms), cachea en memoria
- Requests siguientes (dentro del TTL): lectura de memoria (~0ms)
- Despues del TTL: siguiente request descarga de nuevo desde GCS
- Si GCS falla: usa el cache anterior (no rompe el servicio)

### Paso 3: Servicio de esquemas (`src/services/inventory_schema.py`)

Responsabilidades:
- `get_schema_for_query(query)`: flujo principal
  1. Busca en Vertex AI Search (1 resultado) -> obtiene `category`, `subcategory`
  2. Busca en SchemaStore por subcategory
  3. Si no hay -> busca por category
  4. Si tampoco -> retorna DEFAULT_SCHEMA

```
Pseudocodigo:

class ProductSchemaService:
    def __init__(self, search_service, schema_store):
        self.search_service = search_service
        self.schema_store = schema_store

    def get_schema_for_query(self, query: str) -> dict:
        # 1. Identificar producto via Vertex AI Search
        results = self.search_service.search(query=query, page_size=1)
        if not results:
            return {"category": None, "error": f"No se encontro producto para '{query}'"}

        product = results[0]
        category = product.category
        subcategory = product.subcategory

        # 2. Resolver schema con jerarquia
        schema = self.schema_store.get_subcategory_schema(subcategory)
        if not schema:
            schema = self.schema_store.get_category_schema(category)
        if not schema:
            schema = DEFAULT_SCHEMA

        return {
            "category": category,
            "subcategory": subcategory,
            "product_hint": product.product,
            "required_fields": schema["required_fields"],
            "field_options": schema["field_options"]
        }
```

### Paso 4: Modelos Pydantic (`src/models/schema.py`)

```
FieldOption:
  - type: str              # "choice" | "number" | "text"
  - question: str
  - options: list[str] | None
  - unit: str | None

ProductSchemaResponse:
  - category: str | None
  - subcategory: str | None
  - product_hint: str | None
  - required_fields: list[str]
  - field_options: dict[str, FieldOption]
  - error: str | None
```

### Paso 5: Endpoints (`src/api/schema.py`)

| Endpoint | Metodo | Input | Descripcion |
|----------|--------|-------|-------------|
| `/products/schema` | GET | `query: str` | Busca producto en Vertex AI Search, resuelve esquema desde cache |
| `/schemas/reload` | POST | - | Fuerza recarga del JSON desde Cloud Storage (debug/admin) |
| `/schemas/status` | GET | - | Muestra metadata del cache: fecha de carga, TTL, cantidad de schemas |

El endpoint principal (`/products/schema`) es el que usa equip-mcp-hub como tool.

---

## Variables de entorno nuevas en api-obralex-py

```env
# Cloud Storage - Schemas
GCS_BUCKET=nombre-del-bucket
GCS_SCHEMAS_PATH=schemas/inventory_schemas.json
SCHEMAS_TTL_SECONDS=3600
```

---

## Datos actuales del MVP

Resultado del analisis en Colab (inventory_schemas_clean.json):

### Subcategorias con schema (17)

| Subcategoria | required_fields |
|-------------|-----------------|
| Cables | color |
| Pinturas Decorativas | color, presentation |
| Pinturas Especiales | color, presentation |
| Agua | model |
| Calzado de Seguridad | color, presentation |
| Ropa Industrial | color, presentation |
| Ceramicos | measure, weight |
| Arcilla | measure, weight |
| Muros y tabiqueria | measure, weight |
| Techos | measure, weight |
| Cascos | color, presentation |
| Industriales | color, type, model, measure, weight, material |
| Mortero | weight, material |
| Tachos y Contenedores | weight |
| Epoxicos, Morteros y Grouting | weight |
| Desmoldantes | weight |
| Plasticos y mallas | color, weight |

### Categorias con schema - fallback (6)

| Categoria | required_fields |
|-----------|-----------------|
| Electricidad | color |
| Pinturas | color, presentation |
| Ladrillos | measure, weight |
| Higiene y Limpieza | weight |
| Otros | presentation |
| Embolsados | weight |

**Nota**: Estos schemas mejoraran cuando se complete la redistribucion de `variant` (en proceso).

---

## Flujo de actualizacion

### Actualizacion por cambio de inventarios

```
1. Inventarios se actualizan (hasta cada hora)
2. Periodicamente (semanal o cuando sea necesario):
   a. Ejecutar notebook de Colab
   b. Revisar resultados
   c. Subir JSON a Cloud Storage:
      gsutil cp inventory_schemas_clean.json gs://BUCKET/schemas/inventory_schemas.json
3. api-obralex recarga automaticamente en el proximo ciclo de TTL
```

### Actualizacion por redistribucion de variant

```
1. Companero de maestria completa redistribucion de variant
2. Re-ejecutar notebook de Colab (los campos measure, color, weight tendran mas completitud)
3. Revisar nuevos schemas generados
4. Subir JSON actualizado a Cloud Storage
5. api-obralex recarga automaticamente
```

### Forzar recarga inmediata

```bash
# Via endpoint de admin
curl -X POST https://api-obralex-url/schemas/reload
```

---

## Dependencias entre proyectos

```
Google Colab            -> Analiza inventories, genera inventory_schemas_clean.json
        |
        v
Cloud Storage (bucket)  -> Almacena inventory_schemas.json
        |                  (se sube manualmente o automatizado)
        v
api-obralex-py          -> Lee Cloud Storage (cache TTL) + Vertex AI Search
                           Expone GET /products/schema
        |
        v
equip-mcp-hub           -> Tool get_product_schema que llama a api-obralex
        |
        v
api-maia-py             -> Agente usa el tool para saber que preguntar
```

**Ningun proyecto depende de MongoDB para schemas.** La fuente de verdad es el JSON en Cloud Storage, generado a partir del analisis directo de la coleccion `inventories`.

---

## Migracion futura a MongoDB (post-MVP)

Cuando el equipo Supply normalice la relacion entre `inventories` y las colecciones `categories`/`subcategories`:

1. Agregar `required_fields` y `field_options` a los modelos de Mongoose en mx-internal
2. Migrar los schemas del JSON a las colecciones
3. api-obralex cambia de leer Cloud Storage a leer MongoDB (con motor)
4. Se puede agregar UI de edicion en mx-internal

Esto no bloquea el MVP. El approach de Cloud Storage funciona independientemente.
