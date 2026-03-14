from pydantic import BaseModel

from src.services import InventorySearchResult


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[dict]


class SearchWithSummaryResponse(BaseModel):
    query: str
    summary: str
    total: int
    results: list[dict]


def inventory_result_to_dict(result: InventorySearchResult) -> dict:
    return {
        "document_id": result.document_id,
        "relevance_score": result.relevance_score,
        "id": result.id,
        "sku": result.sku,
        "sku_equip": result.sku_equip,
        "sku_parent": result.sku_parent,
        "product": result.product,
        "description": result.description,
        "brand": result.brand,
        "status": result.status,
        "unity": result.unity,
        "stock": result.stock,
        "category": result.category,
        "subcategory": result.subcategory,
        "currency": result.currency,
        "price": result.price,
        "price_b2b_def": result.price_b2b_def,
        "price_b2c_def": result.price_b2c_def,
        "variant": result.variant,
        "color": result.color,
        "model": result.model,
        "size": result.size,
        "material": result.material,
        "image0": result.image0,
    }
