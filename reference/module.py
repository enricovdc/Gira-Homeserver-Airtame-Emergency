"""End-to-end wiring of inputs -> Airtame client, mirrors HSL_BODY in gen/generate_lbs24815.py."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .airtame_client import (
    AirtameAuthError,
    AirtameClient,
    AirtameError,
    AirtameRateLimitError,
    AirtameServerError,
    AirtameTimeoutError,
)
from .airtame_payload import (
    AlertConfig,
    PayloadValidationError,
    build_clear_payload,
    build_trigger_payload,
)
from .debounce import EdgeDebouncer


@dataclass
class ModuleParameters:
    api_key: str
    endpoint: str
    alert_id_prefix: str = "gira-hs"
    default_headline: str = "Emergency"
    default_description: str = "Emergency alert triggered from Gira HomeServer."
    default_template: str = "high"
    default_is_drill: bool = False
    default_duration_seconds: int = 300
    timeout_seconds: float = 10.0
    max_retries: int = 2
    debounce_seconds: float = 1.0


@dataclass
class ModuleOutputs:
    active: bool = False
    success_pulse: bool = False
    error_pulse: bool = False
    last_status_code: int = 0
    last_message: str = ""
    last_alert_id: str = ""


@dataclass
class ModuleInputs:
    trigger: bool = False
    clear: bool = False
    headline: Optional[str] = None
    description: Optional[str] = None
    template: Optional[str] = None
    is_drill: Optional[bool] = None
    duration_seconds: Optional[int] = None


@dataclass
class AirtameEmergencyAlertModule:
    """Stateful logic module: feed it inputs, read outputs."""
    params: ModuleParameters
    client: AirtameClient
    outputs: ModuleOutputs = field(default_factory=ModuleOutputs)
    _trigger_edge: EdgeDebouncer = field(init=False)
    _clear_edge: EdgeDebouncer = field(init=False)
    _alert_counter: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self._trigger_edge = EdgeDebouncer(self.params.debounce_seconds)
        self._clear_edge = EdgeDebouncer(self.params.debounce_seconds)

    def _next_alert_id(self) -> str:
        self._alert_counter += 1
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"{self.params.alert_id_prefix}-{stamp}-{self._alert_counter}"

    def _resolve_config(self, inputs: ModuleInputs, alert_id: str) -> AlertConfig:
        return AlertConfig(
            alert_id=alert_id,
            headline=inputs.headline or self.params.default_headline,
            description=inputs.description or self.params.default_description,
            template=inputs.template or self.params.default_template,
            is_drill=self.params.default_is_drill
            if inputs.is_drill is None
            else inputs.is_drill,
            duration_seconds=inputs.duration_seconds
            or self.params.default_duration_seconds,
        )

    def process(self, inputs: ModuleInputs) -> ModuleOutputs:
        self.outputs.success_pulse = False
        self.outputs.error_pulse = False

        trigger_edge = self._trigger_edge.update(inputs.trigger)
        clear_edge = self._clear_edge.update(inputs.clear)

        if trigger_edge:
            self._handle_trigger(inputs)
        elif clear_edge and self.outputs.active and self.outputs.last_alert_id:
            self._handle_clear(self.outputs.last_alert_id)

        return self.outputs

    def _handle_trigger(self, inputs: ModuleInputs) -> None:
        alert_id = self._next_alert_id()
        try:
            cfg = self._resolve_config(inputs, alert_id)
            payload = build_trigger_payload(cfg)
            resp = self.client.send(payload)
        except PayloadValidationError as e:
            self._fail(0, f"validation: {e}")
            return
        except AirtameAuthError as e:
            self._fail(401, f"auth: {e}")
            return
        except AirtameRateLimitError as e:
            self._fail(429, f"rate-limit: {e}")
            return
        except AirtameTimeoutError as e:
            self._fail(0, f"timeout: {e}")
            return
        except AirtameServerError as e:
            self._fail(500, f"server: {e}")
            return
        except AirtameError as e:
            self._fail(0, f"transport: {e}")
            return

        self.outputs.last_status_code = resp.status_code
        if resp.ok:
            self.outputs.active = True
            self.outputs.last_alert_id = alert_id
            self.outputs.last_message = "alert initiated"
            self.outputs.success_pulse = True
        else:
            self.outputs.error_pulse = True
            self.outputs.last_message = f"HTTP {resp.status_code}: {resp.body[:200]}"

    def _handle_clear(self, alert_id: str) -> None:
        try:
            payload = build_clear_payload(alert_id)
            resp = self.client.send(payload)
        except AirtameError as e:
            self._fail(0, f"clear: {e}")
            return

        self.outputs.last_status_code = resp.status_code
        if resp.ok:
            self.outputs.active = False
            self.outputs.last_message = "alert resolved"
            self.outputs.success_pulse = True
        else:
            self.outputs.error_pulse = True
            self.outputs.last_message = f"HTTP {resp.status_code}: {resp.body[:200]}"

    def _fail(self, status_code: int, message: str) -> None:
        self.outputs.last_status_code = status_code
        self.outputs.last_message = message
        self.outputs.error_pulse = True
