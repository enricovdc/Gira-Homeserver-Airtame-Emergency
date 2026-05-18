# Airtame Emergency Alert - HSL3 LBS 24815
#
# Companion to projects/airtame_emergency_hsl3/config_airtame_emergency.json.
# Run the HSL3 generator (generator3.cpython-39.pyc) on this pair to produce
# release/24815_airtame_emergency.hsl. The framework injects an `hsl3` object
# into __init__; this module does not subclass anything.
#
# References: HSL3 SDK 3.0 examples (binary_trigger, http_request,
# communication_between_instances) confirm the lifecycle:
#   on_init(inputs, store) -> once at startup
#   on_calc(inputs)        -> every input change
#   on_timer(timer)        -> when a configured timer fires
# Pin / store / timer identifiers are strings, output strings must be bytes
# encoded iso-8859-15, and all HS-side writes must happen on the context
# thread via self.fw.run_in_context(method, args_tuple).
import base64
import json
import threading
import time

import requests


# Airtame AlertTemplate values per the Emergency Alerts payload guidelines.
# Only the first three are reachable via CAP <urgency>; the SRP templates
# (secure / lockdown / evacuate / shelter / hold / blank / all-clear) can
# only be selected by sending JSON. Airtame falls back to "high" if it can't
# determine the template.
ALLOWED_TEMPLATES = (
    "high", "medium", "low",
    "blank", "all-clear", "hold",
    "secure", "lockdown", "evacuate", "shelter",
)
CAP_REACHABLE_TEMPLATES = ("high", "medium", "low")
ALLOWED_FORMATS = ("json", "cap")
MAX_HEADLINE_LEN = 200
MAX_DESCRIPTION_LEN = 2000

# CAP 1.2 namespace; Airtame strictly validates messages against the CAP XSD.
CAP_NS = "urn:oasis:names:tc:emergency:cap:1.2"
# Airtame derives CAP template selection from <urgency> only. SRP templates
# degrade to the nearest urgency bucket on the CAP wire.
TEMPLATE_TO_URGENCY = {
    "high": "Immediate", "lockdown": "Immediate", "evacuate": "Immediate",
    "shelter": "Immediate", "secure": "Immediate",
    "medium": "Expected", "hold": "Expected",
    "low": "Future", "all-clear": "Future", "blank": "Future",
}
SEVERITY_DEFAULT = "Severe"
SEVERITY_DRILL = "Minor"


def _xml_escape(s):
    if s is None:
        return ""
    return (str(s).replace("&", "&amp;")
                  .replace("<", "&lt;")
                  .replace(">", "&gt;")
                  .replace("\"", "&quot;")
                  .replace("'", "&apos;"))


def build_cap_alert(alert_id, sender_id, sent_iso, headline, description,
                    template, is_drill, category, expires_iso):
    """CAP 1.2 Alert. <event> mirrors Airtame's sample shape (short tag from
    the template), <status> is Actual (CAP 'Test' would be discarded by
    recipients; drills are JSON-only)."""
    urgency = TEMPLATE_TO_URGENCY.get(template, "Immediate")
    severity = SEVERITY_DRILL if is_drill else SEVERITY_DEFAULT
    event_short = template.capitalize() if template else "Emergency"
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<alert xmlns="' + CAP_NS + '">'
        '<identifier>' + _xml_escape(alert_id) + '</identifier>'
        '<sender>' + _xml_escape(sender_id) + '</sender>'
        '<sent>' + sent_iso + '</sent>'
        '<status>Actual</status>'
        '<msgType>Alert</msgType>'
        '<scope>Public</scope>'
        '<info>'
        '<category>' + _xml_escape(category) + '</category>'
        '<event>' + _xml_escape(event_short) + '</event>'
        '<urgency>' + urgency + '</urgency>'
        '<severity>' + severity + '</severity>'
        '<certainty>Observed</certainty>'
        '<senderName>' + _xml_escape(sender_id) + '</senderName>'
        '<headline>' + _xml_escape(headline) + '</headline>'
        '<description>' + _xml_escape(description or "") + '</description>'
        '<expires>' + expires_iso + '</expires>'
        '</info>'
        '</alert>'
    )


