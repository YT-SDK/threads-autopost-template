# 週2回の自動作成（Routine）の指示文

Claude Code の Routine（日・水 20:47 JST など）に、下の「指示文」をそのまま登録する。アカウント固有の値（カード置き場など）は設定ファイルから読むので、どのアカウントでも同じ文でよい。

## 指示文
定期の投稿作成と学習（週2回）。このリポジトリの作業ブランチで、origin/main を取り込んでから次を行う。
0. 学習：docs/learning/playbook.md（冒頭の学習ルールに従う）、data/learning.json、最新の data/reports/ を読む。前回の作成以降に評価対象になった投稿（公開24時間時点の eval_metrics）から、型・柱・時間帯・画像・1行目の作りごとの差を読み取り、「仮説→根拠（指数・本数）→次にやること」の形で playbook の「現在の教訓」を更新する（本数が少ないものは仮説と明記、判定は learning.json の decision に従う）。フォロワーの7日増減も確認する。時間帯（朝・昼・夜）が5本以上で「減らす」判定になったら、docs/strategy/posting-times.md を踏まえて枠の変更をユーザーに提案する（自分では変えない）。
1. CLAUDE.md、data/config/ の account_profile.md・post_rules.md（特に B0「2秒ルール」）・ng_words.txt・identity_terms.txt・brand.json・research_domains.json、data/formats.json、docs/strategy/、直近の data/posted/、data/knowledge/research/*.md を読む。
2. 次の作成日までの空き枠（settings.json の posting_slots / posting_slots_weekend）を python -m threads_auto next-slots で求め、その本数のネタを選ぶ。配分は 7割を学習の活用、3割を検証にする。研究ノートの「投稿の切り口」「よくある誤解」もネタ候補にする。
3. 外部知見：ネタに必要な数字・年・規格・因果のうち、data/knowledge/facts/*.json に verified / partial のカードがないもの（または volatile で90日より古いもの）を分野ごとにまとめ、domain-researcher サブエージェントを分野ごとに並列で呼んで調べさせる（.claude/commands/research.md の手順）。
4. /write-posts の手順で下書きを作る。最優先は2秒ルール（1行目20字以内・日常語・本文3〜4行80字以内、専門用語は返信で言い換えつき1回だけ）。本人から聞いていない体験・決定・金額は書かない。数値・規格を書いた投稿は evidence_ids にカードIDを入れ、出典名を返信の末尾に1行で示す。myth のカードの内容を事実として書かない。各投稿の review.notes に「検証：◯◯」または「活用：◯◯」を1行書く。
5. 1本ずつ post-reviewer サブエージェントで審査し（evidence_ids の事実カードも渡す）、80点以上だけキューに入れる（修正は最大2回、通らなければ捨てる）。
6. 全投稿に図解カードを1枚付ける：cards/specs/<名前>.json を書き、python3 tools/make_card.py で cards/out/<名前>.png を作り、目で確認してから brand.json の cards_repo（クローン先 cards_clone_dir、なければ add_repo で追加）の c/ に置いて main に push。<cards_base_url><名前>.png が200で取れることを確かめ、投稿の image_url に設定する。絵（visual や swatches）を主役にし、文字は少なく。カードに地名・人名・他人の写真は入れない。
7. playbook の変更履歴に今回の配分の方針を1行追記する。python -m threads_auto validate（ERROR 0。警告も残さない）と unittest を通し、PRを作って main にマージする。review.human_approved は変更しない。自動で変えてよいのは配分だけで、投稿ルール・書かないこと・NGワード・投稿本数や枠・承認設定は変えない（変えたい場合はユーザーに提案する）。
8. ユーザーへの報告：今回学んだこと、フォロワー数と7日増減、新たに調べた事実（件数と目玉）、作った本数・日程・1行目の一覧、活用／検証の内訳、落とした本数と理由を短く。
