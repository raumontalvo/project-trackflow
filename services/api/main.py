"""FastAPI application for TrackFlow services."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.api.routes.agent import router as agent_router
from services.api.routes.knowledge import router as knowledge_router
from services.api.routes.incidents import router as incidents_router
from services.api.routes.inventory import router as inventory_router


app = FastAPI(
    title="TrackFlow API",
    version="0.1.0",
    description="TrackFlow operational and commercial services.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(knowledge_router)
app.include_router(agent_router)
app.include_router(incidents_router)
app.include_router(inventory_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Basic service health endpoint."""
    return {"status": "ok"}