# Plan: Analisis de Inventarios para derivar required_fields y field_options

## Objetivo

Analizar la coleccion `inventories` de MongoDB agrupando por `categories`/`subcategories` para determinar:
1. **required_fields**: campos con alta completitud que el cliente debe especificar para cotizar
2. **field_options**: valores unicos reales de cada campo para construir las opciones de seleccion

El resultado se exporta como `inventory_schemas_clean.json` y se sube a Cloud Storage para que api-obralex lo consuma con cache TTL (ver PLAN_PRODUCT_SCHEMA.md).

---

## Contexto: Modelo de Inventories

### Campos candidatos a analizar (especificaciones del producto)

Estos son los campos que el **cliente necesita decidir** para poder buscar un producto especifico:

| Campo | Tipo | Ejemplo esperado |
|-------|------|-----------------|
| `color` | String | "Rojo", "Blanco" |
| `presentation` | String | "Caja x 100", "Bolsa 50kg" |
| `type` | String | "Portland Tipo I", "Latex" |
| `model` | String | "KK-18", "Estandar" |
| `size` | String | "1/2\"", "9x13x24" |
| `measure` | String | "3\"", "6m", "12mm" |
| `thickness` | String | "0.5mm", "1.2mm" |
| `weight` | String | "50kg", "25kg" |
| `volume` | String | "1L", "5 galones" |
| `angle` | String | "45", "90" |
| `fabrication` | String | "Nacional", "Importado" |
| `material` | String | "Acero", "PVC", "Galvanizado" |

### Campos EXCLUIDOS del analisis

| Campo | Razon de exclusion |
|-------|-------------------|
| `variant` | Cajon de sastre: mezcla medidas, colores, pesos, tallas. Se redistribuira a los campos correctos (ver seccion "Redistribucion de variant") |
| `brand` | No es una especificacion del cliente. El agente muestra marcas disponibles DESPUES de buscar con los filtros del cliente |
| `unity` | Es atributo del producto, no decision del cliente. Se infiere del producto encontrado |
| `sku*`, `price*`, `margin*` | Metadata interna |
| `image*`, `embeddings*` | Datos tecnicos |
| `keywords`, `accountId`, `actionBy`, `status`, `isActive` | Metadata administrativa |

### Campos de agrupacion

| Campo | Uso |
|-------|-----|
| `categories` | Array de categorias (ej: `["Acero", "Fierros"]`) |
| `subcategories` | Array de subcategorias (ej: `["Fierro corrugado"]`) |

---

## Filtrado de inventarios: solo los que SI tienen informacion

El analisis se enfoca en inventarios que tengan datos utiles. Filtros base:

```python
BASE_FILTER = {
    "status": "active",
    "isActive": True,
    "isDiscontinued": {"$ne": True}
}
```

Ademas, para que una categoria/subcategoria sea considerada valida para el analisis:

- **Minimo 10 productos** en esa agrupacion (si tiene menos, no es representativa)
- **Al menos 1 campo candidato** con >= 90% completitud (si ninguno pasa, no genera esquema)

---

## Observaciones del primer analisis (inventory_schemas.json raw)

Al revisar los resultados del primer analisis se detectaron los siguientes problemas:

### 1. `variant` contamina todo

Aparece como required_field en la mayoria de subcategorias porque tiene alta completitud, pero sus valores mezclan conceptos distintos:

| Subcategoria | variant contiene | Deberia ser |
|-------------|------------------|-------------|
| Cascos | "Amarillo", "Azul", "Blanco" | `color` |
| Calzado de Seguridad | "Talla 34", "Talla 35" | `size` |
| Barras de Acero | "1/2\" x 9 mts", "3/8\" x 9 mts" | `measure` |
| Tachos y Contenedores | "150 kilos", "300 kilos" | `weight` |
| Solventes | "1 gl", "1/4 gln" | `volume` |
| Industriales | "AMARILLO", "5.5 kg" | `color` + `weight` mezclados |

**Accion**: Excluir `variant` del analisis automatico. La redistribucion de variant a los campos correctos se hace en un proceso aparte (ver seccion dedicada).

### 2. `brand` y `unity` no son decisiones del cliente

Aparecen en casi todas las subcategorias con alta completitud, pero:
- El cliente dice "necesito cemento tipo I de 42.5kg", NO "necesito cemento marca Apu"
- La marca y unidad son filtros secundarios que el agente ofrece despues de la busqueda

