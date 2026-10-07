---
description: ステップ6-7 分析と改善ループ — 表示回数を取得・スコアリングし、フォーマット順位とネタの重みを更新
---

# 週次の分析と改善

GitHub Actions（daily analytics）が毎朝 06:13 に自動実行し、`data/learning.json` と `data/reports/` を更新している。学んだことは `docs/learning/playbook.md` に積み上げる。手動で回す／結果を解釈する時に使う。

## 手順

1. 最新化: `git pull`（Actions が指標と weights.json をコミットしているため）
2. Actions を使っていない場合のみ:
   `python -m threads_auto fetch-insights && python -m threads_auto update-weights`
3. `data/reports/` の最新レポートと `data/weights.json` を読み、次を報告する:
   - フォーマット順位と、自動提案（増やす / 検証継続 / 休止候補）への賛否と理由
   - 上位・下位投稿の差分（フック・文字数・テーマ・投稿時間帯）から読み取れる仮説を最大3つ。
     **n が小さい段階では「仮説」と明記し、断定しない**
   - 投稿時間帯ごとの傾向（`scheduled_at` の時刻別に指数を比較。枠あたり 5 本未満なら参考値）
4. ユーザーの合意を得てから反映する:
   - 休止する型 → `formats.json` の `status` を `paused`
   - 新しい型の仮説 → `/build-formats` で検証用の型を追加
   - 投稿枠の変更 → `data/config/settings.json` の `posting_slots`
5. 次週の `/write-posts` で使う配分（型ごとの本数）を提案する。
