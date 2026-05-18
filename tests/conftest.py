"""Test bootstrap: inject the hsl20_4 stub into sys.modules and expose the
generated-class-file module under a clean importable name (the src file
starts with a digit so ``import 24815_...`` is invalid)."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "projects" / "airtame_emergency" / "src" / "24815_AirtameEmergencyAlert.py"

# 1) Provide a stub hsl20_4 module before loading the class file.
import tests._hsl20_4_stub as _stub
sys.modules["hsl20_4"] = _stub

# 2) Load the digit-prefixed source file under a Python-valid alias.
spec = importlib.util.spec_from_file_location("airtame_module", str(SRC))
airtame_module = importlib.util.module_from_spec(spec)
sys.modules["airtame_module"] = airtame_module
spec.loader.exec_module(airtame_module)