**Accion**: Excluir `brand` y `unity` de required_fields. Se usan internamente en `search_products` pero no se preguntan al cliente.

### 3. Datos sucios en opciones

| Problema | Ejemplo | Solucion |
|----------|---------|----------|
| Valor "0" como opcion valida | material: ["0", "Ceramica"] en Ceramicos | Filtrar valores "0", "N/A", "-" |
| Casing inconsistente | "NEGRO" vs "Negro" vs "negro" | Normalizar a Title Case |
| Subcategorias duplicadas | "Placas silico calcareas" vs "Placas silico calcareas" | Merge por similitud |
| Opciones con un solo valor | weight: ["42.5"] en Cemento | Eliminar del schema (no tiene sentido preguntar) |
| Unidades mezcladas en weight | "50kg" vs "50" vs "50 Kilos" | Normalizar formato |

### 4. Campos con una sola opcion

Si un field_option tiene una sola opcion posible, no tiene sentido preguntarle al cliente. Ejemplo:
- Cemento → weight: ["42.5"] (solo hay de 42.5kg)
- Mortero → brand: ["LACASA"] (solo hay una marca)

**Accion**: Si un campo tiene <= 1 opcion unica, no incluirlo como required_field. El valor se asume automaticamente.

---

## Metodologia del analisis (actualizada)

### Paso 1: Filtrar inventarios validos

```python
BASE_FILTER = {
    "status": "active",
    "isActive": True,
    "isDiscontinued": {"$ne": True}
}

# Campos que SI analizamos (especificaciones del cliente)
CANDIDATE_FIELDS = [
    "color", "presentation", "type", "model",
    "size", "measure", "thickness", "weight",
    "volume", "angle", "fabrication", "material"
]

# Valores basura a ignorar
GARBAGE_VALUES = [None, "", "0", "N/A", "-", "n/a", "NA", "null"]

THRESHOLD = 0.90           # 90% completitud
MIN_PRODUCTS = 10          # minimo productos por grupo
MIN_UNIQUE_OPTIONS = 2     # minimo opciones para ser required_field
MAX_CHOICE_OPTIONS = 20    # maximo opciones para ser "choice" (sino es "text")
```

### Paso 2: Completitud por categoria/subcategoria

Para cada grupo, calcular el porcentaje de documentos que tienen cada campo lleno con un valor valido (no basura):

```
Por subcategoria "Barras de Acero" (35 productos):
  - measure:     95% completitud, 10 opciones  -> REQUIRED (choice)
  - weight:      92% completitud, 8 opciones   -> REQUIRED (choice)
  - material:    88% completitud               -> NO (< 90%)
  - color:        5% completitud               -> NO
  - thickness:    0% completitud               -> NO
```

### Paso 3: Limpieza de valores

Para cada campo que pasa el umbral:

1. **Quitar valores basura**: "0", "", None, "N/A"
2. **Normalizar casing**: "NEGRO" → "Negro", "negro" → "Negro"
3. **Trim whitespace**: " 50kg " → "50kg"
4. **Deduplicar por similitud**: "Loza Vitrificada" y "Loza vitrificada" → "Loza vitrificada"

### Paso 4: Validar opciones

- Si campo tiene < 2 opciones unicas → **excluir** (no tiene sentido preguntar)
- Si campo tiene 2-20 opciones → `type: "choice"` con lista de opciones
- Si campo tiene > 20 opciones → `type: "text"` (demasiada variedad para listar)

### Paso 5: Generar preguntas

| Campo | Question |
|-------|----------|
| measure | "De que medida?" |
| weight | "De que peso?" |
| material | "De que material?" |
| color | "De que color?" |
| type | "De que tipo?" |
| size | "De que tamano?" |
| thickness | "De que espesor?" |
| volume | "De que volumen?" |
| presentation | "En que presentacion?" |
| model | "De que modelo?" |
| angle | "De que angulo?" |
| fabrication | "Que tipo de fabricacion?" |

---

## Redistribucion de `variant` (proceso aparte)

El campo `variant` necesita redistribuirse a los campos correctos antes de que el analisis sea preciso. Esto se hace en un proceso separado.

### Approach hibrido (en ejecucion por compañero de maestria)

