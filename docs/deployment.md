# Deployment

## 1. Get an Airtame API key

1. Log in to Airtame Cloud as an organization admin.
2. Open the Emergency Alerts integration settings.
3. Generate an API key. Copy it somewhere safe — Airtame only shows it once.

## 2. Package the module

The deployable artifact is the contents of `module/`:

```
module/lbs24815.xml                     # descriptor (LBS #24815)
module/lbs24815.hsl                     # entry script
module/lib/util.hsl
module/lib/airtame_payload.hsl
module/lib/airtame_client.hsl
```

Import these files into the Gira Project Assistant / Expert tool as a new
logic module ("Logikbaustein"). The descriptor file is the entry; the `.hsl`
files must be installed alongside it so the `#include` directives resolve.

### About the LBS number

`24815` is the module's globally-unique numeric identifier inside an Experten
project. It is encoded both in the file name (`lbs24815.{xml,hsl}`) and in
the `<logicmodule id="24815">` / `<number>24815</number>` fields of the
descriptor. Experten uses this number to bind module instances back to their
script. To avoid collisions with other third-party modules in the same
project, replace `24815` with a number reserved for you on
[hs-help.net](https://hs-help.net/) before publishing. The replacement is a
single global find/replace in the `module/` and `docs/` trees.

## 3. Configure the module instance

When you drop the module into a logic page in Expert, set the parameters:

* `api_endpoint` — leave at the default unless Airtame instructs otherwise.
* `api_key` — paste the API key from step 1. Stored as a password field; the
  module never writes it to the trace log in plaintext (it masks to
  `ab****yz` instead).
* `alert_id_prefix` — anything that helps you identify Gira-originated alerts
  in Airtame's audit log. The default `gira-hs` is fine.
* `default_headline`, `default_description`, `default_template`,
  `default_is_drill`, `default_duration_seconds` — fallbacks used when the
  matching input pin is empty.
* `timeout_seconds`, `max_retries`, `debounce_ms` — leave at defaults unless
  you have evidence of latency or chattering inputs.

## 4. Wire the inputs

* **Input 1 (`trigger`)** — connect to the KNX object that represents
  "emergency active" (e.g. a manual lockdown button or an upstream alarm
  bus). The module fires only on rising edges, so a button-press group
  address that goes 0→1→0 is fine.
* **Input 2 (`clear`)** — connect to the KNX object that represents
  "emergency cleared" (e.g. a key-switch release).
* Inputs 3–7 are optional. If you want per-scenario headlines/descriptions,
  drive them from string constants or a scene module.

## 5. Wire the outputs

* Output 1 (`active`) — useful for visualizations / dashboards.
* Outputs 2 & 3 (`success_pulse` / `error_pulse`) — drive notification logic
  (push to mobile, alarm log, etc.).
* Outputs 4 & 5 (`last_status_code` / `last_message`) — log to a diagnostics
  page.
* Output 6 (`last_alert_id`) — useful when correlating with Airtame's audit
  log.

## 6. Verify

See the manual verification checklist in `README.md` and the runnable
mock-HTTP tests in `tests/`.

## Notes on the HSL HTTP API

`module/lib/airtame_client.hsl` uses `hsl.net.HTTPClient()`, which is
available on Gira HomeServer 4.x firmware that supports the HSL standard
library. If your firmware predates that and only exposes the older
`system.http_request` helper, change `airtame_send` to use it — the rest of
the module is HTTP-API-agnostic. The wire format and behavior remain
identical and are pinned by the tests in `tests/test_client.py`.
