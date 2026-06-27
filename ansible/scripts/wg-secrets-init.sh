#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'USAGE'
Usage: wg-secrets-init.sh [--dry-run] [--check] [--help]

Create and validate local WireGuard key material outside the repository.

Defaults:
  Secret directory:        ~/.config/vpn-gen/wireguard
  Public vars file:       ~/.config/vpn-gen/wireguard/public-vars.yml
  Initial client config:  ~/.config/vpn-gen/wireguard/initial-client.conf

Environment overrides:
  VPN_GEN_WG_SECRET_DIR
  VPN_GEN_WG_PUBLIC_VARS_FILE
  VPN_GEN_WG_CLIENT_CONFIG_PATH
  VPN_GEN_WG_CLIENT_ENDPOINT_HOST
  VPN_GEN_WG_CLIENT_ENDPOINT_PORT
  VPN_GEN_WG_TRANSIT_ENDPOINT_PORT

Modes:
  --dry-run   Print planned actions without creating or changing files.
  --check     Validate existing keys, permissions, and public vars inputs only.
  --help      Show this help text.
USAGE
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

info() {
  printf '%s\n' "$*"
}

yaml_dquote() {
  local value escaped
  value=$1
  escaped=${value//\\/\\\\}
  escaped=${escaped//\"/\\\"}
  printf '"%s"' "$escaped"
}

file_mode() {
  local path mode
  path=$1

  case "$(uname -s)" in
    Darwin|FreeBSD)
      if mode=$(stat -f '%Lp' "$path" 2>/dev/null); then
        printf '%s' "$mode"
        return
      fi
      ;;
    *)
      if mode=$(stat -c '%a' "$path" 2>/dev/null); then
        printf '%s' "$mode"
        return
      fi
      ;;
  esac

  die "cannot read file mode: $path"
}

ensure_mode() {
  local path expected actual
  path=$1
  expected=$2

  if [[ $check_only -eq 1 ]]; then
    actual=$(file_mode "$path")
    [[ "$actual" == "$expected" ]] || die "expected mode $expected for $path, got $actual"
    return
  fi

  chmod "$expected" "$path"
}

dry_run=0
check_only=0

while (($#)); do
  case "$1" in
    --dry-run)
      dry_run=1
      ;;
    --check)
      check_only=1
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1"
      ;;
  esac
  shift
done

if [[ $dry_run -eq 1 && $check_only -eq 1 ]]; then
  die "--dry-run and --check are mutually exclusive"
fi

secret_dir=${VPN_GEN_WG_SECRET_DIR:-"$HOME/.config/vpn-gen/wireguard"}
public_vars_file=${VPN_GEN_WG_PUBLIC_VARS_FILE:-"$secret_dir/public-vars.yml"}
initial_client_config_path=${VPN_GEN_WG_CLIENT_CONFIG_PATH:-"$secret_dir/initial-client.conf"}

client_endpoint_host=${VPN_GEN_WG_CLIENT_ENDPOINT_HOST:-"51.250.14.221"}
client_endpoint_port=${VPN_GEN_WG_CLIENT_ENDPOINT_PORT:-"53774"}
transit_endpoint_port=${VPN_GEN_WG_TRANSIT_ENDPOINT_PORT:-"51821"}

key_ids=(
  "yandex_wg_client"
  "yandex_wg_transit"
  "racknerd_wg_transit"
  "initial_client"
)

key_labels=(
  "Yandex wg-client"
  "Yandex wg-transit"
  "Racknerd wg-transit"
  "initial client"
)

private_path_for() {
  printf '%s/%s.private.key' "$secret_dir" "$1"
}

public_path_for() {
  printf '%s/%s.public.key' "$secret_dir" "$1"
}

require_wg() {
  if ! command -v wg >/dev/null 2>&1; then
    die "WireGuard utility 'wg' is required. Install wireguard-tools first."
  fi
}

