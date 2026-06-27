# Agent Orchestration Plan

## Objective

Implement the cascade VPN described in `cascade-vpn-architecture.md` using small, reviewable Ansible roles and clear agent ownership.

The target state:

- User connects to Yandex Cloud over WireGuard.
- Yandex routes RU destinations directly through Yandex.
- Yandex routes non-RU destinations through an encrypted WireGuard tunnel to Racknerd.
- Racknerd exits non-RU traffic to the Internet.
- Non-RU traffic fails closed if the Yandex-to-Racknerd tunnel is unavailable.

## Testing Discipline

Every agent must test aggressively at each step before handing work to the next agent.

Required behavior:

- Add or update automated checks together with each role, template, script, or routing change.
- Run the narrowest relevant check immediately after each change.
- Run the broader integration checks before declaring the step complete.
- Capture the exact commands used for validation in the final agent report.
- Treat warnings in Ansible, shell scripts, systemd units, nftables, and WireGuard configs as work items unless they are explicitly documented as harmless.
- Stop the handoff if any required check fails.
- Prefer idempotence tests: run the same Ansible playbook twice and confirm the second run is clean or only reports intentional changes.
- For remote networking changes, validate the current SSH control path before and after the change.
- For firewall, route, and WireGuard changes, include a rollback command or playbook before applying the change.
- For split-routing changes, test both positive and negative cases:
  - RU destination exits via Yandex.
  - Non-RU destination exits via Racknerd.
  - Non-RU traffic does not fall back to Yandex when Racknerd transit is down.

Minimum checks by layer:

- Repository layer: `ansible-inventory --list`, YAML syntax checks, linter checks where available.
- Ansible layer: `ansible-playbook --syntax-check`, `ansible-playbook --check` where safe, then live run.
- Host layer: package state, sysctl state, service state, `systemctl is-active`, and idempotent rerun.
- WireGuard layer: `wg show`, interface addresses, latest handshakes, and transfer counters.
- Routing layer: `ip rule show`, `ip route show table 200`, `ip route get` for RU and non-RU targets.
- nftables layer: `nft -c -f <ruleset>`, `nft list ruleset`, and rule counters for both route classes.
- End-to-end layer: client handshake, DNS behavior, RU egress IP, non-RU egress IP, and fail-closed transit outage test.

## Agent 1: Inventory And Baseline

Purpose:

- Keep host inventory and host variables accurate.
- Ensure all VPN hosts are reachable with their configured SSH users.
- Ensure passwordless sudo works.

Inputs:

- `inventory/hosts.yml`
- `inventory/group_vars/all.yml`
- `host_vars/yc_ubuntu_2404_min.yml`
- `host_vars/yandex_wg_direct.yml`
- `host_vars/racknerd_ubuntu.yml`

Tasks:

- Maintain host metadata.
- Run `ansible all -m ping`.
- Run `ansible-playbook playbooks/verify.yml`.
- Refuse to continue if any host is unreachable.

Deliverables:

- Passing baseline checks.
- Updated inventory if IPs or key paths change.

## Agent 2: Secret And Key Material

Purpose:

- Generate and manage WireGuard key material without committing secrets.

Tasks:

- Create local secret directory outside git, e.g. `~/.config/vpn-gen/wireguard/`.
- Generate:
  - Yandex `wg-client` private/public key.
  - Yandex `wg-transit` private/public key.
  - Racknerd `wg-transit` private/public key.
  - Initial user client private/public key.
- Create an Ansible vars file encrypted with Ansible Vault or reference local key files.

Deliverables:

- Secret paths documented.
- Public keys available to Ansible templates.
- Private keys excluded from git.

Acceptance checks:

- `git status` must not show private key files.
- Generated public keys match private keys using `wg pubkey`.

## Agent 3: Common Linux Network Base Role

Purpose:

- Prepare both Ubuntu hosts for routing and WireGuard.

Role name:

- `roles/common_network_base`

Tasks:

- Install packages:
  - `wireguard`
  - `wireguard-tools`
  - `nftables`
  - `iproute2`
  - `curl`
  - `ca-certificates`
  - optional: `unbound`
- Enable IPv4 forwarding:
  - `net.ipv4.ip_forward=1`
- Ensure `nftables` is enabled and running.
- Keep SSH untouched except for confirming access.

Deliverables:

- Base packages installed.
- Sysctl persisted.
- No VPN interfaces configured yet.

Acceptance checks:

- `sysctl net.ipv4.ip_forward` returns `1`.
- `wg --version` works.
- `nft list ruleset` works.

## Agent 4: Racknerd Exit Role

Purpose:

- Configure Racknerd as encrypted transit peer and non-RU Internet exit.

Role name:

- `roles/racknerd_exit`

Tasks:

- Render `/etc/wireguard/wg-transit.conf`.
- Configure Racknerd transit address `10.70.0.2/30`.
- Add Yandex as peer:
  - `AllowedIPs = 10.70.0.1/32, 10.60.0.0/24`
- Enable `wg-quick@wg-transit`.
- Configure nftables:
  - Allow transit UDP port.
  - Allow forwarding from `wg-transit` to public interface.
  - Masquerade `10.60.0.0/24` on public interface.

Deliverables:

- Racknerd can receive Yandex transit packets.
- Racknerd exits client traffic to the Internet.

Acceptance checks:

- `wg show wg-transit`.
- `ip route get 10.60.0.10` uses `wg-transit`.
- NAT rule exists for `10.60.0.0/24`.

