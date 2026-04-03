## ADDED Requirements
### Requirement: OMX tab surfaces runtime overview cards and resilient payload fallback
The OMX tab MUST display runtime overview cards for install status, version, reasoning level, last checked time, current session count, and current worker count. The tab MUST continue to render these cards and the rest of the OMX surface when either `/api/omx/overview` or `/api/omx/dashboard` is unavailable, so long as the alternate payload can be parsed into the matching schema.

#### Scenario: Overview endpoint is unavailable
- **WHEN** the OMX page loads and `/api/omx/overview` returns a 404 response
- **THEN** the tab renders the dashboard payload as its overview fallback
- **AND** the session, worker, and token sections remain visible

#### Scenario: Dashboard endpoint is unavailable
- **WHEN** the OMX page loads and `/api/omx/dashboard` returns a 404 response
- **THEN** the tab renders the overview payload as its dashboard fallback
- **AND** the install, version, reasoning, and command output cards remain visible

### Requirement: OMX tab provides quick workflow references
The OMX tab MUST display a quick-reference section for core OMX workflows with one-line descriptions and executable command examples. At minimum, this section MUST include `ralplan`, `team`, `ultrawork` (alias `ult`), and `team status` references and show the associated command text.

#### Scenario: Operator opens OMX tab
- **WHEN** the dashboard loads the OMX tab
- **THEN** it renders a quick-reference panel with workflow labels, one-line descriptions, and command examples for `ralplan`, `team`, `ultrawork` (alias `ult`), and `team status`

### Requirement: OMX tab exposes live runtime sessions and workers
The OMX tab MUST render session-level and worker-level runtime summaries from OMX runtime state sources. Each session row MUST include a one-line context, and each worker row MUST include a one-line job description.

#### Scenario: Active session and worker state exists
- **WHEN** OMX runtime state includes session and worker records
- **THEN** the OMX tab displays session rows with status, context line, timestamps, and source
- **AND** it displays worker rows with team, worker id, status, one-line job summary, and heartbeat timestamp when available

### Requirement: OMX tab exposes allowlisted command controls
The OMX tab MUST render allowlisted command controls for `status`, `version`, `doctor`, `doctor_team`, `cleanup_dry_run`, `cleanup`, `cancel`, and `reasoning_get`. The tab MUST also render a reasoning-level selector and an action for `reasoning_set` that submits one of `low`, `medium`, `high`, or `xhigh`. The OMX command-output panel MUST remain visible and show the binary path, runtime env path, runtime dir, status snapshot, and the most recent command stdout/stderr.

#### Scenario: Operator runs an allowlisted OMX command
- **WHEN** the operator selects an allowlisted command control
- **THEN** the OMX tab submits the matching OMX action and refreshes overview and dashboard data after a successful run

#### Scenario: Operator updates reasoning level
- **WHEN** the operator chooses a reasoning level and applies it
- **THEN** the OMX tab submits `reasoning_set` with the selected level

### Requirement: OMX tab provides per-session and per-worker token analytics
The OMX tab MUST display token usage grouped by session and by worker. Session token values MUST be shown when available; worker token values MUST remain renderable even when unavailable.

#### Scenario: Worker tokens are unavailable
- **WHEN** OMX runtime state does not provide exact worker token metrics
- **THEN** the OMX tab still renders worker token rows
- **AND** unavailable token fields are shown as an explicit unavailable value (for example `N/A`)
- **AND** the UI displays a note indicating worker token metrics are best-effort/unavailable
