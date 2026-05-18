"""Minimal stand-in for the Gira HSL2 hsl20_4 framework.

Mirrors the *real* API surface verified against the SDK 2.0.7 source:
- pin/remanent methods live on BaseModule (NOT on Framework).
- Framework provides create_*() factories and resolve_dns / get_*() helpers.
- get_framework_index() == 7.
The real framework is inlined into the deployed .hsl by generator.pyc; this
stub is only used in src/ during pytest.
"""


LOGGING_NONE = 0
LOGGING_SYSLOG = 1


class _Logger(object):
    def __init__(self):
        self.records = []

    def info(self, line, msg):    self.records.append(("info", line, msg))
    def debug(self, line, msg):   self.records.append(("debug", line, msg))
    def warning(self, line, msg): self.records.append(("warn", line, msg))
    def error(self, line, msg):   self.records.append(("error", line, msg))


class _Framework(object):
    """The real framework exposes HTTP/TCP/UDP/Timer factories. Tests rarely
    need them; if a future test does, add it here and to the real BaseModule
    subclass under test."""

    @staticmethod
    def get_framework_index():
        return 7

    def resolve_dns(self, hostname):
        return hostname

    def _run_in_context_thread(self, method_to_call, args=None):
        # Stub: run synchronously.
        if args is None:
            method_to_call()
        else:
            method_to_call(*args)


class BaseModule(object):
    def __init__(self, homeserver_context, module_context):
        self._homeserver_context = homeserver_context
        self._module_context = module_context
        self._framework = _Framework()
        self._logger = _Logger()
        # Tests poke values into these dicts:
        self._input_values = {}    # pin_index -> value
        self._output_values = {}   # pin_index -> value
        self._output_history = []  # list of (pin_index, value) writes
        self._remanent_values = {}

    def _get_framework(self):
        return self._framework

    def _get_logger(self, logType, param):
        return self._logger

    # ---- the real API on BaseModule, modeled faithfully -----------------

    def _get_input_value(self, index):
        return self._input_values.get(index)

    def _set_output_value(self, index, value):
        self._output_values[index] = value
        self._output_history.append((index, value))

    def _get_remanent(self, index):
        return self._remanent_values.get(index)

    def _set_remanent(self, index, value):
        if isinstance(value, str):
            value = value[:30000]
        self._remanent_values[index] = value

    # Callbacks intended to be overridden.
    def on_init(self):
        pass

    def on_input_value(self, index, value):
        pass
