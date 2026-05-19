# Lessons learned — Gira HomeServer logic modules

Distilled from this project's iteration. The corresponding skill prompt
in chat history sources from this same content; keep both in sync.

## Three SDK generations, very different shapes

| Generation | Language | Config format | Module shape |
| --- | --- | --- | --- |
| HSL1 (SDK 1.0) | C-like custom DSL | --- | --- |
| HSL2 (SDK 2.0.7) | Python 2.7 | XML | `class Foo(hsl20_4.BaseModule)` with generator-managed sentinel block |
| HSL3 (SDK 3.0) | Python 3.9 | JSON | Plain `class LogicModule:`, framework injected via `__init__(self, hsl3)` |

Don't guess which target — ask the user, or check firmware version
(HSL3 is supported from Experte 4.13+).

## LBS numbers

* Required, embedded in filename + class name + config `id`.
* Reserved ranges: `1-9999` = Gira built-ins (do not use);
  `10000-19999` historic / paid; **`20000-99999` = third-party.**
* Reserve via hs-help.net "LBS-Nummern Vergabe" before publishing.

## Record-format gotcha: `|` and `"` are forbidden in labels

The generated `.hsl` is line-oriented with `|`-delimited records, each
field wrapped in `"..."`. Experte's parser does no escaping. Any
embedded `|` or `"` inside an input/output/translation label breaks
field-count and surfaces as:

> Definition of record type 5000 is faulty

on logic-node load. Safe substitutes: `/` for alternation, `,` for
lists, plain text for emphasis. Verify with:

```bash
awk -F'|' 'NR==2{print NF}' generated.hsl
# must equal 4 + n_inputs + 1 + n_outputs + 1
```

## HSL2 essentials

### Pin / remanent API lives on BaseModule, NOT on Framework

The #1 thing to get right:

```python
self._get_input_value(index)           # NOT self.FRAMEWORK._get_input_value
self._set_output_value(index, value)
self._get_remanent(index)
self._set_remanent(index, value)
```

`self.FRAMEWORK` is for factories and helpers
(`create_http_client`, `create_tcp_client`, `create_udp_*`,
`create_timer`, `create_debug_section`, `resolve_dns`,
`get_homeserver_version`).

### Generator workflow

```
python generator.pyc "<project_name>" <encoding>
```

Run from the SDK's `framework/` directory. Reads
`projects/<name>/{config.xml, src/<id>_<name>.py}`. Writes
`release/<id>_<name>.hsl` (deployable) and `debug/<id>_<name>.py`
(simulator-runnable). The `.hsl` is base64+zlib-compressed Python
wrapped in Gira's `5000|/5001|/5002|/5003|/5004|/5012|` line format.

### Sentinel-marker discipline

The generator preserves user code OUTSIDE the
`##!!!!##...##!!!##` markers and regenerates the middle from
`config.xml` on every run.

* Module-level imports + helper functions go ABOVE the opening marker.
* Methods (still inside the class via indentation) go BELOW the
  closing marker.
* Do NOT add `self.FRAMEWORK._run_in_context_thread(self.on_init)`
  inside the markers — the generator wraps the deployed `.hsl` with
  that call automatically, and an in-markers copy gets wiped on regen.
* The wrap-for-deploy step strips lines starting with `#` and empty
  lines from user code. Comments don't survive into the `.hsl` (they
  remain in `debug/`).

### Config.xml schema

`<module>` with `category`, `context`, `id`, `name`, `version`,
`internal_name`, `external_name`. Children: `<inputs>`, `<outputs>`,
`<remanent_variables>`, `<imports>`, `<libs>`, `<translations>`.

* Slot types: `NUMBER`, `STRING`, `BASE_PATH`, `DESTINATION_PORT`.
  Last two come in pairs, only one of each per module.
* No "parameter" concept; what feels like a parameter is just an input
  with `init_value` set when the module is placed.
* Class name = camel-cased `internal_name` + `id`.

### Remanent variables

Persistent across HS restart. Flushed every 15 minutes only, so don't
rely on them surviving a crash mid-tick. Index via `self.REM_<NAME>`
constants the generator emits. String values capped at 30 000 bytes.

### HTTPS

Use Python 2 stdlib (`urllib2`, `ssl`, `urlparse`); the bundled
`hsl20_4_http_client` is deprecated. Canonical example:
`examples/https_client/WebRequest/`.

## HSL3 essentials

### Class shape

