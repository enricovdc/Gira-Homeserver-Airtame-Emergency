# Airtame Emergency Alert API — wire-protocol reference

Distilled from the official Airtame docs (cited inline) and verified
against a live test webhook during this project's development. The
implementation in `projects/airtame_emergency*/` follows everything
documented here.

## Endpoint and auth

* **Method:** `POST`
* **Base URL:** `https://airtame.cloud/api/v3.0/cloud/public/emergency-alerts`
* **Per-integration URL:** Airtame Cloud generates a unique webhook URL
  per integration, of the form
  `https://airtame.cloud/api/v3.0/cloud/public/emergency-alerts/webhooks/<token>`.
  Use the full URL from your integration's settings page; the base form
  alone does not route to a specific organization.
* **Auth:** HTTP Basic. Username can be any string (the module uses
  `gira`); password must be the API key Airtame Cloud generates when
  you create the integration.
* **Target groups:** chosen when the integration is created in Airtame
  Cloud, NOT in the payload. The webhook URL itself encodes which
  screens / device groups will receive the alert.

## Option 2 — Airtame JSON (recommended)

`Content-Type: application/json`. Schema per the official guidelines:

```
{
  "id":          string,                  // unique; same id resolves the alert
  "status":      "Initiated" | "Resolved",
  "template":    AlertTemplate,           // see below; defaults to "high"
  "headline":    string,                  // title on screen
  "description": string?,                 // optional - body text
  "isDrill":     boolean?,                // optional - shows Drill badge
  "expiresAt":   string?                  // optional - ISO 8601 w/ timezone
}
```

`AlertTemplate` enum:

```
"high" | "medium" | "low" |
"blank" | "all-clear" | "hold" |
"secure" | "lockdown" | "evacuate" | "shelter"
```

**SRP templates** (the last seven) override the headline with a
protocol-defined title — only the description remains user-settable.

### Initiate

```
POST https://airtame.cloud/api/v3.0/cloud/public/emergency-alerts/webhooks/<token>
Authorization: Basic base64("gira:<api-key>")
Content-Type:  application/json

{
  "id": "gira-hs-20260518T080000Z-42",
  "status": "Initiated",
  "template": "high",
  "headline": "Lockdown in effect",
  "description": "Please remain indoors and secure all entries.",
  "isDrill": false,
  "expiresAt": "2026-05-18T08:10:00+00:00"
}
```

### Resolve

```
POST https://airtame.cloud/api/v3.0/cloud/public/emergency-alerts/webhooks/<token>
Authorization: Basic base64("gira:<api-key>")
Content-Type:  application/json

{ "id": "gira-hs-20260518T080000Z-42", "status": "Resolved" }
```

The `id` of a Resolve must match the `id` of the matching Initiate.

## Option 1 — CAP 1.2 XML

`Content-Type: application/xml`. Airtame strictly validates against
the CAP 1.2 XSD and returns HTTP 400 for any deviation. Element order
inside `<info>` is fixed:

```
category → event → urgency → severity → certainty
       → expires? → senderName? → headline? → description?
       → instruction? → area?
```

Airtame's published sample also emits empty `<instruction/>` and an
`<area>` skeleton; this module mirrors that for maximum
schema-compatibility.

### Template selection in CAP

CAP routes template selection through **`<urgency>`** (not `<severity>`).
The mapping this module uses:

| `template` input | CAP `<urgency>` | Airtame chooses |
| --- | --- | --- |
| `high`, `lockdown`, `evacuate`, `shelter`, `secure` | `Immediate` | high |
| `medium`, `hold` | `Expected` | medium |
| `low`, `all-clear`, `blank` | `Future` | low |

CAP cannot select an SRP template directly — those are JSON-only. If
the operator picks `lockdown` and `payload_format=cap`, the module
degrades gracefully to urgency `Immediate` (Airtame's "high"
template).

