import os
import sys
import tempfile

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from shared.incident_analysis.analyzer import analyze_csv
from shared.incident_analysis.exporter import export_results_to_csv
from services.api.routes.suppliers import router as suppliers_router


app = FastAPI(title="TrackFlow Incident Analyzer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LAST_RESULTS = None

app.include_router(suppliers_router)


@app.get("/")
def health_check():
    return {"status": "ok", "service": "TrackFlow Incident Analyzer API"}


@app.post("/api/incidents/analyze")
async def analyze_incidents(file: UploadFile = File(...)):
    global LAST_RESULTS

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temp_file:
        temp_path = temp_file.name
        content = await file.read()
        temp_file.write(content)

    try:
        results = analyze_csv(temp_path)
        LAST_RESULTS = results
        return results
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.get("/api/incidents/results/export")
def export_results():
    if LAST_RESULTS is None:
        raise HTTPException(status_code=404, detail="No analysis results available.")

    output_path = os.path.join(tempfile.gettempdir(), "trackflow-results.csv")
    export_results_to_csv(LAST_RESULTS, output_path)

    return FileResponse(
        output_path,
        media_type="text/csv",
        filename="trackflow-results.csv",
    )    
