#!/usr/bin/env python3
"""Manage WireGuard clients for cascade VPN entry nodes.

The script runs on the Mac/controller. It keeps client private keys and a small
registry outside the repository, then syncs peers to the remote WireGuard
servers over SSH.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any


STATE_DIR = Path(os.environ.get("VPN_GEN_CLIENT_ADMIN_DIR", "~/.config/vpn-gen/wg-client-admin")).expanduser()
REGISTRY_PATH = STATE_DIR / "clients.json"
EXPORT_DIR = Path(os.environ.get("VPN_GEN_CLIENT_EXPORT_DIR", "~/Downloads")).expanduser()
KNOWN_HOSTS = Path(os.environ.get("VPN_GEN_SSH_KNOWN_HOSTS", "~/.config/vpn-gen/ssh/known_hosts")).expanduser()

class CommandError(RuntimeError):
    pass


PROFILE_ALIASES = {
    "primary": "split",
    "direct": "full",
}


def default_profiles_path() -> Path:
    env_path = os.environ.get("VPN_GEN_WG_CLIENT_PROFILES")
    if env_path:
        return Path(env_path).expanduser()
    deployment = os.environ.get("VPN_GEN_DEPLOYMENT", "my-vpn")
    script_dir = Path(__file__).resolve().parent
    json_path = script_dir.parent / "deployments" / deployment / "client-profiles.json"
    if json_path.exists():
        return json_path
    return script_dir.parent / "deployments" / deployment / "client-profiles.yml"


def load_profiles() -> dict[str, dict[str, Any]]:
    path = default_profiles_path()
    if not path.exists():
        raise CommandError(
            f"client profiles file not found: {path}. "
            "Copy deployments/reference/client-profiles.json into your deployment "
            "or set VPN_GEN_WG_CLIENT_PROFILES."
        )

    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        data = json.loads(text)
    else:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise CommandError(
                f"YAML profiles require PyYAML, or use JSON: {path.with_suffix('.json')}"
            ) from exc
        data = yaml.safe_load(text)

    profiles = data.get("profiles") if isinstance(data, dict) else None
    if not isinstance(profiles, dict) or not profiles:
        raise CommandError(f"profiles file must contain a non-empty 'profiles' map: {path}")
    return profiles


PROFILES: dict[str, dict[str, Any]] = load_profiles()


def profile_choices() -> list[str]:
    return sorted(set(PROFILES) | set(PROFILE_ALIASES))


MANAGED_BEGIN = "# wg-client-admin: begin"
MANAGED_END = "# wg-client-admin: end"


@dataclass(frozen=True)
class Profile:
    name: str
    description: str
    ssh_user: str
    ssh_host: str
    ssh_key: Path
    interface: str
    server_public_key: str
    endpoint_host: str
    endpoint_port: int
    network: ipaddress.IPv4Network
    default_dns: str
    default_mtu: int

    @classmethod
    def from_name(cls, name: str) -> "Profile":
        resolved = PROFILE_ALIASES.get(name, name)
        if resolved not in PROFILES:
            raise CommandError(f"unknown profile: {name}")
        raw = PROFILES[resolved]
        return cls(
            name=resolved,
            description=raw["description"],
            ssh_user=raw["ssh_user"],
            ssh_host=raw["ssh_host"],
            ssh_key=Path(raw["ssh_key"]).expanduser(),
            interface=raw["interface"],
            server_public_key=raw["server_public_key"],
            endpoint_host=raw["endpoint_host"],
            endpoint_port=int(raw["endpoint_port"]),
            network=ipaddress.ip_network(raw["network"]),
            default_dns=raw["default_dns"],
            default_mtu=int(raw["default_mtu"]),
        )

    @property
    def endpoint(self) -> str:
        return f"{self.endpoint_host}:{self.endpoint_port}"


def run(cmd: list[str], *, input_text: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and proc.returncode != 0:
        raise CommandError(
            f"command failed ({proc.returncode}): {shlex.join(cmd)}\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return proc


def ssh(profile: Profile, remote_command: str, *, input_text: str | None = None, check: bool = True) -> str:
    cmd = [
        "ssh",
        "-i",
        str(profile.ssh_key),
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        f"UserKnownHostsFile={KNOWN_HOSTS}",
        f"{profile.ssh_user}@{profile.ssh_host}",
        remote_command,
    ]
    return run(cmd, input_text=input_text, check=check).stdout


def require_tools(*names: str) -> None:
    missing = [name for name in names if run(["/usr/bin/env", "bash", "-lc", f"command -v {shlex.quote(name)}"], check=False).returncode != 0]
    if missing:
        raise CommandError(f"missing required tool(s): {', '.join(missing)}")


def load_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.exists():
        return {"version": 1, "clients": {}}
    return json.loads(REGISTRY_PATH.read_text())


def save_registry(registry: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.chmod(0o700)
    tmp = REGISTRY_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    tmp.chmod(0o600)
    tmp.replace(REGISTRY_PATH)


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-")
    if not slug:
        raise CommandError("client name must contain at least one safe character")
    return slug


def registry_key(profile: str, name: str) -> str:
    return f"{profile}:{slugify(name)}"


def client_dir(profile_name: str, client_name: str) -> Path:
    return STATE_DIR / profile_name / slugify(client_name)


def genkey() -> tuple[str, str]:
    require_tools("wg")
    private_key = run(["wg", "genkey"]).stdout.strip()
    public_key = run(["wg", "pubkey"], input_text=private_key + "\n").stdout.strip()
    return private_key, public_key


def default_allowed_ips(profile: Profile) -> str:
    endpoint = ipaddress.ip_network(f"{profile.endpoint_host}/32")
    ipv4 = [str(net) for net in ipaddress.ip_network("0.0.0.0/0").address_exclude(endpoint)]
    return ",".join([*ipv4, "::/0"])


def allocate_ip(profile: Profile, registry: dict[str, Any]) -> str:
    used = {profile.network.network_address, profile.network.broadcast_address}
    # Server address is normally .1.
    used.add(next(profile.network.hosts()))
    for client in registry["clients"].values():
        if client.get("profile") == profile.name:
            used.add(ipaddress.ip_interface(client["address"]).ip)
    for host in profile.network.hosts():
        if host not in used:
            return f"{host}/32"
    raise CommandError(f"no free client addresses in {profile.network}")


def write_key_files(profile_name: str, name: str, private_key: str, public_key: str) -> dict[str, str]:
    directory = client_dir(profile_name, name)
    directory.mkdir(parents=True, exist_ok=True)
    directory.chmod(0o700)
    private_path = directory / "client.private.key"
    public_path = directory / "client.public.key"
    private_path.write_text(private_key + "\n")
    private_path.chmod(0o600)
    public_path.write_text(public_key + "\n")
    public_path.chmod(0o644)
    return {"private_key_path": str(private_path), "public_key_path": str(public_path)}


def read_private_key(client: dict[str, Any]) -> str:
    return Path(client["private_key_path"]).expanduser().read_text().strip()


def render_config(client: dict[str, Any]) -> str:
    private_key = read_private_key(client)
    lines = [
        "[Interface]",
        f"PrivateKey = {private_key}",
        f"Address = {client['address']}",
        f"DNS = {client['dns']}",
    ]
    if client.get("mtu"):
        lines.append(f"MTU = {client['mtu']}")
    lines += [
        "",
        "[Peer]",
        f"PublicKey = {client['server_public_key']}",
        f"Endpoint = {client['endpoint']}",
        f"AllowedIPs = {client['allowed_ips']}",
        f"PersistentKeepalive = {client['persistent_keepalive']}",
        "",
    ]
    return "\n".join(lines)


def remote_apply_peer(profile: Profile, client: dict[str, Any], enabled: bool) -> None:
    allowed_ips = client["address"]
    remote_script = f"""#!/usr/bin/env bash
