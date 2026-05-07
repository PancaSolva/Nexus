# - Libraries -
import json
import pandas as pd
from pydantic import BaseModel
from typing import Optional, List
from fastapi import FastAPI, HTTPException

from detector import AnomalyDetector
from config import ANOMALY_LOG_PATH, FAILED_PAYLOAD_PATH, LOG_DIR
from engine import generate_recommendation
import os

# - Helper Function -
def _log_failed_payload(payload_json: str):
    try:
        with open(str(FAILED_PAYLOAD_PATH), "a") as f:
            f.write(payload_json + "\n")
    except Exception:
        pass


# - API & Detector -  
app = FastAPI(
    title="Nexus — Asentinel Anomaly Detector",
    version="1.2.0",
    description="Anomaly detection API for API health monitoring",
)

detector = AnomalyDetector()


# Payload Schemas
class HealthCheckRecord(BaseModel):
    id_log_monitor: int
    id_aplikasi: int
    id_service: Optional[str] = None
    url: str
    status: str
    http_status_code: int
    response_time_ms: int
    checked_at: str
    created_at: str
    updated_at: str

class BatchPayload(BaseModel):
    records: List[HealthCheckRecord]


# - Endpoints -
@app.get("/")
def root():
    return {
        "message": "Nexus — Asentinel Anomaly Detector",
        "endpoints": {
            "POST /detect": "Single record detection",
            "POST /detect/batch": "Batch detection",
            "GET /recommend": "Generate recommendations from the latest summary"
        },
    }

# Recommendation Engine
@app.get("/recommend")
async def get_recommendation():
    try:
        result = generate_recommendation()
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Detect single record
@app.post("/detect")
async def detect_single(data: HealthCheckRecord):
    try:
        result = detector.detect_single(data.model_dump())
        return result
    except Exception as e:
        _log_failed_payload(data.model_dump_json())
        raise HTTPException(status_code=500, detail=str(e))


# Batch detection
@app.post("/detect/batch")
async def detect_batch(data: BatchPayload):
    try:
        df = pd.DataFrame([r.model_dump() for r in data.records])
        result = detector.detect_batch(df)
        return result
    except Exception as e:
        _log_failed_payload(data.model_dump_json())
        raise HTTPException(status_code=500, detail=str(e))


# Reload model
@app.post("/reload-model")
async def reload_model():
    try:
        detector.reload()
        return {
            "message": "Model reloaded.",
            "threshold": round(float(detector.threshold), 5),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Clear anomaly log
@app.delete("/clear-logs/anomalies")
async def clear_anomaly_log():
    try:
        with open(str(ANOMALY_LOG_PATH), "w") as f:
            json.dump([], f)
        return {"message": "Anomaly log cleared."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Clear failed payloads log
@app.delete("/clear-logs/failed")
async def clear_failed_payloads():
    try:
        with open(str(FAILED_PAYLOAD_PATH), "w") as f:
            f.write("")
        return {"message": "Failed payloads cleared."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Clear summaries
@app.delete("/clear-logs/summaries")
async def clear_summaries():
    try:
        summary_dir = LOG_DIR / "summaries"
        if summary_dir.exists():
            count = 0
            for file in os.listdir(summary_dir):
                if file.startswith("summary_") and file.endswith(".json"):
                    os.remove(summary_dir / file)
                    count += 1
            return {"message": f"Cleared {count} summaries."}
        return {"message": "No summaries found."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))