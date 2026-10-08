---
description: ステップ4 投稿作成とレビュー — フォーマット×ネタで投稿を量産し、post-reviewer サブエージェントが審査して予約キューへ
---

# 投稿の作成・レビュー・予約

作成本数: $ARGUMENTS（指定なしは 7 本）

## 1. 材料を選ぶ
- `data/config/account_profile.md`・`data/config/post_rules.md`・`data/config/power_words.md`・`data/config/ng_words.txt` を読む。
- 柱（account_profile.md 4章）の比率に合わせて本数を割り振る。`tags` には柱名を1つだけ入れる。
- `data/formats.json` から `status: active` の型を選ぶ。`rank` 上位を多めにしつつ、
  `n < 3` の型を全体の 2〜3 割混ぜる（評価が固まっていない型の検証枠）。
- `data/ideas.json` から `status: unused` のネタを `weight` の高い順に選ぶ。同じタグが3本以上続かないようにする。

## 1.5 外部知見を確かめる（研究員）
- `data/knowledge/research/*.md` と `data/knowledge/facts/*.json` を読み、選んだネタに使える事実カード（`status: verified / partial`）と「よくある誤解」を拾う。
- ネタに必要な数字・年・因果のうち、カードがないもの・`volatile: true` で `checked_at` が90日より古いものは、
  **domain-researcher サブエージェント**（Agent ツール、subagent_type: domain-researcher）に、確かめたい主張を箇条書きで渡して調べさせる。
  複数分野にまたがるときは分野ごとに並列で呼ぶ。
- `myth`（通説）のカードは「誤解をほどく」切り口として使ってよいが、通説の側を事実として書かない。

## 2. 下書きを書く
- **最優先は2秒ルール（post_rules.md B0）**：読者はライトユーザー。1行目20字以内・日常語・本文3〜4行80字以内。専門用語・規格名・単位つきの細かい数字は本文に出さず、返信と図解カードに回す。
  書いたら「テーマに興味のない友人がタイムラインで2秒見て止まるか」で読み直し、止まらなければ1行目を作り直す（1本につき1行目の案を3つ出して一番短く強いものを選ぶ）。
- 型の `structure` / `hook_pattern` / `length_guide` / `do` / `dont` に従う。
- 本文（`text`）は3〜4行で、答えの直前で止める。答えは `replies[0]`（コメント欄）の1行目で必ず回収する（C1）。各500字以内。
- 一次情報は account_profile.md 5章の「使ってよい」ものから1つ以上。体験を創作しない。
- 数字・年・規格・因果の主張は、事実カードで裏づけられるものだけを書き、その ID をキューの `evidence_ids` に入れる。
  `partial` のカードは、カードに書かれた条件ごと書く。出典（規格名・機関名）は返信の末尾に1行で示す。
- 一次情報（T1〜T4）＝「本人の視点・判断」、事実カード＝「その判断の裏づけ」。どちらか片方だけの投稿にしない。
- 強い言葉は power_words.md から選び、直近7投稿（`data/posted/`）で使った言葉は使わない。
- 1行目だけで続きを読みたくなるか、を最優先にする。

## 3. サブエージェントでレビュー
- 下書きを1本ずつ **post-reviewer サブエージェント** に渡す（Agent ツール、subagent_type: post-reviewer）。
  渡す情報: 本文・replies・format_id・tags・使った一次情報・idea の key_point と evidence・`evidence_ids` とその事実カードの中身。
- 判定が `revise` なら指摘に従って書き直し、再レビュー（最大2回）。それでも通らなければ `rejected` として保存しない。

## 4. 予約キューに保存
- 空き枠を取得: `python -m threads_auto next-slots --count <本数>`
- 1本ごとに `data/queue/<YYYYMMDD-HHMM>-<format_id>-<短い英字スラッグ>.json` を作る。形式は `data/queue/EXAMPLE.json.sample` を参照。
  - `review`: `{"status": "approved", "score": <点>, "reviewer": "post-reviewer", "notes": "<要約>", "human_approved": false}`
- **全投稿に図解カードを1枚付ける**（2026-10-07 ユーザー決定。写真風・AI生成の画像は使わない）。
  1. `cards/specs/<スラッグ>.json` を書き、`python tools/make_card.py cards/specs/<スラッグ>.json cards/out/<スラッグ>.png` で作る。
     絵（`swatches`・`visual`）を主役にし、文字は少なく（タイトル2行まで・項目は短い句で3つまで）。本文の要点と食い違わないこと。地名・人名・他人の写真は入れない。
  2. 作った画像を目で確認し、`data/config/brand.json` の `cards_repo`（公開リポジトリ）の `c/<スラッグ>.png` に置いて push する。
  3. キューの `image_url` に `<cards_base_url><スラッグ>.png` を入れ、URL が 200 を返すことを確かめる。
- **AI写真（2026-10-08 本人：無料の範囲で比較中のため、Gamma などクレジット・料金がかかる生成は本人の明示的な指示があるときだけ使う）**：1枚目にAIで作った写真風のイメージ、2枚目に図解カードの複数枚投稿にする（2026-10-08 本人決定）。
  1. Gamma の generate_image（type: photo, sizePreset: social-portrait）で作る。プロンプトに「no people, no text, no logos, no brand products, no windows with outside view」を入れる。1枚 70 クレジット消費なので、残りクレジットを報告に書く。
  2. 元画像を scratchpad に保存し、`python tools/make_photo.py <元画像> cards/out/<スラッグ>-photo.jpg` で整える（右下にハンドル名が入り、メタデータは消える。「AIで作った」の表示は付けない）。目で確認し、名作家具そっくり・不自然な物・窓の外の景色があれば使わない。
  3. カード置き場に置き、キューを `image_urls: [<写真のURL>, <図解のURL>]`・`ai_image: true` にする。本文・返信で「私の部屋」など自宅の写真だと言い切らない。
- 使ったネタの `ideas.json` の `status` を `used` にし、`used_in` にキューのファイル名を入れる。

## 5. 機械チェック
- `python -m threads_auto validate` を実行し、ERROR が 0 になるまで直す。

## 6. 報告
- 作成本数・予約日時・型の内訳・レビュー点数を表で示す。
- `settings.json` の `require_human_approval` が true の場合は、
  「内容を確認後 `python -m threads_auto approve --all`（または ID 指定）で承認し、コミット＆プッシュしてください」と伝える。
