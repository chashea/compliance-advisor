"""Route blueprints for the Compliance Advisor Function App.

Each module exports a ``func.Blueprint`` that ``function_app.py`` registers
with the global ``FunctionApp`` instance. Routes are grouped by purpose:

- :mod:`routes.admin`     — health, admin/migrate
- :mod:`routes.dashboard` — read-only advisor/* dashboard endpoints
- :mod:`routes.ai`        — AI-powered advisor/briefing, advisor/ask
- :mod:`routes.ingest`    — collector ingest endpoint
- :mod:`routes.tenants`   — tenant registration + Entra consent callback
- :mod:`routes.collect`   — on-demand collection + hunt endpoints
- :mod:`routes.timers`    — scheduled timer triggers
"""
