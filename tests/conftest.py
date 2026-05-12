import sys
from pathlib import Path

# Make the repository root importable so tests can do `from reference import ...`
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
