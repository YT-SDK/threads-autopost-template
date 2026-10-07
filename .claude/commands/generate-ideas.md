---
description: ステップ3 無限ネタ出し — Discord 等に書き溜めたナレッジからネタを生成し ideas.json に追加
---

# ネタ出し

## 手順

1. 最新のナレッジを取り込む: `python -m threads_auto ingest-discord`
   （環境変数 `DISCORD_BOT_TOKEN` / `DISCORD_CHANNEL_IDS` が未設定ならスキップし、その旨を伝える）
2. 入力を読む:
   - `data/config/account_profile.md`（発信テーマ・読者・書かないこと）
   - `data/knowledge/discord.jsonl` と `data/knowledge/` 配下のその他のメモ
   - `data/ideas.json`（既存ネタ。重複させない）
   - `data/weights.json` の `tag_weights`（あれば。重みが高いタグのネタを多めに）
3. ネタを $ARGUMENTS 件（指定なしは 20 件）作る。1ナレッジから切り口を変えて複数ネタにしてよい:
   - 切り口の例: 失敗談 / やり方の手順 / 誤解の訂正 / 比較 / チェックリスト / 読者の悩みへの回答
4. 各ネタを次の形式で `data/ideas.json` に追記する（IDは既存の続きの連番）:
   ```json
   {"id": "I013", "title": "一言で言うと何の話か", "angle": "切り口", "key_point": "読者が持ち帰る1つの主張",
    "evidence": "根拠となるナレッジの抜粋や出典（Discord メッセージIDなど）", "tags": ["2-3個"],
    "suggested_formats": ["F01"], "status": "unused", "weight": 1.0, "created_at": "YYYY-MM-DD"}
   ```
   - `tags` は既存タグを優先して再利用する（表記ゆれがあると重み付けが効かない）。
5. 追加件数とタグ別件数を報告する。

## 品質基準
- `evidence` が書けないネタは作らない（事実の捏造防止）。
- `account_profile.md` の「書かないこと」に触れるネタは作らない。
