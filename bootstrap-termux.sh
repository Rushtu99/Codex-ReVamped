#!/data/data/com.termux/files/usr/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
install_script="${script_dir}/install.sh"
doctor_script="${script_dir}/doctor.sh"
import_accounts_script="${script_dir}/import-accounts.py"
ui_overlay_script="${script_dir}/apply-ui-overlay.sh"
env_file="${HOME}/.codex-lb/.env"
env_example_file="${HOME}/.codex-lb/.env.example"
launcher_file="${HOME}/.local/bin/codex-lb-start"
wrapper_file="${HOME}/bin/codex"
runtime_env="${HOME}/.codex-portable-setup/runtime.env"
accounts_bundle="${HOME}/.codex-portable-setup/accounts.seed.json"

say() {
  printf '%s\n' "$*"
}

fail() {
  printf '%s\n' "$*" >&2
  exit 1
}

require_termux() {
  if [ "${PREFIX:-}" != "/data/data/com.termux/files/usr" ]; then
    fail "This bootstrap script is intended for Termux."
  fi
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "Required command not found: $1"
  fi
}

ensure_pkg() {
  pkg_name=$1
  if ! dpkg -s "${pkg_name}" >/dev/null 2>&1; then
    say "Installing Termux package: ${pkg_name}"
    pkg install -y "${pkg_name}"
  fi
}

ensure_profile_path() {
  managed_line='export PATH="$HOME/bin:$HOME/.local/bin:$PATH"'
  for profile in "${HOME}/.profile" "${HOME}/.bashrc" "${HOME}/.zprofile"; do
    if [ ! -f "${profile}" ]; then
      : > "${profile}"
    fi
    if ! grep -F "${managed_line}" "${profile}" >/dev/null 2>&1; then
      {
        printf '\n'
        printf '# Added by codex-portable-setup bootstrap\n'
        printf '%s\n' "${managed_line}"
      } >> "${profile}"
    fi
  done
}

ensure_env_override() {
  mkdir -p "${HOME}/.codex-lb"
  if [ ! -f "${env_file}" ]; then
    cp "${env_example_file}" "${env_file}"
  fi

  python - <<'PY'
from pathlib import Path

env_path = Path.home() / ".codex-lb" / ".env"
lines = env_path.read_text().splitlines()
keys = {"HOST": "0.0.0.0", "PORT": "2455"}
seen = set()
out = []

for line in lines:
    if "=" in line and not line.lstrip().startswith("#"):
        key, _, _ = line.partition("=")
        if key in keys:
            out.append(f"{key}={keys[key]}")
            seen.add(key)
            continue
    out.append(line)

for key, value in keys.items():
    if key not in seen:
        out.append(f"{key}={value}")

env_path.write_text("\n".join(out) + "\n")
PY
}

have_managed_wrapper() {
  [ -f "${wrapper_file}" ] && grep -q 'codex-portable-setup runtime metadata' "${wrapper_file}" 2>/dev/null
}

have_managed_launcher() {
  [ -f "${launcher_file}" ] && grep -q 'codex-portable-setup runtime metadata' "${launcher_file}" 2>/dev/null
}

have_runtime_env() {
  [ -f "${runtime_env}" ] && grep -q '^CODEX_LB_BIN=' "${runtime_env}" 2>/dev/null
}

have_valid_codex_config() {
  [ -f "${HOME}/.codex/config.toml" ] && grep -q 'base_url = "http://127.0.0.1:2455/backend-api/codex"' "${HOME}/.codex/config.toml" 2>/dev/null
}

have_complete_managed_setup() {
  have_runtime_env &&
  have_managed_wrapper &&
  have_managed_launcher &&
  have_valid_codex_config &&
  [ -f "${env_example_file}" ]
}

detect_host_ip() {
  if command -v ifconfig >/dev/null 2>&1; then
    ifconfig wlan0 2>/dev/null | awk '/inet / { print $2; exit }'
  fi
}

start_codex_lb() {
  if pgrep -af '[/]codex-lb( |$)' >/dev/null 2>&1; then
    say "codex-lb already running; keeping existing process"
    return 0
  fi

  rm -f "${HOME}/.codex-lb/codex-lb.pid"
  nohup "${launcher_file}" >>"${HOME}/.codex-lb/service.log" 2>&1 &
  sleep 2
  pgrep -af '[/]codex-lb( |$)' >/dev/null 2>&1 || fail "codex-lb did not stay running. Check ~/.codex-lb/service.log"
}

verify_http() {
  python - <<'PY'
import urllib.request
for url in ["http://127.0.0.1:2455/", "http://127.0.0.1:2455/docs"]:
    with urllib.request.urlopen(url, timeout=5) as response:
        print(f"{url} {response.status} {response.getheader('content-type')}")
PY
}

import_accounts_from_config() {
  if [ ! -f "${accounts_bundle}" ]; then
    say "No managed account bundle found; skipping account import"
    return 0
  fi

  say "Importing saved codex-lb accounts from ${accounts_bundle}"
  python "${import_accounts_script}"
}

require_termux

ensure_pkg git
ensure_pkg uv
ensure_pkg python
ensure_pkg nodejs
ensure_pkg rust
ensure_pkg clang
ensure_pkg pkg-config
ensure_pkg openssl
ensure_pkg libffi

require_command git
require_command uv
require_command python
require_command node
require_command npm

if ! command -v codex >/dev/null 2>&1; then
  fail "Codex CLI is not installed yet. Install the real codex binary first, then rerun this script."
fi

ensure_profile_path

if have_complete_managed_setup; then
  say "Managed codex/codex-lb setup already present; skipping reinstall"
else
  say "Running managed codex-portable-setup installer"
  "${install_script}"
fi

ensure_env_override

say "Applying CodexLB ReVamped UI"
"${ui_overlay_script}"

say "Running portability doctor"
"${doctor_script}"

say "Starting codex-lb on 0.0.0.0:2455"
start_codex_lb

say "Verifying local HTTP endpoints"
verify_http

say "Syncing saved accounts from config"
import_accounts_from_config

host_ip=$(detect_host_ip || true)

say ""
say "Bootstrap complete."
say "Managed wrapper: ${wrapper_file}"
say "Managed launcher: ${launcher_file}"
say "LAN listener: 0.0.0.0:2455"
if [ -n "${host_ip}" ]; then
  say "Open codex-lb UI from another device: http://${host_ip}:2455/"
  say "Open docs from another device:       http://${host_ip}:2455/docs"
else
  say "Could not detect wlan0 IP automatically. Run: ifconfig wlan0 | awk '/inet / { print \$2; exit }'"
fi
say "Running 'codex' will auto-start codex-lb in future sessions if it is not already running."
