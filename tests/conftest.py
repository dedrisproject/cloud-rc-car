import sys
from pathlib import Path

# Make the modules under server/ importable from the tests.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))
