# - Libraries -
import os
import httpx
import asyncio
from datetime import datetime
from utils.logger import logger

# Bot credentials and alert settings from environment
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
SEND_RECOVERY_ALERTS: bool = os.getenv("SEND_RECOVERY_ALERTS", "true").lower() == "true"

_MAX_RETRIES = 3
_BASE_DELAY = 1.0  # seconds, doubled each retry


def _escape_md(text: str) -> str:
    """Escape MarkdownV1 special characters for Telegram."""
    text = str(text)
    for ch in ("_", "*", "`", "["):
        text = text.replace(ch, f"\\{ch}")
    return text


def _format_timestamp(raw: str) -> str:
    """Convert ISO timestamp to human-readable format, fallback to now."""
    if not raw:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        return datetime.fromisoformat(raw).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return raw


def _format_down_message(service_name: str, message: str, timestamp: str) -> str:
    """Build a DOWN alert message."""
    return (
        "🔴 *SERVICE DOWN*\n"
        "━━━━━━━━━━━━━━━━━\n"
        f"📛 Service: `{_escape_md(service_name)}`\n"
        f"🕐 Waktu: `{_escape_md(timestamp)}`\n"
        f"❌ Error: `{_escape_md(message)}`\n"
        "━━━━━━━━━━━━━━━━━\n"
        "🏷 _Asentinel Monitor_"
    )


def _format_up_message(service_name: str, message: str, timestamp: str) -> str:
    """Build a RECOVERY alert message."""
    return (
        "🟢 *SERVICE RECOVERED*\n"
        "━━━━━━━━━━━━━━━━━\n"
        f"✅ Service: `{_escape_md(service_name)}`\n"
        f"🕐 Waktu: `{_escape_md(timestamp)}`\n"
        f"📝 Info: `{_escape_md(message or 'Recovered')}`\n"
        "━━━━━━━━━━━━━━━━━\n"
        "🏷 _Asentinel Monitor_"
    )


async def send_alert(
    service_name: str,
    status: str,
    message: str = "",
    timestamp: str = "",
) -> bool:
    """
    Send a Telegram alert for a service event.

    Args:
        service_name: Human-readable service label.
        status: "UP" or "DOWN" (case-insensitive).
        message: Short description or error text.
        timestamp: ISO-8601 string; auto-filled if empty.

    Returns:
        True if the message was delivered, False otherwise.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("Telegram credentials missing — set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
        return False

    status_upper = status.upper()
    ts = _format_timestamp(timestamp)

    if status_upper == "UP" and not SEND_RECOVERY_ALERTS:
        logger.info("Recovery alert skipped (SEND_RECOVERY_ALERTS=false): %s", service_name)
        return False

    if status_upper == "DOWN":
        text = _format_down_message(service_name, message, ts)
    else:
        text = _format_up_message(service_name, message, ts)

    return await _send_telegram_message(text)


async def _send_telegram_message(text: str) -> bool:
    """POST to Telegram with retry + exponential backoff. Returns True on success."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)

            if response.status_code == 200 and response.json().get("ok"):
                logger.info("Telegram message sent (attempt %d)", attempt)
                return True

            logger.warning(
                "Telegram API error (attempt %d): HTTP %d — %s",
                attempt, response.status_code, response.text[:200],
            )

        except httpx.TimeoutException:
            logger.warning("Telegram request timed out (attempt %d)", attempt)
        except httpx.HTTPError as exc:
            logger.warning("Telegram HTTP error (attempt %d): %s", attempt, exc)
        except Exception as exc:
            logger.error("Unexpected error (attempt %d): %s", attempt, exc)

        if attempt < _MAX_RETRIES:
            delay = _BASE_DELAY * (2 ** (attempt - 1))
            logger.info("Retrying in %.1fs…", delay)
            await asyncio.sleep(delay)

    logger.error("All %d Telegram send attempts failed", _MAX_RETRIES)
    return False
