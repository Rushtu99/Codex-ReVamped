#!/bin/sh
set -eu

runtime_env="${HOME}/.codex-portable-setup/runtime.env"

if [ ! -f "${runtime_env}" ]; then
  printf '%s\n' "codex-portable-setup runtime metadata is missing: ${runtime_env}" >&2
  exit 1
fi

# shellcheck disable=SC1090
. "${runtime_env}"

config_file="${CODEX_LB_ENV_FILE:-${HOME}/.codex-lb/.env}"
launcher="${CODEX_LB_BIN:-}"

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

export HOST="${HOST:-${CODEX_HOST_DEFAULT:-0.0.0.0}}"
export PORT="${PORT:-${CODEX_PORT_DEFAULT:-2455}}"

exec "${launcher}" "$@"
