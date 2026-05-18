import base64

import pytest

import airtame_module


def _make_instance():
    return airtame_module.AirtameEmergencyAlert24815(homeserver_context=object())


class FakeHTTP(object):
    """Records calls to _http_post and replays a queued list of responses.

    Each item in `responses` is either a (status, body_text) tuple or an
    exception instance to raise when that attempt is made.
    """
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append({"url": url, "headers": dict(headers),
                           "body": body, "timeout": timeout})
        item = self.responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(airtame_module.time, "sleep", lambda _s: None)


def test_send_uses_basic_auth_and_https_endpoint(no_sleep):
    inst = _make_instance()
    fake = FakeHTTP([(200, '{"ok":true}')])
    inst._http_post = fake

    status, body, err = inst._send(
        '{"id":"i","status":"Initiated"}',
        "https://airtame.cloud/x",
        "k" * 32,
        timeout_s=5,
        max_retries=0,
    )
    assert (status, err) == (200, "")
    call = fake.calls[0]
    auth = call["headers"]["Authorization"]
    assert auth.startswith("Basic ")
    decoded = base64.b64decode(auth.split(" ", 1)[1]).decode()
    assert decoded == "gira:" + "k" * 32
    assert call["headers"]["Content-Type"] == "application/json"


def test_send_rejects_non_https_endpoint():
    inst = _make_instance()
    status, body, err = inst._send("{}", "http://airtame.cloud/x", "k",
                                   timeout_s=5, max_retries=0)
    assert err == "config-endpoint"


def test_send_rejects_empty_key():
    inst = _make_instance()
    status, body, err = inst._send("{}", "https://airtame.cloud/x", "",
                                   timeout_s=5, max_retries=0)
    assert err == "config-key"


def test_send_401_is_auth_error(no_sleep):
    inst = _make_instance()
    inst._http_post = FakeHTTP([(401, "nope")])
    status, body, err = inst._send("{}", "https://airtame.cloud/x", "k",
                                   timeout_s=5, max_retries=2)
    assert (status, err) == (401, "auth")


def test_send_403_is_auth_error(no_sleep):
    inst = _make_instance()
    inst._http_post = FakeHTTP([(403, "forbidden")])
    status, body, err = inst._send("{}", "https://airtame.cloud/x", "k",
                                   timeout_s=5, max_retries=2)
    assert (status, err) == (403, "auth")


def test_send_429_retries_then_gives_up(no_sleep):
    inst = _make_instance()
    fake = FakeHTTP([(429, ""), (429, ""), (429, "")])
    inst._http_post = fake
    status, body, err = inst._send("{}", "https://airtame.cloud/x", "k",
                                   timeout_s=5, max_retries=2)
    assert (status, err) == (429, "rate-limit")
    assert len(fake.calls) == 3


def test_send_429_then_200_recovers(no_sleep):
    inst = _make_instance()
    fake = FakeHTTP([(429, ""), (200, "ok")])
    inst._http_post = fake
    status, body, err = inst._send("{}", "https://airtame.cloud/x", "k",
                                   timeout_s=5, max_retries=2)
    assert (status, err) == (200, "")
    assert len(fake.calls) == 2


def test_send_5xx_retries_then_gives_up(no_sleep):
    inst = _make_instance()
    fake = FakeHTTP([(503, ""), (502, ""), (500, "boom")])
    inst._http_post = fake
    status, body, err = inst._send("{}", "https://airtame.cloud/x", "k",
                                   timeout_s=5, max_retries=2)
    assert err == "server"
    assert status == 500
    assert len(fake.calls) == 3


def test_send_timeout_retries_then_gives_up(no_sleep):
    inst = _make_instance()
    timeout = airtame_module.URLError("timed out")
    inst._http_post = FakeHTTP([timeout, timeout, timeout])
    status, body, err = inst._send("{}", "https://airtame.cloud/x", "k",
                                   timeout_s=5, max_retries=2)
    assert (status, err) == (0, "timeout")


def test_send_other_4xx_no_retry(no_sleep):
    inst = _make_instance()
    fake = FakeHTTP([(404, "not found")])
    inst._http_post = fake
    status, body, err = inst._send("{}", "https://airtame.cloud/x", "k",
                                   timeout_s=5, max_retries=2)
    assert (status, err) == (404, "transport")
    assert len(fake.calls) == 1


def test_mask_secret_helper():
    inst = _make_instance()
    assert inst._mask("") == ""
    assert inst._mask("ab") == "**"
    assert inst._mask("abcdefgh") == "ab****gh"
    assert inst._mask("k" * 32) != "k" * 32
