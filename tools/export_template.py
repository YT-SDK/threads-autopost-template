#!/usr/bin/env python3
"""ひな形（エンジン＋空のテーマ設定）を書き出す。

使い方: python tools/export_template.py <出力先ディレクトリ>
出力先を YT-SDK/threads-autopost-template のクローンにして push すると、ひな形が更新される。
テーマ固有のファイル（data/ の中身・docs/strategy・cards など）は書き出さない。template/ の中身で上書きする。
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# エンジン：どのアカウントでも同じもの（docs/ops/sync-engine.md と合わせる）
ENGINE = [
    "threads_auto", "tests", "tools", "assets", ".github/workflows", ".claude/agents", ".claude/commands",
    "docs/token-setup.md", "docs/ops", "docs/strategy/posting-times.md", "README.md",
    "data/config/post_rules.md", "data/config/power_words.md", "data/config/settings.json",
    "data/queue/EXAMPLE.json.sample",
]
# 空で用意するもの
EMPTY_JSON = {"data/formats.json": [], "data/ideas.json": []}
KEEP_DIRS = ["data/queue", "data/posted", "data/metrics", "data/reports", "data/research",
             "data/knowledge/facts", "data/knowledge/research", "cards/specs", "cards/out"]
PLAYBOOK_RESET = "（まだデータが足りません。比べるのは各投稿の「公開24時間時点」の数値です。）"


def copy(rel: str, out: Path) -> None:
    src, dst = ROOT / rel, out / rel
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    elif src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for rel in ENGINE:
        copy(rel, out)
    # テーマ固有の上書き（空の設定・CLAUDE.md・/setup-account・手順書）
    shutil.copytree(ROOT / "template", out, dirs_exist_ok=True)
    # 新しいアカウントは人の承認から始める
    settings_path = out / "data/config/settings.json"
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    settings["require_human_approval"] = True
    settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for rel, value in EMPTY_JSON.items():
        (out / rel).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for rel in KEEP_DIRS:
        (out / rel).mkdir(parents=True, exist_ok=True)
        (out / rel / ".gitkeep").touch()
    # 投稿ルールの変更履歴はアカウント固有なので空にする
    rules = out / "data/config/post_rules.md"
    text = rules.read_text(encoding="utf-8").split("## 変更履歴")[0]
    rules.write_text(text.replace("（このアカウントではインテリアに詳しくない人）", "") + "## 変更履歴\n", encoding="utf-8")
    # 学習メモは「学習のルール」だけ残し、教訓と履歴を空にする
    playbook = (ROOT / "docs/learning/playbook.md").read_text(encoding="utf-8")
    head = playbook.split("## 現在の教訓")[0]
    (out / "docs/learning").mkdir(parents=True, exist_ok=True)
    (out / "docs/learning/playbook.md").write_text(
        head + "## 現在の教訓\n" + PLAYBOOK_RESET + "\n\n## 変更履歴\n", encoding="utf-8"
    )
    print(f"ひな形を {out} に書き出しました")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("使い方: python tools/export_template.py <出力先ディレクトリ>")
    main(Path(sys.argv[1]))
