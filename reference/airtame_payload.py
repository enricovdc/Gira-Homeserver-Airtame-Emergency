"""Airtame Emergency Alert payload builder and validator.

Mirrors module/lib/airtame_payload.hsl. Endpoint and field semantics follow
the Airtame "Emergency alerts integrations - payload guidelines" docs:
https://help.airtame.com/hc/en-us/articles/28499448688029
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

DEFAULT_ENDPOINT = "https://airtame.cloud/api/v3.0/cloud/public/emergency-alerts"

ALLOWED_STATUSES = ("Initiated", "Resolved")
ALLOWED_TEMPLATES = ("high", "medium", "low")

MAX_HEADLINE_LEN = 200
MAX_DESCRIPTION_LEN = 2000


class PayloadValidationError(ValueError):
    """Raised when required payload fields are missing or invalid."""


@dataclass
class AlertConfig:
    """Configuration sourced from module parameters + runtime input overrides."""
    alert_id: str
    headline: str
    description: str
    template: str = "high"
    is_drill: bool = False
    duration_seconds: int = 300
    expires_at: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.alert_id or not self.alert_id.strip():
            raise PayloadValidationError("alert_id is required")
        if not self.headline or not self.headline.strip():
            raise PayloadValidationError("headline is required")
        if not self.description or not self.description.strip():
            raise PayloadValidationError("description is required")
        if len(self.headline) > MAX_HEADLINE_LEN:
            raise PayloadValidationError(
                f"headline exceeds {MAX_HEADLINE_LEN} characters"
            )
        if len(self.description) > MAX_DESCRIPTION_LEN:
            raise PayloadValidationError(
                f"description exceeds {MAX_DESCRIPTION_LEN} characters"
            )
        if self.template not in ALLOWED_TEMPLATES:
            raise PayloadValidationError(
                f"template must be one of {ALLOWED_TEMPLATES}, got {self.template!r}"
            )
        if self.duration_seconds <= 0:
            raise PayloadValidationError("duration_seconds must be > 0")


def _iso8601_utc(dt: datetime) -> str:
    # ISO 8601 with timezone offset, e.g. 2026-05-12T08:00:00+00:00
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat(timespec="seconds")


def build_trigger_payload(
    cfg: AlertConfig,
    now: Optional[datetime] = None,
) -> dict:
    """Build a JSON-serializable payload for triggering an alert."""
    moment = now or datetime.now(timezone.utc)
    expires_at = cfg.expires_at or _iso8601_utc(
        moment + timedelta(seconds=cfg.duration_seconds)
    )
    return {
        "id": cfg.alert_id,
        "status": "Initiated",
        "template": cfg.template,
        "headline": cfg.headline,
        "description": cfg.description,
        "isDrill": cfg.is_drill,
        "expiresAt": expires_at,
    }


def build_clear_payload(alert_id: str) -> dict:
    """Build a payload that resolves a previously initiated alert."""
    if not alert_id or not alert_id.strip():
        raise PayloadValidationError("alert_id is required to clear an alert")
    return {"id": alert_id, "status": "Resolved"}