1. **Regex** para patrones obvios:
   - Contiene "kg" o "kilos" → `weight`
   - Contiene pulgadas (`"`, `pulg`) o `mm`/`cm`/`m` → `measure`
   - Contiene colores conocidos → `color`
   - Contiene "Talla" → `size`
   - Contiene "gl", "gln", "litros" → `volume`
   - Contiene "mm" sin otras dimensiones → `thickness`

2. **LLM** para ambiguos que no matchean regex, enviando en batch con contexto (category, subcategory, product name)

3. **Revision humana** del porcentaje restante

### Impacto en el analisis

Una vez redistribuido `variant`:
- Los campos como `measure`, `weight`, `color`, `size` tendran mayor completitud
- El analisis de required_fields sera mas preciso
- Se re-ejecuta el notebook y se genera un nuevo `inventory_schemas_clean.json`

### Mientras tanto

El analisis actual funciona sin `variant`. Los campos que ya tienen buena completitud (measure, weight, type, material, etc.) se pueden usar directamente. Cuando la redistribucion este lista, se complementa.

---

## Pipeline de archivos

```
[Google Colab Notebook]
        |
        v
docs/inventory_schemas.json           <- raw del primer analisis (referencia historica)
        |
        v
[Limpieza: quitar variant/brand/unity, normalizar, filtrar basura]
        |
        v
docs/inventory_schemas_clean.json     <- version limpia, lista para Cloud Storage
        |
        v
[Subir a Cloud Storage]
  gsutil cp inventory_schemas_clean.json gs://BUCKET/schemas/inventory_schemas.json
        |
        v
api-obralex: lee desde Cloud Storage con cache TTL (sin deploy)
```

---

## Notebook de Google Colab (actualizado)

### Estrategia de rendimiento

**Una sola consulta a MongoDB** para cargar todos los inventarios validos en un DataFrame de pandas.
Todo el analisis (completitud, opciones, schemas) se hace en memoria con operaciones vectorizadas.
Solo se vuelve a consultar MongoDB al final para insertar resultados.

### Estructura del notebook

```
1. Setup, conexion y carga unica del DataFrame
2. Limpieza y normalizacion del DataFrame
3. Exploracion general
4. Analisis de completitud por subcategoria
5. Analisis de completitud por categoria (fallback)
6. Generacion de schemas
7. Visualizacion (heatmap)
8. Exportar JSON limpio
9. Reporte de subcategorias sin schema
10. (Opcional) Subir a Cloud Storage
```

### Celda 1: Setup y carga unica desde MongoDB

```python
!pip install pymongo pandas matplotlib seaborn

from pymongo import MongoClient
import pandas as pd
import numpy as np
import re
import json

MONGODB_URI = "mongodb+srv://..."
DB_NAME = "..."

client = MongoClient(MONGODB_URI)
db = client[DB_NAME]

# --- Configuracion ---

CANDIDATE_FIELDS = [
    "color", "presentation", "type", "model",
    "size", "measure", "thickness", "weight",
    "volume", "angle", "fabrication", "material"
]

# Campos de agrupacion (son arrays, se explotan despues)
GROUP_FIELDS = ["categories", "subcategories"]

# Campos a traer de MongoDB (solo los necesarios)
PROJECTION_FIELDS = CANDIDATE_FIELDS + GROUP_FIELDS + ["product", "_id"]

GARBAGE_VALUES = {"", "0", "N/A", "-", "n/a", "NA", "null", "0.0", "None"}

THRESHOLD = 0.90
MIN_PRODUCTS = 10
MIN_UNIQUE_OPTIONS = 2
MAX_CHOICE_OPTIONS = 20

FIELD_QUESTIONS = {
    "measure": "De que medida?",
    "weight": "De que peso?",
    "material": "De que material?",
    "color": "De que color?",
    "type": "De que tipo?",
    "size": "De que tamano?",
    "thickness": "De que espesor?",
    "volume": "De que volumen?",
    "presentation": "En que presentacion?",
    "model": "De que modelo?",
    "angle": "De que angulo?",
    "fabrication": "Que tipo de fabricacion?",
}

# --- Carga unica desde MongoDB ---

BASE_FILTER = {
    "status": "active",
    "isActive": True,
    "isDiscontinued": {"$ne": True}
}

projection = {f: 1 for f in PROJECTION_FIELDS}
projection["_id"] = 1

print("Cargando inventarios desde MongoDB...")
cursor = db.inventories.find(BASE_FILTER, projection)
raw_data = list(cursor)
print(f"Cargados: {len(raw_data)} inventarios")

# Crear DataFrame
df = pd.DataFrame(raw_data)
df = df.drop(columns=["_id"], errors="ignore")
print(f"DataFrame shape: {df.shape}")
print(f"Columnas: {list(df.columns)}")
```

