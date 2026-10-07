"""コマンドライン入口: python -m threads_auto <command>"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import analytics, auth, publish
from .config import env_flag, load_settings, require_env
from .discord_ingest import ingest_channel
from .store import Store, write_json
from .threads_api import ThreadsClient
from .validate import validate_queue


def make_client() -> ThreadsClient:
    return ThreadsClient(require_env("THREADS_ACCESS_TOKEN"), os.environ.get("THREADS_USER_ID", "me"))


def cmd_validate(store, settings, args) -> int:
    results = validate_queue(store)
    failed = 0
    for name, (errors, warnings) in results.items():
        mark = "NG" if errors else "OK"
        print(f"[{mark}] {name}")
        for e in errors:
            print(f"   ERROR: {e}")
        for w in warnings:
            print(f"   WARN : {w}")
        failed += bool(errors)
    print(f"\n{len(results)} 件中 {failed} 件にエラー")
    return 1 if failed else 0


def cmd_publish_due(store, settings, args) -> int:
    dry = args.dry_run or env_flag("DRY_RUN")
    client = None if dry else make_client
    for line in publish.publish_due(client, store, settings, datetime.now(timezone.utc), dry_run=dry):
        print(line)
    return 0


def cmd_approve(store, settings, args) -> int:
    count = 0
    for path, item in store.queue():
        if args.all or path.stem in args.ids or path.name in args.ids:
            review = item.setdefault("review", {})
            if review.get("status") != "approved":
                print(f"SKIP {path.name}: AIレビューが approved ではありません（{review.get('status', 'pending')}）")
                continue
            review["human_approved"] = True
            store.save(path, item)
            count += 1
            print(f"APPROVED {path.name}")
    print(f"{count} 件を承認しました")
    return 0


def cmd_status(store, settings, args) -> int:
    counts: dict[str, int] = {}
    for path, item in store.queue():
        review = item.get("review") or {}
        state = item.get("status", "queued")
        if state == "queued":
            state = f"queued/{review.get('status', 'pending')}" + ("+human" if review.get("human_approved") else "")
        counts[state] = counts.get(state, 0) + 1
        print(f"{item.get('scheduled_at', '?'):<27} {state:<28} {path.name}")
    print(f"\nキュー: {counts or 'なし'} / 公開済み: {len(store.posted())} 件")
    return 0


def cmd_next_slots(store, settings, args) -> int:
    for dt in publish.next_free_slots(store, settings, datetime.now(timezone.utc), args.count):
        print(dt.isoformat())
    return 0


def cmd_fetch_insights(store, settings, args) -> int:
    if not any(item.get("media_id") for _, item in store.posted()):
        print("公開済みの投稿がないためスキップ")
        return 0
    for line in analytics.fetch_insights(make_client(), store, settings, datetime.now(timezone.utc)):
        print(line)
    return 0


def cmd_update_weights(store, settings, args) -> int:
    w = analytics.update_weights(store, settings, datetime.now(timezone.utc))
    print(f"評価対象 {w['sample_size']} 本。レポート: {w['report_path']}")
    return 0


def cmd_ingest_discord(store, settings, args) -> int:
    token = require_env("DISCORD_BOT_TOKEN")
    channels = [c.strip() for c in require_env("DISCORD_CHANNEL_IDS").split(",") if c.strip()]
    for ch in channels:
        print(f"channel {ch}: {ingest_channel(store, token, ch)} 件追加")
    return 0


def cmd_whoami(store, settings, args) -> int:
    print(make_client().me())
    return 0


def cmd_refresh_token(store, settings, args) -> int:
    """長期トークンを延長し、新トークンを --output に書き出す（標準出力には出さない）。"""
    res = make_client().refresh_long_lived_token()
    days = int(res.get("expires_in", 0)) // 86400
    write_json(Path(args.output), {"access_token": res["access_token"], "expires_in": res.get("expires_in")})
    print(f"トークンを延長しました（有効期限 約 {days} 日）。出力先: {args.output}")
    return 0


def cmd_auth_url(store, settings, args) -> int:
    app_id = args.app_id or require_env("THREADS_APP_ID")
    redirect = args.redirect_uri or os.environ.get("THREADS_REDIRECT_URI") or "https://localhost/"
    print("次のURLをブラウザで開き、Threads アカウントで「許可」してください:\n")
    print(auth.authorize_url(app_id, redirect))
    print(f"\n許可後に表示される {redirect}?code=... のURL全体をコピーし、1時間以内に get-token --code に渡してください。")
    return 0


def cmd_get_token(store, settings, args) -> int:
    """認可コード（または短期トークン）→ 長期トークン。トークン本体は --output にのみ書き、画面には出さない。"""
    secret = require_env("THREADS_APP_SECRET")
    if args.short_token:
        short, user_id = args.short_token.strip(), None
    elif args.code:
        app_id = require_env("THREADS_APP_ID")
        redirect = args.redirect_uri or os.environ.get("THREADS_REDIRECT_URI") or "https://localhost/"
        res = auth.exchange_code(app_id, secret, auth.extract_code(args.code), redirect)
        short, user_id = res["access_token"], res.get("user_id")
        print("1/3 認可コード → 短期トークン: OK")
    else:
        raise SystemExit("--code か --short-token のどちらかを指定してください")

    long_lived = auth.exchange_long_lived(secret, short)
    token = long_lived["access_token"]
    expires_in = int(long_lived.get("expires_in", 0))
    print("2/3 短期トークン → 長期トークン: OK")

    me = ThreadsClient(token).me()
    user_id = str(user_id or me.get("id"))
    print(f"3/3 疎通確認: OK（@{me.get('username')} / user_id={user_id}）")

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    write_json(Path(args.output), {"access_token": token, "user_id": user_id, "expires_at": expires_at.isoformat()})
    print(f"\n有効期限: {expires_at.astimezone(settings.tz):%Y-%m-%d %H:%M}（約 {expires_in // 86400} 日）")
    print(f"保存先: {args.output}（.gitignore 済み。GitHub Secret に登録したら削除してください）")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="threads_auto", description="Threads 運用自動化 CLI")
    p.add_argument("--data-dir", default=None, help="データディレクトリ（既定: data）")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("validate", help="予約キューを機械チェック").set_defaults(fn=cmd_validate)
    sp = sub.add_parser("publish-due", help="予定時刻を過ぎた承認済み投稿を公開")
    sp.add_argument("--dry-run", action="store_true")
    sp.set_defaults(fn=cmd_publish_due)
    sp = sub.add_parser("approve", help="AIレビュー合格済みの投稿を人が最終承認")
    sp.add_argument("ids", nargs="*")
    sp.add_argument("--all", action="store_true")
    sp.set_defaults(fn=cmd_approve)
    sub.add_parser("status", help="キューの状態を表示").set_defaults(fn=cmd_status)
    sp = sub.add_parser("next-slots", help="空いている投稿枠を表示")
    sp.add_argument("--count", type=int, default=7)
    sp.set_defaults(fn=cmd_next_slots)
    sub.add_parser("fetch-insights", help="公開済み投稿の表示回数などを取得").set_defaults(fn=cmd_fetch_insights)
    sub.add_parser("update-weights", help="フォーマット順位・ネタ重み・週次レポートを更新").set_defaults(fn=cmd_update_weights)
    sub.add_parser("ingest-discord", help="Discord のメモをナレッジに取り込む").set_defaults(fn=cmd_ingest_discord)
    sub.add_parser("whoami", help="トークンの疎通確認").set_defaults(fn=cmd_whoami)
    sp = sub.add_parser("refresh-token", help="長期アクセストークンを延長")
    sp.add_argument("--output", default="new_token.json")
    sp.set_defaults(fn=cmd_refresh_token)
    sp = sub.add_parser("auth-url", help="トークン取得: 認可URLを表示")
    sp.add_argument("--app-id")
    sp.add_argument("--redirect-uri")
    sp.set_defaults(fn=cmd_auth_url)
    sp = sub.add_parser("get-token", help="トークン取得: 認可コード→長期トークン")
    sp.add_argument("--code", help="リダイレクト先URL全体、またはコード")
    sp.add_argument("--short-token", help="管理画面で発行した短期トークン（コードの代わり）")
    sp.add_argument("--redirect-uri")
    sp.add_argument("--output", default=".threads_token.json")
    sp.set_defaults(fn=cmd_get_token)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings(args.data_dir)
    return args.fn(Store(settings.data_dir), settings, args)


if __name__ == "__main__":
    sys.exit(main())