ensure_secret_dir() {
  if [[ $dry_run -eq 1 ]]; then
    info "DRY-RUN: would ensure secret directory exists with mode 0700: $secret_dir"
    return
  fi

  if [[ -e "$secret_dir" && ! -d "$secret_dir" ]]; then
    die "secret path exists but is not a directory: $secret_dir"
  fi

  if [[ -L "$secret_dir" ]]; then
    die "secret directory must not be a symlink: $secret_dir"
  fi

  if [[ ! -d "$secret_dir" ]]; then
    if [[ $check_only -eq 1 ]]; then
      die "secret directory does not exist: $secret_dir"
    fi
    mkdir -p "$secret_dir"
  fi

  if [[ ! -O "$secret_dir" ]]; then
    die "secret directory must be owned by the current user: $secret_dir"
  fi

  ensure_mode "$secret_dir" 700

  if [[ ! -r "$secret_dir" || ! -w "$secret_dir" || ! -x "$secret_dir" ]]; then
    die "secret directory must be readable, writable, and searchable by the current user: $secret_dir"
  fi

  if [[ $check_only -eq 1 ]]; then
    return
  fi

  local probe
  probe="$secret_dir/.write-test.$$"
  if ! (set -C; : > "$probe") 2>/dev/null; then
    die "cannot create files in secret directory: $secret_dir"
  fi
  rm -f "$probe"
}

generate_key_pair() {
  local id label private_path public_path tmp_private tmp_public
  id=$1
  label=$2
  private_path=$(private_path_for "$id")
  public_path=$(public_path_for "$id")

  if [[ -e "$private_path" ]]; then
    if [[ ! -s "$private_path" ]]; then
      die "$label private key exists but is empty: $private_path"
    fi
    ensure_mode "$private_path" 600
    return
  fi

  if [[ -e "$public_path" ]]; then
    die "$label public key exists without matching private key: $public_path"
  fi

  if [[ $check_only -eq 1 ]]; then
    die "$label private key is missing: $private_path"
  fi

  if [[ $dry_run -eq 1 ]]; then
    info "DRY-RUN: would generate $label key pair:"
    info "  private: $private_path"
    info "  public:  $public_path"
    return
  fi

  tmp_private=$(mktemp "$secret_dir/.${id}.private.XXXXXX")
  tmp_public=$(mktemp "$secret_dir/.${id}.public.XXXXXX")
  trap 'rm -f "$tmp_private" "$tmp_public"' RETURN

  wg genkey > "$tmp_private"
  chmod 600 "$tmp_private"
  wg pubkey < "$tmp_private" > "$tmp_public"
  chmod 644 "$tmp_public"

  mv "$tmp_private" "$private_path"
  mv "$tmp_public" "$public_path"
  trap - RETURN

  info "Generated $label key pair."
}

validate_key_pair() {
  local id label private_path public_path derived_public stored_public
  id=$1
  label=$2
  private_path=$(private_path_for "$id")
  public_path=$(public_path_for "$id")

  if [[ $dry_run -eq 1 ]]; then
    if [[ -e "$private_path" && -e "$public_path" ]]; then
      info "DRY-RUN: would validate $label key pair."
    else
      info "DRY-RUN: $label key pair is not complete yet."
    fi
    return
  fi

  [[ -s "$private_path" ]] || die "$label private key is missing or empty: $private_path"
  [[ -s "$public_path" ]] || die "$label public key is missing or empty: $public_path"

  ensure_mode "$private_path" 600
  ensure_mode "$public_path" 644

  derived_public=$(wg pubkey < "$private_path")
  stored_public=$(tr -d '\r\n' < "$public_path")

  if [[ "$derived_public" != "$stored_public" ]]; then
    die "$label public key does not match private key: $public_path"
  fi
}

read_public_key() {
  local path
  path=$(public_path_for "$1")
  tr -d '\r\n' < "$path"
}

