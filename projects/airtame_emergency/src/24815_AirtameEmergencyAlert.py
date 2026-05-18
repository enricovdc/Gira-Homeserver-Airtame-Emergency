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

########################################################################################################
#### Own written code can be placed after this commentblock . Do not change or delete commentblock! ####
#################################################################################################!!!##

    ALLOWED_TEMPLATES = ("high", "medium", "low")
    MAX_HEADLINE_LEN = 200
    MAX_DESCRIPTION_LEN = 2000

    def on_init(self):
        active = int(self.FRAMEWORK._get_remanent(self.REM_ACTIVE) or 0)
        self.FRAMEWORK._set_output_value(self.PIN_O_ACTIVE, 1 if active else 0)
        self.FRAMEWORK._set_output_value(self.PIN_O_SUCCESS_PULSE, 0)
        self.FRAMEWORK._set_output_value(self.PIN_O_ERROR_PULSE, 0)
        self.FRAMEWORK._set_output_value(self.PIN_O_LAST_STATUS_CODE, 0)
        self.FRAMEWORK._set_output_value(self.PIN_O_LAST_MESSAGE, "")
        self.FRAMEWORK._set_output_value(
            self.PIN_O_LAST_ALERT_ID,
            self.FRAMEWORK._get_remanent(self.REM_ACTIVE_ALERT_ID) or "",
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
        v = self.FRAMEWORK._get_input_value(pin)
        if v is None:
            return ""
        return v if isinstance(v, str) else str(v)

    def _pin_int(self, pin, default=0):
        v = self.FRAMEWORK._get_input_value(pin)
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
        return (headline, description, template, is_drill, duration,
                endpoint, api_key, prefix, timeout, retries, debounce)

    # ------- edge detection / debounce ------------------------------------

    def _rising_edge(self, value, prev_rem, ts_rem):
        cur = 1 if (value and int(value) != 0) else 0
        prev = int(self.FRAMEWORK._get_remanent(prev_rem) or 0)
        self.FRAMEWORK._set_remanent(prev_rem, cur)
        if cur and not prev:
            (_, _, _, _, _, _, _, _, _, _, debounce_ms) = self._config()
            now_ms = int(time.time() * 1000)
            last_ms = int(self.FRAMEWORK._get_remanent(ts_rem) or 0)
            # last_ms==0 means "never fired"; bypass debounce for the first edge.
            if last_ms == 0 or (now_ms - last_ms) >= debounce_ms:
                self.FRAMEWORK._set_remanent(ts_rem, now_ms or 1)
                return True
        return False

    # ------- payload + validation -----------------------------------------

    def _validate(self, alert_id, headline, description, template, duration):
        if not alert_id:
            return "alert_id is required"
        if not headline:
            return "headline is required"
        if not description:
            return "description is required"
        if len(headline) > self.MAX_HEADLINE_LEN:
            return "headline exceeds %d characters" % self.MAX_HEADLINE_LEN
        if len(description) > self.MAX_DESCRIPTION_LEN:
            return "description exceeds %d characters" % self.MAX_DESCRIPTION_LEN
        if template not in self.ALLOWED_TEMPLATES:
            return "template must be one of: high, medium, low"
        if duration <= 0:
            return "duration_seconds must be > 0"
        return ""

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

    def _send(self, body_json, endpoint, api_key, timeout_s, max_retries):
        if not endpoint.startswith("https://"):
            return 0, "", "config-endpoint"
        if not api_key:
            return 0, "", "config-key"
        headers = {
            "Authorization": self._basic_auth(api_key),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
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
        counter = int(self.FRAMEWORK._get_remanent(self.REM_COUNTER) or 0) + 1
        self.FRAMEWORK._set_remanent(self.REM_COUNTER, counter)
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        return "%s-%s-%d" % (prefix, stamp, counter)

    def _handle_trigger(self):
        (headline, description, template, is_drill, duration,
         endpoint, api_key, prefix, timeout, retries, _debounce) = self._config()

        alert_id = self._next_alert_id(prefix)
        msg = self._validate(alert_id, headline, description, template, duration)
        if msg:
            self._fail(0, "validation: " + msg)
            return

        body = self._build_trigger_body(alert_id, headline, description,
                                        template, is_drill, duration)
        self.LOGGER.info(0, "[airtame] trigger id=%s key=%s"
                         % (alert_id, self._mask(api_key)))
        status, resp, err = self._send(body, endpoint, api_key, timeout, retries)
        if err == "":
            self.FRAMEWORK._set_remanent(self.REM_ACTIVE, 1)
            self.FRAMEWORK._set_remanent(self.REM_ACTIVE_ALERT_ID, alert_id)
            self.FRAMEWORK._set_output_value(self.PIN_O_ACTIVE, 1)
            self.FRAMEWORK._set_output_value(self.PIN_O_LAST_STATUS_CODE, status)
            self.FRAMEWORK._set_output_value(self.PIN_O_LAST_ALERT_ID, alert_id)
            self.FRAMEWORK._set_output_value(self.PIN_O_LAST_MESSAGE,
                                             "alert initiated")
            self._pulse(self.PIN_O_SUCCESS_PULSE)
        elif err in ("config-endpoint", "config-key"):
            self._fail(0, "config: " + err)
        else:
            self._fail(status, "HTTP %d (%s)" % (status, err))

    def _handle_clear(self):
        (_h, _d, _t, _i, _du,
         endpoint, api_key, _p, timeout, retries, _deb) = self._config()
        active = int(self.FRAMEWORK._get_remanent(self.REM_ACTIVE) or 0)
        alert_id = self.FRAMEWORK._get_remanent(self.REM_ACTIVE_ALERT_ID) or ""
        if not active or not alert_id:
            self.LOGGER.info(0, "[airtame] clear ignored (no active alert)")
            return

        body = self._build_clear_body(alert_id)
        self.LOGGER.info(0, "[airtame] clear id=" + alert_id)
        status, resp, err = self._send(body, endpoint, api_key, timeout, retries)
        if err == "":
            self.FRAMEWORK._set_remanent(self.REM_ACTIVE, 0)
            self.FRAMEWORK._set_output_value(self.PIN_O_ACTIVE, 0)
            self.FRAMEWORK._set_output_value(self.PIN_O_LAST_STATUS_CODE, status)
            self.FRAMEWORK._set_output_value(self.PIN_O_LAST_MESSAGE,
                                             "alert resolved")
            self._pulse(self.PIN_O_SUCCESS_PULSE)
        elif err in ("config-endpoint", "config-key"):
            self._fail(0, "config: " + err)
        else:
            self._fail(status, "HTTP %d (%s)" % (status, err))

    def _pulse(self, pin):
        self.FRAMEWORK._set_output_value(pin, 1)
        self.FRAMEWORK._set_output_value(pin, 0)

    def _fail(self, status, message):
        self.LOGGER.error(0, "[airtame] " + message)
        self.FRAMEWORK._set_output_value(self.PIN_O_LAST_STATUS_CODE, status)
        self.FRAMEWORK._set_output_value(self.PIN_O_LAST_MESSAGE, message)
        self._pulse(self.PIN_O_ERROR_PULSE)
