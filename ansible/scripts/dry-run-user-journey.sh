#!/usr/bin/env bash
# Simulates a new user walking through README scenarios (dry-run only).
#
# Usage:
#   ./scripts/dry-run-user-journey.sh                  # generic VPS providers (default)
#   ./scripts/dry-run-user-journey.sh --profile yandex-racknerd
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ansible_dir=$(cd -- "$script_dir/.." && pwd)
cd "$ansible_dir"

profile=generic
while (($#)); do
  case "$1" in
    --profile)
      profile=$2
      shift 2
      ;;
    --help|-h)
      sed -n '1,8p' "$0"
      exit 0
      ;;
    *)
      printf 'unknown argument: %s\n' "$1" >&2
      exit 2
      ;;
  esac
done

case "$profile" in
  generic)
    env_template=.env.example
    ;;
  yandex-racknerd)
    env_template=deployments/yandex-racknerd/.env.example
    ;;
  *)
    printf 'unknown profile: %s (use generic or yandex-racknerd)\n' "$profile" >&2
    exit 2
    ;;
esac

if [[ ! -f $env_template ]]; then
  printf 'missing env template: %s\n' "$env_template" >&2
  exit 1
fi

tmp_env=$(mktemp)
cp "$env_template" "$tmp_env"
set -a
# shellcheck disable=SC1090
source "$tmp_env"
set +a

PASS=0
FAIL=0
SKIP=0
EXPECT=0

pass() { PASS=$((PASS + 1)); printf '  OK   %s\n' "$1"; }
fail() { FAIL=$((FAIL + 1)); printf '  FAIL %s\n' "$1" >&2; }
skip() { SKIP=$((SKIP + 1)); printf '  SKIP %s\n' "$1"; }
expect() { EXPECT=$((EXPECT + 1)); printf '  EXPECTED %s\n' "$1"; }

run_section() {
  printf '\n=== [%s] %s ===\n' "$profile" "$1"
}

run_cmd() {
  local label=$1
  shift
  printf '+ %s\n' "$*"
  if "$@"; then
    pass "$label"
  else
    fail "$label"
  fi
}

run_section "Шаг 0. Инструменты на Mac"
if command -v ansible >/dev/null 2>&1; then
  pass "ansible установлен: $(ansible --version | head -1)"
else
  fail "ansible не установлен"
fi
if command -v wg >/dev/null 2>&1; then
  pass "wireguard-tools: $(wg --version 2>&1 | head -1)"
else
  skip "wg не установлен (нужен для реального wg-secrets-init)"
fi

run_section "Шаг 2.4 / env"
pass "профиль: $profile"
pass "шаблон env: $env_template"
for var in VPN_GEN_ENTRY_SPLIT_HOST VPN_GEN_EXIT_HOST VPN_GEN_DEPLOYMENT; do
  if [[ -n "${!var:-}" ]]; then
    pass "$var=${!var}"
  else
    fail "$var пуст"
  fi
done

if [[ $profile == generic ]]; then
  for user_var in VPN_GEN_ENTRY_SPLIT_SSH_USER VPN_GEN_ENTRY_FULL_SSH_USER VPN_GEN_EXIT_SSH_USER; do
    if [[ "${!user_var:-deploy}" == deploy ]]; then
      pass "$user_var=deploy (универсальный VPS)"
    else
      fail "$user_var=${!user_var} (ожидался deploy для generic)"
    fi
  done
fi

run_section "Шаг 3. Inventory + verify_env (без SSH)"
run_cmd "ansible-inventory --graph" \
  ansible-inventory -i inventory/hosts.yml --graph

run_cmd "verify_env.yml (локальная проверка .env и SSH-пользователей)" \
  ansible-playbook -i inventory/hosts.yml playbooks/verify_env.yml

run_cmd "ansible_user entry_split_01 из env" \
  bash -c '[[ "$(ansible entry_split_01 -i inventory/hosts.yml -m debug -a var=ansible_user -o 2>/dev/null | sed -n "s/.*\"ansible_user\": \"\\([^\"]*\\)\".*/\\1/p")" == "${VPN_GEN_ENTRY_SPLIT_SSH_USER}" ]]'

