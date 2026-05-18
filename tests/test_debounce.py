import airtame_module


def _instance_with_inputs(inputs):
    inst = airtame_module.AirtameEmergencyAlert24815(homeserver_context=object())
    inst.FRAMEWORK.inputs.update(inputs)
    return inst


REMS_TRIGGER = lambda inst: (inst.REM_LAST_TRIG_VAL, inst.REM_LAST_TRIG_TS_MS)


def test_first_low_sample_no_edge():
    inst = _instance_with_inputs({})
    prev, ts = REMS_TRIGGER(inst)
    assert inst._rising_edge(0, prev, ts) is False


def test_rising_edge_fires_then_held_high_does_not_refire():
    inst = _instance_with_inputs({inst_pin: 0 for inst_pin in [13]})  # debounce_ms default
    prev, ts = REMS_TRIGGER(inst)
    # baseline low
    assert inst._rising_edge(0, prev, ts) is False
    # rising edge
    assert inst._rising_edge(1, prev, ts) is True
    # held high - no refire
    assert inst._rising_edge(1, prev, ts) is False


def test_debounce_blocks_quick_retrigger(monkeypatch):
    inst = _instance_with_inputs({})
    # Force debounce_ms = 1000, no time passing between calls.
    inst.FRAMEWORK.inputs[inst.PIN_I_DEBOUNCE_MS] = 1000

    fake_ms = [0]

    def fake_time():
        return fake_ms[0] / 1000.0
    monkeypatch.setattr(airtame_module.time, "time", fake_time)

    prev, ts = REMS_TRIGGER(inst)

    # First edge at t=0
    assert inst._rising_edge(1, prev, ts) is True
    # Drop and re-raise at t=500ms -> blocked by debounce
    inst._rising_edge(0, prev, ts)
    fake_ms[0] = 500
    assert inst._rising_edge(1, prev, ts) is False
    # Drop and re-raise at t=1500ms -> allowed
    inst._rising_edge(0, prev, ts)
    fake_ms[0] = 1500
    assert inst._rising_edge(1, prev, ts) is True
