"""Tests for the schema migration set under sql/migrations/."""

import re
from pathlib import Path

import pytest

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "sql" / "migrations"


def _migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def test_migrations_dir_exists():
    assert MIGRATIONS_DIR.is_dir(), f"expected migrations dir at {MIGRATIONS_DIR}"


def test_migrations_present():
    files = _migration_files()
    assert files, "no .sql migration files found"


def test_migration_filenames_are_numbered_monotonically():
    files = _migration_files()
    nums = []
    for f in files:
        m = re.match(r"^(\d+)_", f.name)
        assert m, f"migration {f.name} must start with a numeric prefix and underscore"
        nums.append(int(m.group(1)))
    assert nums == sorted(nums), f"migration numbers are not monotonic: {nums}"
    assert len(set(nums)) == len(nums), f"duplicate migration numbers: {nums}"


def test_initial_migration_creates_tenants_table():
    """Sanity check: the baseline migration must contain CREATE TABLE tenants."""
    initial = MIGRATIONS_DIR / "0001_initial_schema.sql"
    text = initial.read_text()
    assert "CREATE TABLE IF NOT EXISTS tenants" in text


def test_timestamptz_migration_lists_all_known_columns():
    """All 17 TEXT date columns identified in the review must be referenced."""
    mig = MIGRATIONS_DIR / "0002_text_to_timestamptz.sql"
    text = mig.read_text()
    expected_columns = [
        ("retention_events", "created"),
        ("retention_event_types", "created"),
        ("retention_event_types", "modified"),
        ("retention_labels", "created"),
        ("retention_labels", "modified"),
        ("audit_records", "created"),
        ("dlp_alerts", "created"),
        ("dlp_alerts", "resolved"),
        ("irm_alerts", "created"),
        ("irm_alerts", "resolved"),
        ("dlp_policies", "created"),
        ("dlp_policies", "modified"),
        ("irm_policies", "created"),
        ("compliance_assessments", "created"),
        ("threat_assessment_requests", "created"),
        ("purview_incidents", "created"),
        ("purview_incidents", "last_update"),
    ]
    for table, col in expected_columns:
        assert table in text, f"{table} missing from timestamptz migration"
        assert col in text, f"{col} missing from timestamptz migration"


def test_yoyo_can_parse_all_migrations():
    """yoyo's own parser must accept every migration without error."""
    yoyo = pytest.importorskip("yoyo")
    migrations = yoyo.read_migrations(str(MIGRATIONS_DIR))
    ids = [m.id for m in migrations]
    assert ids, "yoyo found no migrations"
    assert ids == sorted(ids), f"yoyo ordering does not match filename ordering: {ids}"
