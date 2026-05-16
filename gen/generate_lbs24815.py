"""Generator input for the Gira Experte 4.13 HSL logic-module generator.

This file is the single source of truth for the "Airtame Emergency Alert"
module. Two ways to use it:

  1. Feed it into the HSL generator script bundled with Gira Experte 4.13.
     The top-of-file constants (LBS_NUMBER, LBS_NAME, PARAMETERS, INPUTS,
     OUTPUTS, HSL_BODY) are laid out so they can be consumed by a generator
     that imports this module or scrapes it. If your generator expects
     different constant names, rename them here - the values are unchanged.

  2. Run this file directly:        python3 gen/generate_lbs24815.py
     It will emit dist/lbs24815.hsl using a best-effort header dialect
     (described in docs/deployment.md). Use this only as a fallback if
     the Gira generator is unavailable; the canonical .hsl is whatever
     Gira's generator produces from this same configuration.

The algorithmic content of HSL_BODY is mirrored by the Python reference in
``reference/`` and is covered by the pytest suite in ``tests/``.
"""
from __future__ import annotations

import sys
from pathlib import Path
from textwrap import dedent

# =============================================================================
# Module metadata
# =============================================================================

LBS_NUMBER  = 24815
LBS_NAME    = "Airtame Emergency Alert"
LBS_VERSION = "0.1.0"
LBS_VENDOR  = "Internal"
LBS_HELP    = (
    "Triggers and clears Airtame Emergency Alerts via the Airtame Cloud "
    "public emergency-alerts API. Use this module to display emergency "
    "signage on Airtame screens in response to KNX/Gira events. "
    "LBS number 24815 is a placeholder in the third-party range (20000-99999); "
    "reserve a number on hs-help.net before publishing."
)

# =============================================================================
# Pins
# -----------------------------------------------------------------------------
# Order in these lists is the pin index Experte assigns (1-based).
# Types are the names Experte's generator uses: bool, int, string, password,
# enum. Keep "default" as the literal value the generator should serialize.
# =============================================================================

PARAMETERS = [
    {
        "name": "api_endpoint",
        "label": "API endpoint",
        "type": "string",
        "default": "https://airtame.cloud/api/v3.0/cloud/public/emergency-alerts",
        "help": "Airtame Emergency Alerts endpoint. Must be HTTPS.",
    },
    {
        "name": "api_key",
        "label": "API key",
        "type": "password",
        "default": "",
        "help": "Airtame Cloud API key. Sent as HTTP Basic auth password.",
    },
    {
        "name": "alert_id_prefix",
        "label": "Alert id prefix",
        "type": "string",
        "default": "gira-hs",
        "help": "Prefix used to construct unique alert ids.",
    },
    {
        "name": "default_headline",
        "label": "Default headline",
        "type": "string",
        "default": "Emergency",
    },
    {
        "name": "default_description",
        "label": "Default description",
        "type": "string",
        "default": "Emergency alert triggered from Gira HomeServer.",
    },
    {
        "name": "default_template",
        "label": "Default template",
        "type": "enum",
        "options": ["high", "medium", "low"],
        "default": "high",
    },
    {
        "name": "default_is_drill",
        "label": "Default is-drill",
        "type": "bool",
        "default": False,
    },
    {
        "name": "default_duration_seconds",
        "label": "Default duration (s)",
        "type": "int",
        "default": 300,
        "min": 10,
        "max": 86400,
    },
    {
        "name": "timeout_seconds",
        "label": "HTTP timeout (s)",
        "type": "int",
        "default": 10,
        "min": 1,
        "max": 60,
    },
    {
        "name": "max_retries",
        "label": "Max retries",
        "type": "int",
        "default": 2,
        "min": 0,
        "max": 5,
    },
    {
        "name": "debounce_ms",
        "label": "Debounce (ms)",
        "type": "int",
        "default": 1000,
        "min": 0,
        "max": 60000,
        "help": "Minimum interval between accepted rising edges.",
    },
]

