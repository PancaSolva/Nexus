"""
Nexus Anomaly Notifier — Telegram bridge for batch_detector.py

Called directly from batch_detector after anomalies are written to anomaly_log.json.
Uses synchronous httpx (no asyncio) so it works cleanly inside the detector's
polling loop without spinning up an event loop.

Environment variables (loaded from root .env):
    TELEGRAM_BOT_TOKEN  — Telegram bot token from @BotFather
    TELEGRAM_CHAT_ID    — Target chat/group ID
    ALERT_COOLDOWN_SECONDS — Min seconds between repeat alerts (default 300)
"""

import os
import time
import httpx
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load root .env (one directory above this file)
load_dotenv(Path(__file__).parent.parent / ".env")

TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
COOLDOWN_SECONDS: int = int(os.getenv("ALERT_COOLDOWN_SECONDS", "300"))

_MAX_RETRIES = 3
_BASE_DELAY = 1.0

# Per-endpoint cooldown: {(id_aplikasi, url): last_sent_epoch}
_cooldown_state: dict[tuple, float] = {}


# ─── Message Formatting ──────────────────────────────────────

def _escape_md(text: str) -> str:
    """Escape Telegram MarkdownV1 special characters."""
    for ch in ("_", "*", "`", "["):
        text = str(text).replace(ch, f"\\{ch}")
    return text


def _format_batch_message(anomalies: list[dict]) -> str:
    """Format a list of anomalies into a single grouped Telegram message."""
    count = len(anomalies)
    
    # Get the timestamp of the last anomaly
    last_entry = anomalies[-1]
    ts_raw = last_entry.get("detected_at", "")
    try:
        ts = datetime.fromisoformat(ts_raw).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        ts = ts_raw or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"🚨 *ANOMALIES DETECTED ({count})*",
        "━━━━━━━━━━━━━━━━━"
    ]

    for entry in anomalies:
        # Prefer 'nama' field, fallback to URL extraction
        name = entry.get("nama")
        if not name:
            url = str(entry.get("url", "?"))
            name = url.replace("https://", "").replace("http://", "").replace("www.", "").split(".")[0].capitalize()
        
        if not name or name == "?":
            name = "Unknown"
            
        status_val = entry.get("status")
        http_code = entry.get("http_status_code", "?")
        rt_val = entry.get("response_time_ms", "?")

        # Icon logic: ⚠️ if still up (status 1 & 200), ❌ if down or error
        if status_val == 1 and str(http_code) == "200":
            icon = "⚠️"
        else:
            icon = "❌"

        # Response time formatting
        if isinstance(rt_val, (int, float)):
            rt_str = f"{rt_val}ms"
        else:
            rt_str = str(rt_val)

        line = f"{icon} {_escape_md(name)} | {_escape_md(http_code)} | {_escape_md(rt_str)}"
        lines.append(line)

    lines.append("━━━━━━━━━━━━━━━━━")
    lines.append(f"🕒 {_escape_md(ts)}")
    lines.append("🏷  Nexus Detector")

    return "\n".join(lines)


# ─── Cooldown Gate ───────────────────────────────────────────

def _can_send(entry: dict) -> bool:
    """Return True if this endpoint is not in cooldown."""
    key = (entry.get("id_aplikasi"), entry.get("url"))
    now = time.time()
    last = _cooldown_state.get(key)
    if last is None or (now - last) >= COOLDOWN_SECONDS:
        _cooldown_state[key] = now
        return True
    return False


# ─── HTTP Send ───────────────────────────────────────────────

def _send_message(text: str) -> bool:
    """POST a message to Telegram with exponential-backoff retry."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[notifier] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set — skipping.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(url, json=payload)
            if resp.status_code == 200 and resp.json().get("ok"):
                return True
            print(f"[notifier] Telegram error (attempt {attempt}): {resp.text[:200]}")
        except Exception as exc:
            print(f"[notifier] Request failed (attempt {attempt}): {exc}")

        if attempt < _MAX_RETRIES:
            time.sleep(_BASE_DELAY * (2 ** (attempt - 1)))

    print(f"[notifier] All {_MAX_RETRIES} attempts failed.")
    return False


# ─── Public API ──────────────────────────────────────────────

def notify_anomalies(anomalies: list[dict]) -> int:
    """
    Send Telegram alerts for a list of anomaly entries.

    Groups multiple anomalies into a single message.
    Applies per-endpoint cooldown.
    """
    if not anomalies:
        return 0

    valid_anomalies = []
    for entry in anomalies:
        if _can_send(entry):
            valid_anomalies.append(entry)

    if not valid_anomalies:
        return 0

    text = _format_batch_message(valid_anomalies)
    if _send_message(text):
        return 1

    return 0
