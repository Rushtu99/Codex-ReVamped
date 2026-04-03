## ADDED Requirements

### Requirement: Dashboard account health summary uses compact slash format

The Dashboard account-health summary SHALL render as one compact card with four colorized counters in `Healthy / Watchlist / Limited / Action` order.

#### Scenario: Compact account-health summary is rendered
- **WHEN** the Dashboard page is loaded
- **THEN** the summary shows a single slash-formatted `H/W/L/A` status card instead of four separate cards
- **AND** each counter is visually color-coded to its severity band

### Requirement: Dashboard Account section supports internal scrolling and controls
The Dashboard Account section SHALL be titled `Account`, render account rows inside an internal scroll container, and provide account-level search/filter/sort controls. The sort control SHALL offer `Risk`, `Name A-Z`, `Weekly remaining low-high`, and `Last 1d requests high-low` ordering.

#### Scenario: Account section title and scrolling behavior
- **WHEN** the Dashboard page renders account rows
- **THEN** the section heading is `Account`
- **AND** account rows render inside a bounded scrollable container

#### Scenario: Account filter and sort controls
- **WHEN** an operator changes search text, status filter, plan filter, or sort order
- **THEN** the Account row list updates client-side without triggering a dashboard overview mutation

### Requirement: Dashboard account rows preserve list-style actions and rolling usage chips
The Dashboard Account rows SHALL use the same list-style card treatment as the Accounts tab, including a plan badge, status badge, weekly remaining bar, and a primary action button that reads `Details`, `Resume`, or `Re-auth` based on account status. Each row SHALL also show the `5m`, `15m`, `1h`, and `1d` rolling usage chips from the overview payload beneath the row header.

#### Scenario: Dashboard account row is rendered
- **WHEN** the Dashboard Account list renders an account
- **THEN** the row shows the plan badge and status badge
- **AND** the row shows the weekly remaining bar and the correct primary action label
- **AND** the row shows the `5m`, `15m`, `1h`, and `1d` usage chips
- **AND** duplicate account IDs are labeled with the compact account ID marker when required

### Requirement: Dashboard overview includes rolling per-account usage windows

`GET /api/dashboard/overview` SHALL include rolling per-account usage windows keyed by account id with windows `last5m`, `last15m`, `last1h`, and `last1d`; each window SHALL expose `requestCount` and `totalTokens`.

#### Scenario: Rolling per-account usage map is returned
- **WHEN** `GET /api/dashboard/overview` is called
- **THEN** the payload includes `accountRollingUsage[accountId]` entries
- **AND** each entry contains `last5m`, `last15m`, `last1h`, and `last1d`
- **AND** each window object contains `requestCount` and `totalTokens`

#### Scenario: Dashboard account row shows rolling usage windows
- **WHEN** the Dashboard Account list renders an account row
- **THEN** the row shows `5m`, `15m`, `1h`, and `1d` usage chips
- **AND** each chip includes requests and tokens for that window
