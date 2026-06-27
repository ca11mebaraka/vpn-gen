# Validation And Rollback

This document covers the validation and rollback scaffolding for the cascade VPN:

- Yandex Cloud accepts user WireGuard clients on `wg-client`.
- Yandex Cloud sends non-RU marked traffic through `wg-transit`.
- Racknerd exits non-RU client traffic to the Internet.
- RU traffic exits directly from Yandex Cloud.
- The secondary Yandex direct edge accepts clients on `wg0` and sends all client
  traffic through Racknerd `wg-direct-exit`.

## Static Checks

Run these checks from the `ansible/` directory after editing validation or rollback playbooks:

```sh
ansible-inventory -i inventory/hosts.yml --list
ansible-playbook -i inventory/hosts.yml playbooks/validate_cascade.yml --syntax-check
ansible-playbook -i inventory/hosts.yml playbooks/rollback_cascade.yml --syntax-check
```

## Validation Playbook

`playbooks/validate_cascade.yml` is read-only. It checks:

- SSH baseline connectivity and passwordless sudo.
- IPv4 forwarding on all cascade hosts.
- Expected WireGuard interfaces:
  - Primary Yandex: `wg-client`, `wg-transit`.
  - Secondary Yandex: `wg0`, `wg-transit`.
  - Racknerd: `wg-transit`, `wg-direct-exit`.
- `wg show interfaces`, per-interface `wg show`, and `systemctl is-active` for expected WireGuard services.
- Loaded nftables ruleset presence.
- Yandex policy routing:
  - `fwmark 0x2 lookup 200`.
  - table `200` default route through `wg-transit`.
  - marked route probe to `1.1.1.1` resolving through `wg-transit`.
- Yandex nftables split-routing assumptions:
  - `wg-client` and `wg-transit` references.
  - `ru4` set reference.
  - mark `0x2`.
  - masquerade rule.
  - counter expressions.
- Racknerd NAT assumptions:
  - route to `10.60.0.10` through `wg-transit`.
  - nftables references to `wg-transit`, `10.60.0.0/24`, masquerade, and counters.
- Racknerd direct-exit assumptions:
  - route to `10.80.0.10` through `wg-direct-exit`.
  - nftables references to `wg-direct-exit`, `10.80.0.0/24`, masquerade, and counters.

Run live validation after the deployment playbooks have completed:

```sh
ansible-playbook -i inventory/hosts.yml playbooks/verify.yml
ansible-playbook -i inventory/hosts.yml playbooks/validate_cascade.yml
```

Recommended live run order:

1. Confirm inventory renders with `ansible-inventory -i inventory/hosts.yml --list`.
2. Confirm baseline host access with `playbooks/verify.yml`.
3. Run `playbooks/validate_cascade.yml`.
4. Connect a test WireGuard client.
5. Generate RU and non-RU test traffic from the client.
6. Re-run `playbooks/validate_cascade.yml` and compare nftables counter state on all VPN hosts.
7. For fail-closed testing, stop only Racknerd transit in a planned maintenance window and confirm non-RU traffic fails while RU traffic still exits through Yandex.

## Rollback Playbook

`playbooks/rollback_cascade.yml` is intentionally guarded. By default it refuses to run because `confirm_rollback` defaults to `false`.

The rollback scaffold can:

- Stop and disable `wg-quick@wg-client` on Yandex.
- Stop and disable `wg-quick@wg-transit` on Yandex.
- Remove Yandex table `200` default route through `wg-transit`.
- Remove Yandex `fwmark 0x2 table 200` policy rule.
- Flush Yandex route cache.
- Stop and disable `wg-quick@wg-transit` on Racknerd.
- Stop and disable `wg-quick@wg-direct-exit` on Racknerd if rolling back the secondary Yandex direct path.

Safe dry preflight:

```sh
ansible-playbook -i inventory/hosts.yml playbooks/rollback_cascade.yml --syntax-check
ansible-playbook -i inventory/hosts.yml playbooks/rollback_cascade.yml --check
```

Expected default behavior:

- The syntax check should pass.
- The check-mode run without extra variables should fail at the guard task before any rollback task can run.

To run rollback after confirming scope and SSH access:

```sh
ansible-playbook -i inventory/hosts.yml playbooks/rollback_cascade.yml -e confirm_rollback=true
```

Scoped rollback examples:

```sh
ansible-playbook -i inventory/hosts.yml playbooks/rollback_cascade.yml -e confirm_rollback=true --limit yandex_cloud --tags wireguard
ansible-playbook -i inventory/hosts.yml playbooks/rollback_cascade.yml -e confirm_rollback=true --limit yandex_cloud --tags policy_routing
ansible-playbook -i inventory/hosts.yml playbooks/rollback_cascade.yml -e confirm_rollback=true --limit external_vps --tags wireguard
```

Do not run rollback during normal validation. Keep rollback for planned recovery only, after confirming another access path or the current SSH control path is stable.
