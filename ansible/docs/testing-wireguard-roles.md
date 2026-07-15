# Тестирование ролей WireGuard

Статическая, check-mode и живая проверка ролей `exit`, `entry_split`, `entry_full`.

## Секреты

Приватные ключи **не коммитить**. Передавать через Vault, `--extra-vars` или `*_private_key_path` вне репозитория.

Минимум перед check-mode / apply (single-exit):

- `exit_wg_transit_private_key` или `*_path`
- `exit_entry_split_wg_transit_public_key`
- `entry_split_wg_client_*`, `entry_split_wg_transit_*`
- `entry_split_exit_wg_transit_public_key`
- `entry_split_wg_client_peers`, `entry_split_ru_ipv4_cidrs` или `*_file`

Dual-exit (дополнительно):

- `entry_split_wg_client_2_*`, `entry_split_wg_transit_2_*`
- `entry_split_exit2_wg_transit_public_key`, `entry_split_exit2_wg_transit_endpoint`
- `exit_02`: `exit_wg_transit_*`, `exit_client_cidr: 10.61.0.0/24`, `exit_public_interface`

Full entry:

- `entry_full_wg_client_*`, `entry_full_wg_transit_*`, `entry_full_exit_public_key`
- `exit_entry_full_wg_private_key_path`, `exit_entry_full_public_key`

Пример путей:

```yaml
exit_wg_transit_private_key_path: ~/.config/vpn-gen/wireguard/racknerd_wg_transit.private.key
entry_split_wg_client_private_key_path: ~/.config/vpn-gen/wireguard/yandex_wg_client.private.key
entry_split_wg_client_2_private_key_path: ~/.config/vpn-gen/wireguard/entry_split_wg_client_2.private.key
entry_split_ru_ipv4_cidrs_file: ~/.config/vpn-gen/geo/ru.zone
```

## Статика

Из `ansible/`:

```sh
ansible-inventory --list
ansible-playbook playbooks/exit.yml --syntax-check
ansible-playbook playbooks/entry_split.yml --syntax-check
ansible-playbook playbooks/entry_full.yml --syntax-check
```

## Check-mode

```sh
ansible all -m ping
ansible-playbook playbooks/verify.yml
ansible-playbook playbooks/exit.yml --check --diff
ansible-playbook playbooks/entry_split.yml --check --diff
ansible-playbook playbooks/entry_full.yml --check --diff
```

Ожидания: ранний fail при отсутствии ключей; exit — `wg-transit` (+ `wg-exit-full` при full); entry_split dual — `wg-client`, `wg-client-2`, tables `200`/`201`, marks `0x2`/`0x4`.

## Live apply

Держите открытую SSH-сессию. Порядок: **exit → entry_split → entry_full**.

```sh
ansible-playbook playbooks/exit.yml --diff
ansible exit_01 -m command -a 'wg show wg-transit'
ansible exit_02 -m command -a 'wg show wg-transit'

ansible-playbook playbooks/entry_split.yml --diff
ansible entry_split_01 -m command -a 'ip rule show'
ansible entry_split_01 -m command -a 'ip route show table 200'
ansible entry_split_01 -m command -a 'ip route show table 201'

ansible-playbook playbooks/entry_full.yml --diff
ansible entry_full_01 -m command -a 'wg show wg0'

./scripts/wg-client sync --profile split
```

E2E с клиента:

- lane 1 (`split`): RU → IP entry; non-RU → IP exit_01 (transit listen `49251` на entry)
- lane 2 (`split2`): RU → IP entry; non-RU → IP exit_02 (transit listen `49249` на entry)
- DNS: `dig @10.61.0.1` / `dig @10.60.0.1` с entry
- падение transit → non-RU fail-closed

Диагностика UDP entry→exit (lane 1):

```sh
# на entry — egress
sudo tcpdump -ni enp3s0 'host <exit_ip> and udp port 51821'
# на exit — ingress
sudo tcpdump -ni eth0 'host <entry_ip> and udp port 51821'
```

Если egress есть, ingress нет — смените `entry_split_wg_transit_listen_port` в `host_vars` (см. architecture doc).

## Ручной откат на хосте

exit_01 / exit_02:

```sh
sudo systemctl disable --now wg-quick@wg-transit
sudo rm -f /etc/nftables.d/exit_split.nft
```

entry_split (dual-exit):

```sh
sudo systemctl disable --now wg-quick@wg-client wg-quick@wg-client-2 wg-quick@wg-transit wg-quick@wg-transit-2
sudo ip route del default dev wg-transit table 200 2>/dev/null || true
sudo ip route del default dev wg-transit-2 table 201 2>/dev/null || true
sudo ip rule del fwmark 0x2 table 200 2>/dev/null || true
sudo ip rule del fwmark 0x4 table 201 2>/dev/null || true
sudo rm -f /etc/nftables.d/entry_split.nft
```

Плейbook: [`validation-and-rollback.md`](validation-and-rollback.md).
