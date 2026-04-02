# Codex-ReVamped

Codex-ReVamped is a standalone `codex-lb` distribution for running OpenAI Codex through a custom local gateway with a branded dashboard and an `oh-my-codex` (`omx`) workflow layer.

This repo is intentionally standalone:

- no `home-server` dependency
- no nginx dependency
- no reverse-proxy requirement
- no dashboard wrapper service outside `codex-lb`

The core product is:

- Codex CLI
- custom `codex-lb` setup
- Codex ReVamped UI overlay
- OMX (`oh-my-codex`) setup
- optional account bundle import/export and background sync

## What It Does

- installs and configures `codex-lb`
- points Codex at `http://127.0.0.1:2455/backend-api/codex`
- starts the standalone Codex-ReVamped server with `codex-revamped-start`
- keeps `codex` as a managed wrapper that auto-starts the server if needed
- exposes the dashboard directly on port `2455`
- installs OMX and keeps Codex configured to use the local `codex-lb` gateway
- supports importing and exporting saved `codex-lb` accounts

## Runtime Layout

Runtime state managed by this package lives under:

- `~/.codex-revamped`

Codex and `codex-lb` still keep their own runtime data in:

- `~/.codex`
- `~/.codex-lb`

Compatibility:

- existing installs that still reference `~/.codex-portable-setup` continue to work
- new installs use `~/.codex-revamped`
- `codex-lb-start` remains as a compatibility alias for `codex-revamped-start`

## Quick Start

### Termux / Android

```sh
git clone git@github.com:Rushtu99/Codex-ReVamped.git ~/.codex-revamped
cd ~/.codex-revamped
./bootstrap-termux.sh
```

Then open:

```text
http://PHONE_IP:2455/
```

### Linux / macOS

Prerequisites:

- Codex CLI already installed
- `git`
- `uv`
- `python3`
- `node` and `npm`

Install:

```sh
git clone git@github.com:Rushtu99/Codex-ReVamped.git ~/.codex-revamped
cd ~/.codex-revamped
./install.sh
./doctor.sh
```

Start the standalone server:

```sh
codex-revamped-start
```

Or just run:

```sh
codex
```

### Windows PowerShell

Prerequisites:

- Codex CLI already installed
- `git`
- `uv`
- Python
- Node.js with `npm`

Install:

```powershell
git clone git@github.com:Rushtu99/Codex-ReVamped.git $HOME\.codex-revamped
Set-Location $HOME\.codex-revamped
.\install.ps1
.\doctor.ps1
```

Start the standalone server:

```powershell
codex-revamped-start.ps1
```

## Primary Commands

- `codex`
  Managed wrapper. Starts Codex-ReVamped if needed, then launches the real Codex CLI.

- `codex-revamped-start`
  Starts the standalone `codex-lb` server directly.

- `codex-lb-start`
  Compatibility alias for `codex-revamped-start`.

- `omx`
  `oh-my-codex` CLI for workflow-driven Codex sessions.

## Accounts

This repo supports a managed account bundle:

- `~/.codex-revamped/accounts.seed.json`

Use it to move or restore `codex-lb` account state.

Export:

```sh
cd ~/.codex-revamped
python ./export-accounts.py
```

Import:

```sh
cd ~/.codex-revamped
python ./import-accounts.py
```

Important:

- the bundle contains encrypted account state
- do not commit it
- do not publish it
- keep the matching `~/.codex-lb/encryption.key` private

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Migration](docs/MIGRATION.md)
- [Security](docs/SECURITY.md)

## License

MIT. See [LICENSE](LICENSE).