set -Eeuo pipefail

interface={shlex.quote(profile.interface)}
name={shlex.quote(client["name"])}
public_key={shlex.quote(client["public_key"])}
allowed_ips={shlex.quote(allowed_ips)}
enabled={shlex.quote("1" if enabled else "0")}

conf="/etc/wireguard/${{interface}}.conf"
begin="# wg-client-admin: begin ${{name}}"
end="# wg-client-admin: end ${{name}}"
tmp="$(mktemp)"

awk -v begin="$begin" -v end="$end" '
  $0 == begin {{ skip=1; next }}
  skip && $0 == end {{ skip=0; next }}
  !skip {{ print }}
' "$conf" > "$tmp"
install -m 600 -o root -g root "$tmp" "$conf"
rm -f "$tmp"

if [[ "$enabled" == "1" ]]; then
  {{
    printf '%s\\n' "$begin"
    printf '[Peer]\\n'
    printf 'PublicKey = %s\\n' "$public_key"
    printf 'AllowedIPs = %s\\n' "$allowed_ips"
    printf '%s\\n' "$end"
  }} >> "$conf"
  wg set "$interface" peer "$public_key" allowed-ips "$allowed_ips"
else
  wg set "$interface" peer "$public_key" remove 2>/dev/null || true
fi
"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        local_script = Path(tmp_dir) / "wg-client-admin-remote.sh"
        local_script.write_text(remote_script)
        local_script.chmod(0o700)

        remote_script_path = f"/tmp/wg-client-admin-{os.getpid()}-{client['name']}.sh"
        scp_cmd = [
            "scp",
            "-i",
            str(profile.ssh_key),
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            f"UserKnownHostsFile={KNOWN_HOSTS}",
            str(local_script),
            f"{profile.ssh_user}@{profile.ssh_host}:{remote_script_path}",
        ]
        run(scp_cmd)
        remote_cmd = (
            f"sudo -n bash {shlex.quote(remote_script_path)}; "
            f"status=$?; rm -f {shlex.quote(remote_script_path)}; exit $status"
        )
        ssh(profile, remote_cmd)


