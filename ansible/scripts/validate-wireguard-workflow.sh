#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ansible_dir=$(cd -- "$script_dir/.." && pwd)
ansible_tmp=""

cleanup() {
  if [[ -n "$ansible_tmp" ]]; then
    rm -rf "$ansible_tmp"
  fi
}

trap cleanup EXIT

run() {
  printf '+ %s\n' "$*"
  "$@"
}

run bash -n "$script_dir/wg-secrets-init.sh"
run bash -n "$script_dir/wg-client"
run bash -n "$script_dir/check-no-private-key-material.sh"
run python3 -m py_compile "$script_dir/wg-client-admin.py"

run "$script_dir/wg-secrets-init.sh" --help
run "$script_dir/wg-secrets-init.sh" --dry-run
run "$script_dir/wg-client" --help
run "$script_dir/wg-client" profiles
run "$script_dir/check-no-private-key-material.sh" --help
run "$script_dir/check-no-private-key-material.sh"

if command -v ansible-playbook >/dev/null 2>&1; then
  ansible_tmp=$(mktemp -d "$script_dir/.ansible-tmp.XXXXXX")
  export ANSIBLE_LOCAL_TEMP="$ansible_tmp/local"
  export ANSIBLE_REMOTE_TEMP="$ansible_tmp/remote"
  mkdir -p "$ANSIBLE_LOCAL_TEMP" "$ANSIBLE_REMOTE_TEMP"
  run ansible-playbook -i "$ansible_dir/inventory/hosts.yml" "$ansible_dir/playbooks/client_config.yml" --syntax-check
else
  printf 'SKIP: ansible-playbook is not installed; skipped client_config.yml syntax check.\n'
fi

printf 'WireGuard secret workflow validation passed.\n'
