"""アクセストークン取得（OAuth 認可コード → 短期トークン → 長期トークン）。

公式手順:
  1. https://threads.com/oauth/authorize?client_id=...&redirect_uri=...&scope=...&response_type=code
  2. POST https://graph.threads.net/oauth/access_token（code → 短期トークン, 有効1時間）
  3. GET  https://graph.threads.net/access_token?grant_type=th_exchange_token（→ 長期トークン, 有効60日）
"""

from __future__ import annotations

import urllib.parse

from .http import Transport, request_json, urllib_transport
from .threads_api import GRAPH_ROOT

AUTHORIZE_URL = "https://threads.com/oauth/authorize"
DEFAULT_SCOPES = ("threads_basic", "threads_content_publish", "threads_manage_replies", "threads_manage_insights")


def authorize_url(app_id: str, redirect_uri: str, scopes=DEFAULT_SCOPES, state: str | None = None) -> str:
    params = {"client_id": app_id, "redirect_uri": redirect_uri, "scope": ",".join(scopes), "response_type": "code"}
    if state:
        params["state"] = state
    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def extract_code(value: str) -> str:
    """リダイレクト先URL全体・コード単体のどちらでも受け付け、末尾の #_ を除去する。"""
    value = value.strip()
    if "?" in value or value.startswith("http"):
        params = urllib.parse.parse_qs(value.split("?", 1)[-1].split("#", 1)[0])
        if "error" in params:
            reason = (params.get("error_description") or params["error"])[0]
            raise ValueError(f"認可が完了していません: {reason}（「許可」を押したか確認してください）")
        codes = params.get("code")
        if not codes:
            raise ValueError("URL に code パラメータが見つかりません")
        value = codes[0]
    value = value.split("#", 1)[0].strip()
    if not value:
        raise ValueError("認可コードが空です")
    return value


def exchange_code(app_id: str, app_secret: str, code: str, redirect_uri: str, transport: Transport = urllib_transport) -> dict:
    """認可コード → 短期トークン。戻り値: {"access_token", "user_id"}"""
    return request_json(
        transport,
        "POST",
        f"{GRAPH_ROOT}/oauth/access_token",
        {"client_id": app_id, "client_secret": app_secret, "code": code, "grant_type": "authorization_code", "redirect_uri": redirect_uri},
        retries=0,
    )


def exchange_long_lived(app_secret: str, short_token: str, transport: Transport = urllib_transport) -> dict:
    """短期トークン → 長期トークン。戻り値: {"access_token", "token_type", "expires_in"}"""
    return request_json(
        transport,
        "GET",
        f"{GRAPH_ROOT}/access_token",
        {"grant_type": "th_exchange_token", "client_secret": app_secret, "access_token": short_token},
        retries=0,
    )
