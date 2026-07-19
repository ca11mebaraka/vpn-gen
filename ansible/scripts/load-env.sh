#!/usr/bin/env bash
# shellcheck disable=SC1090
set -Eeuo pipefail

ansible_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
repo_root=$(cd -- "$ansible_dir/.." && pwd)

load_file() {
  local file=$1 mode
  if [[ -f $file ]]; then
    [[ ! -L $file ]] || { printf 'refusing symlinked env file: %s\n' "$file" >&2; return 1; }
    mode=$(stat -c '%a' "$file" 2>/dev/null || stat -f '%Lp' "$file")
    if (( (8#$mode & 8#022) != 0 )); then
      printf 'refusing group/world-writable env file: %s\n' "$file" >&2
      return 1
    fi
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
  [[ $VPN_GEN_DEPLOYMENT =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || {
    printf 'invalid VPN_GEN_DEPLOYMENT: %s\n' "$VPN_GEN_DEPLOYMENT" >&2
    return 1 2>/dev/null || exit 1
  }
  load_file "$ansible_dir/deployments/$VPN_GEN_DEPLOYMENT/.env"
fi
