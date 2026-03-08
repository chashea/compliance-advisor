import sys
from pathlib import Path

# Add functions/ to sys.path so `shared.*` imports resolve
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "functions"))
