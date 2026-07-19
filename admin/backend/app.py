from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import audit, vpn_service
from .auth import COOKIE_NAME, issue_session, require_admin, verify_telegram
from .config import settings

app = FastAPI(title="MyVPN Admin", docs_url=None, redoc_url=None)


class TelegramPayload(BaseModel):
    id: int
    first_name: str = ""
    last_name: str = ""
    username: str = ""
    photo_url: str = ""
    auth_date: int
    hash: str


class CreateDevice(BaseModel):
    owner: str = Field(min_length=2, max_length=24)
    device: str = Field(min_length=2, max_length=24)
    device_type: str = Field(pattern="^(iphone|android|mac|windows|linux|tablet|other)$")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/myvpn-telegram-relay", response_class=HTMLResponse)
def telegram_relay() -> HTMLResponse:
    # Telegram trusts the configured authentication hostname. This
    # fixed-origin relay forwards only the signed payload to the MyVPN opener;
    # MyVPN still performs the authoritative HMAC and admin-ID verification.
    html = """<!doctype html><html><head><meta charset=\"utf-8\"><meta name=\"referrer\" content=\"no-referrer\"><title>MyVPN Telegram Login</title></head><body><script>
    (() => {
      const match = (location.hash || '').match(/[#?&]tgAuthResult=([A-Za-z0-9\\-_=]*)$/);
      if (!match) { document.body.textContent = 'Telegram authentication result is missing.'; return; }
      try {
        let data = match[1].replace(/-/g, '+').replace(/_/g, '/');
        data += '='.repeat((4 - data.length % 4) % 4);
        const payload = JSON.parse(atob(data));
        if (window.opener) {
          window.opener.postMessage({type: 'myvpn:telegram-auth', payload}, __MYVPN_ORIGIN__);
          window.close();
        } else {
          window.location.replace(__MYVPN_ORIGIN__ + '/#tgAuthResult=' + encodeURIComponent(match[1]));
        }
      } catch (_) { document.body.textContent = 'Invalid Telegram authentication result.'; }
    })();
    </script></body></html>"""
    return HTMLResponse(
        html.replace("__MYVPN_ORIGIN__", json.dumps(settings.public_origin)),
        headers={"Cache-Control": "no-store", "X-Frame-Options": "DENY"},
    )


@app.on_event("startup")
def startup() -> None:
    settings.validate()
    audit.connect().close()


@app.get("/api/auth/config")
def auth_config() -> dict[str, str]:
    bot_id = settings.bot_token.split(":", 1)[0]
    if not bot_id.isdigit():
        raise HTTPException(status_code=500, detail="Invalid Telegram bot token")
    return {"bot_id": bot_id, "auth_bridge_origin": settings.auth_bridge_origin}


@app.post("/api/auth/telegram")
def login(payload: TelegramPayload, response: Response) -> dict[str, Any]:
    user = verify_telegram(payload.model_dump())
    response.set_cookie(COOKIE_NAME, issue_session(user), max_age=43200, httponly=True, secure=settings.cookie_secure, samesite="strict", path="/")
    audit.record(user["id"], "auth.login", str(user["id"]))
    return {"user": user}


@app.post("/api/logout")
def logout(response: Response, user: dict = Depends(require_admin)) -> dict[str, str]:
    response.delete_cookie(COOKIE_NAME, path="/")
    audit.record(user["id"], "auth.logout", str(user["id"]))
    return {"status": "ok"}


@app.get("/api/me")
def me(user: dict = Depends(require_admin)) -> dict[str, Any]:
    return user


@app.get("/api/status")
def status(_: dict = Depends(require_admin)) -> dict[str, Any]:
    return {"servers": vpn_service.system_status(), "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()}


@app.get("/api/clients")
def clients(_: dict = Depends(require_admin)) -> dict[str, Any]:
    return {"clients": vpn_service.clients()}


@app.post("/api/clients")
def create_client(payload: CreateDevice, user: dict = Depends(require_admin)) -> dict[str, str]:
    try:
        result = vpn_service.create_client(payload.owner, payload.device, payload.device_type)
    except vpn_service.ServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    audit.record(user["id"], "client.create", result["name"], {"owner": payload.owner, "type": payload.device_type})
    return result


@app.post("/api/clients/{name}/{action}")
def act(name: str, action: str, user: dict = Depends(require_admin)) -> dict[str, str]:
    try:
        result = vpn_service.client_action(name, action)
    except vpn_service.ServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    audit.record(user["id"], f"client.{action}", name)
    return result


@app.delete("/api/clients/{name}")
def remove(name: str, user: dict = Depends(require_admin)) -> dict[str, str]:
    try:
        result = vpn_service.remove_client(name)
    except vpn_service.ServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    audit.record(user["id"], "client.remove", name)
    return result


@app.get("/api/audit")
def audit_log(_: dict = Depends(require_admin)) -> dict[str, Any]:
    return {"events": audit.recent()}


frontend = Path(__file__).resolve().parents[1] / "frontend" / "dist"
app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")


@app.get("/{path:path}")
def spa(path: str) -> FileResponse:
    candidate = frontend / path
    return FileResponse(candidate if path and candidate.is_file() else frontend / "index.html")
