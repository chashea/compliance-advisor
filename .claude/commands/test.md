---
name: test
description: Run the test suite for compliance-advisor
user_invocable: true
---

Run the compliance-advisor test suite.

1. Run all 48 tests: `python3.12 -m pytest tests/ -v`
2. If any tests fail, investigate the failure and fix it autonomously.
3. Re-run only the failing tests to confirm the fix.
4. Report results as a short summary: passed/failed/fixed counts.

If the user provides a specific test file or test name as an argument, run only that instead of the full suite.
