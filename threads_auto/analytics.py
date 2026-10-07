"""ステップ6（表示回数の取得とスコアリング）とステップ7（ランキング・重み付け更新）。

スコアの考え方:
  - 主指標は記事どおり「表示回数(views)」。アカウントの成長で母数が変わるため、
    絶対値ではなく「対象期間の中央値に対する倍率（相対表示指数）」で比較する。
  - 公開からの経過時間が違う投稿を同じ土俵で比べるため、どの投稿も「公開 eval_age_hours（24h）時点」の
    数値で比べる。取得は1日1回なので、24h をはさむ前後2回の取得値から直線で推定し、
    eval_metrics として投稿データに固定する（以後は変えない）。
  - 本数が少ないフォーマットの偶然の当たりを過大評価しないよう、
    平均を 1.0（=中央値並み）へ k 本分だけ引き寄せる（ベイズ平滑化）。
  - エンゲージメント率は参考値としてレポートに併記（重みには使わない）。
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from statistics import median

from .config import Settings
from .http import APIError
from .store import Store, append_jsonl, parse_time, read_json, write_json
from .threads_api import ThreadsClient

WEIGHT_MIN, WEIGHT_MAX = 0.5, 2.0


def fetch_insights(client: ThreadsClient, store: Store, settings: Settings, now: datetime) -> list[str]:
    log, snapshots = [], []
    since = now - timedelta(days=settings["insights_lookback_days"])
    for path, item in store.posted():
        if not item.get("media_id") or not item.get("published_at"):
            continue
        published = parse_time(item["published_at"])
        if published < since:
            continue
        try:
            metrics = client.insights(item["media_id"])
        except APIError as e:
            log.append(f"ERROR {path.name}: {e}")
            continue
        age_hours = round((now - published).total_seconds() / 3600, 1)
        current = dict(metrics, fetched_at=now.isoformat(), age_hours=age_hours)
        if "eval_metrics" not in item and age_hours >= settings["eval_age_hours"]:
            item["eval_metrics"] = eval_snapshot(item.get("metrics"), current, settings["eval_age_hours"])
        item["metrics"] = current
        store.save(path, item)
        snapshots.append({"id": path.stem, "media_id": item["media_id"], **item["metrics"]})
        log.append(f"OK {path.name}: views={metrics.get('views')} age={age_hours}h")
    append_jsonl(store.root / "metrics" / "history.jsonl", snapshots)
    try:
        account = client.account_insights()
        append_jsonl(store.root / "metrics" / "account.jsonl", [dict(account, fetched_at=now.isoformat())])
        log.append(f"OK account: {account}")
    except APIError as e:  # アカウント指標が取れなくても投稿の分析は続ける
        log.append(f"ERROR account: {e}")
    return log


def eval_snapshot(before: dict | None, after: dict, target_hours: float) -> dict:
    """公開 target_hours 時点の数値。前回の取得が target より前なら、前後2回から直線で推定する。

    前回の取得がない（取得の抜けなど）ときは、target を過ぎた最初の取得値をそのまま使う。
    """
    t1 = after["age_hours"]
    if before and before.get("age_hours", target_hours) < target_hours < t1:
        t0 = before["age_hours"]
        ratio = (target_hours - t0) / (t1 - t0)
        values = {
            k: round(before.get(k, 0) + (v - before.get(k, 0)) * ratio)
            for k, v in after.items()
            if isinstance(v, (int, float)) and k != "age_hours"
        }
        return dict(values, age_hours=target_hours, method="interpolated")
    values = {k: v for k, v in after.items() if isinstance(v, (int, float)) and k != "age_hours"}
    return dict(values, age_hours=t1, method="first_after")


def engagement_rate(m: dict) -> float:
    views = m.get("views", 0)
    if not views:
        return 0.0
    return sum(m.get(k, 0) for k in ("likes", "replies", "reposts", "quotes")) / views


def slot_name(hour: int) -> str:
    """投稿時刻を朝・昼・夜にまとめる（枠の時刻を動かしても比べられるように）。"""
    return "朝" if hour < 11 else "昼" if hour < 17 else "夜"


def features(item: dict, settings: Settings) -> dict[str, str]:
    """学習に使う投稿の特徴。どれも投稿データから機械的に決まるものだけ。"""
    tags = item.get("tags") or []
    when = parse_time(item.get("scheduled_at") or item["published_at"]).astimezone(settings.tz)
    first = (item.get("text") or "").splitlines()[0] if item.get("text") else ""
    return {
        "pillar": tags[0] if tags else "(未設定)",
        "slot": slot_name(when.hour),
        "image": "画像あり" if item.get("image_url") else "文字のみ",
        "hook_number": "1行目に数字あり" if any(c.isdigit() for c in first) else "1行目に数字なし",
        "hook_length": "1行目20字以内" if len(first) <= 20 else "1行目21字以上",
    }


FEATURE_LABELS = {
    "pillar": "柱（テーマ）",
    "slot": "投稿時間帯",
    "image": "画像",
    "hook_number": "1行目の数字",
    "hook_length": "1行目の長さ",
}


def scored_posts(store: Store, settings: Settings, now: datetime) -> list[dict]:
    window_start = now - timedelta(days=settings["scoring_window_days"])
    rows = []
    for path, item in store.posted():
        m = item.get("eval_metrics") or {}
        if "views" not in m or not item.get("published_at") or item.get("format_id") == "TEST":
            continue
        if parse_time(item["published_at"]) < window_start:
            continue
        rows.append(
            {
                "id": path.stem,
                "text": item.get("text", ""),
                "permalink": item.get("permalink"),
                "format_id": item.get("format_id") or "(未設定)",
                "tags": item.get("tags") or [],
                "views": m["views"],
                "er": engagement_rate(m),
                "features": features(item, settings),
            }
        )
    if not rows:
        return []
    base = median(r["views"] for r in rows) or 1
    for r in rows:
        r["index"] = r["views"] / base
    return rows


def aggregate(rows: list[dict], key_fn, k: float) -> dict[str, dict]:
    groups: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        for key in key_fn(r):
            groups[key].append(r["index"])
    out = {}
    for key, vals in groups.items():
        smoothed = (sum(vals) + k * 1.0) / (len(vals) + k)
        out[key] = {"score": round(smoothed, 3), "raw_mean": round(sum(vals) / len(vals), 3), "n": len(vals)}
    ranked = sorted(out, key=lambda x: out[x]["score"], reverse=True)
    for i, key in enumerate(ranked, 1):
        out[key]["rank"] = i
    return dict(sorted(out.items(), key=lambda kv: kv[1]["rank"]))


def update_weights(store: Store, settings: Settings, now: datetime) -> dict:
    rows = scored_posts(store, settings, now)
    k = settings["smoothing_k"]
    formats = aggregate(rows, lambda r: [r["format_id"]], k)
    tags = aggregate(rows, lambda r: r["tags"], k)
    tag_weights = {t: min(WEIGHT_MAX, max(WEIGHT_MIN, v["score"])) for t, v in tags.items()}
    feats = {name: aggregate(rows, lambda r, n=name: [r["features"][n]], k) for name in FEATURE_LABELS}

    weights = {
        "updated_at": now.isoformat(),
        "sample_size": len(rows),
        "median_views": median(r["views"] for r in rows) if rows else None,
        "formats": formats,
        "tags": tags,
        "tag_weights": tag_weights,
        "features": feats,
    }
    write_json(store.root / "weights.json", weights)
    write_json(store.root / "learning.json", learning_signals(rows, weights, store, now))

    # formats.json にランキングを書き戻す（/write-posts が参照）
    fmts = store.formats()
    for f in fmts:
        stat = formats.get(f.get("id"))
        f["score"], f["n"], f["rank"] = (stat["score"], stat["n"], stat["rank"]) if stat else (None, 0, None)
    store.save_formats(fmts)

    # ideas.json の未使用ネタに重みを書き戻す（タグ重みの平均。未評価タグは 1.0）
    ideas = store.ideas()
    for idea in ideas:
        if idea.get("status", "unused") != "unused":
            continue
        ws = [tag_weights.get(t, 1.0) for t in idea.get("tags", [])] or [1.0]
        idea["weight"] = round(sum(ws) / len(ws), 3)
    store.save_ideas(ideas)

    report = render_report(rows, weights, settings, now)
    report_path = store.root / "reports" / f"{now.astimezone(settings.tz).date().isoformat()}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    weights["report_path"] = str(report_path)
    return weights


def judge(stat: dict) -> str:
    """本数が少ないうちは判断しない。偶然の当たり外れで配分を振り回さないため。"""
    if stat["n"] < 3:
        return "検証中"
    if stat["score"] >= 1.2:
        return "増やす"
    if stat["n"] >= 5 and stat["score"] < 0.75:
        return "減らす"
    return "維持"


def follower_trend(store: Store) -> dict:
    path = store.root / "metrics" / "account.jsonl"
    if not path.exists():
        return {}
    import json

    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = [r for r in rows if "followers_count" in r]
    if not rows:
        return {}
    latest = rows[-1]
    week_ago = rows[-8] if len(rows) >= 8 else rows[0]
    return {
        "followers": latest["followers_count"],
        "change_7d": latest["followers_count"] - week_ago["followers_count"],
        "as_of": latest.get("fetched_at"),
    }


def learning_signals(rows: list[dict], weights: dict, store: Store, now: datetime) -> dict:
    """投稿づくり（週2回の自動作成）が読む学習結果。判断は judge() の基準だけで機械的に出す。"""
    out = {
        "updated_at": now.isoformat(),
        "sample_size": len(rows),
        "exploration_share": 0.3,
        "followers": follower_trend(store),
        "formats": {k: dict(v, decision=judge(v)) for k, v in weights["formats"].items()},
        "features": {
            name: {k: dict(v, decision=judge(v)) for k, v in groups.items()}
            for name, groups in weights["features"].items()
        },
    }
    ordered = sorted(rows, key=lambda r: r["index"], reverse=True)
    pick = lambda r: {"id": r["id"], "index": round(r["index"], 2), "views": r["views"], "first_line": r["text"].splitlines()[0] if r["text"] else "", **r["features"]}
    out["top"] = [pick(r) for r in ordered[:3]]
    out["bottom"] = [pick(r) for r in ordered[-3:][::-1]] if len(ordered) > 3 else []
    return out


def recommendations(formats: dict) -> list[str]:
    recs = []
    for fid, s in formats.items():
        if s["n"] < 3:
            recs.append(f"- {fid}: 本数 {s['n']} で判定保留。今週あと {3 - s['n']} 本以上試す")
        elif s["score"] >= 1.2:
            recs.append(f"- {fid}: 好調（指数 {s['score']}）。投稿比率を上げ、ネタを変えて再現性を確認")
        elif s["n"] >= 5 and s["score"] < 0.7:
            recs.append(f"- {fid}: 不調が継続（指数 {s['score']}, n={s['n']}）。休止または型の見直し候補")
    return recs or ["- 目立った偏りなし。現行比率を維持"]


def render_report(rows: list[dict], weights: dict, settings: Settings, now: datetime) -> str:
    lines = [
        f"# Threads 週次レポート（{now.astimezone(settings.tz):%Y-%m-%d}）",
        "",
        f"- 対象: 直近 {settings['scoring_window_days']} 日・公開 {settings['eval_age_hours']}h 時点の数値がそろった投稿 {len(rows)} 本",
        "- 比べる数値は公開24時間時点の値（1日1回の取得値の前後2回から推定）",
        f"- 表示回数の中央値: {weights['median_views']}",
        "- 指数 = 表示回数 ÷ 中央値（1.0 が平均並み）。スコアは本数が少ないほど 1.0 に寄せた値",
        "",
    ]
    if not rows:
        lines.append("評価できる投稿がまだありません。")
        return "\n".join(lines) + "\n"

    lines += ["## フォーマット別ランキング", "", "| 順位 | format | スコア | 素の平均 | 本数 |", "|---|---|---|---|---|"]
    for fid, s in weights["formats"].items():
        lines.append(f"| {s['rank']} | {fid} | {s['score']} | {s['raw_mean']} | {s['n']} |")
    lines += ["", "## ネタ（タグ）別の重み", "", "| タグ | 重み | 本数 |", "|---|---|---|"]
    for tag, s in weights["tags"].items():
        lines.append(f"| {tag} | {weights['tag_weights'][tag]} | {s['n']} |")

    ordered = sorted(rows, key=lambda r: r["index"], reverse=True)
    lines += ["", "## 上位3投稿", ""]
    for r in ordered[:3]:
        lines.append(f"- 指数 {r['index']:.2f} / views {r['views']} / ER {r['er']:.1%} / {r['format_id']} — {r['text'][:40]}… {r['permalink'] or ''}")
    lines += ["", "## 下位3投稿", ""]
    for r in ordered[-3:][::-1]:
        lines.append(f"- 指数 {r['index']:.2f} / views {r['views']} / ER {r['er']:.1%} / {r['format_id']} — {r['text'][:40]}… {r['permalink'] or ''}")
    lines += ["", "## 特徴別の傾向（3本未満は判断しない）", ""]
    for name, label in FEATURE_LABELS.items():
        groups = weights["features"].get(name) or {}
        cells = " / ".join(f"{k} {v['score']}（n={v['n']}, {judge(v)}）" for k, v in groups.items())
        lines.append(f"- {label}: {cells or 'データなし'}")
    lines += ["", "## 次週アクション（自動提案）", ""] + recommendations(weights["formats"])
    return "\n".join(lines) + "\n"


def load_weights(store: Store) -> dict:
    return read_json(store.root / "weights.json", {})
