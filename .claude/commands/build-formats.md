---
description: ステップ2 バズフォーマット作成 — 収集した投稿を抽象化して「型」を formats.json に定義
---

# バズフォーマットの作成・更新

## 入力
- `data/research/liked_posts.csv`（ステップ1の収集結果）
- `data/formats.json`（既存の型。`score`/`n`/`rank` は分析結果なので保持する）
- `data/weights.json`（あれば。成績の悪い型の見直しに使う）

## 手順

1. CSV の投稿を読み、テーマではなく **構造** で分類する。見る観点:
   - 1行目（フック）の型: 断言 / 数字 / 失敗告白 / 問いかけ / 常識否定 / ビフォーアフター など
   - 本文の展開: 箇条書き / ストーリー / 比較 / 手順 / Q&A
   - 締め: 問い / 保存促し / 余韻 / 次回予告
   - 文字数帯・改行の密度
2. 3 件以上の投稿に共通する構造だけを「型」として採用する（1〜2件は偶然の可能性が高い）。
3. 各型を次のスキーマで `data/formats.json` に追加・更新する。IDは `F01` からの連番で、既存IDは変えない。
   ```json
   {"id": "F04", "name": "短い名前", "source": "liked_posts.csv の該当 permalink を2-3件",
    "structure": ["行ごとの役割"], "hook_pattern": "穴埋め式のフック例",
    "length_guide": "150-300字", "do": ["..."], "dont": ["..."],
    "status": "active", "score": null, "n": 0, "rank": null}
   ```
4. 収集元の CSV 行の `format_id` 列に該当する型IDを書き込む。
5. `weights.json` で `n >= 5` かつ `score < 0.7` の型は `status` を `paused` にし、理由を `dont` に追記する。
6. 型の一覧（ID・名前・根拠件数・変更点）を表で報告する。

## 禁止
- 元投稿の言い回しを型にそのまま埋め込まない（盗用リスク）。`hook_pattern` は必ず穴埋め式に抽象化する。