def build_cap_cancel(cancel_id, sender_id, cancel_sent_iso, original_id,
                     original_sent_iso, category, is_drill, template="high"):
    """CAP 1.2 Cancel. Per Airtame's Stop-an-alert sample, the cancel mirrors
    the original alert's urgency/severity/certainty rather than degrading to
    Past/Unknown/Unknown."""
    urgency = TEMPLATE_TO_URGENCY.get(template, "Immediate")
    severity = SEVERITY_DRILL if is_drill else SEVERITY_DEFAULT
    references = "%s,%s,%s" % (sender_id, original_id, original_sent_iso)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<alert xmlns="' + CAP_NS + '">'
        '<identifier>' + _xml_escape(cancel_id) + '</identifier>'
        '<sender>' + _xml_escape(sender_id) + '</sender>'
        '<sent>' + cancel_sent_iso + '</sent>'
        '<status>Actual</status>'
        '<msgType>Cancel</msgType>'
        '<scope>Public</scope>'
        '<references>' + _xml_escape(references) + '</references>'
        '<info>'
        '<category>' + _xml_escape(category) + '</category>'
        '<event></event>'
        '<urgency>' + urgency + '</urgency>'
        '<severity>' + severity + '</severity>'
        '<certainty>Observed</certainty>'
        '<senderName>' + _xml_escape(sender_id) + '</senderName>'
        '<headline></headline>'
        '<description></description>'
        '</info>'
        '</alert>'
    )


