# codex-portable-setup

Git-installable package for reproducing a Codex CLI plus `codex-lb` environment on Termux, Linux, macOS, and native Windows PowerShell.

This package versions only portable setup:

- wrapper scripts
- `~/.codex/config.toml`
- `~/.codex-lb/.env.example`
- pinned `codex-lb` install metadata
- install and verification scripts

It does not version:

- `~/.codex/auth*.json`
- `~/.codex/history.jsonl`
- `~/.codex/sessions/`
- `~/.codex` sqlite state/log/cache files
- `~/.codex-lb/.env`
- `~/.codex-lb/store.db*`
- `~/.codex-lb/encryption.key`
- PID or runtime log files

## Quick Start

POSIX shells:

```sh
git clone <your-new-remote> codex-portable-setup
cd codex-portable-setup
./install.sh
./doctor.sh
```

Windows PowerShell:

```powershell
git clone <your-new-remote> codex-portable-setup
Set-Location codex-portable-setup
.\install.ps1
.\doctor.ps1
```

## What The Installer Does

- installs or updates `codex-lb` from the pinned upstream Git ref
- on Termux, reapplies a compatibility overlay to `codex-lb` before install so the package avoids Android-incompatible PostgreSQL wheels
- creates managed runtime metadata in `~/.codex-portable-setup/runtime.env`
- installs the `codex` wrapper into `~/bin` on POSIX and `%USERPROFILE%\bin` on Windows
- installs the `codex-lb-start` launcher
- writes `~/.codex/config.toml`
- writes `~/.codex-lb/.env.example`
- adds the wrapper directory to `PATH` if needed

## Manual Steps After Install

1. Copy `~/.codex-lb/.env.example` to `~/.codex-lb/.env` if you want non-default `codex-lb` settings.
2. Start Codex once or run the launcher directly.
3. Open the `codex-lb` dashboard and add/sign in your accounts.
4. Verify `codex` routes through `http://127.0.0.1:2455/backend-api/codex`.

## Publishing

See [docs/PUBLISHING.md](docs/PUBLISHING.md) for `git init`, first commit, and remote setup.
