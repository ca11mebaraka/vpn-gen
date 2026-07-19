# MyVPN

Security-hardened WireGuard cascade with split routing, reproducible Ansible
deployment and an optional web control plane.

```text
client ── WireGuard ──> entry (RU destinations)
                         └── WireGuard transit ──> exit (other destinations)
```

## Highlights

- fail-closed nftables policy and transit routing;
- pinned SSH host keys and key-only deployment access;
- secrets and generated client profiles kept outside Git;
- per-device WireGuard clients with create, disable, rotate and revoke flows;
- React/TypeScript administration UI with Telegram allowlist authentication;
- server health, handshake, traffic and audit views;
- validation, rollback and static security checks.

Start with [`ansible/README.md`](ansible/README.md), [`SECURITY.md`](SECURITY.md)
and [`admin/README.md`](admin/README.md). Copy the provided `.env.example`
files and keep all real values in ignored local `.env` files or an external
secret store.

## Attribution

This project continues the work from
[`ca11mebaraka/vpn-gen`](https://github.com/ca11mebaraka/vpn-gen). The original
architecture and automation provided the foundation for the security hardening,
deployment workflow and control-plane work maintained in this fork.

## Security

Never commit private keys, client configurations, Telegram tokens, session
secrets, real inventories or secret backups. See [`SECURITY.md`](SECURITY.md)
before deploying or contributing.
