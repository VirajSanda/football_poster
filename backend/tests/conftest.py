import sys
from pathlib import Path

# Ensure project package imports work when running tests from backend/
# add repository root (parent of backend/) so `import backend.xxx` works
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
