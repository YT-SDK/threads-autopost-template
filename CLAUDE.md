# CLAUDE.md

Threads 運用自動化リポジトリ（ひな形から作成）。全体像は README.md、立ち上げは docs/new-account.md。

- 新しいアカウントの設計は `/setup-account <テーマ>`。設定は `data/config/`（account_profile.md・brand.json・research_domains.json・settings.json・ng_words.txt・identity_terms.txt）。
- コード: `threads_auto/`（標準ライブラリのみ・Python 3.11+）。変更したら `python -m unittest discover -s tests` を通す。エンジンの改良は本家（YT-SDK/Threads-）で行い、docs/ops/sync-engine.md の手順で取り込む。
- 運用コマンド: `.claude/commands/`（/setup-account, /collect-research, /build-formats, /generate-ideas, /research, /write-posts, /weekly-review）
- レビュー: `.claude/agents/post-reviewer.md`。外部知見: `.claude/agents/domain-researcher.md`（事実カードは `data/knowledge/facts/*.json`。投稿の数字・年・規格はカードで裏づけ、キューの `evidence_ids` に ID を入れる）。
- 学習: 毎朝 Actions が `data/learning.json` を更新。投稿を作るときは `docs/learning/playbook.md` を最初に読み、最後に教訓を更新する。
- データは `data/` に JSON/CSV で保存し、GitHub Actions もここにコミットする。キューを編集したら必ず `python -m threads_auto validate`。
- 投稿本文を作るときは毎回 `data/config/account_profile.md`・`post_rules.md`・`ng_words.txt` を読む。
- 特定につながる要素（`data/config/identity_terms.txt`）を1投稿に2つ以上入れない。account_profile.md 7章の「書かないこと」を守る。他人の写真を投稿に使わない。
- `review.human_approved` をユーザーの明示的な指示なしに true にしない（承認は Actions の approve ワークフローで本人が行う）。
- アクセストークン等の秘密情報をファイルやコミットに書かない。
