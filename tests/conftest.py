import os
import sys
from pathlib import Path

# Add functions/ to sys.path so `shared.*` imports resolve
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "functions"))

# Provide safe defaults for FunctionSettings so route tests can exercise
# require_auth() without a real Key Vault / database. Individual tests can
# still override these via patch() or monkeypatch.
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test_compliance")
os.environ.setdefault("KEY_VAULT_URL", "https://test.vault.azure.net/")
os.environ.setdefault("AUTH_REQUIRED", "false")

# Integration tests require DATABASE_URL and the `integration` marker.
# Run unit tests only:  pytest tests/ -m "not integration"
# Run integration only: DATABASE_URL=... pytest tests/ -m integration -v
