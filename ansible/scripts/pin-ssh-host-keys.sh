#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=load-env.sh
source "$script_dir/load-env.sh"

known_hosts=${VPN_GEN_SSH_KNOWN_HOSTS:-$HOME/.config/vpn-gen/ssh/known_hosts}
port=${VPN_GEN_SSH_PORT:-22}

pin_host() {
  local label=$1 host=$2 expected=$3 tmp actual
  [[ $host =~ ^[0-9A-Fa-f:.]+$ ]] || { printf '%s host is not a literal IP\n' "$label" >&2; return 1; }
  [[ $expected == SHA256:* && $expected != *CHANGE_ME* ]] || {
    printf 'Set and verify %s fingerprint from the provider console first\n' "$label" >&2
    return 1
  }
  tmp=$(mktemp)
  trap 'rm -f "$tmp"' RETURN
  ssh-keyscan -T 10 -p "$port" -t ed25519 "$host" > "$tmp" 2>/dev/null
  [[ -s $tmp ]] || { printf 'No ED25519 SSH host key received from %s\n' "$host" >&2; return 1; }
  actual=$(ssh-keygen -lf "$tmp" -E sha256 | awk '{print $2}')
  [[ $actual == "$expected" ]] || {
    printf '%s fingerprint mismatch: expected %s, received %s\n' "$label" "$expected" "$actual" >&2
    return 1
  }
  mkdir -p "$(dirname "$known_hosts")"
  touch "$known_hosts"
  chmod 600 "$known_hosts"
  ssh-keygen -R "[$host]:$port" -f "$known_hosts" >/dev/null 2>&1 || true
  ssh-keygen -R "$host" -f "$known_hosts" >/dev/null 2>&1 || true
  cat "$tmp" >> "$known_hosts"
  printf 'Pinned %s SSH host key: %s\n' "$label" "$actual"
  trap - RETURN
  rm -f "$tmp"
}

pin_host ENTRY "${VPN_GEN_ENTRY_SPLIT_HOST:?}" "${VPN_GEN_ENTRY_SSH_HOST_FINGERPRINT:?}"
pin_host EXIT "${VPN_GEN_EXIT_HOST:?}" "${VPN_GEN_EXIT_SSH_HOST_FINGERPRINT:?}"
