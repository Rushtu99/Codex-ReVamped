## Why
The OMX tab now surfaces a compact dashboard alongside command controls and raw command output, giving operators a quick view of:

- current OMX install metadata and runtime status (`available`, `version`, `reasoning`, `last checked`)
- which OMX workflows and operational references to run first (`ralplan`, `team`, `ultrawork/ult`, `team status`)
- what OMX sessions and workers are currently active, including one-line context/job summaries and heartbeat timestamps where available
- token usage visibility by session and best-effort worker summaries when exact worker token metrics are unavailable

Without this, users have to inspect runtime files and logs manually, which slows troubleshooting and execution handoff.

## What Changes
- add a descriptive OMX dashboard panel with:
  - runtime summary cards for install status, version, reasoning, last checked time, session count, and worker count
  - quick workflow skill references (one-line description + command)
  - live session and worker summaries (one-line context/job)
  - token analytics grouped by session and worker
- keep the allowlisted command controls and reasoning selector visible in the OMX tab
- keep the command output panel visible so the last command's stdout/stderr stays readable in the UI
- add `GET /api/omx/dashboard` to aggregate OMX runtime state/log metadata for the UI
- preserve existing OMX command controls (`/api/omx/overview`, `/api/omx/run`)
- keep the frontend resilient by falling back between `/api/omx/overview` and `/api/omx/dashboard` when one payload is unavailable

## Impact
- Backend: new OMX dashboard response schemas and aggregation service logic
- Frontend: OMX tab UI and typed API client for `/api/omx/dashboard`
- Tests: OMX backend integration coverage and OMX frontend integration flow updates
- Specs: `openspec/specs/frontend-architecture/spec.md`
