"""HTTP client for the Airtame Emergency Alerts API.

Mirrors module/lib/airtame_client.hsl. Keeps transport, auth, retry, and
credential masking in one place so the Gira-side wiring stays thin.
"""
from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional

from .airtame_payload import DEFAULT_ENDPOINT


class AirtameError(Exception):
    """Base class for Airtame client failures."""


class AirtameAuthError(AirtameError):
    """401/403 from Airtame."""


class AirtameRateLimitError(AirtameError):
    """429 from Airtame."""


class AirtameServerError(AirtameError):
    """5xx from Airtame."""


class AirtameTimeoutError(AirtameError):
    """Network timeout."""


@dataclass
class AirtameResponse:
    status_code: int
    body: str

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300


# Pluggable transport so tests can inject a fake without monkey-patching urllib.
Transport = Callable[[str, str, dict, bytes, float], AirtameResponse]


def _default_transport(
    method: str, url: str, headers: dict, body: bytes, timeout: float
) -> AirtameResponse:
    req = urllib.request.Request(url=url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return AirtameResponse(resp.status, resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return AirtameResponse(e.code, e.read().decode("utf-8", "replace"))
    except urllib.error.URLError as e:
        if isinstance(e.reason, TimeoutError) or "timed out" in str(e.reason).lower():
            raise AirtameTimeoutError(str(e.reason)) from e
        raise AirtameError(str(e.reason)) from e


def mask_secret(value: str) -> str:
    """Mask an API key for logging. Keep length signal but no plaintext."""
    if not value:
        return ""
    if len(value) <= 4:
        return "*" * len(value)
    return value[:2] + "*" * (len(value) - 4) + value[-2:]


def _basic_auth_header(api_key: str, username: str = "gira") -> str:
    raw = f"{username}:{api_key}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


@dataclass
class AirtameClient:
    api_key: str
    endpoint: str = DEFAULT_ENDPOINT
    timeout_seconds: float = 10.0
    max_retries: int = 2
    retry_backoff_seconds: float = 1.0
    transport: Transport = _default_transport
    sleep: Callable[[float], None] = time.sleep

    def __post_init__(self) -> None:
        if not self.api_key:
            raise AirtameAuthError("api_key is required")
        if not self.endpoint.startswith("https://"):
            raise AirtameError("endpoint must use HTTPS")

    def send(self, payload: dict) -> AirtameResponse:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers = {
            "Authorization": _basic_auth_header(self.api_key),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        attempt = 0
        last_exc: Optional[BaseException] = None
        while attempt <= self.max_retries:
            try:
                resp = self.transport(
                    "POST", self.endpoint, headers, body, self.timeout_seconds
                )
            except AirtameTimeoutError as e:
                last_exc = e
                attempt += 1
                if attempt > self.max_retries:
                    raise
                self.sleep(self.retry_backoff_seconds * (2 ** (attempt - 1)))
                continue

            if resp.status_code in (401, 403):
                raise AirtameAuthError(f"HTTP {resp.status_code}: {resp.body}")
            if resp.status_code == 429:
                attempt += 1
                if attempt > self.max_retries:
                    raise AirtameRateLimitError(f"HTTP 429: {resp.body}")
                self.sleep(self.retry_backoff_seconds * (2 ** (attempt - 1)))
                continue
            if 500 <= resp.status_code < 600:
                attempt += 1
                if attempt > self.max_retries:
                    raise AirtameServerError(
                        f"HTTP {resp.status_code}: {resp.body}"
                    )
                self.sleep(self.retry_backoff_seconds * (2 ** (attempt - 1)))
                continue
            return resp

        # Unreachable: retry loop always returns or raises.
        assert last_exc is not None
        raise last_exc  # pragma: no cover
