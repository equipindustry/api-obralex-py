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

    def _normalize_choice_value(
        self, value: str, field_options: dict, field_name: str
    ) -> str | None:
        """Normalize a user-provided value against the schema's choice options.

        For fields with type "choice", performs case-insensitive matching.
        Returns the canonical option if matched, None if no match found.
        For non-choice fields, returns the value as-is.
        """
        field_def = field_options.get(field_name)
        if not field_def or field_def.get("type") != "choice":
            return value

        options = field_def.get("options", [])
        if not options:
            return value

        # Exact match first
        if value in options:
            return value

        # Case-insensitive match
        value_lower = value.strip().lower()
        for option in options:
            if option.strip().lower() == value_lower:
                return option

        # No match — treat as invalid
        logger.debug(
            "Value '%s' for field '%s' does not match any option: %s",
            value,
            field_name,
            options,
        )
        return None

    def _validate_match(
        self,
        inventory: InventorySearchResult | None,
        user_attrs: dict[str, str | None],
        required_fields: list[str],
    ) -> bool:
        """Validate that the Vertex AI Search result matches the user's attributes.

        Compares each user-provided attribute against the inventory's value.
        Returns False if any attribute contradicts the inventory (case-insensitive).
        """
        if not inventory:
            return False

        for field_name in required_fields:
            user_val = user_attrs.get(field_name)
            if not user_val:
                continue
            inv_val = getattr(inventory, field_name, None)
            if not inv_val:
                continue
            if str(user_val).strip().lower() not in str(inv_val).strip().lower():
                logger.debug(
                    "Match validation failed: field '%s' user='%s' inventory='%s'",
                    field_name,
                    user_val,
                    inv_val,
                )
                return False

        return True

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
        field_options = schema.get("field_options", {})

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

        # Compare user-provided attributes against required_fields.
        # Only attributes explicitly sent by the caller count as "filled".
        # For choice fields, normalize values case-insensitively against
        # the schema options. Invalid values are treated as missing.
        user_attrs = material.get("attributes") or {}
        attributes: dict[str, str | None] = {}
        for f in required_fields:
            raw_value = user_attrs.get(f)
            if raw_value:
                attributes[f] = self._normalize_choice_value(
                    raw_value, field_options, f
                )
            else:
                attributes[f] = None

        missing = [f for f in required_fields if not attributes.get(f)]
        total = len(required_fields)
        filled = total - len(missing)
        completion = round((filled / total) * 100, 1) if total > 0 else 100.0
        status = "complete" if not missing else "incomplete"

        # Assign match_id only if complete AND the inventory actually matches
        # the user's attributes. Prevents false matches when Vertex returns
        # a semantically close but different product.
        match_id = None
        if status == "complete" and inventory:
            if self._validate_match(inventory, attributes, required_fields):
                match_id = inventory.id or inventory.document_id
            else:
                status = "review"

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
