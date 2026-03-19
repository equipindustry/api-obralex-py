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
        "sku_equip": result.sku_equip,
        "product": result.product,
        "description": result.description,
        "brand": result.brand,
        "unity": result.unity,
        "stock": result.stock,
        "category": result.category,
        "subcategory": result.subcategory,
        "cluster": result.cluster,
        "compilation": result.compilation,
        "currency": result.currency,
        "price": result.price,
        "price_b2b_def": result.price_b2b_def,
        "price_b2b_inf": result.price_b2b_inf,
        "price_b2c_def": result.price_b2c_def,
        "price_b2c_inf": result.price_b2c_inf,
        "color": result.color,
        "presentation": result.presentation,
        "type": result.type,
        "model": result.model,
        "size": result.size,
        "measure": result.measure,
        "thickness": result.thickness,
        "weight": result.weight,
        "volume": result.volume,
        "angle": result.angle,
        "fabrication": result.fabrication,
        "material": result.material,
        "reference": result.reference,
        "image0": result.image0,
        "image1": result.image1,
        "image2": result.image2,
        "image3": result.image3,
        "techsheet_url": result.techsheet_url,
        "keywords": result.keywords,
        "account_id": result.account_id,
        "synced_at": result.synced_at,
    }
