# Деплой: Yandex Cloud + Racknerd (reference / частный случай)

**Живая reference-установка**, на которой велась разработка. Сопоставление универсальных ролей с реальными машинами:

| Хост | Роль | Провайдер | Публичный IP | Примечание |
|------|------|-----------|--------------|------------|
| `entry_split_01` | Split entry | Yandex Cloud `ru-central1-a` | `51.250.14.221` | `wg-client` + GeoIP split |
| `entry_full_01` | Full entry | Yandex Cloud `ru-central1-a` | `89.169.158.239` | `wg0`, весь трафик через exit |
| `exit_01` | Exit / NAT | Racknerd VPS | `172.245.154.109` | `wg-transit` + `wg-exit-full` |

## Секреты на Mac (не в git)

| Путь | Назначение |
|------|------------|
| `~/.config/vpn-gen/wireguard/` | Ключи split entry + exit transit |
| `~/.config/vpn-gen/wireguard-entry-full/` | Ключи full entry + transit |
| `~/.config/vpn-gen/geo/ru.zone` | Список российских IPv4 CIDR для split |
| `~/.config/vpn-gen/wg-client-admin/` | Реестр клиентов `wg-client` |

## Конфигурация окружения

**Универсальный путь** (любой VPS-провайдер, везде `deploy`):

```sh
cd ansible
cp .env.example .env
# подставьте свои IP
source scripts/load-env.sh
ansible-playbook playbooks/verify_env.yml
```

**Частный reference-деплой** Yandex + Racknerd (`yc-user` на entry_full):

```sh
cp deployments/yandex-racknerd/.env.example .env
source scripts/load-env.sh
```

## SSH

После `source scripts/load-env.sh`:

```sh
ssh -i "$VPN_GEN_SSH_KEY_ENTRY" "$VPN_GEN_ENTRY_SPLIT_SSH_USER@$VPN_GEN_ENTRY_SPLIT_HOST"
ssh -i "$VPN_GEN_SSH_KEY_ENTRY" "$VPN_GEN_ENTRY_FULL_SSH_USER@$VPN_GEN_ENTRY_FULL_HOST"
ssh -i "$VPN_GEN_SSH_KEY_EXIT" "$VPN_GEN_EXIT_SSH_USER@$VPN_GEN_EXIT_HOST"
```

## Управление клиентами

По умолчанию `wg-client` загружает [`client-profiles.json`](client-profiles.json):

```sh
export VPN_GEN_DEPLOYMENT=yandex-racknerd   # значение по умолчанию
```

Профили: `split` (split entry), `full` (full entry). Алиасы `primary` и `direct` по-прежнему работают.

## Применение

Из каталога `ansible/` (сначала `source scripts/load-env.sh`):

```sh
source scripts/load-env.sh
ansible-playbook playbooks/common_network_base.yml
ansible-playbook playbooks/exit.yml
ansible-playbook playbooks/entry_split.yml
ansible-playbook playbooks/entry_full.yml
ansible-playbook playbooks/validate_cascade.yml
```

Перед изменениями split entry обновите список российских CIDR:

```sh
./scripts/update-ru-zone.sh
```
