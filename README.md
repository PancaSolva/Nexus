<div align="center">
  <img src="Nexus_Logo.png" alt="Nexus Logo" width="300">
</div>

<h1 align="center">Nexus - Anomaly Detector for Asentinel</h1>

<div align="center">
  <strong>English</strong> | <a href="README_INDONESIAN.md">Indonesia</a>
</div>

Detects anomalies in API health monitoring data using **Isolation Forest**.

## How It Works

1. Raw monitoring data comes in (from CSV or database)
2. Features are engineered from the raw data (`feature_engineer.py`)
3. The Isolation Forest model scores each record
4. If a score falls below the threshold, the endpoint gets a **strike** — not flagged yet
5. After **3 consecutive strikes**, the endpoint is confirmed as anomaly and logged
6. To recover, the endpoint must pass **3 consecutive normal checks**
7. During retraining, `summarizer.py` groups the anomaly log into a summary and clears it
8. The `/recommend` endpoint passes the summary to an LLM (`engine.py`) to generate a remediation plan

> Strikes prevent false alarms from temporary spikes. Configurable via `CONFIRM_STRIKES` and `RECOVER_STRIKES` in `config.py`.

## Project Structure

| File | What it does |
|------|-------------|
| `config.py` | All settings (paths, DB, model params, schedule, LLM) |
| `detector.py` | Core detection engine |
| `feature_engineer.py` | Builds features from raw monitoring data |
| `nexus.py` | FastAPI server — detection and recommendation endpoints |
| `batch_detector.py` | Batch detection from CSV (dev) or DB polling (prod) |
| `retrain_scheduler.py` | Retrains the model and triggers the summarizer |
| `summarizer.py` | Groups anomaly logs into a compact summary JSON |
| `engine.py` | Sends the summary to an LLM and returns a remediation plan |
| `run.py` | Interactive CLI menu to run any part of the system |

## Setup

1. Copy `.env.example` to `.env` and fill in your DB credentials and LLM API key.
2. Install requirements:
```bash
pip install -r requirements.txt
```

## Usage

Nexus can be used in two ways:

### Automatic (via CLI)

The recommended way for internal/ops use. Run the interactive menu:

```bash
python run.py
```

From the menu you can run batch detection (CSV or DB), single detection, retrain the model, and manage logs — all from one place.

### API Endpoint (for single payload)

For external systems (e.g. Asentinel's backend) that want to push a single record and get a live anomaly verdict. Start the API server:

```bash
uvicorn nexus:app --reload --env-file .env
```

Then send a `POST` request to `/detect` with a single monitoring record. See `NEXUS API DOCUMENTATION.md` for full endpoint reference.

## Database

When your DB is hosted:

1. Set `DB_ENABLED = True` in `config.py`
2. Fill in DB credentials in `.env`
3. The `log_monitor` table must have these columns:
   `id_log_monitor`, `id_aplikasi`, `id_service`, `url`, `status`, `http_status_code`, `response_time_ms`, `checked_at`, `created_at`, `updated_at`
