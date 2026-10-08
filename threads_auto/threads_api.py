"""Threads API（graph.threads.net）ラッパー。

公式手順: コンテナ作成 POST /{user-id}/threads → 公開 POST /{user-id}/threads_publish
インサイト: GET /{media-id}/insights?metric=views,likes,replies,reposts,quotes,shares
"""

from __future__ import annotations

import time
from typing import Callable

from .http import Transport, request_json, urllib_transport

GRAPH_ROOT = "https://graph.threads.net"
API_VERSION = "v1.0"
POST_METRICS = ("views", "likes", "replies", "reposts", "quotes", "shares")
MAX_TEXT_LENGTH = 500


class ThreadsClient:
    def __init__(
        self,
        access_token: str,
        user_id: str = "me",
        transport: Transport = urllib_transport,
        sleep: Callable[[float], None] = time.sleep,
        publish_wait_seconds: float = 3.0,
    ):
        self.token = access_token
        self.user_id = user_id or "me"
        self.transport = transport
        self.sleep = sleep
        self.publish_wait_seconds = publish_wait_seconds

    def _call(self, method: str, path: str, params: dict | None = None, versioned: bool = True) -> dict:
        base = f"{GRAPH_ROOT}/{API_VERSION}" if versioned else GRAPH_ROOT
        params = dict(params or {}, access_token=self.token)
        return request_json(self.transport, method, f"{base}/{path.lstrip('/')}", params, sleep=self.sleep)

    # --- 投稿 -------------------------------------------------------------
    def create_text_container(self, text: str, reply_to_id: str | None = None) -> str:
        res = self._call(
            "POST",
            f"{self.user_id}/threads",
            {"media_type": "TEXT", "text": text, "reply_to_id": reply_to_id},
        )
        return res["id"]

    def create_image_container(self, image_url: str, text: str = "", reply_to_id: str | None = None) -> str:
        """画像1枚の投稿コンテナ。image_url は誰でも取得できる https の URL であること。"""
        res = self._call(
            "POST",
            f"{self.user_id}/threads",
            {"media_type": "IMAGE", "image_url": image_url, "text": text, "reply_to_id": reply_to_id},
        )
        return res["id"]

    def wait_until_ready(self, creation_id: str, attempts: int = 10, interval: float = 3.0) -> None:
        """画像はサーバー側の取り込みに時間がかかるので、status が FINISHED になるまで待つ。"""
        for _ in range(attempts):
            res = self._call("GET", creation_id, {"fields": "status,error_message"})
            status = res.get("status")
            if status == "FINISHED":
                return
            if status in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"画像の取り込みに失敗しました: {res.get('error_message') or status}")
            self.sleep(interval)
        raise RuntimeError("画像の取り込みが時間内に終わりませんでした")

    def post_image(self, image_url: str, text: str = "", reply_to_id: str | None = None) -> str:
        """画像コンテナ作成→取り込み完了待ち→公開。公開された投稿の media id を返す。"""
        creation_id = self.create_image_container(image_url, text, reply_to_id=reply_to_id)
        self.wait_until_ready(creation_id)
        return self.publish_container(creation_id)

    def post_carousel(self, image_urls: list[str], text: str = "") -> str:
        """複数画像（2〜20枚）の投稿。各画像を子コンテナにし、まとめのコンテナを公開する。"""
        children = []
        for url in image_urls:
            res = self._call("POST", f"{self.user_id}/threads", {"media_type": "IMAGE", "image_url": url, "is_carousel_item": "true"})
            self.wait_until_ready(res["id"])
            children.append(res["id"])
        res = self._call("POST", f"{self.user_id}/threads", {"media_type": "CAROUSEL", "children": ",".join(children), "text": text})
        self.wait_until_ready(res["id"])
        return self.publish_container(res["id"])

    def publish_container(self, creation_id: str) -> str:
        res = self._call("POST", f"{self.user_id}/threads_publish", {"creation_id": creation_id})
        return res["id"]

    def post_text(self, text: str, reply_to_id: str | None = None) -> str:
        """コンテナ作成→待機→公開。公開された投稿の media id を返す。"""
        creation_id = self.create_text_container(text, reply_to_id=reply_to_id)
        if self.publish_wait_seconds:
            self.sleep(self.publish_wait_seconds)
        return self.publish_container(creation_id)

    # --- 取得 -------------------------------------------------------------
    def me(self) -> dict:
        return self._call("GET", "me", {"fields": "id,username"})

    def get_post(self, media_id: str, fields: str = "id,permalink,timestamp,text") -> dict:
        return self._call("GET", media_id, {"fields": fields})

    def recent_posts(self, limit: int = 25) -> list[dict]:
        res = self._call("GET", f"{self.user_id}/threads", {"fields": "id,text,timestamp,permalink", "limit": limit})
        return res.get("data", [])

    def insights(self, media_id: str, metrics: tuple[str, ...] = POST_METRICS) -> dict[str, int]:
        res = self._call("GET", f"{media_id}/insights", {"metric": ",".join(metrics)})
        return parse_insights(res)

    def account_insights(self, metrics: tuple[str, ...] = ("followers_count",)) -> dict[str, int]:
        """アカウント全体の指標（フォロワー数など）。threads_manage_insights が必要。"""
        res = self._call("GET", f"{self.user_id}/threads_insights", {"metric": ",".join(metrics)})
        return parse_insights(res)

    # --- トークン ---------------------------------------------------------
    def refresh_long_lived_token(self) -> dict:
        """長期トークン（60日）を延長。発行から24時間以上経過し、期限内であること。"""
        return self._call("GET", "refresh_access_token", {"grant_type": "th_refresh_token"}, versioned=False)


def parse_insights(res: dict) -> dict[str, int]:
    out: dict[str, int] = {}
    for item in res.get("data", []):
        name = item.get("name")
        if "total_value" in item:
            out[name] = int(item["total_value"].get("value", 0))
        elif item.get("values"):
            out[name] = int(item["values"][-1].get("value", 0))
    return out
