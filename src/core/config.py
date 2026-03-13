from dotenv import load_dotenv
import os

load_dotenv()


class Config:
    GOOGLE_APPLICATION_CREDENTIALS: str = os.getenv(
        "GOOGLE_APPLICATION_CREDENTIALS", ""
    )

    GCP_PROJECT_ID: str = "maia-466013"

    # Vertex AI Search
    VERTEX_SEARCH_LOCATION: str = os.getenv("VERTEX_SEARCH_LOCATION", "")
    VERTEX_SEARCH_DATASTORE_ID: str = os.getenv("VERTEX_SEARCH_DATASTORE_ID", "")
    VERTEX_SEARCH_COLLECTION: str = os.getenv("VERTEX_SEARCH_COLLECTION", "")

    # Cloud Storage
    GCS_BUCKET_KNOWLEDGE: str = os.getenv("GCS_BUCKET_KNOWLEDGE", "")
    GCS_INVENTORY_SCHEMAS_PATH: str = os.getenv("GCS_INVENTORY_SCHEMAS_PATH", "")
    GCS_TTL_SECONDS: int = 3600
