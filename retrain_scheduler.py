# - Libraries -
import time
import argparse
import numpy as np
import pandas as pd
from datetime import datetime

from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest

from summarizer import generate_summary
from feature_engineer import build_features
from config import (
    MODEL_PATH, 
    SCALER_PATH, 
    THRESHOLD_PATH,
    MODEL_PARAMS, 
    THRESHOLD_PERCENTILE,
    TRAINING_CSV, 
    TRAINING_QUERY,
    DB_ENABLED, 
    ENGINE,
    RETRAIN_INTERVAL_HOURS
)
from sqlalchemy import text


# - Functions -
def fetch_training_data() -> pd.DataFrame:
    if DB_ENABLED:
        try:
            with ENGINE.connect() as conn:
                df = pd.read_sql(text(TRAINING_QUERY), conn)
            print(f"[retrain] Fetched {len(df)} rows from database.")
            return df
        except Exception as e:
            print(f"[retrain] DB fetch failed, using CSV: {e}")

    df = pd.read_csv(str(TRAINING_CSV))
    print(f"[retrain] Loaded {len(df)} rows from {TRAINING_CSV.name}")
    return df


def retrain_model(detector=None) -> dict:
    start = time.perf_counter()
    print(f"\n{'='*50}")
    print(f"[retrain] Starting retrain at {datetime.now().isoformat()}\n")

    # Generate summary & clear log from the previous 12h window
    try:
        generate_summary()
    except Exception as e:
        print(f"[retrain] Summary generation failed: {e}")

    # Fetch data from CSV or SQL
    df = fetch_training_data()

    # Feature engineering
    _, feature_df = build_features(df)
    print(f"[retrain] Features built: {feature_df.shape}")

    # Scaling
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(feature_df)

    # Training
    model = IsolationForest(**MODEL_PARAMS)
    model.fit(X_scaled)

    # Threshold
    scores = model.score_samples(X_scaled)
    threshold = float(np.percentile(scores, THRESHOLD_PERCENTILE))

    # Save model, scaler, and threshold
    import joblib
    joblib.dump(model, str(MODEL_PATH))
    joblib.dump(scaler, str(SCALER_PATH))
    joblib.dump(threshold, str(THRESHOLD_PATH))

    elapsed = time.perf_counter() - start

    print(f"[retrain] Model saved to {MODEL_PATH}")
    print(f"[retrain] Threshold: {threshold:.5f} (p{THRESHOLD_PERCENTILE})")
    print(f"[retrain] Duration: {elapsed:.2f}s")
    print(f"[retrain] Training rows: {len(df)}")
    print(f"[retrain] Done: {datetime.now().isoformat()}")
    print(f"{'='*50}\n")

    # Reload model
    if detector is not None:
        detector.reload()
        print("[retrain] Model reloaded.")

    return {
        "training_rows": len(df),
        "threshold": round(threshold, 5),
        "duration_seconds": round(elapsed, 2),
        "retrained_at": datetime.now().isoformat(),
    }


def retrain_loop():
    interval = RETRAIN_INTERVAL_HOURS * 3600
    print(f"[retrain] Loop mode: retraining every {RETRAIN_INTERVAL_HOURS}h")

    while True:
        try:
            retrain_model()
        except Exception as e:
            print(f"[retrain] Error: {e}")
        
        print(f"[retrain] Next retrain in {RETRAIN_INTERVAL_HOURS}h.\n")
        time.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrain anomaly detection model")
    parser.add_argument("--loop", action="store_true", help="Run in loop mode (retrain every 12h)")
    args = parser.parse_args()

    if args.loop:
        retrain_loop()
    else:
        result = retrain_model()
        print(f"\n[retrain] Done: {result}")
