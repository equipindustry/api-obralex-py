from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
import uvicorn

from src.api.health import router as health_router
from src.api.search import router as search_router
from src.api.schema import router as schema_router
from src.api.materials import router as materials_router

app = FastAPI(
    title="Obralex API",
    description="API for functions MCP",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1", tags=["health"])
app.include_router(search_router, prefix="/api/v1", tags=["search"])
app.include_router(schema_router, prefix="/api/v1", tags=["schemas"])
app.include_router(materials_router, prefix="/api/v1", tags=["materials"])


@app.get("/")
async def root():
    return {"message": "Obralex API"}


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=True,
    )
