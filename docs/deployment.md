# Deployment

This repo ships two parallel implementations of the same module:

* **HSL2** under `projects/airtame_emergency/` — for HomeServer firmware
  using the `hsl20_4` framework (Python 2.7 inside the deployed `.hsl`).
* **HSL3** under `projects/airtame_emergency_hsl3/` — for HomeServer
  firmware supporting HSL3 SDK 3.0 (Python 3.9, `LogicModule`,
  JSON config, `requests`).

Pick whichever matches the firmware on your HomeServer. If you're not
sure which the firmware supports, check the Experte 4.13 install for
`HSL/HSL3 SDK 3.0/` — if it's there, HSL3 is available.

## 1. Get an Airtame API key

1. Log in to Airtame Cloud as an organization admin.
2. Open the Emergency Alerts integration settings and generate an API key.
3. Copy it somewhere safe — Airtame only shows it once.

## 2. Locate the Gira HSL2 SDK

The SDK ships with Gira Experte 4.13. Inside the install you'll find a
`framework/` directory with at minimum:

```
framework/
  create_project.pyc      # scaffolds a new project tree
  generator.pyc           # turns src/<id>_<name>.py + config.xml -> release/<id>_<name>.hsl
  hsl20/                  # framework Python modules (hsl20_4.py, debug_page, etc.)
  projects/               # holds one folder per logic module project
```

Both `.pyc` files were inspected to build this repo; the project layout
matches what `create_project.pyc` produces.

## 3. Drop in the project

Two equivalent ways:

### a) Copy the directory in

Copy `projects/airtame_emergency/` from this repo into the SDK's
`projects/` directory:

```
<SDK>/framework/projects/airtame_emergency/
                          config.xml
                          src/24815_AirtameEmergencyAlert.py
```

### b) Scaffold first, then replace

```
cd <SDK>/framework
python create_project.pyc -p "airtame_emergency"
# overwrite the generated config.xml and src/* with the ones from this repo
```

## 4. Generate

From the SDK framework directory:

```
python generator.pyc "airtame_emergency" UTF-8
```

The generator:

1. Reads `projects/airtame_emergency/config.xml`.
2. Reads `projects/airtame_emergency/src/24815_AirtameEmergencyAlert.py`.
3. Splits the source at the `##!!!!##` and `##!!!##` sentinel markers,
   re-emits the metadata block in between (pin constants, BaseModule
   call) from `config.xml`, and preserves user code outside the markers.
4. Writes:
   * `projects/airtame_emergency/release/24815_AirtameEmergencyAlert.hsl`
     — the deployable artifact (base64+zlib-compressed Python class
     wrapped in Gira's `5000|/5001|/5012|` line format).
   * `projects/airtame_emergency/debug/24815_AirtameEmergencyAlert.py`
     — a flat Python view for the simulator.

## 5. Import into Experte

1. Open your Experte 4.13 project.
2. Import the generated `.hsl` from `release/` as a new logic module.
3. Drop the module onto a logic page; Experte shows the 13 inputs / 6
   outputs declared in `config.xml`.

## 6. Configure the module instance

Set the input init-values:

* `API_ENDPOINT` — leave at default unless Airtame instructs otherwise.
* `API_KEY` — paste the key from step 1.
* `ALERT_ID_PREFIX` — anything that helps you spot Gira-originated
  alerts in Airtame's audit log. Default `gira-hs` is fine.
* `HEADLINE`, `DESCRIPTION`, `TEMPLATE`, `IS_DRILL`,
  `DURATION_SECONDS` — fallbacks used when the runtime input is empty.
* `TIMEOUT_SECONDS`, `MAX_RETRIES`, `DEBOUNCE_MS` — leave at defaults
  unless you have evidence of latency or chattering inputs.

## 7. Wire the runtime inputs

* `TRIGGER` (1) — KNX object representing "emergency active" (lockdown
  button, alarm bus, etc.). Edge-debounced.
* `CLEAR` (2) — KNX object representing "emergency cleared".
* Inputs 3–7 are optional per-scenario overrides — drive from string
  constants or a scene if you want different messages per alarm.

## 8. Wire the outputs

* `ACTIVE` (1) — visualizations / dashboards.
* `SUCCESS_PULSE` / `ERROR_PULSE` (2, 3) — notification logic
  (push to mobile, alarm log).
* `LAST_STATUS_CODE` / `LAST_MESSAGE` (4, 5) — diagnostics page.
* `LAST_ALERT_ID` (6) — correlate with Airtame's audit log.

## 9. Verify

* Use `examples/curl_initiate.sh` to confirm the API key works
  end-to-end against the real Airtame endpoint before relying on the
  module.
* Run the pytest suite (`pytest -q`) — 34 tests pin the wire format,
  retry/error behavior, and edge/debounce.
* Walk through the manual checklist in `README.md` once installed.

## About the LBS number

`24815` is the module's globally-unique numeric identifier inside an
Experte project. To avoid collisions with other third-party modules,
reserve a number for yourself on
[hs-help.net](https://hs-help.net/) (community wiki, "LBS-Nummern
Vergabe") and replace `24815` in:

* `config.xml` `id="..."`
* file name `src/24815_AirtameEmergencyAlert.py`
* class name suffix `AirtameEmergencyAlert24815`

The generator derives the class name from `internal_name` + `id`, so
once you change `id` and the file name, re-run the generator on a
fresh `src/` (or rename the class manually before regen).

## Notes on the HSL2 framework API

The deployed module uses these `hsl20_4` surfaces:

* `hsl20_4.BaseModule` — base class.
* `self._get_framework()` — returns the framework object.
* `self._get_logger(hsl20_4.LOGGING_NONE, ())` — logger; the module
  uses `info(line, msg)` and `error(line, msg)`.
* `framework._get_input_value(pin)` / `_set_output_value(pin, value)`.
* `framework._get_remanent(idx)` / `_set_remanent(idx, value)`.

If your framework version exposes these under different names, edit
the helper methods in the class file. The HTTP layer is isolated in
`_http_post`; the test suite pins everything above it so refactors stay
honest.
