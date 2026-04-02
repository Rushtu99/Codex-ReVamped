# Security

Sensitive files that must stay out of git:

- `~/.codex/auth*.json`
- `~/.codex-lb/.env`
- `~/.codex-lb/store.db*`
- `~/.codex-lb/encryption.key`
- `~/.codex-revamped/accounts.seed.json`
- `~/.codex-revamped/runtime.env`

Operational guidance:

- treat the dashboard as a privileged local admin surface
- prefer LAN or VPN access only
- do not publish account bundles
- rotate credentials if bundle or key material was exposed

The account bundle is portable only when the matching `encryption.key` is preserved.
