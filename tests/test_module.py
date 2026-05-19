"""End-to-end behavior tests driving on_input_value(), as the HS would."""
import json
import pytest

import airtame_module


VALID_INPUT_DEFAULTS = {
    # Match the init_values declared in config.xml.
    1: 0,   # TRIGGER
    2: 0,   # CLEAR
    3: "Emergency",
    4: "Emergency alert from Gira HomeServer.",
    5: "high",
    6: 0,   # IS_DRILL
    7: 300, # DURATION_SECONDS
    8: "https://airtame.cloud/api/v3.0/cloud/public/emergency-alerts",
    9: "testkey1234567890",
    10: "gira-hs",
    11: 5,  # TIMEOUT_SECONDS
    12: 2,  # MAX_RETRIES
    13: 0,  # DEBOUNCE_MS (zero so tests don't need fake clocks)
    14: "json",            # PAYLOAD_FORMAT
    15: "gira-homeserver", # SENDER_ID
    16: "Safety",          # CAP_CATEGORY
    17: 0,                 # PROBE_NOW
}


class FakeHTTP(object):
    def __init__(self, responses, parse_json=True):
        self.responses = list(responses)
        self.calls = []
        self._parse_json = parse_json

    def __call__(self, url, headers, body, timeout):
        self.calls.append({"url": url, "headers": dict(headers),
                           "body": json.loads(body) if self._parse_json else body,
                           "timeout": timeout})
        item = self.responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def _build(responses):
    inst = airtame_module.AirtameEmergencyAlert24815(homeserver_context=object())
    inst._input_values.update(VALID_INPUT_DEFAULTS)
    inst._http_post = FakeHTTP(responses)
    inst.on_init()  # establish output defaults like the real HS does
    return inst


def _fire(inst, index, value):
    inst._input_values[index] = value
    inst.on_input_value(index, value)


def test_rising_trigger_sends_initiated_and_sets_outputs(monkeypatch):
    monkeypatch.setattr(airtame_module.time, "sleep", lambda _: None)
    inst = _build([(200, "{}")])

    _fire(inst, inst.PIN_I_TRIGGER, 0)  # baseline
    _fire(inst, inst.PIN_I_TRIGGER, 1)  # rising edge

    fw = inst
    assert fw._output_values[inst.PIN_O_ACTIVE] == 1
    assert fw._output_values[inst.PIN_O_LAST_STATUS_CODE] == 200
    assert fw._output_values[inst.PIN_O_LAST_MESSAGE] == "alert initiated"
    assert fw._output_values[inst.PIN_O_LAST_ALERT_ID].startswith("gira-hs-")
    assert fw._remanent_values[inst.REM_ACTIVE] == 1
    # success_pulse was set high then low (pulse)
    pulse_writes = [v for (p, v) in fw._output_history if p == inst.PIN_O_SUCCESS_PULSE]
    assert pulse_writes[-2:] == [1, 0]

    sent = inst._http_post.calls[0]["body"]
    assert sent["status"] == "Initiated"
    assert sent["headline"] == "Emergency"
    assert sent["template"] == "high"
    assert sent["id"] == fw._output_values[inst.PIN_O_LAST_ALERT_ID]


def test_held_high_trigger_only_fires_once(monkeypatch):
    monkeypatch.setattr(airtame_module.time, "sleep", lambda _: None)
    inst = _build([(200, "{}")])

    _fire(inst, inst.PIN_I_TRIGGER, 1)
    _fire(inst, inst.PIN_I_TRIGGER, 1)
    _fire(inst, inst.PIN_I_TRIGGER, 1)

    assert len(inst._http_post.calls) == 1


def test_clear_after_trigger_sends_resolved_with_same_id(monkeypatch):
    monkeypatch.setattr(airtame_module.time, "sleep", lambda _: None)
    inst = _build([(200, "{}"), (200, "{}")])

    _fire(inst, inst.PIN_I_TRIGGER, 0)
    _fire(inst, inst.PIN_I_TRIGGER, 1)
    alert_id = inst._output_values[inst.PIN_O_LAST_ALERT_ID]

    _fire(inst, inst.PIN_I_CLEAR, 0)
    _fire(inst, inst.PIN_I_CLEAR, 1)

    assert inst._output_values[inst.PIN_O_ACTIVE] == 0
    assert inst._output_values[inst.PIN_O_LAST_MESSAGE] == "alert resolved"
    assert inst._http_post.calls[1]["body"] == {"id": alert_id, "status": "Resolved"}


