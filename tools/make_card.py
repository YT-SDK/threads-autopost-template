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


def visual_room(img: Image.Image, top: int, height: int, spec: dict | None = None) -> None:
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


def visual_compare(img: Image.Image, top: int, height: int, spec: dict | None = None) -> None:
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


def visual_grout(img: Image.Image, top: int, height: int, spec: dict | None = None) -> None:
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


def caption(d: ImageDraw.ImageDraw, top: int, height: int, spec: dict | None) -> None:
    text = (spec or {}).get("visual_note")
    if text:
        d.text((MARGIN, top + height + 12), text, font=font(FONT_MED, 24), fill=SUB)


def visual_bars(img: Image.Image, top: int, height: int, spec: dict | None = None) -> None:
    """横棒グラフ。spec["bars"] = [[ラベル, 値, "表示する値"], ...]、"bar_highlight" で強調する行。"""
    d = ImageDraw.Draw(img)
    bars = spec["bars"]
    vmax = max(b[1] for b in bars) or 1
    fl, fv = font(FONT_BOLD, 34), font(FONT_BOLD, 34)
    label_w = max(d.textlength(b[0], font=fl) for b in bars) + 30
    x0, x1 = MARGIN + label_w, W - MARGIN - 150
    row = height // len(bars)
    for i, (label, value, shown) in enumerate(bars):
        cy = top + i * row + row // 2
        hi = i == spec.get("bar_highlight")
        d.text((MARGIN, cy - 22), label, font=fl, fill=INK)
        w = int((x1 - x0) * value / vmax)
        d.rounded_rectangle([x0, cy - 26, x0 + max(w, 12), cy + 26], radius=12, fill=MUSTARD if hi else WALNUT)
        d.text((x0 + max(w, 12) + 16, cy - 22), shown, font=fv, fill=WALNUT)
    caption(d, top, height, spec)


