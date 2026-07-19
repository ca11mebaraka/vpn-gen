#!/usr/bin/env bash
set -Eeuo pipefail

expected_exit=${VPN_GEN_EXPECTED_EXIT_IP:-}
[[ $expected_exit =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  printf 'Set VPN_GEN_EXPECTED_EXIT_IP to the exit VPS IPv4 address\n' >&2
  exit 1
}

command -v curl >/dev/null || { printf 'curl is required\n' >&2; exit 1; }
actual_ipv4=$(curl --fail --silent --show-error --max-time 15 --ipv4 https://api.ipify.org)
[[ $actual_ipv4 == "$expected_exit" ]] || {
  printf 'IPv4 leak or routing failure: expected exit %s, observed %s\n' "$expected_exit" "$actual_ipv4" >&2
  exit 1
}

if curl --fail --silent --max-time 8 --ipv6 https://api64.ipify.org >/dev/null 2>&1; then
  printf 'IPv6 leak detected: public IPv6 connectivity bypassed the IPv4-only VPN\n' >&2
  exit 1
fi

printf 'Client baseline passed: public IPv4=%s and no public IPv6 path\n' "$actual_ipv4"
