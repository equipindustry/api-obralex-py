import logging

from src.services.inventory_schema import InventorySchemaService
from src.services.vertex_ai_search import VertexAISearchService, InventorySearchResult

logger = logging.getLogger(__name__)

ATTRIBUTE_FIELDS = [
    "color",
    "presentation",
    "type",
    "model",
    "size",
    "measure",
    "thickness",
    "weight",
    "volume",
    "angle",
    "fabrication",
    "material",
    "reference",
    "cluster",
    "compilation",
]


class MaterialAnalyzerService:
    def __init__(
        self,
        schema_service: InventorySchemaService,
        search_service: VertexAISearchService,
    ):
        self._schema_service = schema_service
        self._search_service = search_service

    def analyze(self, materials: list[dict]) -> list[dict]:
        return [self._analyze_one(m) for m in materials]

    def _analyze_one(self, material: dict) -> dict:
        description = material["description"]
        quantity = material.get("quantity")
        unit = material.get("unit")
        brand = material.get("brand")

        schema, inventory = self._schema_service.get_schema_and_inventory(description)

        category = schema.get("category")
        subcategory = schema.get("subcategory")
        schema_source = schema.get("schema_source", "default")
        inventory_hint = schema.get("inventory_hint")
        required_fields = schema.get("required_fields", [])

        if schema_source == "default":
            return {
                "original": description,
                "product": inventory_hint,
                "brand": brand,
                "unit": unit,
                "quantity": quantity,
                "category": category,
                "subcategory": None,
                "schema_source": schema_source,
                "required_fields": [],
                "attributes": {},
                "missing_attributes": [],
                "total_required_fields": 0,
                "completion_percentage": None,
                "status": "detected",
                "match_id": None,
            }

        # Extract attributes from Vertex AI Search result
        attributes = self._extract_attributes_from_inventory(
            inventory, required_fields
        )
        missing = [f for f in required_fields if not attributes.get(f)]
        total = len(required_fields)
        filled = total - len(missing)
        completion = round((filled / total) * 100, 1) if total > 0 else 100.0
        status = "complete" if not missing else "incomplete"

        match_id = None
        if status == "complete" and inventory:
            match_id = inventory.id or inventory.document_id

        return {
            "original": description,
            "product": inventory_hint,
            "brand": brand,
            "unit": unit,
            "quantity": quantity,
            "category": category,
            "subcategory": subcategory,
            "schema_source": schema_source,
            "required_fields": required_fields,
            "attributes": attributes,
            "missing_attributes": missing,
            "total_required_fields": total,
            "completion_percentage": completion,
            "status": status,
            "match_id": match_id,
        }

    def _extract_attributes_from_inventory(
        self,
        inventory: InventorySearchResult | None,
        required_fields: list[str],
    ) -> dict[str, str | None]:
        """Read attribute values directly from the Vertex AI Search result.

        Vertex already resolves semantic matching (e.g. "2 pulgadas" → measure: '2"'),
        so we just read the fields from the inventory result instead of parsing the
        description string.
        """
        attributes: dict[str, str | None] = {}

        for field_name in required_fields:
            value = None
            if inventory:
                raw_value = getattr(inventory, field_name, "")
                if raw_value:
                    value = raw_value
            attributes[field_name] = value

        return attributes
