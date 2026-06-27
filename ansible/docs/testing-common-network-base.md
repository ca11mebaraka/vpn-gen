---
title: Testing common_network_base
---

# Testing common_network_base

This document records validation for the Agent 3 role:
`roles/common_network_base`.

The role prepares Ubuntu hosts for later WireGuard and routing roles. It does
not configure WireGuard interfaces, nftables rules, routes, or SSH settings.

## Local Validation

Run commands from the `ansible/` directory.

If Ansible cannot write to `~/.ansible/tmp` in a sandboxed environment, set
`ANSIBLE_LOCAL_TEMP` to a temporary directory under `ansible/` and remove it
afterward:

```shell
mkdir -p .ansible-tmp
ANSIBLE_LOCAL_TEMP="$PWD/.ansible-tmp" ansible-inventory --list
ANSIBLE_LOCAL_TEMP="$PWD/.ansible-tmp" ansible-playbook playbooks/common_network_base.yml --syntax-check
rmdir .ansible-tmp
```

Validation performed:

```shell
cd ansible && mkdir -p .ansible-tmp && ANSIBLE_LOCAL_TEMP="$PWD/.ansible-tmp" ansible-inventory --list
```

Result: passed. Inventory parsed both target hosts:

- `yc_ubuntu_2404_min`
- `racknerd_ubuntu`

```shell
cd ansible && mkdir -p .ansible-tmp && ANSIBLE_LOCAL_TEMP="$PWD/.ansible-tmp" ansible-playbook playbooks/common_network_base.yml --syntax-check
```

Result: passed.

```shell
cd ansible && mkdir -p .ansible-tmp && ANSIBLE_LOCAL_TEMP="$PWD/.ansible-tmp" ansible-lint --version
```

Result: not run because `ansible-lint` is not installed in the current
environment (`command not found: ansible-lint`).

## Check Mode

Check mode is safe for this role because it should not mutate hosts, but it
still requires SSH access to the live inventory hosts.

Validation attempted:

```shell
cd ansible && mkdir -p .ansible-tmp && ANSIBLE_LOCAL_TEMP="$PWD/.ansible-tmp" ansible-playbook playbooks/common_network_base.yml --check --diff
```

Result: failed before any role task ran. Both hosts were unreachable during
fact gathering:

- `yc_ubuntu_2404_min`: `Permission denied (publickey)`
- `racknerd_ubuntu`: `Permission denied (publickey,password)`

No live apply was run.

## Post-SSH Validation

After SSH key access is restored, rerun check mode before any live apply:

```shell
cd ansible
ansible-playbook playbooks/common_network_base.yml --check --diff
```

If check mode succeeds, apply the role and immediately run it a second time to
confirm idempotence:

```shell
cd ansible
ansible-playbook playbooks/common_network_base.yml --diff
ansible-playbook playbooks/common_network_base.yml --diff
```

Expected second run: no changes.

Host-level acceptance checks after live apply:

```shell
ansible all -m ansible.builtin.command -a "sysctl net.ipv4.ip_forward"
ansible all -m ansible.builtin.command -a "wg --version"
ansible all -m ansible.builtin.command -a "nft list ruleset"
ansible all -m ansible.builtin.systemd -a "name=nftables"
```

Expected results:

- `net.ipv4.ip_forward = 1`
- `wg --version` exits successfully
- `nft list ruleset` exits successfully
- `nftables` is enabled and running