### Celda 2: Limpieza y normalizacion del DataFrame

```python
def normalize_value(val):
    """Normaliza un valor: trim, title case para textos puros."""
    if pd.isna(val) or val is None:
        return np.nan
    val = str(val).strip()
    val = re.sub(r'\s+', ' ', val)
    if val in GARBAGE_VALUES:
        return np.nan
    # Title case solo para textos sin numeros y con mas de 2 chars
    if not re.search(r'[0-9]', val) and len(val) > 2:
        val = val.title()
    return val

# Aplicar normalizacion a todos los campos candidatos
print("Normalizando campos candidatos...")
for field in CANDIDATE_FIELDS:
    if field in df.columns:
        df[field] = df[field].apply(normalize_value)
    else:
        df[field] = np.nan

# Verificar
filled_counts = df[CANDIDATE_FIELDS].notna().sum()
print("\nCampos con datos (total):")
print(filled_counts.sort_values(ascending=False).to_string())
```

### Celda 3: Exploracion general

```python
print(f"Total inventarios validos: {len(df)}")

# --- Explorar subcategorias ---
# Explotar el array "subcategories" para tener una fila por subcategoria
df_sub = df.explode("subcategories").rename(columns={"subcategories": "subcategory_exp"})
df_sub = df_sub.dropna(subset=["subcategory_exp"])

sub_counts = df_sub["subcategory_exp"].value_counts()
print(f"\nSubcategorias unicas: {len(sub_counts)}")

valid_subcats = sub_counts[sub_counts >= MIN_PRODUCTS].index.tolist()
skipped_subcats = sub_counts[sub_counts < MIN_PRODUCTS].index.tolist()

print(f"Subcategorias validas (>= {MIN_PRODUCTS} productos): {len(valid_subcats)}")
print(f"Subcategorias omitidas (< {MIN_PRODUCTS} productos): {len(skipped_subcats)}")

# Mostrar tabla
sub_summary = pd.DataFrame({
    "productos": sub_counts,
    "status": sub_counts.apply(lambda x: "OK" if x >= MIN_PRODUCTS else "SKIP")
})
print(sub_summary.to_string())

# --- Explorar categorias ---
df_cat = df.explode("categories").rename(columns={"categories": "category_exp"})
df_cat = df_cat.dropna(subset=["category_exp"])

cat_counts = df_cat["category_exp"].value_counts()
valid_cats = cat_counts[cat_counts >= MIN_PRODUCTS].index.tolist()

print(f"\nCategorias unicas: {len(cat_counts)}")
print(f"Categorias validas (>= {MIN_PRODUCTS} productos): {len(valid_cats)}")
```

### Celda 4: Funciones de analisis sobre DataFrame

```python
def compute_completeness(df_group, group_col, group_values):
    """
    Calcula % de completitud de cada campo candidato por grupo.
    Retorna un DataFrame: filas=grupos, columnas=campos, valores=% completitud.
    Opera 100% en memoria, sin consultas a MongoDB.
    """
    results = {}

    for group_val in group_values:
        mask = df_group[group_col] == group_val
        group_df = df_group.loc[mask, CANDIDATE_FIELDS]
        total = len(group_df)

        if total < MIN_PRODUCTS:
            continue

        # Completitud: % de valores no-NaN por columna
        completeness = (group_df.notna().sum() / total * 100).round(2)
        results[group_val] = completeness

    return pd.DataFrame(results).T  # filas=grupos, columnas=campos

def extract_options_for_group(df_group, group_col, group_val, field):
    """Extrae valores unicos limpios de un campo para un grupo."""
    mask = df_group[group_col] == group_val
    values = df_group.loc[mask, field].dropna().unique()
    return sorted(set(values))

def generate_schemas(df_group, group_col, completeness_df):
    """
    Genera schemas para todos los grupos a partir del DataFrame de completitud.
    Retorna dict {group_name: {required_fields, field_options}}.
    """
    schemas = {}

    for group_val in completeness_df.index:
        row = completeness_df.loc[group_val]

        # Campos que pasan el umbral
        passing_fields = row[row >= THRESHOLD * 100].index.tolist()

        required_fields = []
        field_options = {}

        for field in passing_fields:
            options = extract_options_for_group(df_group, group_col, group_val, field)

            # Saltar campos con menos de 2 opciones
            if len(options) < MIN_UNIQUE_OPTIONS:
                continue

            required_fields.append(field)

            if len(options) <= MAX_CHOICE_OPTIONS:
                field_options[field] = {
                    "type": "choice",
                    "question": FIELD_QUESTIONS.get(field, f"Especifica {field}:"),
                    "options": options
                }
            else:
                field_options[field] = {
                    "type": "text",
                    "question": FIELD_QUESTIONS.get(field, f"Especifica {field}:")
                }

        if required_fields:
            schemas[group_val] = {
                "required_fields": required_fields,
                "field_options": field_options
            }

    return schemas
```

