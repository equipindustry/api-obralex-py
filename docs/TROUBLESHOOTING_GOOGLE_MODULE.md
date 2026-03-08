# Troubleshooting: Error "ModuleNotFoundError: No module named 'google'"

## Problema

Al intentar ejecutar el proyecto con `uvicorn`, se obtenía el siguiente error:

```
ModuleNotFoundError: No module named 'google'
  File "/Users/alexisvasquez/Documents/EI/Backend/api-obralex-py/src/services/vertex_ai_search.py", line 1, in <module>
    from google.cloud import discoveryengine_v1 as discoveryengine
```

Este error ocurría a pesar de tener el entorno virtual activado y el paquete `google-cloud-discoveryengine==0.17.0` instalado en `requirements.txt`.

## Causa Raíz

El problema tenía dos causas principales:

### 1. Paquete conflictivo en `requirements.txt`

El archivo `requirements.txt` contenía el paquete `google==3.0.0`, que **NO** es parte de las librerías oficiales de Google Cloud. Este paquete estaba interfiriendo con el namespace `google.cloud`, impidiendo que Python pudiera importar correctamente `google.cloud.discoveryengine_v1`.

```txt
# requirements.txt (INCORRECTO)
google-cloud-discoveryengine==0.17.0
google==3.0.0  # <-- Este paquete causaba el conflicto
```

### 2. Entorno virtual corrupto

El entorno virtual (`.venv`) tenía una configuración incorrecta en su `sys.path`, causando que Python buscara módulos en el siguiente orden:

1. `/Library/Frameworks/Python.framework/Versions/3.11/lib/python311.zip` (Python del sistema)
2. `/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11` (Python del sistema)
3. `/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/lib-dynload` (Python del sistema)
4. `/Users/alexisvasquez/Documents/EI/Backend/api-obralex-py/.venv/lib/python3.11/site-packages` (Entorno virtual)

Esto hacía que Python buscara primero en el sistema antes que en el entorno virtual, ignorando los paquetes instalados en `.venv`.

## Solución Aplicada

### Paso 1: Eliminar el paquete conflictivo

Se eliminó `google==3.0.0` del archivo `requirements.txt`:

```txt
# requirements.txt (CORRECTO)
fastapi==0.128.0
uvicorn[standard]==0.40.0
gunicorn==25.1.0
pydantic==2.12.5
black==26.1.0
google-cloud-discoveryengine==0.17.0
python-dotenv==1.2.1
```

### Paso 2: Recrear el entorno virtual

Se eliminó completamente el entorno virtual corrupto y se creó uno nuevo desde cero:

```bash
# Eliminar entorno virtual anterior
rm -rf .venv

# Crear nuevo entorno virtual
python3 -m venv .venv

# Activar el entorno virtual
source .venv/bin/activate

# Actualizar pip
pip install --upgrade pip

# Instalar dependencias
pip install -r requirements.txt
```

### Paso 3: Limpiar caché de Python

Se eliminaron todos los archivos de caché de Python que podrían contener referencias al módulo corrupto:

```bash
# Eliminar directorios __pycache__
find . -type d -name __pycache__ -exec rm -rf {} +

# Eliminar archivos .pyc
find . -name "*.pyc" -delete
```

### Paso 4: Verificar la instalación

Se verificó que el módulo se importa correctamente:

```bash
python -c "import google.cloud.discoveryengine_v1; print('Módulo importado correctamente')"
```

## Cómo ejecutar el proyecto

Una vez aplicada la solución, el proyecto se puede ejecutar normalmente:

```bash
# Activar el entorno virtual
source .venv/bin/activate

# Ejecutar el servidor con reload
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## Prevención

Para evitar este problema en el futuro:

1. **Nunca instalar el paquete `google`**: Este paquete no es oficial de Google Cloud y causa conflictos con los paquetes legítimos como `google-cloud-*`.

2. **Verificar `requirements.txt`**: Asegurarse de que solo contenga paquetes oficiales de Google Cloud que siguen el patrón `google-cloud-{servicio}`.

3. **Recrear el entorno virtual si hay problemas**: Si el entorno virtual presenta comportamientos extraños, es mejor recrearlo desde cero que intentar repararlo.

4. **Usar siempre el entorno virtual**: Verificar que el entorno virtual esté activado antes de ejecutar el proyecto con:
   ```bash
   which python  # Debe apuntar a .venv/bin/python
   which pip     # Debe apuntar a .venv/bin/pip
   ```

## Paquetes de Google Cloud correctos

Para trabajar con servicios de Google Cloud, usar siempre los paquetes oficiales:

- `google-cloud-storage` - Cloud Storage
- `google-cloud-firestore` - Firestore
- `google-cloud-bigquery` - BigQuery
- `google-cloud-discoveryengine` - Vertex AI Search (Discovery Engine)
- `google-cloud-aiplatform` - Vertex AI
- etc.

**NUNCA usar**:
- `google` - Paquete no oficial que causa conflictos
- `googleapis` - Usar `google-api-python-client` en su lugar si se necesita

## Referencias

- [Google Cloud Python Client Libraries](https://cloud.google.com/python/docs/reference)
- [Python Virtual Environments](https://docs.python.org/3/library/venv.html)
