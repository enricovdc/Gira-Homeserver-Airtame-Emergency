# KNX wiring guide

How to bind this module's inputs and outputs to KNX group addresses on
a Gira HomeServer, including the gotchas you'll hit if you wire the
"obvious" datatype.

If you're new to Gira logic modules, skim
[`inputs_outputs.md`](inputs_outputs.md) first — that's the pin
contract; this doc is the KNX-side translation layer on top of it.

## TL;DR — what to wire to KNX and what NOT to

| Pin | KNX-wire it? | Why |
| --- | --- | --- |
| `TRIGGER`, `CLEAR`, `IS_DRILL`, `PROBE_NOW` | **YES** | These are the user-facing on/off signals. DPT 1.001. |
| `ACTIVE`, `SUCCESS_PULSE`, `ERROR_PULSE`, `LIVENESS` | **YES** | Wire to status LEDs, dashboard indicators, push-notification gateways. DPT 1.001. |
| `LAST_STATUS_CODE`, `LAST_PROBE_STATUS_CODE` | Maybe | DPT 7.001 fits HTTP codes (0–65535). Useful for diagnostics, but usually surfaced via Experte's visualisation, not KNX. |
| `HEADLINE`, `DESCRIPTION` | **NO**, usually | DPT 16 strings truncate at 14 bytes. Set as `init_value` at module-place time; only wire if you really need runtime swap from a KNX-side text source. |
| `API_ENDPOINT`, `API_KEY`, `ALERT_ID_PREFIX`, `SENDER_ID`, `CAP_CATEGORY`, `PAYLOAD_FORMAT`, `TEMPLATE` | **NO** | Configuration values. Set once via `init_value`. The Airtame URL (~80 chars) and the API key (32 chars) both exceed DPT 16's 14-byte limit. |
| `DEBOUNCE_MS`, `DURATION_SECONDS`, `TIMEOUT_SECONDS`, `MAX_RETRIES` | **NO**, usually | Configuration. Set as `init_value`. |
| `LAST_MESSAGE`, `LAST_ALERT_ID` | **NO** (over KNX) | Wire directly to Experte visualisation fields. KNX DPT 16 would truncate "HTTP 401 (auth)" or `gira-hs-20260519T084200Z-1` to garbage. |

## Datapoint Types

The Gira HomeServer translates between KNX group addresses (over the
bus, raw bytes per a DPT) and the Python types the logic module sees.
Quick reference for the DPTs you'll meet wiring this module:

| DPT | Bytes | KNX-side | Python in module |
| --- | --- | --- | --- |
| `1.001` | 1 bit | Switch: on / off | `int` 0 or 1 |
| `5.010` | 1 B | Counter pulses 0–255 | `int` |
| `7.001` | 2 B | Unsigned int 0–65 535 | `int` |
| `12.001` | 4 B | Unsigned int 0–4 294 967 295 | `int` |
| `16.001` | **14 B** | ASCII string, truncated at 14 chars | `str` |
| `16.000` | **14 B** | Latin-1 string, truncated at 14 chars | `str` |

DPT 16.001 is the showstopper here: any KNX string is 14 bytes max.
Sending `gira-hs-20260519T084200Z-1` (29 chars) over the bus arrives
truncated to `gira-hs-202605`. That's why this module exposes
diagnostic strings on its module-level outputs, but the README and
help recommend reading them via Experte visualisation rather than
group-addressing them.

## Wiring patterns

The diagrams below use `--->` for a KNX group address binding and
`==>` for an internal Experte logic wire (no KNX, can be any datatype).

### Pattern 1 — Manual lockdown switch with key-reset clear

The simplest setup: a wall-mounted key-switch fires the alert when
turned on, and a separate key-switch (or the same one, opposite
edge) clears it.

```
   KNX key-switch  --->  1.001  --->  TRIGGER (E1) ==> [module]
   KNX key-reset   --->  1.001  --->  CLEAR   (E2) ==> [module]

                                      ACTIVE  (A1) --->  1.001 ---> Status LED on visualisation
                                      ERROR_PULSE (A3) ---> 1.001 ---> Optional alarm
```

Set `HEADLINE`, `DESCRIPTION`, `TEMPLATE = "lockdown"`, and
`API_ENDPOINT` / `API_KEY` as `init_value`s in Experte at the time you
place the module. **Do not wire them to KNX** (DPT 16's 14-byte limit
will silently mangle the URL / key).

### Pattern 2 — Existing alarm bus integration

If you already have a building-wide alarm logic that emits a single
"emergency active" bool, just feed it into TRIGGER. Add an inverter +
edge detector or use Experte's "RS-Flipflop" block if you want the
alert to track the alarm state.

```
   Alarm bus  --->  1.001  ==> [edge detector] ==> TRIGGER
                                                ==> CLEAR (on falling edge)
```

### Pattern 3 — Periodic safe probe (recommended for production)

Wire `PROBE_NOW` to a Gira scheduler block running once a day. The
module sends a `Resolved` for a throwaway id (no alert appears on
screens, see [`AIRTAME_API.md`](AIRTAME_API.md)). `LIVENESS` then
holds your "Airtame integration is healthy" state until the next
probe.

```
   Gira scheduler "every 24h"  ==> [edge → 0.5s pulse] ==> PROBE_NOW (E17)

                                              LIVENESS  (A7) ---> 1.001 ---> Dashboard "Airtame OK" LED
                          LAST_PROBE_STATUS_CODE (A8) ---> [visualisation: numeric field]
```

