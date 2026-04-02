#!/data/data/com.termux/files/usr/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
overlay_root="${script_dir}/overlays/codex-lb"
target_root="${HOME}/.local/src/codex-lb"
frontend_dir="${target_root}/frontend"
runtime_env_primary="${HOME}/.codex-revamped/runtime.env"
runtime_env_legacy="${HOME}/.codex-portable-setup/runtime.env"

say() {
  printf '%s\n' "$*"
}

fail() {
  printf '%s\n' "$*" >&2
  exit 1
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "Required command not found: $1"
  fi
}

if [ ! -d "${overlay_root}" ]; then
  fail "UI overlay directory not found: ${overlay_root}"
fi

if [ ! -d "${target_root}" ]; then
  fail "Managed codex-lb source not found: ${target_root}"
fi

if [ ! -f "${frontend_dir}/package.json" ]; then
  fail "codex-lb frontend is missing: ${frontend_dir}"
fi

require_command python
require_command npm

frontend_install_and_build() {
  say "Installing frontend dependencies with npm"
  npm install --legacy-peer-deps
  say "Building frontend assets with npm"
  npm exec vite build
}

say "Applying CodexLB ReVamped UI overlay"
OVERLAY_ROOT="${overlay_root}" TARGET_ROOT="${target_root}" python - <<'PY'
from pathlib import Path
import os
import shutil

overlay_root = Path(os.environ["OVERLAY_ROOT"])
target_root = Path(os.environ["TARGET_ROOT"])

for source in overlay_root.rglob("*"):
    if source.is_dir():
        continue
    rel = source.relative_to(overlay_root)
    dest = target_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
PY

say "Building frontend assets"
cd "${frontend_dir}"
frontend_install_and_build

if pgrep -af '[/]codex-lb( |$)' >/dev/null 2>&1; then
  say "codex-lb is running; refreshed assets will be served on next request"
else
  say "codex-lb is not running; start it with codex or codex-lb-start"
fi

if [ -f "${runtime_env_primary}" ] || [ -f "${runtime_env_legacy}" ]; then
  say "Codex-ReVamped UI overlay applied successfully."
fi
