# エンジンの改良を各アカウントに取り込む

## 役割分担
- **YT-SDK/Threads-** が本家。エンジンの改良はまずここで行い、テストを通す。
- `python tools/export_template.py <出力先>` で、エンジン＋空のテーマ設定を書き出し、**YT-SDK/threads-autopost-template** に push する。
- 各アカウントのリポジトリは、ひな形から作ったもの。改良を取り込むときは、下の「エンジンのファイル」だけをひな形からコピーする（テーマの設定・データには触れない）。

## エンジンのファイル（上書きしてよい）
`tools/export_template.py` の `ENGINE` に一覧がある：threads_auto/、tests/、tools/、assets/、.github/workflows/、.claude/agents/、.claude/commands/、docs/token-setup.md、docs/ops/、docs/strategy/posting-times.md

## テーマのファイル（上書きしない）
data/ 以下すべて（config・formats・ideas・knowledge・queue・posted・metrics など）、docs/strategy/（posting-times.md 以外）、docs/learning/playbook.md、cards/、CLAUDE.md

## 取り込み手順（Claude に「エンジンを最新にして」と頼めばよい）
1. ひな形リポジトリを取得し、ENGINE のファイルだけを各アカウントのリポジトリにコピーする。
2. `python -m unittest discover -s tests` と `python -m threads_auto validate` を通す。
3. PR を作って main にマージする。
