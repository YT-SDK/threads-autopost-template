#!/usr/bin/env python3
"""AIで作った写真風の画像を、投稿の1枚目用（1080x1350）に整える。

- 中央で切り抜いて 4:5 にそろえる
- 右下にハンドル名を入れる（「AIで作ったイメージ」の表示は --label のときだけ。2026-10-08 本人決定で既定は表示なし）
- 位置情報などのメタデータは保存しない

使い方: python tools/make_photo.py <元画像> <出力.jpg> [--label]
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_card import BG, FONT_MED, HANDLE, INK, font  # noqa: E402

W, H = 1080, 1350
LABEL = "AIで作ったイメージ"


def make(src: Path, out: Path, label: bool = False) -> None:
    im = Image.open(src).convert("RGB")
    scale = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    left, top = (im.width - W) // 2, (im.height - H) // 2
    im = im.crop((left, top, left + W, top + H))
    d = ImageDraw.Draw(im, "RGBA")
    f = font(FONT_MED, 30)
    pad = 18
    tags = ((LABEL, False), (HANDLE, True)) if label else ((HANDLE, True),)
    for text, x_right in tags:
        tw = d.textlength(text, font=f)
        x = W - 40 - tw - pad if x_right else 40
        y = H - 40 - 30 - pad
        d.rounded_rectangle([x - pad, y - pad + 4, x + tw + pad, y + 30 + pad], radius=14, fill=(*BG, 215))
        d.text((x, y), text, font=f, fill=INK)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, "JPEG", quality=90, optimize=True)  # EXIF などは付けない


if __name__ == "__main__":
    make(Path(sys.argv[1]), Path(sys.argv[2]), label="--label" in sys.argv[3:])