You can also wire `PROBE_NOW` to a manual KNX button labelled "Test
Airtame integration" — operator-driven on-demand verification, with
zero risk of triggering a real alert.

### Pattern 4 — Per-scenario alerts (lockdown vs evacuate vs hold)

Run several module instances, each with different `TEMPLATE`,
`HEADLINE`, `DESCRIPTION` baked in as `init_value`s. Wire each
instance's `TRIGGER` to a different KNX button on the panel:

```
   "Lockdown" button  --->  1.001  ---> TRIGGER (instance #1, TEMPLATE="lockdown")
   "Evacuate" button  --->  1.001  ---> TRIGGER (instance #2, TEMPLATE="evacuate")
   "All clear" button --->  1.001  ---> CLEAR   (all instances)
```

The "all clear" button can be wired to all three instances'
`CLEAR` inputs in parallel — sending a Resolve to an instance with no
active alert is a documented no-op, so the inactive ones just shrug.

### Pattern 5 — Push-notification on result

Wire `SUCCESS_PULSE` and `ERROR_PULSE` to whatever notification
gateway you have (mobile push via the Gira S1, Telegram bridge,
email-on-bus, etc.). Each output pulses high-then-low after the HTTP
response, so a single rising-edge sink catches it.

```
   SUCCESS_PULSE  ==> [→1] ==> Mobile push "Alert sent: <last_alert_id>"
   ERROR_PULSE    ==> [→1] ==> Mobile push "Alert FAILED: <last_message>"
```

`LAST_ALERT_ID` and `LAST_MESSAGE` go via the internal Experte wiring,
not over KNX — so you keep the full string length intact for the
notification body.

## Recommended group-address scheme

If you're starting a fresh project, a 3-level scheme like
`Domain / Sub / Object` keeps Airtame addresses together:

```
  6/0/0   TRIGGER             1.001
  6/0/1   CLEAR               1.001
  6/0/2   IS_DRILL            1.001
  6/0/3   PROBE_NOW           1.001

  6/1/0   ACTIVE              1.001
  6/1/1   SUCCESS_PULSE       1.001
  6/1/2   ERROR_PULSE         1.001
  6/1/3   LIVENESS            1.001

  6/2/0   LAST_STATUS_CODE        7.001    (optional - usually visualisation)
  6/2/1   LAST_PROBE_STATUS_CODE  7.001    (optional)
```

`6` is arbitrary — pick whatever main group you reserve for emergency
/ alarm functions.

## Testing the wiring in Experte's monitor view

You don't need a physical KNX button to verify a fresh install:

1. Open the project in Experte and switch to the monitor / simulation
   view.
2. Right-click the `TRIGGER` group address → "Send value" → `1`,
   then immediately `0`.
3. Watch the module's outputs:
   * `SUCCESS_PULSE` should flick to 1 then 0 within a second.
   * `ACTIVE` should latch to 1.
   * `LAST_STATUS_CODE` should be 200 (or 2xx).
   * `LAST_MESSAGE` should read `alert initiated`.
4. Verify in Airtame Cloud that the alert appeared, then
   right-click `CLEAR` → "Send value" → `1`, then `0`.
5. `ACTIVE` falls back to 0; `LAST_MESSAGE` becomes `alert resolved`.

For the safe probe path, do the same with `PROBE_NOW` — but **nothing
should appear on Airtame screens**. `LIVENESS` should latch to 1 and
`LAST_PROBE_STATUS_CODE` to 200.

## Common KNX-side gotchas

| Symptom | Cause | Fix |
| --- | --- | --- |
| `TRIGGER` cycle does nothing on the bus | KNX object datatype is wrong (e.g. you bound a DPT 5.001 0–255 counter to the module's NUMBER input that expects a bool 0/1). | Use DPT 1.001 for trigger / clear / drill / probe. |
| `LAST_MESSAGE` shows truncated garbage on a KNX-side display | Wired through a DPT 16 group address; the 14-byte truncation chopped `HTTP 401 (auth)` mid-word. | Route to Experte's visualisation system directly; don't put a KNX group address on the wire for these. |
| `API_KEY` works one day, breaks the next | Same issue — set via a DPT 16 binding instead of an `init_value`, so only the first 14 chars are ever delivered to the module. | Set `API_KEY` as the input's `init_value` in Experte when you place the module. |
| Alert fires twice on one button press | The KNX object is set to "Send by change AND cyclic"; the cyclic resend re-issues the rising edge. | Either disable cyclic send on that GA or rely on the module's `DEBOUNCE_MS` (default 1000 ms) to swallow the duplicate. |
| `PROBE_NOW` accidentally configured the same GA as `TRIGGER` | Single button wired to both inputs sends a real alert AND a probe on every press. | Use separate group addresses for the two; the probe path is intentionally distinct. |
| Long `HEADLINE` / `DESCRIPTION` from a scene block arrives empty | The scene block emits a DPT 16 string and the actual text is longer than 14 bytes — only the first 14 chars survive, but Experte may also discard if a length mismatch is enforced. | Pass long strings via internal Experte string wires (no KNX), or pre-define them as `init_value`s and only toggle `TEMPLATE` from KNX. |

## See also

- [`inputs_outputs.md`](inputs_outputs.md) — the canonical pin contract
  this doc maps onto KNX.
- [`AIRTAME_API.md`](AIRTAME_API.md) — the wire protocol on the
  Airtame side, including the probe semantics referenced in
  Pattern 3.
- [`deployment.md`](deployment.md) — generator workflow and how the
  HSL2 / HSL3 `.hsl` files get produced.
