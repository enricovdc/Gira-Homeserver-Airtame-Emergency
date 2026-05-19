"""CAP 1.2 XML payload tests for both HSL2 and HSL3 modules.

Airtame's "Option 1: CAP Standard" (per the Emergency Alerts payload
guidelines docs) accepts CAP 1.2 XML on the same endpoint as JSON. Airtame
strictly validates against the CAP XSD and derives template selection from
the CAP <urgency> field. These tests pin: namespace, required elements,
template->urgency mapping, drill->Test status, Cancel <references> shape.
"""
import xml.etree.ElementTree as ET

import pytest

import airtame_module          # HSL2
import airtame_hsl3_module     # HSL3
import tests._hsl3_stub as h3stub

CAP_NS = "{urn:oasis:names:tc:emergency:cap:1.2}"


# ----- parametrize over both module flavors --------------------------------

@pytest.fixture(params=["hsl2", "hsl3"])
def cap(request):
    """Returns a small object exposing build_alert / build_cancel for the
    flavor under test, so the same assertions cover both modules."""
    if request.param == "hsl2":
        inst = airtame_module.AirtameEmergencyAlert24815(homeserver_context=object())
        class _W:
            flavor = "hsl2"
            build_alert = staticmethod(lambda **kw: inst._build_cap_alert(**kw))
            build_cancel = staticmethod(lambda **kw: inst._build_cap_cancel(**kw))
        return _W()
    else:
        class _W:
            flavor = "hsl3"
            build_alert = staticmethod(airtame_hsl3_module.build_cap_alert)
            build_cancel = staticmethod(airtame_hsl3_module.build_cap_cancel)
        return _W()


# ----- shape + namespace ---------------------------------------------------

def _parse(xml):
    # Tolerate the leading XML declaration; ET handles it.
    return ET.fromstring(xml)


def test_cap_alert_root_namespace_and_minimum_elements(cap):
    xml = cap.build_alert(
        alert_id="abc-123",
        sender_id="gira-homeserver",
        sent_iso="2026-05-18T08:00:00+00:00",
        headline="Lockdown",
        description="Shelter in place.",
        template="high",
        is_drill=False,
        **({"duration_s": 600, "category": "Safety",
            "expires_iso": "2026-05-18T08:10:00+00:00"}
           if cap.flavor == "hsl2"
           else {"category": "Safety",
                 "expires_iso": "2026-05-18T08:10:00+00:00"})
    )
    root = _parse(xml)
    assert root.tag == CAP_NS + "alert"

    required = ("identifier", "sender", "sent", "status", "msgType", "scope")
    for name in required:
        elem = root.find(CAP_NS + name)
        assert elem is not None, "missing <%s>" % name
        assert elem.text, "<%s> must not be empty" % name

    info = root.find(CAP_NS + "info")
    assert info is not None
    for name in ("category", "event", "urgency", "severity", "certainty"):
        elem = info.find(CAP_NS + name)
        assert elem is not None, "<info>/<%s> missing" % name
        assert elem.text, "<info>/<%s> must not be empty" % name


def test_template_high_maps_to_urgency_immediate(cap):
    xml = cap.build_alert(
        alert_id="i", sender_id="s", sent_iso="2026-05-18T08:00:00+00:00",
        headline="h", description="d", template="high", is_drill=False,
        **({"duration_s": 60, "category": "Safety",
            "expires_iso": "2026-05-18T08:01:00+00:00"}
           if cap.flavor == "hsl2"
           else {"category": "Safety",
                 "expires_iso": "2026-05-18T08:01:00+00:00"})
    )
    info = _parse(xml).find(CAP_NS + "info")
    assert info.find(CAP_NS + "urgency").text == "Immediate"


@pytest.mark.parametrize("template,expected_urgency", [
    ("high", "Immediate"),
    ("medium", "Expected"),
    ("low", "Future"),
])
def test_template_to_urgency_mapping(cap, template, expected_urgency):
    extras = ({"duration_s": 60, "category": "Safety",
               "expires_iso": "2026-05-18T08:01:00+00:00"}
              if cap.flavor == "hsl2"
              else {"category": "Safety",
                    "expires_iso": "2026-05-18T08:01:00+00:00"})
    xml = cap.build_alert(
        alert_id="i", sender_id="s", sent_iso="2026-05-18T08:00:00+00:00",
        headline="h", description="d", template=template, is_drill=False,
        **extras)
    info = _parse(xml).find(CAP_NS + "info")
    assert info.find(CAP_NS + "urgency").text == expected_urgency


def test_drill_keeps_actual_status_and_uses_minor_severity(cap):
    """Airtame's CAP sample always shows <status>Actual</status>; CAP 'Test'
    means recipients must disregard. Drill differentiation in CAP comes from
    <severity>=Minor instead of switching status."""
    extras = ({"duration_s": 60, "category": "Safety",
               "expires_iso": "2026-05-18T08:01:00+00:00"}
              if cap.flavor == "hsl2"
              else {"category": "Safety",
                    "expires_iso": "2026-05-18T08:01:00+00:00"})
    xml = cap.build_alert(
        alert_id="i", sender_id="s", sent_iso="2026-05-18T08:00:00+00:00",
        headline="h", description="d", template="high", is_drill=True,
        **extras)
    root = _parse(xml)
    assert root.find(CAP_NS + "status").text == "Actual"
    assert root.find(CAP_NS + "info").find(CAP_NS + "severity").text == "Minor"