### Celda 5: Analisis por subcategoria

```python
print("Analizando completitud por subcategoria...")

# Calcular completitud (una sola operacion vectorizada)
sub_completeness = compute_completeness(df_sub, "subcategory_exp", valid_subcats)

print(f"\nMatriz de completitud: {sub_completeness.shape}")
print(sub_completeness.to_string())

# Generar schemas
subcategory_schemas = generate_schemas(df_sub, "subcategory_exp", sub_completeness)

print(f"\n--- Subcategorias con schema: {len(subcategory_schemas)} de {len(valid_subcats)} ---")
for name, schema in subcategory_schemas.items():
    total = int(sub_completeness.loc[name].name and (df_sub["subcategory_exp"] == name).sum())
    print(f"\n{name} ({total} productos):")
    for f in schema["required_fields"]:
        opts = schema["field_options"][f]
        n_opts = len(opts.get("options", [])) if opts["type"] == "choice" else "libre"
        pct = sub_completeness.loc[name, f]
        print(f"  {f}: {pct}% | {opts['type']} ({n_opts} opciones)")
```

### Celda 6: Analisis por categoria (fallback)

```python
print("Analizando completitud por categoria...")

cat_completeness = compute_completeness(df_cat, "category_exp", valid_cats)

print(f"\nMatriz de completitud: {cat_completeness.shape}")
print(cat_completeness.to_string())

# Generar schemas
category_schemas = generate_schemas(df_cat, "category_exp", cat_completeness)

print(f"\n--- Categorias con schema: {len(category_schemas)} de {len(valid_cats)} ---")
for name, schema in category_schemas.items():
    total = int((df_cat["category_exp"] == name).sum())
    print(f"\n{name} ({total} productos):")
    for f in schema["required_fields"]:
        opts = schema["field_options"][f]
        n_opts = len(opts.get("options", [])) if opts["type"] == "choice" else "libre"
        pct = cat_completeness.loc[name, f]
        print(f"  {f}: {pct}% | {opts['type']} ({n_opts} opciones)")
```

### Celda 7: Visualizacion (heatmaps)

```python
import matplotlib.pyplot as plt
import seaborn as sns

fig, axes = plt.subplots(1, 2, figsize=(24, max(10, len(sub_completeness) * 0.4)),
                          gridspec_kw={"width_ratios": [2, 1]})

# Heatmap subcategorias
sns.heatmap(
    sub_completeness, annot=True, fmt=".0f", cmap="RdYlGn",
    vmin=0, vmax=100, linewidths=0.5, ax=axes[0]
)
axes[0].set_title(f"% Completitud por SUBCATEGORIA (umbral: {THRESHOLD*100}%)")
axes[0].set_xlabel("Campo")
axes[0].set_ylabel("Subcategoria")
axes[0].tick_params(axis="x", rotation=45)

# Heatmap categorias
sns.heatmap(
    cat_completeness, annot=True, fmt=".0f", cmap="RdYlGn",
    vmin=0, vmax=100, linewidths=0.5, ax=axes[1]
)
axes[1].set_title(f"% Completitud por CATEGORIA (umbral: {THRESHOLD*100}%)")
axes[1].set_xlabel("Campo")
axes[1].set_ylabel("Categoria")
axes[1].tick_params(axis="x", rotation=45)

plt.tight_layout()
plt.show()
```

