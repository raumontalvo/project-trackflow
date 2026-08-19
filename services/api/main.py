"""FastAPI application for TrackFlow services."""

import os
import sys
import tempfile
from pathlib import Path

from celery.result import AsyncResult
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from shared.incident_analysis.exporter import export_results_to_csv
from services.api.auth import get_current_user
from services.api.database import create_db_and_tables
from services.api.routes.agent import router as agent_router
from services.api.routes.auth_routes import router as auth_router
from services.api.routes.chat import router as chat_router
from services.api.routes.incidents import router as incidents_router
from services.api.routes.inventory import router as inventory_router
from services.api.routes.knowledge import router as knowledge_router
from services.api.routes.notifications import router as notifications_router
from services.api.routes.rfp_intake import router as rfp_intake_router
from services.api.routes.suppliers import router as suppliers_router
from services.api.routes.telemetry import router as telemetry_router
from services.api.routes.users_routes import router as users_router
from services.celery_app import celery_app
from services.tasks import analyze_incidents_task

app = FastAPI(
    title="TrackFlow API",
    version="0.1.0",
    description="TrackFlow operational and commercial services.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LAST_RESULTS = None

app.include_router(agent_router)
app.include_router(chat_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(suppliers_router)
app.include_router(incidents_router)
app.include_router(inventory_router)
app.include_router(telemetry_router)
app.include_router(knowledge_router)
app.include_router(rfp_intake_router)
app.include_router(notifications_router)


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


@app.get("/")
def health_check():
    return {"status": "ok", "service": "TrackFlow API"}


@app.get("/health")
def health() -> dict[str, str]:
    """Basic service health endpoint."""
    return {"status": "ok"}


@app.post(
    "/api/incidents/analyze",
    dependencies=[Depends(get_current_user)],
    status_code=status.HTTP_202_ACCEPTED,
)
async def analyze_incidents(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed.")

    task_data_dir = Path(os.getenv("TASK_DATA_DIR", tempfile.gettempdir()))
    task_data_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".csv",
        dir=task_data_dir,
    ) as temp_file:
        content = await file.read()
        temp_file.write(content)
        temp_path = temp_file.name

    try:
        task = analyze_incidents_task.delay(temp_path)
    except Exception:
        Path(temp_path).unlink(missing_ok=True)
        raise HTTPException(
            status_code=503,
            detail="The analysis queue is temporarily unavailable.",
        )

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "task_id": task.id,
            "status": "pending",
        },
    )


@app.get("/tasks/{task_id}")
def get_task_status(task_id: str):
    task = AsyncResult(task_id, app=celery_app)

    state_mapping = {
        "PENDING": "pending",
        "RECEIVED": "pending",
        "STARTED": "started",
        "RETRY": "started",
        "SUCCESS": "success",
        "FAILURE": "failure",
        "REVOKED": "failure",
    }

    response = {
        "task_id": task_id,
        "status": state_mapping.get(task.state, task.state.lower()),
        "result": None,
    }

    if task.successful():
        response["result"] = task.result
    elif task.failed():
        response["result"] = {
            "error": str(task.result),
        }

    return response


@app.get("/api/incidents/results/export", dependencies=[Depends(get_current_user)])
def export_results():
    if LAST_RESULTS is None:
        raise HTTPException(status_code=404, detail="No analysis results available.")

    output_path = os.path.join(tempfile.gettempdir(), "trackflow-results.csv")

    try:
        export_results_to_csv(LAST_RESULTS, output_path)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="We could not export the analysis results right now. Please try again later.",
        )

    return FileResponse(
        output_path,
        media_type="text/csv",
        filename="trackflow-results.csv",
    )
