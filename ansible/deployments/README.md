# Деплойments (конкретные установки)

Здесь лежат **значения, специфичные для окружения**. Роли и плейбуки Ansible в родительском каталоге не привязаны к провайдеру.

## Структура

```
deployments/
├── reference/              # Шаблон с placeholder-значениями (split + split2 + full)
│   └── client-profiles.json
└── yandex-racknerd/        # Живой reference-деплой
    ├── README.md
    ├── .env.example
    ├── client-profiles.json
    └── client-profiles.yml
```

## Новый деплой

1. Скопируйте `reference/client-profiles.json` → `deployments/<имя>/client-profiles.json`.
2. Отредактируйте `ansible/.env` — IP, SSH, exit_02 при dual-exit.
3. `ansible-playbook playbooks/verify_env.yml`.
4. Заполните `inventory/host_vars/*.yml` — публичные ключи WG, `entry_split_dual_exit_enabled`, peers.
5. `./scripts/wg-secrets-init.sh` (+ ключи lane 2 / exit_02 при dual-exit).
6. `export VPN_GEN_DEPLOYMENT=<имя>`.
7. Плейбуки по порядку (см. [README](../README.md)); затем `./scripts/wg-client sync --profile split`.

## Модель

| Концепция | Смысл |
|-----------|--------|
| **entry_split** | Split entry; RU — локально, остальное — на exit (lane 1 и/или 2) |
| **entry_full** | Весь трафик на exit |
| **exit_01** | Exit lane 1 (`10.60.0.0/24`) |
| **exit_02** | Exit lane 2 (`10.61.0.0/24`) |
| **split / split2** | Профили wg-client; lane group с общим ключом |

Имена провайдеров допустимы только в README деплоя.

## Reference-деплой

[`yandex-racknerd/README.md`](yandex-racknerd/README.md) — cloud.ru split entry, Yandex full entry, Racknerd exit_01, VPS exit_02.
