# Obralex API

API REST construida con FastAPI para el ecosistema **Equip Construye** (marketplace B2B de materiales de construccion).

Expone servicios de busqueda de inventarios via Vertex AI Search y resolucion de schemas de inventario desde Cloud Storage, consumidos por equip-mcp-hub y api-maia.

## Instalacion

```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Copiar `.env.example` a `.env` y configurar las variables.

## Ejecucion

```bash
uvicorn main:app --reload
```

La API estara disponible en `http://localhost:8000`

## Endpoints

| Endpoint                     | Metodo | Descripcion                                           |
| ---------------------------- | ------ | ----------------------------------------------------- |
| `/`                          | GET    | Mensaje de bienvenida                                 |
| `/api/v1/health`             | GET    | Health check                                          |
| `/api/v1/search`             | GET    | Buscar inventarios en Vertex AI Search                |
| `/api/v1/search/summary`     | GET    | Buscar con resumen generado por IA                    |
| `/api/v1/inventories/schema` | GET    | Obtener required_fields y field_options para un query |
| `/api/v1/schemas/catalog`    | GET    | Catalogo de categorias y subcategorias con sus campos |
| `/api/v1/schemas/status`     | GET    | Estado del cache de schemas                           |
| `/api/v1/schemas/reload`     | POST   | Forzar recarga de schemas desde Cloud Storage         |
| `/docs`                      | GET    | Documentacion interactiva (Swagger)                   |

## Arquitectura

```
Cliente (Telegram) -> api-maia -> equip-mcp-hub -> api-obralex -> Vertex AI Search + Cloud Storage
```

### Estructura del proyecto

```
src/
├── api/            # Routers FastAPI
│   ├── health.py
│   ├── search.py
│   └── schema.py
├── core/           # Configuracion, credenciales, logging
│   ├── config.py
│   ├── environment.py
│   └── logging.py
├── models/         # Modelos Pydantic de response
│   ├── search.py
│   └── schema.py
└── services/       # Logica de negocio
    ├── vertex_ai_search.py
    └── inventory_schema.py
```

### Servicios principales

- **VertexAISearchService** — Busca inventarios en Google Discovery Engine (Vertex AI Search). Usa `MessageToDict` de protobuf para parsear `struct_data`. Los campos mapean 1:1 con la tabla BigQuery `inventories-simplify-prod` (nombres singulares: `category`, `subcategory`).
- **InventorySchemaService** — Resuelve que campos debe especificar el cliente para un producto. Combina Vertex AI Search (identifica categoria/subcategoria) con un JSON de schemas cacheado desde Cloud Storage (TTL de 1 hora). Jerarquia de resolucion: subcategoria -> categoria -> default. Si el JSON solo contiene `subcategory_schemas`, construye automaticamente `category_schemas` agrupando subcategorias por categoria (union de campos requeridos y merge de opciones). Expone tambien un catalogo completo de categorias/subcategorias con detalle de campos via `get_catalog()`. Schemas actuales: Cables (Electricidad), Barras de Acero y Clavos (Acero).

### Terminologia

- **Inventory** = material en almacen de la startup (lo que tenemos en stock). Fuente: MongoDB `inventories`, sincronizado a BigQuery (`inventories-simplify-prod`) via `api-adatrack` e indexado en Vertex AI Search.
- **Product** = material que solicita el cliente (lo que quiere cotizar)

### Mapeo de campos BigQuery

La tabla `inventories-simplify-prod` usa nombres singulares (`category`, `subcategory`) que mapean 1:1 al dataclass `InventorySearchResult` (~37 campos). Campos organizados en: identificadores (`id`, `sku_equip`), producto (`product`, `description`, `brand`, `unity`, `stock`), clasificacion (`category`, `subcategory`, `cluster`, `compilation`), 13 atributos (`color`, `presentation`, `type`, `model`, `size`, `measure`, `thickness`, `weight`, `volume`, `angle`, `fabrication`, `material`, `reference`), precios (`price`, `price_b2b_def`, `price_b2b_inf`, `price_b2c_def`, `price_b2c_inf`, `currency`), media (`image0`–`image3`, `techsheet_url`), busqueda (`keywords` como array) y metadata (`account_id`, `synced_at`).

