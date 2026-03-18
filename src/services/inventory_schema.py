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
        self._build_category_schemas()
        self._loaded_at = time.time()
        logger.info(
            "Schemas loaded from gs://%s/%s (%d subcategories, %d categories)",
            self._bucket_name,
            self._blob_path,
            len(self._cache.get("subcategory_schemas", {})),
            len(self._cache.get("category_schemas", {})),
        )

    def _build_category_schemas(self) -> None:
        """Build category_schemas from subcategory_schemas if not present in the JSON."""
        if self._cache.get("category_schemas"):
            return

        sub_schemas = self._cache.get("subcategory_schemas", {})
        category_map: dict[str, list[str]] = {}
        for sub_name, sub_schema in sub_schemas.items():
            cat = sub_schema.get("category")
            if cat:
                category_map.setdefault(cat, []).append(sub_name)

        category_schemas = {}
        for cat, subcategories in category_map.items():
            all_fields: dict[str, dict] = {}
            required_set: set[str] = set()
            for sub_name in subcategories:
                sub = sub_schemas[sub_name]
                required_set.update(sub.get("required_fields", []))
                for field_name, field_def in sub.get("field_options", {}).items():
                    if field_name not in all_fields:
                        all_fields[field_name] = {
                            "type": field_def["type"],
                            "question": field_def["question"],
                        }
                        if field_def.get("options"):
                            all_fields[field_name]["options"] = list(field_def["options"])
                    elif field_def.get("options"):
                        existing = all_fields[field_name]
                        if existing.get("options") is not None:
                            merged = set(existing["options"]) | set(field_def["options"])
                            existing["options"] = sorted(merged)
                        else:
                            existing["type"] = "choice"
                            existing["options"] = list(field_def["options"])

            category_schemas[cat] = {
                "required_fields": sorted(required_set),
                "field_options": all_fields,
                "subcategories": sorted(subcategories),
            }

        self._cache["category_schemas"] = category_schemas
        logger.info("Built category_schemas for %d categories from subcategory data", len(category_schemas))

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

        result = {
            "category": category,
            "subcategory": subcategory,
            "inventory_hint": product.product,
            "required_fields": schema["required_fields"],
            "field_options": schema["field_options"],
            "schema_source": source,
        }

        if source == "category" and schema.get("subcategories"):
            result["available_subcategories"] = schema["subcategories"]

        return result

    def reload(self) -> dict:
        self._load_from_gcs()
        return self._cache

    def get_catalog(self) -> dict:
        schemas = self._get_schemas()
        sub_schemas = schemas.get("subcategory_schemas", {})

        category_map: dict[str, list[dict]] = {}
        for sub_name, sub_schema in sub_schemas.items():
            cat = sub_schema.get("category", "Sin categoría")
            category_map.setdefault(cat, []).append(
                {
                    "subcategory": sub_name,
                    "required_fields": sub_schema.get("required_fields", []),
                    "field_options": sub_schema.get("field_options", {}),
                }
            )

        for subs in category_map.values():
            subs.sort(key=lambda s: s["subcategory"])

        categories = sorted(
            [
                {"category": cat, "subcategories": subs}
                for cat, subs in category_map.items()
            ],
            key=lambda c: c["category"],
        )

        return {
            "total_categories": len(categories),
            "total_subcategories": len(sub_schemas),
            "categories": categories,
        }

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
