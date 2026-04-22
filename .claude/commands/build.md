---
name: build
description: Build the frontend and compile Bicep infrastructure
user_invocable: true
---

Build all compilable artifacts for compliance-advisor.

1. **Frontend**: From `frontend/`, run `npm run build` (tsc -b && vite build). Report any type or build errors.
2. **Bicep**: From repo root, run `az bicep build --file infra/main.bicep --outfile azuredeploy.json`. Report any template errors.
3. Summarize: build status for each component (pass/fail).
