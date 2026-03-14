from google.cloud import discoveryengine_v1 as discoveryengine
from google.protobuf.json_format import MessageToDict
from dataclasses import dataclass, field
from typing import Any
import json


@dataclass
class InventorySearchResult:
    document_id: str
    relevance_score: float

    # Identificadores
    id: str = ""
    sku: str = ""
    sku_equip: str = ""
    sku_parent: str = ""

    # Producto
    product: str = ""
    description: str = ""
    brand: str = ""
    status: str = ""
    unity: str = ""
    stock: str = ""

    # Clasificacion
    category: str = ""
    subcategory: str = ""
    categories: list[str] = field(default_factory=list)

    # Precios
    currency: str = ""
    price: float = 0.0
    price_b2b_def: float = 0.0
    price_b2c_def: float = 0.0

    # Atributos
    variant: str = ""
    color: str = ""
    model: str = ""
    size: str = ""
    material: str = ""

    # Media
    image0: str = ""

    # Raw data
    raw: dict[str, Any] = field(default_factory=dict)


class VertexAISearchService:
    def __init__(
        self,
        project_id: str,
        location: str,
        datastore_id: str,
        collection: str = "default_collection",
    ):
        self.project_id = project_id
        self.location = location
        self.datastore_id = datastore_id
        self.collection = collection
        self._client = self._create_client()

    def _create_client(self) -> discoveryengine.SearchServiceClient:
        if self.location == "global":
            return discoveryengine.SearchServiceClient()

        api_endpoint = f"{self.location}-discoveryengine.googleapis.com"
        return discoveryengine.SearchServiceClient(
            client_options={"api_endpoint": api_endpoint}
        )

    @property
    def serving_config(self) -> str:
        return (
            f"projects/{self.project_id}/"
            f"locations/{self.location}/"
            f"collections/{self.collection}/"
            f"dataStores/{self.datastore_id}/"
            f"servingConfigs/default_search"
        )

    def search(
        self,
        query: str,
        page_size: int = 10,
        offset: int = 0,
    ) -> list[InventorySearchResult]:
        request = discoveryengine.SearchRequest(
            serving_config=self.serving_config,
            query=query,
            page_size=page_size,
            offset=offset,
        )

        response = self._client.search(request)
        return [self._parse_result(r) for r in response.results]

    def _parse_result(self, result) -> InventorySearchResult:
        struct_pb = discoveryengine.Document.pb(result.document).struct_data
        data = MessageToDict(struct_pb)
        return InventorySearchResult(
            document_id=result.document.id,
            relevance_score=getattr(result, "relevance_score", 0.0),
            id=data.get("id", ""),
            sku=data.get("sku", ""),
            sku_equip=data.get("sku_equip", ""),
            sku_parent=data.get("sku_parent", ""),
            product=data.get("product", ""),
            description=data.get("description", ""),
            brand=data.get("brand", ""),
            status=data.get("status", ""),
            unity=data.get("unity", ""),
            stock=data.get("stock", ""),
            category=data.get("category", ""),
            subcategory=data.get("subcategory", ""),
            categories=data.get("categories", []),
            currency=data.get("currency", ""),
            price=float(data.get("price", 0.0)),
            price_b2b_def=float(data.get("price_b2b_def", 0.0)),
            price_b2c_def=float(data.get("price_b2c_def", 0.0)),
            variant=data.get("variant", ""),
            color=data.get("color", ""),
            model=data.get("model", ""),
            size=data.get("size", ""),
            material=data.get("material", ""),
            image0=data.get("image0", ""),
            raw=data,
        )

    def search_with_summary(
        self,
        query: str,
        page_size: int = 10,
    ) -> tuple[str, list[InventorySearchResult]]:
        content_search_spec = discoveryengine.SearchRequest.ContentSearchSpec(
            summary_spec=discoveryengine.SearchRequest.ContentSearchSpec.SummarySpec(
                summary_result_count=page_size,
                include_citations=True,
            ),
            extractive_content_spec=discoveryengine.SearchRequest.ContentSearchSpec.ExtractiveContentSpec(
                max_extractive_answer_count=1,
            ),
        )

        request = discoveryengine.SearchRequest(
            serving_config=self.serving_config,
            query=query,
            page_size=page_size,
            content_search_spec=content_search_spec,
        )

        response = self._client.search(request)

        summary = ""
        if response.summary:
            summary = response.summary.summary_text

        results = [self._parse_result(r) for r in response.results]
        return summary, results
