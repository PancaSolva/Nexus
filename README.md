<div align="center">
  <img src="Nexus_Logo.png" alt="Nexus Logo" width="300">
</div>

<h1 align="center">Nexus - Anomaly Detector for Asentinel</h1>

<div align="center">
  <strong>English</strong> | <a href="README_INDONESIAN.md">Indonesia</a>
</div>

Detects anomalies in API health monitoring data using **Isolation Forest**. Built to work with Asentinel's `log_monitor` table.

## How It Works

1. Raw monitoring data comes in (from CSV or database)
2. Features are engineered from the raw data (`feature_engineer.py`)
3. The Isolation Forest model scores each record
4. If a record scores below the threshold, it gets a **strike** — but it's not flagged yet
5. Only after **3 consecutive strikes**, the endpoint is confirmed as an anomaly and logged
6. To recover, the endpoint must pass **3 consecutive normal checks**
7. Every 12 hours (during retraining), `summarizer.py` groups the anomalies into a summary and clears the log.
8. The `/recommend` endpoint passes the summary to the Groq LLM (`engine.py`) to generate a technical remediation plan.

This strike system prevents false alarms from temporary lag spikes. Configurable via `CONFIRM_STRIKES` and `RECOVER_STRIKES` in `config.py`.

## Project Structure

| File | What it does |
|------|-------------|
| `config.py` | All settings (paths, DB, model params, schedule, LLM configs) |
| `detector.py` | Core detection engine (used by everything else) |
| `feature_engineer.py` | Builds features from raw monitoring data |
| `nexus.py` | FastAPI server with detection and recommendation endpoints |
| `retrain_scheduler.py` | Retrains the model from CSV or DB (and triggers summarizer) |
| `batch_detector.py` | Batch detection from CSV (dev) or DB polling (prod) |
| `summarizer.py` | Groups the 12-hour anomaly logs into a summary JSON |
| `engine.py` | Interacts with the Groq API (LLM) to generate recommendations |

## Setup

1. Copy `.env.example` to `.env` (or create a `.env` file) and fill in your DB credentials and `GROQ_API_KEY`.
2. Install requirements:
```bash
pip install -r requirements.txt
```

## Usage

**Start the API server (IMPORTANT: pass the `.env` file so Python can read the API key):**
```bash
uvicorn nexus:app --reload --env-file .env
```

**Retrain the model:**
```bash
python retrain_scheduler.py
```

**Retrain the model (every 12 hours):**
```bash
python retrain_scheduler.py --loop
```

**Run batch detection from CSV:**
```bash
python batch_detector.py
```

**Run batch detection from DB (when DB is ready):**
```bash
python batch_detector.py --poll
```

## Database

The system is ready for database connection. When your DB is hosted:

1. Set `DB_ENABLED = True` in `config.py`
2. Fill in `DB_CONFIG` with your credentials (or use `.env`)
3. The `log_monitor` table must have these columns (**IMPORTANT** or else the system will fail):
   `id_log_monitor`, `id_aplikasi`, `id_service`, `url`, `status`, `http_status_code`, `response_time_ms`, `checked_at`, `created_at`, `updated_at`
