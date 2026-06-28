# Проверка и откат

Документ описывает проверку и откат каскадного VPN:

- entry принимает клиентов WireGuard на `wg-client` (split) или `wg0` (full);
- split entry отправляет немarkированный «не-локальный» трафик через `wg-transit`;
- exit выпускает transit-трафик в интернет с NAT;
- «локальный» трафик (для split — РФ) выходит напрямую с entry;
- full entry (`entry_full_01`) отправляет весь клиентский трафик через exit (`wg-exit-full`).

## Статические проверки

Из каталога `ansible/`:

```sh
ansible-inventory -i inventory/hosts.yml --list
ansible-playbook -i inventory/hosts.yml playbooks/validate_cascade.yml --syntax-check
ansible-playbook -i inventory/hosts.yml playbooks/rollback_cascade.yml --syntax-check
```

## Плейбук validate_cascade.yml

Только чтение. Проверяет:

- SSH и passwordless sudo;
- IPv4 forwarding на всех узлах;
- интерфейсы WireGuard:
  - split entry: `wg-client`, `wg-transit`;
  - full entry: `wg0`, `wg-transit`;
  - exit: `wg-transit`, `wg-exit-full`;
- `wg show`, `systemctl is-active` для сервисов;
- загруженный nftables;
- policy routing на split entry: `fwmark 0x2`, table `200`, default через `wg-transit`;
- nftables split: `ru4`, mark `0x2`, masquerade, counters;
- exit NAT для `10.60.0.0/24` и `10.80.0.0/24`.

Живая проверка после деплоя:

```sh
ansible-playbook -i inventory/hosts.yml playbooks/verify.yml
ansible-playbook -i inventory/hosts.yml playbooks/validate_cascade.yml
```

Рекомендуемый порядок:

1. `ansible-inventory --list`
2. `playbooks/verify.yml`
3. `playbooks/validate_cascade.yml`
4. Подключить тестового клиента WireGuard
5. Сгенерировать трафик (локальный и «зарубежный» destination)
6. Повторить validate и сравнить счётчики nftables
7. Для fail-closed: остановить transit на exit — «зарубежный» трафик должен пропасть, локальный — продолжить работать через entry

## Плейбук rollback_cascade.yml

По умолчанию **не выполняется** (`confirm_rollback=false`).

Может:

- остановить `wg-quick@wg-client` и `wg-quick@wg-transit` на entry;
- удалить policy route table `200` и rule `fwmark 0x2`;
- остановить `wg-transit` и `wg-exit-full` на exit.

Сухой прогон:

```sh
ansible-playbook -i inventory/hosts.yml playbooks/rollback_cascade.yml --syntax-check
ansible-playbook -i inventory/hosts.yml playbooks/rollback_cascade.yml --check
```

Без `-e confirm_rollback=true` плейбук должен остановиться на guard-задаче.

Запуск отката:

```sh
ansible-playbook -i inventory/hosts.yml playbooks/rollback_cascade.yml -e confirm_rollback=true
```

Выборочно:

```sh
ansible-playbook ... -e confirm_rollback=true --limit entry --tags wireguard
ansible-playbook ... -e confirm_rollback=true --limit entry --tags policy_routing
ansible-playbook ... -e confirm_rollback=true --limit exit --tags wireguard
```

Откат — только для планового восстановления, не для обычной проверки. Убедитесь, что есть альтернативный SSH-доступ.