def remote_list(profile: Profile) -> str:
    return ssh(profile, f"sudo wg show {shlex.quote(profile.interface)}")


def command_profiles(_: argparse.Namespace) -> None:
    for name, raw in PROFILES.items():
        print(f"{name}: {raw['description']} ({raw['endpoint_host']}:{raw['endpoint_port']}, {raw['network']})")


def command_add(args: argparse.Namespace) -> None:
    require_tools("wg")
    profile = Profile.from_name(args.profile)
    registry = load_registry()
    name = slugify(args.name)
    key = registry_key(profile.name, name)
    if key in registry["clients"]:
        raise CommandError(f"client already exists: {key}")
    private_key, public_key = genkey()
    address = args.address or allocate_ip(profile, registry)
    ipaddress.ip_interface(address)
    paths = write_key_files(profile.name, name, private_key, public_key)
    client = {
        "name": name,
        "profile": profile.name,
        "enabled": True,
        "address": address,
        "dns": args.dns or profile.default_dns,
        "mtu": args.mtu if args.mtu is not None else profile.default_mtu,
        "allowed_ips": args.allowed_ips or default_allowed_ips(profile),
        "endpoint": profile.endpoint,
        "server_public_key": profile.server_public_key,
        "public_key": public_key,
        "private_key_path": paths["private_key_path"],
        "public_key_path": paths["public_key_path"],
        "persistent_keepalive": args.persistent_keepalive,
    }
    try:
        remote_apply_peer(profile, client, enabled=True)
    except CommandError:
        shutil.rmtree(client_dir(profile.name, name), ignore_errors=True)
        raise
    registry["clients"][key] = client
    save_registry(registry)
    config_path = export_client(client, args.output)
    print(f"added {key}")
    print(f"config: {config_path}")


def command_edit(args: argparse.Namespace) -> None:
    registry = load_registry()
    key = registry_key(args.profile, args.name)
    client = registry["clients"].get(key)
    if not client:
        raise CommandError(f"client not found: {key}")
    profile = Profile.from_name(client["profile"])
    if args.address:
        ipaddress.ip_interface(args.address)
        client["address"] = args.address
    if args.dns:
        client["dns"] = args.dns
    if args.mtu is not None:
        client["mtu"] = args.mtu
    if args.allowed_ips:
        client["allowed_ips"] = args.allowed_ips
    if args.endpoint:
        client["endpoint"] = args.endpoint
    remote_apply_peer(profile, client, enabled=bool(client["enabled"]))
    save_registry(registry)
    print(f"edited {key}")


