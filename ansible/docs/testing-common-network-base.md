# Тестирование common_network_base

Валидация роли `roles/common_network_base` — подготовка Ubuntu-хостов к WireGuard и маршрутизации (без самих туннелей и правил nftables).

## Локальная проверка

Из `ansible/`:

```sh
mkdir -p .ansible-tmp
ANSIBLE_LOCAL_TEMP="$PWD/.ansible-tmp" ansible-inventory --list
ANSIBLE_LOCAL_TEMP="$PWD/.ansible-tmp" ansible-playbook playbooks/common_network_base.yml --syntax-check
rmdir .ansible-tmp
```

Inventory должен видеть хосты (`entry_split_01`, `exit_01`, `exit_02`, …).

## Check-mode

```sh
ansible-playbook playbooks/common_network_base.yml --check --diff
```

Требует SSH. При `Permission denied` — настроить ключи в `inventory/host_vars/`.

## Live apply

```sh
ansible-playbook playbooks/common_network_base.yml --diff
ansible-playbook playbooks/common_network_base.yml --diff   # второй прогон — без изменений
```

Проверки на хостах:

```sh
ansible all -m command -a "sysctl net.ipv4.ip_forward"
ansible all -m command -a "wg --version"
ansible all -m command -a "nft list ruleset"
ansible all -m systemd -a "name=nftables"
```

Ожидается: `ip_forward=1`, `wg` и `nft` доступны, `nftables` enabled/active.
