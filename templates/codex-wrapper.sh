#!/bin/sh
set -eu

runtime_env="${HOME}/.codex-portable-setup/runtime.env"

if [ ! -f "${runtime_env}" ]; then
  printf '%s\n' "codex-portable-setup runtime metadata is missing: ${runtime_env}" >&2
  printf '%s\n' "Run install.sh from the package repo first." >&2
  exit 1
fi

# shellcheck disable=SC1090
. "${runtime_env}"

lb_dir="${CODEX_LB_DIR:-${HOME}/.codex-lb}"
pid_file="${lb_dir}/codex-lb.pid"
log_file="${lb_dir}/service.log"
launcher="${CODEX_LB_LAUNCHER:-}"
real_codex="${CODEX_REAL_BIN:-}"

if [ -z "${launcher}" ] || [ ! -x "${launcher}" ]; then
  printf '%s\n' "codex-lb launcher not found: ${launcher}" >&2
  exit 1
fi

if [ -z "${real_codex}" ] || [ ! -x "${real_codex}" ]; then
  printf '%s\n' "Real codex binary not found: ${real_codex}" >&2
  printf '%s\n' "Re-run install.sh after installing the real codex binary." >&2
  exit 1
fi

mkdir -p "${lb_dir}"

export HOST="${HOST:-${CODEX_HOST_DEFAULT:-0.0.0.0}}"
export PORT="${PORT:-${CODEX_PORT_DEFAULT:-2455}}"

if ! pgrep -f "[/]codex-lb( |$)" >/dev/null 2>&1; then
  nohup "${launcher}" >>"${log_file}" 2>&1 &
  echo "$!" > "${pid_file}"
fi

exec "${real_codex}" "$@"
