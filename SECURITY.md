# MyVPN security baseline

The `secure-main` branch is fail-closed by design:

- input and forwarding chains default to `drop`;
- SSH is limited to `VPN_GEN_ADMIN_IPV4_CIDRS`;
- transit WireGuard packets are limited to the peer VPS public IP;
- non-RU client traffic can leave entry only through `wg-transit`;
- roles never use `flush ruleset`;
- reference deployments and documentation IP ranges fail preflight;
- SSH host keys must be pinned before client administration;
- every firewall reload arms a two-minute automatic rollback and disarms it
  only after Ansible reconnects successfully;
- IPv6 is disabled on VPN nodes and client routes capture `::/0` to prevent a
  direct IPv6 bypass;
- secrets and generated client configurations remain outside Git.

Before every deployment run:

```sh
./ansible/scripts/security-static-check.sh
source ansible/scripts/load-env.sh
cd ansible
ansible-playbook playbooks/verify_env.yml
```

Never set `VPN_GEN_ALLOW_WORLD_SSH=true` on production hosts. A first rollout
must keep a provider console open and include an out-of-band rollback test.

For a fresh VPS, verify the ED25519 fingerprints displayed by the provider,
set them in `.env`, and run `scripts/pin-ssh-host-keys.sh` before bootstrap.
The bootstrap playbook requires `VPN_GEN_CONFIRM_BOOTSTRAP=yes` and disables
password and root SSH only after installing the controller public key for
`deploy`.

Use `scripts/backup-secrets.sh` with an offline `age` recipient before adding
production clients. `wg-client rotate` replaces a compromised client key;
`wg-client remove NAME --confirm` revokes and deletes a client from the live
server and controller registry.
