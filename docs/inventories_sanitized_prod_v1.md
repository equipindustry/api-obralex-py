# Inventarios Sanitized Prod v1

Resumen del dataset `inventories_sanitized_prod_v1.xlsx` usado como fuente de datos en Vertex AI Search.

## Datos generales

- **Total de registros:** 3,091
- **Columnas:** 39
- **Marcas:** 49

## Columnas del dataset

| Columna | Descripcion |
|---------|-------------|
| `id` | ID del inventario (MongoDB ObjectId) |
| `sku` | SKU del proveedor |
| `sku_equip` | SKU interno de Equip |
| `product` | Nombre del producto |
| `description` | Descripcion del producto |
| `brand` | Marca |
| `unity` | Unidad de medida (UND, KG, MTS, M2, etc.) |
| `stock` | Stock disponible |
| `categories` | Categoria principal |
| `subcategories` | Subcategoria |
| `deepcategories` | Categoria profunda (generalmente vacia) |
| `color` | Color (57% de registros) |
| `presentation` | Presentacion (54%) |
| `type` | Tipo (29%) |
| `model` | Modelo (24%) |
| `size` | Tamano (11%) |
| `measure` | Medida (43%) |
| `thickness` | Espesor (4%) |
| `weight` | Peso (37%) |
| `volume` | Volumen (3%) |
| `angle` | Angulo (4%) |
| `fabrication` | Fabricacion (4%) |
| `material` | Material (6%) |
| `reference` | Referencia (0% - sin datos) |
| `price` | Precio base |
| `price_b2b_def` | Precio B2B default |
| `price_b2b_inf` | Precio B2B inferior |
| `price_b2c_def` | Precio B2C default |
| `price_b2c_inf` | Precio B2C inferior |
| `currency` | Moneda (USD) |
| `image0` - `image3` | URLs de imagenes |
| `techsheet_url` | URL de ficha tecnica |
| `account_id` | ID de la cuenta del proveedor |
| `process` | Estado del proceso |
| `synced_at` | Fecha de sincronizacion |
| `source_updated_at` | Fecha de actualizacion en origen |

## Categorias y subcategorias

| Categoria | Subcategorias | Items |
|-----------|---------------|-------|
| Tuberias, Valvulas y Conexiones | Agua, Desague, Electrica, Tuberia Electrica, UF | 981 |
| Electricidad | Cables | 658 |
| Pinturas | Industriales, Pinturas Decorativas, Pinturas Especiales, Pinturas Industriales, Resanar y Empastar | 581 |
| Equipos Proteccion Personal | Arneses, Bioseguridad, Calzado de Seguridad, Cascos, Guantes, Lentes, Proteccion Auditiva, Ropa Industrial | 349 |
| Quimicos para Construccion | Aditivos para Concreto, Desmoldantes, Epoxicos/Morteros/Grouting, Impermeabilizantes, Selladores de Juntas, Separadores | 176 |
| Banos y Cocinas | Banos, Cocinas, Duchas | 165 |
| Ladrillos | Acabados, Arcilla, Enchapes, Muros y tabiqueria, Placas, Techos | 62 |
| Pisos y Pegamentos | Ceramicos, Pegamentos y Fraguas, Porcelanatos | 53 |
| Acero | Alambres, Barras de Acero, Clavos | 33 |
| Ferreteria | Solventes | 24 |
| Embolsados | Cemento, Mortero | 8 |
| Herramientas | Herramientas inalambricas | 1 |

## Marcas principales

Aceros Arequipa, American Colors, Bonn, Bosch, CELSA, Celima, Centelsa, CPP, Fast, Indeco, Koplast, Lark, Pavco, Piramide, Plastica, Porcelanite, Rotoplas, San Lorenzo, Sika, Siderperu, Sol, Tekno, Vainsa, Z Aditivos, entre otras.

## Unidades de medida

| Unidad | Descripcion | Categorias principales |
|--------|-------------|----------------------|
| UND | Unidad | Tuberias, Pisos, Banos, Herramientas |
| KG | Kilogramo | Acero, Quimicos |
| MTS | Metros | Pisos, Electricidad, Quimicos |
| M2 | Metro cuadrado | Pisos y Pegamentos |
| RLL | Rollo | Electricidad |
| MLL | Millar | Ladrillos |
| CAJ | Caja | Acero, EPP |
| PAR | Par | EPP (calzado, guantes) |
| KIT | Kit | Pinturas |
| LT | Litro | Quimicos |
| GR | Gramo | Quimicos |
| ML | Mililitro | Quimicos |

---

## Pruebas para endpoint `/api/v1/inventories/schema`

Queries de prueba organizados por categoria para validar que el endpoint devuelve los `required_fields` y `field_options` correctos.

### Acero

| # | Query | Categoria esperada | Subcategoria esperada |
|---|-------|-------------------|----------------------|
| 1 | `fierro de construccion 1/2` | Acero | Barras de Acero |
| 2 | `barra de acero 12mm` | Acero | Barras de Acero |
| 3 | `alambre negro recocido` | Acero | Alambres |
| 4 | `clavos 2 pulgadas` | Acero | Clavos |

### Tuberias, Valvulas y Conexiones

