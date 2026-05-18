# coding: UTF-8
# Airtame Emergency Alert - LBS 24815
#
# Authored against the Gira HSL2 SDK 2.0.7 framework. Run
#   python generator.pyc "airtame_emergency" UTF-8
# from inside the SDK's framework directory to produce
# projects/airtame_emergency/release/24815_AirtameEmergencyAlert.hsl.
#
# At deploy time hsl20_4 is injected into the enclosing scope by the
# generator's inlined framework block. The try/import below is only here so
# this file is importable by pytest in src/ (the tests stub hsl20_4).
try:
    import hsl20_4
except ImportError:
    pass

import base64
import json
import time
import re

try:
    # Python 2 (Gira HS runtime).
    from urllib2 import Request, urlopen, HTTPError, URLError
except ImportError:
    # Python 3 (pytest).
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError

##!!!!####################################################################################################
#### Own written code can be placed above this commentblock . Do not change or delete commentblock! ####
########################################################################################################
##** Code created by generator - DO NOT CHANGE! **##

class AirtameEmergencyAlert24815(hsl20_4.BaseModule):

    def __init__(self, homeserver_context):
        hsl20_4.BaseModule.__init__(self, homeserver_context, "airtame_emergency")
        self.FRAMEWORK = self._get_framework()
        self.LOGGER = self._get_logger(hsl20_4.LOGGING_NONE,())
        self.PIN_I_TRIGGER=1
        self.PIN_I_CLEAR=2
        self.PIN_I_HEADLINE=3
        self.PIN_I_DESCRIPTION=4
        self.PIN_I_TEMPLATE=5
        self.PIN_I_IS_DRILL=6
        self.PIN_I_DURATION_SECONDS=7
        self.PIN_I_API_ENDPOINT=8
        self.PIN_I_API_KEY=9
        self.PIN_I_ALERT_ID_PREFIX=10
        self.PIN_I_TIMEOUT_SECONDS=11
        self.PIN_I_MAX_RETRIES=12
        self.PIN_I_DEBOUNCE_MS=13
        self.PIN_O_ACTIVE=1
        self.PIN_O_SUCCESS_PULSE=2
        self.PIN_O_ERROR_PULSE=3
        self.PIN_O_LAST_STATUS_CODE=4
        self.PIN_O_LAST_MESSAGE=5
        self.PIN_O_LAST_ALERT_ID=6
        self.REM_ACTIVE=1
        self.REM_ACTIVE_ALERT_ID=2
        self.REM_COUNTER=3
        self.REM_LAST_TRIG_VAL=4
        self.REM_LAST_TRIG_TS_MS=5
        self.REM_LAST_CLR_VAL=6
        self.REM_LAST_CLR_TS_MS=7
        self.REM_ACTIVE_SENT_TS=8
        self.PIN_I_PAYLOAD_FORMAT=14
        self.PIN_I_SENDER_ID=15
        self.PIN_I_CAP_CATEGORY=16

