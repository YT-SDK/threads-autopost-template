"""データ置き場（リポジトリ内の JSON/CSV）。GitHub Actions がコミットして状態を保持する。

data/
  research/liked_posts.csv   ステップ1: 競合リサーチ
  formats.json               ステップ2: バズフォーマット（型）
  knowledge/                 ステップ3: Discord 等から集めたナレッジ
  ideas.json                 ステップ3: ネタ帳
  queue/<id>.json            ステップ4: レビュー済み予約投稿
  posted/<id>.json           ステップ5: 公開済み（media id / 指標）
  metrics/history.jsonl      ステップ6: 指標スナップショット
  weights.json, reports/     ステップ7: ランキング・重み・週次レポート
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def parse_time(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"タイムゾーン付きで指定してください: {value}")
    return dt


class Store:
    def __init__(self, data_dir: Path):
        self.root = Path(data_dir)

    @property
    def queue_dir(self) -> Path:
        return self.root / "queue"

    @property
    def posted_dir(self) -> Path:
        return self.root / "posted"

    def _load_dir(self, d: Path) -> list[tuple[Path, dict]]:
        if not d.exists():
            return []
        return [(p, read_json(p, {})) for p in sorted(d.glob("*.json"))]

    def queue(self) -> list[tuple[Path, dict]]:
        return self._load_dir(self.queue_dir)

    def posted(self) -> list[tuple[Path, dict]]:
        return self._load_dir(self.posted_dir)

    def save(self, path: Path, item: dict) -> None:
        write_json(path, item)

    def move_to_posted(self, path: Path, item: dict) -> Path:
        dest = self.posted_dir / path.name
        write_json(dest, item)
        path.unlink()
        return dest

    def formats(self) -> list[dict]:
        return read_json(self.root / "formats.json", [])

    def save_formats(self, formats: list[dict]) -> None:
        write_json(self.root / "formats.json", formats)

    def ideas(self) -> list[dict]:
        return read_json(self.root / "ideas.json", [])

    def save_ideas(self, ideas: list[dict]) -> None:
        write_json(self.root / "ideas.json", ideas)

    def ng_words(self) -> list[str]:
        path = self.root / "config" / "ng_words.txt"
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()
        return [w.strip() for w in lines if w.strip() and not w.startswith("#")]

    def identity_terms(self) -> dict[str, str]:
        """経歴の要素ごとの正規表現（1行1要素「ラベル: 正規表現」）。2要素以上が同じ投稿に出たら身バレのおそれ。"""
        path = self.root / "config" / "identity_terms.txt"
        if not path.exists():
            return {}
        terms = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            label, pattern = line.split(":", 1)
            terms[label.strip()] = pattern.strip()
        return terms

    def facts(self) -> dict[str, dict]:
        """研究員エージェントが集めた事実カード（data/knowledge/facts/*.json）を ID で引けるようにする。"""
        cards: dict[str, dict] = {}
        for path in sorted((self.root / "knowledge" / "facts").glob("*.json")):
            for card in read_json(path, []):
                if isinstance(card, dict) and card.get("id"):
                    cards[card["id"]] = card
        return cards