```python
class LogicModule:
    def __init__(self, hsl3):
        self.fw = hsl3
        self.debug = self.fw.create_debug_section()

    def on_init(self, inputs, store):  pass
    def on_calc(self, inputs):         pass
    def on_timer(self, timer):         pass
```

No inheritance. `hsl3` is the framework object the runtime injects.

### Input / store containers expose multiple key forms — resolve once

On at least one firmware version, `inputs.keys()` and `store.keys()`
return BOTH numeric indices AND `UPPERCASE` const-name strings
(e.g. `[1, 2, ..., 'TRIGGER', 'CLEAR', ...]`), but NOT the lowercase
`identifier` strings from the JSON config. The SDK example uses
lowercase, so the policy varies. **Probe `keys()` in `on_init` and
cache which form each logical name resolves to**, then use the cached
form everywhere downstream:

```python
def _resolve_keys(self, inputs, store):
    in_keys = list(inputs.keys())
    for i, name in enumerate(self.INPUT_NAMES, start=1):
        for cand in (name, name.upper(), i):
            if cand in in_keys:
                self._in_key[name] = cand
                break
        else:
            self._in_key[name] = name
```

### Strings cross the boundary as bytes (iso-8859-15)

* `inputs.value(...)` returns string-typed inputs as **`bytes`**, not
  `str`. Decode at the read seam:
  ```python
  def _to_str(v):
      if isinstance(v, bytes):
          return v.decode("iso-8859-15", "replace")
      return v
  ```
* `store.value(...)` similarly returns bytes for string stores.
* `self.fw.set_output(name, value)` and `self.fw.set_store(name, value)`
  **require bytes** for string-typed targets. Sending `str` raises
  `ValueError: Value must be of type bytes`.
  ```python
  self.fw.set_output(name, text.encode("iso-8859-15", "replace"))
  self.fw.set_output(name, float(number))
  ```

### Threading and IO

