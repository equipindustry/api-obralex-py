from fastapi import APIRouter

from src.models.materials import (
    AnalyzeMaterialsRequest,
    AnalyzeMaterialsResponse,
)
from src.services import VertexAISearchService, InventorySchemaService
from src.services.material_analyzer import MaterialAnalyzerService

from src.core.config import Config

router = APIRouter()

_search_service = VertexAISearchService(
    project_id=Config.GCP_PROJECT_ID,
    location=Config.VERTEX_SEARCH_LOCATION,
    datastore_id=Config.VERTEX_SEARCH_DATASTORE_ID,
    collection=Config.VERTEX_SEARCH_COLLECTION,
)

_schema_service = InventorySchemaService(search_service=_search_service)
_analyzer_service = MaterialAnalyzerService(
    schema_service=_schema_service,
    search_service=_search_service,
)


@router.post("/materials/analyze", response_model=AnalyzeMaterialsResponse)
async def analyze_materials(request: AnalyzeMaterialsRequest):
    products = _analyzer_service.analyze(
        [m.model_dump() for m in request.materials_structured]
    )
    return {"products": products}
