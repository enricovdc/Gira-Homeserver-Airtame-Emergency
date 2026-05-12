"""Edge detection and debounce for KNX-style trigger inputs.

A noisy KNX bus can flip a trigger input multiple times in quick succession.
The logic module must only fire an HTTP request on the rising edge, and ignore
repeated rising edges that arrive inside the debounce window.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class EdgeDebouncer:
    """Tracks one boolean input and reports debounced rising edges."""
    debounce_seconds: float = 1.0
    clock: Callable[[], float] = time.monotonic
    _last_value: Optional[bool] = field(default=None, init=False, repr=False)
    _last_fired_at: float = field(default=float("-inf"), init=False, repr=False)

    def update(self, value: bool) -> bool:
        """Feed a new input sample. Returns True iff this is a debounced rising edge."""
        now = self.clock()
        previous = self._last_value
        self._last_value = value
        if value and not previous:
            if now - self._last_fired_at >= self.debounce_seconds:
                self._last_fired_at = now
                return True
        return False
