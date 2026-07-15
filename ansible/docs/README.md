# Документация

| Документ | Описание |
|----------|----------|
| [Архитектура каскадного VPN](cascade-vpn-architecture.md) | Топология, dual-exit, адреса, маршрутизация, DNS |
| [Имена и деплой](naming-and-deployment-plan.md) | Концепции entry/exit, split2, lane groups |
| [Секреты и конфиги клиента](secrets-and-client-config.md) | Ключи WireGuard вне git, dual-exit keys |
| [Управление клиентами](wg-client-admin.md) | `wg-client`: split / split2 / full, QR, sync |
| [Проверка и откат](validation-and-rollback.md) | validate_cascade (dual-exit, DNS, handshake), rollback |
| [Тестирование ролей WireGuard](testing-wireguard-roles.md) | Check-mode и live-проверки entry/exit |
| [Тестирование базовой сети](testing-common-network-base.md) | Роль `common_network_base` |
| [План оркестрации агентов](agent-orchestration-plan.md) | Пошаговый план для агентов/CI |
| [**ТЗ vpn-gen v2**](v2-development-spec.md) | Vendor-neutral refactor (work packages) |

Деплойments:

- [Каталог deployments](../deployments/README.md)
- [Reference: cloud.ru + Yandex + dual exit](../deployments/yandex-racknerd/README.md)

Главная страница: [README](../README.md)
