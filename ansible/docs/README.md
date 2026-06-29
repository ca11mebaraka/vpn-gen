# Документация

| Документ | Описание |
|----------|----------|
| [Архитектура каскадного VPN](cascade-vpn-architecture.md) | Топология, адреса, маршрутизация, DNS, безопасность |
| [Имена и деплой](naming-and-deployment-plan.md) | Концепции entry/exit, перенос с провайдерских имён |
| [Секреты и конфиги клиента](secrets-and-client-config.md) | Ключи WireGuard вне git, `wg-secrets-init.sh` |
| [Управление клиентами](wg-client-admin.md) | Скрипт `wg-client`: добавление, QR, отключение |
| [Проверка и откат](validation-and-rollback.md) | `validate_cascade.yml`, `rollback_cascade.yml` |
| [Тестирование ролей WireGuard](testing-wireguard-roles.md) | Check-mode и live-проверки entry/exit |
| [Тестирование базовой сети](testing-common-network-base.md) | Роль `common_network_base` |
| [План оркестрации агентов](agent-orchestration-plan.md) | Пошаговый план автоматизации для агентов/CI |
| [**ТЗ vpn-gen v2**](v2-development-spec.md) | Задание на чистую версию: без рудиментов, vendor-neutral, work packages |

Деплойments:

- [Каталог deployments](../deployments/README.md)
- [Пример: Yandex + Racknerd](../deployments/yandex-racknerd/README.md)

Главная страница с диаграммой рабочего процесса: [README](../README.md)
