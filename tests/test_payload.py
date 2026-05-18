import json

import pytest

import airtame_module
import tests._hsl20_4_stub as stub


def _make_instance():
    cls = airtame_module.AirtameEmergencyAlert24815
    return cls(homeserver_context=object())


def test_trigger_payload_shape(monkeypatch):
    inst = _make_instance()
    # Freeze "now" at 2025-05-18T08:00:00Z. gmtime() unpatched still works
    # because we only override .time(); patch is auto-restored after the test.
    monkeypatch.setattr(airtame_module.time, "time", lambda: 1747555200)
    body = inst._build_trigger_body(
        alert_id="abc-123",
        headline="Lockdown",
        description="Shelter in place.",
        template="high",
        is_drill=False,
        duration=600,
    )
    parsed = json.loads(body)
    assert parsed == {
        "id": "abc-123",
        "status": "Initiated",
        "template": "high",
        "headline": "Lockdown",
        "description": "Shelter in place.",
        "isDrill": False,
        "expiresAt": "2025-05-18T08:10:00+00:00",
    }


def test_clear_payload_shape():
    inst = _make_instance()
    body = inst._build_clear_body("abc-123")
    assert json.loads(body) == {"id": "abc-123", "status": "Resolved"}


@pytest.mark.parametrize(
    "kwargs,needle",
    [
        ({"alert_id": "",  "headline": "h", "description": "d", "template": "high",   "duration": 10}, "alert_id"),
        ({"alert_id": "i", "headline": "",  "description": "d", "template": "high",   "duration": 10}, "headline"),
        ({"alert_id": "i", "headline": "h", "description": "d", "template": "ultra",  "duration": 10}, "template"),
        ({"alert_id": "i", "headline": "h", "description": "d", "template": "high",   "duration": 0},  "duration"),
        ({"alert_id": "i", "headline": "x" * 201, "description": "d", "template": "high", "duration": 10}, "headline exceeds"),
        ({"alert_id": "i", "headline": "h", "description": "x" * 2001, "template": "high", "duration": 10}, "description exceeds"),
    ],
)
def test_validation_rejects(kwargs, needle):
    inst = _make_instance()
    msg = inst._validate(**kwargs)
    assert needle in msg


def test_description_is_optional_per_airtame_spec():
    """Per Airtame Emergency Alerts payload guidelines, description is
    optional (description? in the JSON schema)."""
    inst = _make_instance()
    assert inst._validate("i", "h", "",   "high", 10) == ""
    assert inst._validate("i", "h", None, "high", 10) == ""


@pytest.mark.parametrize("template", [
    "high", "medium", "low",
    "blank", "all-clear", "hold",
    "secure", "lockdown", "evacuate", "shelter",
])
def test_all_airtame_alert_templates_accepted(template):
    """All 10 AlertTemplate values from the docs must pass validation."""
    inst = _make_instance()
    assert inst._validate("i", "h", "d", template, 10) == ""


def test_validation_accepts_minimal_valid():
    inst = _make_instance()
    assert inst._validate("i", "h", "d", "high", 10) == ""