### Celda 8: Exportar JSON limpio

```python
output = {
    "metadata": {
        "threshold": THRESHOLD,
        "min_products": MIN_PRODUCTS,
        "min_unique_options": MIN_UNIQUE_OPTIONS,
        "max_choice_options": MAX_CHOICE_OPTIONS,
        "excluded_fields": ["variant", "brand", "unity"],
        "excluded_reason": {
            "variant": "Cajon de sastre, pendiente redistribucion",
            "brand": "No es decision del cliente, es filtro secundario",
            "unity": "Se infiere del producto, no se pregunta"
        },
        "total_inventories_analyzed": len(df),
        "subcategories_with_schema": len(subcategory_schemas),
        "categories_with_schema": len(category_schemas),
        "analysis_date": pd.Timestamp.now().isoformat()
    },
    "subcategory_schemas": subcategory_schemas,
    "category_schemas": category_schemas
}

with open("inventory_schemas_clean.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("Exportado a inventory_schemas_clean.json")
print(f"  Subcategorias: {len(subcategory_schemas)}")
print(f"  Categorias: {len(category_schemas)}")

# Descargar en Colab
from google.colab import files
files.download("inventory_schemas_clean.json")
```

### Celda 9: Reporte de subcategorias SIN schema

```python
# Subcategorias validas que no generaron schema
no_schema = [s for s in valid_subcats if s not in subcategory_schemas]
print(f"Subcategorias validas SIN schema ({len(no_schema)}):")
print(f"(Ninguno de sus campos candidatos pasa el umbral de {THRESHOLD*100}%)\n")

if no_schema:
    # Obtener el mejor campo de cada una directamente del DataFrame de completitud
    for subcat in no_schema:
        row = sub_completeness.loc[subcat]
        best_field = row.idxmax()
        best_pct = row.max()
        total = int((df_sub["subcategory_exp"] == subcat).sum())
        print(f"  {subcat} ({total} prod) - mejor campo: {best_field} ({best_pct}%)")
```

### Celda 10: (Opcional) Subir a Cloud Storage

```python
# Subir directamente desde Colab a Cloud Storage
# Requiere autenticacion con service account o cuenta de Google

from google.cloud import storage

BUCKET_NAME = "nombre-del-bucket"
DESTINATION_PATH = "schemas/inventory_schemas.json"

client_gcs = storage.Client()
bucket = client_gcs.bucket(BUCKET_NAME)
blob = bucket.blob(DESTINATION_PATH)
blob.upload_from_filename("inventory_schemas_clean.json")

print(f"Subido a gs://{BUCKET_NAME}/{DESTINATION_PATH}")
print("api-obralex recargara automaticamente en el proximo ciclo de TTL")
```

---

## Consideraciones importantes

### Enfoque en inventarios con informacion

El proyecto esta orientado a detectar inventarios que SI tienen informacion completa. Inventarios con datos faltantes no se ignoran, simplemente no contribuyen al porcentaje de completitud. Si una subcategoria tiene 30 productos pero solo 5 tienen `measure` lleno, ese campo no sera required_field para esa subcategoria.

### Calidad de datos

- Valores inconsistentes ("3 pulgadas", "3\"", "3 pulg") se normalizan en el paso de limpieza
- La redistribucion de `variant` (en proceso) mejorara significativamente la completitud de campos como measure, color, weight, size
- Despues de la redistribucion, re-ejecutar el notebook para obtener schemas mas completos

### Umbral configurable

- El 90% es el punto de partida. Puede ajustarse por categoria si es necesario
- El minimo de 10 productos evita que subcategorias con pocos items generen schemas no representativos
- El minimo de 2 opciones unicas evita preguntas donde solo hay una respuesta posible

### Iteracion

Este analisis no es un one-shot. El flujo es iterativo:

```
1. Ejecutar analisis con datos actuales → inventory_schemas_clean.json v1
2. Subir a Cloud Storage → api-obralex recarga automaticamente
3. Redistribuir variant → datos mas limpios
4. Re-ejecutar analisis → inventory_schemas_clean.json v2
5. Revision humana → ajustes manuales
6. Subir version actualizada a Cloud Storage
7. Probar con el agente (api-maia)
8. Ajustar schemas segun feedback real de usuarios
```
