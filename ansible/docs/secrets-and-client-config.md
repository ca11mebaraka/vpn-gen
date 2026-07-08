# Секреты WireGuard и конфиг клиента

Приватные ключи WireGuard хранятся **вне git**. Ansible получает только публичные ключи и пути к локальным файлам с приватными ключами.

## Файлы

- Каталог секретов: `~/.config/vpn-gen/wireguard/`
- Публичные переменные: `~/.config/vpn-gen/wireguard/public-vars.yml`
- Первый клиентский конфиг: `~/.config/vpn-gen/wireguard/initial-client.conf`
- Скрипты:
  - `ansible/scripts/wg-secrets-init.sh`
  - `ansible/scripts/check-no-private-key-material.sh`
  - `ansible/scripts/validate-wireguard-workflow.sh`
- Шаблон: `ansible/templates/client/initial-client.conf.j2`
- Плейбук: `ansible/playbooks/client_config.yml`

Файл `public-vars.yml` содержит только публичные ключи и пути. **Значений приватных ключей там быть не должно.**

## Инициализация и проверка

```sh
cd ansible
cp .env.example .env   # или deployments/yandex-racknerd/.env.example
source scripts/load-env.sh
../ansible/scripts/wg-secrets-init.sh
```

Скрипт идемпотентен: создаёт недостающие ключи, не перезаписывает существующие.

Базовые пары (single-exit):

- `entry_split_wg_client`
- `entry_split_wg_transit`
- `exit_wg_transit`
- `initial_client`

**Dual-exit** (дополнительно, вручную или через `wg genkey`):

| Файл | Назначение |
|------|------------|
| `entry_split_wg_client_2.private.key` | Сервер lane 2 (`wg-client-2`) |
| `entry_split_wg_transit_2.private.key` | Transit lane 2 (`wg-transit-2`) |
| `exit2_wg_transit.private.key` | Transit на `exit_02` |

Пути задаются в `inventory/group_vars/all/controller.yml` и `host_vars/exit_02.yml`.

```sh
ansible/scripts/wg-secrets-init.sh --help
ansible/scripts/wg-secrets-init.sh --dry-run
ansible/scripts/wg-secrets-init.sh --check
```

## Переменные окружения

```sh
VPN_GEN_WG_SECRET_DIR="$HOME/.config/vpn-gen/wireguard"
VPN_GEN_WG_PUBLIC_VARS_FILE="$HOME/.config/vpn-gen/wireguard/public-vars.yml"
VPN_GEN_WG_CLIENT_ENDPOINT_HOST="$VPN_GEN_ENTRY_SPLIT_HOST"
VPN_GEN_WG_CLIENT_ENDPOINT_PORT="53774"
VPN_GEN_ENTRY_SPLIT_CLIENT_PORT_2="54774"
VPN_GEN_EXIT_TRANSIT_PORT="51821"
VPN_GEN_EXIT2_TRANSIT_PORT="51821"
```

Пути в `inventory/host_vars/` строятся из `$HOME/.config/vpn-gen/...` — **не прописывайте** `/Users/<имя>/...` в git.

## Генерация первого клиентского конфига

```sh
cd ansible
ansible-playbook -i inventory/hosts.yml playbooks/client_config.yml
```

> Для новых пользователей удобнее [`wg-client`](wg-client-admin.md) — ключи, peer на сервере и QR автоматически.

## Проверка утечек

```sh
ansible/scripts/check-no-private-key-material.sh
ansible/scripts/validate-wireguard-workflow.sh
```

## Переменные для ролей

Фрагмент имён (см. `group_vars/all/controller.yml`):

| Компонент | Переменные |
|-----------|------------|
| entry `wg-client` | `entry_split_wg_client_*` |
| entry `wg-client-2` | `entry_split_wg_client_2_*` |
| entry `wg-transit` | `entry_split_wg_transit_*` |
| entry `wg-transit-2` | `entry_split_wg_transit_2_*` |
| exit_01 `wg-transit` | `exit_wg_transit_*` |
| exit_02 `wg-transit` | `exit_wg_transit_*` + `exit_client_cidr: 10.61.0.0/24` |

На macOS в AllowedIPs клиента **исключайте IP endpoint** entry — скрипт `wg-client` делает это автоматически.

Приватные ключи **нельзя** класть в inventory, host_vars, docs или коммитируемые vars.
