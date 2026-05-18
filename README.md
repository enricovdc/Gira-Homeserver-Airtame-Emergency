# Gira HomeServer ↔ Airtame Emergency Alert

A Gira HomeServer logic module that triggers and clears
[Airtame Emergency Alerts](https://help.airtame.com/hc/en-us/articles/28499448688029-Emergency-alerts-integrations-payload-guidelines)
from KNX / Gira events.

Two parallel implementations are shipped, one per SDK generation:

* **HSL2 SDK 2.0.7** (`hsl20_4` framework, Python 2.7, `.py` subclass of
  `hsl20_4.BaseModule`, XML config). Pick this if your HS firmware runs
  the HSL2 framework.
* **HSL3 SDK 3.0** (Python 3.9, plain `LogicModule` class with a
  framework object injected into `__init__`, JSON config). Pick this if
  your HS firmware supports HSL3. Uses `requests` and explicit
  `threading.Thread` for HTTP, which is the canonical HSL3 pattern.

Both implementations produce identical Airtame wire payloads; the
algorithmic behavior is the same.

**LBS number:** `24815` (community third-party range `20000-99999`).
Placeholder — if publishing, reserve one on
[hs-help.net](https://hs-help.net/) under "LBS-Nummern Vergabe" and
update the id in `config.xml`/`config_*.json`, the file names, and the
class name `AirtameEmergencyAlert24815`.

## Layout

```
projects/airtame_emergency/                     -- HSL2 project (SDK 2.0.7)
  config.xml                                       inputs / outputs / remanent vars / translations
  src/24815_AirtameEmergencyAlert.py               class AirtameEmergencyAlert24815(hsl20_4.BaseModule)
  release/                                         generator.pyc output (.hsl, gitignored)
  debug/                                           generator.pyc output (.py for simulator, gitignored)

projects/airtame_emergency_hsl3/                -- HSL3 project (SDK 3.0)
  config_airtame_emergency.json                    JSON config (inputs/outputs/stores/timers/scripts)
  hsl3_24815_airtame_emergency.py                  class LogicModule (no inheritance, framework injected)

tests/                                          pytest suite (Python 3) covering both
  conftest.py                                      injects hsl20_4 + hsl3 stubs, loads both source files
  _hsl20_4_stub.py     _hsl3_stub.py               stand-ins matching the SDK Doxygen surface
  test_payload.py  test_client.py  test_debounce.py  test_module.py   -- HSL2
  test_hsl3_module.py                                                  -- HSL3

docs/                                           Pin contract and deployment notes
examples/                                       curl scripts for manual smoke tests
```

## What it does

* On a debounced rising edge of input `TRIGGER`, POSTs an `Initiated`
  alert to the Airtame Emergency Alerts endpoint.
* On a debounced rising edge of input `CLEAR`, POSTs a `Resolved` payload
  with the same `id` to stop the active alert.
* Authenticates via HTTP Basic with the configured API key.
* Retries on `429` / `5xx` / timeouts with exponential backoff.
* Validates required fields before any HTTP call.
* Masks the API key in trace logs.
* Persists `active`, `active_alert_id`, edge state, and a monotonic
  counter as remanent variables so behavior survives HS restarts.
* Exposes `ACTIVE`, `SUCCESS_PULSE`, `ERROR_PULSE`, `LAST_STATUS_CODE`,
  `LAST_MESSAGE`, `LAST_ALERT_ID` as outputs.

See `docs/inputs_outputs.md` for the full pin contract and
`docs/deployment.md` for installation.

## Generating the .hsl

### HSL3 (SDK 3.0)

`HSL3 SDK 3.0/generator/generator3.cpython-39.pyc` consumes the JSON
config + the script and emits `<id>_<name>.hsl`. The exact CLI shape isn't
covered here — see the SDK PDFs (`HSL3 SDK 3.0 Doku EN.pdf` /
`Doku DE.pdf`) for the invocation — but the file pair this repo ships
already matches the layout of the SDK's `examples/http_request/` module
(JSON beside the `.py`, `scripts[0].filename` referencing the script).

### HSL2 (SDK 2.0.7)

The HSL2 SDK ships two scripts (`framework/create_project.pyc` and
`framework/generator.pyc`). Workflow:

1. Copy this repo's `projects/airtame_emergency/` directory into the
   SDK's `projects/` folder, **or** run
   `python create_project.pyc -p "airtame_emergency"` first and then
   replace the generated `config.xml` and `src/` with the ones here.
2. From the framework directory, run:
   ```
   python generator.pyc "airtame_emergency" UTF-8
   ```
3. The generator writes
   `projects/airtame_emergency/release/24815_AirtameEmergencyAlert.hsl`
   (deployable) and `.../debug/24815_AirtameEmergencyAlert.py`
   (simulator-runnable).
4. Import the `.hsl` into your Experte 4.13 project as a new logic
   module ("Logikbaustein"). The class name pattern Experte expects
   (`<InternalNameCamelCased><id>`) is already produced by the
   generator from `config.xml`.

When the generator re-runs on this `src/` file, it preserves user code
outside the `##!!!!##` ... `##!!!##` sentinel markers and regenerates
the block in between (pin constants, base-class call) from `config.xml`.
Don't edit anything between the markers by hand.

## Running tests

```
pip install -r requirements.txt
pytest -q
```

The suite (47 tests across HSL2 and HSL3) covers:

* Payload shape for `Initiated` and `Resolved`
* Validation: missing / oversized headline / description / bad template / bad duration
* HTTP success / 401 / 403 / 429-retry / 5xx-retry / timeout-retry / 404 no-retry
* Basic-auth header construction; non-HTTPS endpoint rejection; empty-key rejection
* Secret masking (`mask_secret` and end-to-end log inspection)
* Rising-edge detection + debounce window
* End-to-end `on_input_value`: trigger fires once on held-high, clear sends
  Resolve with matching id, validation surfaces to outputs without HTTP,
  auth/timeout errors surface to outputs, `on_init` restores from remanent

The tests run on Python 3 against a stub `hsl20_4` (`tests/_hsl20_4_stub.py`)
that models just enough of `BaseModule` / `_Framework` / `_Logger` for the
class to be exercised without the real Gira framework.

## Manual verification checklist

After deploying to a real HomeServer:

1. Set the input init-values in Experte: `API_KEY`, optionally tweak
   `API_ENDPOINT`, `ALERT_ID_PREFIX`, `TIMEOUT_SECONDS`, etc.
2. Wire input 1 (`TRIGGER`) to a test KNX object you can toggle.
3. Toggle 0 → 1 → 0.
   * Expect `SUCCESS_PULSE` to flick high then low, `ACTIVE` = 1,
     `LAST_STATUS_CODE` = 2xx, `LAST_ALERT_ID` populated.
   * Expect the alert to appear on Airtame screens.
4. Hold input 1 high for several seconds. **No second request.**
5. Toggle input 2 (`CLEAR`) 0 → 1 → 0.
   * Expect `SUCCESS_PULSE`, `ACTIVE` = 0, alert disappears.
6. Set `API_KEY` to an obviously invalid string and trigger.
   * Expect `ERROR_PULSE`, `LAST_STATUS_CODE` = 401, `LAST_MESSAGE`
     starts with `HTTP 401 (auth)`.
   * Trace log shows the masked key (`ab****yz`), never plaintext.
7. (Optional) Run `examples/curl_initiate.sh` to confirm the API key
   independently of the HomeServer.

## Security notes

* `API_KEY` is an input of type `STRING`. Set it once in Experte at module
  insertion time; Experte stores project files encrypted in the HS
  password store.
* `_mask()` is called before any log line that mentions the key.
  `tests/test_client.py::test_mask_secret_helper` and
  `tests/test_module.py::test_secret_is_masked_in_logger` pin this.
* `_send()` refuses to call when the endpoint isn't `https://` or the
  key is empty — both surface as `LAST_MESSAGE = "config: …"`.
* `.gitignore` blocks `projects/*/release/`, `projects/*/debug/`,
  `.env`, and `secrets.local.*`.

## Limitations / out of scope

* Only the Emergency Alerts endpoint is implemented.
* `_http_post()` uses `urllib2` (Py2 on HS, `urllib.request` on Py3
  for tests). If your HS firmware needs an alternative transport,
  override only `_http_post` — wire format is locked by tests.
