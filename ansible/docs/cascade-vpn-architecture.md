# Архитектура каскадного VPN

## Цель

Двухступенчатый VPN на собственной инфраструктуре:

- пользователь подключается по WireGuard к **entry**-узлу;
- entry — точка входа и политики маршрутизации;
- «локальный» трафик (для РФ — адреса из GeoIP) выходит напрямую с entry;
- остальной трафик идёт через зашифрованный transit-туннель на **exit** и выходит в интернет оттуда;
- канал entry ↔ exit всегда зашифрован WireGuard.

## Текущие хосты (reference-деплой yandex-racknerd)

| Хост | Роль | IP | Провайдер | SSH |
|------|------|-----|-----------|-----|
| `entry_split_01` | Split entry (dual-exit) | `176.123.164.26` | cloud.ru | `user1` |
| `entry_full_01` | Full entry | `89.169.158.239` | Yandex Cloud | `yc-user` |
| `exit_01` | Exit lane 1 | `172.245.154.109` | Racknerd | `deploy` |
| `exit_02` | Exit lane 2 | `87.199.207.184` | VPS | `root` |

Подробности провайдера и `.env`: [`deployments/yandex-racknerd/README.md`](../deployments/yandex-racknerd/README.md).

## Логическая схема

```mermaid
flowchart LR
  user[Пользователь]
  split[entry_split\n176.123.164.26\nSplit + GeoIP]
  full[entry_full\n89.169.158.239\nВесь трафик через exit]
  exit1[exit_01\n172.245.154.109\nlane 1]
  exit2[exit_02\n87.199.207.184\nlane 2]
  local[Локальный интернет]
  world[Зарубежный интернет]

  user --> split
  user --> full
  split --> local
  split -->|lane 1 transit 10.70.0.0/30| exit1
  split -->|lane 2 transit 10.71.0.0/30| exit2
  full -->|transit 10.91.0.0/32| exit1
  exit1 --> world
  exit2 --> world
```

## Dual-exit split (lane 1 / lane 2)

На одном split entry могут работать **два независимых выхода**:

| Lane | Клиентский интерфейс | Порт | Подсеть клиентов | DNS | Transit | Exit |
|------|---------------------|------|------------------|-----|---------|------|
| 1 | `wg-client` | `53774` | `10.60.0.0/24` | `10.60.0.1` | `wg-transit` → `10.70.0.0/30` | `exit_01` |
| 2 | `wg-client-2` | `54774` | `10.61.0.0/24` | `10.61.0.1` | `wg-transit-2` → `10.71.0.0/30` | `exit_02` |

**Lane group `split`:** один пользователь — один ключ — два конфига. Адрес зеркалируется по host-октету: `10.60.0.N` ↔ `10.61.0.N`. Отдельные подсети устраняют конфликт маршрутов и DNS на entry.

Управление клиентами: `./scripts/wg-client add <name> --profile split` создаёт peers на обеих lane; конфиг lane 2 — `--profile split2` или `export --all-lanes`.

Включение dual-exit в Ansible: `entry_split_dual_exit_enabled: true` в `inventory/host_vars/entry_split_01.yml`.

## План адресов

| Сеть | Назначение |
|------|------------|
| `10.60.0.0/24` | Клиенты split lane 1 (`10.60.0.1` — сервер, exit_01) |
| `10.61.0.0/24` | Клиенты split lane 2 (`10.61.0.1` — сервер, exit_02) |
| `10.70.0.0/30` | Transit split lane 1 ↔ exit_01 (`10.70.0.1` / `10.70.0.2`) |
| `10.71.0.0/30` | Transit split lane 2 ↔ exit_02 (`10.71.0.1` / `10.71.0.2`) |
| `10.80.0.0/24` | Клиенты full entry (`10.80.0.1` — сервер) |
| `10.91.0.0/32` | Transit full ↔ exit (`10.91.0.1` / `10.91.0.2`) |
| table `200` | Policy routing lane 1: `fwmark 0x2` → `wg-transit` |
| table `201` | Policy routing lane 2: `fwmark 0x4` → `wg-transit-2` |
| table `210` | Policy routing full: трафик `10.80.0.0/24` → `wg-transit` |

Порты (reference):

| Назначение | Порт |
|------------|------|
| split lane 1 клиенты | `53774` |
| split lane 2 клиенты | `54774` |
| transit split на exit | `51821` |
| transit split listen на entry (cloud.ru) | `49248` / `49249` (ephemeral — см. host_vars) |
| full клиенты | `51944` |
| transit full entry | `51945` |
| exit full | `51946` |

## Интерфейсы WireGuard

### entry_split (dual-exit)