write_public_vars() {
  local tmp_file

  if [[ $dry_run -eq 1 ]]; then
    info "DRY-RUN: would write public Ansible vars without private key material: $public_vars_file"
    return
  fi

  if [[ $check_only -eq 1 ]]; then
    [[ -s "$public_vars_file" ]] || die "public vars file is missing or empty: $public_vars_file"
    ensure_mode "$public_vars_file" 600
    info "Validated public vars file exists: $public_vars_file"
    return
  fi

  tmp_file=$(mktemp "$secret_dir/.public-vars.yml.XXXXXX")
  trap 'rm -f "$tmp_file"' RETURN

  {
    printf '%s\n' '---'
    printf '%s\n' '# Generated by ansible/scripts/wg-secrets-init.sh.'
    printf '%s\n' '# Contains public keys and local file paths only; never add private key material here.'
    printf 'wireguard_secret_dir: %s\n' "$(yaml_dquote "$secret_dir")"
    printf 'wireguard_public_vars_file: %s\n' "$(yaml_dquote "$public_vars_file")"
    printf 'wireguard_initial_client_config_path: %s\n' "$(yaml_dquote "$initial_client_config_path")"
    printf '%s\n' ''
    printf 'wireguard_client_network: "10.60.0.0/24"\n'
    printf 'wireguard_client_interface: "wg-client"\n'
    printf 'wireguard_transit_interface: "wg-transit"\n'
    printf 'wireguard_yandex_wg_client_address: "10.60.0.1/24"\n'
    printf 'wireguard_yandex_wg_transit_address: "10.70.0.1/30"\n'
    printf 'wireguard_racknerd_wg_transit_address: "10.70.0.2/30"\n'
    printf 'wireguard_initial_client_address: "10.60.0.10/32"\n'
    printf 'wireguard_initial_client_dns: "10.60.0.1"\n'
    printf 'wireguard_client_allowed_ips: "0.0.0.0/0"\n'
    printf 'wireguard_yandex_client_endpoint_host: %s\n' "$(yaml_dquote "$client_endpoint_host")"
    printf 'wireguard_yandex_client_endpoint_port: %s\n' "$(yaml_dquote "$client_endpoint_port")"
    printf 'wireguard_transit_endpoint_port: %s\n' "$(yaml_dquote "$transit_endpoint_port")"
    printf '%s\n' ''
    printf 'wireguard_yandex_wg_client_private_key_path: %s\n' "$(yaml_dquote "$(private_path_for yandex_wg_client)")"
    printf 'wireguard_yandex_wg_client_public_key: %s\n' "$(yaml_dquote "$(read_public_key yandex_wg_client)")"
    printf 'wireguard_yandex_wg_transit_private_key_path: %s\n' "$(yaml_dquote "$(private_path_for yandex_wg_transit)")"
    printf 'wireguard_yandex_wg_transit_public_key: %s\n' "$(yaml_dquote "$(read_public_key yandex_wg_transit)")"
    printf 'wireguard_racknerd_wg_transit_private_key_path: %s\n' "$(yaml_dquote "$(private_path_for racknerd_wg_transit)")"
    printf 'wireguard_racknerd_wg_transit_public_key: %s\n' "$(yaml_dquote "$(read_public_key racknerd_wg_transit)")"
    printf 'wireguard_initial_client_private_key_path: %s\n' "$(yaml_dquote "$(private_path_for initial_client)")"
    printf 'wireguard_initial_client_public_key: %s\n' "$(yaml_dquote "$(read_public_key initial_client)")"
  } > "$tmp_file"

  chmod 600 "$tmp_file"
  mv "$tmp_file" "$public_vars_file"
  trap - RETURN

  info "Wrote public Ansible vars: $public_vars_file"
}

main() {
  info "WireGuard secret directory: $secret_dir"
  ensure_secret_dir

  if [[ $dry_run -eq 0 ]]; then
    require_wg
  elif command -v wg >/dev/null 2>&1; then
    info "DRY-RUN: WireGuard utility found."
  else
    info "DRY-RUN: WireGuard utility 'wg' is not installed; real generation would fail until wireguard-tools is installed."
  fi

  local index id label
  for index in "${!key_ids[@]}"; do
    id=${key_ids[$index]}
    label=${key_labels[$index]}
    generate_key_pair "$id" "$label"
    validate_key_pair "$id" "$label"
  done

  write_public_vars

  if [[ $dry_run -eq 1 ]]; then
    info "Dry run complete; no files were changed."
  elif [[ $check_only -eq 1 ]]; then
    info "Secret workflow check passed."
  else
    info "Secret workflow initialized successfully."
  fi
}

main "$@"
