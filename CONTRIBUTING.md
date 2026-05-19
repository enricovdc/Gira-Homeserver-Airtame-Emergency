# Contributing

Thanks for taking a look at the module. Whether you're fixing a bug,
porting to a new firmware, or adding a feature — here's how the
repository fits together and what's expected of a change.

## Repo layout

```
projects/airtame_emergency/             HSL2 SDK 2.0.7 project
  config.xml                            inputs / outputs / remanent vars
  src/24815_AirtameEmergencyAlert.py    class AirtameEmergencyAlert24815(hsl20_4.BaseModule)
  release/                              committed .hsl + .hslz deliverables
  debug/                                committed simulator-runnable .py

projects/airtame_emergency_hsl3/        HSL3 SDK 3.0 project
  config_airtame_emergency.json         inputs / outputs / stores / timers
  hsl3_24815_airtame_emergency.py       class LogicModule (no inheritance)
  *.hsl  *.hslz                         committed deliverables

help/{en,de}/log24815.html              Experte F1 help pages
help/style.css                          shared stylesheet

tests/                                  pytest suite (98 tests as of v0.1.0)
docs/                                   pin contract, deployment, AIRTAME_API, LESSONS_LEARNED
scripts/                                generate_hsl.sh, build_hslz.py
examples/                               curl smoke-test scripts
```

## Development loop

A change typically touches three or four files: source, config,
tests, and (sometimes) help. The Makefile chains the steps:

```bash
make install-deps    # one-time: pip install -r requirements.txt
make test            # fast feedback - runs the full pytest suite
make build           # regenerate .hsl + .hslz from sources
make verify          # test + build + record-5000 sanity check
```

`make test` does not need the Gira SDK or Python 2.7 / 3.9 —
everything runs against the framework stubs in `tests/_hsl*_stub.py`.

`make build` does need both interpreters plus the SDK; set the env
vars per call:

```bash
GIRA_SDK_DIR=/path/to/Gira_HomeServer_SDK_Doku \
PYTHON27=python2.7 PYTHON39=python3.9 \
make build
```

For tips on getting Python 2.7 / 3.9 in a sandbox without `apt`, see
`docs/LESSONS_LEARNED.md` § Tooling.

## Adding an input or output

Both HSL2 and HSL3 projects need to stay structurally identical.

1. **HSL2 — `projects/airtame_emergency/config.xml`**
   - Add the new `<input>` / `<output>` / `<remanent_variable>` element
     in the desired position (numeric pin index follows position).
   - Make sure label / description text contains NO `|` and NO `"`
     (record 5000 parser is unescaped — see Troubleshooting in README).
2. **HSL2 — `src/24815_AirtameEmergencyAlert.py`**
   - The `PIN_I_*` / `PIN_O_*` / `REM_*` constants between the
     `##!!!!##` ... `##!!!##` markers are generator-managed; running
     `make build` regenerates them from `config.xml`. Don't hand-edit.
   - Use the new constants in the methods after the closing marker.
3. **HSL3 — `projects/airtame_emergency_hsl3/config_airtame_emergency.json`**
   - Add the matching `inputs[]` / `outputs[]` / `stores[]` entry.
   - Every entry needs a `"type"` field (`"number"` or `"string"`),
     even on stores (undocumented; generator fails without it).
4. **HSL3 — `hsl3_24815_airtame_emergency.py`**
   - Add the logical name to `INPUT_NAMES` / `OUTPUT_NAMES` /
     `STORE_NAMES` so `_resolve_keys` includes it in the multi-form
     lookup map.
   - Read via `self._iv(inputs, "name")` / `self._sv(store, "name")`.
   - Write via `self._set_output("name", value)` / `self._set_store("name", value)`.
   - Encode strings to bytes via `_enc()` on writes; the helpers
     handle decode-on-read via `_to_str()`.
5. **Help — `help/{en,de}/log24815.html`**
   - Add an `<tr>` to the matching `table-in` / `table-out` table.
   - Increment the pin number in the leading `<td>`.

Then `make verify` to regenerate everything and confirm field counts.

## Testing expectations

Every behaviour change needs a test. Patterns established in the repo:

* **Payload shape** — assert on the JSON dict or parsed `ET.Element`.
* **State machine** — drive `on_calc` / `on_input_value` with a
  scripted sequence and assert outputs + remanent state.
* **HTTP** — inject a fake via `inst._http_post` (HSL2) or
  `inst._send_http` (HSL3); never hit the network from a test.
* **Threading** — monkeypatch `airtame_hsl3_module.threading.Thread`
  with a synchronous runner (see `sync_threads_hsl3` fixture).
* **Time** — monkeypatch `airtame_module.time` / `airtame_hsl3_module.time`
  for debounce / expiry checks.

If you fix a real-firmware bug, add a regression test even if it
duplicates an end-to-end test you've already written. The
`test_string_inputs_are_decoded_when_framework_returns_bytes` and
`test_string_stores_are_persisted_as_bytes_not_str` tests are
single-purpose by design — they document one specific firmware quirk
each.

## Wire-format changes

If your change alters the bytes sent to Airtame:

* Read `docs/AIRTAME_API.md` first; the published guidelines are the
  contract.
* Add or update tests in `tests/test_cap_payload.py` and
  `tests/test_payload.py` to pin the expected bytes.
* For CAP, the element order inside `<info>` is fixed by the CAP 1.2
  XSD — keep tests asserting the order (`test_cap_*_info_children_in_xsd_order`).

## Committing

* `make verify` before committing — both `pytest` and the build must
  pass.
* Commit messages: short imperative subject ≤ 72 chars, then a blank
  line, then a paragraph or two of body. Reference real-HS error
  messages when fixing them so they're searchable in the log later.
* The `.hsl` and `.hslz` files are committed deliverables; if your
  change requires regeneration, run `make build` and commit the new
  binaries alongside the source change.

## Pull requests

Include in the PR description:

* What changed and why.
* Whether `make verify` is green.
* If the change required testing on a real HomeServer, paste the
  relevant log lines from Experte (with credentials redacted).

## Reporting bugs

Bug reports are most useful when they include the exact text of any
Experte error / log message, and the LBS / firmware version of the
HomeServer. The `Troubleshooting` table in `README.md` is built from
real reports — adding to it is a welcome PR target.
