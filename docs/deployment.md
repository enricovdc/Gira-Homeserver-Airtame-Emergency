# Deployment

## 1. Get an Airtame API key

1. Log in to Airtame Cloud as an organization admin.
2. Open the Emergency Alerts integration settings.
3. Generate an API key. Copy it somewhere safe — Airtame only shows it once.

## 2. Generate the .hsl

The deployable artifact is a single `.hsl` file produced from
`gen/generate_lbs24815.py`. Two ways to produce it:

### Preferred: Gira Experte 4.13's bundled generator

1. Find the HSL generator script bundled with your Experte 4.13 install
   (a `.py` file under the install directory).
2. Run it against `gen/generate_lbs24815.py`. The top-of-file constants
   (`LBS_NUMBER = 24815`, `LBS_NAME`, `PARAMETERS`, `INPUTS`, `OUTPUTS`,
   `HSL_BODY`) describe everything the generator needs.
3. If the generator expects different constant names (e.g. lowercase, or
   wrapped in a `define_module(...)` call), rename the top-level constants
   in `gen/generate_lbs24815.py` to match. Don't change the values.
4. The generator emits a canonical `lbs24815.hsl` containing the LBS
   metadata header followed by `HSL_BODY`.

### Fallback: run the source file directly

```
python3 gen/generate_lbs24815.py
# writes dist/lbs24815.hsl
```

This uses a best-effort header dialect. Use it only if you can't run the
Gira generator. The body code is identical either way.

## 3. Import into Experte

1. Open your Experte 4.13 project.
2. Import the generated `lbs24815.hsl` as a new logic module
   ("Logikbaustein").
3. Drop the module onto a logic page.

### About the LBS number

`24815` is the module's globally-unique numeric identifier inside an Experte
project. To avoid collisions with other third-party modules in the same
project, replace it with a number reserved for you on
[hs-help.net](https://hs-help.net/) before publishing. Single global
find/replace in the repo: `LBS_NUMBER = 24815` → your number, and rename
output files accordingly. Tests don't need to change.

## 4. Configure the module instance

Set the parameters in Experte:

* `api_endpoint` — leave at default unless Airtame instructs otherwise.
* `api_key` — paste the API key from step 1. The descriptor declares this
  as `password` so Experte stores it in the HS password store; the body
  masks it (`ab****yz`) in trace logs.
* `alert_id_prefix` — anything that helps you identify Gira-originated
  alerts in Airtame's audit log. Default `gira-hs` is fine.
* `default_headline`, `default_description`, `default_template`,
  `default_is_drill`, `default_duration_seconds` — fallbacks used when the
  matching input pin is empty.
* `timeout_seconds`, `max_retries`, `debounce_ms` — leave at defaults
  unless you have evidence of latency or chattering inputs.

## 5. Wire the inputs

* **Input 1 (`trigger`)** — connect to the KNX object that represents
  "emergency active" (e.g. a manual lockdown button or an upstream alarm
  bus). Fires only on rising edges.
* **Input 2 (`clear`)** — connect to the KNX object that represents
  "emergency cleared" (e.g. a key-switch release).
* Inputs 3–7 are optional. Drive them from string constants or scenes
  if you want per-scenario headlines / descriptions / drill flags.

## 6. Wire the outputs

* Output 1 (`active`) — useful for visualizations / dashboards.
* Outputs 2 & 3 (`success_pulse` / `error_pulse`) — drive notification
  logic (push to mobile, alarm log, etc.).
* Outputs 4 & 5 (`last_status_code` / `last_message`) — log to a
  diagnostics page.
* Output 6 (`last_alert_id`) — useful when correlating with Airtame's
  audit log.

## 7. Verify

See the manual verification checklist in `README.md` and the
mocked-HTTP tests in `tests/`.

## Notes on the HSL HTTP API

`HSL_BODY` uses `hsl.net.HTTPClient()`, which is available on Gira
HomeServer 4.x firmware that supports the HSL standard library. If your
firmware exposes a different HTTP helper (older `system.http_request`,
etc.), change only the `airtame_send` function in `HSL_BODY`. The wire
format and behavior are pinned by `tests/test_client.py` and won't change.
