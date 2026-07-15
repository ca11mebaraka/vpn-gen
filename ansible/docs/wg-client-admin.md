# Управление WireGuard-клиентами с Mac

Скрипт `scripts/wg-client` управляет клиентами entry-узлов. Профили загружаются из `deployments/<имя>/client-profiles.json` (по умолчанию `yandex-racknerd`).

## Профили (reference-деплой)

| Профиль | Узел | Интерфейс | Сеть клиентов | DNS | Порт |
|---------|------|-----------|---------------|-----|------|
| `split` | `176.123.164.26` lane 1 | `wg-client` | `10.60.0.0/24` | `10.60.0.1` | `53774` |
| `split2` | `176.123.164.26` lane 2 | `wg-client-2` | `10.61.0.0/24` | `10.61.0.1` | `54774` |
| `full` | `89.169.158.239` | `wg0` | `10.80.0.0/24` | `1.1.1.1` | `51944` |

Алиасы: `primary` → `split`, `direct` → `full`.

### Lane group `split`

Профили `split` и `split2` объединены в **lane group**: один пользователь — один ключ — два IP (`10.60.0.N` ↔ `10.61.0.N`).

```sh
./scripts/wg-client add user-alice --profile split
# создаёт split:user-alice и split2:user-alice, peers на wg-client и wg-client-2

./scripts/wg-client sync --profile split
# синхронизирует всех клиентов lane group на обе lane
```

В reference-деплое оба lane рабочие. Для новых клиентов (особенно Keenetic/роутеры) удобнее **lane 2** (`split2`); lane 1 (`split`) — через Racknerd после фикса transit-порта `49251`.

Ключи клиентов и реестр хранятся локально в `~/.config/vpn-gen/wg-client-admin/` и **не попадают в git**. На сервере peer добавляется в `/etc/wireguard/<interface>.conf` внутри маркеров `# wg-client-admin: begin <name>` … `# wg-client-admin: end <name>`.

## Требования

На Mac:

```sh
brew install wireguard-tools qrencode
```

SSH-доступ к entry настроен (`~/.ssh/yc_vm_ed25519`, пользователь `user1` на split entry).

## Быстрый старт

Из каталога `ansible`:

```sh
cd ansible
source scripts/load-env.sh

./scripts/wg-client profiles
./scripts/wg-client add laptop-ivan --profile split
./scripts/wg-client list
./scripts/wg-client list --remote --profile split2
```

Готовый конфиг по умолчанию: `~/Downloads/wg-<profile>-<name>.conf`.

## Команды

### `profiles`

```sh
./scripts/wg-client profiles
```

### `add <name>`

Создаёт пару ключей, назначает свободный IP, добавляет peer на сервер(а), сохраняет в реестр, выдаёт `.conf`.

```sh
./scripts/wg-client add phone-maria --profile full
./scripts/wg-client add laptop --profile split --address 10.60.0.20/32
./scripts/wg-client add tablet --profile split2 --dns 10.61.0.1
./scripts/wg-client add guest --profile split --output ~/Downloads/guest-vpn.conf
```

| Опция | Описание |
|-------|----------|
| `--profile` | `split`, `split2`, `full`; алиасы `primary`, `direct` |
| `--address` | IP на primary lane (`split`), mirror на `split2` автоматически |
| `--dns` | DNS в конфиге |
| `--mtu` | MTU (по умолчанию `1280`) |
| `--allowed-ips` | AllowedIPs (по умолчанию split-tunnel без IP endpoint) |
| `--persistent-keepalive` | Keepalive (по умолчанию `25`) |
| `--output` | Путь к `.conf` (только primary lane) |

### `edit`, `disable`, `enable`

```sh
./scripts/wg-client edit laptop-ivan --profile split --dns 10.60.0.1
./scripts/wg-client disable old-laptop --profile split
./scripts/wg-client enable old-laptop --profile split
```

### `list`

