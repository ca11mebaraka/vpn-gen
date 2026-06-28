# Тестирование ролей WireGuard

Статическая, check-mode и живая проверка ролей `exit`, `entry_split`, `entry_full`.

## Секреты

Приватные ключи **не коммитить**. Передавать через Vault, `--extra-vars` или `*_private_key_path` вне репозитория.

Минимум перед check-mode / apply:

- `exit_wg_transit_private_key` или `*_path`
- `exit_entry_split_wg_transit_public_key`
- `entry_split_wg_client_*`, `entry_split_wg_transit_*`
- `entry_split_exit_wg_transit_public_key`
- `entry_split_wg_client_peers`, `entry_split_ru_ipv4_cidrs` или `*_file`
- `entry_full_wg_client_*`, `entry_full_wg_transit_*`, `entry_full_exit_public_key`
- `exit_entry_full_wg_private_key_path`, `exit_entry_full_public_key`

Пример путей:

```yaml
exit_wg_transit_private_key_path: ~/.config/vpn-gen/wireguard/racknerd_wg_transit.private.key
entry_split_wg_client_private_key_path: ~/.config/vpn-gen/wireguard/yandex_wg_client.private.key
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

Ожидания: ранний fail при отсутствии ключей; exit показывает `wg-transit` + `wg-exit-full`; entry_split — `wg-client`, table `200`, mark `0x2`; entry_full — `wg0`, table `210`.

## Live apply

Держите открытую SSH-сессию. Порядок: **exit → entry_split → entry_full**.

```sh
ansible-playbook playbooks/exit.yml --diff
ansible exit -m command -a 'wg show wg-transit'
ansible exit -m command -a 'wg show wg-exit-full'

ansible-playbook playbooks/entry_split.yml --diff
ansible entry_split -m command -a 'ip rule show'
ansible entry_split -m command -a 'ip route show table 200'

ansible-playbook playbooks/entry_full.yml --diff
ansible entry_full -m command -a 'wg show wg0'
```

E2E с клиента: RU → IP entry; non-RU → IP exit; падение exit transit → non-RU fail-closed.

## Ручной откат на хосте

exit:

```sh
sudo systemctl disable --now wg-quick@wg-transit wg-quick@wg-exit-full
sudo rm -f /etc/nftables.d/exit_split.nft /etc/nftables.d/exit_full.nft
```

entry_split:

```sh
sudo systemctl disable --now wg-quick@wg-client wg-quick@wg-transit
sudo ip route del default dev wg-transit table 200 2>/dev/null || true
sudo ip rule del fwmark 0x2 table 200 2>/dev/null || true
sudo rm -f /etc/nftables.d/entry_split.nft
```

Плейbook: [`validation-and-rollback.md`](validation-and-rollback.md).
