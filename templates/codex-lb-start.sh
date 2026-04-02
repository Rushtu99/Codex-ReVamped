#!/bin/sh
set -eu

runtime_env_primary="${HOME}/.codex-revamped/runtime.env"
runtime_env_legacy="${HOME}/.codex-portable-setup/runtime.env"

if [ -f "${runtime_env_primary}" ]; then
  runtime_env="${runtime_env_primary}"
elif [ -f "${runtime_env_legacy}" ]; then
  runtime_env="${runtime_env_legacy}"
else
  printf '%s\n' "Codex-ReVamped runtime metadata is missing: ${runtime_env_primary}" >&2
  exit 1
fi

# shellcheck disable=SC1090
. "${runtime_env}"
export CODEX_RUNTIME_ENV="${runtime_env}"
portable_setup_dir="${CODEX_PORTABLE_DIR:-$(dirname "${runtime_env}")}"
export CODEX_PORTABLE_SETUP_DIR="${portable_setup_dir}"

config_file="${CODEX_LB_ENV_FILE:-${HOME}/.codex-lb/.env}"
launcher="${CODEX_LB_BIN:-}"
syncer="${CODEX_ACCOUNT_SYNCER:-}"

if [ -f "${config_file}" ]; then
  set -a
  # shellcheck disable=SC1090
  . "${config_file}"
  set +a
fi

if [ -z "${launcher}" ] || [ ! -x "${launcher}" ]; then
  printf '%s\n' "codex-lb binary not found: ${launcher}" >&2
  printf '%s\n' "Re-run install.sh after uv installs codex-lb." >&2
  exit 1
fi

export HOST="${HOST:-${CODEX_HOST_DEFAULT:-127.0.0.1}}"
export PORT="${PORT:-${CODEX_PORT_DEFAULT:-2455}}"

if [ -n "${syncer}" ] && [ -x "${syncer}" ] && ! pgrep -f "[/]codex-account-sync( |$)" >/dev/null 2>&1; then
  nohup "${syncer}" >>"${HOME}/.codex-lb/service.log" 2>&1 &
fi

exec "${launcher}" "$@"