```sh
./scripts/wg-client list
./scripts/wg-client list --profile split2
./scripts/wg-client list --remote
```

### `export` / `qr`

```sh
./scripts/wg-client export laptop-ivan --profile split2
./scripts/wg-client export laptop-ivan --profile split --all-lanes
./scripts/wg-client qr phone-maria --profile split2 --output ~/Downloads/phone-qr.png
```

`--all-lanes` — конфиги для `split` и `split2` одним вызовом.

### `show-config`

```sh
./scripts/wg-client show-config laptop-ivan --profile split2
```

### `sync`

```sh
./scripts/wg-client sync --profile split
```

Синхронизирует **всю lane group** (`split` + `split2`). Обязательно после `ansible-playbook entry_split.yml`.

## Переменные окружения

| Переменная | По умолчанию | Назначение |
|------------|--------------|------------|
| `VPN_GEN_DEPLOYMENT` | `yandex-racknerd` | Каталог в `deployments/` |
| `VPN_GEN_WG_CLIENT_PROFILES` | — | Явный путь к JSON профилей |
| `VPN_GEN_CLIENT_ADMIN_DIR` | `~/.config/vpn-gen/wg-client-admin` | Реестр и ключи |
| `VPN_GEN_CLIENT_EXPORT_DIR` | `~/Downloads` | Каталог для `.conf` и QR |

## Структура локальных данных

```
~/.config/vpn-gen/wg-client-admin/
├── clients.json
├── split/
│   └── <name>/
│       ├── client.private.key
│       └── client.public.key
└── full/
    └── <name>/
        ├── client.private.key
        └── client.public.key
```

Ключи lane group хранятся в `split/<name>/`; записи реестра — `split:<name>` и `split2:<name>`.

## Типовые сценарии

### Новый пользователь (lane 2, рекомендуется)

```sh
./scripts/wg-client add user-alice --profile split
./scripts/wg-client qr user-alice --profile split2
```

Передайте `~/Downloads/wg-split2-user-alice.conf` или QR.

### Оба конфига (lane 1 + lane 2)

```sh
./scripts/wg-client export user-alice --profile split --all-lanes
```

### Кто подключён

```sh
ssh user1@176.123.164.26 'sudo wg show wg-client-2'
./scripts/wg-client list --remote --profile split2
```

## AllowedIPs

По умолчанию split-tunnel: весь IPv4 **минус** IP endpoint entry (carving для macOS/iOS). Длинный список в `.conf` — норма, не «лишние сети».

## Связь с Ansible

Скрипт управляет **только клиентскими peer'ами**. Ansible-роли настраивают серверы и transit.

Peer'ы из `wg-client` живут в marked-блоках конфига. После полного перезаписывания конфига ролью:

```sh
./scripts/wg-client sync --profile split
```

## Устранение неполадок

**SSH/sudo** — проверьте доступ:

```sh
ssh -i ~/.ssh/yc_vm_ed25519 user1@176.123.164.26 'sudo -n wg show wg-client-2'
```

**macOS routing loop** — не задавайте `--allowed-ips 0.0.0.0/0` вручную.

**После entry_split.yml пропали клиенты** — `./scripts/wg-client sync --profile split`.

**Lane 1: зарубеж не работает** — проверьте handshake `sudo wg show wg-transit` (должен быть `listening port: 49251`, peer с `latest handshake`). Если нет — см. [cascade-vpn-architecture.md](cascade-vpn-architecture.md) (UDP cloud.ru → Racknerd, смена ephemeral listen-порта). Временный обход: конфиг `split2`.

**DNS не резолвится** — клиент должен использовать `10.60.0.1` / `10.61.0.1`; на entry: `dig @10.61.0.1 yandex.ru`, `systemctl status dnsmasq`.

**Entry unreachable при `add`** — клиент создаётся локально в реестре; залейте на сервер позже: `./scripts/wg-client sync --profile split`.
