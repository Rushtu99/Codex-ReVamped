# codex-portable-setup

Portable setup package for reproducing a Codex CLI plus `codex-lb` environment on Termux, with the `codex-lb` UI exposed to your local network.

This package versions only the setup layer:

- wrapper scripts
- `~/.codex/config.toml`
- `~/.codex-lb/.env.example`
- `~/.codex-portable-setup/accounts.seed.json`
- the `CodexLB ReVamped` frontend overlay under `overlays/codex-lb/`
- pinned `codex-lb` install metadata
- install and verification scripts

It does not version:

- `~/.codex/auth*.json`
- `~/.codex/history.jsonl`
- `~/.codex/sessions/`
- `~/.codex-lb/.env`
- `~/.codex-lb/store.db*`
- `~/.codex-lb/encryption.key`
- PID or runtime log files

## What You Get

- running `codex` auto-starts `codex-lb` if it is not already running
- Codex routes through the local `codex-lb` proxy at `http://127.0.0.1:2455/backend-api/codex`
- the `codex-lb` dashboard is exposed on your LAN at `http://PHONE_IP:2455/`
- saved `codex-lb` accounts stay in `~/.codex-lb/store.db`
- saved `codex-lb` accounts can also be reseeded from `~/.codex-portable-setup/accounts.seed.json`
- the upstream frontend is reskinned as `CodexLB ReVamped`

## One-Command Bootstrap

If Codex is already installed on the phone, you can do the whole Termux setup with:

```sh
cd ~/.codex-portable-setup
./bootstrap-termux.sh
```

That script:

- installs required Termux packages if missing
- runs the managed installer only when the wrapper/runtime/config layer is missing or stale
- forces `HOST=0.0.0.0` and `PORT=2455` in `~/.codex-lb/.env`
- applies the tracked `CodexLB ReVamped` frontend overlay
- builds the frontend inside `~/.local/src/codex-lb/frontend` with `npm`
- runs `./doctor.sh`
- starts `codex-lb` only if it is not already running
- imports saved accounts from `accounts.seed.json` as the final managed data step
- prints the LAN URL to open from your PC

If Codex itself is not installed yet, the script stops with a clear error and leaves the rest untouched.

### Re-running safely

`bootstrap-termux.sh` is intended to be safe to rerun.

It skips a full reinstall when all of these are already correct:

- `~/.codex-portable-setup/runtime.env` exists
- `~/bin/codex` is the managed wrapper
- `~/.local/bin/codex-lb-start` is the managed launcher
- `~/.codex/config.toml` points Codex at `127.0.0.1:2455/backend-api/codex`
- `~/.codex-lb/.env.example` exists

It still repairs the live `~/.codex-lb/.env` listener settings and runs the doctor checks on every run.

## UI Maintenance

### Automated

`bootstrap-termux.sh` now includes the UI step automatically. If you rerun bootstrap, it reapplies the tracked ReVamped frontend before validating the install.

### Manual UI-only update

If `codex-lb` is already installed and you only want to refresh the UI:

```sh
cd ~/.codex-portable-setup
./apply-ui-overlay.sh
```

That script:

- copies the tracked overlay files from `overlays/codex-lb/` into `~/.local/src/codex-lb`
- installs frontend dependencies with `npm`
- rebuilds the production frontend

This path is intended for people who do not want to reinstall the wrapper/runtime setup and only want the latest `CodexLB ReVamped` UI.

## Exact Install Steps

### 1. Install Codex first

Make sure the real Codex CLI exists before installing the wrapper layer:

```sh
command -v codex
codex --version
```

On this machine the real binary is:

```sh
/data/data/com.termux/files/usr/bin/codex
```

### 2. Install the portable wrapper package

```sh
cd ~/.codex-portable-setup
./install.sh
./doctor.sh
```

The installer:

- updates the pinned upstream `codex-lb` checkout in `~/.local/src/codex-lb`
- writes `~/.codex-portable-setup/runtime.env`
- installs the managed `codex` wrapper into `~/bin/codex`
- installs the managed launcher into `~/.local/bin/codex-lb-start`
- writes `~/.codex/config.toml`
- writes `~/.codex-lb/.env.example`

### 2a. Apply the UI manually if you are not using bootstrap

If you are doing a manual install instead of bootstrap, run:

```sh
cd ~/.codex-portable-setup
./apply-ui-overlay.sh
```

This is the step that turns the upstream `codex-lb` frontend into `CodexLB ReVamped`.

### 3. Make sure your PATH prefers the managed wrapper

The shell should resolve:

```sh
command -v codex
```

