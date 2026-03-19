---
name: db
description: Run database queries or inspect schema for compliance-advisor PostgreSQL
user_invocable: true
---

Connect to the compliance-advisor PostgreSQL database and run queries or inspect schema.

**Connection details:**
- Host: `cadvisor-pg-7zez2cj3gamky.postgres.database.azure.com`
- Database: `compliance_advisor`
- User: `cadvisor_admin`
- psql binary: `$(brew --prefix libpq)/bin/psql`

**Usage:**
- If the user provides a SQL query, run it via psql.
- If no query is provided, ask what they want to inspect.
- Common operations:
  - `\dt` — list all tables
  - `SELECT count(*) FROM <table>` — row counts
  - Schema inspection: `\d+ <table>`

**Safety:**
- READ-ONLY by default. Ask for explicit confirmation before any INSERT, UPDATE, DELETE, or DDL.
- Never drop tables or truncate without the user typing the exact command.
- Mask any PII in output if present.