def test_clear_without_active_alert_is_noop(monkeypatch):
    monkeypatch.setattr(airtame_module.time, "sleep", lambda _: None)
    inst = _build([])  # no HTTP responses queued because none should fire
    _fire(inst, inst.PIN_I_CLEAR, 0)
    _fire(inst, inst.PIN_I_CLEAR, 1)
    assert inst._http_post.calls == []


def test_validation_failure_does_not_call_http(monkeypatch):
    monkeypatch.setattr(airtame_module.time, "sleep", lambda _: None)
    inst = _build([])
    # Force a headline that overruns MAX_HEADLINE_LEN so validation fires
    # (the bare empty case falls back to "Emergency" via _config's default).
    inst._input_values[inst.PIN_I_HEADLINE] = "x" * 201

    _fire(inst, inst.PIN_I_TRIGGER, 1)

    assert inst._http_post.calls == []
    msg = inst._output_values[inst.PIN_O_LAST_MESSAGE]
    assert "validation" in msg
    assert "headline exceeds" in msg


def test_auth_error_surfaces_to_outputs(monkeypatch):
    monkeypatch.setattr(airtame_module.time, "sleep", lambda _: None)
    inst = _build([(401, "bad token")])
    _fire(inst, inst.PIN_I_TRIGGER, 1)

    fw = inst
    assert fw._output_values[inst.PIN_O_LAST_STATUS_CODE] == 401
    assert "auth" in fw._output_values[inst.PIN_O_LAST_MESSAGE].lower()
    assert fw._output_values[inst.PIN_O_ACTIVE] == 0


def test_timeout_surfaces_to_outputs(monkeypatch):
    monkeypatch.setattr(airtame_module.time, "sleep", lambda _: None)
    err = airtame_module.URLError("timed out")
    inst = _build([err, err, err])
    _fire(inst, inst.PIN_I_TRIGGER, 1)

    fw = inst
    assert fw._output_values[inst.PIN_O_LAST_STATUS_CODE] == 0
    assert "timeout" in fw._output_values[inst.PIN_O_LAST_MESSAGE].lower()


def test_secret_is_masked_in_logger(monkeypatch):
    monkeypatch.setattr(airtame_module.time, "sleep", lambda _: None)
    inst = _build([(200, "{}")])
    _fire(inst, inst.PIN_I_TRIGGER, 1)
    flat = " ".join(rec[2] for rec in inst.LOGGER.records)
    assert VALID_INPUT_DEFAULTS[9] not in flat   # raw key never appears
    assert "te" in flat and "90" in flat          # masked prefix/suffix do


def test_non_https_endpoint_surfaces_config_error(monkeypatch):
    monkeypatch.setattr(airtame_module.time, "sleep", lambda _: None)
    inst = _build([])
    inst._input_values[inst.PIN_I_API_ENDPOINT] = "http://airtame.cloud/x"
    _fire(inst, inst.PIN_I_TRIGGER, 1)
    assert inst._http_post.calls == []
    assert "config" in inst._output_values[inst.PIN_O_LAST_MESSAGE]


def test_on_init_restores_active_from_remanent(monkeypatch):
    inst = _build([])
    inst._remanent_values[inst.REM_ACTIVE] = 1
    inst._remanent_values[inst.REM_ACTIVE_ALERT_ID] = "prev-alert-7"
    inst.on_init()
    assert inst._output_values[inst.PIN_O_ACTIVE] == 1
    assert inst._output_values[inst.PIN_O_LAST_ALERT_ID] == "prev-alert-7"


# ----- HSL2 + CAP format end-to-end ---------------------------------------

def test_cap_format_sends_application_xml_and_persists_sent_ts(monkeypatch):
    monkeypatch.setattr(airtame_module.time, "sleep", lambda _: None)
    inst = airtame_module.AirtameEmergencyAlert24815(homeserver_context=object())
    inst._input_values.update(VALID_INPUT_DEFAULTS)
    inst._input_values[14] = "cap"  # PAYLOAD_FORMAT
    inst._http_post = FakeHTTP([(200, "")], parse_json=False)
    inst.on_init()

    inst.on_input_value(inst.PIN_I_TRIGGER, 1)

    call = inst._http_post.calls[0]
    assert call["headers"]["Content-Type"] == "application/xml"
    # ACTIVE_SENT_TS must be persisted so a later CAP Cancel can reference it.
    sent_ts = inst._remanent_values[inst.REM_ACTIVE_SENT_TS]
    assert sent_ts and "+00:00" in sent_ts


