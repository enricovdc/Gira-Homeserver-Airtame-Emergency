# Gira HomeServer ↔ Airtame Emergency Alert

A Gira HomeServer 4 logic module that triggers and clears
[Airtame Emergency Alerts](https://help.airtame.com/hc/en-us/articles/28499448688029-Emergency-alerts-integrations-payload-guidelines)
from KNX / Gira events.

**LBS number:** `24815` (third-party / community range `20000-99999`). This
is an arbitrary placeholder. If you plan to distribute this module publicly,
reserve a number on the community wiki at
[hs-help.net](https://hs-help.net/) under "LBS-Nummern Vergabe" and update
`LBS_NUMBER` in `gen/generate_lbs24815.py`.

## Layout

```
gen/generate_lbs24815.py    Single source of truth - feed into Gira Experte 4.13's
                            HSL generator. Top-of-file constants declare the
                            LBS number, parameters, inputs, outputs; HSL_BODY
                            holds the function bodies. Running this file
                            directly emits a fallback .hsl into dist/.

dist/                       Generated artefacts (gitignored). Either Gira's
                            generator output or the fallback emitted by
                            gen/generate_lbs24815.py.

reference/                  Python port of the HSL logic - executable spec
                            the test suite pins behavior against.

tests/                      pytest suite (31 tests).
docs/                       Pin contract and deployment notes.
examples/                   curl scripts for manual smoke tests against
                            the real Airtame endpoint.
```

### Why a Python source-of-truth?

Gira logic modules are deployed as a single `.hsl` file with a structured
metadata header that the Gira Experte 4.13 software's bundled HSL generator
produces. Hand-rolling that header risks subtle parser mismatches between
Experte versions, so we keep the **inputs** to the generator
(`gen/generate_lbs24815.py`) in this repo and let Experte produce the
canonical `.hsl`.

The `reference/` Python package is a separate concern: it's a line-for-line
port of the HSL function bodies in `HSL_BODY` so we can unit-test the wire
protocol, validation rules, and state machine without a running HomeServer.

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
  `last_message`, `last_alert_id` as outputs.

See `docs/inputs_outputs.md` for the full pin contract and
`docs/deployment.md` for installation steps.

## Generating the .hsl

### Preferred: through Gira Experte 4.13

1. Locate the HSL generator script bundled with Experte 4.13 (typically a
   `.py` file under the Experte install directory).
2. Feed `gen/generate_lbs24815.py` to it. The module metadata constants
   (`LBS_NUMBER`, `LBS_NAME`, `PARAMETERS`, `INPUTS`, `OUTPUTS`, `HSL_BODY`)
   are laid out so the generator can consume them.
3. If the generator expects a different schema, rename the top-level
   constants in `gen/generate_lbs24815.py` to match - the values stay the same.
4. The generator writes a canonical `dist/lbs24815.hsl` that Experte can
   import as a logic module.

### Fallback: run the source file directly

```
python3 gen/generate_lbs24815.py
# writes dist/lbs24815.hsl with a best-effort header.
```

Use this only when the Gira generator is unavailable. Prefer Gira's output
in production.

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

When you change `HSL_BODY` in `gen/generate_lbs24815.py`, update the
matching function in `reference/` and re-run tests.

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

* The API key is declared as a `password` parameter, so Experte stores it in
  the HS password store rather than as plaintext in the project file.
* `mask_secret()` (in `HSL_BODY`) is called before any trace log line that
  mentions the key. `tests/test_client.py::test_mask_secret_*` pins this
  behavior.
* The body refuses to send when the endpoint isn't `https://` or the key is
  empty - both surface as an `error_pulse` with `last_message` starting with
  `config: …`.
* `.gitignore` blocks `dist/`, `.env`, `secrets.local.*`, and built `.hslz`
  archives from being committed.

## Limitations / out of scope

* Only the Emergency Alerts endpoint is implemented. Device management,
  fleet config, screen layout, etc. are not handled here.
* `HSL_BODY` uses `hsl.net.HTTPClient` for HTTPS. If your Experte 4.13 /
  HomeServer firmware exposes a different HTTP helper, edit only the
  `airtame_send` function in `HSL_BODY` - the rest of the module is
  HTTP-API-agnostic and the wire format is locked by `tests/test_client.py`.
