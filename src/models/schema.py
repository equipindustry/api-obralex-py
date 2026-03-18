from pydantic import BaseModel


class FieldOption(BaseModel):
    type: str
    question: str
    options: list[str] | None = None
    unit: str | None = None


class InventorySchemaResponse(BaseModel):
    category: str | None
    subcategory: str | None
    inventory_hint: str | None
    required_fields: list[str]
    field_options: dict[str, FieldOption]
    schema_source: str
    available_subcategories: list[str] | None = None


class SchemaStatusResponse(BaseModel):
    loaded: bool
    loaded_at: float
    ttl_seconds: int
    subcategory_count: int
    category_count: int
    metadata: dict | None
