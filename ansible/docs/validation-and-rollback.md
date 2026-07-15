# Проверка и откат

Документ описывает проверку и откат каскадного VPN:

- entry принимает клиентов WireGuard на `wg-client` / `wg-client-2` (split) или `wg0` (full);
- split entry отправляет немarkированный «не-локальный» трафик через `wg-transit` / `wg-transit-2`;
- exit выпускает transit-трафик в интернет с NAT;
- «локальный» трафик (для split — РФ) выходит напрямую с entry;
- full entry (`entry_full_01`) отправляет весь клиентский трафик через exit_01 (`wg-exit-full` / `wg-direct-exit`).

## Статические проверки

Из каталога `ansible/`:

```sh
source scripts/load-env.sh
ansible-inventory -i inventory/hosts.yml --list
ansible-playbook -i inventory/hosts.yml playbooks/validate_cascade.yml --syntax-check
ansible-playbook -i inventory/hosts.yml playbooks/rollback_cascade.yml --syntax-check
```

## Плейбук validate_cascade.yml

Только чтение. Проверяет:

- SSH и passwordless sudo;
- IPv4 forwarding на всех узлах;
- интерфейсы WireGuard:
  - split entry (dual-exit): `wg-client`, `wg-client-2`, `wg-transit`, `wg-transit-2`;
  - split entry (single): `wg-client`, `wg-transit`;
  - full entry: `wg0`, `wg-transit`;
  - exit_01: `wg-transit`, `wg-exit-full` / `wg-direct-exit`;
  - exit_02: `wg-transit` (`10.61.0.0/24`);
- `wg show`, `systemctl is-active` для сервисов;
- загруженный nftables;
- policy routing на split entry: `fwmark 0x2` → table `200`, `fwmark 0x4` → table `201`;
- nftables split: `ru4`, mark, masquerade, counters;
- exit NAT для `10.60.0.0/24`, `10.61.0.0/24`, `10.80.0.0/24`.

Живая проверка после деплоя:

```sh
ansible-playbook -i inventory/hosts.yml playbooks/verify.yml
ansible-playbook -i inventory/hosts.yml playbooks/validate_cascade.yml
```

На entry (dual-exit):

```sh
sudo wg show wg-client wg-client-2 wg-transit wg-transit-2
sudo wg show wg-transit | grep -E 'listening|handshake'
sudo wg show wg-transit-2 | grep -E 'listening|handshake'
dig @10.61.0.1 yandex.ru +short
sudo nft list chain inet entry_split mark_client_traffic
ping -c 2 10.70.0.2   # exit_01 transit
ping -c 2 10.71.0.2   # exit_02 transit
```

Рекомендуемый порядок:

1. `ansible-inventory --list`
2. `playbooks/verify.yml`
3. `playbooks/validate_cascade.yml`
4. Подключить тестового клиента WireGuard (`split` или `split2`)
5. Сгенерировать трафик (локальный и «зарубежный» destination)
6. Повторить validate и сравнить счётчики nftables
7. Fail-closed: остановить transit на exit — «зарубежный» трафик lane должен пропасть, локальный — продолжить
8. Transit handshake: на entry `wg-transit` (lane 1, listen `49251`) и `wg-transit-2` (lane 2, listen `49249`) — `latest handshake` не старше нескольких минут

После `entry_split.yml`:

```sh
./scripts/wg-client sync --profile split
```

## Плейбук rollback_cascade.yml

По умолчанию **не выполняется** (`confirm_rollback=false`).

Может:

- остановить `wg-quick@wg-client`, `wg-client-2`, `wg-transit`, `wg-transit-2` на entry;
- удалить policy route tables `200` / `201` и rules `fwmark 0x2` / `0x4`;
- остановить `wg-transit` на exit_01 / exit_02 и `wg-exit-full` на exit_01.

Сухой прогон:

```sh
ansible-playbook -i inventory/hosts.yml playbooks/rollback_cascade.yml --syntax-check
ansible-playbook -i inventory/hosts.yml playbooks/rollback_cascade.yml --check
```

Запуск отката:

```sh
ansible-playbook -i inventory/hosts.yml playbooks/rollback_cascade.yml -e confirm_rollback=true
```

Выборочно:

```sh
ansible-playbook ... -e confirm_rollback=true --limit entry_split_01 --tags wireguard
ansible-playbook ... -e confirm_rollback=true --limit exit_02 --tags wireguard
```

Откат — только для планового восстановления. Убедитесь, что есть альтернативный SSH-доступ.
