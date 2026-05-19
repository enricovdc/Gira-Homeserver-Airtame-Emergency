# Changelog

All notable changes to this module are documented in this file. Format
loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- `Makefile` with `make test / build / verify / clean` for one-command
  workflows.
- `docs/AIRTAME_API.md` summarising the wire protocol (JSON + CAP),
  authentication, the per-integration webhook URL pattern, and response
  semantics.
- `docs/LESSONS_LEARNED.md` codifying the patterns and pitfalls
  uncovered during development (mirrors the Gira-logic skill content).
- README "Troubleshooting" section listing the real bugs encountered
  with their fixes.

## [0.1.0] — Initial deliverable

### Added — module
- HSL2 SDK 2.0.7 project at `projects/airtame_emergency/`
  (`config.xml` + `src/24815_AirtameEmergencyAlert.py`) built around
  `hsl20_4.BaseModule` with the generator-managed sentinel block.
- HSL3 SDK 3.0 project at `projects/airtame_emergency_hsl3/`
  (`config_airtame_emergency.json` + `hsl3_24815_airtame_emergency.py`)
  built around a framework-injected `hsl3` object with
  `on_init / on_calc / on_timer` lifecycle.
- Identical algorithmic behavior for both: edge-debounced trigger /
  clear, JSON (Airtame Option 2) and CAP 1.2 XML (Airtame Option 1)
  payload formats selectable per-instance, exponential-backoff retry
  on `429` / `5xx` / timeouts, secret masking in trace logs,
  HTTPS-only enforcement.
- 8 remanent variables / store entries preserving `active`,
  `active_alert_id`, `active_sent_ts` (for CAP `<references>`),
  monotonic counter, and trigger/clear edge state across HS restarts.

### Added — deliverables
- Pre-generated `.hsl` artefacts committed under
  `projects/*/release/` and the HSL3 project root.
- Pre-generated `.hslz` archives bundling `.hsl` + EN/DE help + shared
  `style.css`, flattened to the SDK-required root layout.
- EN and DE help files at `help/{en,de}/log24815.html` following the
  SDK's `Help Template` structure (Description, Inputs, Outputs,
  Other, Payload formats, Behaviour table).
- `scripts/generate_hsl.sh` wrapping both generators
  (Python 2.7 + Python 3.9) with `GIRA_SDK_DIR` / `PYTHON27` /
  `PYTHON39` env vars.
- `scripts/build_hslz.py` flattening the help tree and rewriting
  `style.css` paths into HSLZ-compatible form.

### Added — tests
- 98 pytest tests across HSL2, HSL3, and the shared CAP payload spec.
- Framework stubs at `tests/_hsl20_4_stub.py` and `tests/_hsl3_stub.py`
  mirroring the real SDK APIs (read from `hsl20_4.py` source, not
  guessed) and exposing inputs/stores under all key forms the real
  firmware uses.
- Regression tests for every real bug encountered:
  - HSL2 pin/remanent lookups via BaseModule, not Framework.
  - HSL3 multi-form key resolution (numeric / UPPERCASE / lowercase).
  - HSL3 string inputs decoded from `bytes`.
  - HSL3 string stores persisted as `bytes`.
  - CAP element order matches the XSD sequence.
  - CAP message includes the `<instruction/>` and `<area>` skeleton
    per Airtame's sample.

### Fixed during development
- **HSL2 API mismatch** — replaced `self.FRAMEWORK._set_output_value`
  with `self._set_output_value` and similar; pin methods live on
  `BaseModule`, not `Framework`.
- **Record 5000 faulty** — escaped `|` and `"` characters out of all
  input/output labels in `config.xml` and the HSL3 JSON. Verified
  field count = `4 + n_inputs + 1 + n_outputs + 1`.
- **HSL3 trigger never fired** — added `_resolve_keys()` probing
  `inputs.keys()` on `on_init` and caching whichever form
  (lowercase / UPPERCASE / numeric) each logical name resolves to.
- **`TypeError: startswith first arg must be bytes…`** — added
  `_to_str(v)` helper decoding `bytes` values from string inputs and
  stores via `iso-8859-15` before any `str` operation.
- **`ValueError: Value must be of type bytes`** on `set_store` — encode
  string values via `_enc(s)` in `_persist_store` and `_persist_active`
  for HSL3 (matches the long-standing `set_output` convention).
- **CAP HTTP 400** — reordered `<info>` children to comply with the
  CAP 1.2 XSD sequence (`<expires>` between `<certainty>` and
  `<senderName>`, not at the end). Added empty `<instruction/>` and
  `<area>` skeleton matching Airtame's published sample.

### Documentation
- Comprehensive `README.md` covering build, deployment, and manual
  verification.
- `docs/inputs_outputs.md` enumerating every pin with init value and
  semantics.
- `docs/deployment.md` walking through the HSL2 and HSL3 generator
  CLI invocations.
- `examples/curl_initiate.sh` and `examples/curl_resolve.sh` for live
  smoke-testing the Airtame endpoint independently of the HomeServer.
