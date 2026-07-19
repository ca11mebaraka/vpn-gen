#!/usr/bin/env bash
set -Eeuo pipefail

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"

fail=0
reject() {
  local pattern=$1 message=$2
  if rg -n -g '!security-static-check.sh' "$pattern" ansible/roles ansible/scripts ansible/playbooks; then
    printf 'SECURITY ERROR: %s\n' "$message" >&2
    fail=1
  fi
}

reject 'flush ruleset' 'roles must not erase the host ruleset'
reject 'hook (input|forward).*policy accept;' 'base input/forward chains must be default-deny'
reject 'StrictHostKeyChecking=accept-new|StrictHostKeyChecking=no' 'SSH host identity must be pre-pinned'
reject 'VPN_GEN_DEPLOYMENT.*, *"yandex-racknerd"' 'reference deployment must not be the default'

for handler in ansible/roles/{entry_split,entry_full,exit}/handlers/main.yml; do
  rg -q 'on-active=2m' "$handler" || {
    printf 'SECURITY ERROR: firewall rollback watchdog missing in %s\n' "$handler" >&2
    fail=1
  }
  rg -q 'Confirm SSH survived firewall reload' "$handler" || {
    printf 'SECURITY ERROR: post-firewall SSH verification missing in %s\n' "$handler" >&2
    fail=1
  }
done

for template in \
  ansible/roles/entry_split/templates/entry_split.nft.j2 \
  ansible/roles/entry_full/templates/nftables.conf.j2 \
  ansible/roles/exit/templates/exit_split.nft.j2; do
  rg -q 'policy drop;' "$template" || {
    printf 'SECURITY ERROR: no default drop policy in %s\n' "$template" >&2
    fail=1
  }
done

./ansible/scripts/check-no-private-key-material.sh || fail=1
(( fail == 0 )) || exit 1
printf 'Security static checks passed.\n'