class LogicModule:
    def __init__(self, hsl3):
        self.fw = hsl3
        self.debug = self.fw.create_debug_section()
        # Cached snapshot of the latest inputs - read fresh on each on_calc.
        self._snap = {}
        # Edge-detect / debounce state, restored from `store` in on_init.
        self._last_trig_val = 0
        self._last_trig_ts_ms = 0
        self._last_clr_val = 0
        self._last_clr_ts_ms = 0
        self._counter = 0
        # Active-alert state, also restored from `store`.
        self._active = False
        self._active_alert_id = ""
        self._active_sent_ts = ""  # ISO 8601, needed for CAP cancel <references>
        # HTTP transport seam - tests monkeypatch this; default uses requests.
        self._send_http = self._send_http_real

    # ---- HSL3 lifecycle hooks --------------------------------------------

    def on_init(self, inputs, store):
        self.debug.log("on_init keys=%s store_keys=%s"
                       % (list(inputs.keys()), list(store.keys())))
        self._snap_from(inputs)
        try:
            self._active = bool(int(store.value("active") or 0))
            self._active_alert_id = store.value("active_alert_id") or ""
            self._active_sent_ts = store.value("active_sent_ts") or ""
            self._counter = int(store.value("counter") or 0)
            self._last_trig_val = int(store.value("last_trig_val") or 0)
            self._last_trig_ts_ms = int(store.value("last_trig_ts_ms") or 0)
            self._last_clr_val = int(store.value("last_clr_val") or 0)
            self._last_clr_ts_ms = int(store.value("last_clr_ts_ms") or 0)
        except Exception as e:
            self.debug.log("store restore failed: %s" % e)
        # Restore the user-visible outputs to match the persisted state.
        self.fw.run_in_context(self._emit_outputs, (
            1 if self._active else 0, 0, 0, 0, "", self._active_alert_id))

    def on_calc(self, inputs):
        self._snap_from(inputs)
        if inputs.changed("trigger"):
            if self._rising_edge(int(self._snap.get("trigger") or 0),
                                 attr="trig"):
                self._handle_trigger()
        if inputs.changed("clear"):
            if self._rising_edge(int(self._snap.get("clear") or 0),
                                 attr="clr"):
                self._handle_clear()

    def on_timer(self, timer):
        pass

    # ---- snapshot helpers ------------------------------------------------

    def _snap_from(self, inputs):
        for k in inputs.keys():
            self._snap[k] = inputs.value(k)

    def _cfg(self, key, default):
        v = self._snap.get(key)
        return v if (v is not None and v != "") else default

    # ---- edge detection / debounce --------------------------------------

    def _rising_edge(self, cur_val, attr):
        cur = 1 if cur_val else 0
        prev = self._last_trig_val if attr == "trig" else self._last_clr_val
        if attr == "trig":
            self._last_trig_val = cur
            store_val_id = "last_trig_val"
            store_ts_id = "last_trig_ts_ms"
            last_ts_attr = "_last_trig_ts_ms"
        else:
            self._last_clr_val = cur
            store_val_id = "last_clr_val"
            store_ts_id = "last_clr_ts_ms"
            last_ts_attr = "_last_clr_ts_ms"

        self.fw.run_in_context(self._persist_store, (store_val_id, cur))

        if cur and not prev:
            debounce_ms = int(self._cfg("debounce_ms", 1000))
            now_ms = int(time.time() * 1000)
            last_ms = getattr(self, last_ts_attr)
            if last_ms == 0 or (now_ms - last_ms) >= debounce_ms:
                setattr(self, last_ts_attr, now_ms or 1)
                self.fw.run_in_context(self._persist_store,
                                       (store_ts_id, now_ms or 1))
                return True
        return False

    # ---- payload + validation -------------------------------------------

    def _validate(self, alert_id, headline, description, template, duration,
                  payload_format="json"):
        # Per Airtame payload guidelines, description is optional.
        if not alert_id:
            return "alert_id is required"
        if not headline:
            return "headline is required"
        if len(headline) > MAX_HEADLINE_LEN:
            return "headline exceeds %d characters" % MAX_HEADLINE_LEN
        if description and len(description) > MAX_DESCRIPTION_LEN:
            return "description exceeds %d characters" % MAX_DESCRIPTION_LEN
        if template not in ALLOWED_TEMPLATES:
            return ("template must be one of: high, medium, low, blank, "
                    "all-clear, hold, secure, lockdown, evacuate, shelter")
        if duration <= 0:
            return "duration_seconds must be > 0"
        if payload_format not in ALLOWED_FORMATS:
            return "payload_format must be one of: json, cap"
        return ""

    def _iso8601_utc(self, epoch_s):
        return time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(epoch_s))

    def _build_trigger_body(self, alert_id, headline, description, template,
                            is_drill, duration):
        return json.dumps({
            "id": alert_id,
            "status": "Initiated",
            "template": template,
            "headline": headline,
            "description": description,
            "isDrill": bool(is_drill),
            "expiresAt": self._iso8601_utc(int(time.time()) + int(duration)),
        }, separators=(",", ":"))

    def _build_clear_body(self, alert_id):
        return json.dumps({"id": alert_id, "status": "Resolved"},
                          separators=(",", ":"))

    # ---- HTTP -----------------------------------------------------------

    def _mask(self, secret):
        if not secret: return ""
        n = len(secret)
        if n <= 4:     return "*" * n
        return secret[:2] + "*" * (n - 4) + secret[-2:]

    def _send_http_real(self, url, headers, body, timeout, max_retries):
        """Returns (status, body_text, error_tag) where error_tag is one of
        '', 'auth', 'rate-limit', 'server', 'timeout', 'transport'."""
        attempt = 0
        backoff = 1.0
        while attempt <= max_retries:
            try:
                resp = requests.post(url, data=body, headers=headers,
                                     timeout=timeout)
            except requests.Timeout:
                attempt += 1
                if attempt > max_retries:
                    return 0, "", "timeout"
                time.sleep(backoff); backoff *= 2
                continue
            except requests.RequestException as e:
                self.debug.log("transport error: %s" % e)
                return 0, "", "transport"
            text = resp.text[:500] if resp.text else ""
            sc = resp.status_code
            if 200 <= sc < 300:        return sc, text, ""
            if sc in (401, 403):       return sc, text, "auth"
            if sc == 429:
                attempt += 1
                if attempt > max_retries: return sc, text, "rate-limit"
                time.sleep(backoff); backoff *= 2
                continue
            if 500 <= sc < 600:
                attempt += 1
                if attempt > max_retries: return sc, text, "server"
                time.sleep(backoff); backoff *= 2
                continue
            return sc, text, "transport"
        return 0, "", "transport"

    # ---- trigger / clear ------------------------------------------------

    def _next_alert_id(self, prefix):
        self._counter += 1
        self.fw.run_in_context(self._persist_store, ("counter", self._counter))
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        return "%s-%s-%d" % (prefix, stamp, self._counter)

    def _handle_trigger(self):
        endpoint = self._cfg("api_endpoint", "https://airtame.cloud/api/v3.0/cloud/public/emergency-alerts")
        api_key  = self._cfg("api_key", "")
        prefix   = self._cfg("alert_id_prefix", "gira-hs")
        headline = self._cfg("headline", "Emergency")
        desc     = self._cfg("description", "Emergency alert from Gira HomeServer.")
        template = self._cfg("template", "high")
        is_drill = bool(int(self._cfg("is_drill", 0) or 0))
        duration = int(self._cfg("duration_seconds", 300) or 300)
        timeout  = int(self._cfg("timeout_seconds", 10) or 10)
        retries  = int(self._cfg("max_retries", 2) or 2)
        payload_format = (self._cfg("payload_format", "json") or "json").lower()
        sender_id    = self._cfg("sender_id", "gira-homeserver")
        cap_category = self._cfg("cap_category", "Safety")

        if not endpoint.startswith("https://"):
            self._fail(0, "config: endpoint must use HTTPS"); return
        if not api_key:
            self._fail(0, "config: api_key is required"); return

        alert_id = self._next_alert_id(prefix)
        vmsg = self._validate(alert_id, headline, desc, template, duration,
                              payload_format)
        if vmsg:
            self._fail(0, "validation: " + vmsg); return

        now_s = int(time.time())
        sent_iso = self._iso8601_utc(now_s)
        expires_iso = self._iso8601_utc(now_s + duration)

        if payload_format == "cap":
            body = build_cap_alert(alert_id, sender_id, sent_iso, headline,
                                   desc, template, is_drill, cap_category,
                                   expires_iso)
            content_type = "application/xml"
        else:
            body = self._build_trigger_body(alert_id, headline, desc, template,
                                            is_drill, duration)
            content_type = "application/json"

        headers = {
            "Authorization": "Basic " + base64.b64encode(
                ("gira:" + api_key).encode("utf-8")).decode("ascii"),
            "Content-Type": content_type,
            "Accept": "application/json",
        }
        # Remember the sent timestamp so a later CAP Cancel can reference it.
        self._active_sent_ts = sent_iso
        self.fw.run_in_context(self._persist_store, ("active_sent_ts", sent_iso))
        self.debug.log("trigger (%s) id=%s key=%s"
                       % (payload_format, alert_id, self._mask(api_key)))
        threading.Thread(target=self._do_send_trigger,
                         args=(endpoint, headers, body, timeout, retries, alert_id),
                         daemon=True).start()

    def _do_send_trigger(self, endpoint, headers, body, timeout, retries, alert_id):
        status, resp, err = self._send_http(endpoint, headers, body, timeout, retries)
        if err == "":
            self._active = True
            self._active_alert_id = alert_id
            self.fw.run_in_context(self._persist_active, (1, alert_id))
            self.fw.run_in_context(self._emit_outputs,
                                   (1, 1, 0, status, "alert initiated", alert_id))
            # pulse low
            self.fw.run_in_context(self._set_output_single,
                                   ("success_pulse", 0))
        else:
            self.fw.run_in_context(self._emit_outputs,
                                   (1 if self._active else 0, 0, 1, status,
                                    "HTTP %d (%s)" % (status, err) if status else err,
                                    self._active_alert_id))
            self.fw.run_in_context(self._set_output_single,
                                   ("error_pulse", 0))

    def _handle_clear(self):
        if not self._active or not self._active_alert_id:
            self.debug.log("clear ignored (no active alert)")
            return
        endpoint = self._cfg("api_endpoint", "")
        api_key  = self._cfg("api_key", "")
        timeout  = int(self._cfg("timeout_seconds", 10) or 10)
        retries  = int(self._cfg("max_retries", 2) or 2)
        payload_format = (self._cfg("payload_format", "json") or "json").lower()
        sender_id    = self._cfg("sender_id", "gira-homeserver")
        cap_category = self._cfg("cap_category", "Safety")
        is_drill = bool(int(self._cfg("is_drill", 0) or 0))
        prefix = self._cfg("alert_id_prefix", "gira-hs")
        if not endpoint.startswith("https://") or not api_key:
            self._fail(0, "config: endpoint/api_key invalid"); return

        if payload_format == "cap":
            cancel_id = self._next_alert_id(prefix + "-cancel")
            sent_iso = self._iso8601_utc(int(time.time()))
            template = self._cfg("template", "high")
            body = build_cap_cancel(cancel_id, sender_id, sent_iso,
                                    self._active_alert_id,
                                    self._active_sent_ts or "",
                                    cap_category, is_drill, template)
            content_type = "application/xml"
        else:
            body = self._build_clear_body(self._active_alert_id)
            content_type = "application/json"

        headers = {
            "Authorization": "Basic " + base64.b64encode(
                ("gira:" + api_key).encode("utf-8")).decode("ascii"),
            "Content-Type": content_type,
            "Accept": "application/json",
        }
        self.debug.log("clear (%s) id=%s"
                       % (payload_format, self._active_alert_id))
        threading.Thread(target=self._do_send_clear,
                         args=(endpoint, headers, body, timeout, retries),
                         daemon=True).start()

    def _do_send_clear(self, endpoint, headers, body, timeout, retries):
        status, resp, err = self._send_http(endpoint, headers, body, timeout, retries)
        if err == "":
            self._active = False
            self.fw.run_in_context(self._persist_active, (0, self._active_alert_id))
            self.fw.run_in_context(self._emit_outputs,
                                   (0, 1, 0, status, "alert resolved",
                                    self._active_alert_id))
            self.fw.run_in_context(self._set_output_single,
                                   ("success_pulse", 0))
        else:
            self.fw.run_in_context(self._emit_outputs,
                                   (1 if self._active else 0, 0, 1, status,
                                    "HTTP %d (%s)" % (status, err) if status else err,
                                    self._active_alert_id))
            self.fw.run_in_context(self._set_output_single,
                                   ("error_pulse", 0))

    def _fail(self, status, message):
        self.debug.log("FAIL: " + message)
        self.fw.run_in_context(self._emit_outputs,
                               (1 if self._active else 0, 0, 1, status, message,
                                self._active_alert_id))
        self.fw.run_in_context(self._set_output_single, ("error_pulse", 0))

    # ---- output helpers (must run in context thread) --------------------

    def _emit_outputs(self, active, success_pulse, error_pulse,
                      status_code, message, alert_id):
        self.fw.set_output("active", float(active))
        self.fw.set_output("success_pulse", float(success_pulse))
        self.fw.set_output("error_pulse", float(error_pulse))
        self.fw.set_output("last_status_code", float(status_code))
        self.fw.set_output("last_message", _enc(message))
        self.fw.set_output("last_alert_id", _enc(alert_id))

    def _set_output_single(self, identifier, value):
        # HSL3 spec: string outputs are bytes (iso-8859-15); numbers are floats.
        if isinstance(value, str):
            self.fw.set_output(identifier, _enc(value))
        else:
            self.fw.set_output(identifier, float(value))

    def _persist_store(self, identifier, value):
        self.fw.set_store(identifier, value if isinstance(value, str) else float(value))

    def _persist_active(self, active, alert_id):
        self.fw.set_store("active", float(active))
        self.fw.set_store("active_alert_id", alert_id)


def _enc(s):
    if s is None:
        return b""
    if isinstance(s, bytes):
        return s
    return s.encode("iso-8859-15", "replace")
