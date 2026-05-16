"""Integration test fixtures -- requires a running PostgreSQL instance."""

import os
from pathlib import Path
from unittest.mock import MagicMock

import psycopg2
import pytest

# Apply all yoyo migrations in order to bootstrap the test schema.
# (Replaced the single sql/schema.sql load when migrations were
# introduced in PR #14.)
MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "sql" / "migrations"


@pytest.fixture(scope="session")
def db_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("No DATABASE_URL set -- skipping integration tests")
    return url


@pytest.fixture(scope="session")
def db_schema(db_url):
    """Create all tables once per session by applying every migration."""
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS public CASCADE")
        cur.execute("CREATE SCHEMA public")
        for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
            sql = migration.read_text()
            try:
                cur.execute(sql)
            except psycopg2.Error as exc:
                # 0002 (TIMESTAMPTZ) wraps everything in a DO block that no-ops
                # when columns are already the right type, but the
                # pg_stat_statements migration in 0004 needs the extension to
                # be preloaded. Skip that one in the test database.
                if "pg_stat_statements" in sql:
                    continue
                raise RuntimeError(f"Failed to apply {migration.name}: {exc}") from exc
    conn.close()
    yield
    # Cleanup: drop and recreate public schema
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS public CASCADE")
        cur.execute("CREATE SCHEMA public")
    conn.close()


@pytest.fixture()
def db_conn(db_url, db_schema):
    """Per-test connection with rollback for isolation."""
    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    yield conn
    conn.rollback()
    conn.close()


@pytest.fixture(autouse=True)
def patch_db(db_conn, db_url, monkeypatch):
    """Monkeypatch shared.db and shared.config to use test database."""
    import shared.config as config_module
    import shared.db as db_module

    class FakePool:
        def getconn(self):
            return db_conn

        def putconn(self, conn):
            pass

    # Clear lru_cache so patched settings take effect
    config_module.get_settings.cache_clear()

    # Patch the pool
    monkeypatch.setattr(db_module, "_pool", FakePool())

    # Patch get_settings to return settings with test DATABASE_URL
    mock_settings = MagicMock()
    mock_settings.DATABASE_URL = db_url
    mock_settings.KEY_VAULT_URL = "https://fake.vault.azure.net/"
    mock_settings.ALLOWED_TENANT_IDS = ""
    mock_settings.allowed_tenants = set()
    monkeypatch.setattr(config_module, "get_settings", lambda: mock_settings)

    # Override get_conn to use our test connection directly (no commit/rollback;
    # the db_conn fixture handles rollback for isolation)
    from contextlib import contextmanager

    @contextmanager
    def fake_get_conn():
        yield db_conn

    monkeypatch.setattr(db_module, "get_conn", fake_get_conn)

    yield
