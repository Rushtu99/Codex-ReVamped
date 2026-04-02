#!/bin/sh
set -eu

runtime_env_primary="${HOME}/.codex-revamped/runtime.env"
runtime_env_legacy="${HOME}/.codex-portable-setup/runtime.env"
portable_dir="${HOME}/.codex-revamped"

if [ -f "${runtime_env_primary}" ]; then
  runtime_env="${runtime_env_primary}"
elif [ -f "${runtime_env_legacy}" ]; then
  runtime_env="${runtime_env_legacy}"
  portable_dir="${HOME}/.codex-portable-setup"
else
  runtime_env="${runtime_env_primary}"
fi

codex_config="${HOME}/.codex/config.toml"
lb_env_example="${HOME}/.codex-lb/.env.example"
wrapper="${HOME}/bin/codex"
launcher="${HOME}/.local/bin/codex-revamped-start"
launcher_alias="${HOME}/.local/bin/codex-lb-start"
syncer="${HOME}/.local/bin/codex-account-sync"
omx_cli="${HOME}/.local/bin/omx"
oh_my_codex_cli="${HOME}/.local/bin/oh-my-codex"
accounts_bundle="${portable_dir}/accounts.seed.json"

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

for cmd in git uv awk sed node npm python; do
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

for path in "${runtime_env}" "${codex_config}" "${lb_env_example}" "${wrapper}" "${launcher}" "${launcher_alias}" "${syncer}"; do
  if [ -f "${path}" ]; then
    ok "file present: ${path}"
  else
    warn "file missing: ${path}"
  fi
done

if [ -f "${accounts_bundle}" ]; then
  ok "managed account bundle present: ${accounts_bundle}"
else
  warn "managed account bundle missing: ${accounts_bundle}"
fi

if [ -x "${omx_cli}" ]; then
  ok "omx wrapper present: ${omx_cli}"
else
  warn "omx wrapper missing"
fi

if [ -x "${oh_my_codex_cli}" ]; then
  ok "oh-my-codex wrapper present: ${oh_my_codex_cli}"
else
  warn "oh-my-codex wrapper missing"
fi

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

  if [ -n "${CODEX_OMX_BIN:-}" ] && [ -x "${CODEX_OMX_BIN}" ]; then
    ok "omx binary exists: ${CODEX_OMX_BIN}"
  else
    warn "omx binary missing or invalid in runtime metadata"
  fi
fi

if [ -f "${codex_config}" ] && grep -F 'base_url = "http://127.0.0.1:2455/backend-api/codex"' "${codex_config}" >/dev/null 2>&1; then
  ok "Codex config points at the local codex-lb proxy"
else
  warn "Codex config does not appear to target the local codex-lb proxy"
fi

printf '%s\n' "Doctor finished."
