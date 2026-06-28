# План оркестрации агентов

Реализация каскадного VPN из [`cascade-vpn-architecture.md`](cascade-vpn-architecture.md) через небольшие Ansible-роли с чётким разделением задач.

## Целевое состояние

- пользователь подключается к entry по WireGuard;
- split entry выпускает «локальный» трафик напрямую;
- split entry отправляет остальной трафик в зашифрованный tunnel на exit;
- exit делает NAT в интернет;
- при падении tunnel non-RU трафик **не** уходит напрямую с entry (fail-closed).

## Дисциплина тестирования

На каждом шаге — максимум проверок:

- автоматические тесты вместе с каждым изменением;
- узкая проверка сразу после правки, широкая — перед handoff;
- фиксировать команды в отчёте;
- предупреждения Ansible/systemd/nftables/wg — исправлять, если не документированы как безопасные;
- **стоп** при падении обязательной проверки;
- idempotence: второй прогон плейбука без лишних изменений;
- для сетевых изменений — проверить SSH до и после, иметь rollback.

Минимум по слоям:

| Слой | Проверки |
|------|----------|
| Репозиторий | `ansible-inventory --list`, YAML syntax, lint |
| Ansible | `--syntax-check`, `--check`, live run |
| Хост | пакеты, sysctl, systemd, idempotent rerun |
| WireGuard | `wg show`, handshakes, counters |
| Маршруты | `ip rule`, table 200/210, `ip route get` |
| nftables | `nft -c`, `nft list ruleset`, counters |
| E2E | клиент, DNS, RU/non-RU egress IP, fail-closed |

## Агент 1: Inventory и baseline

- актуальный `inventory/hosts.yml`, host_vars;
- `ansible all -m ping`, `playbooks/verify.yml`;
- стоп, если хост недоступен.

## Агент 2: Секреты и ключи

- каталог `~/.config/vpn-gen/wireguard/` вне git;
- ключи: entry_split client/transit, exit transit, initial client;
- `wg-secrets-init.sh`, `public-vars.yml` без приватных значений;
- `git status` не показывает `*.private.key`.

## Агент 3: common_network_base

- пакеты: wireguard, nftables, iproute2, curl;
- `net.ipv4.ip_forward=1`, nftables enabled;
- **без** VPN-интерфейсов.

## Агент 4: exit

- роль `roles/exit`;
- `wg-transit`, опционально `wg-exit-full` для full entry;
- nftables NAT/forward для `10.60.0.0/24` и `10.80.0.0/24`;
- проверки: `wg show`, `ip route get 10.60.0.10`.

## Агент 5: entry_split

- роль `roles/entry_split`;
- `wg-client` + `wg-transit`, table 200, fwmark 0x2;
- nftables: ru4, bypass, mark, masquerade;
- проверки: `ip rule`, table 200, ru4 в ruleset.

## Агент 6: GeoIP / RU CIDR

- скрипт `update-ru-zone.sh` на контроллере (live);
- опционально: systemd timer на entry (future);
- reload nft set без простоя SSH.

## Агент 7: Клиенты

- `wg-client` / `client_config.yml`;
- peer на entry, `.conf` + QR;
- handshake в `wg show`.

## Агент 8: Валидация

- `validate_cascade.yml`;
- E2E: RU → entry IP, non-RU → exit IP;
- outage test: stop exit transit.

## Порядок выполнения

1. Inventory + verify  
2. Secrets  
3. common_network_base  
4. exit  
5. entry_split (+ entry_full при необходимости)  
6. RU zone refresh  
7. Clients  
8. Validation  

## Milestones

| Этап | Содержание |
|------|------------|
| M1 Transit | только wg-transit entry↔exit |
| M2 Client VPN | wg-client, smoke all-via-entry |
| M3 Policy split | ru4 + mark + exit path |
| M4 Hardening | validate/rollback playbooks, wg-client |

## Ограничения для агентов

- не коммитить приватные ключи;
- не ломать SSH без запасного доступа;
- не затирать весь nftables без backup;
- не использовать auto-route injection WireGuard на transit;
- не допускать fallback non-RU через entry при мёртвом exit.
