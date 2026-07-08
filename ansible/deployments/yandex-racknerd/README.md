# Деплой: cloud.ru + Yandex Cloud + dual exit (reference)

**Живая reference-установка**, на которой велась разработка. Сопоставление универсальных ролей с реальными машинами:

| Хост | Роль | Провайдер | Публичный IP | Примечание |
|------|------|-----------|--------------|------------|
| `entry_split_01` | Split entry (dual-exit) | cloud.ru | `176.123.164.26` | `wg-client` + `wg-client-2`, GeoIP split |
| `entry_full_01` | Full entry | Yandex Cloud `ru-central1-a` | `89.169.158.239` | `wg0`, весь трафик через exit_01 |
| `exit_01` | Exit lane 1 / NAT | Racknerd VPS | `172.245.154.109` | `wg-transit` для lane 1 + `wg-direct-exit` (full) |
| `exit_02` | Exit lane 2 / NAT | VPS | `87.199.207.184` | `wg-transit` для lane 2 (`10.61.0.0/24`) |

> Исторически split entry был на Yandex Cloud (`51.250.14.221`); сейчас перенесён на cloud.ru. Каталог деплоя сохраняет имя `yandex-racknerd`.

## Dual-exit split

| Lane | wg-client | Порт | Подсеть | Exit | Профиль wg-client |
|------|-----------|------|---------|------|-------------------|
| 1 | `wg-client` | `53774` | `10.60.0.0/24` | exit_01 | `split` |
| 2 | `wg-client-2` | `54774` | `10.61.0.0/24` | exit_02 | `split2` |

Рекомендуемый рабочий lane для новых клиентов — **lane 2** (`split2`), пока UDP-путь entry (cloud.ru) → exit_01 (Racknerd) нестабилен.

## Секреты на Mac (не в git)

| Путь | Назначение |
|------|------------|
| `~/.config/vpn-gen/wireguard/` | Ключи split entry (lane 1 + 2) + exit transit |
| `~/.config/vpn-gen/wireguard-entry-full/` | Ключи full entry + transit |
| `~/.config/vpn-gen/geo/ru.zone` | Список российских IPv4 CIDR для split |
| `~/.config/vpn-gen/wg-client-admin/` | Реестр клиентов `wg-client` |

Дополнительные ключи dual-exit (имена файлов в `host_vars`):

- `entry_split_wg_client_2.private.key`
- `entry_split_wg_transit_2.private.key`
- `exit2_wg_transit.private.key`

## Конфигурация окружения

**Частный reference-деплой** (скопируйте в `ansible/.env`):

```sh
cd ansible
cp deployments/yandex-racknerd/.env.example .env
# отредактируйте IP и пути к ключам
source scripts/load-env.sh
ansible-playbook playbooks/verify_env.yml
```

**Универсальный шаблон** (любой VPS, один пользователь `deploy`):

```sh
cp .env.example .env
source scripts/load-env.sh
```

## SSH

После `source scripts/load-env.sh`:

```sh
ssh -i "$VPN_GEN_SSH_KEY_ENTRY" "$VPN_GEN_ENTRY_SPLIT_SSH_USER@$VPN_GEN_ENTRY_SPLIT_HOST"
ssh -i "$VPN_GEN_SSH_KEY_ENTRY" "$VPN_GEN_ENTRY_FULL_SSH_USER@$VPN_GEN_ENTRY_FULL_HOST"
ssh -i "$VPN_GEN_SSH_KEY_EXIT" "$VPN_GEN_EXIT_SSH_USER@$VPN_GEN_EXIT_HOST"
ssh -i "$VPN_GEN_SSH_KEY_EXIT2" "$VPN_GEN_EXIT2_SSH_USER@$VPN_GEN_EXIT2_HOST"
```

Примеры с текущими IP:

```sh
ssh -i ~/.ssh/yc_vm_ed25519 user1@176.123.164.26          # split entry
ssh -i ~/.ssh/yc_vm_ed25519 yc-user@89.169.158.239        # full entry
ssh -i ~/.ssh/vps_172_245_154_109_ed25519 deploy@172.245.154.109   # exit_01
ssh -i ~/.ssh/yc_vm_ed25519 root@87.199.207.184           # exit_02
```

## Управление клиентами

По умолчанию `wg-client` загружает [`client-profiles.json`](client-profiles.json):

```sh
export VPN_GEN_DEPLOYMENT=yandex-racknerd   # значение по умолчанию
```

Профили:

| Профиль | Назначение |
|---------|------------|
| `split` | lane 1 — `wg-client`, `10.60.0.x`, порт `53774` |
| `split2` | lane 2 — `wg-client-2`, `10.61.0.x`, порт `54774` |
| `full` | full entry — `wg0`, `10.80.0.x` |

Алиасы: `primary` → `split`, `direct` → `full`.

```sh
# один ключ — обе lane
./scripts/wg-client add user-alice --profile split
./scripts/wg-client export user-alice --profile split --all-lanes
./scripts/wg-client qr user-alice --profile split2
```

## Применение

Из каталога `ansible/` (сначала `source scripts/load-env.sh`):

```sh
source scripts/load-env.sh
./scripts/update-ru-zone.sh
ansible-playbook playbooks/common_network_base.yml
ansible-playbook playbooks/exit.yml
ansible-playbook playbooks/entry_split.yml
ansible-playbook playbooks/entry_full.yml   # если VPN_GEN_EXIT_ENTRY_FULL_ENABLED=true
ansible-playbook playbooks/validate_cascade.yml
./scripts/wg-client sync --profile split    # после entry_split — восстановить клиентов
```

Выборочный деплой exit:

```sh
ansible-playbook playbooks/exit.yml --limit exit_01
ansible-playbook playbooks/exit.yml --limit exit_02
```