### Initiate (CAP)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>gira-hs-20260518T080000Z-42</identifier>
  <sender>gira-homeserver</sender>
  <sent>2026-05-18T08:00:00+00:00</sent>
  <status>Actual</status>
  <msgType>Alert</msgType>
  <scope>Public</scope>
  <info>
    <category>Safety</category>
    <event>Lockdown</event>
    <urgency>Immediate</urgency>
    <severity>Severe</severity>
    <certainty>Observed</certainty>
    <expires>2026-05-18T08:10:00+00:00</expires>
    <senderName>gira-homeserver</senderName>
    <headline>Lockdown in effect</headline>
    <description>Please remain indoors and secure all entries.</description>
    <instruction/>
    <area>
      <areaDesc></areaDesc>
      <circle></circle>
    </area>
  </info>
</alert>
```

### Cancel (CAP)

CAP cancels reference the original message via
`<references>sender,identifier,sent</references>` — all three must
match the alert being cancelled. The module persists the original
`<sent>` timestamp in the `ACTIVE_SENT_TS` remanent / store entry so
the reference survives a HomeServer restart.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>gira-hs-cancel-20260518T080500Z-1</identifier>
  <sender>gira-homeserver</sender>
  <sent>2026-05-18T08:05:00+00:00</sent>
  <status>Actual</status>
  <msgType>Cancel</msgType>
  <scope>Public</scope>
  <references>gira-homeserver,gira-hs-20260518T080000Z-42,2026-05-18T08:00:00+00:00</references>
  <info>
    <category>Safety</category>
    <event></event>
    <urgency>Immediate</urgency>
    <severity>Severe</severity>
    <certainty>Observed</certainty>
    <senderName>gira-homeserver</senderName>
    <headline></headline>
    <description></description>
    <instruction/>
    <area>
      <areaDesc></areaDesc>
      <circle></circle>
    </area>
  </info>
</alert>
```

Cancel mirrors the original alert's urgency / severity / certainty per
Airtame's published sample — not the canonical CAP
"Past / Unknown / Unknown" you'd see in pure-CAP setups.

## Response & error handling

* `2xx` — alert accepted.
* `400` — payload validation failed. For CAP this means the XSD
  rejected the message; for JSON it means a required field is missing
  or malformed.
* `401` / `403` — bad / revoked API key.
* `429` — rate-limit. The module backs off exponentially (1, 2, 4 s)
  and retries up to `max_retries` times.
* `5xx` — Airtame internal error. Retry policy as above.
* Network timeouts — retried with the same backoff schedule.

The module exposes the outcome through three outputs:
`LAST_STATUS_CODE` (HTTP code, `0` for transport/timeout/config
errors), `LAST_MESSAGE` (short categorised string), and pulses on
`SUCCESS_PULSE` / `ERROR_PULSE`.

## Notable behaviour

* **No `id` retention required:** Airtame keys alerts by the `id`
  field. Sending a Resolve with an id that was never seen is silently
  accepted (no error). This means the module's edge-state remanent
  variables are the source of truth for "what id is currently active".
* **Drill flag in CAP has no badge:** because CAP lacks an `isDrill`
  field, drill alerts sent as CAP display the same UI as real alerts.
  Drill differentiation in CAP is reflected only in
  `<severity>Minor</severity>` for telemetry purposes.
* **Idempotency:** repeatedly POSTing the same payload (same `id`,
  same `status`) does not duplicate; Airtame deduplicates server-side.

## Sources

- [Emergency alerts integrations — payload guidelines](https://help.airtame.com/hc/en-us/articles/28499448688029-Emergency-alerts-integrations-payload-guidelines)
- [How to create integrations for emergency alerts](https://help.airtame.com/hc/en-us/articles/27011752494493-How-to-create-integrations-for-emergency-alerts)
- [Introduction to emergency alerts in Airtame Cloud](https://help.airtame.com/hc/en-us/articles/26089077514781-Introduction-to-emergency-alerts-in-Airtame-Cloud)
- [Common Alerting Protocol v1.2 OASIS standard](https://docs.oasis-open.org/emergency/cap/v1.2/CAP-v1.2-os.html)
