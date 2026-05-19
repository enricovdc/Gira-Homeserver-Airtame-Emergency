# Airtame Emergency Alert — Pin contract

Source of truth: `projects/airtame_emergency/config.xml` (consumed by
`generator.pyc`) plus the constants block inside
`projects/airtame_emergency/src/24815_AirtameEmergencyAlert.py` between
the `##!!!!##` and `##!!!##` markers.

Pin indices below match what the generator assigns from the order of
elements in `config.xml`.

## Inputs

In HSL2 there is no separate "parameter" concept — every configurable
value is an input. The `init_value` in `config.xml` is what Experte
proposes when the module is placed; the user can leave it as-is or wire
runtime objects to it.

| # | const_name | type | init | Description |
| --- | --- | --- | --- | --- |
| 1  | `TRIGGER`            | NUMBER | `0`     | Rising edge sends an `Initiated` alert. Edge-debounced. |
| 2  | `CLEAR`              | NUMBER | `0`     | Rising edge sends a `Resolved` alert for the active id. |
| 3  | `HEADLINE`           | STRING | `Emergency` | Alert title. Falls back to "Emergency" if empty. |
| 4  | `DESCRIPTION`        | STRING | `Emergency alert from Gira HomeServer.` | Alert body. |
| 5  | `TEMPLATE`           | STRING | `high`  | Airtame visual template. One of `high`, `medium`, `low`. |
| 6  | `IS_DRILL`           | NUMBER | `0`     | Non-zero marks the alert as a drill (Drill badge on screens). |
| 7  | `DURATION_SECONDS`   | NUMBER | `300`   | Used to compute `expiresAt` (now + duration). |
| 8  | `API_ENDPOINT`       | STRING | `https://airtame.cloud/api/v3.0/cloud/public/emergency-alerts` | Must start with `https://`. |
| 9  | `API_KEY`            | STRING | `""`    | Airtame Cloud API key (Basic-auth password). |
| 10 | `ALERT_ID_PREFIX`    | STRING | `gira-hs` | Used to build unique alert ids: `<prefix>-<UTC stamp>-<counter>`. |
| 11 | `TIMEOUT_SECONDS`    | NUMBER | `10`    | Per-request HTTP timeout. |
| 12 | `MAX_RETRIES`        | NUMBER | `2`     | Retries on `429`, `5xx`, and timeouts (exp backoff). |
| 13 | `DEBOUNCE_MS`        | NUMBER | `1000`  | Minimum interval between accepted rising edges. |
| 17 | `PROBE_NOW`          | NUMBER | `0`     | Rising edge sends a safe probe (Resolved with throwaway id). Does not initiate any alert on screens. JSON only. |

## Outputs

| # | const_name | type | init | Semantics |
| --- | --- | --- | --- | --- |
| 1 | `ACTIVE`           | NUMBER | `0`  | `1` while the most recent `Initiated` alert has not been resolved (restored from remanent on `on_init`). |
| 2 | `SUCCESS_PULSE`    | NUMBER | `0`  | Pulses `1` then `0` after each 2xx response. |
| 3 | `ERROR_PULSE`      | NUMBER | `0`  | Pulses `1` then `0` on validation failure or non-2xx response. |
| 4 | `LAST_STATUS_CODE` | NUMBER | `0`  | HTTP status of the last request. `0` for transport errors / timeouts / config errors. |
| 5 | `LAST_MESSAGE`     | STRING | `""` | Short result string. Examples: `alert initiated`, `alert resolved`, `validation: …`, `HTTP <n> (auth\|rate-limit\|timeout\|server\|transport)`, `config: …`. |
| 6 | `LAST_ALERT_ID`    | STRING | `""` | ID of the most recent `Initiated` alert (kept after Resolve for diagnostics). |
| 7 | `LIVENESS`         | NUMBER | `0`  | `1` if the most recent probe got a 2xx response, else `0`. Persists across HS restart. |
| 8 | `LAST_PROBE_STATUS_CODE` | NUMBER | `0` | HTTP status of the last probe (`0` for transport error / timeout). |

## Remanent variables

Persisted across HS restart. Not exposed to Experte logic pages.

| # | const_name | type | Purpose |
| --- | --- | --- | --- |
| 1 | `ACTIVE`           | NUMBER | Mirrors output 1 across restarts. |
| 2 | `ACTIVE_ALERT_ID`  | STRING | The id used to clear an alert that survived a restart. |
| 3 | `COUNTER`          | NUMBER | Monotonic suffix for alert ids. |
| 4 | `LAST_TRIG_VAL`    | NUMBER | Previous `TRIGGER` value for edge detect. |
| 5 | `LAST_TRIG_TS_MS`  | NUMBER | Timestamp of the last accepted trigger edge for debounce. |
| 6 | `LAST_CLR_VAL`     | NUMBER | Previous `CLEAR` value for edge detect. |
| 7 | `LAST_CLR_TS_MS`   | NUMBER | Timestamp of the last accepted clear edge. |

## Edge / debounce semantics

* `TRIGGER` and `CLEAR` are rising-edge triggered. A value held high will
  not refire until it goes low and rises again **and** at least
  `DEBOUNCE_MS` has passed since the last accepted edge on that pin.
* The very first rising edge after a fresh install (when the timestamp
  remanent is `0`) is always accepted.

## Validation

Before any HTTP call, `_validate` enforces:

* `alert_id` non-empty (always set internally)
* `headline` non-empty, ≤ 200 chars
* `description` non-empty, ≤ 2000 chars
* `template` ∈ {`high`, `medium`, `low`}
* `duration_seconds` > 0

Plus, in `_send`:

* `endpoint` starts with `https://`
* `api_key` non-empty

A failure sets `LAST_STATUS_CODE` = `0`, `LAST_MESSAGE` = `validation: …`
or `config: …`, pulses `ERROR_PULSE`. No HTTP request is made.

## Wire protocol

POST to `API_ENDPOINT` with:

```
Authorization: Basic base64("gira:<API_KEY>")
Content-Type:  application/json
Accept:        application/json
```

### Initiate

```json
{
  "id": "gira-hs-20260518T080000Z-42",
  "status": "Initiated",
  "template": "high",
  "headline": "Lockdown",
  "description": "Shelter in place.",
  "isDrill": false,
  "expiresAt": "2026-05-18T08:10:00+00:00"
}
```

### Resolve

```json
{ "id": "gira-hs-20260518T080000Z-42", "status": "Resolved" }
```

The id of a Resolve always matches the id of the matching Initiate; the
module tracks this via the `ACTIVE_ALERT_ID` remanent variable.
