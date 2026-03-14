# Plan: Campo `keywords` con sinónimos para mejorar búsquedas en Vertex AI Search

## Contexto

**api-obralex-py** es el backend que consulta Vertex AI Search para buscar inventarios de materiales de construcción. El datastore de Vertex AI Search se alimenta de la tabla BigQuery `inventories_sanitized_prod`.

### Problema detectado

Los clientes usan **términos coloquiales peruanos** que no existen literalmente en los campos del inventario. Ejemplo:

| Query del cliente | Producto real en BD | Match actual |
|---|---|---|
| "fierro de construccion 1/2" | "Barra de construcción Grado 60 1/2" X 9m" | No encuentra (0 resultados) |
| "necesito fierro para columnas" | "Barra de construcción..." | No encuentra |
| "tubos para baño" | "Tubo agua PVC..." | Depende del ranking |
| "algo para pintar paredes" | "Pintura latex..." | Depende del ranking |

Vertex AI Search con Enterprise edition tiene búsqueda semántica, pero **no cubre sinónimos del dominio de construcción peruano** (ej: "fierro" = "barra de acero").

### Solución

Agregar un campo `keywords` en la sincronización de inventarios (`api-adatrack`) que contenga sinónimos y términos coloquiales asociados al producto. Este campo viaja por el pipeline:

```
MongoDB → api-adatrack (sync) → inventories_prod → inventories_sanitized_prod → Vertex AI Search
```

Al marcar `keywords` como **Searchable** en Vertex AI Search, las queries coloquiales matchearán con los productos correctos.

---

## Especificación del campo `keywords`

### Formato

```
keywords: string
```

Un string con términos separados por comas. No es un array — BigQuery lo almacena como `STRING` y Vertex AI Search lo indexa como texto completo.

### Ejemplo

Para el inventario: `"Barra de construcción Grado 60 1/2" X 9m"` (categoría: Acero, subcategoría: Barras de Acero)

```
keywords: "fierro, fierro de construccion, varilla, varilla de construccion, fierro corrugado, varilla corrugada, fierro para columna, fierro para viga"
```

---

## Diccionario de sinónimos por categoría/subcategoría

Este diccionario debe usarse como base para generar los `keywords`. Se aplican según la **categoría y/o subcategoría** del inventario, combinados con atributos del producto.

### Acero

| Subcategoría | Sinónimos |
|---|---|
| Barras de Acero | fierro, fierro de construccion, varilla, varilla de construccion, fierro corrugado, varilla corrugada, fierro para columna, fierro para viga, fierro para losa |
| Alambres | alambre negro, alambre recocido, alambre de amarre, alambre para construccion |
| Clavos | clavo de acero, clavo para madera, clavo para encofrado |

### Tuberías, Válvulas y Conexiones

| Subcategoría | Sinónimos |
|---|---|
| Agua | tubo de agua, tuberia de agua, caño, conexion de agua, tubo pvc agua |
| Desagüe | tubo de desague, tuberia de desague, tubo para baño, tubo para drenaje |
| Eléctrica | tubo electrico, tuberia electrica, tubo conduit, tubo para cables |
| Tubería Eléctrica | tubo sap, tubo electrico, canaleta, tubo para cableado |
| UF | tubo uf, tuberia union flexible, tubo naranja, tubo para alcantarillado |

### Electricidad

| Subcategoría | Sinónimos |
|---|---|
| Cables | cable de luz, cable electrico, alambre electrico, cable para corriente, cable para instalacion, cable thw, cable vulcanizado |

### Pinturas

| Subcategoría | Sinónimos |
|---|---|
| Pinturas Decorativas | pintura para pared, pintura latex, pintura de color, pintura para interiores, pintura para exteriores, pintura lavable |
| Pinturas Especiales | anticorrosivo, pintura antioxido, pintura para metal |
| Pinturas Industriales | pintura epoxico, pintura industrial, pintura para piso |
| Resanar y Empastar | temple, imprimante, masilla, pasta para pared, empaste |
| Industriales | pintura industrial, esmalte, pintura epoxico |

### Equipos de Protección Personal

| Subcategoría | Sinónimos |
|---|---|
| Cascos | casco de obra, casco de seguridad, casco para construccion |
| Guantes | guantes de seguridad, guantes de trabajo, guantes dielectricos, guantes de proteccion |
| Calzado de Seguridad | botas de seguridad, zapatos de seguridad, botas con punta de acero, botas de obra |
| Lentes | lentes de seguridad, gafas de seguridad, proteccion para los ojos, lentes de proteccion |
| Arneses | arnes de seguridad, arnes anticaidas, linea de vida, equipo de altura |
| Protección Auditiva | protector de oidos, tapones para oidos, orejeras de seguridad |
| Bioseguridad | mascarilla, respirador, proteccion respiratoria |
| Ropa Industrial | ropa de trabajo, overol, chaleco de seguridad, mameluco |

### Químicos para Construcción

| Subcategoría | Sinónimos |
|---|---|
| Aditivos para Concreto | aditivo sika, plastificante, acelerante de fragua, aditivo para mezcla |
| Impermeabilizantes | impermeabilizante para techo, sellador de techos, membrana liquida, proteccion contra agua |
| Desmoldantes | desmoldante para encofrado, aceite para encofrado, desmoldante para concreto |
| Selladores de Juntas | sellador de juntas, silicona, sikaflex, sellador elastomerico |
| Epóxicos/Morteros/Grouting | epoxico, mortero epoxico, grout, anclaje quimico |

