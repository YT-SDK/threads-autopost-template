"""予約キューの機械チェック（文字数・予約時刻・重複・NGワード・レビュー状態）。

AIレビュー（post-reviewer サブエージェント）の前後に必ず通す「最後の関所」。
"""

from __future__ import annotations

import re
import unicodedata

from .store import Store, parse_time
from .threads_api import MAX_TEXT_LENGTH

URL_RE = re.compile(r"https?://\S+")
MAX_LINKS = 5
REVIEW_STATUSES = {"pending", "approved", "rejected"}
# 根拠に使えない事実カードの状態（通説・未確認・出典が食い違う）
UNUSABLE_FACT_STATUSES = {"myth", "unverified", "conflict"}
# 2秒ルール（post_rules.md B0・B3）：1行目の文字数・本文の長さ・本文に出さない専門用語
HOOK_MAX = 25
BODY_MAX_LINES, BODY_MAX_CHARS = 4, 80
JARGON_RE = re.compile(r"Ra|R9|lm|ルーメン|JIS|演色|全光束|配光|色温度|\d+\s*K\b")
# 本文に数値の主張があるかの目安（単位つきの数字）
CLAIM_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:K|lm|ルーメン|lx|ルクス|cm|mm|℃|%|％|畳)")


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text or ""))


def validate_item(
    item: dict,
    *,
    format_ids: set[str],
    ng_words: list[str],
    posted_texts: set[str],
    identity_terms: dict[str, str] | None = None,
    facts: dict[str, dict] | None = None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    parts = [item.get("text", "")] + list(item.get("replies", []))
    if not parts[0].strip():
        errors.append("text が空です")
    for i, part in enumerate(parts):
        label = "本文" if i == 0 else f"返信{i}"
        if len(part) > MAX_TEXT_LENGTH:
            errors.append(f"{label}が {len(part)} 文字です（上限 {MAX_TEXT_LENGTH}）")
        if len(URL_RE.findall(part)) > MAX_LINKS:
            errors.append(f"{label}のリンクが {MAX_LINKS} 件を超えています")
        if part.count("#") + part.count("＃") > 1:
            warnings.append(f"{label}: Threads のトピックタグは1投稿1つまでです")
        for w in ng_words:
            if w in part:
                errors.append(f"{label}に NGワード「{w}」が含まれます")

    lines = [l for l in parts[0].splitlines() if l.strip()]
    if lines and len(re.sub(r"^PR[｜|]\s*", "", lines[0])) > HOOK_MAX:
        warnings.append(f"1行目が {len(lines[0])} 字です（2秒ルール：20字以内・最大{HOOK_MAX}字）")
    if len(lines) > BODY_MAX_LINES or len("".join(lines)) > BODY_MAX_CHARS:
        warnings.append(f"本文が {len(lines)} 行・{len(''.join(lines))} 字です（2秒ルール：{BODY_MAX_LINES}行・{BODY_MAX_CHARS}字以内）")
    jargon = sorted(set(JARGON_RE.findall(parts[0])))
    if jargon:
        warnings.append(f"本文に専門用語があります（返信へ移す）: {'、'.join(jargon)}")

    urls = ([item["image_url"]] if item.get("image_url") else []) + list(item.get("image_urls") or [])
    if any(not str(u).startswith("https://") for u in urls):
        errors.append("image_url / image_urls は https:// で始まる公開URLにしてください")
    if item.get("image_urls") and not 2 <= len(item["image_urls"]) <= 20:
        errors.append("image_urls（複数枚投稿）は2〜20枚にしてください")
    whole = "\n".join(parts)
    found = [label for label, pat in (identity_terms or {}).items() if re.search(pat, whole)]
    if len(found) >= 2:
        errors.append(f"経歴の要素が1投稿に2つ以上あります（身バレのおそれ）: {'、'.join(found)}")
    if URL_RE.search(whole) and "PR" not in parts[0].splitlines()[0].upper():
        warnings.append("リンクがあります。報酬が発生する案件なら本文の冒頭に「PR」を入れてください（ステマ規制）")

    evidence = item.get("evidence_ids") or []
    for fid in evidence:
        card = (facts or {}).get(fid)
        if card is None:
            errors.append(f"evidence_ids の {fid} が data/knowledge/facts にありません")
        elif card.get("status") in UNUSABLE_FACT_STATUSES:
            errors.append(f"{fid} は status={card['status']} のため根拠に使えません")
    if CLAIM_RE.search(whole) and not evidence:
        warnings.append("数値の主張があります。根拠の事実カードを evidence_ids に入れてください")

    try:
        parse_time(item.get("scheduled_at", ""))
    except (ValueError, TypeError) as e:
        errors.append(f"scheduled_at が不正です: {e}")

    fmt = item.get("format_id")
    if not fmt:
        warnings.append("format_id が未設定です（分析でフォーマット評価ができません）")
    elif format_ids and fmt not in format_ids:
        warnings.append(f"format_id {fmt} は formats.json にありません")
    if not item.get("tags"):
        warnings.append("tags が未設定です（ネタの重み付けに使えません）")

    review = item.get("review") or {}
    if review.get("status", "pending") not in REVIEW_STATUSES:
        errors.append(f"review.status は {sorted(REVIEW_STATUSES)} のいずれかにしてください")

    if normalize(parts[0]) in posted_texts:
        errors.append("公開済みの投稿と本文が同一です")
    return errors, warnings


def validate_queue(store: Store) -> dict[str, tuple[list[str], list[str]]]:
    format_ids = {f["id"] for f in store.formats() if "id" in f}
    posted_texts = {normalize(p.get("text", "")) for _, p in store.posted()}
    ng = store.ng_words()
    identity = store.identity_terms()
    facts = store.facts()
    seen: dict[str, str] = {}
    results = {}
    for path, item in store.queue():
        errors, warnings = validate_item(item, format_ids=format_ids, ng_words=ng, posted_texts=posted_texts, identity_terms=identity, facts=facts)
        key = normalize(item.get("text", ""))
        if key and key in seen:
            errors.append(f"{seen[key]} と本文が重複しています")
        seen.setdefault(key, path.name)
        results[path.name] = (errors, warnings)
    return results
