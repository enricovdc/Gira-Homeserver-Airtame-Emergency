# Airtame Emergency Alert — Inputs, Outputs, Parameters

This document is the contract between the Gira HomeServer project that
embeds this module and the module itself. Indexes match the pin numbers
declared in `module/airtame_emergency_alert.xml`.

## Parameters (configured once, at module insert time)

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `api_endpoint` | string (URL) | `https://airtame.cloud/api/v3.0/cloud/public/emergency-alerts` | Airtame endpoint. Must be HTTPS. |
| `api_key` | password | _required_ | Airtame Cloud API key. Sent as HTTP Basic auth password. Never logged in plaintext. |
| `alert_id_prefix` | string | `gira-hs` | Prefix used to construct unique alert ids: `<prefix>-<UTC timestamp>-<counter>`. |
| `default_headline` | string | `Emergency` | Used when input 3 is empty. |
| `default_description` | string | `Emergency alert triggered from Gira HomeServer.` | Used when input 4 is empty. |
| `default_template` | enum (`high` \| `medium` \| `low`) | `high` | Airtame visual template. |
| `default_is_drill` | bool | `false` | Marks alerts as drills (Airtame shows a Drill badge). |
| `default_duration_seconds` | int (10–86400) | `300` | Used to compute `expiresAt` when input 7 is unset. |
| `timeout_seconds` | int (1–60) | `10` | HTTP request timeout. |
| `max_retries` | int (0–5) | `2` | Retries on 429, 5xx, and timeouts (exponential backoff). |
| `debounce_ms` | int (0–60000) | `1000` | Minimum interval between accepted rising edges per input. |

## Inputs

| # | Name | Type | Required | Notes |
| --- | --- | --- | --- | --- |
| 1 | `trigger` | bool | yes | Rising edge sends an `Initiated` alert. Held-high does not refire. |
| 2 | `clear` | bool | yes | Rising edge sends a `Resolved` payload for the currently-active alert. No-op if none. |
| 3 | `headline` | string | no | Overrides `default_headline` if non-empty. |
| 4 | `description` | string | no | Overrides `default_description` if non-empty. |
| 5 | `template` | string | no | Overrides `default_template` if one of `high\|medium\|low`. |
| 6 | `is_drill` | bool | no | Overrides `default_is_drill`. |
| 7 | `duration_seconds` | int | no | Overrides `default_duration_seconds` when > 0. |

## Outputs

| # | Name | Type | Semantics |
| --- | --- | --- | --- |
| 1 | `active` | bool | True while the most recent `Initiated` alert has not been `Resolved`. |
| 2 | `success_pulse` | bool | Pulses high for one execution cycle after each 2xx response. |
| 3 | `error_pulse` | bool | Pulses high for one execution cycle on validation failure or non-2xx. |
| 4 | `last_status_code` | int | HTTP status of the last request. `0` for transport errors / timeouts. |
| 5 | `last_message` | string | Short human-readable result. Categories: `alert initiated`, `alert resolved`, `validation: …`, `HTTP <n> (auth\|rate-limit\|timeout\|server\|transport)`. |
| 6 | `last_alert_id` | string | ID assigned to the most recent `Initiated` alert (kept after Resolve for diagnostics). |

## Edge / debounce semantics

* Inputs 1 and 2 are rising-edge triggered. A trigger that stays high will
  not refire until it falls and rises again **and** at least `debounce_ms`
  has passed since the last accepted rising edge.
* `trigger` and `clear` share independent debouncers. Both can rise in the
  same cycle, but `trigger` is processed first; `clear` in the same cycle
  will resolve the alert that was just initiated.

## Validation

Before any HTTP call, the module validates:

* `alert_id` non-empty (always set internally)
* `headline` non-empty, ≤ 200 chars
* `description` non-empty, ≤ 2000 chars
* `template` ∈ {`high`, `medium`, `low`}
* `duration_seconds` > 0
* `api_endpoint` starts with `https://`
* `api_key` non-empty

A validation failure sets `error_pulse=1`, `last_status_code=0`, and
`last_message="validation: <reason>"`. No HTTP request is made.

## Wire protocol

POST to `api_endpoint` with:

```
Authorization: Basic base64("gira:<api_key>")
Content-Type:  application/json
Accept:        application/json
```

### Initiate

```json
{
  "id": "gira-hs-20260512T080000Z-42",
  "status": "Initiated",
  "template": "high",
  "headline": "Lockdown",
  "description": "Shelter in place.",
  "isDrill": false,
  "expiresAt": "2026-05-12T08:10:00+00:00"
}
```

### Resolve

```json
{ "id": "gira-hs-20260512T080000Z-42", "status": "Resolved" }
```

The `id` of a Resolve must match the `id` of the original Initiate.
The module tracks this automatically.
