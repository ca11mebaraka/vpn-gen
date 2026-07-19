# MyVPN Admin

Закрытая панель управления WireGuard на выделенном controller-узле.

## Возможности

- Telegram Login с allowlist конкретных Telegram ID;
- состояние контроллера, российского entry и европейского exit;
- список peer, handshake и счётчики трафика;
- отдельные устройства внутри пользователя;
- создание `.conf` и QR;
- enable/disable/rotate/remove;
- SQLite-аудит действий.

## Запуск

```bash
cd admin
cp .env.example .env
# заполнить Telegram bot token и случайный session secret
docker compose up -d --build
```

Настройте DNS/Traefik host, Telegram admin ID и origin авторизации в локальном
`.env`. Если один Telegram-бот обслуживает несколько приложений, укажите
разрешённый Telegram-домен как `MYVPN_AUTH_BRIDGE_ORIGIN`: фиксированный relay
вернёт подписанный payload на `MYVPN_ADMIN_PUBLIC_ORIGIN`.

Приложение намеренно не стартует без Telegram token и session secret длиной от 32 символов.
