#!/usr/bin/env bash
set -Eeuo pipefail

OUT="${VPN_GEN_RU_ZONE_FILE:-$HOME/.config/vpn-gen/geo/ru.zone}"
URL="${VPN_GEN_RU_ZONE_URL:-https://www.ipdeny.com/ipblocks/data/countries/ru.zone}"
EXPECTED_SHA256="${VPN_GEN_RU_ZONE_SHA256:-}"
ALLOW_CUSTOM="${VPN_GEN_ALLOW_CUSTOM_RU_ZONE_URL:-false}"

[[ $URL == https://* ]] || { printf 'RU zone URL must use HTTPS\n' >&2; exit 1; }
if [[ $ALLOW_CUSTOM != true && $URL != https://www.ipdeny.com/ipblocks/data/countries/ru.zone ]]; then
  printf 'Custom RU zone URL requires VPN_GEN_ALLOW_CUSTOM_RU_ZONE_URL=true\n' >&2
  exit 1
fi

mkdir -p "$(dirname "$OUT")"
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

curl --proto '=https' --tlsv1.2 --fail --silent --show-error --location "$URL" -o "$tmp"
python3 - "$tmp" <<'PY'
import ipaddress
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
lines = [line.strip() for line in path.read_text(encoding="ascii").splitlines() if line.strip()]
if len(lines) < 1000:
    raise SystemExit(f"RU zone is unexpectedly small: {len(lines)} entries")
for line in lines:
    network = ipaddress.ip_network(line, strict=True)
    if network.version != 4:
        raise SystemExit(f"non-IPv4 network in RU zone: {line}")
if len(lines) != len(set(lines)):
    raise SystemExit("RU zone contains duplicate entries")
PY

actual_sha256="$(sha256sum "$tmp" | awk '{print $1}')"
if [[ -n $EXPECTED_SHA256 && $actual_sha256 != "$EXPECTED_SHA256" ]]; then
  printf 'RU zone SHA-256 mismatch: expected %s, got %s\n' "$EXPECTED_SHA256" "$actual_sha256" >&2
  exit 1
fi

install -m 0600 "$tmp" "$OUT"
printf 'Installed %s entries; sha256=%s\n' "$(wc -l < "$OUT")" "$actual_sha256"
