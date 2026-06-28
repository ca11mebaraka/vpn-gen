#!/usr/bin/env bash
# shellcheck disable=SC1090
set -Eeuo pipefail

ansible_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
repo_root=$(cd -- "$ansible_dir/.." && pwd)

load_file() {
  local file=$1
  if [[ -f $file ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$file"
    set +a
    printf 'loaded %s\n' "$file" >&2
  fi
}

load_file "$ansible_dir/.env"
load_file "$repo_root/.env"

if [[ -n "${VPN_GEN_DEPLOYMENT:-}" ]]; then
  load_file "$ansible_dir/deployments/$VPN_GEN_DEPLOYMENT/.env"
fi