| # | Query | Categoria esperada | Subcategoria esperada |
|---|-------|-------------------|----------------------|
| 5 | `tubo de agua 1 pulgada` | Tuberias, Valvulas y Conexiones | Agua |
| 6 | `codo desague 4 pulgadas` | Tuberias, Valvulas y Conexiones | Desague |
| 7 | `tuberia electrica sap 3/4` | Tuberias, Valvulas y Conexiones | Tuberia Electrica |
| 8 | `union simple agua` | Tuberias, Valvulas y Conexiones | Agua |
| 9 | `yee desague 2 pulgadas` | Tuberias, Valvulas y Conexiones | Desague |
| 10 | `tubo uf 200mm naranja` | Tuberias, Valvulas y Conexiones | UF |

### Electricidad

| # | Query | Categoria esperada | Subcategoria esperada |
|---|-------|-------------------|----------------------|
| 11 | `cable electrico 10 awg` | Electricidad | Cables |
| 12 | `cable indeco thw 14` | Electricidad | Cables |
| 13 | `cable vulcanizado 3x10` | Electricidad | Cables |

### Pinturas

| # | Query | Categoria esperada | Subcategoria esperada |
|---|-------|-------------------|----------------------|
| 14 | `pintura latex blanco` | Pinturas | Pinturas Decorativas |
| 15 | `anticorrosivo gris` | Pinturas | Pinturas Especiales |
| 16 | `temple blanco 25 kg` | Pinturas | Resanar y Empastar |
| 17 | `imprimante blanco` | Pinturas | Resanar y Empastar |
| 18 | `pintura epoxico` | Pinturas | Industriales |

### Equipos de Proteccion Personal

| # | Query | Categoria esperada | Subcategoria esperada |
|---|-------|-------------------|----------------------|
| 19 | `casco de seguridad amarillo` | Equipos Proteccion Personal | Cascos |
| 20 | `guantes dielectricos` | Equipos Proteccion Personal | Guantes |
| 21 | `botas de seguridad` | Equipos Proteccion Personal | Calzado de Seguridad |
| 22 | `lentes de seguridad` | Equipos Proteccion Personal | Lentes |
| 23 | `arnes 3 anillos` | Equipos Proteccion Personal | Arneses |
| 24 | `protector de oidos` | Equipos Proteccion Personal | Proteccion Auditiva |

### Quimicos para Construccion

| # | Query | Categoria esperada | Subcategoria esperada |
|---|-------|-------------------|----------------------|
| 25 | `aditivo para concreto sika` | Quimicos para Construccion | Aditivos para Concreto |
| 26 | `impermeabilizante para techo` | Quimicos para Construccion | Impermeabilizantes para Estructuras |
| 27 | `desmoldante para encofrado` | Quimicos para Construccion | Desmoldantes |
| 28 | `sellador de juntas` | Quimicos para Construccion | Selladores de Juntas |

### Banos y Cocinas

| # | Query | Categoria esperada | Subcategoria esperada |
|---|-------|-------------------|----------------------|
| 29 | `tanque de agua rotoplas` | Banos y Cocinas | Banos |
| 30 | `terma electrica instantanea` | Banos y Cocinas | Duchas |
| 31 | `lavadero de cocina inox` | Banos y Cocinas | Cocinas |

### Ladrillos

| # | Query | Categoria esperada | Subcategoria esperada |
|---|-------|-------------------|----------------------|
| 32 | `ladrillo king kong` | Ladrillos | Arcilla |
| 33 | `bloqueta de concreto 12` | Ladrillos | Muros y tabiqueria |
| 34 | `fachaleta decorativa` | Ladrillos | Enchapes y decorativos |
| 35 | `bovedilla para techo` | Ladrillos | Techos |

### Pisos y Pegamentos

| # | Query | Categoria esperada | Subcategoria esperada |
|---|-------|-------------------|----------------------|
| 36 | `ceramico para piso blanco` | Pisos y Pegamentos | Ceramicos |
| 37 | `porcelanato 60x60 gris` | Pisos y Pegamentos | Porcelanatos |
| 38 | `pegamento para ceramico` | Pisos y Pegamentos | Pegamentos y Fraguas |

### Embolsados

| # | Query | Categoria esperada | Subcategoria esperada |
|---|-------|-------------------|----------------------|
| 39 | `cemento sol tipo 1` | Embolsados | Cemento |
| 40 | `mortero para muros` | Embolsados | Mortero |

### Ferreteria

| # | Query | Categoria esperada | Subcategoria esperada |
|---|-------|-------------------|----------------------|
| 41 | `pegamento pvc` | Ferreteria | Solventes |

### Queries ambiguos / lenguaje natural (simulan como habla un cliente real)

| # | Query | Nota |
|---|-------|------|
| 42 | `necesito fierro para columnas` | Deberia resolver a Acero > Barras de Acero |
| 43 | `tubos para baño` | Podria ser Tuberias > Agua o Desague |
| 44 | `algo para pintar paredes` | Deberia resolver a Pinturas > Pinturas Decorativas |
| 45 | `material para pegar mayolica` | Deberia resolver a Pisos y Pegamentos > Pegamentos y Fraguas |
| 46 | `proteccion para los ojos` | Deberia resolver a EPP > Lentes |
| 47 | `quiero piso de madera` | Deberia resolver a Pisos y Pegamentos > Porcelanatos (tablon madera) |
| 48 | `necesito cable para luz` | Deberia resolver a Electricidad > Cables |
| 49 | `que tienen para impermeabilizar` | Deberia resolver a Quimicos > Impermeabilizantes |
| 50 | `busco cemento` | Deberia resolver a Embolsados > Cemento |
