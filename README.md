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

### Payload formats — Airtame Option 1 (CAP) and Option 2 (JSON)

Airtame's [Emergency Alerts payload guidelines](https://help.airtame.com/hc/en-us/articles/28499448688029-Emergency-alerts-integrations-payload-guidelines)
accept two wire formats on the same endpoint with the same Basic auth.
The doc is the source of truth — the implementation follows it
verbatim and the tests pin every deviation.

#### Option 2 — Airtame JSON (recommended by the docs)

`Content-Type: application/json`. Schema:

```
id: string;                    // unique value expected
status: "Initiated" | "Resolved";
template: AlertTemplate;       // defaults to "high" if Airtame can't determine one
headline: string;
description?: string;          // optional
isDrill?: boolean;             // optional - shows the Drill badge
expiresAt?: string;            // optional, ISO 8601 with timezone
```

`AlertTemplate` accepts **all 10** values from the docs:
`high`, `medium`, `low`, `blank`, `all-clear`, `hold`, `secure`,
`lockdown`, `evacuate`, `shelter`. The SRP templates (`secure`,
`lockdown`, `evacuate`, `shelter`, `hold`, plus `all-clear` and `blank`)
are screen-protocol templates: per the docs *"only the description is
customizable as the headline is set by the protocol"* — so the
`HEADLINE` input you provide will be ignored by Airtame on those.

Clearing: send the same `id` with `status: "Resolved"`.

#### Option 1 — CAP 1.2 XML

`Content-Type: application/xml`, namespace
`urn:oasis:names:tc:emergency:cap:1.2`. Airtame strictly validates
against the CAP XSD and rejects invalid messages.

Per the Airtame docs: *"For CAP structured messages, we use the
`<urgency>` field from the XML to define what to choose between high,
medium and low."* — CAP can only reach those three templates. SRP
templates require JSON. The module maps the `TEMPLATE` input to
`<urgency>`:

| `TEMPLATE` input | CAP `<urgency>` | Airtame chooses |
| --- | --- | --- |
| `high`, `lockdown`, `evacuate`, `shelter`, `secure` | `Immediate` | high |
| `medium`, `hold` | `Expected` | medium |
| `low`, `all-clear`, `blank` | `Future` | low |

Drill alerts in CAP are sent with `<severity>Minor</severity>` (real
alerts use `Severe`). `<status>` is always `Actual` — CAP `Test`
status means "recipients must disregard" so Airtame would drop it.
Drill differentiation in JSON happens via the `isDrill` field; there
is no equivalent in CAP, so drills don't show the Drill badge when
sent as CAP.

Cancel: send a fresh message with `<msgType>Cancel</msgType>` and
`<references>SENDER,ORIGINAL_ID,ORIGINAL_SENT</references>` pointing
at the alert to stop. Per Airtame's published Stop-an-alert sample,
the Cancel mirrors the original alert's urgency/severity/certainty
rather than degrading to `Past/Unknown/Unknown`.

#### Selecting the format

Set the `PAYLOAD_FORMAT` input to `"json"` (default) or `"cap"` in
Experte at module insertion time, or drive it from a runtime string.
When `cap`, the module also reads `SENDER_ID` (used for `<sender>`,
`<senderName>` and the `<references>` prefix) and `CAP_CATEGORY` (for
`<info>/<category>`; default `Safety`). For CAP-mode cancellation,
the module persists the original `<sent>` timestamp in the
`ACTIVE_SENT_TS` remanent variable / store so it survives HS
restarts.

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

### HSL3 (SDK 3.0) — `python generator3.cpython-39.pyc --source ...`

Pulled verbatim from `HSL3 SDK 3.0 Doku EN.pdf` (pp. 3, 16-17):

> The generator is called via the command line with the Python interpreter.
> `--source` is used to specify the configuration file
> (default value: `config.xml`).
> `--target` specifies the target file, which overwrites the configuration
> file specifications.
> Optionally, `--debug` enables debug outputs that are disabled by default.

#### One-time environment setup (Windows, from the docs)

```
py install 3.9
cd Projekte
py -3.9 -m venv hsl3
cd hsl3
Scripts\activate
```

Unzip `hsl3_generator_und_beispiele.zip` from the Experte 4.13 install
into the `Projekte\hsl3` directory. After this, the `generator/`
folder contains `generator3.cpython-39.pyc`.

On Linux / macOS the equivalent is:

```
python3.9 -m venv hsl3 && source hsl3/bin/activate
pip install requests        # needed by the module, not by the generator
```

#### Generate the .hsl

From inside this repo:

```
cd projects/airtame_emergency_hsl3
python <path-to-SDK>/HSL3\ SDK\ 3.0/generator/generator3.cpython-39.pyc \
       --source config_airtame_emergency.json \
       --target 24815_airtame_emergency.hsl \
       --debug
```

The generator reads `config_airtame_emergency.json`, picks up
`hsl3_24815_airtame_emergency.py` (referenced via `scripts[0].filename`),
and writes `24815_airtame_emergency.hsl` next to the config.

`--target` is optional: if you omit it, the generator uses
`module.hsl_filename` from the JSON (`24815_airtame_emergency.hsl`),
so the short form is just:

```
python <path>/generator3.cpython-39.pyc -s config_airtame_emergency.json
```

CLI summary (from the docs):

