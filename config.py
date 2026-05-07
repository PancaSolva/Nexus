# - Libraries -
import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine

# Load environment variables from .env file
load_dotenv()

# - Path(s) -
BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models"
LOG_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"

MODEL_PATH = MODEL_DIR / "model.pkl"
SCALER_PATH = MODEL_DIR / "scaler.pkl"
THRESHOLD_PATH = MODEL_DIR / "threshold.pkl"

ANOMALY_LOG_PATH = LOG_DIR / "anomaly_log.json"
FAILED_PAYLOAD_PATH = LOG_DIR / "failed_payloads.jsonl"

# - Database -
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306") or 3306),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASS", ""),
    "database": os.getenv("DB_NAME", "Asentinel"),
}

# Set to True if DB is hosted
DB_ENABLED = True

# SQLAlchemy Connection String
DATABASE_URL = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"

# Create SQLAlchemy Engine
ENGINE = create_engine(DATABASE_URL)

# Fetch training data from DB
TRAINING_QUERY = """
    SELECT id_log_monitor, id_aplikasi, id_service, url, 
           status, http_status_code, response_time_ms,
           checked_at, created_at, updated_at
    FROM log_monitor
"""

# Fetch new records from DB
FETCH_QUERY = """
    SELECT id_log_monitor, id_aplikasi, id_service, url,
           status, http_status_code, response_time_ms,
           checked_at, created_at, updated_at
    FROM log_monitor
    WHERE id_log_monitor > {last_id}
    ORDER BY id_log_monitor ASC
"""

# - Model Hyperparameter(s) -
MODEL_PARAMS = {
    "n_estimators": 200,
    "max_features": 0.8,
    "contamination": "auto",
    "random_state": 42,
    "n_jobs": -1,
}

# Threshold = Nth percentile of training anomaly scores
THRESHOLD_PERCENTILE = 10

# - Strike & Recover Confirmation -
CONFIRM_STRIKES = 3
RECOVER_STRIKES = 3

# - Model Retraining Interval -
RETRAIN_INTERVAL_HOURS = 12

# - Schedule Retraining (every 12 hours: 02.00 & 14.00) -
RETRAIN_SCHEDULE = {
    "hour": "2,14",
    "minute": "0",
}

# - Batch Fetching Interval (every 10 seconds) -
FETCH_INTERVAL_SECONDS = 10

# - LLM Engine Configuration -
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3") or 0.3)
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "500") or 500)

# - CSV Training Data (without DB) -
TRAINING_CSV = DATA_DIR / "log_monitor.csv"

# - Check Directories Exist -
MODEL_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
