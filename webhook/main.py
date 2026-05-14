"""
Asentinel Webhook — FastAPI Application

Routes:
  POST /webhook        — Receive monitoring payloads (from Laravel or custom)
  POST /webhook/test   — Send a test notification
  GET  /health         — Liveness probe
  GET  /status         — Monitor & cooldown state
"""

import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Literal

import asyncio
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from utils.logger import logger
from utils.cooldown import cooldown_manager
from services.telegram import send_alert
from services.monitor import start_monitoring, stop_monitoring, get_monitor_status

WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "")
APP_VERSION = "1.0.0"


# ─── Pydantic Models ─────────────────────────────────────────

class WebhookPayload(BaseModel):
    """Incoming webhook event payload."""
    service_name: str = Field(..., min_length=1)
    status: Literal["UP", "DOWN", "up", "down"]
    message: str = Field(default="")
    timestamp: str = Field(default="")


class WebhookResponse(BaseModel):
    """Standard response envelope."""
    success: bool
    message: str
    data: dict | None = None


# ─── Lifespan ────────────────────────────────────────────────

_monitor_tasks: List[asyncio.Task] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _monitor_tasks
    logger.info("🚀 Asentinel Webhook v%s starting…", APP_VERSION)
    _monitor_tasks = await start_monitoring()
    yield
    logger.info("🛑 Shutting down…")
    await stop_monitoring(_monitor_tasks)


# ─── App ─────────────────────────────────────────────────────

app = FastAPI(
    title="Asentinel Webhook",
    description="Webhook receiver & monitoring notifier for Asentinel infrastructure.",
    version=APP_VERSION,
    lifespan=lifespan,
)


# ─── Helpers ─────────────────────────────────────────────────

def _validate_secret(provided: str | None) -> None:
    """Raise 401 if a secret is configured and the request doesn't match."""
    if WEBHOOK_SECRET and provided != WEBHOOK_SECRET:
        logger.warning("Unauthorized webhook attempt (bad secret)")
        raise HTTPException(status_code=401, detail="Invalid or missing webhook secret")


def _normalise_timestamp(raw: str) -> str:
    """Return the given timestamp, or UTC now if empty."""
    return raw if raw else datetime.now(timezone.utc).isoformat()


# ─── Routes ──────────────────────────────────────────────────

@app.post("/webhook", response_model=WebhookResponse)
async def receive_webhook(
    payload: WebhookPayload,
    x_webhook_secret: str | None = Header(default=None),
):
    """Validate, check cooldown, and forward to Telegram."""
    _validate_secret(x_webhook_secret)

    status_upper = payload.status.upper()
    timestamp = _normalise_timestamp(payload.timestamp)

    logger.info("Webhook received: service=%s status=%s", payload.service_name, status_upper)

    if not cooldown_manager.can_send(payload.service_name, status_upper):
        logger.info("Alert suppressed by cooldown: %s [%s]", payload.service_name, status_upper)
        return WebhookResponse(
            success=True,
            message="Received but alert suppressed (cooldown active)",
            data={"service_name": payload.service_name, "status": status_upper, "alert_sent": False},
        )

    sent = await send_alert(
        service_name=payload.service_name,
        status=status_upper,
        message=payload.message,
        timestamp=timestamp,
    )

    return WebhookResponse(
        success=True,
        message="Webhook processed",
        data={"service_name": payload.service_name, "status": status_upper, "alert_sent": sent},
    )


@app.post("/webhook/test", response_model=WebhookResponse)
async def test_webhook(x_webhook_secret: str | None = Header(default=None)):
    """Send a test DOWN alert to verify Telegram integration."""
    _validate_secret(x_webhook_secret)
    logger.info("Test notification triggered")

    sent = await send_alert(
        service_name="Test-Service",
        status="DOWN",
        message="This is a TEST alert from Asentinel Webhook",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    return WebhookResponse(
        success=True,
        message="Test notification sent" if sent else "Test notification failed",
        data={"alert_sent": sent},
    )


@app.get("/health")
async def health_check():
    """Liveness probe."""
    return {"status": "healthy", "version": APP_VERSION, "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/status")
async def system_status(x_webhook_secret: str | None = Header(default=None)):
    """Return monitor & cooldown state."""
    _validate_secret(x_webhook_secret)
    return {
        "version": APP_VERSION,
        "monitoring": get_monitor_status(),
        "cooldown": cooldown_manager.get_status(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ─── Global Error Handler ─────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(status_code=500, content={"success": False, "message": "Internal server error"})


# ─── CLI Entry Point ─────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "9000"))
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=os.getenv("APP_DEBUG", "false").lower() == "true",
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
