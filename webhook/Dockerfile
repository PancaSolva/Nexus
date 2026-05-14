# ─────────────────────────────────────────────────────────────
# Asentinel Webhook — Production Docker Image
# Multi-stage build for a minimal, secure Python container.
# ─────────────────────────────────────────────────────────────

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN addgroup --system appgroup \
    && adduser --system --ingroup appgroup appuser \
    && mkdir -p /app/logs \
    && chown -R appuser:appgroup /app

USER appuser

EXPOSE 9000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000", "--workers", "1"]
