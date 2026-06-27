# Testing WireGuard Roles

This document covers the static, check-mode, and live validation sequence for
the `racknerd_exit`, `yandex_edge`, and `yandex_direct_edge` roles.

## Secret Inputs

Do not commit WireGuard private keys. Provide them with Ansible Vault,
`--extra-vars`, or file lookups from a directory outside the repository.

Required before check-mode or live apply:

- `racknerd_exit_wg_transit_private_key` or `racknerd_exit_wg_transit_private_key_path`
- `racknerd_exit_yandex_wg_transit_public_key`
- `yandex_edge_wg_client_private_key` or `yandex_edge_wg_client_private_key_path`
- `yandex_edge_wg_transit_private_key` or `yandex_edge_wg_transit_private_key_path`
- `yandex_edge_racknerd_wg_transit_public_key`
- `yandex_edge_wg_client_peers` with user client public keys when clients are ready
- `yandex_edge_ru_ipv4_cidrs` or `yandex_edge_ru_ipv4_cidrs_file`
- `yandex_direct_wg_client_private_key_path`
- `yandex_direct_wg_transit_private_key_path`
- `yandex_direct_racknerd_public_key`
- `racknerd_direct_exit_wg_private_key_path`
- `racknerd_direct_exit_yandex_public_key`

Example non-git secret paths:

```yaml
racknerd_exit_wg_transit_private_key_path: ~/.config/vpn-gen/wireguard/racknerd-wg-transit.key
yandex_edge_wg_client_private_key_path: ~/.config/vpn-gen/wireguard/yandex-wg-client.key
yandex_edge_wg_transit_private_key_path: ~/.config/vpn-gen/wireguard/yandex-wg-transit.key
yandex_edge_ru_ipv4_cidrs_file: ~/.config/vpn-gen/geo/ru.zone
```

## Static Sanity

Run from `ansible/`:

```sh
ansible-inventory --list
python3 - <<'PY'
from pathlib import Path
import yaml

for path in [
    *Path("roles/racknerd_exit").rglob("*.yml"),
    *Path("roles/yandex_edge").rglob("*.yml"),
    *Path("roles/yandex_direct_edge").rglob("*.yml"),
    Path("playbooks/wireguard_transit.yml"),
    Path("playbooks/yandex_edge.yml"),
    Path("playbooks/yandex_direct_edge.yml"),
]:
    with path.open() as fh:
        yaml.safe_load(fh)
    print(path)
PY
python3 - <<'PY'
from pathlib import Path
from jinja2 import Environment, StrictUndefined

env = Environment(undefined=StrictUndefined)
for path in [
    *Path("roles/racknerd_exit/templates").glob("*.j2"),
    *Path("roles/yandex_edge/templates").glob("*.j2"),
    *Path("roles/yandex_direct_edge/templates").glob("*.j2"),
]:
    env.parse(path.read_text())
    print(path)
PY
ansible-playbook playbooks/wireguard_transit.yml --syntax-check
ansible-playbook playbooks/yandex_edge.yml --syntax-check
ansible-playbook playbooks/yandex_direct_edge.yml --syntax-check
```

These checks do not apply roles to remote servers.

## Check-Mode Sequence

Run only after secret variables and public peer keys are available:

```sh
ansible all -m ping
ansible-playbook playbooks/verify.yml
ansible-playbook playbooks/wireguard_transit.yml --check --diff
ansible-playbook playbooks/yandex_edge.yml --check --diff
ansible-playbook playbooks/yandex_direct_edge.yml --check --diff
```

Expected behavior:

- The roles should render WireGuard and nftables changes without storing private
  key files in git.
- Missing key variables should fail early with a clear assertion.
- The Racknerd role should show `wg-transit` and nftables NAT/forwarding changes.
- The Racknerd role should also manage `wg-direct-exit` for the secondary Yandex node.
- The Yandex role should show `wg-client`, `wg-transit`, policy table `200`,
  fwmark `0x2`, and nftables marking/NAT changes.
- The direct Yandex role should show `wg0`, `wg-transit`, policy table `210`,
  and nftables forwarding for `10.80.0.0/24`.

## Live Apply Sequence

Before applying networking changes, keep an active SSH session to each host and
prepare rollback commands.

Racknerd:

```sh
ansible-playbook playbooks/wireguard_transit.yml --diff
ansible-playbook playbooks/wireguard_transit.yml --diff
ansible external_vps -m command -a 'wg show wg-transit'
ansible external_vps -m command -a 'wg show wg-direct-exit'
ansible external_vps -m command -a 'ip route get 10.60.0.10'
ansible external_vps -m command -a 'ip route get 10.80.0.10'
ansible external_vps -m command -a 'nft list ruleset'
```

Yandex:

```sh
ansible-playbook playbooks/yandex_edge.yml --diff
ansible-playbook playbooks/yandex_edge.yml --diff
ansible yandex_edge -m command -a 'wg show wg-client'
ansible yandex_edge -m command -a 'wg show wg-transit'
ansible yandex_edge -m command -a 'ip rule show'
ansible yandex_edge -m command -a 'ip route show table 200'
ansible yandex_edge -m command -a 'nft list ruleset'
```

Secondary Yandex direct edge:

```sh
ansible-playbook playbooks/yandex_direct_edge.yml --diff
ansible-playbook playbooks/yandex_direct_edge.yml --diff
ansible yandex_direct -m command -a 'wg show wg0'
ansible yandex_direct -m command -a 'wg show wg-transit'
ansible yandex_direct -m command -a 'ip rule show'
ansible yandex_direct -m command -a 'ip route show table 210'
ansible yandex_direct -m command -a 'nft list ruleset'
```

End-to-end tests from a client:

- RU destination exits via Yandex.
- Non-RU destination exits via Racknerd.
- Stopping Racknerd `wg-transit` makes non-RU traffic fail closed instead of
  falling back to Yandex.
- RU traffic continues to exit via Yandex while transit is down.

## Rollback Commands

Racknerd:

```sh
sudo systemctl disable --now wg-quick@wg-transit
sudo systemctl disable --now wg-quick@wg-direct-exit
sudo rm -f /etc/nftables.d/racknerd_exit.nft
sudo rm -f /etc/nftables.d/racknerd_direct_exit.nft
sudo sed -i '\#include "/etc/nftables.d/racknerd_exit.nft"#d' /etc/nftables.conf
sudo sed -i '\#include "/etc/nftables.d/racknerd_direct_exit.nft"#d' /etc/nftables.conf
sudo nft -c -f /etc/nftables.conf && sudo systemctl reload nftables
```

Yandex:

```sh
sudo systemctl disable --now wg-quick@wg-client wg-quick@wg-transit
sudo ip route del default dev wg-transit table 200 2>/dev/null || true
sudo ip rule del fwmark 0x2 table 200 priority 200 2>/dev/null || true
sudo rm -f /etc/nftables.d/yandex_edge.nft
sudo sed -i '\#include "/etc/nftables.d/yandex_edge.nft"#d' /etc/nftables.conf
sudo nft -c -f /etc/nftables.conf && sudo systemctl reload nftables
```
