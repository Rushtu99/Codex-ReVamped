#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
manifest_file="${script_dir}/manifest/versions.env"

if [ ! -f "${manifest_file}" ]; then
  printf '%s\n' "Manifest not found: ${manifest_file}" >&2
  exit 1
fi

# shellcheck disable=SC1090
. "${manifest_file}"

target_bin_dir="${HOME}/bin"
launcher_dir="${HOME}/.local/bin"
managed_source_dir="${HOME}/.local/src/codex-lb"
codex_dir="${HOME}/.codex"
lb_dir="${HOME}/.codex-lb"
runtime_dir="${HOME}/.codex-portable-setup"
runtime_env="${runtime_dir}/runtime.env"
codex_config_file="${codex_dir}/config.toml"
lb_env_example_file="${lb_dir}/.env.example"
wrapper_file="${target_bin_dir}/codex"
launcher_file="${launcher_dir}/codex-lb-start"
profile_managed_line='export PATH="$HOME/bin:$PATH"'

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

detect_platform() {
  if [ -n "${TERMUX_VERSION:-}" ] || [ "${PREFIX:-}" = "/data/data/com.termux/files/usr" ] || [ "$(uname -o 2>/dev/null || true)" = "Android" ]; then
    printf '%s\n' "termux"
    return 0
  fi

  printf '%s\n' "posix"
}

is_wrapper_candidate() {
  candidate=$1

  if [ ! -f "${candidate}" ]; then
    return 1
  fi

  if grep -E 'codex-lb-start|real_codex=|codex-portable-setup runtime metadata' "${candidate}" >/dev/null 2>&1; then
    return 0
  fi

  return 1
}

resolve_real_codex() {
  if [ -f "${runtime_env}" ]; then
    # shellcheck disable=SC1090
    . "${runtime_env}"
    if [ -n "${CODEX_REAL_BIN:-}" ] && [ -x "${CODEX_REAL_BIN}" ] && [ "${CODEX_REAL_BIN}" != "${wrapper_file}" ]; then
      printf '%s\n' "${CODEX_REAL_BIN}"
      return 0
    fi
  fi

  if command -v which >/dev/null 2>&1; then
    candidates=$(which -a codex 2>/dev/null | awk '!seen[$0]++' || true)
    if [ -n "${candidates}" ]; then
      while IFS= read -r candidate; do
        if [ -n "${candidate}" ] && [ "${candidate}" != "${wrapper_file}" ] && [ -x "${candidate}" ] && ! is_wrapper_candidate "${candidate}"; then
          printf '%s\n' "${candidate}"
          return 0
        fi
      done <<EOF
${candidates}
EOF
    fi
  fi

  for candidate in \
    /data/data/com.termux/files/usr/bin/codex \
    /opt/homebrew/bin/codex \
    /usr/local/bin/codex \
    /usr/bin/codex
  do
    if [ -x "${candidate}" ] && [ "${candidate}" != "${wrapper_file}" ] && ! is_wrapper_candidate "${candidate}"; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done

  fail "Could not resolve the real codex binary. Install Codex first, or remove the managed wrapper from PATH and re-run install.sh."
}

resolve_codex_lb_bin() {
  if command -v codex-lb >/dev/null 2>&1; then
    command -v codex-lb
    return 0
  fi

  for candidate in \
    "${HOME}/.local/bin/codex-lb" \
    "${HOME}/bin/codex-lb"
  do
    if [ -x "${candidate}" ]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done

  tool_dir=$(uv tool dir 2>/dev/null || true)
  if [ -n "${tool_dir}" ]; then
    for candidate in \
      "$(dirname "${tool_dir}")/bin/codex-lb" \
      "${tool_dir}/codex-lb/bin/codex-lb"
    do
      if [ -x "${candidate}" ]; then
        printf '%s\n' "${candidate}"
        return 0
      fi
    done
  fi

  fail "uv installed codex-lb, but the codex-lb executable could not be located."
}

