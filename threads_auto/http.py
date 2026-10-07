"""標準ライブラリだけで動く最小のHTTPクライアント（テスト時は transport を差し替える）。"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable

# transport(method, url, body_bytes, headers) -> (status, parsed_json)
Transport = Callable[[str, str, bytes | None, dict], tuple[int, dict]]


def urllib_transport(method: str, url: str, body: bytes | None, headers: dict) -> tuple[int, dict]:
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8") or "{}"
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") or "{}"
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"error": {"message": raw}}
        return e.code, payload


class APIError(Exception):
    def __init__(self, status: int, payload: dict):
        err = payload.get("error", payload) if isinstance(payload, dict) else payload
        message = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        super().__init__(f"HTTP {status}: {message}")
        self.status = status
        self.payload = payload


def request_json(
    transport: Transport,
    method: str,
    url: str,
    params: dict | None = None,
    headers: dict | None = None,
    form: bool = True,
    retries: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """GETはクエリ、POSTはフォームで送る。429/5xx は指数バックオフで再試行。"""
    params = {k: v for k, v in (params or {}).items() if v is not None}
    headers = dict(headers or {})
    body = None
    if method == "GET":
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
    elif form:
        body = urllib.parse.urlencode(params).encode("utf-8")
        headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    else:
        body = json.dumps(params).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")

    for attempt in range(retries + 1):
        status, payload = transport(method, url, body, headers)
        if status < 400:
            return payload
        if (status == 429 or status >= 500) and attempt < retries:
            sleep(2 ** (attempt + 1))
            continue
        raise APIError(status, payload)
    raise AssertionError("unreachable")
