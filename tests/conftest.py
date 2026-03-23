import sys
from pathlib import Path

# Add functions/ to sys.path so `shared.*` imports resolve
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "functions"))

# Integration tests require DATABASE_URL and the `integration` marker.
# Run unit tests only:  pytest tests/ -m "not integration"
# Run integration only: DATABASE_URL=... pytest tests/ -m integration -v
