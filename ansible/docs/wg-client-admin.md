# Управление WireGuard-клиентами с Mac

Скрипт `scripts/wg-client` управляет клиентами двух входных узлов Yandex Cloud:

| Профиль | Узел | Интерфейс | Сеть клиентов | DNS по умолчанию |
|---------|------|-----------|---------------|------------------|
| `primary` | `51.250.14.221` (split-routing) | `wg-client` | `10.60.0.0/24` | `10.60.0.1` |
| `direct` | `89.169.158.239` (полный выход через Racknerd) | `wg0` | `10.80.0.0/24` | `1.1.1.1` |

Ключи клиентов и реестр хранятся локально в `~/.config/vpn-gen/wg-client-admin/` и **не попадают в git**. На сервере peer добавляется в `/etc/wireguard/<interface>.conf` внутри маркеров `# wg-client-admin: begin <name>` … `# wg-client-admin: end <name>`.

## Требования

На Mac должны быть установлены:

```sh
brew install wireguard-tools qrencode
```

SSH-доступ к узлам Yandex уже настроен (`~/.ssh/yc_vm_ed25519`, пользователи `deploy` / `yc-user`).

## Быстрый старт

Из каталога `ansible`:

```sh
cd ansible

# Список профилей
./scripts/wg-client profiles

# Добавить клиента (ключи создаются автоматически, peer синхронизируется на сервер)
./scripts/wg-client add laptop-ivan --profile primary

# Список управляемых клиентов
./scripts/wg-client list

# Список + состояние на сервере
./scripts/wg-client list --remote
```

Готовый конфиг по умолчанию сохраняется в `~/Downloads/wg-<profile>-<name>.conf`.

## Команды

### `profiles`

Показывает доступные профили серверов.

```sh
./scripts/wg-client profiles
```

### `add <name>`

Создаёт пару ключей, назначает свободный IP, добавляет peer на сервер, сохраняет запись в реестр и выдаёт `.conf`.

```sh
./scripts/wg-client add phone-maria --profile direct
./scripts/wg-client add laptop --profile primary --address 10.60.0.20/32
./scripts/wg-client add tablet --profile primary --dns 10.60.0.1 --mtu 1280
./scripts/wg-client add guest --profile primary --output ~/Downloads/guest-vpn.conf
```

Опции:

| Опция | Описание |
|-------|----------|
| `--profile` | `primary` (по умолчанию) или `direct` |
| `--address` | IP клиента, например `10.60.0.20/32` |
| `--dns` | DNS в конфиге клиента |
| `--mtu` | MTU (по умолчанию `1280`) |
| `--allowed-ips` | AllowedIPs для клиента (по умолчанию `0.0.0.0/0` без IP endpoint, чтобы избежать routing loop на macOS) |
| `--persistent-keepalive` | Keepalive (по умолчанию `25`) |
| `--output` | Путь к `.conf` |

### `edit <name>`

Меняет параметры клиента и пересинхронизирует peer на сервере.

```sh
./scripts/wg-client edit laptop-ivan --profile primary --dns 1.1.1.1
./scripts/wg-client edit phone-maria --profile direct --mtu 1420
./scripts/wg-client edit laptop --profile primary --address 10.60.0.25/32
```

### `disable <name>` / `enable <name>`

Отключает или включает клиента на сервере. Локальные ключи и запись в реестре сохраняются.

```sh
./scripts/wg-client disable old-laptop --profile primary
./scripts/wg-client enable old-laptop --profile primary
```

### `list`

```sh
./scripts/wg-client list
./scripts/wg-client list --profile direct
./scripts/wg-client list --remote
```

### `export <name>`

Записывает `.conf` без изменения сервера.

```sh
./scripts/wg-client export laptop-ivan --profile primary
./scripts/wg-client export phone-maria --profile direct --output ~/Downloads/phone.conf
```

### `qr <name>`

Генерирует PNG с QR-кодом конфигурации (удобно для телефона).

