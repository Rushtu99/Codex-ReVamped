# Architecture

Codex-ReVamped is built around `codex-lb`.

Runtime flow:

1. User runs `codex`.
2. The managed wrapper loads `~/.codex-revamped/runtime.env`.
3. If the standalone server is not already running, the wrapper starts `codex-revamped-start`.
4. `codex-revamped-start` launches `codex-lb`.
5. Codex reads `~/.codex/config.toml`.
6. Codex sends requests to `http://127.0.0.1:2455/backend-api/codex`.
7. `codex-lb` proxies upstream and serves the dashboard on the same port.

Supporting pieces:

- `overlays/codex-lb/` contains the branded frontend overlay
- `export-accounts.py` and `import-accounts.py` manage account bundle portability
- `templates/codex-account-sync.py` keeps account bundle state updated after dashboard changes
- `omx` is installed as the supported workflow layer on top of Codex

This package does not require `home-server`, nginx, or any separate gateway service.