def visual_pairs(img: Image.Image, top: int, height: int, spec: dict | None = None) -> None:
    """色の変化の見本。spec["pairs"] = [[ラベル, 前の色, 後の色, 前の説明, 後の説明], ...]"""
    d = ImageDraw.Draw(img)
    pairs = spec["pairs"]
    row = height // len(pairs)
    fl, fs = font(FONT_BOLD, 36), font(FONT_MED, 26)
    sw_w = 300
    for i, (label, c0, c1, t0, t1) in enumerate(pairs):
        y = top + i * row + 10
        d.text((MARGIN, y), label, font=fl, fill=INK)
        by = y + 54
        bh = row - 110
        x_a = MARGIN
        x_b = W - MARGIN - sw_w
        for x, c, t in ((x_a, c0, t0), (x_b, c1, t1)):
            col = hex2rgb(c)
            d.rounded_rectangle([x, by, x + sw_w, by + bh], radius=14, fill=col)
            grain = tuple(max(v - 22, 0) for v in col)
            for k in range(1, 4):
                gy = by + k * bh // 4
                d.line([x + 16, gy, x + sw_w - 16, gy + 4], fill=grain, width=3)
            d.text((x, by + bh + 8), t, font=fs, fill=SUB)
        ax = (x_a + sw_w + x_b) // 2
        d.line([x_a + sw_w + 30, by + bh // 2, x_b - 30, by + bh // 2], fill=SUB, width=4)
        d.polygon([(x_b - 30, by + bh // 2 - 14), (x_b - 6, by + bh // 2), (x_b - 30, by + bh // 2 + 14)], fill=SUB)
        del ax
    caption(d, top, height, spec)


def visual_timeline(img: Image.Image, top: int, height: int, spec: dict | None = None) -> None:
    """年表。spec["events"] = [[年, 説明], ...]"""
    d = ImageDraw.Draw(img)
    ev = spec["events"]
    y = top + height // 2 - 20
    d.line([MARGIN, y, W - MARGIN, y], fill=LINE, width=6)
    fy, ft = font(FONT_BOLD, 44), font(FONT_MED, 28)
    step = (W - 2 * MARGIN) // len(ev)
    for i, (year, text) in enumerate(ev):
        cx = MARGIN + step * i + step // 2
        hi = i == spec.get("event_highlight")
        r = 18 if hi else 12
        d.ellipse([cx - r, y - r, cx + r, y + r], fill=MUSTARD if hi else WALNUT)
        tw = d.textlength(year, font=fy)
        d.text((cx - tw / 2, y - 90), year, font=fy, fill=WALNUT if not hi else INK)
        lines = wrap(d, text, ft, step - 20)
        ty = y + 34
        for ln in lines:
            d.text((cx - d.textlength(ln, font=ft) / 2, ty), ln, font=ft, fill=INK)
            ty += 40
    caption(d, top, height, spec)


def visual_versus(img: Image.Image, top: int, height: int, spec: dict | None = None) -> None:
    """2つを並べて比べる。spec["sides"] = [{"title":..., "lines":[...], "tone":"good|bad|plain"}, ...]"""
    d = ImageDraw.Draw(img)
    gap = 36
    pw = (W - 2 * MARGIN - gap) // 2
    tones = {"good": (252, 236, 208), "bad": (226, 222, 214), "plain": (240, 232, 218)}
    ft, fl = font(FONT_BOLD, 38), font(FONT_MED, 30)
    for i, side in enumerate(spec["sides"]):
        x = MARGIN + i * (pw + gap)
        d.rounded_rectangle([x, top, x + pw, top + height], radius=24, fill=tones.get(side.get("tone", "plain")))
        ty = draw_lines(d, (x + 28, top + 26), wrap(d, side["title"], ft, pw - 56), ft, INK, 1.25)
        d.line([x + 28, ty + 8, x + pw - 28, ty + 8], fill=LINE, width=3)
        ly = ty + 30
        for line in side["lines"]:
            ly = draw_lines(d, (x + 28, ly), wrap(d, "・" + line, fl, pw - 56), fl, SUB, 1.35) + 8
    caption(d, top, height, spec)


def visual_area(img: Image.Image, top: int, height: int, spec: dict | None = None) -> None:
    """小さな色見本と、同じ色の大きな壁。spec["color"] は見本の色、spec["wall_color"] は壁で見える色。"""
    d = ImageDraw.Draw(img)
    base = hex2rgb(spec["color"])
    wall = hex2rgb(spec.get("wall_color", spec["color"]))
    f = font(FONT_BOLD, 32)
    # 色見本
    sx, sy = MARGIN + 30, top + height // 2 - 60
    d.rounded_rectangle([sx - 18, sy - 70, sx + 170, sy + 190], radius=14, fill=(255, 255, 255), outline=LINE, width=3)
    d.rectangle([sx, sy - 50, sx + 152, sy + 102], fill=base)
    d.text((sx, sy + 120), "色見本", font=f, fill=INK)
    # 壁（部屋の奥の面）
    x0, x1 = MARGIN + 300, W - MARGIN
    d.polygon([(x0, top), (x1, top), (x1, top + height - 40), (x0, top + height - 40)], fill=wall)
    d.rectangle([x0, top + height - 40, x1, top + height], fill=(214, 196, 168))
    d.rounded_rectangle([x0 + 160, top + height - 150, x0 + 470, top + height - 60], radius=18, fill=(244, 236, 220))
    d.text((x0 + 24, top + 20), "同じ色を壁一面に", font=f, fill=INK)
    caption(d, top, height, spec)


def visual_chair(img: Image.Image, top: int, height: int, spec: dict | None = None) -> None:
    """横から見たテーブルと椅子。天板と座面の差を矢印で示す。spec["gap_label"]"""
    d = ImageDraw.Draw(img)
    floor = top + height - 30
    d.line([MARGIN, floor, W - MARGIN, floor], fill=WALNUT, width=6)
    # テーブル
    tt = floor - 250
    d.rounded_rectangle([MARGIN + 380, tt, W - MARGIN - 40, tt + 18], radius=6, fill=WALNUT)
    for lx in (MARGIN + 420, W - MARGIN - 80):
        d.line([lx, tt + 18, lx, floor], fill=WALNUT, width=10)
    # 椅子（座面・背もたれ・細い脚）
    seat = floor - 150
    cx0, cx1 = MARGIN + 140, MARGIN + 330
    d.rounded_rectangle([cx0, seat, cx1, seat + 16], radius=6, fill=INK)
    d.line([cx0 + 10, seat - 170, cx0 + 24, seat], fill=INK, width=10)
    for lx in (cx0 + 20, cx1 - 20):
        d.line([lx, seat + 16, lx, floor], fill=INK, width=6)
    # 矢印（座面の高さ〜天板の高さ）
    ax = MARGIN + 365
    d.line([cx1, seat, ax + 40, seat], fill=LINE, width=3)
    d.line([ax, tt + 4, ax, seat], fill=MUSTARD, width=6)
    for yy, s in ((tt + 4, 1), (seat, -1)):
        d.polygon([(ax - 14, yy + 18 * s), (ax, yy), (ax + 14, yy + 18 * s)], fill=MUSTARD)
    label = spec.get("gap_label", "")
    f = font(FONT_BOLD, 44)
    lx = (MARGIN + 420 + W - MARGIN - 80) // 2 - d.textlength(label, font=f) / 2  # テーブルの下、脚の間
    d.text((lx, (tt + seat) // 2 - 10), label, font=f, fill=INK)
    d.line([ax + 10, (tt + seat) // 2 + 14, lx - 14, (tt + seat) // 2 + 14], fill=MUSTARD, width=3)
    caption(d, top, height, spec)


def visual_lantern(img: Image.Image, top: int, height: int, spec: dict | None = None) -> None:
    """骨が規則正しい提灯と、不規則な骨の和紙のあかり。"""
    import random
    d = ImageDraw.Draw(img)
    gap = 36
    pw = (W - 2 * MARGIN - gap) // 2
    labels = spec.get("labels", ["規則正しい骨", "不規則な骨"])
    f = font(FONT_BOLD, 32)
    for i in range(2):
        x = MARGIN + i * (pw + gap)
        d.rounded_rectangle([x, top, x + pw, top + height], radius=24, fill=(240, 232, 218))
        cx, cy = x + pw // 2, top + height // 2 - 10
        rx, ry = 110, 128
        glow(img, cx, cy, 170, (255, 200, 130), 150)
        d = ImageDraw.Draw(img)
        d.line([cx, top + 20, cx, cy - ry], fill=INK, width=3)
        d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=(253, 244, 226), outline=SUB, width=3)
        rnd = random.Random(7)
        for k in range(1, 9):
            if i == 0:
                yy = cy - ry + k * (2 * ry) // 9
                off = 0
            else:
                yy = cy - ry + k * (2 * ry) // 9 + rnd.randint(-14, 14)
                off = rnd.randint(-18, 18)
            dy = yy - cy
            half = int(rx * (1 - (dy / ry) ** 2) ** 0.5) if abs(dy) < ry else 0
            d.line([cx - half, yy - off // 2, cx + half, yy + off // 2], fill=SUB, width=2)
        d.text((x + 24, top + height - 54), labels[i], font=f, fill=INK)
    caption(d, top, height, spec)


def visual_rug(img: Image.Image, top: int, height: int, spec: dict | None = None) -> None:
    """上から見たダイニング。テーブルの周りにラグの余白（spec["margin_label"]）。"""
    d = ImageDraw.Draw(img)
    cx = W // 2
    rug_w, rug_h = 720, height - 40
    rx0, ry0 = cx - rug_w // 2, top + 10
    d.rounded_rectangle([rx0, ry0, rx0 + rug_w, ry0 + rug_h], radius=20, fill=(232, 214, 186), outline=SUB, width=3)
    tw, th = 300, 150
    tx0, ty0 = cx - tw // 2, ry0 + rug_h // 2 - th // 2
    d.rounded_rectangle([tx0, ty0, tx0 + tw, ty0 + th], radius=12, fill=WALNUT)
    for sx in (tx0 + 50, tx0 + tw - 110):
        for sy, h in ((ty0 - 80, 60), (ty0 + th + 20, 60)):
            d.rounded_rectangle([sx, sy, sx + 60, sy + h], radius=10, fill=INK)
    f = font(FONT_BOLD, 30)
    label = spec.get("margin_label", "")
    # 余白の矢印（テーブルの横）
    ay = ty0 + th // 2
    for xa, xb in ((rx0, tx0), (tx0 + tw, rx0 + rug_w)):
        d.line([xa + 8, ay, xb - 8, ay], fill=MUSTARD, width=5)
        tl = d.textlength(label, font=f)
        d.text(((xa + xb) / 2 - tl / 2, ay - 46), label, font=f, fill=INK)
    caption(d, top, height, spec)


VISUALS.update({
    "bars": visual_bars, "pairs": visual_pairs, "timeline": visual_timeline, "versus": visual_versus,
    "area": visual_area, "chair": visual_chair, "lantern": visual_lantern, "rug": visual_rug,
})


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
        VISUALS[spec["visual"]](img, y - 10, vh, spec)
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
