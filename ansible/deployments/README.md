# Деплойments (конкретные установки)

Здесь лежат **значения, специфичные для окружения**. Роли и плейбуки Ansible в родительском каталоге не привязаны к провайдеру; только файлы здесь и `inventory/host_vars/` описывают конкретную установку.

## Структура

```
deployments/
├── reference/              # Шаблон с placeholder-значениями
│   └── client-profiles.json
└── yandex-racknerd/        # Живой reference-деплой (частный случай)
    ├── README.md
    └── client-profiles.json
```

## Новый деплой

1. Скопируйте `reference/client-profiles.json` в `deployments/<ваше-имя>/client-profiles.json`.
2. Отредактируйте `ansible/.env` — IP и SSH (шаблон `.env.example`; для Yandex+Racknerd см. `deployments/yandex-racknerd/.env.example`).
3. Проверка без SSH: `ansible-playbook playbooks/verify_env.yml`.
4. Заполните `inventory/host_vars/*.yml` — публичные ключи WireGuard и peers (не пути `/Users/.../`).
5. Создайте ключи серверов: `./scripts/wg-secrets-init.sh`.
6. Укажите деплой для управления клиентами:

```sh
export VPN_GEN_DEPLOYMENT=<ваше-имя>
# или явно:
export VPN_GEN_WG_CLIENT_PROFILES="$PWD/deployments/<ваше-имя>/client-profiles.json"
```

7. Примените плейбуки по порядку (см. [README](../README.md)).

## Модель

| Концепция | Смысл |
|-----------|--------|
| **entry_split** | Пользователь подключается сюда; «свой» трафик выходит локально, остальной — на **exit** |
| **entry_full** | Пользователь подключается сюда; весь трафик идёт на **exit** |
| **exit** | Принимает зашифрованный transit от entry и делает NAT в интернет |

Имена провайдеров (Yandex Cloud, Racknerd, AWS, Hetzner, …) допустимы только в README деплоя, не в ролях и общих docs.