def command_set_enabled(args: argparse.Namespace, enabled: bool) -> None:
    registry = load_registry()
    key = registry_key(args.profile, args.name)
    client = registry["clients"].get(key)
    if not client:
        raise CommandError(f"client not found: {key}")
    profile = Profile.from_name(client["profile"])
    client["enabled"] = enabled
    remote_apply_peer(profile, client, enabled=enabled)
    save_registry(registry)
    print(("enabled" if enabled else "disabled") + f" {key}")


def command_remove(args: argparse.Namespace) -> None:
    registry = load_registry()
    key = registry_key(args.profile, args.name)
    client = registry["clients"].get(key)
    if not client:
        raise CommandError(f"client not found: {key}")
    if not args.confirm:
        raise CommandError("removal requires --confirm")
    profile = Profile.from_name(client["profile"])
    remote_apply_peer(profile, client, enabled=False)
    shutil.rmtree(client_dir(profile.name, client["name"]), ignore_errors=False)
    del registry["clients"][key]
    save_registry(registry)
    print(f"removed {key}; previously exported configs and encrypted backups must be destroyed separately")


def command_rotate(args: argparse.Namespace) -> None:
    registry = load_registry()
    key = registry_key(args.profile, args.name)
    client = registry["clients"].get(key)
    if not client:
        raise CommandError(f"client not found: {key}")
    profile = Profile.from_name(client["profile"])
    old_client = copy.deepcopy(client)
    old_private_key = read_private_key(old_client)
    old_public_key = old_client["public_key"]
    private_key, public_key = genkey()

    remote_apply_peer(profile, old_client, enabled=False)
    paths = write_key_files(profile.name, client["name"], private_key, public_key)
    client["private_key_path"] = paths["private_key_path"]
    client["public_key_path"] = paths["public_key_path"]
    client["public_key"] = public_key
    try:
        remote_apply_peer(profile, client, enabled=bool(client["enabled"]))
    except CommandError:
        write_key_files(profile.name, client["name"], old_private_key, old_public_key)
        try:
            remote_apply_peer(profile, old_client, enabled=bool(old_client["enabled"]))
        except CommandError:
            pass
        raise
    registry["clients"][key] = client
    save_registry(registry)
    config_path = export_client(client, args.output)
    print(f"rotated {key}")
    print(f"new config: {config_path}")


def command_list(args: argparse.Namespace) -> None:
    registry = load_registry()
    print("Managed clients:")
    for key, client in sorted(registry["clients"].items()):
        if args.profile and client["profile"] != args.profile:
            continue
        status = "enabled" if client.get("enabled") else "disabled"
        print(f"- {key} {client['address']} {status} pub={client['public_key']}")
    if args.remote:
        profiles = [args.profile] if args.profile else sorted(PROFILES)
        for profile_name in profiles:
            profile = Profile.from_name(profile_name)
            print(f"\nRemote {profile_name} ({profile.interface}):")
            print(remote_list(profile).rstrip())


def export_client(client: dict[str, Any], output: str | None = None) -> Path:
    if output:
        path = Path(output).expanduser()
    else:
        path = EXPORT_DIR / f"wg-{client['profile']}-{client['name']}.conf"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_config(client))
    path.chmod(0o600)
    return path


def command_export(args: argparse.Namespace) -> None:
    registry = load_registry()
    key = registry_key(args.profile, args.name)
    client = registry["clients"].get(key)
    if not client:
        raise CommandError(f"client not found: {key}")
    path = export_client(client, args.output)
    print(path)


def command_qr(args: argparse.Namespace) -> None:
    require_tools("qrencode")
    registry = load_registry()
    key = registry_key(args.profile, args.name)
    client = registry["clients"].get(key)
    if not client:
        raise CommandError(f"client not found: {key}")
    config_text = render_config(client)
    if args.output:
        path = Path(args.output).expanduser()
    else:
        path = EXPORT_DIR / f"wg-{client['profile']}-{client['name']}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    run(["qrencode", "-o", str(path), "-t", "png"], input_text=config_text)
    print(path)