def test_real_alert_uses_actual_status_and_severe_severity(cap):
    extras = ({"duration_s": 60, "category": "Safety",
               "expires_iso": "2026-05-18T08:01:00+00:00"}
              if cap.flavor == "hsl2"
              else {"category": "Safety",
                    "expires_iso": "2026-05-18T08:01:00+00:00"})
    xml = cap.build_alert(
        alert_id="i", sender_id="s", sent_iso="2026-05-18T08:00:00+00:00",
        headline="h", description="d", template="high", is_drill=False,
        **extras)
    root = _parse(xml)
    assert root.find(CAP_NS + "status").text == "Actual"
    assert root.find(CAP_NS + "info").find(CAP_NS + "severity").text == "Severe"


def test_xml_special_chars_in_text_are_escaped(cap):
    headline_with_amp = 'Fire & smoke <west "wing">'
    extras = ({"duration_s": 60, "category": "Safety",
               "expires_iso": "2026-05-18T08:01:00+00:00"}
              if cap.flavor == "hsl2"
              else {"category": "Safety",
                    "expires_iso": "2026-05-18T08:01:00+00:00"})
    xml = cap.build_alert(
        alert_id="i", sender_id="s", sent_iso="2026-05-18T08:00:00+00:00",
        headline=headline_with_amp, description="d", template="high",
        is_drill=False, **extras)
    # If escaping is broken, ET.fromstring raises. The recovered text must
    # match the original after XML decoding.
    root = _parse(xml)
    assert root.find(CAP_NS + "info").find(CAP_NS + "headline").text == headline_with_amp


# ----- Cancel + <references> ----------------------------------------------

def test_cap_cancel_has_correct_msgtype_and_references(cap):
    """Airtame's Stop-an-alert sample mirrors the original alert's
    urgency/severity/certainty (not Past/Unknown/Unknown)."""
    kw = dict(
        cancel_id="cancel-1",
        sender_id="gira-homeserver",
        cancel_sent_iso="2026-05-18T08:15:00+00:00",
        original_id="abc-123",
        original_sent_iso="2026-05-18T08:00:00+00:00",
        category="Safety",
        is_drill=False,
        template="high",
    )
    xml = cap.build_cancel(**kw)
    root = _parse(xml)
    assert root.find(CAP_NS + "msgType").text == "Cancel"
    refs = root.find(CAP_NS + "references")
    assert refs is not None
    # CAP 1.2 spec: references is a space-or-newline separated list of
    # `sender,identifier,sent` triples. We send exactly one triple.
    assert refs.text == "gira-homeserver,abc-123,2026-05-18T08:00:00+00:00"
    info = root.find(CAP_NS + "info")
    assert info.find(CAP_NS + "urgency").text == "Immediate"
    assert info.find(CAP_NS + "severity").text == "Severe"
    assert info.find(CAP_NS + "certainty").text == "Observed"


# ----- End-to-end: HSL3 module sends application/xml for CAP --------------

class _RecordingFakeHTTP:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
    def __call__(self, url, headers, body, timeout, max_retries):
        self.calls.append({"url": url, "headers": dict(headers),
                           "body": body, "timeout": timeout})
        item = self.responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        status, body_text = item
        err = "" if 200 <= status < 300 else ("auth" if status in (401, 403)
              else ("rate-limit" if status == 429
              else ("server" if 500 <= status < 600 else "transport")))
        return status, body_text, err


def _hsl3_inputs_with_format(fmt):
    return h3stub.make_inputs(
        trigger=0, clear=0,
        headline="Lockdown", description="Shelter in place.",
        template="high", is_drill=0, duration_seconds=300,
        api_endpoint="https://airtame.cloud/api/v3.0/cloud/public/emergency-alerts",
        api_key="testkey1234567890",
        alert_id_prefix="gira-hs",
        timeout_seconds=5, max_retries=2, debounce_ms=0,
        payload_format=fmt, sender_id="gira-homeserver", cap_category="Safety",
    )


@pytest.fixture
def sync_threads_hsl3(monkeypatch):
    class _SyncThread:
        def __init__(self, target=None, args=(), kwargs=None, daemon=None):
            self._t = target; self._a = args; self._k = kwargs or {}
        def start(self):
            self._t(*self._a, **self._k)
    monkeypatch.setattr(airtame_hsl3_module.threading, "Thread", _SyncThread)


def test_hsl3_cap_trigger_sends_application_xml_with_cap_body(sync_threads_hsl3):
    hsl3 = h3stub.Hsl3()
    inst = airtame_hsl3_module.LogicModule(hsl3)
    inst._send_http = _RecordingFakeHTTP([(200, "")])
    inputs = _hsl3_inputs_with_format("cap")
    inst.on_init(inputs, h3stub.make_store())
    inputs._clear_changed()
    inputs._set("trigger", 1, mark_changed=True)
    inst.on_calc(inputs)

    call = inst._send_http.calls[0]
    assert call["headers"]["Content-Type"] == "application/xml"
    root = ET.fromstring(call["body"])
    assert root.tag == CAP_NS + "alert"
    assert root.find(CAP_NS + "msgType").text == "Alert"
    assert root.find(CAP_NS + "info").find(CAP_NS + "urgency").text == "Immediate"