Rollback:

- Stop and disable `wg-quick@wg-transit`.
- Remove nftables role include.

## Agent 5: Yandex Edge Role

Purpose:

- Configure Yandex as WireGuard client endpoint and routing policy node.

Role name:

- `roles/yandex_edge`

Tasks:

- Render `/etc/wireguard/wg-client.conf`.
- Render `/etc/wireguard/wg-transit.conf`.
- Configure `wg-client` address `10.60.0.1/24`.
- Configure `wg-transit` address `10.70.0.1/30`.
- Set `Table = off` for `wg-transit`.
- Add Racknerd as transit peer:
- Endpoint: `172.245.154.109:51821`
  - `AllowedIPs = 0.0.0.0/0`
- Add policy routing:
  - `ip rule add fwmark 0x2 table 200`
  - `ip route add default dev wg-transit table 200`
- Configure nftables:
  - RU CIDR set.
  - Bypass set for private/local/control ranges.
  - Mark non-RU client packets with `0x2`.
  - Masquerade RU client traffic through Yandex public interface.
  - Do not masquerade traffic forwarded to Racknerd.
- Enable both WireGuard services.

Deliverables:

- User clients can connect to Yandex.
- Yandex can forward non-RU traffic to Racknerd.
- RU traffic exits from Yandex.

Acceptance checks:

- `wg show wg-client`.
- `wg show wg-transit`.
- `ip rule show` contains `fwmark 0x2 lookup 200`.
- `ip route show table 200` contains `default dev wg-transit`.
- nftables contains `ru4` and bypass sets.

Rollback:

- Stop `wg-quick@wg-client`.
- Stop `wg-quick@wg-transit`.
- Remove table `200` route and `fwmark` rule.
- Restore previous nftables ruleset.

## Agent 6: GeoIP Update Role

Purpose:

- Keep the Yandex RU CIDR set fresh.

Role name:

- `roles/geoip_ru_routes`

Tasks:

- Install update script on Yandex:
  - Download RU IPv4 CIDRs.
  - Validate CIDR format.
  - Write nftables include atomically.
  - Reload nftables.
- Add systemd service and timer.
- Keep last known good CIDR file.

Deliverables:

- Automated RU CIDR updates.
- Safe reload behavior.

Acceptance checks:

- Manual service run succeeds.
- Timer is enabled.
- nftables set contains RU intervals.

Rollback:

- Disable timer.
- Restore last known good nftables include.

## Agent 7: Client Configuration Role

Purpose:

- Generate initial user WireGuard client config.

Role name:

- `roles/wg_client_config`

Tasks:

- Create client config with:
  - Client address `10.60.0.10/32`.
  - DNS `10.60.0.1`.
- Endpoint `51.250.14.221:53774`.
  - `AllowedIPs = 0.0.0.0/0`.
- Add the client public key as peer on Yandex `wg-client`.
- Reload `wg-client` safely.

Deliverables:

- Initial `.conf` file for WireGuard client.
- Yandex peer installed.

Acceptance checks:

- Client handshake appears in `wg show wg-client`.
- Client can reach both RU and non-RU test endpoints.

## Agent 8: Validation And Observability

Purpose:

- Prove the route split and encrypted transit behavior.

Tasks:

- Run baseline Ansible checks.
- Check WireGuard handshakes.
- From a test client:
  - Query a RU IP echo endpoint and verify Yandex exit.
  - Query a non-RU IP echo endpoint and verify Racknerd exit.
- On Yandex:
  - Confirm marked packet counters increase for non-RU traffic.
  - Confirm direct NAT counters increase for RU traffic.
- On Racknerd:
  - Confirm NAT counters increase for non-RU traffic.
- Temporarily stop Racknerd transit and verify:
  - Non-RU traffic fails.
  - RU traffic still exits via Yandex.

Deliverables:

- Validation log.
- Known-good command list.
- Any routing exceptions discovered during testing.

## Recommended Execution Order

1. Agent 1: Inventory And Baseline
2. Agent 2: Secret And Key Material
3. Agent 3: Common Linux Network Base Role
4. Agent 4: Racknerd Exit Role
5. Agent 5: Yandex Edge Role
6. Agent 6: GeoIP Update Role
7. Agent 7: Client Configuration Role
8. Agent 8: Validation And Observability

## Implementation Milestones

### Milestone 1: Transit Tunnel

- Configure `wg-transit` only.
- Verify encrypted Yandex-to-Racknerd connectivity.
- No user traffic routed yet.

### Milestone 2: Client VPN

- Configure `wg-client`.
- Verify user can connect to Yandex.
- Route all client traffic through Yandex temporarily for smoke testing.

### Milestone 3: Policy Split

- Add RU CIDR nftables set.
- Add marking and policy table.
- Route non-RU traffic through Racknerd.
- Keep RU traffic on Yandex.

### Milestone 4: Hardening And Automation

- Add GeoIP timer.
- Add firewall tightening.
- Add validation playbooks.
- Add rollback playbooks.

## Guardrails For Agents

- Do not store private keys or passwords in git.
- Do not disable SSH access before proving another access path works.
- Do not replace the whole nftables ruleset without a saved rollback copy.
- Do not enable default route injection from WireGuard; use explicit policy routing.
- Do not allow non-RU traffic to fall back through Yandex when Racknerd is down.
- Prefer idempotent Ansible modules/templates over ad hoc shell commands.