El campo `keywords` contiene sinonimos peruanos de construccion (ej: "fierro" -> "barra de acero") generados por `api-adatrack` durante la sincronizacion. Ver `docs/PLAN_KEYWORDS_SYNONYMS.md` para el diccionario completo.

## Vertex AI Search: App vs Datastore

En Vertex AI Search existen dos recursos principales:

- **Datastore** — Almacena y indexa los datos (conexion a BigQuery, Cloud Storage, etc.).
- **App (Engine)** — Capa de configuracion sobre el datastore que activa la capacidad de busqueda y genera el `servingConfig` necesario para hacer queries.

**Es obligatorio crear ambos.** Aunque en el codigo solo se referencia el `VERTEX_SEARCH_DATASTORE_ID`, la app debe existir porque es la que genera el `servingConfig/default_search` que la API de Discovery Engine necesita para ejecutar busquedas. Sin la app, ese serving config no existe y las llamadas fallarian.

El codigo accede al serving config directamente por la ruta del datastore (`dataStores/{id}/servingConfigs/default_search`), por eso no se necesita el App ID como variable de entorno.

### Configuracion del schema del Datastore

Los campos del schema del datastore deben configurarse explicitamente:

- **Searchable** — el motor los usa para rankear resultados (activar para: `product`, `description`, `brand`, `category`, `subcategory`, `keywords`)
- **Retrievable** — se retornan en la respuesta de la API via `struct_data` (activar para todos los campos necesarios en la respuesta)
- **Indexable** — permite filtrado exacto (activar segun necesidad)

Enterprise edition y Generative Responses deben estar habilitados en la App para que la busqueda semantica funcione.

## Variables de entorno

| Variable                         | Descripcion                                                  |
| -------------------------------- | ------------------------------------------------------------ |
| `GOOGLE_APPLICATION_CREDENTIALS` | Ruta al JSON del service account (no necesario en Cloud Run) |
| `VERTEX_SEARCH_LOCATION`         | Region de Vertex AI Search                                   |
| `VERTEX_SEARCH_DATASTORE_ID`     | ID del datastore                                             |
| `VERTEX_SEARCH_COLLECTION`       | Nombre de la coleccion                                       |
| `GCS_BUCKET_KNOWLEDGE`           | Bucket de Cloud Storage para schemas                         |

## Deploy en GCP (Cloud Run)

### Paso 1: Autenticar con GCloud

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project maia-466013
```

### Paso 2: Construir imagen Docker

```bash
docker build -t us-central1-docker.pkg.dev/maia-466013/ar-api-obralex-prod/api-obralex-prod:1 . --platform linux/amd64
```

### Paso 3: Autenticar Docker con Artifact Registry

```bash
gcloud auth print-access-token | docker login -u oauth2accesstoken --password-stdin https://us-central1-docker.pkg.dev

gcloud auth configure-docker us-central1-docker.pkg.dev
```

### Paso 4: Subir imagen

```bash
docker push us-central1-docker.pkg.dev/maia-466013/ar-api-obralex-prod/api-obralex-prod:1
```

## Dataset de inventarios

El datastore de Vertex AI Search se alimenta desde la tabla BigQuery `inventories-simplify-prod` con 251 registros activos (categorias Acero y Electricidad). El dataset se expande incrementalmente a medida que se completan los mapeos de categorias en `api-adatrack`.

## Documentacion adicional

- `docs/inventories_sanitized_prod_v1.md` — Resumen del dataset de inventarios y 50 queries de prueba para el endpoint de schema
- `docs/API_SCHEMA_EXAMPLES.md` — Ejemplos de requests para los endpoints de schema
- `docs/PLAN_PRODUCT_SCHEMA.md` — Plan de arquitectura de schemas desde Cloud Storage
- `docs/PLAN_INVENTORY_ANALYSIS.md` — Plan de analisis de inventarios en Colab
- `docs/PLAN_KEYWORDS_SYNONYMS.md` — Plan para campo `keywords` con sinonimos peruanos de construccion
