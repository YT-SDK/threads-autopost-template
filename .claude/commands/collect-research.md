---
description: ステップ1 競合リサーチ — Threads で「いいね」した投稿を Claude in Chrome で収集し CSV に追記
---

# 競合リサーチの収集

前提: Chrome に Claude in Chrome 拡張が入り、Threads にログイン済み。参考にしたい投稿には日頃から「いいね」を付けておく。

## 手順

1. `data/research/liked_posts.csv` を読み、既存の `permalink` 一覧を把握する（重複追記しない）。
2. Claude in Chrome で Threads を開き、プロフィール → 設定 → アカウント →「いいね」一覧を表示する。
3. 上から順に、未収集の投稿を最大 $ARGUMENTS 件（指定がなければ 30 件）読み取る。各投稿について:
   - `author`（@ID）、`permalink`、`posted_at`（分かる範囲で）、`likes` / `replies` / `reposts`（表示値。「1.2万」は 12000 に変換）
   - `text`: 本文全文（改行は `\n` に置換）
   - `why_liked`: なぜ伸びたと考えるかを 1 行（フック・構成・テーマのどれが効いたか）
   - `format_id`: 空欄のまま（/build-formats で付与）
   - `collected_at`: 今日の日付
4. CSV に追記する。カンマ・改行・ダブルクォートを含むフィールドは正しくクォートする。
5. 最後に「追加件数 / 総件数 / 多かったテーマ上位3」を報告する。

## 注意

- 収集は自分の研究用途に限る。他人の投稿本文をそのまま転載・再投稿に使わない（型の抽出のみに使う）。
- ページ読み込みが遅い場合はスクロールして待つ。取得できない数値は空欄にし、推測で埋めない。
- Claude in Chrome が使えない場合は、ユーザーに CSV への手入力（本文と permalink だけでも可）を案内する。
