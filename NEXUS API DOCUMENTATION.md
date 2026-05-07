# Nexus API Documentation

Base URL: `http://127.0.0.1:8000`

---

## GET /

Health check. Returns available endpoints.

**Response:**
```json
{
  "message": "Nexus — Asentinel Anomaly Detector",
  "endpoints": {
    "POST /detect": "Single record detection",
    "POST /detect/batch": "Batch detection",
    "GET /recommend": "Generate recommendations from the latest summary"
  }
}
```
---

## POST /detect

Detect anomaly on a single record. Use this from PHP or any external service.

**Request Body:**
```json
{
  "id_log_monitor": 1,
  "id_aplikasi": 20,
  "id_service": "19",
  "url": "https://www.example.com",
  "status": "DOWN",
  "http_status_code": 503,
  "response_time_ms": -1,
  "checked_at": "2026-04-17 02:26:05",
  "created_at": "2026-04-17 02:26:05",
  "updated_at": "2026-04-17 02:26:05"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `id_log_monitor` | int | yes | |
| `id_aplikasi` | int | yes | |
| `id_service` | string | no | `null` if monolithic |
| `url` | string | yes | |
| `status` | string | yes | `"UP"` or `"DOWN"` |
| `http_status_code` | int | yes | |
| `response_time_ms` | int | yes | `-1` if DOWN |
| `checked_at` | string | yes | `YYYY-MM-DD HH:MM:SS` |
| `created_at` | string | yes | `YYYY-MM-DD HH:MM:SS` |
| `updated_at` | string | yes | `YYYY-MM-DD HH:MM:SS` |

**Response (200):**
```json
{
  "id_log_monitor": 1,
  "id_aplikasi": 20,
  "id_service": "19",
  "url": "https://www.example.com",
  "status": 0,
  "http_status_code": 503,
  "response_time_ms": -1,
  "threshold": -0.52707,
  "anomaly_score": -0.64358,
  "raw_anomaly": true,
  "is_anomaly": false,
  "strike_count": 1,
  "recovery_count": 0
}
```

- `raw_anomaly`: `true` if the model score is below threshold (raw, single-check result)
- `is_anomaly`: `true` only after the endpoint has been anomalous for **3 consecutive checks** (confirmed)
- `strike_count`: how many consecutive anomaly detections so far
- `recovery_count`: how many consecutive normal detections so far
- `anomaly_score`: lower = more anomalous
- `threshold`: current model threshold

---

## POST /detect/batch

Detect anomalies on multiple records at once.

**Request Body:**
```json
{
  "records": [
    {
      "id_log_monitor": 1,
      "id_aplikasi": 20,
      "id_service": "19",
      "url": "https://www.example.com",
      "status": "DOWN",
      "http_status_code": 503,
      "response_time_ms": -1,
      "checked_at": "2026-04-17 02:26:05",
      "created_at": "2026-04-17 02:26:05",
      "updated_at": "2026-04-17 02:26:05"
    }
  ]
}
```

**Response (200):**
```json
{
  "total": 1,
  "anomalies_found": 0,
  "threshold": -0.52707,
  "results": [ ... ]
}
```

---

## GET /recommend

Generate a technical recommendation plan based on the latest anomaly summary.

**Response (200):**
```json
{
  "period": {
    "from": "2026-04-17 02:26:05",
    "to": "2026-04-17 04:17:26",
    "generated_at": "2026-04-23T22:55:50.719207"
  },
  "recommendation": [
    "1. Investigasi server...",
    "2. Periksa load balancer...",
    "3. Evaluasi kapasitas..."
  ]
}
```

---

## Administrative Endpoints

### POST /reload-model
Reload the model from disk without restarting the server.

### DELETE /clear-logs/anomalies
Clear the anomaly log file (`logs/anomaly_log.json`).

### DELETE /clear-logs/failed
Clear the failed payloads log (`logs/failed_payloads.jsonl`).

### DELETE /clear-logs/summaries
Clear all generated summary files in `logs/summaries/`.

---

## Error Handling
Failed payloads for `/detect` are saved to `logs/failed_payloads.jsonl` for later debugging. Errors return a 500 status code with detail:
```json
{ "detail": "error message" }
```