#!/usr/bin/env bash
set -euo pipefail

profile_name="${LARK_CHANNEL_PROFILE:-codex}"
bridge_root="${LARK_CHANNEL_HOME:-${HOME}/.lark-channel}"
source_config="${bridge_root}/profiles/${profile_name}/lark-cli-source/config.json"
failed=0

check_command() {
  local command_name="$1"
  local package_hint="$2"
  if command -v "${command_name}" >/dev/null 2>&1; then
    printf 'ok      %-21s %s\n' "${command_name}" "$(command -v "${command_name}")"
  else
    printf 'missing %-21s install %s\n' "${command_name}" "${package_hint}"
    failed=1
  fi
}

check_command codex 'Codex CLI'
check_command lark-channel-bridge 'lark-channel-bridge'
check_command lark-cli '@larksuite/cli'

if [[ -f "${source_config}" ]]; then
  printf 'ok      %-21s %s\n' 'profile' "${profile_name}"
else
  printf 'missing %-21s %s\n' 'profile' "${profile_name}"
  printf '        initialize with: lark-channel-bridge run --profile %s --agent codex\n' "${profile_name}"
  failed=1
fi

exit "${failed}"