- **wg-client** — lane 1; `:53774`; `10.60.0.1/24`; exit_01
- **wg-client-2** — lane 2; `:54774`; `10.61.0.1/24`; exit_02
- **wg-transit** — tunnel на exit_01; `10.70.0.1/30`
- **wg-transit-2** — tunnel на exit_02; `10.71.0.1/30`

### entry_split (single-exit)

- **wg-client** — клиенты; endpoint split entry; адрес `10.60.0.1/24`
- **wg-transit** — tunnel на exit; `10.70.0.1/30`; peer exit `:51821`; `Table = off`

### entry_full

- **wg0** — клиенты; endpoint `89.169.158.239:51944`; адрес `10.80.0.1/24`
- **wg-transit** — tunnel на `wg-exit-full` exit; `10.91.0.1/32`; порт `51945`

### exit

- **exit_01 / wg-transit** — от split entry lane 1; `:51821`; `10.70.0.2/30`; AllowedIPs: `10.70.0.1/32, 10.60.0.0/24`
- **exit_02 / wg-transit** — от split entry lane 2; `:51821`; `10.71.0.2/30`; AllowedIPs: `10.71.0.1/32, 10.61.0.0/24`
- **wg-exit-full** (exit_01) — от full entry; `:51946`; `10.91.0.2/32`; AllowedIPs: `10.91.0.1/32, 10.80.0.0/24`

## Политика маршрутизации (split)

Трафик из клиентских подсетей классифицируется на entry:

1. **Bypass** — private/local/control + IP exit-узлов: не отправлять на transit
2. **RU CIDR (ru4)** — выход с публичного интерфейса entry + masquerade
3. **Остальное** — mark `0x2` (lane 1) или `0x4` (lane 2) → table `200` / `201` → соответствующий `wg-transit*` → exit + NAT

Если transit недоступен, немarkированный «зарубежный» трафик **не** должен «проскочить» напрямую с entry (fail-closed).

## Поток пакетов

**Локальный (RU) destination:** клиент → `wg-client*` → ru4 match → NAT на entry → виден IP entry.

**Зарубежный destination:** клиент → `wg-client*` → не в ru4 → mark → `wg-transit*` → exit NAT → виден IP exit.

## DNS

- Клиентам lane 1: DNS `10.60.0.1`; lane 2: DNS `10.61.0.1`.
- На entry: `dnsmasq` на `wg-client` + `wg-client-2` (`bind-interfaces`), upstream из `entry_split_dns_upstreams`, `filter-AAAA`.
- Маршрутизация по **IP после DNS**; CDN могут отдавать разные адреса — это ограничение IP-based split.

## nftables

**entry_split:** interval-set `ru4`, bypass-set, mangle (mark `0x2` / `0x4`), masquerade для локального выхода клиентов обеих lane.

**exit:** forward + masquerade для `10.60.0.0/24` (exit_01), `10.61.0.0/24` (exit_02), `10.80.0.0/24` (wg-exit-full).

После изменений nft на entry handler выполняет `nft -f /etc/nftables.conf` (не `systemctl reload`), чтобы правила гарантированно попали в kernel.

## Обновление списка RU CIDR

Кэш на Mac: `~/.config/vpn-gen/geo/ru.zone`. Обновление:

```sh
ansible/scripts/update-ru-zone.sh
```

Ansible-роль читает файл с контроллера и рендерит set `ru4`.

## Безопасность

- SSH только по ключам
- Отдельные ключи: клиенты / transit (на каждую lane)
- Секреты вне git
- Firewall: SSH, UDP WireGuard, established/related
- `Table = off` на transit — маршруты только явно через Ansible

## Операционные проверки

```sh
source scripts/load-env.sh
ansible all -m ping
ansible-playbook playbooks/verify.yml
ansible-playbook playbooks/validate_cascade.yml
```

На entry:

```sh
sudo wg show wg-client wg-client-2 wg-transit wg-transit-2
```

После `entry_split.yml` восстановите клиентские peers:

```sh
./scripts/wg-client sync --profile split
```

С клиента: RU → IP entry; non-RU → IP соответствующего exit; при падении transit non-RU не работает, RU — работает.

## Известные ограничения (reference-деплой)

- **cloud.ru entry:** egress UDP с «красивых» портов (51821 и т.п.) может блокироваться — для transit на entry используются ephemeral listen-порты (`49248`, `49249`), см. `entry_split_01.yml`.
- **Между cloud.ru и Racknerd:** UDP entry → exit_01 может не проходить на уровне провайдеров; lane 2 через exit_02 — рабочий резервный путь.
- **exit_02:** публичный интерфейс может называться `ens3`, не `eth0` — задаётся в `inventory/host_vars/exit_02.yml`.

## Вне scope первой версии

- маршрутизация по доменам;
- IPv6;
- self-service портал;
- обфускация поверх WireGuard.
