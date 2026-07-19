#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ansible_dir=$(cd -- "$script_dir/.." && pwd)
# shellcheck source=load-env.sh
source "$script_dir/load-env.sh"

recipient=${VPN_GEN_BACKUP_AGE_RECIPIENT:-}
output=${1:-"$PWD/vpn-gen-secrets-$(date -u +%Y%m%dT%H%M%SZ).tar.age"}
[[ $recipient == age1* ]] || { printf 'Set VPN_GEN_BACKUP_AGE_RECIPIENT to an age public recipient\n' >&2; exit 1; }
command -v age >/dev/null || { printf 'age is required for encrypted backups\n' >&2; exit 1; }

config_dir=${VPN_GEN_CONFIG_DIR:-$HOME/.config/vpn-gen}
ssh_key=${VPN_GEN_SSH_KEY_ENTRY:-}
paths=()
for path in "$config_dir" "$ansible_dir/.env" "$ssh_key"; do
  [[ -n $path && -e $path ]] || continue
  absolute=$(realpath "$path")
  [[ $absolute != / && $absolute != "$HOME" ]] || { printf 'Refusing unsafe backup path: %s\n' "$absolute" >&2; exit 1; }
  paths+=("${absolute#/}")
done
(( ${#paths[@]} > 0 )) || { printf 'No secret paths exist yet\n' >&2; exit 1; }

mkdir -p "$(dirname "$output")"
tmp=$(mktemp "$(dirname "$output")/.vpn-gen-backup.XXXXXX")
trap 'rm -f "$tmp"' EXIT
tar -C / -cf - "${paths[@]}" | age -r "$recipient" -o "$tmp"
chmod 600 "$tmp"
mv "$tmp" "$output"
trap - EXIT
printf 'Encrypted backup written: %s\n' "$output"
printf 'Verify without extracting: age -d %q | tar -tf -\n' "$output"
