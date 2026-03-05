#!/usr/bin/env python3
"""One-time script to create the SQLite database from sql/schema_sqlite.sql."""
import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

project_root = Path(__file__).parent
schema_path = project_root / "sql" / "schema_sqlite.sql"

db_path = os.environ.get("SQLITE_DB_PATH", str(project_root / "data" / "compliance.db"))
Path(db_path).parent.mkdir(parents=True, exist_ok=True)
conn = sqlite3.connect(db_path)
conn.executescript(schema_path.read_text())
conn.close()
print(f"Database initialized: {db_path}")
