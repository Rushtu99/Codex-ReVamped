## Why

Dashboard operators currently split account triage across multiple widgets and cannot quickly compare short-window usage pressure per account. This slows decision-making when rotating accounts, diagnosing quota pressure, or prioritizing follow-up actions.

## What Changes

- Replace the four separate account-health counters with a single compact status card in `H/W/L/A` slash format.
- Rename dashboard `Account health` section to `Account`, render it as an internal scroll container, and keep the row-level action buttons and list styling aligned with the Accounts tab.
- Add dashboard-side account search/filter/sort controls.
- Switch dashboard account rows to the same visual list layout style used in the Accounts tab.
- Extend dashboard overview payload with per-account rolling usage windows (`last5m`, `last15m`, `last1h`, `last1d`) containing request count and total tokens.

## Impact

- Backend: dashboard response schema + aggregation logic for rolling per-account usage.
- Frontend: dashboard overview schema, account list rendering, and dashboard integration tests.
- Specs: `openspec/specs/frontend-architecture/spec.md`.