INPUTS = [
    {"name": "trigger",          "type": "bool",   "help": "Rising edge sends an Initiated alert."},
    {"name": "clear",            "type": "bool",   "help": "Rising edge sends a Resolved alert for the active id."},
    {"name": "headline",         "type": "string", "optional": True, "help": "Optional override of default_headline."},
    {"name": "description",      "type": "string", "optional": True, "help": "Optional override of default_description."},
    {"name": "template",         "type": "string", "optional": True, "help": "Optional override of default_template (high|medium|low)."},
    {"name": "is_drill",         "type": "bool",   "optional": True, "help": "Optional override of default_is_drill."},
    {"name": "duration_seconds", "type": "int",    "optional": True, "help": "Optional override of default_duration_seconds."},
]

OUTPUTS = [
    {"name": "active",           "type": "bool",   "help": "True while the last initiated alert has not been resolved."},
    {"name": "success_pulse",    "type": "bool",   "help": "Pulses high for one cycle after a successful 2xx response."},
    {"name": "error_pulse",      "type": "bool",   "help": "Pulses high for one cycle on validation or HTTP failure."},
    {"name": "last_status_code", "type": "int",    "help": "HTTP status code from the last request (0 = transport error)."},
    {"name": "last_message",     "type": "string", "help": "Short human-readable result or error message."},
    {"name": "last_alert_id",    "type": "string", "help": "ID assigned to the most recent initiated alert."},
]

# =============================================================================
# HSL body
# -----------------------------------------------------------------------------
# Single self-contained block that the generator should drop under the LBS
# header it produces. No #includes. The body assumes the generator has
# already declared variables backing PARAM[...], INPUT[...], OUTPUT[...]
# according to the lists above; reference them by their declared names.
#
# Algorithmic behavior is pinned by reference/airtame_*.py + tests/.
# =============================================================================

