from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import HTTPException, Request, status

from .config import settings

COOKIE_NAME = "myvpn_admin_session"
SESSION_TTL = 12 * 60 * 60
TELEGRAM_TTL = 10 * 60


def verify_telegram(payload: dict[str, Any]) -> dict[str, Any]:
    supplied_hash = str(payload.get("hash", ""))
    fields = {key: str(value) for key, value in payload.items() if key != "hash" and value is not None}
    check = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret = hashlib.sha256(settings.bot_token.encode()).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not supplied_hash or not hmac.compare_digest(expected, supplied_hash):
        raise HTTPException(status_code=403, detail="Invalid Telegram signature")
    auth_date = int(fields.get("auth_date", "0"))
    if abs(int(time.time()) - auth_date) > TELEGRAM_TTL:
        raise HTTPException(status_code=403, detail="Expired Telegram authentication")
    telegram_id = int(fields.get("id", "0"))
    if telegram_id not in settings.admin_ids:
        raise HTTPException(status_code=403, detail="Administrator access required")
    return {"id": telegram_id, "username": fields.get("username", ""), "name": fields.get("first_name", "Admin")}


def issue_session(user: dict[str, Any]) -> str:
    body = {"id": user["id"], "username": user.get("username", ""), "exp": int(time.time()) + SESSION_TTL}
    encoded = base64.urlsafe_b64encode(json.dumps(body, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(settings.session_secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def read_session(token: str) -> dict[str, Any]:
    try:
        encoded, signature = token.rsplit(".", 1)
        expected = hmac.new(settings.session_secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise ValueError
        padding = "=" * (-len(encoded) % 4)
        body = json.loads(base64.urlsafe_b64decode(encoded + padding))
        if int(body["exp"]) < int(time.time()) or int(body["id"]) not in settings.admin_ids:
            raise ValueError
        return body
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session") from exc


def require_admin(request: Request) -> dict[str, Any]:
    token = request.cookies.get(COOKIE_NAME, "")
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    return read_session(token)