| flag | short | meaning | default |
| --- | --- | --- | --- |
| `--source <file>` | `-s` | configuration file | `config.xml` |
| `--target <file>` | `-t` | output `.hsl` (overrides `hsl_filename` in the config) | from config |
| `--debug` | `-d` | verbose generator output | off |

#### Import into Experte 4.13

> The generated *.hsl file can then be imported and used with
> Expert version 4.13.0 and above. (HSL3 SDK Doku EN.pdf, p. 3)

In Experte: File → Import → Logikbaustein → pick the generated
`24815_airtame_emergency.hsl`. Drop the module onto a logic page; the
13 inputs / 6 outputs declared in the JSON will be visible.

### HSL2 (SDK 2.0.7) — `python generator.pyc "<project>" <encoding>`

The HSL2 SDK lives at `Gira HomeServer SDK Doku/HSL/HSL2 SDK 2.0.7/`.
Inside `framework/` you'll find:

```
framework/
  create_project.pyc      # scaffolds projects/<name>/{src,release,debug,config.xml}
  generator.pyc           # turns src/<id>_<name>.py + config.xml -> release/<id>_<name>.hsl
  hsl20/                  # framework Python modules (hsl20_4.py + helpers)
  python26/               # bundled Python 2.6 interpreter (Windows install only)
```

The generator is Python 2.7. On Windows the SDK ships its own bundled
interpreter; on Linux / macOS, install Python 2.7 yourself (e.g.
`pyenv install 2.7.18`).

#### Step 1 — drop the project into the SDK

Either:

**a)** Copy this repo's `projects/airtame_emergency/` directory into
`<SDK>/HSL/HSL2 SDK 2.0.7/framework/projects/`. Final tree:

```
<SDK>/HSL/HSL2 SDK 2.0.7/framework/projects/airtame_emergency/
  config.xml
  src/24815_AirtameEmergencyAlert.py
```

**b)** Or scaffold first, then overwrite:

```
cd <SDK>/HSL/HSL2\ SDK\ 2.0.7/framework
python create_project.pyc -p "airtame_emergency"
# overwrite the generated config.xml and src/ with the files from this repo
```

(`create_project.pyc` creates the four sibling folders
`src/`, `release/`, `debug/` plus a starter `config.xml`.)

#### Step 2 — generate

From the framework directory:

```
cd <SDK>/HSL/HSL2\ SDK\ 2.0.7/framework
python generator.pyc "airtame_emergency" UTF-8
```

CLI: `python generator.pyc <project-folder-name> <source-encoding>`.
The encoding must match the `# coding:` line at the top of
`src/24815_AirtameEmergencyAlert.py` — this repo uses **UTF-8**.

#### Step 3 — outputs

The generator writes two files:

```
projects/airtame_emergency/release/24815_AirtameEmergencyAlert.hsl   <- deployable
projects/airtame_emergency/debug/24815_AirtameEmergencyAlert.py      <- simulator-runnable
```

#### Step 4 — import into Experte 4.13

File → Import → Logikbaustein → pick
`release/24815_AirtameEmergencyAlert.hsl`. Drop the module onto a logic
page. The 13 inputs and 6 outputs declared in `config.xml` will be
visible, with their `init_value`s pre-filled.

#### Re-generation hygiene

When the generator re-runs on `src/24815_AirtameEmergencyAlert.py`,
it preserves user code outside the `##!!!!##` ... `##!!!##` sentinel
markers and **regenerates the block in between** (pin constants,
`BaseModule.__init__` call) from `config.xml`. Don't edit anything
between the markers by hand — your change will be overwritten on the
next generate.

If you change `config.xml` (rename a pin, add an input, etc.), re-run
`python generator.pyc "airtame_emergency" UTF-8` and the pin constants
inside the markers update automatically.

## Running tests

```
pip install -r requirements.txt
pytest -q
```

The suite (90 tests across HSL2, HSL3, and the shared CAP payload spec)
covers:

* Payload shape for `Initiated` and `Resolved`
* Validation: missing / oversized headline / description / bad template / bad duration
* HTTP success / 401 / 403 / 429-retry / 5xx-retry / timeout-retry / 404 no-retry
* Basic-auth header construction; non-HTTPS endpoint rejection; empty-key rejection
* Secret masking (`mask_secret` and end-to-end log inspection)
* Rising-edge detection + debounce window
* End-to-end `on_input_value`: trigger fires once on held-high, clear sends
  Resolve with matching id, validation surfaces to outputs without HTTP,
  auth/timeout errors surface to outputs, `on_init` restores from remanent
* All 10 Airtame AlertTemplate values accepted (`high`, `medium`,
  `low`, `blank`, `all-clear`, `hold`, `secure`, `lockdown`, `evacuate`,
  `shelter`) and description is optional per the docs
* CAP 1.2 XML payload: correct namespace, required elements
  (`identifier`/`sender`/`sent`/`status`/`msgType`/`scope` plus
  `info`/`category`/`event`/`urgency`/`severity`/`certainty`),
  template→urgency mapping (including SRP templates degrading to
  Immediate/Expected/Future), drill→`<severity>Minor</severity>`
  while `<status>` stays `Actual`, Cancel mirrors the original
  alert's urgency/severity/certainty (per the published sample),
  Cancel `<references>` payload shape, XML special-char escaping,
  and `application/xml` Content-Type switching when
  `PAYLOAD_FORMAT=cap`

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
