## 1. Spec

- [x] 1.1 Add dashboard compact status-card and Account-section requirements.
- [x] 1.2 Add dashboard rolling per-account usage window requirement.
- [x] 1.3 Validate OpenSpec changes with `uv run pytest tests/integration/test_dashboard_overview.py`, `cd frontend && bun run test -- src/__integration__/dashboard-flow.test.tsx`, `cd frontend && bun run build`, and `openspec validate --specs`.

## 2. Backend

- [x] 2.1 Extend dashboard overview schema with `accountRollingUsage`.
- [x] 2.2 Aggregate rolling usage per account for 5m/15m/1h/1d windows.
- [x] 2.3 Add dashboard integration assertions for new response fields.

## 3. Frontend

- [x] 3.1 Extend dashboard Zod schema/types for `accountRollingUsage`.
- [x] 3.2 Replace four account-health cards with one compact `H/W/L/A` card.
- [x] 3.3 Rename `Account health` to `Account`, add scroll container, and add search/filter/sort controls.
- [x] 3.4 Render dashboard account rows with Accounts-tab list layout style plus `5m/15m/1h/1d` usage chips.
- [x] 3.5 Update frontend tests for new dashboard rendering expectations.
