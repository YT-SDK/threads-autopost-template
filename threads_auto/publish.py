"""ステップ5: 予約時刻を過ぎた承認済み投稿を公開する（GitHub Actions から毎時実行）。

二重投稿対策:
  - 公開前に直近の自分の投稿と本文を照合し、同一なら「公開済み」として記録だけ行う
    （前回実行で公開後のコミットに失敗したケースを救済）
  - workflow 側で concurrency を1にして同時実行を防ぐ
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from .config import Settings
from .http import APIError
from .store import Store, parse_time
from .threads_api import ThreadsClient
from .validate import normalize, validate_queue


def is_publishable(item: dict, settings: Settings) -> bool:
    if item.get("status", "queued") != "queued":
        return False
    review = item.get("review") or {}
    if review.get("status") != "approved":
        return False
    if settings["require_human_approval"] and not review.get("human_approved"):
        return False
    return True


def last_published_at(store: Store) -> datetime | None:
    times = [parse_time(p["published_at"]) for _, p in store.posted() if p.get("published_at")]
    return max(times) if times else None


def publish_due(client: ThreadsClient | Callable[[], ThreadsClient] | None, store: Store, settings: Settings, now: datetime, dry_run: bool = False) -> list[str]:
    log: list[str] = []
    validation = validate_queue(store)
    expire = timedelta(hours=settings["expire_hours"])

    due = []
    for path, item in store.queue():
        if not is_publishable(item, settings):
            continue
        scheduled = parse_time(item["scheduled_at"])
        if scheduled > now:
            continue
        if now - scheduled > expire:
            item["status"] = "expired"
            store.save(path, item)
            log.append(f"EXPIRED {path.name}: 予定 {item['scheduled_at']} から {settings['expire_hours']}h 超過")
            continue
        errors, _ = validation.get(path.name, ([], []))
        if errors:
            log.append(f"SKIP {path.name}: " + " / ".join(errors))
            continue
        due.append((scheduled, path, item))
    due.sort(key=lambda t: t[0])

    last = last_published_at(store)
    min_gap = timedelta(minutes=settings["min_interval_minutes"])
    if last and due and now - last < min_gap:
        log.append(f"WAIT 直前の投稿から {settings['min_interval_minutes']} 分経過していません")
        return log

    if due and callable(client) and not dry_run:
        client = client()  # 公開対象があるときだけトークンを要求する
    recent_texts: dict[str, dict] = {}
    if due and client and not dry_run:
        recent_texts = {normalize(p.get("text", "")): p for p in client.recent_posts(limit=25)}

    for _, path, item in due[: settings["max_posts_per_run"]]:
        if dry_run or client is None:
            log.append(f"DRY-RUN {path.name}: {item['text'][:40]}…")
            continue
        try:
            # 本文・返信ごとに進捗を保存し、途中で失敗しても公開済みの部分は二度と投稿しない
            media_id = item.get("media_id")
            existing = recent_texts.get(normalize(item["text"]))
            recovered = False
            if not media_id and existing:
                # 本文の記録がないのに公開済み＝別の実行がすでに公開した可能性が高い。
                # 返信もその実行が付けているはずなので、二重投稿を避けて返信は付けない（2026-10-08 返信の二重投稿）
                media_id = existing["id"]
                recovered = True
                log.append(f"RECOVERED {path.name}: 本文は公開済み（{media_id}）。返信は二重投稿を避けるため付けない（要確認）")
            if not media_id:
                if len(item.get("image_urls") or []) >= 2:
                    media_id = client.post_carousel(item["image_urls"], item["text"])
                elif item.get("image_url"):
                    media_id = client.post_image(item["image_url"], item["text"])
                else:
                    media_id = client.post_text(item["text"])
            item["media_id"] = media_id
            store.save(path, item)
            reply_ids = list(item.get("reply_media_ids", []))
            parent = reply_ids[-1] if reply_ids else media_id
            pending = [] if recovered else item.get("replies", [])[len(reply_ids):]
            if recovered and item.get("replies") and not reply_ids:
                item["replies_unverified"] = True
            for reply in pending:
                parent = client.post_text(reply, reply_to_id=parent)
                reply_ids.append(parent)
                item["reply_media_ids"] = reply_ids
                store.save(path, item)
            info = client.get_post(media_id, fields="id,permalink,timestamp")
        except (APIError, RuntimeError) as e:
            item["attempts"] = item.get("attempts", 0) + 1
            item["last_error"] = str(e)
            if item["attempts"] >= settings["max_attempts"]:
                item["status"] = "failed"
            store.save(path, item)
            log.append(f"ERROR {path.name}: {e}")
            continue

        item.update(
            status="posted",
            media_id=media_id,
            reply_media_ids=reply_ids,
            permalink=info.get("permalink"),
            published_at=info.get("timestamp") or now.isoformat(),
        )
        item.pop("last_error", None)
        store.move_to_posted(path, item)
        log.append(f"POSTED {path.name}: {item.get('permalink')}")
    if not due:
        log.append("公開対象なし")
    return log


def next_free_slots(store: Store, settings: Settings, now: datetime, count: int) -> list[datetime]:
    """posting_slots（土日は posting_slots_weekend があればそちら）のうち、空いている直近の枠を返す。"""
    tz = settings.tz
    taken = set()
    for _, item in store.queue() + store.posted():
        try:
            taken.add(parse_time(item["scheduled_at"]).astimezone(tz).replace(second=0, microsecond=0))
        except (KeyError, ValueError):
            pass
    slots: list[datetime] = []
    local_now = now.astimezone(tz)
    day = local_now.date()
    while len(slots) < count:
        weekend = day.weekday() >= 5 and settings.get("posting_slots_weekend")
        for hm in weekend or settings["posting_slots"]:
            h, m = map(int, hm.split(":"))
            dt = datetime(day.year, day.month, day.day, h, m, tzinfo=tz)
            if dt > local_now + timedelta(minutes=10) and dt not in taken:
                slots.append(dt)
                if len(slots) == count:
                    break
        day += timedelta(days=1)
    return slots
