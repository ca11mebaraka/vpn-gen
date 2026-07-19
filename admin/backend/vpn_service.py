from __future__ import annotations

import base64
import ipaddress
import json
import os
import re
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from .config import settings

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,47}$")
ACTIONS = {"enable", "disable", "rotate"}


class ServiceError(RuntimeError):
    pass


def _run(args: list[str], *, timeout: int = 30, input_text: str | None = None) -> str:
    try:
        result = subprocess.run(
            args, cwd=settings.ansible_dir, input=input_text, text=True,
            capture_output=True, timeout=timeout, check=False, env=_environment(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ServiceError(str(exc)) from exc
    if result.returncode:
        message = (result.stderr or result.stdout or "command failed").strip()
        raise ServiceError(message[-1200:])
    return result.stdout


def _environment() -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        "VPN_GEN_DEPLOYMENT": settings.deployment,
        "VPN_GEN_CLIENT_ADMIN_DIR": str(settings.client_admin_dir),
        "VPN_GEN_CLIENT_EXPORT_DIR": str(settings.client_export_dir),
        "VPN_GEN_SSH_KNOWN_HOSTS": str(settings.known_hosts),
    })
    return env


def _name(value: str) -> str:
    value = value.strip().lower()
    if not NAME_RE.fullmatch(value):
        raise ServiceError("Use 2-48 lowercase Latin letters, digits or hyphens")
    return value


def _manager(*args: str, timeout: int = 30) -> str:
    return _run([str(settings.ansible_dir / "scripts/wg-client"), *args], timeout=timeout)


def registry() -> dict[str, Any]:
    path = settings.client_admin_dir / "clients.json"
    if not path.exists():
        return {"clients": {}}
    return json.loads(path.read_text())


def remote_dump() -> list[dict[str, Any]]:
    profile = json.loads((settings.ansible_dir / "deployments" / settings.deployment / "client-profiles.json").read_text())["profiles"]["split"]
    cmd = [
        "ssh", "-i", profile["ssh_key"], "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
        "-o", f"UserKnownHostsFile={settings.known_hosts}", f"{profile['ssh_user']}@{profile['ssh_host']}",
        "sudo", "wg", "show", profile["interface"], "dump",
    ]
    lines = _run(cmd).splitlines()[1:]
    peers = []
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 8:
            continue
        peers.append({
            "public_key": parts[0], "endpoint": None if parts[2] == "(none)" else parts[2],
            "address": parts[3], "latest_handshake": int(parts[4]),
            "received_bytes": int(parts[5]), "sent_bytes": int(parts[6]),
        })
    return peers


def clients() -> list[dict[str, Any]]:
    managed = registry().get("clients", {})
    by_key = {item.get("public_key"): (key, item) for key, item in managed.items()}
    result = []
    for peer in remote_dump():
        match = by_key.get(peer["public_key"])
        key, item = match if match else ("initial:mac", {})
        name = item.get("name", "initial-mac")
        result.append(peer | {
            "registry_key": key, "name": name, "owner": item.get("owner", settings.initial_owner),
            "device_type": item.get("device_type", "mac" if not match else "other"),
            "enabled": item.get("enabled", True), "managed": bool(match),
        })
    return sorted(result, key=lambda row: (row["owner"], row["name"]))


def create_client(owner: str, device: str, device_type: str) -> dict[str, str]:
    owner_slug = _name(owner)
    device_slug = _name(device)
    client_name = _name(f"{owner_slug}-{device_slug}")
    output = settings.client_export_dir / f"wg-split-{client_name}.conf"
    _manager("add", client_name, "--profile", "split", "--output", str(output), timeout=45)
    data = registry()
    key = f"split:{client_name}"
    data["clients"][key]["owner"] = owner_slug
    data["clients"][key]["device_type"] = device_type
    path = settings.client_admin_dir / "clients.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    path.chmod(0o600)
    config = output.read_text()
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
        qr_path = Path(handle.name)
    try:
        _run(["qrencode", "-o", str(qr_path), "-t", "png"], input_text=config)
        qr = base64.b64encode(qr_path.read_bytes()).decode()
    finally:
        qr_path.unlink(missing_ok=True)
    return {"name": client_name, "config": config, "qr": f"data:image/png;base64,{qr}"}


def client_action(name: str, action: str) -> dict[str, str]:
    name = _name(name)
    if action not in ACTIONS:
        raise ServiceError("Unsupported action")
    output = _manager(action, name, "--profile", "split", timeout=45)
    response = {"status": "ok", "message": output.strip()}
    if action == "rotate":
        config_path = settings.client_export_dir / f"wg-split-{name}.conf"
        if config_path.exists():
            response["config"] = config_path.read_text()
    return response


def remove_client(name: str) -> dict[str, str]:
    name = _name(name)
    return {"status": "ok", "message": _manager("remove", name, "--profile", "split", "--confirm", timeout=45).strip()}


def _ssh_status(host: str, role: str) -> dict[str, Any]:
    profile = json.loads((settings.ansible_dir / "deployments" / settings.deployment / "client-profiles.json").read_text())["profiles"]["split"]
    command = "uptime -p; systemctl is-active nftables; systemctl --failed --no-legend | wc -l; df -P / | tail -1 | tr -s ' ' | cut -d' ' -f5; free -m | awk 'NR==2{print int($3*100/$2)}'"
    started = time.monotonic()
    out = _run(["ssh", "-i", profile["ssh_key"], "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", f"UserKnownHostsFile={settings.known_hosts}", f"deploy@{host}", command], timeout=12)
    lines = out.strip().splitlines()
    if len(lines) != 5:
        raise ServiceError("Unexpected server status response")
    uptime, firewall, failed, disk, memory = lines
    return {"name": role, "host": host, "online": True, "uptime": uptime, "firewall": firewall, "failed_units": int(failed), "disk": disk, "memory": int(memory), "latency_ms": round((time.monotonic()-started)*1000)}


def system_status() -> list[dict[str, Any]]:
    load = os.getloadavg()[0]
    controller = {"name": settings.controller_name, "host": socket.gethostname(), "online": True, "uptime": "local", "firewall": "host", "failed_units": 0, "disk": "—", "memory": 0, "load": round(load, 2)}
    result = [controller]
    for host, role in ((settings.entry_host, "Россия · Entry"), (settings.exit_host, "Европа · Exit")):
        try:
            result.append(_ssh_status(host, role))
        except ServiceError as exc:
            result.append({"name": role, "host": host, "online": False, "error": str(exc)})
    return result
