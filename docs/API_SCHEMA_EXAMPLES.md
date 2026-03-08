# Ejemplos de requests - Schema Endpoints

Base URL: `http://localhost:8000/api/v1`

---

## 1. GET /inventories/schema

Endpoint principal. Es el que usa equip-mcp-hub como tool `get_inventory_schema`.

### Producto con schema de subcategoria

```
GET /api/v1/inventories/schema?query=cable electrico
```

Respuesta esperada:

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

### Producto con fallback a categoria

```
GET /api/v1/inventories/schema?query=pintura esmalte
```

Respuesta esperada:

```json
{
  "category": "Pinturas",
  "subcategory": "Esmaltes",
  "inventory_hint": "Pintura esmalte sintetico",
  "required_fields": ["color", "presentation"],
  "field_options": {
    "color": {
      "type": "text",
      "question": "De que color?"
    },
    "presentation": {
      "type": "choice",
      "question": "En que presentacion?",
      "options": ["1 Gl", "1/4 Gl", "4 Gl", "5 Gl"]
    }
  },
  "schema_source": "category"
}
```

### Producto sin schema -> default

```
GET /api/v1/inventories/schema?query=martillo
```

Respuesta esperada:

```json
{
  "category": "Herramientas",
  "subcategory": "Martillos",
  "inventory_hint": "Martillo de una Stanley",
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
  },
  "schema_source": "default"
}
```

### Producto no encontrado en Vertex

```
GET /api/v1/inventories/schema?query=xyzproductoinexistente
```

Respuesta esperada:

```json
{
  "category": null,
  "subcategory": null,
  "inventory_hint": null,
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
  },
  "schema_source": "default"
}
```

---

## 2. GET /schemas/status

Estado del cache de schemas en memoria.

```
GET /api/v1/schemas/status
```

Respuesta esperada:

```json
{
  "loaded": true,
  "loaded_at": 1741305600.0,
  "ttl_seconds": 3600,
  "subcategory_count": 17,
  "category_count": 6,
  "metadata": {
    "threshold": 0.9,
    "min_products": 10,
    "min_unique_options": 2,
    "analysis_date": "2026-03-07T23:48:07"
  }
}
```

---

## 3. POST /schemas/reload

Fuerza recarga del JSON desde Cloud Storage.

```
POST /api/v1/schemas/reload
```

Respuesta esperada:

```json
{
  "message": "Schemas reloaded"
}
```

---

## Flujo de prueba sugerido

1. `GET /schemas/status` -> verificar que `loaded: false` (primera vez)
2. `GET /inventories/schema?query=clavos` -> dispara la primera carga desde GCS + busqueda en Vertex
3. `GET /schemas/status` -> ahora `loaded: true` con los conteos
4. `GET /inventories/schema?query=cable electrico` -> schema de subcategoria
5. `GET /inventories/schema?query=pintura esmalte` -> fallback a categoria
6. `GET /inventories/schema?query=martillo` -> fallback a default
7. `POST /schemas/reload` -> fuerza recarga
8. `GET /schemas/status` -> `loaded_at` actualizado