########################################################################################################
#### Own written code can be placed after this commentblock . Do not change or delete commentblock! ####
#################################################################################################!!!##

    # Airtame AlertTemplate values (Emergency Alerts payload guidelines).
    # The first three are also reachable via CAP <urgency>; the rest are
    # JSON-only because CAP routes templates exclusively through <urgency>.
    ALLOWED_TEMPLATES = (
        "high", "medium", "low",
        "blank", "all-clear", "hold",
        "secure", "lockdown", "evacuate", "shelter",
    )
    CAP_REACHABLE_TEMPLATES = ("high", "medium", "low")
    ALLOWED_FORMATS = ("json", "cap")
    MAX_HEADLINE_LEN = 200
    MAX_DESCRIPTION_LEN = 2000
    CAP_NS = "urn:oasis:names:tc:emergency:cap:1.2"
    # Airtame derives template selection from CAP <urgency>, not <severity>.
    # Mapping is one-way and lossy: the seven SRP templates can only be
    # selected by sending JSON. When a CAP-incompatible template is asked
    # for in CAP mode, the module degrades urgency to the closest of
    # Immediate / Expected / Future.
    TEMPLATE_TO_URGENCY = {
        "high": "Immediate", "lockdown": "Immediate", "evacuate": "Immediate",
        "shelter": "Immediate", "secure": "Immediate",
        "medium": "Expected", "hold": "Expected",
        "low": "Future", "all-clear": "Future", "blank": "Future",
    }
    SEVERITY_DEFAULT = "Severe"
    SEVERITY_DRILL = "Minor"

    def on_init(self):
        active = int(self._get_remanent(self.REM_ACTIVE) or 0)
        self._set_output_value(self.PIN_O_ACTIVE, 1 if active else 0)
        self._set_output_value(self.PIN_O_SUCCESS_PULSE, 0)
        self._set_output_value(self.PIN_O_ERROR_PULSE, 0)
        self._set_output_value(self.PIN_O_LAST_STATUS_CODE, 0)
        self._set_output_value(self.PIN_O_LAST_MESSAGE, "")
        self._set_output_value(
            self.PIN_O_LAST_ALERT_ID,
            self._get_remanent(self.REM_ACTIVE_ALERT_ID) or "",
        )

    def on_input_value(self, index, value):
        try:
            if index == self.PIN_I_TRIGGER:
                if self._rising_edge(value, self.REM_LAST_TRIG_VAL,
                                     self.REM_LAST_TRIG_TS_MS):
                    self._handle_trigger()
            elif index == self.PIN_I_CLEAR:
                if self._rising_edge(value, self.REM_LAST_CLR_VAL,
                                     self.REM_LAST_CLR_TS_MS):
                    self._handle_clear()
        except Exception as e:
            self._fail(0, "internal: " + str(e))

    # ------- input / config readers ---------------------------------------

    def _pin_str(self, pin):
        v = self._get_input_value(pin)
        if v is None:
            return ""
        return v if isinstance(v, str) else str(v)

    def _pin_int(self, pin, default=0):
        v = self._get_input_value(pin)
        try:
            return int(v)
        except (TypeError, ValueError):
            return default

    def _config(self):
        headline = self._pin_str(self.PIN_I_HEADLINE) or "Emergency"
        description = (self._pin_str(self.PIN_I_DESCRIPTION)
                       or "Emergency alert from Gira HomeServer.")
        template = self._pin_str(self.PIN_I_TEMPLATE) or "high"
        is_drill = bool(self._pin_int(self.PIN_I_IS_DRILL, 0))
        duration = self._pin_int(self.PIN_I_DURATION_SECONDS, 300)
        endpoint = (self._pin_str(self.PIN_I_API_ENDPOINT)
                    or "https://airtame.cloud/api/v3.0/cloud/public/emergency-alerts")
        api_key = self._pin_str(self.PIN_I_API_KEY)
        prefix = self._pin_str(self.PIN_I_ALERT_ID_PREFIX) or "gira-hs"
        timeout = self._pin_int(self.PIN_I_TIMEOUT_SECONDS, 10)
        retries = self._pin_int(self.PIN_I_MAX_RETRIES, 2)
        debounce = self._pin_int(self.PIN_I_DEBOUNCE_MS, 1000)
        payload_format = (self._pin_str(self.PIN_I_PAYLOAD_FORMAT) or "json").lower()
        sender_id = self._pin_str(self.PIN_I_SENDER_ID) or "gira-homeserver"
        cap_category = self._pin_str(self.PIN_I_CAP_CATEGORY) or "Safety"
        return (headline, description, template, is_drill, duration,
                endpoint, api_key, prefix, timeout, retries, debounce,
                payload_format, sender_id, cap_category)

    # ------- edge detection / debounce ------------------------------------

    def _rising_edge(self, value, prev_rem, ts_rem):
        cur = 1 if (value and int(value) != 0) else 0
        prev = int(self._get_remanent(prev_rem) or 0)
        self._set_remanent(prev_rem, cur)
        if cur and not prev:
            cfg = self._config()
            debounce_ms = cfg[10]
            now_ms = int(time.time() * 1000)
            last_ms = int(self._get_remanent(ts_rem) or 0)
            # last_ms==0 means "never fired"; bypass debounce for the first edge.
            if last_ms == 0 or (now_ms - last_ms) >= debounce_ms:
                self._set_remanent(ts_rem, now_ms or 1)
                return True
        return False

    # ------- payload + validation -----------------------------------------

    def _validate(self, alert_id, headline, description, template, duration,
                  payload_format="json"):
        # Per Airtame payload guidelines, "description" is optional - only
        # id / status / template / headline are required for JSON.
        if not alert_id:
            return "alert_id is required"
        if not headline:
            return "headline is required"
        if len(headline) > self.MAX_HEADLINE_LEN:
            return "headline exceeds %d characters" % self.MAX_HEADLINE_LEN
        if description and len(description) > self.MAX_DESCRIPTION_LEN:
            return "description exceeds %d characters" % self.MAX_DESCRIPTION_LEN
        if template not in self.ALLOWED_TEMPLATES:
            return ("template must be one of: high, medium, low, blank, "
                    "all-clear, hold, secure, lockdown, evacuate, shelter")
        if duration <= 0:
            return "duration_seconds must be > 0"
        if payload_format not in self.ALLOWED_FORMATS:
            return "payload_format must be one of: json, cap"
        return ""

    # ------- CAP 1.2 XML payload ------------------------------------------

    def _xml_escape(self, s):
        # Escape the five XML-reserved characters. ElementTree.tostring would
        # do this for us, but staying with hand-rolled strings keeps the byte
        # output deterministic and free of namespace-prefix surprises.
        if s is None:
            return ""
        s = str(s)
        return (s.replace("&", "&amp;")
                 .replace("<", "&lt;")
                 .replace(">", "&gt;")
                 .replace("\"", "&quot;")
                 .replace("'", "&apos;"))

    def _build_cap_alert(self, alert_id, sender_id, sent_iso, headline,
                         description, template, is_drill, duration_s,
                         category, expires_iso):
        # Airtame's CAP sample maps <event> to the short template-like tag
        # ("Lockdown" in the example, not the headline). Match that shape.
        urgency = self.TEMPLATE_TO_URGENCY.get(template, "Immediate")
        severity = self.SEVERITY_DRILL if is_drill else self.SEVERITY_DEFAULT
        # Airtame's published sample uses <status>Actual</status> for both
        # real alerts and (implicitly) drills - the CAP "Test" value means
        # "transport test, recipients must disregard" so it'd be dropped.
        # Drills are flagged in JSON via isDrill; in CAP we have no equivalent.
        status = "Actual"
        event_short = template.capitalize() if template else "Emergency"
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<alert xmlns="' + self.CAP_NS + '">'
            '<identifier>' + self._xml_escape(alert_id) + '</identifier>'
            '<sender>' + self._xml_escape(sender_id) + '</sender>'
            '<sent>' + sent_iso + '</sent>'
            '<status>' + status + '</status>'
            '<msgType>Alert</msgType>'
            '<scope>Public</scope>'
            '<info>'
            '<category>' + self._xml_escape(category) + '</category>'
            '<event>' + self._xml_escape(event_short) + '</event>'
            '<urgency>' + urgency + '</urgency>'
            '<severity>' + severity + '</severity>'
            '<certainty>Observed</certainty>'
            '<senderName>' + self._xml_escape(sender_id) + '</senderName>'
            '<headline>' + self._xml_escape(headline) + '</headline>'
            '<description>' + self._xml_escape(description or "") + '</description>'
            '<expires>' + expires_iso + '</expires>'
            '</info>'
            '</alert>'
        )

    def _build_cap_cancel(self, cancel_id, sender_id, cancel_sent_iso,
                          original_id, original_sent_iso, category, is_drill,
                          template="high"):
        # Per Airtame's published Stop-an-alert sample, the Cancel mirrors
        # the original alert's urgency/severity/certainty rather than
        # degrading to Past/Unknown/Unknown.
        urgency = self.TEMPLATE_TO_URGENCY.get(template, "Immediate")
        severity = self.SEVERITY_DRILL if is_drill else self.SEVERITY_DEFAULT
        status = "Actual"
        references = "%s,%s,%s" % (sender_id, original_id, original_sent_iso)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<alert xmlns="' + self.CAP_NS + '">'
            '<identifier>' + self._xml_escape(cancel_id) + '</identifier>'
            '<sender>' + self._xml_escape(sender_id) + '</sender>'
            '<sent>' + cancel_sent_iso + '</sent>'
            '<status>' + status + '</status>'
            '<msgType>Cancel</msgType>'
            '<scope>Public</scope>'
            '<references>' + self._xml_escape(references) + '</references>'
            '<info>'
            '<category>' + self._xml_escape(category) + '</category>'
            '<event></event>'
            '<urgency>' + urgency + '</urgency>'
            '<severity>' + severity + '</severity>'
            '<certainty>Observed</certainty>'
            '<senderName>' + self._xml_escape(sender_id) + '</senderName>'
            '<headline></headline>'
            '<description></description>'
            '</info>'
            '</alert>'
        )

    def _iso8601_utc(self, epoch_s):
        return time.strftime("%Y-%m-%dT%H:%M:%S+00:00",
                             time.gmtime(epoch_s))

    def _build_trigger_body(self, alert_id, headline, description, template,
                            is_drill, duration):
        payload = {
            "id": alert_id,
            "status": "Initiated",
            "template": template,
            "headline": headline,
            "description": description,
            "isDrill": bool(is_drill),
            "expiresAt": self._iso8601_utc(int(time.time()) + int(duration)),
        }
        return json.dumps(payload, separators=(",", ":"))

    def _build_clear_body(self, alert_id):
        return json.dumps({"id": alert_id, "status": "Resolved"},
                          separators=(",", ":"))

    # ------- HTTP ---------------------------------------------------------

    def _mask(self, secret):
        if not secret:
            return ""
        n = len(secret)
        if n <= 4:
            return "*" * n
        return secret[:2] + "*" * (n - 4) + secret[-2:]

    def _basic_auth(self, api_key):
        raw = ("gira:" + api_key).encode("utf-8")
        return "Basic " + base64.b64encode(raw).decode("ascii")

    def _http_post(self, url, headers, body, timeout):
        # Overridable seam: tests monkeypatch this method on the instance
        # to avoid real network IO. Returns (status_code, body_text)
        # or raises URLError on transport failure / timeout.
        req = Request(url=url, data=body.encode("utf-8"))
        req.get_method = lambda: "POST"
        for k, v in headers.items():
            req.add_header(k, v)
        try:
            resp = urlopen(req, timeout=timeout)
            return resp.getcode(), resp.read().decode("utf-8", "replace")
        except HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")

    def _send(self, body, endpoint, api_key, timeout_s, max_retries,
              content_type="application/json"):
        if not endpoint.startswith("https://"):
            return 0, "", "config-endpoint"
        if not api_key:
            return 0, "", "config-key"
        headers = {
            "Authorization": self._basic_auth(api_key),
            "Content-Type": content_type,
            "Accept": "application/json",
        }
        body_json = body  # name retained for the rest of the method below
        attempt = 0
        backoff = 1.0
        while attempt <= max_retries:
            try:
                status, resp_body = self._http_post(
                    endpoint, headers, body_json, timeout_s)
            except URLError as e:
                attempt += 1
                if attempt > max_retries:
                    return 0, "", "timeout"
                time.sleep(backoff)
                backoff *= 2
                continue
            if len(resp_body) > 500:
                resp_body = resp_body[:500]
            if 200 <= status < 300:
                return status, resp_body, ""
            if status in (401, 403):
                return status, resp_body, "auth"
            if status == 429:
                attempt += 1
                if attempt > max_retries:
                    return status, resp_body, "rate-limit"
                time.sleep(backoff)
                backoff *= 2
                continue
            if 500 <= status < 600:
                attempt += 1
                if attempt > max_retries:
                    return status, resp_body, "server"
                time.sleep(backoff)
                backoff *= 2
                continue
            return status, resp_body, "transport"
        return 0, "", "transport"

    # ------- trigger / clear handlers -------------------------------------

    def _next_alert_id(self, prefix):
        counter = int(self._get_remanent(self.REM_COUNTER) or 0) + 1
        self._set_remanent(self.REM_COUNTER, counter)
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        return "%s-%s-%d" % (prefix, stamp, counter)

    def _handle_trigger(self):
        cfg = self._config()
        (headline, description, template, is_drill, duration,
         endpoint, api_key, prefix, timeout, retries, _debounce,
         payload_format, sender_id, cap_category) = cfg

        alert_id = self._next_alert_id(prefix)
        msg = self._validate(alert_id, headline, description, template,
                             duration, payload_format)
        if msg:
            self._fail(0, "validation: " + msg)
            return

        now_s = int(time.time())
        sent_iso = self._iso8601_utc(now_s)
        expires_iso = self._iso8601_utc(now_s + int(duration))

        if payload_format == "cap":
            body = self._build_cap_alert(alert_id, sender_id, sent_iso,
                                         headline, description, template,
                                         is_drill, duration, cap_category,
                                         expires_iso)
            content_type = "application/xml"
        else:
            body = self._build_trigger_body(alert_id, headline, description,
                                            template, is_drill, duration)
            content_type = "application/json"

        self.LOGGER.info(0, "[airtame] trigger (%s) id=%s key=%s"
                         % (payload_format, alert_id, self._mask(api_key)))
        status, resp, err = self._send(body, endpoint, api_key, timeout,
                                       retries, content_type=content_type)
        if err == "":
            self._set_remanent(self.REM_ACTIVE, 1)
            self._set_remanent(self.REM_ACTIVE_ALERT_ID, alert_id)
            self._set_remanent(self.REM_ACTIVE_SENT_TS, sent_iso)
            self._set_output_value(self.PIN_O_ACTIVE, 1)
            self._set_output_value(self.PIN_O_LAST_STATUS_CODE, status)
            self._set_output_value(self.PIN_O_LAST_ALERT_ID, alert_id)
            self._set_output_value(self.PIN_O_LAST_MESSAGE, "alert initiated")
            self._pulse(self.PIN_O_SUCCESS_PULSE)
        elif err in ("config-endpoint", "config-key"):
            self._fail(0, "config: " + err)
        else:
            self._fail(status, "HTTP %d (%s)" % (status, err))

    def _handle_clear(self):
        cfg = self._config()
        (_h, _d, template, is_drill, _du,
         endpoint, api_key, prefix, timeout, retries, _deb,
         payload_format, sender_id, cap_category) = cfg
        active = int(self._get_remanent(self.REM_ACTIVE) or 0)
        alert_id = self._get_remanent(self.REM_ACTIVE_ALERT_ID) or ""
        original_sent_iso = self._get_remanent(self.REM_ACTIVE_SENT_TS) or ""
        if not active or not alert_id:
            self.LOGGER.info(0, "[airtame] clear ignored (no active alert)")
            return

        if payload_format == "cap":
            cancel_id = self._next_alert_id(prefix + "-cancel")
            sent_iso = self._iso8601_utc(int(time.time()))
            body = self._build_cap_cancel(cancel_id, sender_id, sent_iso,
                                          alert_id, original_sent_iso,
                                          cap_category, is_drill, template)
            content_type = "application/xml"
        else:
            body = self._build_clear_body(alert_id)
            content_type = "application/json"

        self.LOGGER.info(0, "[airtame] clear (%s) id=%s"
                         % (payload_format, alert_id))
        status, resp, err = self._send(body, endpoint, api_key, timeout,
                                       retries, content_type=content_type)
        if err == "":
            self._set_remanent(self.REM_ACTIVE, 0)
            self._set_output_value(self.PIN_O_ACTIVE, 0)
            self._set_output_value(self.PIN_O_LAST_STATUS_CODE, status)
            self._set_output_value(self.PIN_O_LAST_MESSAGE, "alert resolved")
            self._pulse(self.PIN_O_SUCCESS_PULSE)
        elif err in ("config-endpoint", "config-key"):
            self._fail(0, "config: " + err)
        else:
            self._fail(status, "HTTP %d (%s)" % (status, err))

    def _pulse(self, pin):
        self._set_output_value(pin, 1)
        self._set_output_value(pin, 0)

    def _fail(self, status, message):
        self.LOGGER.error(0, "[airtame] " + message)
        self._set_output_value(self.PIN_O_LAST_STATUS_CODE, status)
        self._set_output_value(self.PIN_O_LAST_MESSAGE, message)
        self._pulse(self.PIN_O_ERROR_PULSE)
