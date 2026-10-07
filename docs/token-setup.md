# Threads アクセストークン取得ガイド

所要時間は 20〜30 分です。**ターミナルを使わず、ブラウザだけで完了します**（ルートA）。

> **最重要ルール**: アクセストークンと App Secret は、Claude とのチャット、Slack、メール、リポジトリ内のファイルなど、**GitHub の Secrets 以外には一切貼らないでください**。
> トークンがあれば、第三者があなたの名前で投稿できてしまいます。
> 万一漏れた場合は、Meta のアプリ設定で App Secret をリセットしてください。発行済みのトークンは失効します。

## スマホだけで進める場合（すべて可能です）

| 作業 | 使うもの | 注意 |
|---|---|---|
| Meta の設定（①〜④） | Safari / Chrome | **「PC版サイトを表示」に切り替えてください**。モバイル表示ではメニューが隠れます（Safari: アドレスバー左の「ぁあ」→ デスクトップ用Webサイトを表示 / Chrome: ︙ → PC版サイト） |
| テスター承認（⑤） | Threads アプリ | 反映まで数分かかることがあります |
| PAT 作成・Secrets 登録（⑥⑦） | Safari / Chrome（PC版表示） | GitHub アプリではできません。PAT は画面を閉じると二度と見えないので、**同じブラウザの別タブで Secrets 登録画面を先に開いておき**、コピー→すぐ貼り付けます |
| 認可（⑧） | Safari / Chrome | **Threads アプリが勝手に開いてしまう場合があります**。その場合は URL をコピーし、ブラウザのアドレスバーに貼り付けて開いてください（それでもアプリが開く場合はプライベートブラウズで） |
| URL のコピー（⑧→⑨） | 同上 | エラー画面でアドレスバーをタップすると URL 全体が表示されます。「全選択→コピー」してください。`code=` が含まれていれば OK です（末尾の `#_` は付いたままで構いません） |
| ワークフロー実行（⑨⑩） | Safari / Chrome（PC版表示） | 「Run workflow」ボタンは Actions 画面の右側にあります |

> スクリーンショットで質問する場合は、**Secret・トークン・PAT が写っていないか必ず確認**してください（アプリIDは写っても問題ありません）。

## 全体の流れ

```
[Meta] ①アプリ作成 → ②権限追加 → ③テスター招待 → ④リダイレクトURI登録
[Threads] ⑤招待を承認
[GitHub] ⑥PAT作成 → ⑦Secrets/Variables登録
[ブラウザ] ⑧認可URLを開いて「許可」 → ⑨表示されたURLを setup-token ワークフローに貼る
          → Actions が長期トークン（60日）に交換し、Secret に自動登録（画面には出ない）
```

---

## Part 1. Meta 側の準備

### ① アプリを作成する
1. https://developers.facebook.com/apps/ を開き、「アプリを作成」を押します。
2. ユースケースで **「Threads API にアクセス」（Access the Threads API）** を選びます。
3. アプリ名は自由です（例: `threads-auto-<あなたの名前>`）。ビジネスポートフォリオは「今はリンクしない」で構いません。

### ② 権限を追加する
アプリダッシュボード → **ユースケース → Threads API → カスタマイズ（Customize）→ 権限（Permissions）** で、次の4つを「追加」にします。

| 権限 | 用途 |
|---|---|
| `threads_basic` | 必須（全API） |
| `threads_content_publish` | 投稿（ステップ5） |
| `threads_manage_replies` | 自分の投稿への返信（コメント欄）。**ないと本文だけ出て返信が 403 になる** |
| `threads_manage_insights` | 表示回数の取得（ステップ6） |

### ③ 自分をテスターに招待する
**アプリの役割（App roles）→ 役割（Roles）→ メンバーを追加（Add People）→「Threads テスター（Threads Tester）」** を選び、自分の Threads ユーザー名を入力します。

### ④ リダイレクトURIを登録し、ID と Secret を控える
**ユースケース → Threads API → カスタマイズ → 設定（Settings）** で:
- **コールバックURLのリダイレクト（Redirect Callback URLs）** に `https://localhost/` を追加します。末尾のスラッシュまで正確に入力し、保存してください。
- アンインストールや削除のコールバックURLが必須と言われた場合は、同じ `https://localhost/` を入れて構いません。
- 同じ画面にある **Threads アプリ ID（Threads App ID）** と **Threads App Secret** を控えます。

> ⚠️ **よくある失敗**: 画面上部や「設定 → ベーシック」には、Meta（Facebook）用のアプリIDも別に表示されます。使うのは **「Threads」と書かれている方の ID と Secret** です。取り違えると、⑨で `Invalid client_id` や `Error validating client secret` になります。

## Part 2. Threads 側の承認

### ⑤ テスター招待を承認する
Threads アプリまたは threads.com → **設定 → アカウント → ウェブサイトのアクセス許可（Website permissions）→ 招待（Invites）** で、該当アプリの招待を「承認」します。
- **Android 版アプリ**: プロフィール → 右上「＝」→ 設定 → **その他の設定** → ウェブサイトのアクセス許可 → 招待（「アカウントセンター」や「アカウントステータス」ではありません）

---

## Part 3. GitHub 側の準備

