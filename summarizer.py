# - Libraries -
import json
from collections import defaultdict
from datetime import datetime

from config import (
    LOG_DIR,
    ANOMALY_LOG_PATH,
)

SUMMARY_DIR = LOG_DIR / "summaries"


def _severity(worst_score: float) -> str:
    """Rate severity based on worst anomaly score (more negative = worse)."""
    if worst_score < -0.65:
        return "critical"
    elif worst_score < -0.55:
        return "high"
    elif worst_score < -0.45:
        return "medium"
    return "low"


def generate_summary():
    """Reads the anomaly log, generates an informative summary, and clears the log."""

    SUMMARY_DIR.mkdir(exist_ok=True)

    # Read the log
    try:
        with open(ANOMALY_LOG_PATH, "r") as f:
            log_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        log_data = []

    if not log_data:
        print("[summary] No anomalies to summarize.")
        return None

    total = len(log_data)

    # --- Aggregate ---
    affected_apps = set()
    affected_urls = set()
    down_count = 0
    http_errors_counter = defaultdict(int)
    hour_counter = defaultdict(int)
    endpoints = {}

    for record in log_data:
        app_id = record["id_aplikasi"]
        url = record["url"]
        key = f"{app_id}|{url}"
        is_down = record["status"] == 0

        affected_apps.add(app_id)
        affected_urls.add(url)
        if is_down:
            down_count += 1

        http_code = record.get("http_status_code", 0)
        if http_code >= 400:
            http_errors_counter[http_code] += 1

        # Track peak hour from checked_at
        try:
            checked_dt = datetime.fromisoformat(str(record["checked_at"]))
            hour_counter[checked_dt.hour] += 1
        except (ValueError, TypeError):
            pass

        if key not in endpoints:
            endpoints[key] = {
                "id_aplikasi": app_id,
                "url": url,
                "id_service": record.get("id_service", ""),
                "anomaly_count": 0,
                "down_count": 0,
                "scores": [],
                "response_times": [],
                "rt_drifts": [],
                "http_errors": defaultdict(int),
            }

        ep = endpoints[key]
        ep["anomaly_count"] += 1
        ep["scores"].append(record["anomaly_score"])
        if is_down:
            ep["down_count"] += 1
        if http_code >= 400:
            ep["http_errors"][http_code] += 1
        rt = record.get("response_time_ms", -1)
        if rt > 0:
            ep["response_times"].append(rt)
        drift = record.get("rt_drift", 0.0)
        if drift:
            ep["rt_drifts"].append(drift)

    # --- Format top endpoints ---
    sorted_eps = sorted(
        endpoints.values(), key=lambda x: x["anomaly_count"], reverse=True
    )

    top_endpoints = []
    for ep in sorted_eps[:5]:
        scores = ep["scores"]
        rts = ep["response_times"]
        drifts = ep["rt_drifts"]
        worst = min(scores) if scores else None
        http_err_dict = dict(ep["http_errors"]) or None

        top_endpoints.append({
            "id_aplikasi": ep["id_aplikasi"],
            "url": ep["url"],
            "id_service": ep["id_service"],
            "severity": _severity(worst) if worst is not None else "unknown",
            "anomaly_count": ep["anomaly_count"],
            "down_count": ep["down_count"],
            "worst_score": round(worst, 5) if worst is not None else None,
            "avg_score": round(sum(scores) / len(scores), 5) if scores else None,
            "avg_response_time_ms": round(sum(rts) / len(rts)) if rts else None,
            "avg_rt_drift_ms": round(sum(drifts) / len(drifts), 2) if drifts else None,
            "http_errors": http_err_dict,
        })

    # --- Overview ---
    most_common_error = (
        max(http_errors_counter, key=http_errors_counter.get)
        if http_errors_counter else None
    )
    peak_hour = (
        max(hour_counter, key=hour_counter.get) if hour_counter else None
    )
    down_pct = round((down_count / total) * 100, 1) if total else 0.0

    summary = {
        "period": {
            "from": min(r["checked_at"] for r in log_data),
            "to": max(r["checked_at"] for r in log_data),
            "generated_at": datetime.now().isoformat(),
        },
        "overview": {
            "total_anomaly_events": total,
            "affected_apps": len(affected_apps),
            "affected_endpoints": len(affected_urls),
            "down_percentage": down_pct,
            "most_common_http_error": most_common_error,
            "peak_anomaly_hour": f"{peak_hour:02d}:00" if peak_hour is not None else None,
        },
        "top_endpoints": top_endpoints,
    }

    # --- Save ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_path = SUMMARY_DIR / f"summary_{timestamp}.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"[summary] Saved → {summary_path.name}")

    # --- Clear anomaly log ---
    with open(ANOMALY_LOG_PATH, "w") as f:
        json.dump([], f)
    print("[summary] Anomaly log cleared.")

    return summary


if __name__ == "__main__":
    generate_summary()
