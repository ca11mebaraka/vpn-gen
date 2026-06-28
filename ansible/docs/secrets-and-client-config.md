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

Из корня репозитория:

```sh
ansible/scripts/wg-secrets-init.sh
```

Скрипт идемпотентен: создаёт недостающие ключи и проверяет пары, не перезаписывая существующие приватные ключи.

Генерируемые пары:

- `entry_split_wg_client`
- `entry_split_wg_transit`
- `exit_wg_transit`
- `initial_client`

Полезные режимы:

```sh
ansible/scripts/wg-secrets-init.sh --help
ansible/scripts/wg-secrets-init.sh --dry-run
ansible/scripts/wg-secrets-init.sh --check
```

Для реальной инициализации нужна утилита `wg` из wireguard-tools. Каталог секретов должен принадлежать текущему пользователю, не быть symlink, права `0700`; приватные ключи — `0600`.

Переопределения через env (удобнее всего — файл `ansible/.env`, см. [`.env.example`](../.env.example)):

```sh
cd ansible
cp .env.example .env
source scripts/load-env.sh
ansible/scripts/wg-secrets-init.sh
```

Ключевые переменные:

```sh
VPN_GEN_WG_SECRET_DIR="$HOME/.config/vpn-gen/wireguard"
VPN_GEN_WG_PUBLIC_VARS_FILE="$HOME/.config/vpn-gen/wireguard/public-vars.yml"
VPN_GEN_WG_CLIENT_CONFIG_PATH="$HOME/.config/vpn-gen/wireguard/initial-client.conf"
VPN_GEN_WG_CLIENT_ENDPOINT_HOST="$VPN_GEN_ENTRY_SPLIT_HOST"
VPN_GEN_WG_CLIENT_ENDPOINT_PORT="53774"
VPN_GEN_EXIT_TRANSIT_PORT="51821"
```

Пути в `inventory/host_vars/` строятся из `$HOME/.config/vpn-gen/...` через `group_vars/all/controller.yml` — **не прописывайте** `/Users/<имя>/...` в git.

## Генерация первого клиентского конфига

После создания секретов:

```sh
cd ansible
ansible-playbook -i inventory/hosts.yml playbooks/client_config.yml
```

Шаблон читает приватный ключ клиента только с локального диска во время генерации. Готовый `.conf` по умолчанию пишется вне репозитория.

> Для новых пользователей удобнее [`wg-client`](wg-client-admin.md) — он создаёт ключи, peer на сервере и QR автоматически.

## Проверка утечек

```sh
ansible/scripts/check-no-private-key-material.sh
```

Проверяется:

- tracked-файлы `*.private.key`;
- строки вида `PrivateKey = <base64>` в git;
- совпадение с локальными `*.private.key`, если каталог секретов существует.

Полная локальная проверка workflow:

```sh
ansible/scripts/validate-wireguard-workflow.sh
```

## Переменные для ролей

Сгенерированные имена (фрагмент):

- entry `wg-client`: `wireguard_entry_split_wg_client_*`, `wireguard_client_*`
- entry `wg-transit`: `wireguard_entry_split_wg_transit_*`, `wireguard_exit_wg_transit_public_key`
- exit `wg-transit`: `wireguard_exit_wg_transit_*`
- клиент: `wireguard_initial_client_*`, `wireguard_entry_split_client_endpoint_*`, `wireguard_client_allowed_ips`

На macOS в `wireguard_client_allowed_ips` **исключайте IP endpoint** (например `51.250.14.221/32`), иначе туннель зациклит маршрут к серверу.

Приватные ключи можно читать с контроллера при рендере конфигов WireGuard, но **нельзя** класть их значения в inventory, host_vars, docs или коммитируемые vars.
