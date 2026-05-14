# - Libraries -
import os
import json
import httpx
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List

from utils.logger import logger
from utils.cooldown import cooldown_manager
from services.telegram import send_alert

MONITOR_ENABLED: bool = os.getenv("MONITOR_ENABLED", "true").lower() == "true"
_DEFAULT_INTERVAL = 60   # seconds between checks per target
_HTTP_TIMEOUT = 10.0     # seconds before a request is considered timed out

# Tracks last known status per service name to detect transitions
_previous_status: Dict[str, str] = {}


def _load_targets() -> List[Dict[str, Any]]:
    """
    Parse MONITOR_TARGETS from environment (JSON array).

    Expected format:
        [{"name": "App", "url": "http://host/health", "interval": 60}]
    """
    raw = os.getenv("MONITOR_TARGETS", "[]")
    try:
        targets = json.loads(raw)
        if not isinstance(targets, list):
            logger.error("MONITOR_TARGETS must be a JSON array, got %s", type(targets))
            return []
        logger.info("Loaded %d monitor target(s)", len(targets))
        return targets
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse MONITOR_TARGETS: %s", exc)
        return []


async def _check_single_target(target: Dict[str, Any]) -> None:
    """
    HTTP GET health check for one target.

    Considered DOWN on: connection failure, timeout, or non-2xx response.
    Notifies on status change only (UP→DOWN or DOWN→UP).
    """
    name: str = target.get("name", "Unknown")
    url: str = target.get("url", "")

    if not url:
        logger.warning("Monitor target '%s' has no URL — skipping", name)
        return

    status = "UP"
    message = "OK"

    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.get(url)

        if 200 <= response.status_code < 300:
            message = f"HTTP {response.status_code}"
            logger.debug("✓ %s — %s (%s)", name, url, message)
        else:
            status = "DOWN"
            message = f"HTTP {response.status_code}"
            logger.warning("✗ %s — %s returned %s", name, url, message)

    except httpx.TimeoutException:
        status = "DOWN"
        message = "Connection Timeout"
        logger.warning("✗ %s — %s timed out", name, url)

    except httpx.ConnectError:
        status = "DOWN"
        message = "Connection Refused"
        logger.warning("✗ %s — %s connection refused", name, url)

    except Exception as exc:
        status = "DOWN"
        message = str(exc)[:200]
        logger.warning("✗ %s — %s error: %s", name, url, message)

    # Only notify on status transitions (or first-seen DOWN)
    prev = _previous_status.get(name)
    _previous_status[name] = status

    should_notify = (prev is None and status == "DOWN") or (prev is not None and prev != status)

    if should_notify:
        timestamp = datetime.now(timezone.utc).isoformat()
        if cooldown_manager.can_send(name, status):
            await send_alert(service_name=name, status=status, message=message, timestamp=timestamp)
        else:
            logger.debug("Alert suppressed by cooldown: %s [%s]", name, status)


async def _monitor_loop(target: Dict[str, Any]) -> None:
    """Continuously check a single target at its configured interval."""
    name = target.get("name", "Unknown")
    interval = int(target.get("interval", _DEFAULT_INTERVAL))
    logger.info("Monitor started: %s (every %ds)", name, interval)

    while True:
        try:
            await _check_single_target(target)
        except Exception as exc:
            logger.error("Unhandled error checking %s: %s", name, exc)
        await asyncio.sleep(interval)


async def start_monitoring() -> List[asyncio.Task]:
    """Launch one background task per configured target. Returns tasks for cancellation."""
    if not MONITOR_ENABLED:
        logger.info("Monitoring disabled (MONITOR_ENABLED=false)")
        return []

    targets = _load_targets()
    if not targets:
        logger.info("No monitor targets configured — scheduler idle")
        return []

    tasks = [
        asyncio.create_task(_monitor_loop(t), name=f"monitor-{t.get('name', 'unknown')}")
        for t in targets
    ]
    logger.info("Monitoring scheduler started with %d target(s)", len(tasks))
    return tasks


async def stop_monitoring(tasks: List[asyncio.Task]) -> None:
    """Cancel all monitor tasks gracefully on shutdown."""
    for task in tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    logger.info("Monitoring scheduler stopped")


def get_monitor_status() -> Dict[str, Any]:
    """Return current known status of all monitored targets."""
    return {
        "enabled": MONITOR_ENABLED,
        "targets": _load_targets(),
        "current_status": dict(_previous_status),
    }
