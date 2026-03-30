#!/bin/sh
set -eu

runtime_env="${HOME}/.codex-portable-setup/runtime.env"
codex_config="${HOME}/.codex/config.toml"
lb_env_example="${HOME}/.codex-lb/.env.example"
wrapper="${HOME}/bin/codex"
launcher="${HOME}/.local/bin/codex-lb-start"

ok() {
  printf 'OK: %s\n' "$*"
}

warn() {
  printf 'WARN: %s\n' "$*"
}

fail() {
  printf 'FAIL: %s\n' "$*"
  exit 1
}

for cmd in git uv awk sed; do
  if command -v "${cmd}" >/dev/null 2>&1; then
    ok "command available: ${cmd}"
  else
    fail "missing command: ${cmd}"
  fi
done

if command -v codex >/dev/null 2>&1; then
  ok "codex is available on PATH"
else
  warn "codex is not currently available on PATH"
fi

for path in "${runtime_env}" "${codex_config}" "${lb_env_example}" "${wrapper}" "${launcher}"; do
  if [ -f "${path}" ]; then
    ok "file present: ${path}"
  else
    warn "file missing: ${path}"
  fi
done

if [ -f "${runtime_env}" ]; then
  # shellcheck disable=SC1090
  . "${runtime_env}"
  if [ -n "${CODEX_REAL_BIN:-}" ] && [ -x "${CODEX_REAL_BIN}" ]; then
    ok "real codex binary exists: ${CODEX_REAL_BIN}"
  else
    warn "real codex binary missing or invalid in runtime metadata"
  fi

  if [ -n "${CODEX_LB_BIN:-}" ] && [ -x "${CODEX_LB_BIN}" ]; then
    ok "codex-lb binary exists: ${CODEX_LB_BIN}"
  else
    warn "codex-lb binary missing or invalid in runtime metadata"
  fi
fi

if [ -f "${codex_config}" ] && grep -F 'base_url = "http://127.0.0.1:2455/backend-api/codex"' "${codex_config}" >/dev/null 2>&1; then
  ok "Codex config points at the local codex-lb proxy"
else
  warn "Codex config does not appear to target the local codex-lb proxy"
fi

printf '%s\n' "Doctor finished."
