# Ansible Inventory

This directory contains the Ansible configuration for the two prepared Ubuntu hosts.

## Hosts

- `yc_ubuntu_2404_min`
  - Public IP: `111.88.242.229`
  - Internal IP: `10.128.0.24`
  - User: `deploy`
  - SSH key: `~/.ssh/yc_vm_ed25519`
  - Sudo: passwordless

- `racknerd_ubuntu`
  - Public IP: `172.245.154.109`
  - User: `deploy`
  - SSH key: `~/.ssh/vps_172_245_154_109_ed25519`
  - Sudo: passwordless

## Commands

Run commands from this directory:

```sh
cd ansible
ansible all -m ping
ansible-playbook playbooks/verify.yml
```

Target one group:

```sh
ansible yandex_cloud -m ping
ansible external_vps -m ping
```

## Cascade VPN Design

- Architecture spec: `docs/cascade-vpn-architecture.md`
- Agent orchestration plan: `docs/agent-orchestration-plan.md`

## Notes

Private keys and passwords are not stored in this repository. The inventory only references local SSH key paths.
