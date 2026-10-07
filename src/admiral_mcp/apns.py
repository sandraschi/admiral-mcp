"""APNs push relay using aioapns (HTTP/2, token auth with .p8)."""

import logging
import time
from pathlib import Path

from admiral_mcp.config import get_config

logger = logging.getLogger(__name__)


class APNsRelay:
    """Sends push notifications to iOS devices via Apple APNs.

    Uses aioapns for HTTP/2 connection pooling and JWT token auth.
    Gracefully degrades if APNs is not configured.
    """

    def __init__(self) -> None:
        self._client = None
        config = get_config()
        self._configured = config.apns_configured
        self._device_token = config.apns_device_token
        self._topic = config.apns_topic
        self._use_sandbox = config.apns_use_sandbox
        if self._configured:
            self._init_client(config)

    def _init_client(self, config) -> None:
        from aioapns import APNs

        key_path = Path(config.apns_key_path)
        if not key_path.exists():
            logger.error("APNs key not found at %s", key_path)
            self._configured = False
            return

        self._client = APNs(
            key=key_path.read_text(),
            key_id=config.apns_key_id,
            team_id=config.apns_team_id,
            topic=config.apns_topic,
            use_sandbox=config.apns_use_sandbox,
        )
        logger.info(
            "APNs configured (sandbox=%s, topic=%s)",
            config.apns_use_sandbox,
            config.apns_topic,
        )

    async def send_approval_alert(
        self,
        approval_id: str,
        run_id: str,
        summary: str,
        diff_ref: str | None = None,
    ) -> bool:
        """Send an actionable alert push with FLEET_APPROVAL category."""
        if not self._configured:
            logger.info("[no-apns] Would send approval alert: %s", approval_id)
            return False

        from aioapns import PRIORITY_HIGH, NotificationRequest

        payload = {
            "aps": {
                "alert": {
                    "title": "Approval Needed",
                    "subtitle": f"Run: {run_id}",
                    "body": summary[:200],
                },
                "category": "FLEET_APPROVAL",
                "mutable-content": 1,
                "badge": 1,
            },
            "approval_id": approval_id,
            "run_id": run_id,
            "diff_ref": diff_ref or "",
        }

        request = NotificationRequest(
            device_token=self._device_token,
            message=payload,
            priority=PRIORITY_HIGH,
            push_type="alert",
        )

        try:
            await self._client.send_notification(request)
            logger.info("APNs alert sent: approval_id=%s", approval_id)
            return True
        except Exception:
            logger.exception("APNs alert push failed")
            return False

    async def send_live_activity_update(
        self,
        run_id: str,
        phase: int,
        phase_name: str,
        status: str,
        cost: float,
        total_phases: int,
    ) -> bool:
        """Send a Live Activity update via APNs push type 'liveactivity'."""
        if not self._configured:
            logger.info("[no-apns] Would send LA update: %s phase %d", run_id, phase)
            return False

        from aioapns import PRIORITY_HIGH, NotificationRequest

        payload = {
            "aps": {
                "timestamp": int(time.time()),
                "event": "update",
                "content-state": {
                    "run_id": run_id,
                    "phase": phase,
                    "phase_name": phase_name,
                    "status": status,
                    "cost": f"${cost:.2f}",
                    "total_phases": total_phases,
                },
            }
        }

        request = NotificationRequest(
            device_token=self._device_token,
            message=payload,
            priority=PRIORITY_HIGH,
            push_type="liveactivity",
        )

        try:
            await self._client.send_notification(request)
            logger.info("APNs LA update sent: run_id=%s phase=%d", run_id, phase)
            return True
        except Exception:
            logger.exception("APNs LA push failed")
            return False

    @property
    def is_configured(self) -> bool:
        return self._configured
