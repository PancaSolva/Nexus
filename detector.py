# - Libraries -
import json
import joblib
import numpy as np
import pandas as pd
from datetime import datetime

from feature_engineer import build_features
from config import (
    MODEL_PATH,
    SCALER_PATH,
    THRESHOLD_PATH,
    ANOMALY_LOG_PATH,
    CONFIRM_STRIKES,
    RECOVER_STRIKES,
)


# - Anomaly Detector Class -
class AnomalyDetector:

    def __init__(self):
        self.model = None
        self.scaler = None
        self.threshold = None
        self._state = {}
        self._load_model()

    def _load_model(self):
        self.model = joblib.load(str(MODEL_PATH))
        self.scaler = joblib.load(str(SCALER_PATH))
        self.threshold = joblib.load(str(THRESHOLD_PATH))

    def reload(self):
        self._load_model()

    def _get_endpoint_key(self, row):
        return (int(row["id_aplikasi"]), str(row["url"]))

    def _update_state(self, key, raw_anomaly: bool) -> dict:
        if key not in self._state:
            self._state[key] = {
                "status": "normal",
                "strike_count": 0,
                "recovery_count": 0,
            }

        state = self._state[key]
        confirmed = False

        if raw_anomaly:
            state["strike_count"] += 1
            state["recovery_count"] = 0

            if state["status"] == "normal" and state["strike_count"] >= CONFIRM_STRIKES:
                state["status"] = "anomaly"
                confirmed = True
        else:
            state["recovery_count"] += 1
            state["strike_count"] = 0

            if state["status"] == "anomaly" and state["recovery_count"] >= RECOVER_STRIKES:
                state["status"] = "normal"
                confirmed = True

        return {
            "status": state["status"],
            "confirmed": confirmed,
            "strike_count": state["strike_count"],
            "recovery_count": state["recovery_count"],
        }

    def detect_batch(self, df: pd.DataFrame, log_anomalies: bool = True) -> dict:
        # Feature engineering
        original_df, feature_df = build_features(df)

        # Scale + score
        scaled = self.scaler.transform(feature_df)
        scores = self.model.score_samples(scaled)
        raw_anomalies = scores < self.threshold

        # Build results
        results = []
        anomalies_to_log = []

        for i, (score, raw_anomaly) in enumerate(zip(scores, raw_anomalies)):
            row = original_df.iloc[i]
            preproc_row = feature_df.iloc[i]
            raw_anomaly = bool(raw_anomaly)

            key = self._get_endpoint_key(row)
            state = self._update_state(key, raw_anomaly)

            # is_anomaly reflects confirmed state, not raw score
            is_confirmed_anomaly = state["status"] == "anomaly"

            entry = {
                "id_log_monitor": int(row["id_log_monitor"]),
                "id_aplikasi": int(row["id_aplikasi"]),
                "nama": str(row["nama"]) if "nama" in row and pd.notna(row["nama"]) else None,
                "id_service": str(row["id_service"]),
                "url": str(row["url"]),
                "status": int(row["status"]),
                "http_status_code": int(row["http_status_code"]),
                "response_time_ms": int(row["response_time_ms"]),
                "threshold": round(float(self.threshold), 5),
                "anomaly_score": round(float(score), 5),
                "raw_anomaly": raw_anomaly,
                "is_anomaly": is_confirmed_anomaly,
                "strike_count": state["strike_count"],
                "recovery_count": state["recovery_count"],
            }

            results.append(entry)

            # Log every record where the endpoint is in confirmed anomaly state
            if is_confirmed_anomaly:
                anomaly_entry = {
                    **entry,
                    "rolling_z_score": round(float(preproc_row["rolling_z_score"]), 5) if "rolling_z_score" in preproc_row else 0.0,
                    "rt_drift": round(float(preproc_row["rt_drift"]), 5) if "rt_drift" in preproc_row else 0.0,
                    "checked_at": str(row["checked_at"]),
                    "detected_at": datetime.now().isoformat(),
                }
                anomalies_to_log.append(anomaly_entry)

        # Log anomalies
        if log_anomalies and anomalies_to_log:
            self._append_anomaly_log(anomalies_to_log)

        return {
            "total": len(results),
            "anomalies_found": sum(1 for r in results if r["is_anomaly"]),
            "threshold": self.threshold,
            "results": results,
        }

    def detect_single(self, record: dict, log_anomalies: bool = True) -> dict:
        df = pd.DataFrame([record])
        batch_result = self.detect_batch(df, log_anomalies=log_anomalies)
        return batch_result["results"][0]

    def _append_anomaly_log(self, new_anomalies: list):
        log_path = str(ANOMALY_LOG_PATH)

        try:
            with open(log_path, "r") as f:
                existing = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            existing = []

        existing.extend(new_anomalies)

        with open(log_path, "w") as f:
            json.dump(existing, f, indent=2)