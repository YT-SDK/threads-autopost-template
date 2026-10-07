# 新しいテーマのアカウントを立ち上げる手順

このリポジトリは「Threads 自動投稿の仕組み」のひな形です。エンジン（公開・分析・学習・チェック）はそのまま使い、テーマごとの設定だけを作ります。
目安：本人の作業 1〜2時間（スマホで可）＋ Claude との対話 1時間。

## 全体の流れ
| # | やること | だれが | どこで |
|---|---|---|---|
| 1 | Threads アカウントを作る（Instagram から） | 本人 | アプリ |
| 2 | このひな形から新しいリポジトリを作る | 本人 | GitHub（ブラウザ） |
| 3 | 図解カード置き場の公開リポジトリを作る | 本人 | GitHub（ブラウザ） |
| 4 | Claude Code のセッションで新リポジトリを開き、`/setup-account <テーマ>` | 本人＋Claude | Claude |
| 5 | Meta の登録とトークン（docs/token-setup.md） | 本人 | Meta・GitHub |
| 6 | 初回の調査・型づくり・最初の投稿 | Claude（本人が確認） | Claude |
| 7 | 週2回の自動作成（Routine）を登録 | Claude | Claude |

## 1. Threads アカウント
- Instagram で新しいアカウントを作り、Threads を始める。匿名で運用するなら、本名・顔・既存アカウントとのつながり（同じプロフィール写真・同じ言い回し）を避ける。
- ユーザーネームとプロフィール文は、手順4の対話で決めてから入れてもよい。

## 2. ひな形から新しいリポジトリを作る
1. GitHub で `YT-SDK/threads-autopost-template` を開く。
2. 緑の **Use this template** →「Create a new repository」。
3. 名前（例：`threads-<テーマ>`）、**Private** を選んで作成。
4. Claude の GitHub 連携（Claude GitHub App）が「All repositories」なら追加作業は不要。

## 3. 図解カード置き場（公開リポジトリ）
1. GitHub で新しいリポジトリを **Public** で作る（例：`<テーマ>-cards`。README だけ入れて作成）。
2. 名前を手順4で Claude に伝える（`data/config/brand.json` の `cards_repo` に入る）。
- 画像は Threads が自前のサーバーに保存し直すため、読者にこの URL は見えない。ただし公開リポジトリなので、中身（画像）は誰でも見られる。

## 4. アカウント設計（Claude と対話）
Claude Code で新しいリポジトリのセッションを開き、`/setup-account <テーマの候補>` と送る。次を一緒に決めて、ファイルに書き込む。
- `data/config/account_profile.md`：テーマ・読者・柱・一次情報・書かないこと
- `data/config/ng_words.txt`・`identity_terms.txt`：身バレ対策
- `data/config/research_domains.json`：研究員が調べる分野
- `data/config/brand.json`：表示名・ハンドル・図解の色・カード置き場
- `data/config/settings.json`：投稿時間（既定は平日 7:15・12:05・21:00／土日 9:45・13:00・21:00。根拠は docs/strategy/posting-times.md）

## 5. Meta の登録とトークン
`docs/token-setup.md` の手順どおり。**既存アカウントと同じ Meta アプリを使ってよい**（アプリの「テスター」に新しい Threads アカウントを追加する）。
- 新しいリポジトリの Secrets に `THREADS_APP_ID`・`THREADS_APP_SECRET`・`GH_SECRETS_PAT` を登録し、`setup-token` を実行する。
- 認可URLのスコープは `threads_basic, threads_content_publish, threads_manage_replies, threads_manage_insights`（コードの既定値）。
- トークン・App Secret・`code=` を含むURLは、Claude とのチャットに貼らない。

## 6. 初回の調査・型・最初の投稿
- `/research`：研究分野ごとに事実カードを作る（並列）。
- `/build-formats`：型を作る（伸びている投稿の収集は `/collect-research`）。
- `/write-posts 3`：最初の3本。最初は `require_human_approval: true` のまま、内容を見て Actions の **approve** で承認する。

## 7. 週2回の自動作成（Routine）
Claude に「週2回の自動作成を登録して」と頼む。指示文の元は `docs/ops/routine-prompt.md`（アカウント名やカード置き場は設定ファイルから読む）。

## 注意（複数アカウントを運用するとき）
- **同じ GitHub アカウント・同じ Meta アプリで管理すると、運営側からは同じ人だと分かる**。読者側には見えない。
- 同じ仕組みで作った似た投稿を複数アカウントで流すと、Meta の「不自然な振る舞い」と判定されるおそれがある。テーマ・読者・一次情報・図解の色をアカウントごとに変え、文章を使い回さない。
- エンジンの改良は、元のリポジトリ（ひな形）に入れてから各アカウントに取り込む（docs/ops/sync-engine.md）。
