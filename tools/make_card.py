#!/usr/bin/env python3
"""図解カード（1080x1350・4:5）を作る。投稿の1枚目の画像に使う。

Pillow が必要（threads_auto 本体は標準ライブラリのみ。このスクリプトは手元・セッション内でだけ使う）。
フォント: assets/fonts/ZenMaruGothic（SIL Open Font License）

使い方:
  python tools/make_card.py cards/spec.json out.png

spec.json の形:
  {"kind": "table", "title": "...", "subtitle": "...", "columns": ["呼び方", "範囲"],
   "rows": [["電球色", "2600〜3250K"], ...], "highlight": 0, "note": "出典: JIS Z 9112"}
  {"kind": "list", "title": "...", "subtitle": "...",
   "items": [["見出し", "説明"], ...], "note": "..."}
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FONT_MED = ROOT / "assets/fonts/ZenMaruGothic-Medium.ttf"
FONT_BOLD = ROOT / "assets/fonts/ZenMaruGothic-Bold.ttf"

W, H = 1080, 1350
MARGIN = 84

def _hex(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# アカウントごとの見た目は data/config/brand.json（名前・ハンドル・色）。ないときは下の既定値
BRAND = json.loads((ROOT / "data/config/brand.json").read_text(encoding="utf-8")) if (ROOT / "data/config/brand.json").exists() else {}
_P = {"bg": "#F6F1E7", "ink": "#3B2F2A", "sub": "#7A685C", "accent": "#7A4E2D", "accent2": "#C9A227", "line": "#DCD1BE"}
_P.update(BRAND.get("palette", {}))
BG = _hex(_P["bg"])            # 背景
INK = _hex(_P["ink"])          # 文字
SUB = _hex(_P["sub"])          # 補足の文字
WALNUT = _hex(_P["accent"])    # 強調色（番号・線）
MUSTARD = _hex(_P["accent2"])  # 第2強調色（表のハイライト）
LINE = _hex(_P["line"])        # 罫線
ACCOUNT_NAME = BRAND.get("account_name", "")
HANDLE = BRAND.get("handle", "")


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def wrap(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont, width: int) -> list[str]:
    """日本語を1文字単位で折り返す。"""
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        if draw.textlength(cur + ch, font=f) > width and cur:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def draw_lines(draw, xy, lines, f, fill, gap=1.35):
    x, y = xy
    for line in lines:
        draw.text((x, y), line, font=f, fill=fill)
        y += int(f.size * gap)
    return y


def hex2rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def glow(img: Image.Image, cx: int, cy: int, r: int, color, strength: int = 150) -> None:
    """光のにじみ（ぼかした円を重ねる）。"""
    layer = Image.new("RGBA", img.size, (*color, 0))  # 透明部分も同じ色にして、ぼかしの縁が黒ずまないようにする
    ImageDraw.Draw(layer).ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*color, strength))
    layer = layer.filter(ImageFilter.GaussianBlur(r * 0.45))
    img.paste(Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB"))


def badge(draw: ImageDraw.ImageDraw, cx: int, cy: int, n: int, r: int = 26) -> None:
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WALNUT)
    f = font(FONT_BOLD, int(r * 1.15))
    t = str(n)
    draw.text((cx - draw.textlength(t, font=f) / 2, cy - r * 0.78), t, font=f, fill=BG)


def visual_room(img: Image.Image, top: int, height: int) -> None:
    """部屋の断面：①テーブル上のペンダント ②角のフロアランプ ③壁のブラケット。"""
    d = ImageDraw.Draw(img)
    x0, x1 = MARGIN, W - MARGIN
    ceil, floor = top + 20, top + height - 30
    warm = (255, 196, 120)
    # 光（先に描いて、上から家具を重ねる）
    glow(img, 560, floor - 120, 150, warm, 140)      # ペンダントの下
    glow(img, 190, floor - 150, 120, warm, 130)      # フロアランプ
    glow(img, 900, top + height // 2 - 10, 110, warm, 120)  # 壁
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([x0, ceil, x1, floor], radius=24, outline=LINE, width=4)
    d.line([x0, floor, x1, floor], fill=WALNUT, width=8)
    # ① テーブルとペンダント
    d.line([560, ceil, 560, floor - 205], fill=INK, width=3)
    d.ellipse([505, floor - 215, 615, floor - 150], fill=(250, 238, 214), outline=SUB, width=3)
    for k in range(3):
        y = floor - 200 + k * 16
        d.line([512, y, 608, y], fill=LINE, width=2)
    d.rounded_rectangle([420, floor - 80, 700, floor - 66], radius=6, fill=WALNUT)
    d.line([450, floor - 66, 450, floor], fill=WALNUT, width=8)
    d.line([670, floor - 66, 670, floor], fill=WALNUT, width=8)
    badge(d, 640, floor - 240, 1)
    # ② 角のフロアランプ（キノコ型）
    d.line([190, floor - 150, 190, floor], fill=INK, width=5)
    d.ellipse([160, floor - 8, 220, floor + 4], fill=INK)
    d.pieslice([130, floor - 230, 250, floor - 110], 180, 360, fill=(250, 238, 214), outline=SUB, width=3)
    badge(d, 270, floor - 230, 2)
    # ③ 壁のブラケット
    by = top + height // 2 - 10
    d.rectangle([x1 - 30, by - 30, x1 - 18, by + 30], fill=WALNUT)
    d.line([x1 - 30, by, x1 - 70, by], fill=INK, width=4)
    d.ellipse([x1 - 105, by - 32, x1 - 45, by + 28], fill=(250, 238, 214), outline=SUB, width=3)
    badge(d, x1 - 140, by - 60, 3)
    # 消した天井灯
    d.ellipse([x0 + (x1 - x0) // 2 - 60 + 200, ceil - 4, x0 + (x1 - x0) // 2 + 60 + 200, ceil + 26], outline=LINE, width=3)
    f = font(FONT_MED, 24)
    d.text((x0 + (x1 - x0) // 2 + 150, ceil + 34), "天井の照明はOFF", font=f, fill=SUB)


def visual_compare(img: Image.Image, top: int, height: int) -> None:
    """同じ木とトマトを Ra80台 / Ra90以上 で並べたイメージ。"""
    d = ImageDraw.Draw(img)
    gap = 36
    pw = (W - 2 * MARGIN - gap) // 2
    panels = [
        ("Ra 80台", (120, 92, 70), (176, 92, 80), (210, 205, 190)),
        ("Ra 90以上", (110, 66, 36), (214, 58, 40), (252, 236, 208)),
    ]
    fl = font(FONT_BOLD, 34)
    for i, (label, wood, tomato, light) in enumerate(panels):
        x = MARGIN + i * (pw + gap)
        d.rounded_rectangle([x, top, x + pw, top + height], radius=24, fill=light)
        d.text((x + 28, top + 22), label, font=fl, fill=INK)
        # 木の板（木目）
        bx0, by0, bx1, by1 = x + 40, top + 90, x + pw - 40, top + height - 110
        d.rounded_rectangle([bx0, by0, bx1, by1], radius=14, fill=wood)
        grain = tuple(max(c - 26, 0) for c in wood)
        for k in range(1, 6):
            y = by0 + k * (by1 - by0) // 6
            pts = [(xx, y + int(6 * ((xx - bx0) / (bx1 - bx0) - 0.5) ** 2 * 8)) for xx in range(bx0 + 14, bx1 - 14, 12)]
            d.line(pts, fill=grain, width=3)
        # トマト
        cx, cy, r = bx0 + (bx1 - bx0) // 2, by1 - 10, 58
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=tomato)
        d.polygon([(cx - 18, cy - r + 4), (cx, cy - r - 16), (cx + 18, cy - r + 4)], fill=(70, 110, 60))
    d.text((MARGIN, top + height + 12), "※見え方のイメージです", font=font(FONT_MED, 24), fill=SUB)


def visual_grout(img: Image.Image, top: int, height: int) -> None:
    """白い50角タイルを「白目地・昼光色」と「グレー目地＋明るい木＋電球色」で並べたイメージ。"""
    d = ImageDraw.Draw(img)
    gap = 36
    pw = (W - 2 * MARGIN - gap) // 2
    panels = [
        ("白目地・昼光色", (236, 240, 246), (244, 247, 252), (238, 242, 248), None),
        ("グレー目地＋木＋電球色", (252, 236, 208), (250, 244, 232), (176, 170, 160), (214, 160, 112)),
    ]
    fl = font(FONT_BOLD, 30)
    for i, (label, light, tile, grout, wood) in enumerate(panels):
        x = MARGIN + i * (pw + gap)
        d.rounded_rectangle([x, top, x + pw, top + height], radius=24, fill=light)
        d.text((x + 28, top + 22), label, font=fl, fill=INK)
        # タイル面（目地の格子）
        tx0, ty0, tx1 = x + 40, top + 84, x + pw - 40
        ty1 = top + height - (96 if wood else 40)
        cell, line = 38, 4
        tx1 = tx0 + (tx1 - tx0) // cell * cell  # 端のタイルが欠けないよう、マス目の倍数にそろえる
        ty1 = ty0 + (ty1 - ty0) // cell * cell
        d.rectangle([tx0, ty0, tx1, ty1], fill=grout)
        yy = ty0
        while yy < ty1:
            xx = tx0
            while xx < tx1:
                d.rectangle([xx + line // 2, yy + line // 2, xx + cell - line // 2, yy + cell - line // 2], fill=tile)
                xx += cell
            yy += cell
        if wood:  # 洗面台の扉・棚板の明るい木
            d.rounded_rectangle([tx0, ty1 + 6, tx1, top + height - 40], radius=8, fill=wood)
            for k in range(1, 3):
                y = ty1 + 6 + k * (top + height - 46 - ty1) // 3
                d.line([tx0 + 14, y, tx1 - 14, y], fill=tuple(c - 22 for c in wood), width=2)
    d.text((MARGIN, top + height + 12), "※見え方のイメージです", font=font(FONT_MED, 24), fill=SUB)


VISUALS = {"room": visual_room, "compare": visual_compare, "grout": visual_grout}


def header(draw: ImageDraw.ImageDraw, spec: dict) -> int:
    y = MARGIN
    draw.rectangle([MARGIN, y, MARGIN + 72, y + 10], fill=WALNUT)
    y += 40
    y = draw_lines(draw, (MARGIN, y), wrap(draw, spec["title"], font(FONT_BOLD, 64), W - 2 * MARGIN), font(FONT_BOLD, 64), INK, 1.3)
    if spec.get("subtitle"):
        y += 10
        y = draw_lines(draw, (MARGIN, y), wrap(draw, spec["subtitle"], font(FONT_MED, 34), W - 2 * MARGIN), font(FONT_MED, 34), SUB)
    return y + 40


def footer(draw: ImageDraw.ImageDraw, spec: dict) -> None:
    f = font(FONT_MED, 26)
    y = H - MARGIN - 30
    if spec.get("note"):
        draw.text((MARGIN, y - 44), spec["note"], font=f, fill=SUB)
    draw.line([MARGIN, y - 4, W - MARGIN, y - 4], fill=LINE, width=2)
    draw.text((MARGIN, y + 10), ACCOUNT_NAME, font=f, fill=SUB)
    tw = draw.textlength(HANDLE, font=f)
    draw.text((W - MARGIN - tw, y + 10), HANDLE, font=f, fill=SUB)


def table(spec: dict) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    y = header(d, spec)
    cols = spec["columns"]
    rows = spec["rows"]
    fh, fb = font(FONT_MED, 30), font(FONT_BOLD, 42)
    widths = spec.get("widths") or [0.42, 0.58]
    xs = [MARGIN]
    for w in widths[:-1]:
        xs.append(xs[-1] + int((W - 2 * MARGIN) * w))
    for x, c in zip(xs, cols):
        d.text((x + 20, y), c, font=fh, fill=SUB)
    y += 56
    avail = H - MARGIN - 140 - y
    row_h = min(130, avail // max(len(rows), 1))
    for i, row in enumerate(rows):
        top = y + i * row_h
        if i == spec.get("highlight"):
            d.rounded_rectangle([MARGIN, top + 6, W - MARGIN, top + row_h - 6], radius=18, fill=(236, 222, 196))
            d.rectangle([MARGIN, top + 6, MARGIN + 10, top + row_h - 6], fill=MUSTARD)
        else:
            d.line([MARGIN, top + row_h - 1, W - MARGIN, top + row_h - 1], fill=LINE, width=2)
        sw = (spec.get("swatches") or [None] * len(rows))[i]
        pad = 0
        if sw:
            cy, r = top + row_h // 2, 30
            col = hex2rgb(sw)
            glow(img, MARGIN + 66, cy, r + 26, col, 200)
            d = ImageDraw.Draw(img)
            d.ellipse([MARGIN + 66 - r, cy - r, MARGIN + 66 + r, cy + r], fill=col, outline=LINE, width=2)
            pad = 90
        for j, (x, cell) in enumerate(zip(xs, row)):
            f = fb if j == 0 else font(FONT_MED, 38)
            d.text((x + 28 + (pad if j == 0 else 0), top + (row_h - f.size) // 2 - 4), cell, font=f, fill=INK if j == 0 else WALNUT)
    footer(d, spec)
    return img


def listing(spec: dict) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    y = header(d, spec)
    if spec.get("visual"):
        vh = spec.get("visual_height", 400)
        VISUALS[spec["visual"]](img, y - 10, vh)
        d = ImageDraw.Draw(img)
        y += vh + 40
    items = spec["items"]
    compact = bool(spec.get("visual"))
    fn, fh, fb = font(FONT_BOLD, 40), font(FONT_BOLD, 38 if compact else 44), font(FONT_MED, 28 if compact else 34)
    avail = H - MARGIN - 140 - y
    block = avail // max(len(items), 1)
    for i, (head, body) in enumerate(items):
        top = y + i * block
        cx, cy, r = MARGIN + 34, top + 34, 34
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WALNUT)
        num = str(i + 1)
        d.text((cx - d.textlength(num, font=fn) / 2, cy - 24), num, font=fn, fill=BG)
        tx = MARGIN + 100
        ty = draw_lines(d, (tx, top + 6), wrap(d, head, fh, W - MARGIN - tx), fh, INK, 1.25)
        draw_lines(d, (tx, ty + 6), wrap(d, body, fb, W - MARGIN - tx), fb, SUB, 1.4)
    footer(d, spec)
    return img


def make(spec: dict, out: Path) -> None:
    img = {"table": table, "list": listing}[spec["kind"]](spec)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG", optimize=True)  # 位置情報などのメタデータは含めない


if __name__ == "__main__":
    make(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")), Path(sys.argv[2]))
