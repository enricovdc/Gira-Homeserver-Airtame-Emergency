"""Minimal stand-in for the Gira HSL2 hsl20_4 framework, just enough to import
and exercise a BaseModule subclass under pytest.

The real framework is inlined into the deployed .hsl by generator.pyc, so this
stub is *only* used in src/ during local Python tests. It models the subset of
the API the Airtame Emergency Alert module relies on; if the deployed module
calls something not modeled here, tests will fail with a clean AttributeError
that points at the missing surface.
"""

LOGGING_NONE = "NONE"
LOGGING_SYSLOG = "SYSLOG"
LOGGING_UDP = "UDP"


class _Logger(object):
    def __init__(self):
        self.records = []

    def info(self, line, msg):    self.records.append(("info", line, msg))
    def debug(self, line, msg):   self.records.append(("debug", line, msg))
    def warning(self, line, msg): self.records.append(("warn", line, msg))
    def error(self, line, msg):   self.records.append(("error", line, msg))


class _Framework(object):
    """Tracks pin and remanent state for assertions in tests."""

    def __init__(self):
        self.inputs = {}     # pin_index -> value (NUMBER or STRING)
        self.outputs = {}    # pin_index -> value
        self.output_history = []  # list of (pin_index, value) in write order
        self.remanent = {}   # rem_index -> value

    def _set_output_value(self, pin, value):
        self.outputs[pin] = value
        self.output_history.append((pin, value))

    def _get_input_value(self, pin):
        return self.inputs.get(pin)

    def _set_remanent(self, idx, value):
        self.remanent[idx] = value

    def _get_remanent(self, idx):
        return self.remanent.get(idx)


class BaseModule(object):
    def __init__(self, homeserver_context, context_name):
        self._homeserver_context = homeserver_context
        self._context_name = context_name
        self._framework = _Framework()
        self._logger = _Logger()

    def _get_framework(self):
        return self._framework

    def _get_logger(self, logging_type, logging_args):
        return self._logger
