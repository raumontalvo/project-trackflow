import os
import sys
import tempfile

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from shared.incident_analysis.analyzer import analyze_csv
from shared.incident_analysis.exporter import export_results_to_csv
from services.api.auth import get_current_user
from services.api.database import create_db_and_tables
from services.api.routes.auth_routes import router as auth_router
from services.api.routes.incidents import router as incidents_router
from services.api.routes.inventory import router as inventory_router
from services.api.routes.suppliers import router as suppliers_router
from services.api.routes.users_routes import router as users_router

app = FastAPI(title="TrackFlow Incident Analyzer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LAST_RESULTS = None

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(suppliers_router)
app.include_router(incidents_router)
app.include_router(inventory_router)


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


@app.get("/")
def health_check():
    return {"status": "ok", "service": "TrackFlow Incident Analyzer API"}


@app.post("/api/incidents/analyze", dependencies=[Depends(get_current_user)])
async def analyze_incidents(file: UploadFile = File(...)):
    global LAST_RESULTS

    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed.")

    temp_path = ""

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temp_file:
            temp_path = temp_file.name
            content = await file.read()
            temp_file.write(content)

        results = analyze_csv(temp_path)
        LAST_RESULTS = results
        return results

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="The CSV file could not be analyzed. Please check the file format and try again.",
        )

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="We could not analyze the file right now. Please try again later.",
        )

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


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
