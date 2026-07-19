from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from .config import settings


def connect() -> sqlite3.Connection:
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(settings.db_path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        admin_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        target TEXT NOT NULL,
        details TEXT NOT NULL
    )""")
    return db


def record(admin_id: int, action: str, target: str, details: dict[str, Any] | None = None) -> None:
    with connect() as db:
        db.execute(
            "INSERT INTO audit_log(created_at,admin_id,action,target,details) VALUES(?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), admin_id, action, target, json.dumps(details or {}, ensure_ascii=False)),
        )


def recent(limit: int = 100) -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (min(limit, 500),)).fetchall()
    return [dict(row) | {"details": json.loads(row["details"])} for row in rows]
