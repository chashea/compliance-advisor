---
name: lint
description: Lint and format the codebase (ruff, black, tsc)
user_invocable: true
---

Run all linters and formatters for the compliance-advisor project.

1. **Python backend**: From the repo root, run:
   - `ruff check .` — fix any errors found
   - `black --check .` — if formatting issues, run `black .` to fix
2. **Frontend**: From `frontend/`, run:
   - `npm run lint` — fix any ESLint errors
   - `npm run build` — verify TypeScript compiles cleanly (tsc -b && vite build)
3. Report results: list any issues found and whether they were auto-fixed or need manual intervention.