```sh
./scripts/wg-client qr phone-maria --profile direct
./scripts/wg-client qr laptop-ivan --profile primary --output ~/Downloads/laptop-qr.png
```

### `show-config <name>`

Печатает конфиг в stdout (для копирования или пайпа).

```sh
./scripts/wg-client show-config laptop-ivan --profile primary
```

### `sync`

Пересинхронизирует всех клиентов из реестра на сервер(а).

```sh
./scripts/wg-client sync
./scripts/wg-client sync --profile primary
```

Полезно после ручного отката конфигурации на сервере или восстановления из бэкапа.

## Переменные окружения

| Переменная | По умолчанию | Назначение |
|------------|--------------|------------|
| `VPN_GEN_CLIENT_ADMIN_DIR` | `~/.config/vpn-gen/wg-client-admin` | Реестр и ключи клиентов |
| `VPN_GEN_CLIENT_EXPORT_DIR` | `~/Downloads` | Каталог для `.conf` и QR по умолчанию |

## Структура локальных данных

```
~/.config/vpn-gen/wg-client-admin/
├── clients.json              # реестр всех клиентов
├── primary/
│   └── <name>/
│       ├── client.private.key
│       └── client.public.key
└── direct/
    └── <name>/
        ├── client.private.key
        └── client.public.key
```

Права: каталог `0700`, приватные ключи и `clients.json` — `0600`.

## Типовые сценарии

### Выдать VPN новому пользователю

```sh
./scripts/wg-client add user-alice --profile primary
./scripts/wg-client qr user-alice --profile primary
```

Передайте файл `~/Downloads/wg-primary-user-alice.conf` или QR-код.

### Временно отключить доступ

```sh
./scripts/wg-client disable user-alice --profile primary
```

### Сменить DNS или MTU

```sh
./scripts/wg-client edit user-alice --profile primary --dns 10.60.0.1 --mtu 1280
./scripts/wg-client export user-alice --profile primary --output ~/Downloads/user-alice-new.conf
```

### Проверить, кто подключён

```sh
./scripts/wg-client list --remote --profile primary
```

В выводе `wg show` смотрите `latest handshake` у каждого peer.

## Связь с Ansible

Скрипт управляет **только клиентскими peer'ами** через SSH и не заменяет Ansible-роли для базовой настройки серверов (`yandex_edge`, `yandex_direct_edge`). Существующие peer'ы, созданные вручную или через Ansible (например `initial-client`, `fresh-client`, `direct-client`), не импортируются автоматически — их можно продолжать вести через inventory/host_vars.

Новые клиенты, добавленные через `wg-client`, живут в отдельных marked-блоках конфига и не конфликтуют с Ansible, пока вы не перезаписываете весь файл ролью без сохранения этих блоков.

## Проверка установки

```sh
cd ansible
./scripts/wg-client profiles
./scripts/wg-client list --remote
python3 -m py_compile scripts/wg-client-admin.py
```

## Устранение неполадок

**`ERROR: missing required tool(s): wg`** — установите `wireguard-tools`.

**`ERROR: missing required tool(s): qrencode`** — нужен только для `qr`; установите `qrencode`.

**SSH/sudo ошибка** — проверьте доступ:

```sh
ssh -i ~/.ssh/yc_vm_ed25519 deploy@51.250.14.221 'sudo -n wg show wg-client'
ssh -i ~/.ssh/yc_vm_ed25519 yc-user@89.169.158.239 'sudo -n wg show wg0'
```

**Клиент не подключается на macOS** — убедитесь, что в AllowedIPs **нет** IP endpoint сервера. Скрипт исключает его автоматически; не задавайте `--allowed-ips 0.0.0.0/0` вручную.

**После `ansible-playbook yandex_edge.yml` пропали клиенты** — роль перезаписывает конфиг из шаблона. Восстановите клиентов:

```sh
./scripts/wg-client sync --profile primary
```