### Baños y Cocinas

| Subcategoría | Sinónimos |
|---|---|
| Baños | sanitario, inodoro, lavatorio, tanque de agua, cisterna |
| Cocinas | lavadero, grifo de cocina, lavaplatos |
| Duchas | terma, calentador de agua, ducha electrica, terma instantanea |

### Ladrillos

| Subcategoría | Sinónimos |
|---|---|
| Arcilla | ladrillo king kong, ladrillo de arcilla, ladrillo macizo, ladrillo pandereta |
| Muros y tabiquería | bloque de concreto, bloqueta, bloque para muro |
| Enchapes | fachaleta, ladrillo decorativo, enchape de ladrillo |
| Techos | bovedilla, ladrillo de techo, ladrillo para aligerado |

### Pisos y Pegamentos

| Subcategoría | Sinónimos |
|---|---|
| Cerámicos | ceramica, mayolica, ceramico para pared, ceramico para piso |
| Porcelanatos | porcelanato, piso de porcelanato, tablon, piso tipo madera |
| Pegamentos y Fraguas | pegamento para ceramico, pegamento para mayolica, fragua, mortero para piso |

### Embolsados

| Subcategoría | Sinónimos |
|---|---|
| Cemento | cemento portland, cemento sol, cemento tipo 1, bolsa de cemento |
| Mortero | mortero seco, mezcla lista, mortero para muros |

### Ferretería

| Subcategoría | Sinónimos |
|---|---|
| Solventes | pegamento pvc, thinner, solvente, aguarras, limpiador pvc |

---

## Lógica de generación de `keywords`

### Reglas

1. Buscar la **subcategoría** del inventario en el diccionario de sinónimos
2. Tomar los sinónimos base de esa subcategoría
3. Si el producto tiene atributos relevantes (medida, marca, material), generar combinaciones adicionales:
   - Ej: subcategoría "Barras de Acero" + medida "1/2" → agregar "fierro 1/2", "varilla 1/2"
4. Concatenar todo en un solo string separado por comas
5. No duplicar términos que ya existen en el campo `product`

### Pseudocódigo

```python
def generate_keywords(inventory: dict, synonyms_dict: dict) -> str:
    subcategory = inventory.get("subcategories", "")
    product_name = inventory.get("product", "").lower()

    # Obtener sinónimos base
    base_synonyms = synonyms_dict.get(subcategory, [])

    # Filtrar sinónimos que ya están en el nombre del producto
    keywords = [s for s in base_synonyms if s.lower() not in product_name]

    # Agregar combinaciones con medida si existe
    measure = inventory.get("measure", "")
    if measure:
        key_measures = [s.split(",")[0] for s in base_synonyms[:3]]  # top 3 sinónimos
        for term in key_measures:
            keywords.append(f"{term} {measure}")

    return ", ".join(keywords)
```

---

## Implementación en api-adatrack

### Dónde agregar

En el proceso de sincronización de inventarios a `inventories_prod`, al momento de construir el row para BigQuery, agregar el campo `keywords` generado.

### Pasos

1. Crear archivo de configuración con el diccionario de sinónimos (ej: `src/config/inventory_synonyms.py` o `src/config/inventory_synonyms.json`)
2. Crear función `generate_keywords(inventory)` que reciba un inventario y retorne el string de keywords
3. En la función de sincronización, llamar a `generate_keywords()` y agregar el campo `keywords` al row antes de insertarlo en BigQuery
4. Agregar la columna `keywords` (tipo `STRING`) al schema de la tabla `inventories_prod` en BigQuery
5. Asegurar que el campo se propague a `inventories_sanitized_prod`

### Impacto en api-obralex

No requiere cambios en código. Solo se necesita:

1. Que el campo `keywords` exista en `inventories_sanitized_prod`
2. En Vertex AI Search, marcar `keywords` como **Searchable** y **Retrievable**
3. Re-sincronizar el datastore para indexar el nuevo campo

---

## Configuración en Vertex AI Search

Una vez que `keywords` exista en `inventories_sanitized_prod`:

1. Ir a **Vertex AI Search Console → Datastore → Schema**
2. El campo `keywords` debería aparecer automáticamente
3. Marcar como:
   - **Searchable**: SI (fundamental)
   - **Retrievable**: SI (para debug y visibilidad)
   - **Indexable**: NO (no se usará para filtrado exacto)
   - **Dynamic Facetable**: NO
4. Re-importar/sincronizar datos si es necesario

---

## Queries de validación

Después de implementar, validar estos queries que antes fallaban:

| # | Query | Resultado esperado |
|---|---|---|
| 1 | `fierro de construccion 1/2` | Barra de construcción Grado 60 1/2" (Acero > Barras de Acero) |
| 2 | `necesito fierro para columnas` | Barras de acero (Acero > Barras de Acero) |
| 3 | `algo para pintar paredes` | Pinturas Decorativas |
| 4 | `proteccion para los ojos` | Lentes de seguridad (EPP > Lentes) |
| 5 | `tubos para baño` | Tuberías agua/desagüe |
| 6 | `material para pegar mayolica` | Pegamentos y Fraguas |
| 7 | `quiero piso de madera` | Porcelanatos (tablón tipo madera) |
| 8 | `botas con punta de acero` | Calzado de Seguridad |
| 9 | `busco cemento` | Cemento (Embolsados) |
| 10 | `cable para luz` | Cables (Electricidad) |