### ⑥ Secret 書き込み用の PAT を作る（トークンの自動延長にも使います）
1. GitHub → 右上アイコン → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**
2. 次のように設定します。
   - Resource owner: このリポジトリの所有者（`YT-SDK`）
   - Expiration: 1年（期限が来たら作り直します）
   - Repository access: **Only select repositories → `Threads-`**
   - Permissions → Repository permissions → **Secrets: Read and write**（これ以外は付けない）
3. 生成された値をコピーします（この画面を閉じると二度と表示されません）。

> 組織（Organization）のリポジトリの場合、組織の設定によっては PAT に管理者の承認が必要です。「Pending」のままなら、組織の Owner に承認を依頼してください。

### ⑦ Secrets と Variables を登録する
リポジトリ → **Settings → Secrets and variables → Actions**

| タブ | 名前 | 値 |
|---|---|---|
| Secrets | `THREADS_APP_SECRET` | ④で控えた Threads App Secret |
| Secrets | `GH_SECRETS_PAT` | ⑥の PAT |
| Variables | `THREADS_APP_ID` | ④で控えた Threads アプリ ID |
| Variables | `THREADS_REDIRECT_URI` | `https://localhost/`（④と同じ文字列。省略した場合もこの値になります） |

あわせて、**Settings → Actions → General → Workflow permissions** を **Read and write permissions** にしてください（投稿処理がデータをコミットするために必要です）。

> 前提: `setup-token` ワークフローは、このブランチが既定ブランチ（main）にマージされた後に、Actions 画面に表示されます。

---

## Part 4. トークンを取得する

### ⑧ 認可URLを開いて「許可」する
次のURLの `<THREADS_APP_ID>` を自分のIDに置き換えて、ブラウザで開きます。

```
https://threads.com/oauth/authorize?client_id=<THREADS_APP_ID>&redirect_uri=https%3A%2F%2Flocalhost%2F&scope=threads_basic%2Cthreads_content_publish%2Cthreads_manage_replies%2Cthreads_manage_insights&response_type=code
```

Threads にログインした状態で「許可」を押すと、**「このサイトにアクセスできません」というエラー画面**になります。これは正常です。
アドレスバーに `https://localhost/?code=AQB...#_` と表示されているので、**URL全体をコピー**してください。

### ⑨ setup-token ワークフローに貼る（1時間以内）
リポジトリ → **Actions → 「setup token (初回のトークン取得)」→ Run workflow** を開き、`code` 欄に⑧のURLを貼って実行します。

1〜2分で緑のチェックが付けば完了です。Secrets に `THREADS_ACCESS_TOKEN` と `THREADS_USER_ID` が自動で登録されています。トークンそのものは誰の画面にも表示されません。

### ⑩ 動作を確認する
**Actions → publish → Run workflow** を、`dry_run` にチェックを入れて実行します。エラーにならなければ、トークンは有効です。

---

## 別ルート

### ルートB: 手元の PC に Python 3.11 以上がある場合
```bash
cp .env.example .env    # THREADS_APP_ID / THREADS_APP_SECRET を記入（.env は Git 管理外）
set -a && . ./.env && set +a
python -m threads_auto auth-url                        # ⑧のURLが表示される
python -m threads_auto get-token --code 'https://localhost/?code=...#_'
# → .threads_token.json に保存される（画面にはトークンを表示しない）
gh secret set THREADS_ACCESS_TOKEN < <(python -c "import json;print(json.load(open('.threads_token.json'))['access_token'],end='')")
rm .threads_token.json
```

### ルートC: ダッシュボードにトークン生成ボタンがある場合
Meta の画面に、テスター用の「アクセストークンを生成（Generate Access Token）」ボタンがあることがあります。表示や位置は時期によって変わり、公式ドキュメントにも記載がありません。
- 生成されたトークンが**1時間有効（短期）**の場合: ルートBの `get-token --short-token <トークン>` で長期トークンに交換してから登録します。
- すでに**60日有効（長期）**の場合: そのまま Secret `THREADS_ACCESS_TOKEN` に登録できます。
- どちらか分からない場合は、ルートA（公式手順）を使ってください。

---

## トラブルシューティング

| 症状 | 原因と対処 |
|---|---|
| ⑧で「Invalid redirect_uri」「URL をブロックしました」 | ④の登録値と完全一致していません（`https`、末尾の `/`）。保存し忘れも多いので確認してください |
| ⑧でアカウントが選べない / 権限がないと出る | ⑤の招待承認が済んでいないか、③で別のアカウントを招待しています |
| ⑨で `Invalid client_id` / `Error validating client secret` | Meta 用の ID を使っています。「Threads」側の ID と Secret を使ってください |
| ⑨で `code has been used` / `expired` | 認可コードは1時間以内・1回限りです。⑧からやり直してください |
| ⑨で 「未登録です: …」 | ⑦の登録漏れです。メッセージに出た名前を登録してください |
| 投稿で本文は出たのに返信が `HTTP 403: Application does not have permission` | `threads_manage_replies` が未追加です。②で追加し、⑧⑨をやり直してください |
| ⑨で `gh: HTTP 403` | PAT の権限不足（Secrets: Read and write）、対象リポジトリの指定漏れ、または組織の承認待ちです |
| publish が `Session has expired` | 60日の期限切れです。⑧⑨をやり直してください（通常は refresh-token ワークフローが月2回延長します） |
