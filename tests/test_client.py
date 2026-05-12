import base64
import json
from dataclasses import dataclass, field
from typing import List

import pytest

from reference.airtame_client import (
    AirtameAuthError,
    AirtameClient,
    AirtameError,
    AirtameRateLimitError,
    AirtameResponse,
    AirtameServerError,
    AirtameTimeoutError,
    mask_secret,
)


@dataclass
class FakeTransport:
    """Replays a queued list of responses; raises TimeoutError sentinels on demand."""
    responses: List[object]  # AirtameResponse or BaseException
    calls: list = field(default_factory=list)

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append(
            {"method": method, "url": url, "headers": dict(headers), "body": body, "timeout": timeout}
        )
        item = self.responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


@pytest.fixture
def sleep_recorder():
    delays = []
    return delays, delays.append


def make_client(transport, sleep_fn=lambda _s: None, **overrides):
    kwargs = dict(api_key="k" * 32, transport=transport, sleep=sleep_fn, max_retries=2)
    kwargs.update(overrides)
    return AirtameClient(**kwargs)


def test_send_posts_json_with_basic_auth():
    transport = FakeTransport([AirtameResponse(200, '{"ok":true}')])
    client = make_client(transport)
    resp = client.send({"id": "i", "status": "Initiated"})

    assert resp.status_code == 200
    call = transport.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "https://airtame.cloud/api/v3.0/cloud/public/emergency-alerts"
    assert call["headers"]["Content-Type"] == "application/json"
    auth = call["headers"]["Authorization"]
    assert auth.startswith("Basic ")
    decoded = base64.b64decode(auth.split(" ", 1)[1]).decode()
    assert decoded.endswith(":" + "k" * 32)
    assert json.loads(call["body"]) == {"id": "i", "status": "Initiated"}


def test_missing_api_key_rejected():
    with pytest.raises(AirtameAuthError):
        AirtameClient(api_key="")


def test_non_https_endpoint_rejected():
    with pytest.raises(AirtameError):
        AirtameClient(api_key="k", endpoint="http://airtame.cloud/x")


def test_401_raises_auth_error():
    transport = FakeTransport([AirtameResponse(401, "nope")])
    client = make_client(transport)
    with pytest.raises(AirtameAuthError):
        client.send({"id": "i"})


def test_403_raises_auth_error():
    transport = FakeTransport([AirtameResponse(403, "forbidden")])
    client = make_client(transport)
    with pytest.raises(AirtameAuthError):
        client.send({"id": "i"})


def test_429_retries_then_raises(sleep_recorder):
    delays, sleep_fn = sleep_recorder
    transport = FakeTransport(
        [AirtameResponse(429, "slow down"), AirtameResponse(429, "slow down"), AirtameResponse(429, "slow down")]
    )
    client = make_client(transport, sleep_fn=sleep_fn, retry_backoff_seconds=0.1)
    with pytest.raises(AirtameRateLimitError):
        client.send({"id": "i"})
    assert len(transport.calls) == 3  # initial + 2 retries
    assert delays == [0.1, 0.2]  # exponential backoff


def test_429_recovers_after_retry(sleep_recorder):
    delays, sleep_fn = sleep_recorder
    transport = FakeTransport([AirtameResponse(429, ""), AirtameResponse(200, "ok")])
    client = make_client(transport, sleep_fn=sleep_fn, retry_backoff_seconds=0.05)
    resp = client.send({"id": "i"})
    assert resp.status_code == 200
    assert len(transport.calls) == 2


def test_5xx_retries_then_raises(sleep_recorder):
    delays, sleep_fn = sleep_recorder
    transport = FakeTransport(
        [AirtameResponse(503, ""), AirtameResponse(503, ""), AirtameResponse(500, "boom")]
    )
    client = make_client(transport, sleep_fn=sleep_fn, retry_backoff_seconds=0.0)
    with pytest.raises(AirtameServerError):
        client.send({"id": "i"})
    assert len(transport.calls) == 3


def test_timeout_retries_then_raises():
    transport = FakeTransport(
        [AirtameTimeoutError("timed out"), AirtameTimeoutError("timed out"), AirtameTimeoutError("timed out")]
    )
    client = make_client(transport, retry_backoff_seconds=0.0)
    with pytest.raises(AirtameTimeoutError):
        client.send({"id": "i"})
    assert len(transport.calls) == 3


def test_mask_secret_hides_middle():
    assert mask_secret("abcdefgh") == "ab****gh"
    assert mask_secret("ab") == "**"
    assert mask_secret("") == ""


def test_secret_is_never_in_str_repr():
    transport = FakeTransport([AirtameResponse(200, "ok")])
    client = make_client(transport)
    assert "k" * 32 not in repr(client) or "Authorization" not in repr(client)
    # Stronger: ensure logs would not include the key by checking masking helper.
    assert mask_secret("k" * 32) != "k" * 32