HSL_BODY = dedent(r"""
    // =========================================================================
    // Airtame Emergency Alert - LBS 24815 - logic body
    // Wire protocol pinned by reference/airtame_payload.py and tests/.
    // =========================================================================

    // ----- Module-scope state populated by airtame_send() --------------------
    int    airtame_last_status = 0;
    string airtame_last_body   = "";
    string airtame_last_error  = "";

    // ----- Helpers -----------------------------------------------------------
    function string json_escape(string s) {
        string out = "";
        int i = 0;
        int n = strlen(s);
        while (i < n) {
            string c = substr(s, i, 1);
            if      (c == "\"") { out = out + "\\\""; }
            else if (c == "\\") { out = out + "\\\\"; }
            else if (c == "\n") { out = out + "\\n";  }
            else if (c == "\r") { out = out + "\\r";  }
            else if (c == "\t") { out = out + "\\t";  }
            else if (c == "\b") { out = out + "\\b";  }
            else if (c == "\f") { out = out + "\\f";  }
            else                { out = out + c;      }
            i = i + 1;
        }
        return out;
    }

    function string iso8601_utc(int epoch_seconds) {
        return system.strftime("%Y-%m-%dT%H:%M:%S+00:00", epoch_seconds);
    }

    function string mask_secret(string secret) {
        int n = strlen(secret);
        if (n == 0) { return ""; }
        if (n <= 4) {
            string r = "";
            int i = 0;
            while (i < n) { r = r + "*"; i = i + 1; }
            return r;
        }
        return substr(secret, 0, 2) + "****" + substr(secret, n - 2, 2);
    }

    function bool edge_rising(bool value, string state_key, int debounce_ms) {
        string prev_key = "edge_prev_" + state_key;
        string last_key = "edge_last_" + state_key;
        int now_ms = system.gettime_ms();
        int prev   = system.getval(prev_key, 0);
        int last   = system.getval(last_key, -1000000000);
        bool rose  = (value && prev == 0);
        system.setval(prev_key, value ? 1 : 0);
        if (rose && (now_ms - last) >= debounce_ms) {
            system.setval(last_key, now_ms);
            return true;
        }
        return false;
    }

    function void log_info(string scope, string msg) {
        system.trace("[airtame] " + scope + ": " + msg);
    }

    function void log_error(string scope, string msg) {
        system.trace("[airtame][ERROR] " + scope + ": " + msg);
    }

    // ----- Payload builder ---------------------------------------------------
    function string validate_alert(string alert_id, string headline,
                                   string description, string template,
                                   int duration_seconds) {
        if (strlen(alert_id) == 0)      { return "alert_id is required"; }
        if (strlen(headline) == 0)      { return "headline is required"; }
        if (strlen(description) == 0)   { return "description is required"; }
        if (strlen(headline) > 200)     { return "headline exceeds 200 characters"; }
        if (strlen(description) > 2000) { return "description exceeds 2000 characters"; }
        if (template != "high" && template != "medium" && template != "low") {
            return "template must be one of: high, medium, low";
        }
        if (duration_seconds <= 0) { return "duration_seconds must be > 0"; }
        return "";
    }

    function string build_trigger_payload(string alert_id, string headline,
                                          string description, string template,
                                          bool is_drill, int duration_seconds) {
        int    now_s   = system.time();
        string expires = iso8601_utc(now_s + duration_seconds);
        string drill_s = is_drill ? "true" : "false";
        return "{"
            + "\"id\":\""          + json_escape(alert_id)    + "\","
            + "\"status\":\"Initiated\","
            + "\"template\":\""    + json_escape(template)    + "\","
            + "\"headline\":\""    + json_escape(headline)    + "\","
            + "\"description\":\"" + json_escape(description) + "\","
            + "\"isDrill\":"       + drill_s                  + ","
            + "\"expiresAt\":\""   + expires                  + "\""
            + "}";
    }

    function string build_clear_payload(string alert_id) {
        return "{\"id\":\"" + json_escape(alert_id) + "\",\"status\":\"Resolved\"}";
    }

    // ----- HTTP client -------------------------------------------------------
    function string basic_auth_header(string api_key) {
        // Airtame docs: username can be anything; password must be the API key.
        return "Basic " + system.base64_encode("gira:" + api_key);
    }

    function bool airtame_send(string endpoint, string api_key, string body_json,
                               int timeout_seconds, int max_retries) {
        int    attempt    = 0;
        int    backoff_ms = 1000;
        string auth       = basic_auth_header(api_key);

        while (attempt <= max_retries) {
            var req = hsl.net.HTTPClient();
            req.setMethod("POST");
            req.setUrl(endpoint);
            req.setHeader("Authorization", auth);
            req.setHeader("Content-Type", "application/json");
            req.setHeader("Accept", "application/json");
            req.setTimeout(timeout_seconds * 1000);
            req.setBody(body_json);

            int    status    = 0;
            string body      = "";
            bool   timed_out = false;
            try {
                var resp = req.execute();
                status = resp.getStatusCode();
                body   = resp.getBody();
            } catch (e) {
                timed_out = true;
                log_error("client", "transport: " + e.message);
            }

            if (timed_out) {
                attempt = attempt + 1;
                if (attempt > max_retries) {
                    airtame_last_status = 0;
                    airtame_last_body   = "";
                    airtame_last_error  = "timeout";
                    return false;
                }
                system.sleep_ms(backoff_ms);
                backoff_ms = backoff_ms * 2;
                continue;
            }

            if (strlen(body) > 500) { body = substr(body, 0, 500); }
            airtame_last_status = status;
            airtame_last_body   = body;

            if (status >= 200 && status < 300) {
                airtame_last_error = "";
                return true;
            }
            if (status == 401 || status == 403) {
                airtame_last_error = "auth";
                log_error("client", "auth rejected (key=" + mask_secret(api_key) + ")");
                return false;
            }
            if (status == 429) {
                attempt = attempt + 1;
                if (attempt > max_retries) { airtame_last_error = "rate-limit"; return false; }
                system.sleep_ms(backoff_ms);
                backoff_ms = backoff_ms * 2;
                continue;
            }
            if (status >= 500 && status < 600) {
                attempt = attempt + 1;
                if (attempt > max_retries) { airtame_last_error = "server"; return false; }
                system.sleep_ms(backoff_ms);
                backoff_ms = backoff_ms * 2;
                continue;
            }
            airtame_last_error = "transport";
            return false;
        }
        return false;
    }

    // ----- Main entry --------------------------------------------------------
    // Inputs (declared via INPUTS list):  1=trigger 2=clear 3=headline
    //   4=description 5=template 6=is_drill 7=duration_seconds
    // Outputs (declared via OUTPUTS list): 1=active 2=success_pulse
    //   3=error_pulse 4=last_status_code 5=last_message 6=last_alert_id

    bool   in_trigger     = INPUT[1];
    bool   in_clear       = INPUT[2];
    string in_headline    = INPUT[3];
    string in_description = INPUT[4];
    string in_template    = INPUT[5];
    bool   in_is_drill    = INPUT[6];
    int    in_duration_s  = INPUT[7];

    string p_endpoint        = PARAM["api_endpoint"];
    string p_api_key         = PARAM["api_key"];
    string p_id_prefix       = PARAM["alert_id_prefix"];
    string p_def_headline    = PARAM["default_headline"];
    string p_def_description = PARAM["default_description"];
    string p_def_template    = PARAM["default_template"];
    bool   p_def_is_drill    = PARAM["default_is_drill"];
    int    p_def_duration_s  = PARAM["default_duration_seconds"];
    int    p_timeout_s       = PARAM["timeout_seconds"];
    int    p_max_retries     = PARAM["max_retries"];
    int    p_debounce_ms     = PARAM["debounce_ms"];

    string headline    = (strlen(in_headline)    > 0) ? in_headline    : p_def_headline;
    string description = (strlen(in_description) > 0) ? in_description : p_def_description;
    string template    = (strlen(in_template)    > 0) ? in_template    : p_def_template;
    bool   is_drill    = p_def_is_drill;
    int    duration_s  = (in_duration_s > 0) ? in_duration_s : p_def_duration_s;

    int    counter         = system.getval("airtame_counter",   0);
    string active_alert_id = system.getval("airtame_active_id", "");
    bool   active          = system.getval("airtame_active",    0) != 0;

    // Config guards: refuse to send on non-HTTPS endpoint or empty key.
    if (substr(p_endpoint, 0, 8) != "https://") {
        OUTPUT[1] = active ? 1 : 0;
        OUTPUT[2] = 0;
        OUTPUT[3] = 1;
        OUTPUT[4] = 0;
        OUTPUT[5] = "config: endpoint must use HTTPS";
        OUTPUT[6] = active_alert_id;
        log_error("module", "endpoint must use HTTPS");
        return;
    }
    if (strlen(p_api_key) == 0) {
        OUTPUT[1] = active ? 1 : 0;
        OUTPUT[2] = 0;
        OUTPUT[3] = 1;
        OUTPUT[4] = 0;
        OUTPUT[5] = "config: api_key is required";
        OUTPUT[6] = active_alert_id;
        log_error("module", "api_key parameter is empty");
        return;
    }

    bool   success_pulse = false;
    bool   error_pulse   = false;
    string message       = "";

    bool fired_trigger = edge_rising(in_trigger, "trigger", p_debounce_ms);
    bool fired_clear   = edge_rising(in_clear,   "clear",   p_debounce_ms);

    if (fired_trigger) {
        counter = counter + 1;
        system.setval("airtame_counter", counter);
        string stamp    = system.strftime("%Y%m%dT%H%M%SZ", system.time());
        string alert_id = p_id_prefix + "-" + stamp + "-" + counter;

        string vmsg = validate_alert(alert_id, headline, description, template, duration_s);
        if (strlen(vmsg) > 0) {
            error_pulse = true;
            message = "validation: " + vmsg;
            log_error("trigger", message);
            OUTPUT[1] = active ? 1 : 0;
            OUTPUT[2] = 0;
            OUTPUT[3] = 1;
            OUTPUT[4] = 0;
            OUTPUT[5] = message;
            OUTPUT[6] = active_alert_id;
            return;
        }

        string body = build_trigger_payload(alert_id, headline, description,
                                            template, is_drill, duration_s);
        log_info("trigger", "sending alert id=" + alert_id +
                            " key=" + mask_secret(p_api_key));
        bool ok = airtame_send(p_endpoint, p_api_key, body, p_timeout_s, p_max_retries);
        if (ok) {
            active = true;
            active_alert_id = alert_id;
            success_pulse = true;
            message = "alert initiated";
            system.setval("airtame_active", 1);
            system.setval("airtame_active_id", active_alert_id);
        } else {
            error_pulse = true;
            message = "HTTP " + airtame_last_status + " (" + airtame_last_error + ")";
        }
    }
    else if (fired_clear) {
        if (!active || strlen(active_alert_id) == 0) {
            log_info("clear", "ignored (no active alert)");
        } else {
            string body = build_clear_payload(active_alert_id);
            log_info("clear", "resolving id=" + active_alert_id);
            bool ok = airtame_send(p_endpoint, p_api_key, body, p_timeout_s, p_max_retries);
            if (ok) {
                active = false;
                success_pulse = true;
                message = "alert resolved";
                system.setval("airtame_active", 0);
            } else {
                error_pulse = true;
                message = "HTTP " + airtame_last_status + " (" + airtame_last_error + ")";
            }
        }
    }

    OUTPUT[1] = active ? 1 : 0;
    OUTPUT[2] = success_pulse ? 1 : 0;
    OUTPUT[3] = error_pulse   ? 1 : 0;
    OUTPUT[4] = airtame_last_status;
    OUTPUT[5] = (strlen(message) > 0) ? message : airtame_last_body;
    OUTPUT[6] = active_alert_id;
""").lstrip()


