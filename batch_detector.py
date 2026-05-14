import time
import argparse
import pandas as pd

from detector import AnomalyDetector
from config import (
    TRAINING_CSV,
    DB_ENABLED,
    ENGINE,
    FETCH_QUERY,
    FETCH_INTERVAL_SECONDS,
)
from sqlalchemy import text

# Telegram notifier — imported lazily so missing credentials never crash the detector
try:
    from webhook.notifier import notify_anomalies
    _NOTIFIER_AVAILABLE = True
except ImportError:
    _NOTIFIER_AVAILABLE = False


# Max anomalies to notify per batch; batches above this are treated as
# historical/bulk data and silently skipped (prevents spam on first DB fetch).
_NOTIFY_BATCH_LIMIT = 5


def _notify(anomalies: list, label: str = "") -> None:
    """Send Telegram alerts if the notifier is configured and batch is within limit."""
    if not _NOTIFIER_AVAILABLE:
        return
    count = len(anomalies)
    if count > _NOTIFY_BATCH_LIMIT:
        print(f"  [notifier] Skipped — {count} anomalies exceeds batch limit ({_NOTIFY_BATCH_LIMIT}). Likely historical data.")
        return
    sent = notify_anomalies(anomalies)
    if sent:
        print(f"  [notifier] Sent {sent} Telegram alert(s). {label}")


# ─── CSV Mode (dev / offline) ────────────────────────────────

def detect_csv(detector: AnomalyDetector):
    df = pd.read_csv(str(TRAINING_CSV))
    df["checked_at"] = pd.to_datetime(df["checked_at"])
    df["batch_group"] = df["checked_at"].dt.floor("min")

    total_anomalies = 0

    for batch_time, batch_df in df.groupby("batch_group"):
        batch_df = batch_df.copy()
        batch_df.loc[
            (batch_df["status"] == "DOWN") & (batch_df["response_time_ms"].isnull()),
            "response_time_ms",
        ] = -1
        batch_df = batch_df.drop(columns=["batch_group"])

        print(f"\nBatch: {batch_time} ({len(batch_df)} rows)")

        start = time.perf_counter()
        result = detector.detect_batch(batch_df)
        elapsed = time.perf_counter() - start

        total_anomalies += result["anomalies_found"]
        print(f"  Total: {result['total']} | Anomalies: {result['anomalies_found']} | Time: {elapsed:.3f}s")

        anomaly_entries = []
        for r in result["results"]:
            if r["is_anomaly"]:
                status_str = "UP" if r["status"] == 1 else "DOWN"
                name_str = r.get("nama") or f"ID:{r['id_aplikasi']}"
                service_str = "Monolithic" if r["id_service"] == "monolithic" else str(r["id_service"]).split(".")[0]
                print(f"  [ 🚨 ANOMALY ] {name_str} | Service: {service_str} | URL: {r['url']}")
                print(f"  [ ℹ️  INFO ] Status: {status_str} | HTTP: {r['http_status_code']} | RT: {r['response_time_ms']}ms | Score: {r['anomaly_score']}\n")
                anomaly_entries.append(r)

        # CSV mode: skip notification if the batch has too many anomalies
        # (entire CSV is treated as historical data in that case)
        _notify(anomaly_entries, label=f"(batch {batch_time})")

    print(f"\n{'='*50}")
    print(f"Done. Total anomalies detected: {total_anomalies}")


# ─── DB Polling Mode (prod) ──────────────────────────────────

def detect_database(detector: AnomalyDetector):
    if not DB_ENABLED:
        print("[detector] DB_ENABLED is False — use CSV mode instead.")
        return

    last_id = 0
    is_first_fetch = True
    print(f"[detector] Starting DB poll loop (every {FETCH_INTERVAL_SECONDS}s)")

    while True:
        try:
            with ENGINE.connect() as conn:
                query = FETCH_QUERY.format(last_id=last_id)
                df = pd.read_sql(text(query), conn)

            if df.empty:
                print(f"[detector] No new records (last_id={last_id}).")
            else:
                print(f"[detector] Found {len(df)} new records (id > {last_id})")

                result = detector.detect_batch(df)
                last_id = max(int(df["id_log_monitor"].max()), last_id)

                print(f"[detector] Total: {result['total']} | Anomalies: {result['anomalies_found']}")

                anomaly_entries = []
                for r in result["results"]:
                    if r["is_anomaly"]:
                        anomaly_entries.append(r)
                        if not is_first_fetch:
                            status_str = "UP" if r["status"] == 1 else "DOWN"
                            name_str = r.get("nama") or f"ID:{r['id_aplikasi']}"
                            service_str = "Monolithic" if r["id_service"] == "monolithic" else str(r["id_service"]).split(".")[0]
                            print(f"  [ 🚨 ANOMALY ] {name_str} | Service: {service_str} | URL: {r['url']}")
                            print(f"  [ ℹ️  INFO ] Status: {status_str} | HTTP: {r['http_status_code']} | RT: {r['response_time_ms']}ms | Score: {r['anomaly_score']}")

                # First fetch always pulls ALL historical data — skip notification
                # to avoid flooding the chat with hundreds of old anomalies.
                if is_first_fetch:
                    print(f"  [notifier] Skipped first fetch ({result['anomalies_found']} anomalies — historical baseline).")
                else:
                    _notify(anomaly_entries)

                is_first_fetch = False

        except Exception as e:
            print(f"[detector] Error: {e}")

        time.sleep(FETCH_INTERVAL_SECONDS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch anomaly detector")
    parser.add_argument("--poll", action="store_true", help="Enable DB polling mode")
    args = parser.parse_args()

    detector = AnomalyDetector()

    if args.poll:
        detect_database(detector)
    else:
        detect_csv(detector)