def test_hsl3_cap_clear_sends_cancel_with_references(sync_threads_hsl3):
    hsl3 = h3stub.Hsl3()
    inst = airtame_hsl3_module.LogicModule(hsl3)
    inst._send_http = _RecordingFakeHTTP([(200, ""), (200, "")])
    inputs = _hsl3_inputs_with_format("cap")
    inst.on_init(inputs, h3stub.make_store())
    inputs._clear_changed()

    inputs._set("trigger", 1, mark_changed=True)
    inst.on_calc(inputs)
    inputs._set("trigger", 0, mark_changed=True)
    inst.on_calc(inputs)
    inputs._set("clear", 1, mark_changed=True)
    inst.on_calc(inputs)

    cancel_call = inst._send_http.calls[1]
    assert cancel_call["headers"]["Content-Type"] == "application/xml"
    root = ET.fromstring(cancel_call["body"])
    assert root.find(CAP_NS + "msgType").text == "Cancel"
    refs = root.find(CAP_NS + "references").text
    assert refs.startswith("gira-homeserver,gira-hs-")
    assert ",%s" % inst._active_sent_ts in refs


def test_hsl3_json_format_still_sends_application_json(sync_threads_hsl3):
    """Sanity: switching format=cap doesn't break the default json path."""
    hsl3 = h3stub.Hsl3()
    inst = airtame_hsl3_module.LogicModule(hsl3)
    inst._send_http = _RecordingFakeHTTP([(200, "")])
    inputs = _hsl3_inputs_with_format("json")
    inst.on_init(inputs, h3stub.make_store())
    inputs._clear_changed()
    inputs._set("trigger", 1, mark_changed=True)
    inst.on_calc(inputs)
    call = inst._send_http.calls[0]
    assert call["headers"]["Content-Type"] == "application/json"
    # Body should be valid JSON, not XML.
    import json as _json
    parsed = _json.loads(call["body"])
    assert parsed["status"] == "Initiated"


# ----- CAP XSD element-order compliance (Airtame validates strictly) -----


CAP_INFO_ORDER = [
    "category", "event", "urgency", "severity", "certainty",
    "expires", "senderName", "headline", "description",
    "instruction", "area",
]


def _info_child_order(xml_bytes_or_str):
    root = ET.fromstring(xml_bytes_or_str)
    info = root.find(CAP_NS + "info")
    # Strip namespace prefix to compare against the readable list.
    return [child.tag.split("}", 1)[-1] for child in info]


def test_cap_alert_info_children_in_xsd_order(cap):
    extras = ({"duration_s": 60, "category": "Safety",
               "expires_iso": "2026-05-18T08:01:00+00:00"}
              if cap.flavor == "hsl2"
              else {"category": "Safety",
                    "expires_iso": "2026-05-18T08:01:00+00:00"})
    xml = cap.build_alert(
        alert_id="i", sender_id="s", sent_iso="2026-05-18T08:00:00+00:00",
        headline="h", description="d", template="high", is_drill=False,
        **extras)
    order = _info_child_order(xml)
    # We emit every documented element from the Airtame sample.
    assert order == CAP_INFO_ORDER


def test_cap_cancel_info_children_in_xsd_order(cap):
    xml = cap.build_cancel(
        cancel_id="cancel-1", sender_id="s",
        cancel_sent_iso="2026-05-18T08:15:00+00:00",
        original_id="abc-123",
        original_sent_iso="2026-05-18T08:00:00+00:00",
        category="Safety", is_drill=False, template="high")
    order = _info_child_order(xml)
    # Cancel has no <expires>; rest matches the sample.
    expected = [e for e in CAP_INFO_ORDER if e != "expires"]
    assert order == expected


def test_cap_alert_includes_instruction_and_area_skeleton(cap):
    """Airtame's published sample includes <instruction/> and
    <area><areaDesc/><circle/></area> with empty content. Match that exactly
    so the message validates against Airtame's XSD."""
    extras = ({"duration_s": 60, "category": "Safety",
               "expires_iso": "2026-05-18T08:01:00+00:00"}
              if cap.flavor == "hsl2"
              else {"category": "Safety",
                    "expires_iso": "2026-05-18T08:01:00+00:00"})
    xml = cap.build_alert(
        alert_id="i", sender_id="s", sent_iso="2026-05-18T08:00:00+00:00",
        headline="h", description="d", template="high", is_drill=False,
        **extras)
    info = ET.fromstring(xml).find(CAP_NS + "info")
    assert info.find(CAP_NS + "instruction") is not None
    area = info.find(CAP_NS + "area")
    assert area is not None
    assert area.find(CAP_NS + "areaDesc") is not None
    assert area.find(CAP_NS + "circle") is not None
