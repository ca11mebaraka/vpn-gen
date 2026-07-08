# План оркестрации агентов

Реализация каскадного VPN из [`cascade-vpn-architecture.md`](cascade-vpn-architecture.md) через небольшие Ansible-роли с чётким разделением задач.

## Целевое состояние

- пользователь подключается к entry по WireGuard;
- split entry выпускает «локальный» трафик напрямую;
- split entry отправляет остальной трафик в зашифрованный tunnel на exit (lane 1 и/или lane 2);
- exit делает NAT в интернет;
- при падении tunnel non-RU трафик **не** уходит напрямую с entry (fail-closed).

## Дисциплина тестирования

| Слой | Проверки |
|------|----------|
| Репозиторий | `ansible-inventory --list`, YAML syntax, lint |
| Ansible | `--syntax-check`, `--check`, live run |
| Хост | пакеты, sysctl, systemd, idempotent rerun |
| WireGuard | `wg show`, handshakes, counters |
| Маршруты | `ip rule`, tables 200/201/210, `ip route get` |
| nftables | `nft -c`, `nft list ruleset`, counters |
| E2E | клиент split/split2, DNS, RU/non-RU egress IP, fail-closed |

## Агент 1: Inventory и baseline

- `inventory/hosts.yml`: `entry_split_01`, `entry_full_01`, `exit_01`, `exit_02`;
- `ansible/.env` + `verify_env.yml`;
- `ansible all -m ping`, `playbooks/verify.yml`.

## Агент 2: Секреты и ключи

- `~/.config/vpn-gen/wireguard/` вне git;
- ключи: entry_split client/transit (+ client_2/transit_2 при dual-exit), exit_01/exit_02 transit;
- `wg-secrets-init.sh`, `public-vars.yml` без приватных значений.

## Агент 3: common_network_base

- wireguard, nftables, iproute2; `ip_forward=1`;
- **без** VPN-интерфейсов.

## Агент 4: exit

- роль `roles/exit` на `exit_01` и `exit_02`;
- exit_01: `wg-transit` (`10.60.0.0/24`) + опционально full entry;
- exit_02: `wg-transit` (`10.61.0.0/24`), `exit_public_interface` из host_vars;
- nftables NAT/forward.

## Агент 5: entry_split

- `wg-client` + `wg-transit` (lane 1);
- при `entry_split_dual_exit_enabled`: `wg-client-2` + `wg-transit-2`;
- tables 200/201, fwmark 0x2/0x4;
- nftables: ru4, bypass, mark, masquerade;
- dnsmasq на обеих lane;
- `meta: flush_handlers` перед dnsmasq; nft reload через `nft -f`.

## Агент 6: GeoIP / RU CIDR

- `update-ru-zone.sh` на контроллере;
- reload nft set `ru4`.

## Агент 7: Клиенты

- `wg-client add/sync` — lane group `split`;
- `.conf` + QR для `split` и `split2`;
- handshake в `wg show wg-client` / `wg-client-2`.

## Агент 8: Валидация

- `validate_cascade.yml`;
- E2E lane 2 (reference): non-RU → exit_02;
- outage test: stop transit на exit.

## Порядок выполнения

1. Inventory + verify  
2. Secrets (+ dual-exit keys)  
3. common_network_base  
4. exit (`exit_01`, `exit_02`)  
5. entry_split (+ entry_full при необходимости)  
6. RU zone refresh  
7. `wg-client sync --profile split`  
8. Validation  

## Milestones

| Этап | Содержание |
|------|------------|
| M1 Transit | wg-transit entry↔exit |
| M2 Client VPN | wg-client, smoke |
| M3 Policy split | ru4 + mark + exit path |
| M4 Dual-exit | wg-client-2, exit_02, split2 profile |
| M5 Hardening | validate/rollback, wg-client lane groups |

## Ограничения для агентов

- не коммитить приватные ключи;
- не ломать SSH без запасного доступа;
- после `entry_split.yml` — `wg-client sync`;
- не использовать auto-route injection WireGuard на transit;
- не допускать fallback non-RU через entry при мёртвом exit.
