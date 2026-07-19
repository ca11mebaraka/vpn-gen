from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _csv_ints(value: str) -> frozenset[int]:
    return frozenset(int(item.strip()) for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    bot_token: str = os.getenv("MYVPN_ADMIN_TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", "")
    admin_ids: frozenset[int] = _csv_ints(os.getenv("MYVPN_ADMIN_TELEGRAM_IDS", ""))
    session_secret: str = os.getenv("MYVPN_ADMIN_SESSION_SECRET") or os.getenv("JWT_SECRET", "")
    cookie_secure: bool = os.getenv("MYVPN_ADMIN_COOKIE_SECURE", "true").lower() == "true"
    db_path: Path = Path(os.getenv("MYVPN_ADMIN_DB", "/app/data/admin.db"))
    repo_root: Path = Path(os.getenv("MYVPN_REPO_ROOT", "/workspace"))
    ansible_dir: Path = Path(os.getenv("MYVPN_ANSIBLE_DIR", "/workspace/ansible"))
    client_admin_dir: Path = Path(os.getenv("MYVPN_CLIENT_ADMIN_DIR", "/secrets/config/wg-client-admin"))
    client_export_dir: Path = Path(os.getenv("MYVPN_CLIENT_EXPORT_DIR", "/secrets/client-exports"))
    known_hosts: Path = Path(os.getenv("MYVPN_SSH_KNOWN_HOSTS", "/secrets/ssh/known_hosts"))
    controller_name: str = os.getenv("MYVPN_CONTROLLER_NAME", "controller")
    deployment: str = os.getenv("MYVPN_DEPLOYMENT", "reference")
    entry_host: str = os.getenv("MYVPN_ENTRY_HOST", "")
    exit_host: str = os.getenv("MYVPN_EXIT_HOST", "")
    public_origin: str = os.getenv("MYVPN_ADMIN_PUBLIC_ORIGIN", "")
    auth_bridge_origin: str = os.getenv("MYVPN_AUTH_BRIDGE_ORIGIN", "")
    initial_owner: str = os.getenv("MYVPN_INITIAL_OWNER", "Initial owner")

    def validate(self) -> None:
        if len(self.session_secret) < 32:
            raise RuntimeError("MYVPN_ADMIN_SESSION_SECRET must contain at least 32 characters")
        if not self.bot_token:
            raise RuntimeError("MYVPN_ADMIN_TELEGRAM_BOT_TOKEN is required")
        if not self.admin_ids:
            raise RuntimeError("MYVPN_ADMIN_TELEGRAM_IDS must not be empty")
        if not self.entry_host or not self.exit_host:
            raise RuntimeError("MYVPN_ENTRY_HOST and MYVPN_EXIT_HOST are required")
        if not self.public_origin.startswith("https://") or not self.auth_bridge_origin.startswith("https://"):
            raise RuntimeError("MYVPN_ADMIN_PUBLIC_ORIGIN and MYVPN_AUTH_BRIDGE_ORIGIN must use HTTPS")


settings = Settings()
