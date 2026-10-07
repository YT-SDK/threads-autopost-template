# Threads 運用自動化（7ステップ実装）

[AI Crew School の記事「Claude Code × Threads運用 全自動化 7ステップ」](https://www.ai-crew-school.jp/blog/threads-automation-7steps/) の仕組みを、実際に動くコードにしたものです。
記事は概念紹介にとどまるため、スプレッドシート構成、スコア計算式、GitHub Actions の設定、二重投稿対策はこのリポジトリで独自に設計しました。

## 全体像

| # | ステップ | 担当 | 実装 |
|---|---|---|---|
| 1 | 競合リサーチ | Claude in Chrome | `/collect-research` → `data/research/liked_posts.csv` |
| 2 | バズフォーマット作成 | Claude Code | `/build-formats` → `data/formats.json` |
| 3 | ネタ出し | Discord + Claude Code | `ingest-discord` + `/generate-ideas` → `data/ideas.json` |
| 4 | 投稿作成・レビュー | Claude Code + サブエージェント | `/write-posts` + `post-reviewer` → `data/queue/*.json` |
| 5 | 自動投稿 | GitHub Actions（毎時） | `publish.yml` → Threads API |
| 6 | 表示回数の分析 | GitHub Actions（毎週月曜） | `weekly-analytics.yml` → `data/posted/*.json` の `metrics` |
| 7 | 改善ループ | 自動 + `/weekly-review` | `weights.json`・`formats.json` の順位・`ideas.json` の重み・`data/reports/` |

```
いいね ──▶ 1 CSV ──▶ 2 型(formats) ─┐
Discordメモ ─▶ 3 ネタ(ideas) ────────┼─▶ 4 下書き ─▶ AIレビュー ─▶ 機械チェック ─▶ 人の承認 ─▶ queue
                  ▲                    │                                                        │
                  │ 重み               │ 順位                                                    ▼
                  └──── 7 改善 ◀── 6 表示回数取得・スコア ◀── posted ◀──── 5 GitHub Actions 予約投稿
```

人が手を動かすのは週に1回、合計30〜60分程度を想定しています（`/collect-research`、`/write-posts`、承認、レポート確認）。1〜4 は手元の Claude Code、5〜7 は GitHub Actions で動きます。

---

## セットアップ

### 1. アクセストークンの取得（ステップ5の前提）

**[docs/token-setup.md](docs/token-setup.md) の手順に従ってください。** ブラウザだけで完了します。
Meta でアプリを作成してテスターを承認し、認可URLで「許可」した後、表示されたURLを `setup-token` ワークフローに貼ると、長期トークン（60日）が Secret に自動登録されます。

### 2. GitHub の設定

**Settings → Secrets and variables → Actions** に次を登録します。

| 名前 | 必須 | 内容 |
|---|---|---|
| `THREADS_ACCESS_TOKEN` | ✅ | 長期アクセストークン（`setup-token` ワークフローが自動登録） |
| `THREADS_USER_ID` | 任意 | 未設定なら `me` |
| `GH_SECRETS_PAT` | 推奨 | トークンの自動延長用です。fine-grained PAT に、このリポジトリの「Secrets: Read and write」権限を付けてください |

**Settings → Actions → General → Workflow permissions** を「Read and write」にします。Actions が投稿状態をコミットするために必要です。

最初の1〜2回は、Variables に `DRY_RUN=1` を入れるか、`publish` を手動実行して `dry_run` にチェックを入れて動作を確認してください。

### 3. Discord（ステップ3・任意）

1. Discord Developer Portal で Bot を作成し、**MESSAGE CONTENT INTENT** を ON にします。
2. メモ用チャンネルに Bot を招待し、「メッセージ履歴を読む」権限を付けます。
3. ローカルの `.env`（`.env.example` をコピー）に `DISCORD_BOT_TOKEN` と `DISCORD_CHANNEL_IDS`（カンマ区切り）を設定します。

> Claude Code の Discord 連携（channels / MCP）を使っている場合は、それで `data/knowledge/` にメモを書き出しても構いません。`/generate-ideas` は `data/knowledge/` 配下をすべて読みます。

### 4. アカウント設計を埋める

`data/config/account_profile.md`（読者・トーン・書かないこと）と `data/config/ng_words.txt` を埋めます。**ここが空のままだと、レビューの基準が曖昧になります。**

---

## 週次の運用

```bash
# 月曜: Actions が分析結果をコミット済み
git pull
claude   # 以下は Claude Code 内で実行
/weekly-review          # 6-7: 結果の解釈と改善案（合意したものだけ反映）
/collect-research 30    # 1: いいねした投稿を収集
/build-formats          # 2: 型の追加・休止（隔週でも可）
/generate-ideas 20      # 3: ネタ補充
/write-posts 21         # 4: 1週間分（3枠×7日）を作成・レビュー・予約
```
```bash
python -m threads_auto status          # キュー確認
python -m threads_auto approve --all   # 内容を読んだうえで承認
git add data && git commit -m "queue: week N" && git push
```
あとは Actions が予定時刻に投稿し、翌週月曜に分析します。

### CLI 一覧（`python -m threads_auto <cmd>`）

| コマンド | 用途 |
|---|---|
| `validate` | キューの機械チェックです（500字上限、リンク数、NGワード、重複、予約時刻のTZ、レビュー状態） |
| `status` / `next-slots --count N` | キューの状態 / 空いている投稿枠 |
| `approve <id...>` / `--all` | 人による最終承認（AIレビューが approved のものだけ承認できます） |
| `publish-due [--dry-run]` | 予定時刻を過ぎた投稿を公開します（Actions 用） |
| `fetch-insights` / `update-weights` | 指標の取得 / 順位・重み・レポートの更新（Actions 用） |
| `ingest-discord` / `whoami` / `refresh-token` | Discord の取り込み / 疎通確認 / トークン延長 |
| `auth-url` / `get-token --code <URL>` | 初回のトークン取得（手元で実行する場合） |

外部ライブラリは使っていません（Python 3.11 以上の標準ライブラリのみ）。テストは `python -m unittest discover -s tests` で実行できます。

---

## 設計判断（記事に書かれていない部分）

### スコアリング（ステップ6）
- **主指標は表示回数（views）**です（記事に準拠）。アカウントが伸びると絶対値は上がり続けるため、**直近14日の中央値を1.0とした倍率（相対表示指数）**で比べます。
- どの投稿も**公開24時間時点の数値**で比べます（`eval_age_hours`）。取得は1日1回なので、24時間をはさむ前後2回の取得値から直線で推定し、`eval_metrics` として固定します。取得時点の累計で比べると、古い投稿ほど有利になるためです。
- 型ごとの平均は、本数が少ないほど1.0に寄せます（`smoothing_k=2` のベイズ平滑化）。1本だけの大当たりで型を過大評価しないためです。
- いいね・返信などのエンゲージメント率は、レポートに参考値として載せるだけで、重みには使いません。

### 改善ループ（ステップ7）
- 型ごとの順位を `formats.json` の `rank` / `score` に書き戻し、`/write-posts` は上位の型を多めに使います。ただし、**本数3未満の型にも2〜3割の検証枠を残します**。当たり型だけに寄せ続けると、飽きられて全体が下がるためです。
- タグごとの重み（0.5〜2.0）を未使用ネタの `weight` に書き戻し、重みの高いネタから使います。
- 休止や型の新設などの構造的な変更は自動では行いません。`/weekly-review` で提案し、人が合意したときだけ反映します。

### 安全装置（ステップ4〜5）
- **3段階の関所**: AIレビュー（`post-reviewer`、80点以上）→ 機械チェック（`validate`）→ 人の承認（`require_human_approval: true`）。
- **二重投稿の防止**: 同時実行を1本に制限し、公開前に直近25件の自分の投稿と本文を照合します。同じ本文が既にあれば、投稿せずに記録だけします。
- **一斉放出の防止**: 1回の実行で最大1本、前の投稿から60分以上空けます。予定から24時間を過ぎた投稿は `expired` にします（Actions が止まった後に古い投稿がまとめて出るのを防ぎます）。
- 公開に3回失敗した投稿は `failed` にして止めます。原因は `last_error` に残ります。

---

## リスクと失敗パターン

| # | 失敗パターン | 予防策（実装済み / 運用） |
|---|---|---|
| 1 | **勤務先の情報や、個人が推測できる事例の流出**（会社員の発信で最も重い事故） | NGワードで機械的にブロックし、レビューで即不合格にし、人の承認を必須にしています。`account_profile.md` の「書かないこと」を具体的に書き、就業規則やSNSガイドラインも確認してください |
| 2 | **型への過剰最適化で似た投稿ばかりになり、フォロワーの反応が落ちる** | 検証枠2〜3割、同じタグの連続を禁止、成績が落ち続ける型は休止候補にします。レポートの中央値が3週連続で下がったら、型を入れ替えるサインです |
| 3 | **トークン失効で投稿が静かに止まる** | 月2回の自動延長（`GH_SECRETS_PAT` が必要です）。Actions の失敗通知を受け取れるようにし、`status` に `expired` / `failed` が溜まっていないか毎週確認してください |

その他の注意:
- **「全自動」は目指していません。** 記事の構成どおりにしつつ、人の承認を残す初期設定にしています。2〜4週間運用してレビュー差し戻し率が十分に下がったら、`require_human_approval` を `false` にすることを検討してください。
- 他人の投稿は**型の抽出だけ**に使います。本文の転用は盗用リスクがあるため、`/build-formats` で禁止しています。
- Threads API の制限: 本文500字、24時間あたり250投稿、トピックタグは1投稿1つ（公式ドキュメントで最新値を確認してください）。
- GitHub Actions の cron は数分〜十数分遅れることがあり、長く更新のないリポジトリでは定期実行が自動で止まることがあります。Actions がデータをコミットし続けるので通常は問題になりませんが、止まった場合は手動実行で再開してください。

## 他のテーマのアカウントに使う
この仕組みはエンジン（`threads_auto/`・Actions・エージェント・コマンド）とテーマの設定（`data/config/`・`data/` の中身）に分かれています。
- ひな形の書き出し：`python tools/export_template.py <出力先>`（テーマ固有のファイルは含まない。`template/` の空の設定で上書き）
- 新しいアカウントの立ち上げ手順：`template/docs/new-account.md`（ひな形では `docs/new-account.md`）
- テーマごとの設定：`data/config/brand.json`（表示名・図解の色・カード置き場）、`research_domains.json`（研究員の分野）、`account_profile.md`・`ng_words.txt`・`identity_terms.txt`・`settings.json`
- エンジンの改良の取り込み：`docs/ops/sync-engine.md`。週2回の自動作成の指示文：`docs/ops/routine-prompt.md`
