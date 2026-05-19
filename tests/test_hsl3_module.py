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
    "payload_format": "json", "sender_id": "gira-homeserver",
    "cap_category": "Safety", "probe_now": 0,
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


def test_string_inputs_are_decoded_when_framework_returns_bytes():
    """Regression: at least one HS firmware returns string inputs as
    iso-8859-15 bytes (mirroring how the framework requires bytes for
    string OUTPUTS). The module must decode them before doing str
    operations like endpoint.startswith('https://')."""
    hsl3 = stub.Hsl3()
    inst = hsl3mod.LogicModule(hsl3)
    calls = []
    def _err_for(s):
        if 200 <= s < 300: return ""
        if s in (401, 403): return "auth"
        if s == 429: return "rate-limit"
        if 500 <= s < 600: return "server"
        return "transport"
    def fake_send(url, headers, body, timeout, max_retries):
        calls.append({"url": url, "body": body})
        return 200, "", _err_for(200)
    inst._send_http = fake_send

    # Pass every string field as bytes - mirror real firmware behavior.
    inputs = stub.make_inputs(
        trigger=0, clear=0,
        headline=b"Lockdown",
        description=b"Shelter in place.",
        template=b"high",
        is_drill=0,
        duration_seconds=300,
        api_endpoint=b"https://airtame.cloud/api/v3.0/cloud/public/emergency-alerts/webhooks/abc",
        api_key=b"key-bytes-1234567890",
        alert_id_prefix=b"gira-hs",
        timeout_seconds=5, max_retries=2, debounce_ms=0,
        payload_format=b"json",
        sender_id=b"gira-homeserver",
        cap_category=b"Safety",
    )
    inst.on_init(inputs, stub.make_store())
    inputs._clear_changed()
    inputs._set("trigger", 1, mark_changed=True)
    inst.on_calc(inputs)

    # No TypeError on .startswith("https://"); request actually fired.
    assert len(calls) == 1
    body = calls[0]["body"]
    assert "Lockdown" in body
    assert hsl3.outputs["active"] == 1.0


# ----- HSL3 probe -------------------------------------------------------


def _build_with_probe_threads(monkeypatch, http_responses):
    """Same as _build but installs the synchronous-thread monkeypatch
    locally so the test can be standalone (autouse fixture covers fixture
    tests but inline helpers like this one need explicit setup)."""
    class _SyncThread:
        def __init__(self, target=None, args=(), kwargs=None, daemon=None):
            self._t = target; self._a = args; self._k = kwargs or {}
        def start(self):
            self._t(*self._a, **(self._k))
    monkeypatch.setattr(hsl3mod.threading, "Thread", _SyncThread)
    return _build(http_responses)


def test_probe_sends_resolved_with_throwaway_id_and_lights_liveness():
    inst, hsl3, inputs, calls = _build([(200, "")])
    _calc(inst, inputs, {"probe_now": 1})

    # Wire format: Resolved with throwaway id, never Initiated.
    body = calls[0]["body"]
    assert body["status"] == "Resolved", "probe must never initiate an alert"
    assert "-probe-" in body["id"]
    # Outputs reflect probe success.
    assert hsl3.outputs["liveness"] == 1.0
    assert hsl3.outputs["last_probe_status_code"] == 200.0
    assert hsl3.store["liveness"] == 1.0
    # Probe does NOT touch the live alert state.
    assert hsl3.outputs["active"] == 0.0


def test_probe_failure_clears_liveness():
    inst, hsl3, inputs, calls = _build([(401, "bad token")])
    # Pre-set liveness=1 in the module so the test sees it flip back.
    inst._liveness = 1
    _calc(inst, inputs, {"probe_now": 1})

    assert hsl3.outputs["liveness"] == 0.0
    assert hsl3.outputs["last_probe_status_code"] == 401.0
    assert hsl3.store["liveness"] == 0.0
    assert calls[0]["body"]["status"] == "Resolved"
    assert hsl3.outputs["active"] == 0.0


def test_probe_uses_json_even_when_payload_format_is_cap():
    """Probe always uses JSON regardless of payload_format - CAP Cancel
    needs <references> to a real prior alert."""
    hsl3 = stub.Hsl3()
    inst = hsl3mod.LogicModule(hsl3)
    inst._send_http = lambda *a, **kw: (200, "", "")
    inputs = stub.make_inputs(**dict(DEFAULTS, payload_format="cap"))
    inst.on_init(inputs, stub.make_store())
    inputs._clear_changed()

    captured = []
    def fake(url, headers, body, timeout, max_retries):
        captured.append({"headers": dict(headers), "body": json.loads(body)})
        return 200, "", ""
    inst._send_http = fake
    inputs._set("probe_now", 1, mark_changed=True)
    inst.on_calc(inputs)

    assert captured[0]["headers"]["Content-Type"] == "application/json"
    assert captured[0]["body"]["status"] == "Resolved"


def test_on_init_restores_liveness_from_store():
    hsl3 = stub.Hsl3()
    inst = hsl3mod.LogicModule(hsl3)
    store = stub.make_store(liveness=1)
    inst.on_init(stub.make_inputs(**DEFAULTS), store)
    assert hsl3.outputs["liveness"] == 1.0
    assert inst._liveness == 1


def test_string_stores_are_persisted_as_bytes_not_str():
    """Regression: HS3 set_store requires bytes for string-typed stores
    (mirroring set_output). Persisting active_alert_id and active_sent_ts
    as str raised `ValueError: Value must be of type bytes` on the real
    firmware."""
    hsl3 = stub.Hsl3()
    inst = hsl3mod.LogicModule(hsl3)
    inst._send_http = lambda *a, **kw: (200, "", "")
    inputs = stub.make_inputs(**DEFAULTS)
    inst.on_init(inputs, stub.make_store())
    inputs._clear_changed()
    inputs._set("trigger", 1, mark_changed=True)
    inst.on_calc(inputs)

    # String-typed stores must land as bytes, numeric stores as float.
    assert isinstance(hsl3.store["active_alert_id"], bytes)
    assert isinstance(hsl3.store["active_sent_ts"], bytes)
    assert isinstance(hsl3.store["active"], float)
    assert hsl3.store["active"] == 1.0