Don't block `on_calc`. Spawn `threading.Thread(target=...,
daemon=True)` for HTTP / network work; marshal output writes back via
`self.fw.run_in_context(method, args_tuple)`. `requests` is available
in the HS Python 3 bundle.

### Config (JSON) — undocumented gotcha

`stores[].type` is REQUIRED (`"number"` or `"string"`), even though
the SDK examples ship with `"stores": []` and don't show the field.
Same for inputs / outputs. The generator fails with:

> TypeError: __init__() missing 1 required positional argument: 'type'

if you forget.

### Generator CLI

```
python generator3.cpython-39.pyc --source config.json [--target out.hsl] [--debug]
```

Short flags: `-s`, `-t`, `-d`. `--target` overrides `hsl_filename`
from the JSON; if omitted, the JSON wins.

## Help files (Experte F1)

The SDK ships a template at `HSL/Help Template/{en,de}/log55555.html`
+ `style.css`. Rename to `log<LBS>.html` and fill in.

Required chapters (the template's TOC anchor names matter to Experte's
navigation): 1. Description, 2. Inputs, 3. Outputs, 4. Other, plus
optional 5. Similar functions and 6. Value table / behaviour table.

Tables use the SDK's CSS classes (`table-in`, `table-out`,
`table-logic-info`, `io-nr input/output center`, `io-name`,
`io-init`, `io-init string center`, `o-sbc center`, `io-descr`).
Boxes use `alert-box ibox-warn` (Important) and
`alert-box ibox-hint` (Note).

## HSLZ — bundling .hsl + help into one importable archive

An `.hslz` is a renamed `.zip` (per
`HSL/HSLZ/en/hslz_structure.html`). Experte → "Logikbausteine →
Importieren" installs the logic node and its help files in one step.

### Required flat layout

All files at the archive root — no subdirectories for help:

```
<ID>_<Name>.hsl              the logic node
<LANG>-log<ID>.html          help, LANG in {DE, EN, FR, IT}
log<ID>.html                 (alternative) single help, follows Experte UI lang
style.css                    optional shared stylesheet
<ID>/hsupload/*.*            optional companion files uploaded to HS (HSL2.0+ only)
```

If your source layout keeps help under `help/en/` and `help/de/`,
rewrite the `<link rel="stylesheet">` in the HTML from
`../style.css` to `style.css` before zipping, since everything is
flat at the archive root.

## CAP 1.2 XSD enforces element order inside `<info>`

Airtame validates strictly:

```
category → event → urgency → severity → certainty
→ expires (optional) → senderName → headline → description
→ instruction → area
```

A message with `<expires>` after `<description>` parses as XML but
fails the XSD; Airtame returns HTTP 400. Also include the optional
`<instruction/>` and `<area><areaDesc></areaDesc><circle></circle></area>`
even when empty — Airtame's published sample emits them and that
keeps the message inside the validator's happy path.

## Testing under pytest (CI-friendly)

Real HSL only runs on a HomeServer. Cover behavior in CI:

* Write a minimal `hsl20_4` or `hsl3` stub module mirroring the real
  API surface; READ THE SDK SOURCE, don't guess. For HSL2 the stub
  needs `BaseModule` with `_get_input_value` / `_set_output_value` /
  `_get_remanent` / `_set_remanent` / `_get_framework` /
  `_get_logger`, plus `LOGGING_NONE`. For HSL3 a fake `hsl3` plus
  `inputs / store / timer` containers with `keys / value / changed`.
  **Register inputs/stores under all key forms** (numeric, UPPERCASE,
  lowercase) so the stub mirrors real-firmware behavior and tests
  that probe `keys()` work the same way the real module does.
* HSL2 class files start with a digit (`24815_Foo.py`) so direct
  `import` fails. Side-load via
  `importlib.util.spec_from_file_location` and inject the stub into
  `sys.modules["hsl20_4"]` BEFORE loading.
* Make HTTP overridable: factor `_http_post` / `_send_http` into an
  instance method so tests can monkeypatch it.
* For HSL3, monkeypatch `threading.Thread` to run synchronously in
  tests so worker-thread side effects land before assertions.

## Tooling: getting the toolchain in a sandbox

* HSL2 `generator.pyc` is Python 2.7 bytecode → `uncompyle6`
  decompiles cleanly. Read `framework/hsl20/hsl20_4.py` for the real
  API.
* HSL3 `generator3.cpython-39.pyc` is Python 3.9 bytecode →
  `uncompyle6 / decompyle3` don't support 3.9; must run the `.pyc`
  with an actual Python 3.9 interpreter.
* No Python 2.7 / 3.9 in apt? Standalone builds work:
  * Python 3.9: github.com/astral-sh/python-build-standalone releases
    (linux/macos static binaries).
  * Python 2.7:
    `repo.anaconda.com/pkgs/main/linux-64/python-2.7.18-*.tar.bz2`.

## Common pitfalls and how to spot them

| Symptom | Cause | Fix |
| --- | --- | --- |
| `Definition of record type 5000 is faulty` in Experte | `\|` or `"` inside an input/output label | Replace with `/`, `,`, plain text |
| `TypeError: __init__() missing 1 required positional argument: 'type'` from HSL3 generator | Missing `type` field on a `stores`/`inputs`/`outputs` entry | Add `"type": "number"\|"string"` |
| HSL2 outputs always 0 / nothing happens | `self.FRAMEWORK._set_output_value(...)` instead of `self._set_output_value(...)` | Pin methods live on BaseModule, not Framework |
| HSL3 trigger doesn't fire | Looked up by lowercase, but firmware exposes UPPERCASE / numeric only | Probe `inputs.keys()` and cache the right form per logical name |
| HSL3 `TypeError: startswith first arg must be bytes or a tuple of bytes, not str` | String inputs arrive as bytes, used in str operation | Decode bytes → str at the read seam |
| HSL3 `ValueError: Value must be of type bytes` | Wrote str to `set_output` / `set_store` for a string-typed target | Encode str → bytes via iso-8859-15 |
| HSL3 string outputs show `b'...'` in Experte | Forgot to encode before `set_output` | Same fix as above |
| Airtame HTTP 400 on CAP | `<info>` children out of XSD order, or missing `<instruction/>`/`<area>` | Reorder per CAP 1.2 XSD; add empty `<instruction/>` and `<area>` skeleton |
| HSL2 module silently does nothing after regen | Helper code placed inside the `##!!!!##...##!!!##` markers and wiped | Move helpers outside the markers |
| Help file 404 / no styling after .hslz install | `help/en/` and `help/de/` subdirs not flattened to `EN-log<ID>.html` / `DE-log<ID>.html`, or stylesheet href not rewritten | Build script must flatten the tree and rewrite the link |
| HSL2 source file unimportable in pytest | Filename starts with a digit, plain `import` fails | Side-load with `importlib.util.spec_from_file_location` |

## Reference implementation

This repository is the worked example. Each pitfall above has a
regression test in `tests/` that would have caught the bug at CI time.
