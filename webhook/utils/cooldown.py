# Anti-spam cooldown manager — prevents duplicate alerts for the same
# service within a configurable window. Resets on status transitions.

import os
import time
from typing import Dict, Tuple

from utils.logger import logger


class CooldownManager:
    """
    Tracks per-service alert timestamps and blocks repeated alerts of the
    same status within the cooldown window.

    Rules:
      - First alert for a service → always allow.
      - Status transition (DOWN→UP or UP→DOWN) → always allow, reset timer.
      - Same status within cooldown window → block.
      - Same status after cooldown expires → allow, reset timer.
    """

    def __init__(self, cooldown_seconds: int | None = None):
        self.cooldown_seconds: int = cooldown_seconds or int(
            os.getenv("ALERT_COOLDOWN_SECONDS", "300")
        )
        # {service_key: (last_status, last_alert_epoch)}
        self._state: Dict[str, Tuple[str, float]] = {}
        logger.info("CooldownManager initialized — cooldown=%ds", self.cooldown_seconds)

    def can_send(self, service_name: str, status: str) -> bool:
        """Return True if an alert for this service is allowed right now."""
        now = time.time()
        key = service_name.strip().lower()
        status_upper = status.upper()

        if key not in self._state:
            self._state[key] = (status_upper, now)
            logger.debug("Cooldown PASS (first alert): %s [%s]", service_name, status)
            return True

        last_status, last_time = self._state[key]

        if last_status != status_upper:
            # Status changed — always allow and reset
            self._state[key] = (status_upper, now)
            logger.debug("Cooldown PASS (status change %s→%s): %s", last_status, status_upper, service_name)
            return True

        elapsed = now - last_time
        if elapsed >= self.cooldown_seconds:
            self._state[key] = (status_upper, now)
            logger.debug("Cooldown PASS (expired, %.0fs elapsed): %s [%s]", elapsed, service_name, status)
            return True

        logger.info("Cooldown BLOCK (%.0fs remaining): %s [%s]", self.cooldown_seconds - elapsed, service_name, status)
        return False

    def reset(self, service_name: str) -> None:
        """Clear cooldown state for a specific service."""
        self._state.pop(service_name.strip().lower(), None)
        logger.debug("Cooldown reset: %s", service_name)

    def reset_all(self) -> None:
        """Clear all cooldown state."""
        self._state.clear()
        logger.debug("All cooldowns reset")

    def get_status(self) -> Dict[str, dict]:
        """Return current cooldown info for all tracked services."""
        now = time.time()
        return {
            key: {
                "last_status": status,
                "last_alert_ago_seconds": round(now - last_time, 1),
                "cooldown_remaining_seconds": max(0, round(self.cooldown_seconds - (now - last_time), 1)),
            }
            for key, (status, last_time) in self._state.items()
        }


# Module-level singleton
cooldown_manager = CooldownManager()
