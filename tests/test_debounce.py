from reference.debounce import EdgeDebouncer


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def test_only_rising_edge_fires():
    clock = FakeClock()
    d = EdgeDebouncer(debounce_seconds=1.0, clock=clock)
    assert d.update(False) is False
    assert d.update(True) is True
    assert d.update(True) is False  # held high, no new edge
    assert d.update(False) is False
    clock.t = 2.0
    assert d.update(True) is True


def test_repeated_rising_edges_inside_window_are_suppressed():
    clock = FakeClock()
    d = EdgeDebouncer(debounce_seconds=1.0, clock=clock)
    assert d.update(True) is True
    assert d.update(False) is False
    clock.t = 0.5
    assert d.update(True) is False  # too soon
    clock.t = 1.5
    assert d.update(False) is False
    clock.t = 1.6
    assert d.update(True) is True


def test_first_sample_low_is_not_an_edge():
    clock = FakeClock()
    d = EdgeDebouncer(debounce_seconds=1.0, clock=clock)
    assert d.update(False) is False
