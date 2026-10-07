"""設定の読み込み。秘密情報は環境変数、運用パラメータは data/config/settings.json。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

DEFAULT_SETTINGS = {
    "timezone": "Asia/Tokyo",
    # 1日の投稿枠（ローカル時刻）。next-slots がこの枠に空きを割り当てる
    "posting_slots": ["07:30", "12:15", "20:30"],
    # 土日の投稿枠（任意）。未設定なら posting_slots を使う
    "posting_slots_weekend": [],
    # true の間は `approve` で人が承認した投稿しか公開しない
    "require_human_approval": True,
    # 1回の実行で公開する最大件数（Actions停止後の一斉放出を防ぐ）
    "max_posts_per_run": 1,
    # 直前の投稿からの最小間隔（分）
    "min_interval_minutes": 60,
    # 予定時刻からこの時間を過ぎた投稿は公開せず expired にする
    "expire_hours": 24,
    # 公開に失敗した投稿を failed にするまでの試行回数
    "max_attempts": 3,
    # 分析: 何日前までの投稿の数値を取得するか
    "insights_lookback_days": 14,
    # 分析: 投稿どうしを比べる時点（公開からの経過時間）。経過時間の差で古い投稿が有利にならないようにする
    "eval_age_hours": 24,
    # 分析: スコア集計の対象期間（日）
    "scoring_window_days": 14,
    # 分析: ベイズ平滑化の事前サンプル数（小標本の過大評価を抑える）
    "smoothing_k": 2,
    # レビュー合格ライン（post-reviewer が付ける 0-100 点）
    "review_pass_score": 80,
}


@dataclass
class Settings:
    data_dir: Path
    values: dict = field(default_factory=dict)

    def __getitem__(self, key):
        return self.values[key]

    def get(self, key, default=None):
        return self.values.get(key, default)

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.values["timezone"])


def load_settings(data_dir: str | Path | None = None) -> Settings:
    data_dir = Path(data_dir or os.environ.get("THREADS_DATA_DIR", "data"))
    values = dict(DEFAULT_SETTINGS)
    path = data_dir / "config" / "settings.json"
    if path.exists():
        values.update(json.loads(path.read_text(encoding="utf-8")))
    return Settings(data_dir=data_dir, values=values)


def env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"環境変数 {name} が未設定です（.env.example / README を参照）")
    return value
