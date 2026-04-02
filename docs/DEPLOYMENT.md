# Deployment

Codex-ReVamped is intended to be hosted directly by `codex-lb`.

Default listener:

- `HOST=0.0.0.0`
- `PORT=2455`

Local start:

```sh
codex-revamped-start
```

Managed start through Codex:

```sh
codex
```

LAN access:

- open `http://HOST:2455/`
- API docs remain at `http://HOST:2455/docs`

Recommended deployment posture:

- keep the service on a trusted LAN or VPN
- do not expose the dashboard publicly without a reverse proxy and access control
- keep `~/.codex-lb/.env`, `~/.codex-lb/encryption.key`, and `~/.codex-revamped/accounts.seed.json` private