def command_show_config(args: argparse.Namespace) -> None:
    registry = load_registry()
    key = registry_key(args.profile, args.name)
    client = registry["clients"].get(key)
    if not client:
        raise CommandError(f"client not found: {key}")
    print(render_config(client), end="")


def command_sync(args: argparse.Namespace) -> None:
    registry = load_registry()
    count = 0
    for key, client in sorted(registry["clients"].items()):
        if args.profile and client["profile"] != args.profile:
            continue
        profile = Profile.from_name(client["profile"])
        remote_apply_peer(profile, client, enabled=bool(client["enabled"]))
        count += 1
    print(f"synced {count} clients")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage vpn-gen WireGuard clients from macOS.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("profiles", help="List managed server profiles").set_defaults(func=command_profiles)

    list_p = sub.add_parser("list", help="List managed clients")
    list_p.add_argument("--profile", choices=profile_choices())
    list_p.add_argument("--remote", action="store_true", help="Also show remote wg state")
    list_p.set_defaults(func=command_list)

    add_p = sub.add_parser("add", help="Add a new client and sync it to the server")
    add_p.add_argument("name")
    add_p.add_argument("--profile", choices=profile_choices(), default="split")
    add_p.add_argument("--address", help="Client address, e.g. 10.60.0.20/32")
    add_p.add_argument("--dns")
    add_p.add_argument("--mtu", type=int)
    add_p.add_argument("--allowed-ips")
    add_p.add_argument("--persistent-keepalive", type=int, default=25)
    add_p.add_argument("--output", help="Where to write the client config")
    add_p.set_defaults(func=command_add)

    edit_p = sub.add_parser("edit", help="Edit client metadata and resync")
    edit_p.add_argument("name")
    edit_p.add_argument("--profile", choices=profile_choices(), default="split")
    edit_p.add_argument("--address")
    edit_p.add_argument("--dns")
    edit_p.add_argument("--mtu", type=int)
    edit_p.add_argument("--allowed-ips")
    edit_p.add_argument("--endpoint")
    edit_p.set_defaults(func=command_edit)

    disable_p = sub.add_parser("disable", help="Disable a client on the remote server")
    disable_p.add_argument("name")
    disable_p.add_argument("--profile", choices=profile_choices(), default="split")
    disable_p.set_defaults(func=lambda args: command_set_enabled(args, False))

    enable_p = sub.add_parser("enable", help="Re-enable a managed client")
    enable_p.add_argument("name")
    enable_p.add_argument("--profile", choices=profile_choices(), default="split")
    enable_p.set_defaults(func=lambda args: command_set_enabled(args, True))

    remove_p = sub.add_parser("remove", help="Revoke and permanently remove a managed client")
    remove_p.add_argument("name")
    remove_p.add_argument("--profile", choices=profile_choices(), default="split")
    remove_p.add_argument("--confirm", action="store_true")
    remove_p.set_defaults(func=command_remove)

    rotate_p = sub.add_parser("rotate", help="Replace a client's WireGuard key pair")
    rotate_p.add_argument("name")
    rotate_p.add_argument("--profile", choices=profile_choices(), default="split")
    rotate_p.add_argument("--output")
    rotate_p.set_defaults(func=command_rotate)

    export_p = sub.add_parser("export", help="Write client config")
    export_p.add_argument("name")
    export_p.add_argument("--profile", choices=profile_choices(), default="split")
    export_p.add_argument("--output")
    export_p.set_defaults(func=command_export)

    qr_p = sub.add_parser("qr", help="Generate a QR PNG for a client")
    qr_p.add_argument("name")
    qr_p.add_argument("--profile", choices=profile_choices(), default="split")
    qr_p.add_argument("--output")
    qr_p.set_defaults(func=command_qr)

    show_p = sub.add_parser("show-config", help="Print client config to stdout")
    show_p.add_argument("name")
    show_p.add_argument("--profile", choices=profile_choices(), default="split")
    show_p.set_defaults(func=command_show_config)

    sync_p = sub.add_parser("sync", help="Resync managed clients to remote servers")
    sync_p.add_argument("--profile", choices=profile_choices())
    sync_p.set_defaults(func=command_sync)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except CommandError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
