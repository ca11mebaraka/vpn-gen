# WireGuard Secrets And Client Config

This workflow keeps WireGuard private keys outside git and gives Ansible only
public keys plus local private key file paths.

## Files

- Local secret directory: `~/.config/vpn-gen/wireguard/`
- Generated public vars: `~/.config/vpn-gen/wireguard/public-vars.yml`
- Generated initial client config: `~/.config/vpn-gen/wireguard/initial-client.conf`
- Repository scripts:
  - `ansible/scripts/wg-secrets-init.sh`
  - `ansible/scripts/check-no-private-key-material.sh`
  - `ansible/scripts/validate-wireguard-workflow.sh`
- Repository template:
  - `ansible/templates/client/initial-client.conf.j2`
- Repository playbook:
  - `ansible/playbooks/client_config.yml`

The generated `public-vars.yml` contains public keys and local paths only. It
must not contain private key values.

## Initialize Or Validate Secrets

Run from the repository root:

```sh
ansible/scripts/wg-secrets-init.sh
```

The script is idempotent. It creates missing keys and validates existing key
pairs without overwriting private keys.

Generated key pairs:

- `yandex_wg_client`
- `yandex_wg_transit`
- `racknerd_wg_transit`
- `initial_client`

Useful checks:

```sh
ansible/scripts/wg-secrets-init.sh --help
ansible/scripts/wg-secrets-init.sh --dry-run
ansible/scripts/wg-secrets-init.sh --check
```

The real initialization path requires the `wg` utility from WireGuard tools.
The secret directory must be owned by the current user, must not be a symlink,
and is forced to mode `0700`. Private key files are forced to mode `0600`.

Optional environment overrides:

```sh
VPN_GEN_WG_SECRET_DIR="$HOME/.config/vpn-gen/wireguard"
VPN_GEN_WG_PUBLIC_VARS_FILE="$HOME/.config/vpn-gen/wireguard/public-vars.yml"
VPN_GEN_WG_CLIENT_CONFIG_PATH="$HOME/.config/vpn-gen/wireguard/initial-client.conf"
VPN_GEN_WG_CLIENT_ENDPOINT_HOST="111.88.242.229"
VPN_GEN_WG_CLIENT_ENDPOINT_PORT="51820"
VPN_GEN_WG_TRANSIT_ENDPOINT_PORT="51821"
```

## Generate Initial Client Config

After secrets exist, render the client config locally:

```sh
cd ansible
ansible-playbook -i inventory/hosts.yml playbooks/client_config.yml
```

The template reads the initial client private key with:

```jinja
{{ lookup('ansible.builtin.file', wireguard_initial_client_private_key_path) | trim }}
```

That private key is read from the local secret path only during config
generation. The rendered client config is written outside the repository by
default.

## Leak Checks

Run the tracked-file leak guard:

```sh
ansible/scripts/check-no-private-key-material.sh
```

It checks:

- tracked files named `*.private.key`
- inline private-key-looking assignments such as `PrivateKey = <base64>`
- actual values from local `*.private.key` files, if the secret directory exists

Run the full local workflow validation:

```sh
ansible/scripts/validate-wireguard-workflow.sh
```

This runs shell syntax checks, help/dry-run checks, the tracked-file leak guard,
and `ansible-playbook --syntax-check` for `playbooks/client_config.yml` when
Ansible is installed.

## Variables For Roles

Future roles should use these generated variables:

- Yandex `wg-client` interface:
  - `wireguard_yandex_wg_client_private_key_path`
  - `wireguard_yandex_wg_client_public_key`
  - `wireguard_initial_client_public_key`
  - `wireguard_client_interface`
  - `wireguard_yandex_wg_client_address`
  - `wireguard_client_network`
- Yandex `wg-transit` interface:
  - `wireguard_yandex_wg_transit_private_key_path`
  - `wireguard_yandex_wg_transit_public_key`
  - `wireguard_racknerd_wg_transit_public_key`
  - `wireguard_transit_interface`
  - `wireguard_yandex_wg_transit_address`
  - `wireguard_transit_endpoint_port`
- Racknerd `wg-transit` interface:
  - `wireguard_racknerd_wg_transit_private_key_path`
  - `wireguard_racknerd_wg_transit_public_key`
  - `wireguard_yandex_wg_transit_public_key`
  - `wireguard_racknerd_wg_transit_address`
  - `wireguard_transit_endpoint_port`
- Initial client config:
  - `wireguard_initial_client_private_key_path`
  - `wireguard_initial_client_public_key`
  - `wireguard_initial_client_address`
  - `wireguard_initial_client_dns`
  - `wireguard_initial_client_config_path`
  - `wireguard_yandex_client_endpoint_host`
  - `wireguard_yandex_client_endpoint_port`
  - `wireguard_client_allowed_ips`

Roles may read private key files from the local controller when rendering
WireGuard configs, but must not place private key values into inventory,
host_vars, group_vars, docs, or committed vars files.
