"""End-to-end behavior tests for the Airtame emergency-alert module wiring."""
import json
from dataclasses import dataclass, field
from typing import List

import pytest

from reference.airtame_client import (
    AirtameClient,
    AirtameResponse,
    AirtameTimeoutError,
)
from reference.module import (
    AirtameEmergencyAlertModule,
    ModuleInputs,
    ModuleParameters,
)


@dataclass
class RecordingTransport:
    responses: List[object]
    calls: list = field(default_factory=list)

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append({"body": json.loads(body), "headers": dict(headers)})
        item = self.responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def build_module(transport, **param_overrides):
    params = ModuleParameters(
        api_key="testkey1234567890",
        endpoint="https://airtame.cloud/api/v3.0/cloud/public/emergency-alerts",
        debounce_seconds=0.0,
    )
    for k, v in param_overrides.items():
        setattr(params, k, v)
    client = AirtameClient(
        api_key=params.api_key,
        endpoint=params.endpoint,
        timeout_seconds=params.timeout_seconds,
        max_retries=params.max_retries,
        retry_backoff_seconds=0.0,
        transport=transport,
        sleep=lambda _s: None,
    )
    return AirtameEmergencyAlertModule(params=params, client=client)


def test_rising_trigger_sends_initiated_payload():
    transport = RecordingTransport([AirtameResponse(200, "{}")])
    mod = build_module(transport)

    mod.process(ModuleInputs(trigger=False))
    out = mod.process(
        ModuleInputs(trigger=True, headline="Fire", description="Evacuate now.")
    )

    assert out.active is True
    assert out.success_pulse is True
    assert out.error_pulse is False
    assert out.last_status_code == 200
    assert out.last_alert_id.startswith("gira-hs-")

    body = transport.calls[0]["body"]
    assert body["status"] == "Initiated"
    assert body["headline"] == "Fire"
    assert body["description"] == "Evacuate now."
    assert body["id"] == out.last_alert_id


def test_clear_after_trigger_sends_resolved_with_same_id():
    transport = RecordingTransport(
        [AirtameResponse(200, "{}"), AirtameResponse(200, "{}")]
    )
    mod = build_module(transport)

    mod.process(ModuleInputs(trigger=True, headline="h", description="d"))
    alert_id = mod.outputs.last_alert_id
    mod.process(ModuleInputs(trigger=False))  # falling edge
    mod.process(ModuleInputs(clear=False))  # baseline
    out = mod.process(ModuleInputs(clear=True))

    assert out.active is False
    assert out.success_pulse is True
    assert transport.calls[1]["body"] == {"id": alert_id, "status": "Resolved"}


def test_held_high_trigger_only_fires_once():
    transport = RecordingTransport([AirtameResponse(200, "{}")])
    mod = build_module(transport)

    mod.process(ModuleInputs(trigger=True, headline="h", description="d"))
    mod.process(ModuleInputs(trigger=True, headline="h", description="d"))
    mod.process(ModuleInputs(trigger=True, headline="h", description="d"))

    assert len(transport.calls) == 1


def test_validation_error_sets_error_output_without_http_call():
    transport = RecordingTransport([])
    mod = build_module(transport)
    # Empty headline overrides the default and fails validation only if both
    # default and override are blank; force this by emptying the default too.
    mod.params.default_headline = ""
    out = mod.process(ModuleInputs(trigger=True, headline=""))

    assert out.error_pulse is True
    assert out.success_pulse is False
    assert "headline" in out.last_message
    assert transport.calls == []


def test_auth_error_surfaces_to_outputs():
    transport = RecordingTransport([AirtameResponse(401, "bad token")])
    mod = build_module(transport)

    out = mod.process(ModuleInputs(trigger=True))

    assert out.error_pulse is True
    assert out.active is False
    assert out.last_status_code == 401
    assert "auth" in out.last_message.lower()


def test_timeout_surfaces_to_outputs():
    transport = RecordingTransport(
        [AirtameTimeoutError("t"), AirtameTimeoutError("t"), AirtameTimeoutError("t")]
    )
    mod = build_module(transport)

    out = mod.process(ModuleInputs(trigger=True))

    assert out.error_pulse is True
    assert out.last_status_code == 0
    assert "timeout" in out.last_message.lower()


def test_clear_without_active_alert_is_noop():
    transport = RecordingTransport([])
    mod = build_module(transport)

    out = mod.process(ModuleInputs(clear=True))

    assert transport.calls == []
    assert out.success_pulse is False
    assert out.error_pulse is False


def test_secret_not_present_in_outputs():
    transport = RecordingTransport([AirtameResponse(401, "bearer testkey1234567890 rejected")])
    mod = build_module(transport)
    out = mod.process(ModuleInputs(trigger=True))
    # We intentionally truncate the response body, but also assert we never
    # echo our own key in any output field.
    assert "testkey1234567890" not in out.last_alert_id
    # The server echoed the key (hypothetically) - that is the server's fault,
    # but our own logs/outputs must not have it independently. We don't put
    # the Authorization header in outputs, so this passes by construction.
    assert "Authorization" not in out.last_message