to:

```sh
~/bin/codex
```

If not, restart the shell or ensure your profile includes:

```sh
export PATH="$HOME/bin:$HOME/.local/bin:$PATH"
```

### 4. Configure `codex-lb` for LAN access

The live file is:

```sh
~/.codex-lb/.env
```

For local-network access, keep:

```env
HOST=0.0.0.0
PORT=2455
```

That makes the dashboard reachable from other devices on the same network.

### 5. Start `codex-lb`

You can start it directly once:

```sh
~/.local/bin/codex-lb-start
```

or simply run:

```sh
codex
```

The managed wrapper at `~/bin/codex` checks whether `codex-lb` is already running. If not, it starts `codex-lb-start` first and then execs the real Codex binary.

### 6. Open the `codex-lb` UI from your PC

Find the phone IP:

```sh
ifconfig wlan0 | awk '/inet / { print $2; exit }'
```

Then from your PC browser open:

```text
http://PHONE_IP:2455/
```

Swagger docs stay at:

```text
http://PHONE_IP:2455/docs
```

### 7. Add or reuse your saved accounts

The `codex-lb` account database is:

```sh
~/.codex-lb/store.db
```

If that file already exists, your previously saved accounts and usage history are reused automatically.

This portable setup also supports a managed account bundle:

```sh
~/.codex-portable-setup/accounts.seed.json
```

That file stores:

- account metadata
- encrypted account token blobs
- the matching `codex-lb` encryption key

Export the current saved accounts into the managed bundle with:

```sh
cd ~/.codex-portable-setup
python ./export-accounts.py
```

Import them manually with:

```sh
cd ~/.codex-portable-setup
python ./import-accounts.py
```

`bootstrap-termux.sh` now runs that import automatically at the end when `accounts.seed.json` exists.

Important:

- the bundle contains sensitive encrypted account state
- keep it private
- do not commit it to a public repo
- the importer refuses to overwrite a different existing `~/.codex-lb/encryption.key`

### 8. Verify Codex is actually using `codex-lb`

The Codex config file should contain:

```toml
[model_providers.codex-lb]
base_url = "http://127.0.0.1:2455/backend-api/codex"
wire_api = "responses"
supports_websockets = true
requires_openai_auth = true
```

The file is:

```sh
~/.codex/config.toml
```

## Local Network Integration Notes

- Codex itself still talks to `127.0.0.1:2455`, which is correct and should not be changed.
- The dashboard/UI is visible to the LAN because `codex-lb` binds to `0.0.0.0`.
- If your PC still cannot see it, the next thing to check is Android or Termux firewall/network policy, not the Codex config.
- If you are SSHed into the phone and only terminal apps are visible, browser UI access from the PC still requires the phone to listen on the Wi‑Fi interface, which is why `HOST=0.0.0.0` matters.

## Verification Commands

Run these on the phone:

```sh
cd ~/.codex-portable-setup
./doctor.sh
./apply-ui-overlay.sh
command -v codex
pgrep -af '[/]codex-lb( |$)'
python - <<'PY'
import urllib.request
for url in [
    'http://127.0.0.1:2455/',
    'http://127.0.0.1:2455/docs',
]:
    with urllib.request.urlopen(url, timeout=5) as r:
        print(url, r.status, r.getheader('content-type'))
PY
```

Run this on your PC:

```text
http://PHONE_IP:2455/
```

## Troubleshooting

### `codex` does not start `codex-lb`

Check:

```sh
command -v codex
sed -n '1,120p' ~/bin/codex
sed -n '1,120p' ~/.local/bin/codex-lb-start
sed -n '1,120p' ~/.codex-portable-setup/runtime.env
```

### `codex-lb` UI is not visible on the PC

Check:

```sh
pgrep -af '[/]codex-lb( |$)'
sed -n '1,80p' ~/.codex-lb/.env
ifconfig wlan0 | awk '/inet / { print $2; exit }'
```

Make sure:

- `HOST=0.0.0.0`
- `PORT=2455`
- you are using the phone Wi‑Fi IP on the PC

### The UI looks like upstream `codex-lb` instead of `CodexLB ReVamped`

Run:

```sh
cd ~/.codex-portable-setup
./apply-ui-overlay.sh
```

Then hard-refresh the browser. The active frontend source is `~/.local/src/codex-lb/frontend`, and the built assets are emitted to `~/.local/src/codex-lb/app/static`.

### Saved accounts disappeared

Check the database:

```sh
ls -lh ~/.codex-lb/store.db*
```

This package does not delete `store.db`, so if the file is still present your accounts should still be there.