# =============================================================================
# Fallback writer
# -----------------------------------------------------------------------------
# Run this file directly to emit a best-effort .hsl with a generic LBS header.
# The CANONICAL artifact is whatever Gira Experte 4.13's bundled generator
# produces from the same constants above. Compare both and prefer Gira's.
# =============================================================================

def _render_param_header() -> str:
    lines = []
    for i, p in enumerate(PARAMETERS, start=1):
        lines.append(f"// Parameter {i}: {p['name']} ({p['type']})"
                     + (f" default={p['default']!r}" if p.get('default') != '' else ""))
    return "\n".join(lines)


def _render_pin_header(title: str, pins: list[dict]) -> str:
    lines = [f"// {title}:"]
    for i, pin in enumerate(pins, start=1):
        optional = " (optional)" if pin.get("optional") else ""
        lines.append(f"//   {i}: {pin['name']} [{pin['type']}]{optional}"
                     + (f"  {pin.get('help','')}" if pin.get('help') else ""))
    return "\n".join(lines)


def render_hsl() -> str:
    return (
        f"// LBS {LBS_NUMBER} - {LBS_NAME} - v{LBS_VERSION}\n"
        f"// Vendor: {LBS_VENDOR}\n"
        f"// {LBS_HELP}\n"
        f"//\n"
        f"// NOTE: this header is a fallback. Prefer the header Gira Experte\n"
        f"// 4.13's bundled generator produces from gen/generate_lbs24815.py.\n"
        f"//\n"
        f"{_render_pin_header('Inputs', INPUTS)}\n"
        f"//\n"
        f"{_render_pin_header('Outputs', OUTPUTS)}\n"
        f"//\n"
        f"{_render_param_header()}\n"
        f"// ----------------------------------------------------------------\n"
        f"\n"
        f"{HSL_BODY}"
    )


def main(out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_hsl(), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        Path(__file__).resolve().parent.parent / "dist" / f"lbs{LBS_NUMBER}.hsl"
    )
    main(target)
