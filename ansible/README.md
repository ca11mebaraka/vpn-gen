# Ansible Inventory

This directory contains the Ansible configuration for the prepared Ubuntu VPN hosts.

## Рабочий процесс

Ниже — схема всей работы с VPN: от первоначальной настройки до выдачи доступа сотрудникам. Команды сгруппированы по этапам; пояснения написаны простым языком.

```mermaid
flowchart TB
    subgraph stage0["Этап 0. Подготовка на Mac (один раз)"]
        S0A["Создать ключи серверов<br/>scripts/wg-secrets-init.sh"]
        S0B["Обновить список российских IP<br/>scripts/update-ru-zone.sh"]
        S0C["Проверить, что секреты не попали в git<br/>scripts/check-no-private-key-material.sh"]
        S0A --> S0B --> S0C
    end

    subgraph stage1["Этап 1. Проверка доступа к серверам"]
        S1A["Убедиться, что все машины отвечают<br/>ansible all -m ping"]
        S1B["Проверить пользователей и sudo<br/>playbooks/verify.yml"]
        S1A --> S1B
    end

    subgraph stage2["Этап 2. Настройка серверов"]
        S2A["Базовая сеть на всех узлах<br/>playbooks/common_network_base.yml"]
        S2B["Выходной узел Racknerd<br/>playbooks/wireguard_transit.yml"]
        S2C["Входной узел со split-маршрутизацией<br/>playbooks/yandex_edge.yml"]
        S2D["Второй входной узел<br/>playbooks/yandex_direct_edge.yml"]
        S2A --> S2B --> S2C --> S2D
    end

    subgraph stage3["Этап 3. Проверка, что всё работает"]
        S3A["Комплексная проверка VPN<br/>playbooks/validate_cascade.yml"]
        S3B["Проверка скриптов и конфигов<br/>scripts/validate-wireguard-workflow.sh"]
        S3A --> S3B
    end

    subgraph stage4["Этап 4. Выдача доступа людям (регулярно)"]
        S4A["Посмотреть доступные серверы<br/>scripts/wg-client profiles"]
        S4B["Добавить нового пользователя<br/>scripts/wg-client add"]
        S4C["Выдать файл настроек<br/>scripts/wg-client export"]
        S4D["Выдать QR-код для телефона<br/>scripts/wg-client qr"]
        S4E["Изменить настройки<br/>scripts/wg-client edit"]
        S4F["Временно отключить<br/>scripts/wg-client disable"]
        S4G["Посмотреть список и активность<br/>scripts/wg-client list --remote"]
        S4H["Восстановить после сбоя<br/>scripts/wg-client sync"]
        S4A --> S4B --> S4C
        S4B --> S4D
        S4B --> S4E
        S4B --> S4F
        S4B --> S4G
        S4F --> S4H
    end

    subgraph stage5["Этап 5. Если что-то пошло не так"]
        S5A["Откатить настройки VPN<br/>playbooks/rollback_cascade.yml"]
        S5B["Подробная инструкция<br/>docs/validation-and-rollback.md"]
        S5A --- S5B
    end

    stage0 --> stage1 --> stage2 --> stage3 --> stage4
    stage3 -.->|"проблемы"| stage5
    stage4 -.->|"проблемы"| stage5
```

### Этап 0. Подготовка на Mac

| Что делаем | Зачем (простыми словами) | Команда |
|------------|--------------------------|---------|
| Создаём ключи | Генерируем «замки и ключи» для серверов; хранятся только на вашем Mac, не в git | [`scripts/wg-secrets-init.sh`](scripts/wg-secrets-init.sh) |
| Обновляем список российских IP | Чтобы split-VPN знал, какой трафик оставлять в России, а какой отправлять за рубеж | [`scripts/update-ru-zone.sh`](scripts/update-ru-zone.sh) |
| Проверяем git | Убеждаемся, что секретные ключи случайно не попали в репозиторий | [`scripts/check-no-private-key-material.sh`](scripts/check-no-private-key-material.sh) |
| Генерируем первый конфиг клиента | Создаёт файл настроек для тестового подключения (устаревший путь; для новых клиентов удобнее `wg-client`) | [`playbooks/client_config.yml`](playbooks/client_config.yml) |

Подробнее о секретах: [`docs/secrets-and-client-config.md`](docs/secrets-and-client-config.md)

### Этап 1. Проверка доступа

| Что делаем | Зачем | Команда |
|------------|-------|---------|
| Пинг всех серверов | Проверяем, что Mac «видит» все машины по сети | `ansible all -m ping` |
| Проверка пользователей | Убеждаемся, что можно зайти и выполнять команды от имени администратора | [`playbooks/verify.yml`](playbooks/verify.yml) |

Проверка одной группы: `ansible yandex_edge -m ping`, `ansible external_vps -m ping`

### Этап 2. Настройка серверов

