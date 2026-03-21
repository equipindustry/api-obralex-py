from pydantic import BaseModel


class DetectedMaterial(BaseModel):
    description: str
    quantity: float | None = None
    unit: str | None = None
    brand: str | None = None


class AnalyzeMaterialsRequest(BaseModel):
    materials_structured: list[DetectedMaterial]


class EnrichedProduct(BaseModel):
    original: str
    product: str | None = None
    brand: str | None = None
    unit: str | None = None
    quantity: float | None = None
    category: str | None = None
    subcategory: str | None = None
    schema_source: str
    required_fields: list[str]
    attributes: dict[str, str | None]
    missing_attributes: list[str]
    total_required_fields: int
    completion_percentage: float | None = None
    status: str
    match_id: str | None = None


class AnalyzeMaterialsResponse(BaseModel):
    products: list[EnrichedProduct]