install_codex_lb() {
  platform=$1

  if [ "${platform}" = "termux" ]; then
    mkdir -p "$(dirname "${managed_source_dir}")"
    if [ -d "${managed_source_dir}/.git" ]; then
      say "Updating managed codex-lb source checkout in ${managed_source_dir}"
      git -C "${managed_source_dir}" fetch origin
    elif [ -e "${managed_source_dir}" ]; then
      fail "Managed source path exists but is not a git checkout: ${managed_source_dir}"
    else
      say "Cloning codex-lb source into ${managed_source_dir}"
      git clone "${CODEX_LB_GIT_URL}" "${managed_source_dir}"
    fi

    git -C "${managed_source_dir}" checkout "${CODEX_LB_REF}"
    cp "${script_dir}/templates/termux-codex-lb-pyproject.toml" "${managed_source_dir}/pyproject.toml"
    rm -f "${managed_source_dir}/uv.lock"
    UV_LINK_MODE=copy uv tool install --force --editable "${managed_source_dir}"
    return 0
  fi

  uv tool install --force "${CODEX_LB_TOOL_SPEC}"
}

ensure_path_block() {
  for profile in "${HOME}/.profile" "${HOME}/.bashrc" "${HOME}/.zprofile"; do
    if [ ! -f "${profile}" ]; then
      : > "${profile}"
    fi
    if ! grep -F "${profile_managed_line}" "${profile}" >/dev/null 2>&1; then
      {
        printf '\n'
        printf '# Added by %s\n' "${PACKAGE_NAME}"
        printf '%s\n' "${profile_managed_line}"
      } >> "${profile}"
    fi
  done

  case ":${PATH}:" in
    *":${target_bin_dir}:"*) ;;
    *) say "Added ${target_bin_dir} to your shell profile. Restart your shell after install." ;;
  esac
}

backup_if_needed() {
  target=$1
  source_file=$2

  if [ ! -f "${target}" ]; then
    return 0
  fi

  if cmp -s "${target}" "${source_file}"; then
    return 0
  fi

  backup="${target}.bak.$(date +%Y%m%d%H%M%S)"
  cp "${target}" "${backup}"
  say "Backed up ${target} to ${backup}"
}

render_config() {
  rendered_file=$1
  home_path_escaped=$(printf '%s' "${HOME}" | sed 's/[\/&]/\\&/g')
  sed "s/__HOME_PATH__/${home_path_escaped}/g" \
    "${script_dir}/templates/codex-config.toml.tmpl" > "${rendered_file}"
}

require_command git
require_command uv
require_command codex
require_command awk
require_command sed
require_command pgrep

platform=$(detect_platform)
mkdir -p "${target_bin_dir}" "${launcher_dir}" "${codex_dir}" "${lb_dir}" "${runtime_dir}"

real_codex=$(resolve_real_codex)
say "Using codex binary: ${real_codex}"

say "Installing codex-lb from ${CODEX_LB_GIT_URL}@${CODEX_LB_REF}"
install_codex_lb "${platform}"
codex_lb_bin=$(resolve_codex_lb_bin)

tmp_runtime="${runtime_env}.tmp"
cat > "${tmp_runtime}" <<EOF
PACKAGE_NAME=${PACKAGE_NAME}
PACKAGE_VERSION=${PACKAGE_VERSION}
PACKAGE_SLUG=${PACKAGE_SLUG}
CODEX_REAL_BIN=${real_codex}
CODEX_LB_BIN=${codex_lb_bin}
CODEX_LB_LAUNCHER=${launcher_file}
CODEX_LB_SOURCE_DIR=${managed_source_dir}
CODEX_LB_DIR=${lb_dir}
CODEX_LB_ENV_FILE=${lb_dir}/.env
CODEX_HOST_DEFAULT=${DEFAULT_HOST}
CODEX_PORT_DEFAULT=${DEFAULT_PORT}
EOF
backup_if_needed "${runtime_env}" "${tmp_runtime}"
mv "${tmp_runtime}" "${runtime_env}"

tmp_config="${codex_config_file}.tmp"
render_config "${tmp_config}"
backup_if_needed "${codex_config_file}" "${tmp_config}"
mv "${tmp_config}" "${codex_config_file}"

backup_if_needed "${launcher_file}" "${script_dir}/templates/codex-lb-start.sh"
cp "${script_dir}/templates/codex-lb-start.sh" "${launcher_file}"
chmod 700 "${launcher_file}"

backup_if_needed "${wrapper_file}" "${script_dir}/templates/codex-wrapper.sh"
cp "${script_dir}/templates/codex-wrapper.sh" "${wrapper_file}"
chmod 700 "${wrapper_file}"

backup_if_needed "${lb_env_example_file}" "${script_dir}/templates/codex-lb.env.example"
cp "${script_dir}/templates/codex-lb.env.example" "${lb_env_example_file}"

ensure_path_block

say "Install complete."
say "Next: copy ${lb_env_example_file} to ${lb_dir}/.env if you need overrides, then run ${wrapper_file}."