| Что делаем | Зачем | Команда |
|------------|-------|---------|
| Базовая сеть | Включаем пересылку трафика и базовый файрвол на всех узлах | [`playbooks/common_network_base.yml`](playbooks/common_network_base.yml) |
| Racknerd | Настраиваем зарубежный «выход» в интернет | [`playbooks/wireguard_transit.yml`](playbooks/wireguard_transit.yml) |
| Primary Yandex | Настраиваем главный вход: российский трафик — из Yandex, остальной — через Racknerd | [`playbooks/yandex_edge.yml`](playbooks/yandex_edge.yml) |
| Direct Yandex | Настраиваем второй вход: весь трафик через Racknerd | [`playbooks/yandex_direct_edge.yml`](playbooks/yandex_direct_edge.yml) |

Архитектура и схема трафика: [`docs/cascade-vpn-architecture.md`](docs/cascade-vpn-architecture.md)

### Этап 3. Проверка работоспособности

| Что делаем | Зачем | Команда |
|------------|-------|---------|
| Комплексная проверка | Автоматически проверяет VPN, маршруты, сервисы на всех узлах | [`playbooks/validate_cascade.yml`](playbooks/validate_cascade.yml) |
| Проверка скриптов | Убеждается, что локальные скрипты и конфиги в порядке | [`scripts/validate-wireguard-workflow.sh`](scripts/validate-wireguard-workflow.sh) |

### Этап 4. Выдача доступа сотрудникам

Ежедневная работа — через [`scripts/wg-client`](scripts/wg-client). Полная инструкция: [`docs/wg-client-admin.md`](docs/wg-client-admin.md)

| Что делаем | Зачем | Команда |
|------------|-------|---------|
| Список серверов | Показывает два входа: `primary` (split) и `direct` (полный выход) | `./scripts/wg-client profiles` |
| Добавить человека | Создаёт личный ключ, прописывает на сервере, выдаёт файл настроек | `./scripts/wg-client add <имя> --profile primary` |
| Файл настроек | Пересохраняет `.conf` для импорта в WireGuard | `./scripts/wg-client export <имя> --profile primary` |
| QR-код | Картинка для быстрого подключения с телефона | `./scripts/wg-client qr <имя> --profile primary` |
| Изменить настройки | Меняет DNS, MTU или IP и обновляет сервер | `./scripts/wg-client edit <имя> --profile primary` |
| Отключить | Временно закрывает доступ без удаления ключей | `./scripts/wg-client disable <имя> --profile primary` |
| Включить обратно | Возвращает доступ | `./scripts/wg-client enable <имя> --profile primary` |
| Список клиентов | Показывает всех, кого вы добавляли | `./scripts/wg-client list` |
| Кто сейчас подключён | Показывает активность на сервере | `./scripts/wg-client list --remote` |
| Показать конфиг | Выводит настройки в терминал | `./scripts/wg-client show-config <имя> --profile primary` |
| Восстановить | Переносит всех клиентов из реестра обратно на сервер | `./scripts/wg-client sync` |

### Этап 5. Откат при проблемах

| Что делаем | Зачем | Команда |
|------------|-------|---------|
| Откат VPN | Возвращает серверы к безопасному состоянию | [`playbooks/rollback_cascade.yml`](playbooks/rollback_cascade.yml) |
| Инструкция | Пошаговые действия при сбоях | [`docs/validation-and-rollback.md`](docs/validation-and-rollback.md) |

Все команды ниже выполняются из каталога `ansible`:

```sh
cd ansible
```

## Hosts

- `yc_ubuntu_2404_min`
  - Role: split-routing Russian entry node
  - Public IP: `51.250.14.221`
  - Internal IP: `10.128.0.24`
  - User: `deploy`
  - SSH key: `~/.ssh/yc_vm_ed25519`
  - Sudo: passwordless

- `yandex_wg_direct`
  - Role: simple Yandex entry node with Racknerd exit
  - Public IP: `89.169.158.239`
  - Internal IP: `10.128.0.22`
  - User: `yc-user`
  - SSH key: `~/.ssh/yc_vm_ed25519`
  - Sudo: passwordless

- `racknerd_ubuntu`
  - Role: Racknerd exit for both Yandex entry nodes
  - Public IP: `172.245.154.109`
  - User: `deploy`
  - SSH key: `~/.ssh/vps_172_245_154_109_ed25519`
  - Sudo: passwordless

## Документация

- Архитектура VPN: [`docs/cascade-vpn-architecture.md`](docs/cascade-vpn-architecture.md)
- План автоматизации: [`docs/agent-orchestration-plan.md`](docs/agent-orchestration-plan.md)
- Управление клиентами: [`docs/wg-client-admin.md`](docs/wg-client-admin.md)
- Секреты и конфиги: [`docs/secrets-and-client-config.md`](docs/secrets-and-client-config.md)
- Проверка и откат: [`docs/validation-and-rollback.md`](docs/validation-and-rollback.md)

## Notes

Private keys and passwords are not stored in this repository. Host variables reference local secret paths under `~/.config/vpn-gen/`.
