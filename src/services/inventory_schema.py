from google.cloud import storage
import logging
import json
import time

from src.services.vertex_ai_search import VertexAISearchService

from src.core.config import Config

logger = logging.getLogger(__name__)

DEFAULT_SCHEMA = {
    "required_fields": ["especificacion", "cantidad"],
    "field_options": {
        "especificacion": {
            "type": "text",
            "question": "Puedes dar mas detalles sobre lo que necesitas?",
        },
        "cantidad": {
            "type": "number",
            "unit": "unidades",
            "question": "Cuantas unidades necesitas?",
        },
    },
}


class InventorySchemaService:
    def __init__(self, search_service: VertexAISearchService):
        self.search_service = search_service
        self._bucket_name = Config.GCS_BUCKET_KNOWLEDGE
        self._blob_path = Config.GCS_INVENTORY_SCHEMAS_PATH
        self._ttl = Config.GCS_TTL_SECONDS
        self._cache: dict | None = None
        self._loaded_at: float = 0
        self._gcs_client = storage.Client()

    # --- Cache GCS ---

    def _is_expired(self) -> bool:
        return (time.time() - self._loaded_at) > self._ttl

    def _load_from_gcs(self) -> None:
        bucket = self._gcs_client.bucket(self._bucket_name)
        blob = bucket.blob(self._blob_path)
        content = blob.download_as_text()
        self._cache = json.loads(content)
        self._loaded_at = time.time()
        logger.info(
            "Schemas loaded from gs://%s/%s", self._bucket_name, self._blob_path
        )

    def _get_schemas(self) -> dict:
        if self._cache is None or self._is_expired():
            try:
                self._load_from_gcs()
            except Exception:
                logger.exception("Failed to load schemas from GCS")
                if self._cache is not None:
                    return self._cache
                raise
        return self._cache

    def _get_subcategory_schema(self, subcategory: str) -> dict | None:
        return self._get_schemas().get("subcategory_schemas", {}).get(subcategory)

    def _get_category_schema(self, category: str) -> dict | None:
        return self._get_schemas().get("category_schemas", {}).get(category)

    # --- Public API ---

    def get_schema_for_query(self, query: str) -> dict:
        results = self.search_service.search(query=query, page_size=1)
        if not results:
            return {
                "category": None,
                "subcategory": None,
                "inventory_hint": None,
                "required_fields": DEFAULT_SCHEMA["required_fields"],
                "field_options": DEFAULT_SCHEMA["field_options"],
                "schema_source": "default",
            }

        product = results[0]
        category = product.category
        subcategory = product.subcategory

        schema = self._get_subcategory_schema(subcategory)
        source = "subcategory"

        if not schema:
            schema = self._get_category_schema(category)
            source = "category"

        if not schema:
            schema = DEFAULT_SCHEMA
            source = "default"

        return {
            "category": category,
            "subcategory": subcategory,
            "inventory_hint": product.product,
            "required_fields": schema["required_fields"],
            "field_options": schema["field_options"],
            "schema_source": source,
        }

    def reload(self) -> dict:
        self._load_from_gcs()
        return self._cache

    def status(self) -> dict:
        schemas = self._cache or {}
        return {
            "loaded": self._cache is not None,
            "loaded_at": self._loaded_at,
            "ttl_seconds": self._ttl,
            "subcategory_count": len(schemas.get("subcategory_schemas", {})),
            "category_count": len(schemas.get("category_schemas", {})),
            "metadata": schemas.get("metadata"),
        }
