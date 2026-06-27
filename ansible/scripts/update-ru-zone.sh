#!/usr/bin/env bash
set -euo pipefail

OUT="${VPN_GEN_RU_ZONE_FILE:-$HOME/.config/vpn-gen/geo/ru.zone}"
URL="${VPN_GEN_RU_ZONE_URL:-https://www.ipdeny.com/ipblocks/data/countries/ru.zone}"

mkdir -p "$(dirname "$OUT")"
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

curl -fsSL "$URL" -o "$tmp"
grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+/[0-9]+$' "$tmp"
install -m 0600 "$tmp" "$OUT"
wc -l "$OUT"
