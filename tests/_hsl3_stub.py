"""Stand-in for the HSL3 SDK 3.0 runtime, sized for pytest coverage.

Mirrors the surface the HSL3 examples (binary_trigger, http_request,
communication_between_instances) call into:

    hsl3.create_debug_section()        -> Debug with .log(msg)
    hsl3.set_output(name, value)
    hsl3.set_store(name, value)
    hsl3.set_timer(name, seconds)
    hsl3.get_instance_id()
    hsl3.get_instance(id)
    hsl3.run_in_context(method, args)

Containers passed to lifecycle hooks:
    inputs.keys() / value(name) / changed(name)
    store.keys()  / value(name) / changed(name)
    timer.changed(name)
"""


class _Debug:
    def __init__(self):
        self.records = []

    def log(self, msg):
        self.records.append(str(msg))


class _Container:
    """Backs inputs / store / timer with a dict and a changed-set.

    On at least one real HomeServer firmware the framework exposes each
    input/store under MULTIPLE keys: numeric index (1-based, in
    declaration order), UPPERCASE const-name string, AND (per the SDK
    example) the lowercase identifier. This stub mirrors that so module
    code that probes inputs.keys() and picks any of the three forms
    works against the stub and against the real firmware identically.
    """
    def __init__(self, values=None):
        values = dict(values or {})
        # logical name -> tuple of (lower, upper, idx) keys it's registered under
        self._aliases = {}
        self._values = {}
        self._changed = set()
        for i, (name, value) in enumerate(values.items(), start=1):
            self._register(name, i, value, mark_changed=True)

    def _register(self, name, idx, value, mark_changed):
        aliases = (name, name.upper(), idx) if isinstance(name, str) else (name,)
        self._aliases[name] = aliases
        for k in aliases:
            self._values[k] = value
            if mark_changed:
                self._changed.add(k)

    def keys(self):
        # Preserve declaration order for numeric keys, then string aliases.
        ordered = []
        for aliases in self._aliases.values():
            for k in aliases:
                if k not in ordered:
                    ordered.append(k)
        return ordered

    def value(self, name):
        return self._values.get(name)

    def changed(self, name):
        return name in self._changed

    # ---- test helpers - not part of the SDK surface ----
    def _set(self, name, value, mark_changed=True):
        if name not in self._aliases:
            idx = len(self._aliases) + 1
            self._register(name, idx, value, mark_changed=mark_changed)
            return
        for k in self._aliases[name]:
            self._values[k] = value
            if mark_changed:
                self._changed.add(k)
            else:
                self._changed.discard(k)

    def _clear_changed(self):
        self._changed.clear()


class Hsl3:
    def __init__(self):
        self.outputs = {}              # name -> value
        self.output_history = []       # list of (name, value)
        self.store = {}                # name -> value
        self.store_history = []
        self.timers = {}               # name -> seconds
        self.debug = _Debug()
        self._instance_id = 1

    def create_debug_section(self):
        return self.debug

    def set_output(self, name, value):
        self.outputs[name] = value
        self.output_history.append((name, value))

    def set_store(self, name, value):
        self.store[name] = value
        self.store_history.append((name, value))

    def set_timer(self, name, seconds):
        self.timers[name] = seconds

    def get_instance_id(self):
        return self._instance_id

    def get_instance(self, instance_id):
        return None

    def run_in_context(self, method, args):
        # Tests run synchronously - immediately invoke on the current thread.
        method(*args)


def make_inputs(**values):
    return _Container(values)


def make_store(**values):
    return _Container(values)