# ----- HSL2 probe (Resolved with throwaway id, no emergency on screen) ----

def test_probe_sends_resolved_with_throwaway_id_and_lights_liveness(monkeypatch):
    monkeypatch.setattr(airtame_module.time, "sleep", lambda _: None)
    inst = airtame_module.AirtameEmergencyAlert24815(homeserver_context=object())
    inst._input_values.update(VALID_INPUT_DEFAULTS)
    inst._http_post = FakeHTTP([(200, "")])
    inst.on_init()

    inst.on_input_value(inst.PIN_I_PROBE_NOW, 1)

    # Wire format: Resolved with id containing "-probe-", and NEVER an Initiated.
    body = inst._http_post.calls[0]["body"]
    assert body["status"] == "Resolved", "probe must never initiate an alert"
    assert "-probe-" in body["id"], "probe id must be distinguishable"
    # Outputs reflect probe success and persist across restart.
    assert inst._output_values[inst.PIN_O_LIVENESS] == 1
    assert inst._output_values[inst.PIN_O_LAST_PROBE_STATUS_CODE] == 200
    assert inst._remanent_values[inst.REM_LIVENESS] == 1
    # Probe doesn't touch the live alert state.
    assert inst._output_values[inst.PIN_O_ACTIVE] == 0


def test_probe_failure_clears_liveness_and_does_not_emit_active(monkeypatch):
    monkeypatch.setattr(airtame_module.time, "sleep", lambda _: None)
    inst = airtame_module.AirtameEmergencyAlert24815(homeserver_context=object())
    inst._input_values.update(VALID_INPUT_DEFAULTS)
    # Pre-seed liveness as 1 so the test sees it flip back to 0.
    inst._remanent_values[inst.REM_LIVENESS] = 1
    inst._http_post = FakeHTTP([(401, "bad token")])
    inst.on_init()

    inst.on_input_value(inst.PIN_I_PROBE_NOW, 1)

    assert inst._output_values[inst.PIN_O_LIVENESS] == 0
    assert inst._output_values[inst.PIN_O_LAST_PROBE_STATUS_CODE] == 401
    assert inst._remanent_values[inst.REM_LIVENESS] == 0
    # Still: probe must not have initiated anything.
    assert inst._http_post.calls[0]["body"]["status"] == "Resolved"
    assert inst._output_values[inst.PIN_O_ACTIVE] == 0


def test_probe_uses_json_even_when_payload_format_is_cap(monkeypatch):
    """A probe in CAP mode would need a <references> to a real prior alert
    and isn't a clean side-effect-free probe. Module forces JSON for probes."""
    monkeypatch.setattr(airtame_module.time, "sleep", lambda _: None)
    inst = airtame_module.AirtameEmergencyAlert24815(homeserver_context=object())
    inst._input_values.update(VALID_INPUT_DEFAULTS)
    inst._input_values[14] = "cap"
    inst._http_post = FakeHTTP([(200, "")])
    inst.on_init()

    inst.on_input_value(inst.PIN_I_PROBE_NOW, 1)

    assert inst._http_post.calls[0]["headers"]["Content-Type"] == "application/json"


def test_cap_clear_sends_cancel_xml_with_references(monkeypatch):
    monkeypatch.setattr(airtame_module.time, "sleep", lambda _: None)
    inst = airtame_module.AirtameEmergencyAlert24815(homeserver_context=object())
    inst._input_values.update(VALID_INPUT_DEFAULTS)
    inst._input_values[14] = "cap"
    inst._http_post = FakeHTTP([(200, ""), (200, "")], parse_json=False)
    inst.on_init()

    inst.on_input_value(inst.PIN_I_TRIGGER, 1)
    sent_ts = inst._remanent_values[inst.REM_ACTIVE_SENT_TS]
    active_id = inst._output_values[inst.PIN_O_LAST_ALERT_ID]

    inst.on_input_value(inst.PIN_I_CLEAR, 1)

    cancel = inst._http_post.calls[1]["body"]
    assert "<msgType>Cancel</msgType>" in cancel
    expected_ref = "gira-homeserver,%s,%s" % (active_id, sent_ts)
    assert "<references>" + expected_ref + "</references>" in cancel
    assert inst._output_values[inst.PIN_O_ACTIVE] == 0
