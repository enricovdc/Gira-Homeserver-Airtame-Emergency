"""HSL3 LogicModule behavior tests.

Drives the module the way the HSL3 runtime would: on_init with inputs+store,
on_calc with inputs whose .changed() reflects what shifted. The real runtime
shells HTTP into a background thread; tests replace threading.Thread so the
work runs synchronously and stubs _send_http so no real network IO occurs.
"""
import json

import pytest

import airtame_hsl3_module as hsl3mod
import tests._hsl3_stub as stub


DEFAULTS = {
    "trigger": 0, "clear": 0,
    "headline": "Emergency",
    "description": "Emergency alert from Gira HomeServer.",
    "template": "high", "is_drill": 0, "duration_seconds": 300,
    "api_endpoint": "https://airtame.cloud/api/v3.0/cloud/public/emergency-alerts",
    "api_key": "testkey1234567890",
    "alert_id_prefix": "gira-hs",
    "timeout_seconds": 5, "max_retries": 2, "debounce_ms": 0,
}


@pytest.fixture(autouse=True)
def synchronous_threads(monkeypatch):
    """HSL3 module spawns daemon threads for HTTP; run them synchronously."""
    class _SyncThread:
        def __init__(self, target=None, args=(), kwargs=None, daemon=None):
            self._target = target
            self._args = args
            self._kwargs = kwargs or {}
        def start(self):
            self._target(*self._args, **self._kwargs)
    monkeypatch.setattr(hsl3mod.threading, "Thread", _SyncThread)


def _build(http_responses):
    """Construct a module + drive on_init; return (module, hsl3, send_calls)."""
    hsl3 = stub.Hsl3()
    inst = hsl3mod.LogicModule(hsl3)
    calls = []
    def _err_for(status):
        if 200 <= status < 300:     return ""
        if status in (401, 403):    return "auth"
        if status == 429:           return "rate-limit"
        if 500 <= status < 600:     return "server"
        return "transport"
    def fake_send(url, headers, body, timeout, max_retries):
        calls.append({"url": url, "headers": dict(headers),
                      "body": json.loads(body), "timeout": timeout})
        item = http_responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        status, body_text = item
        return status, body_text, _err_for(status)
    inst._send_http = fake_send

    inputs = stub.make_inputs(**DEFAULTS)
    store = stub.make_store()
    inst.on_init(inputs, store)
    inputs._clear_changed()  # subsequent on_calc only fires for things we change
    return inst, hsl3, inputs, calls


def _calc(inst, inputs, changes):
    """Apply the given identifier->value changes and invoke on_calc."""
    inputs._clear_changed()
    for k, v in changes.items():
        inputs._set(k, v, mark_changed=True)
    inst.on_calc(inputs)


def test_rising_trigger_sends_initiated_and_sets_outputs():
    inst, hsl3, inputs, calls = _build([(200, "{}")])
    _calc(inst, inputs, {"trigger": 1})

    assert hsl3.outputs["active"] == 1.0
    assert hsl3.outputs["last_status_code"] == 200.0
    assert hsl3.outputs["last_message"] == b"alert initiated"
    assert hsl3.outputs["last_alert_id"].startswith(b"gira-hs-")
    assert hsl3.store["active"] == 1.0

    body = calls[0]["body"]
    assert body["status"] == "Initiated"
    assert body["headline"] == "Emergency"
    assert body["template"] == "high"
    assert body["id"] == hsl3.outputs["last_alert_id"].decode("iso-8859-15")


def test_held_high_trigger_only_fires_once():
    inst, hsl3, inputs, calls = _build([(200, "{}")])
    _calc(inst, inputs, {"trigger": 1})
    _calc(inst, inputs, {"trigger": 1})  # still high - no new edge
    _calc(inst, inputs, {"trigger": 1})
    assert len(calls) == 1


def test_clear_after_trigger_sends_resolved_with_same_id():
    inst, hsl3, inputs, calls = _build([(200, "{}"), (200, "{}")])
    _calc(inst, inputs, {"trigger": 1})
    alert_id_bytes = hsl3.outputs["last_alert_id"]
    alert_id = alert_id_bytes.decode("iso-8859-15")

    _calc(inst, inputs, {"trigger": 0})
    _calc(inst, inputs, {"clear": 1})

    assert hsl3.outputs["active"] == 0.0
    assert hsl3.outputs["last_message"] == b"alert resolved"
    assert calls[1]["body"] == {"id": alert_id, "status": "Resolved"}


def test_clear_without_active_alert_is_noop():
    inst, hsl3, inputs, calls = _build([])
    _calc(inst, inputs, {"clear": 1})
    assert calls == []