run_section "Этап 0. Подготовка на Mac (dry-run)"
run_cmd "wg-secrets-init --dry-run" "$script_dir/wg-secrets-init.sh" --dry-run
run_cmd "check-no-private-key-material" "$script_dir/check-no-private-key-material.sh"
run_cmd "validate-wireguard-workflow" "$script_dir/validate-wireguard-workflow.sh"

run_section "Этап 1. Проверка доступа"
skip "ansible all -m ping — живой SSH (после настройки серверов)"
if [[ $profile == generic ]]; then
  skip "verify.yml — живой SSH; для generic достаточно verify_env.yml"
else
  skip "verify.yml — см. прогон ниже для профиля $profile"
fi

if [[ $profile == yandex-racknerd ]]; then
  if ansible-playbook -i inventory/hosts.yml playbooks/verify.yml; then
    pass "verify.yml (yandex-racknerd, живые хосты, ansible_user per host)"
  else
    expect "verify.yml (SSH/sudo на одном из хостов — проверьте .env и доступ)"
  fi
fi

run_section "Этап 2. Плейбуки (--syntax-check)"
for pb in common_network_base exit entry_split entry_full verify verify_env validate_cascade rollback_cascade client_config; do
  run_cmd "playbooks/${pb}.yml --syntax-check" \
    ansible-playbook -i inventory/hosts.yml "playbooks/${pb}.yml" --syntax-check
done

if [[ $profile == yandex-racknerd ]]; then
  run_section "Этап 2b. yandex-racknerd (--check --diff, живые хосты)"
  for pb in common_network_base entry_split; do
    run_cmd "playbooks/${pb}.yml --check --diff" \
      ansible-playbook -i inventory/hosts.yml "playbooks/${pb}.yml" --check --diff
  done
  if [[ "${VPN_GEN_EXIT_ENTRY_FULL_ENABLED:-false}" == true ]]; then
    exit_full_key="${VPN_GEN_WG_ENTRY_FULL_SECRET_DIR:-$HOME/.config/vpn-gen/wireguard-entry-full}/exit_entry_full_wg.private.key"
    if [[ -f $exit_full_key ]]; then
      run_cmd "playbooks/exit.yml --check --diff" \
        ansible-playbook -i inventory/hosts.yml playbooks/exit.yml --check --diff
    else
      expect "playbooks/exit.yml (VPN_GEN_EXIT_ENTRY_FULL_ENABLED=true, но нет $exit_full_key)"
    fi
  else
    run_cmd "playbooks/exit.yml --check --diff" \
      ansible-playbook -i inventory/hosts.yml playbooks/exit.yml --check --diff
  fi
  entry_full_key="${VPN_GEN_WG_ENTRY_FULL_SECRET_DIR:-$HOME/.config/vpn-gen/wireguard-entry-full}/server.private.key"
  if [[ -f $entry_full_key ]]; then
    run_cmd "playbooks/entry_full.yml --check --diff" \
      ansible-playbook -i inventory/hosts.yml playbooks/entry_full.yml --check --diff
  else
    skip "playbooks/entry_full.yml (нет wireguard-entry-full ключей)"
  fi
else
  skip "playbooks --check --diff на живых хостах (generic: IP из TEST-NET, серверов нет)"
fi

run_section "Этап 4. wg-client (локально)"
export VPN_GEN_DEPLOYMENT
if [[ $profile == generic ]]; then
  export VPN_GEN_WG_CLIENT_PROFILES="$ansible_dir/deployments/reference/client-profiles.json"
fi
run_cmd "wg-client profiles" "$script_dir/wg-client" profiles
run_cmd "wg-client list" "$script_dir/wg-client" list

run_section "Итог"
rm -f "$tmp_env"
printf 'OK: %s  FAIL: %s  EXPECTED: %s  SKIP: %s\n' "$PASS" "$FAIL" "$EXPECT" "$SKIP"
[[ "$FAIL" -eq 0 ]]
