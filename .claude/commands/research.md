---
description: 外部知見の調査 — domain-researcher サブエージェントに分野・テーマを調べさせ、出典つきの事実カードと投稿の切り口を data/knowledge/ に残す
---

# 外部知見の調査

テーマ: $ARGUMENTS（指定なしは「次に書くネタで、事実カードが足りないもの」）

1. `data/knowledge/research/*.md` と `data/knowledge/facts/*.json` を読み、すでに分かっていること・未確認のもの・`volatile: true` で `checked_at` が90日より古いものを洗い出す。
2. 確かめたい主張を、分野（`data/config/research_domains.json` の `id`）ごとに箇条書きにする。
3. 分野ごとに **domain-researcher サブエージェント**（Agent ツール、subagent_type: domain-researcher）を並列で呼ぶ。
   1回の依頼は1分野・主張10個までにする。同じ分野のファイルを2つのエージェントに同時に書かせない。
4. 戻ってきたら、追加・更新されたカードを確認する：
   - JSON として読めるか（`python -c "import json,glob;[json.load(open(p)) for p in glob.glob('data/knowledge/facts/*.json')]"`）
   - `verified` のカードに S/A の出典、または独立した B が2つあるか（足りなければ `partial` か `unverified` に下げる）
5. 研究ノートの「投稿の切り口」を `data/ideas.json` に `status: unused` で追加してよい（`source: "research"`、`evidence_ids` つき）。
6. 報告：分野ごとの件数（status 別）、すぐ使える切り口の上位3つ、使ってはいけない通説。
