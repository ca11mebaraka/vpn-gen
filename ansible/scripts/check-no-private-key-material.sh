#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'USAGE'
Usage: check-no-private-key-material.sh [--help]

Check git-tracked files for WireGuard private key leaks.

The check scans:
  - tracked files named *.private.key
  - inline WireGuard private key assignments such as PrivateKey = <base64>
  - actual local private key values from ~/.config/vpn-gen/wireguard/*.private.key

Environment override:
  VPN_GEN_WG_SECRET_DIR
USAGE
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

if [[ ${1:-} == "--help" || ${1:-} == "-h" ]]; then
  usage
  exit 0
fi

if (($#)); then
  die "unknown argument: $1"
fi

repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || die "not inside a git repository"
secret_dir=${VPN_GEN_WG_SECRET_DIR:-"$HOME/.config/vpn-gen/wireguard"}
status=0

cd "$repo_root"

tracked_private_files=()
while IFS= read -r -d '' tracked_path; do
  case "$tracked_path" in
    *.private.key)
      tracked_private_files+=("$tracked_path")
      ;;
  esac
done < <(git ls-files -z)

if ((${#tracked_private_files[@]})); then
  printf 'Tracked private key files are not allowed:\n' >&2
  printf '  %s\n' "${tracked_private_files[@]}" >&2
  status=1
fi

inline_private_pattern="(PrivateKey[[:space:]]*=|private_key:[[:space:]]*)[[:space:]]*[\"']?[A-Za-z0-9+/]{42}="
if git grep -nE "$inline_private_pattern" -- . >/tmp/vpn-gen-inline-private-key-matches.$$ 2>/dev/null; then
  printf 'Inline private key-looking values found in tracked files:\n' >&2
  sed 's/^/  /' "/tmp/vpn-gen-inline-private-key-matches.$$" >&2
  status=1
fi
rm -f "/tmp/vpn-gen-inline-private-key-matches.$$"

if [[ -d "$secret_dir" ]]; then
  shopt -s nullglob
  private_key_files=("$secret_dir"/*.private.key)
  shopt -u nullglob

  for private_key_file in "${private_key_files[@]}"; do
    private_key_value=$(tr -d '\r\n' < "$private_key_file")
    if [[ -z "$private_key_value" ]]; then
      printf 'Local private key file is empty: %s\n' "$private_key_file" >&2
      status=1
      continue
    fi

    if git grep -F -n -- "$private_key_value" -- . >/tmp/vpn-gen-private-key-value-matches.$$ 2>/dev/null; then
      printf 'Local private key value from %s appears in tracked files:\n' "$private_key_file" >&2
      sed 's/^/  /' "/tmp/vpn-gen-private-key-value-matches.$$" >&2
      status=1
    fi
    rm -f "/tmp/vpn-gen-private-key-value-matches.$$"
  done
else
  printf 'Secret directory does not exist yet; skipped value-based scan: %s\n' "$secret_dir"
fi

if [[ $status -ne 0 ]]; then
  die "private key material check failed"
fi

printf 'No WireGuard private key material found in git-tracked files.\n'
