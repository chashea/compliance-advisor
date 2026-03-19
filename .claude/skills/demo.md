---
name: demo
description: Start the frontend in demo mode with mock data
user_invocable: true
---

Start the compliance-advisor frontend in demo mode (no backend needed).

```bash
cd frontend && npm run demo
```

This runs Vite with `VITE_DEMO=true`, which uses mock data instead of hitting the Function App APIs.

After starting, report the local URL (usually http://localhost:5173).
