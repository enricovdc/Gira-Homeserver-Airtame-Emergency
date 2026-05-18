"""Test bootstrap: inject framework stubs into sys.modules and expose the
generated-class-file modules under clean importable names (their source
filenames start with digits, so direct import would be invalid)."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# --- HSL2 ----------------------------------------------------------------
import tests._hsl20_4_stub as _hsl2_stub
sys.modules["hsl20_4"] = _hsl2_stub

HSL2_SRC = ROOT / "projects" / "airtame_emergency" / "src" / "24815_AirtameEmergencyAlert.py"
_spec = importlib.util.spec_from_file_location("airtame_module", str(HSL2_SRC))
airtame_module = importlib.util.module_from_spec(_spec)
sys.modules["airtame_module"] = airtame_module
_spec.loader.exec_module(airtame_module)

# --- HSL3 ----------------------------------------------------------------
HSL3_SRC = ROOT / "projects" / "airtame_emergency_hsl3" / "hsl3_24815_airtame_emergency.py"
_spec3 = importlib.util.spec_from_file_location("airtame_hsl3_module", str(HSL3_SRC))
airtame_hsl3_module = importlib.util.module_from_spec(_spec3)
sys.modules["airtame_hsl3_module"] = airtame_hsl3_module
_spec3.loader.exec_module(airtame_hsl3_module)
