from datetime import datetime, timezone

import pytest

from reference.airtame_payload import (
    AlertConfig,
    PayloadValidationError,
    build_clear_payload,
    build_trigger_payload,
)


def test_trigger_payload_has_all_documented_fields():
    cfg = AlertConfig(
        alert_id="abc-123",
        headline="Lockdown",
        description="Shelter in place.",
        template="high",
        is_drill=False,
        duration_seconds=600,
    )
    fixed_now = datetime(2026, 5, 12, 8, 0, 0, tzinfo=timezone.utc)
    payload = build_trigger_payload(cfg, now=fixed_now)
    assert payload == {
        "id": "abc-123",
        "status": "Initiated",
        "template": "high",
        "headline": "Lockdown",
        "description": "Shelter in place.",
        "isDrill": False,
        "expiresAt": "2026-05-12T08:10:00+00:00",
    }


def test_explicit_expires_at_is_preserved():
    cfg = AlertConfig(
        alert_id="x",
        headline="h",
        description="d",
        expires_at="2026-05-12T09:00:00+00:00",
    )
    payload = build_trigger_payload(cfg, now=datetime(2026, 5, 12, 8, tzinfo=timezone.utc))
    assert payload["expiresAt"] == "2026-05-12T09:00:00+00:00"


def test_clear_payload_only_id_and_status():
    assert build_clear_payload("abc-123") == {"id": "abc-123", "status": "Resolved"}


@pytest.mark.parametrize(
    "kwargs,msg",
    [
        ({"alert_id": "", "headline": "h", "description": "d"}, "alert_id"),
        ({"alert_id": "i", "headline": "", "description": "d"}, "headline"),
        ({"alert_id": "i", "headline": "h", "description": ""}, "description"),
        ({"alert_id": "i", "headline": "h", "description": "d", "template": "ultra"}, "template"),
        ({"alert_id": "i", "headline": "h", "description": "d", "duration_seconds": 0}, "duration"),
    ],
)
def test_invalid_config_raises(kwargs, msg):
    with pytest.raises(PayloadValidationError) as exc:
        AlertConfig(**kwargs)
    assert msg in str(exc.value).lower()


def test_clear_requires_id():
    with pytest.raises(PayloadValidationError):
        build_clear_payload("")
