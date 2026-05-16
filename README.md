# Gira HomeServer ↔ Airtame Emergency Alert

A Gira HomeServer 4 logic module that triggers and clears
[Airtame Emergency Alerts](https://help.airtame.com/hc/en-us/articles/28499448688029-Emergency-alerts-integrations-payload-guidelines)
from KNX / Gira events.

**LBS number:** `24815` (third-party / community range `20000-99999`).
This is an arbitrary placeholder chosen from the unreserved range. If you plan
to distribute this module publicly, reserve a number on the community wiki at
[hs-help.net](https://hs-help.net/) under "LBS-Nummern Vergabe" and then
rename `module/lbs24815.{xml,hsl}` and update the `id`/`number` fields inside
the descriptor.

## Layout

```
module/                  Files deployed to the HomeServer (the actual logic module)
  lbs24815.xml                  Descriptor: parameters, inputs, outputs (LBS #24815)
  lbs24815.hsl                  Entry script
  lib/util.hsl                  JSON escape, base64, ISO 8601, debounce
  lib/airtame_payload.hsl       Payload builder + validation
  lib/airtame_client.hsl        HTTPS POST + retries + secret masking

reference/               Python reference implementation (executable spec)
  airtame_payload.py            Mirrors lib/airtame_payload.hsl
  airtame_client.py             Mirrors lib/airtame_client.hsl
  debounce.py                   Mirrors edge_rising() in lib/util.hsl
  module.py                     Mirrors lbs24815.hsl

tests/                   pytest suite running against the Python reference
docs/                    inputs/outputs and deployment notes
examples/                curl scripts for manual smoke tests
```

### Why a Python reference?

HSL only runs on a Gira HomeServer, so its behavior cannot be unit-tested
in CI directly. The `reference/` package is a line-for-line port of the
HSL code into Python and serves as the executable spec the test suite
pins. When the HSL and Python disagree, the HSL is wrong — change it to
match the tests.

## What it does

* On a debounced rising edge of input `trigger`, POSTs an `Initiated`
  alert to the Airtame Emergency Alerts endpoint.
* On a debounced rising edge of input `clear`, POSTs a `Resolved` payload
  with the same `id` to stop the active alert.
* Authenticates via HTTP Basic with the configured API key.
* Retries on `429` / `5xx` / timeouts with exponential backoff.
* Validates required fields before any HTTP call.
* Masks the API key in trace logs.
* Exposes `active`, `success_pulse`, `error_pulse`, `last_status_code`,
  `last_message`, and `last_alert_id` as outputs.

See `docs/inputs_outputs.md` for the full pin contract and
`docs/deployment.md` for installation steps.

## Running tests

```
pip install -r requirements.txt
pytest -q
```

The suite covers:

* Payload shape for `Initiated` and `Resolved` (`tests/test_payload.py`)
* Validation: missing id / headline / description / bad template / bad duration
* HTTP success / 401 / 403 / 429 with retry / 5xx with retry / timeout with retry
* Basic-auth header construction; rejection of non-HTTPS endpoints
* Secret masking for logs
* Rising-edge detection and debounce window (`tests/test_debounce.py`)
* End-to-end module behavior: trigger fires once on held-high input,
  clear sends Resolve with the matching id, validation surfaces to outputs,
  auth/timeout errors surface to outputs (`tests/test_module.py`)

## Manual verification checklist

Once installed on a Gira HomeServer:

1. Configure parameters (`api_endpoint`, `api_key`, defaults).
2. Wire input 1 to a test KNX object you can toggle from the Gira app.
3. Toggle input 1 from 0 → 1 → 0.
   * Expect `success_pulse` to fire once, `active` = 1, `last_status_code` = 2xx,
     `last_alert_id` populated.
   * Expect the alert to appear on Airtame screens.
4. Hold input 1 high for several seconds.
   * Expect **no** second request (held-high does not refire).
5. Toggle input 2 (`clear`) from 0 → 1 → 0.
   * Expect `success_pulse` to fire once, `active` = 0, alert disappears
     from Airtame screens.
6. Set `api_key` to an obviously invalid string and trigger again.
   * Expect `error_pulse` = 1, `last_status_code` = 401,
     `last_message` starts with `HTTP 401 (auth)`.
   * Expect the trace log to show the masked key (`ab****yz`), not the
     plaintext key.
7. (Optional) Use `examples/curl_initiate.sh` to confirm your API key
   independently of the HomeServer.

## Security notes

* The API key is declared `type="password"` in the descriptor; the HS
  password store should keep it out of plaintext exports.
* `module/lib/util.hsl` `mask_secret()` is called before any trace log
  line that mentions the key. `tests/test_client.py::test_mask_secret_*`
  pins this behavior.
* `module/lib/airtame_client.hsl` and the Python reference both reject
  non-HTTPS endpoints in `__post_init__` / a guard at the top of the
  entry script.
* `.gitignore` blocks `.env`, `secrets.local.*`, and built `.hslz`
  archives from being committed.

## Limitations / out of scope

* Only the Emergency Alerts endpoint is implemented. Device management,
  fleet config, screen layout, etc. are not handled here.
* The HSL HTTP layer assumes `hsl.net.HTTPClient` is available (Gira HS
  4.x). Older firmwares need the small change documented at the bottom
  of `docs/deployment.md`.