def test_validation_failure_blocks_http():
    inst, hsl3, inputs, calls = _build([])
    _calc(inst, inputs, {"trigger": 1, "headline": "x" * 201})
    assert calls == []
    assert b"headline exceeds" in hsl3.outputs["last_message"]


def test_auth_error_surfaces_to_outputs():
    inst, hsl3, inputs, calls = _build([(401, "bad token")])
    _calc(inst, inputs, {"trigger": 1})
    assert hsl3.outputs["last_status_code"] == 401.0
    assert b"auth" in hsl3.outputs["last_message"]
    assert hsl3.outputs["active"] == 0.0


def test_timeout_surfaces_to_outputs():
    import requests as _requests
    inst, hsl3, inputs, calls = _build([_requests.Timeout("timed out")])
    # Replace _send_http with one that retries internally per the real signature.
    real_send = inst._send_http
    def send_raising(url, headers, body, timeout, max_retries):
        return 0, "", "timeout"
    inst._send_http = send_raising
    _calc(inst, inputs, {"trigger": 1})
    assert hsl3.outputs["last_status_code"] == 0.0
    assert b"timeout" in hsl3.outputs["last_message"]


def test_secret_is_masked_in_debug_log():
    inst, hsl3, inputs, calls = _build([(200, "{}")])
    _calc(inst, inputs, {"trigger": 1})
    flat = " ".join(hsl3.debug.records)
    assert DEFAULTS["api_key"] not in flat
    assert "te" in flat and "90" in flat


def test_non_https_endpoint_surfaces_config_error():
    inst, hsl3, inputs, calls = _build([])
    _calc(inst, inputs, {"trigger": 1, "api_endpoint": "http://airtame.cloud/x"})
    assert calls == []
    assert b"config" in hsl3.outputs["last_message"]


def test_on_init_restores_active_from_store():
    hsl3 = stub.Hsl3()
    inst = hsl3mod.LogicModule(hsl3)
    inputs = stub.make_inputs(**DEFAULTS)
    store = stub.make_store(active=1, active_alert_id="prev-alert-7",
                            counter=42, last_trig_val=0, last_trig_ts_ms=0,
                            last_clr_val=0, last_clr_ts_ms=0)
    inst.on_init(inputs, store)

    assert inst._active is True
    assert inst._active_alert_id == "prev-alert-7"
    assert inst._counter == 42
    assert hsl3.outputs["active"] == 1.0
    assert hsl3.outputs["last_alert_id"] == b"prev-alert-7"


def test_payload_builders_match_airtame_spec():
    inst = hsl3mod.LogicModule(stub.Hsl3())
    body = inst._build_trigger_body("abc-123", "Lockdown", "Shelter in place.",
                                    "high", False, 600)
    parsed = json.loads(body)
    assert parsed["status"] == "Initiated"
    assert parsed["template"] == "high"
    assert parsed["headline"] == "Lockdown"
    assert parsed["isDrill"] is False
    assert parsed["id"] == "abc-123"
    assert "expiresAt" in parsed and "+00:00" in parsed["expiresAt"]

    assert json.loads(inst._build_clear_body("abc-123")) == {
        "id": "abc-123", "status": "Resolved",
    }


def test_validate_rejects_bad_inputs():
    inst = hsl3mod.LogicModule(stub.Hsl3())
    cases = [
        (("",  "h", "d", "high",   10), "alert_id"),
        (("i", "",  "d", "high",   10), "headline"),
        (("i", "h", "d", "ultra",  10), "template"),
        (("i", "h", "d", "high",   0),  "duration"),
    ]
    for args, needle in cases:
        assert needle in inst._validate(*args)
    assert inst._validate("i", "h", "d", "high", 10) == ""
    # description is optional per the Airtame payload guidelines.
    assert inst._validate("i", "h", "", "high", 10) == ""


@pytest.mark.parametrize("template", [
    "high", "medium", "low",
    "blank", "all-clear", "hold",
    "secure", "lockdown", "evacuate", "shelter",
])
def test_all_airtame_alert_templates_accepted_hsl3(template):
    inst = hsl3mod.LogicModule(stub.Hsl3())
    assert inst._validate("i", "h", "d", template, 10) == ""


def test_mask_helper():
    inst = hsl3mod.LogicModule(stub.Hsl3())
    assert inst._mask("") == ""
    assert inst._mask("ab") == "**"
    assert inst._mask("abcdefgh") == "ab****gh"
    assert "k" * 32 != inst._mask("k" * 32)
