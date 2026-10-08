#!/usr/bin/env python3
"""Claude がコードで描くイラストの1枚目（1080x1350）。写真の代わりに、部屋の雰囲気を見せる。

外部の画像生成サービスを使わないので費用がかからない。描けるのは平面的なイラストで、写真のような質感は出ない。
spec の例: {"time": "night", "items": ["pendant", "sideboard", "lamp", "sofa", "rug", "plant"], "wall": "#EFE6D6"}
使い方: python tools/make_scene.py <spec.json> <出力.png>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_card import FONT_MED, HANDLE, font, glow, hex2rgb  # noqa: E402

W, H = 1080, 1350
WALNUT = (110, 70, 40)
WALNUT_D = (84, 52, 30)
IVORY = (236, 228, 212)
WARM = (255, 196, 120)


def draw_scene(spec: dict) -> Image.Image:
    night = spec.get("time", "night") == "night"
    wall = hex2rgb(spec.get("wall", "#E9DFCC" if not night else "#B9A88F"))
    floor_c = hex2rgb(spec.get("floor", "#A4553A"))
    img = Image.new("RGB", (W, H), wall)
    d = ImageDraw.Draw(img)
    floor_y = 980
    # 床（テラコッタのタイル）
    d.rectangle([0, floor_y, W, H], fill=floor_c)
    for x in range(-200, W + 200, 120):
        d.line([x, floor_y, x + (x - W / 2) * 0.6, H], fill=tuple(max(c - 25, 0) for c in floor_c), width=3)
    for i, y in enumerate([floor_y + 40, floor_y + 100, floor_y + 180, floor_y + 280]):
        d.line([0, y, W, y], fill=tuple(max(c - 25, 0) for c in floor_c), width=3)
    d.line([0, floor_y, W, floor_y], fill=WALNUT_D, width=6)
    items = spec.get("items", [])
    lights = []
    if "pendant" in items:
        lights.append((640, 420, 230))
    if "lamp" in items:
        lights.append((230, 640, 200))
    if "sconce" in items:
        lights.append((900, 520, 170))
    if night:  # 夜は部屋全体を少し暗くして、灯りのまわりだけ明るく
        shade = Image.new("RGB", (W, H), (40, 28, 20))
        img = Image.blend(img, shade, 0.35)
    for x, y, r in lights:
        glow(img, x, y, r, WARM, 170 if night else 90)
    d = ImageDraw.Draw(img)
    if "rug" in items:
        d.ellipse([200, 1040, 900, 1240], fill=(226, 212, 186))
        d.ellipse([240, 1065, 860, 1215], outline=(206, 190, 160), width=4)
    if "sideboard" in items:
        d.rounded_rectangle([90, 730, 470, 900], radius=10, fill=WALNUT)
        d.line([280, 740, 280, 890], fill=WALNUT_D, width=4)
        for lx in (120, 440):
            d.line([lx, 900, lx + (8 if lx > 200 else -8), floor_y + 10], fill=WALNUT_D, width=9)
    if "lamp" in items:
        d.line([230, 730, 230, 650], fill=(180, 150, 90), width=6)
        d.ellipse([200, 722, 260, 736], fill=(180, 150, 90))
        d.pieslice([170, 590, 290, 700], 180, 360, fill=(250, 238, 214))
    if "vases" in items:
        d.rounded_rectangle([330, 640, 370, 730], radius=16, fill=(201, 162, 39))
        d.ellipse([380, 670, 430, 730], fill=(110, 120, 60))
    if "pendant" in items:
        d.line([640, 0, 640, 330], fill=(60, 50, 40), width=3)
        d.ellipse([560, 330, 720, 490], fill=(253, 244, 226), outline=(200, 180, 150), width=3)
        for k in range(1, 7):
            y = 330 + k * 160 // 7
            half = int(80 * (1 - ((y - 410) / 80) ** 2) ** 0.5)
            d.line([640 - half, y, 640 + half, y], fill=(220, 200, 170), width=2)
    if "sconce" in items:
        d.rectangle([960, 500, 972, 560], fill=WALNUT)
        d.ellipse([890, 495, 950, 555], fill=(253, 244, 226), outline=(200, 180, 150), width=3)
    if "sofa" in items:
        d.rounded_rectangle([560, 790, 1020, 900], radius=40, fill=IVORY)
        d.rounded_rectangle([540, 860, 1040, 960], radius=40, fill=(244, 238, 226))
        for lx in (590, 1000):
            d.line([lx, 960, lx, floor_y + 12], fill=WALNUT_D, width=8)
    if "table" in items:
        d.ellipse([560, 990, 820, 1040], fill=WALNUT)
        for lx in (600, 780):
            d.line([lx, 1020, lx + (10 if lx > 690 else -10), 1130], fill=WALNUT_D, width=8)
    if "plant" in items:
        d.rounded_rectangle([60, 900, 130, 980], radius=12, fill=(190, 110, 70))
        for ang, ln in ((-0.6, 160), (-0.2, 200), (0.3, 170), (0.7, 140)):
            import math
            x2, y2 = 95 + math.sin(ang) * ln, 900 - math.cos(ang) * ln
            d.line([95, 900, x2, y2], fill=(70, 100, 60), width=5)
            d.ellipse([x2 - 26, y2 - 16, x2 + 26, y2 + 16], fill=(90, 125, 75))
    img = img.filter(ImageFilter.SMOOTH)
    d = ImageDraw.Draw(img, "RGBA")
    f = font(FONT_MED, 30)
    tw = d.textlength(HANDLE, font=f)
    d.rounded_rectangle([W - 58 - tw - 18, H - 98, W - 40, H - 40], radius=14, fill=(246, 241, 231, 215))
    d.text((W - 58 - tw, H - 88), HANDLE, font=f, fill=(59, 47, 42))
    return img


if __name__ == "__main__":
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = Path(sys.argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)
    draw_scene(spec).save(out, "PNG", optimize=True)
