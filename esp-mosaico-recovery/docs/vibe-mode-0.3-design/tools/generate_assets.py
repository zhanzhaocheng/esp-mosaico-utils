#!/usr/bin/env python3
"""Regenerate the Vibe Mode 0.3 design assets: font subsets, icons and QR codes.

Design tooling only; firmware builds do not run this script. Requirements:
Pillow, fonttools and qrcode (``pip install pillow fonttools qrcode``).

Font sources are the OFL variable fonts from https://github.com/google/fonts:
``ofl/doto/Doto[ROND,wght].ttf`` and ``ofl/notosanssc/NotoSansSC[wght].ttf``
(checked against google/fonts commit bd8f81ddb5c74d5c8897b36ad88b440266245103).
Pass the checkout root with ``--google-fonts``; icons and QR codes need no
external input. Each output is deterministic for the same tool versions.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw

DESIGN = Path(__file__).resolve().parents[1]
ASSETS = DESIGN / "assets"

WHITE = (242, 242, 242)
GREY = (154, 154, 154)
DIM = (92, 92, 92)
BLACK = (0, 0, 0)
ORANGE = (255, 76, 1)

# ASCII plus the few symbols the English design uses. The Chinese phase only
# extends NOTO_EXTRA with its fixed CJK copy; the fonts themselves stay.
ASCII = "".join(chr(c) for c in range(0x20, 0x7F))
NOTO_EXTRA = "·•…—–‹›→←↑↓×°✓●○"
DOTO_EXTRA = "·•…—–×°"

# Stable short links the website can redirect. Placeholders until the official
# documentation URLs are confirmed; keep each URL <= 42 bytes (QR version 3-M).
QR_CODES = {
    "ideas": "https://mosaico-ideas.espressif.com/",
    "help-start": "https://mosaico.espressif.com/vibe/start",
    "help-agent": "https://mosaico.espressif.com/vibe/agent",
    "help-ids": "https://mosaico.espressif.com/vibe/ids",
    "help-fix": "https://mosaico.espressif.com/vibe/fix",
}


# --------------------------------------------------------------------------
# Fonts
# --------------------------------------------------------------------------
def _instance(source: Path, axes: dict[str, float]):
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer

    font = TTFont(source)
    instancer.instantiateVariableFont(font, axes, inplace=True, updateFontNames=False)
    return font


def _subset(font, text: str):
    from fontTools import subset

    options = subset.Options()
    options.layout_features = ["kern", "liga", "calt"]
    options.name_IDs = ["*"]
    options.notdef_outline = True
    options.hinting = False
    subsetter = subset.Subsetter(options)
    subsetter.populate(text=text)
    subsetter.subset(font)
    return font


def _metrics(font, ascent: int, descent: int) -> None:
    """Use tight, identical vertical metrics so GSP label heights are predictable."""
    font["hhea"].ascent = ascent
    font["hhea"].descent = -descent
    font["hhea"].lineGap = 0
    os2 = font["OS/2"]
    os2.sTypoAscender = ascent
    os2.sTypoDescender = -descent
    os2.sTypoLineGap = 0
    os2.usWinAscent = ascent
    os2.usWinDescent = descent


def _names(font, family: str, style: str) -> None:
    table = font["name"]
    for record in list(table.names):
        if record.nameID in (1, 2, 3, 4, 6, 16, 17, 21, 22, 25):
            table.removeNames(nameID=record.nameID)
    full = f"{family} {style}"
    postscript = full.replace(" ", "")
    for name_id, value in ((1, full if style != "Regular" else family),
                           (2, "Regular"), (3, f"{postscript};vibe-subset"),
                           (4, full), (6, postscript), (16, family), (17, style)):
        table.setName(value, name_id, 3, 1, 0x409)
        table.setName(value, name_id, 1, 0, 0)


def build_fonts(google_fonts: Path) -> None:
    out = ASSETS / "fonts"
    out.mkdir(parents=True, exist_ok=True)
    doto = google_fonts / "ofl/doto/Doto[ROND,wght].ttf"
    noto = google_fonts / "ofl/notosanssc/NotoSansSC[wght].ttf"
    font = _subset(_instance(doto, {"ROND": 100, "wght": 900}), ASCII + DOTO_EXTRA)
    # Doto caps occupy 0..700 units and descenders reach -200.
    _metrics(font, 800, 200)
    _names(font, "Doto Vibe", "Black")
    font.save(out / "Doto-Black.subset.ttf")
    for style, weight in (("Regular", 400), ("Medium", 500)):
        font = _subset(_instance(noto, {"wght": weight}), ASCII + NOTO_EXTRA)
        # 1.25 em keeps Latin accents and the CJK ideographic box (-120..880).
        _metrics(font, 1000, 250)
        _names(font, "Noto Sans SC Vibe", style)
        font.save(out / f"NotoSansSC-{style}.subset.ttf")
    for name, source in (("OFL-Doto.txt", doto.with_name("OFL.txt")),
                         ("OFL-NotoSansSC.txt", noto.with_name("OFL.txt"))):
        (out / name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


# --------------------------------------------------------------------------
# Icons: 24-unit grid, round caps and joins, 8x supersampled
# --------------------------------------------------------------------------
class Pen:
    def __init__(self, size: int, grid: float = 24.0, scale: int = 8):
        self.size, self.scale = size, scale
        self.k = size * scale / grid
        self.image = Image.new("L", (size * scale, size * scale), 0)
        self.draw = ImageDraw.Draw(self.image)

    def p(self, x: float, y: float) -> tuple[float, float]:
        return x * self.k, y * self.k

    def dot(self, x: float, y: float, r: float, value: int = 255) -> None:
        cx, cy = self.p(x, y)
        rr = r * self.k
        self.draw.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=value)

    def px(self, width: float) -> int:
        return max(1, round(width * self.k))

    def stroke_box(self, x0, y0, x1, y1, width: float):
        # Pillow strokes grow inward from the box; widen it by half a stroke
        # so every outline is centered on its nominal geometry.
        h = width / 2
        return (*self.p(x0 - h, y0 - h), *self.p(x1 + h, y1 + h))

    def line(self, points, width: float = 1.75, value: int = 255) -> None:
        pts = [self.p(x, y) for x, y in points]
        self.draw.line(pts, fill=value, width=self.px(width))
        for x, y in points:
            self.dot(x, y, width / 2, value)

    def earc(self, x0, y0, x1, y1, start, end, width: float = 1.75, value: int = 255) -> None:
        self.draw.arc(self.stroke_box(x0, y0, x1, y1, width), start, end, fill=value,
                      width=self.px(width))
        cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
        for angle in (start, end):
            a = math.radians(angle)
            self.dot(cx + rx * math.cos(a), cy + ry * math.sin(a), width / 2, value)

    def arc(self, cx, cy, r, start, end, width: float = 1.75, value: int = 255) -> None:
        self.earc(cx - r, cy - r, cx + r, cy + r, start, end, width, value)

    def circle(self, cx, cy, r, width: float | None = 1.75, value: int = 255) -> None:
        if width is None:
            self.draw.ellipse((*self.p(cx - r, cy - r), *self.p(cx + r, cy + r)), fill=value)
        else:
            self.draw.ellipse(self.stroke_box(cx - r, cy - r, cx + r, cy + r, width),
                              outline=value, width=self.px(width))

    def rrect(self, x0, y0, x1, y1, r, width: float | None = 1.75, value: int = 255) -> None:
        if width is None:
            self.draw.rounded_rectangle((*self.p(x0, y0), *self.p(x1, y1)), r * self.k, fill=value)
        else:
            self.draw.rounded_rectangle(self.stroke_box(x0, y0, x1, y1, width),
                                        (r + width / 2) * self.k, outline=value,
                                        width=self.px(width))

    def polygon(self, points, value: int = 255) -> None:
        self.draw.polygon([self.p(x, y) for x, y in points], fill=value)

    def erase_circle(self, cx, cy, r) -> None:
        self.circle(cx, cy, r, None, 0)

    def result(self, color) -> Image.Image:
        alpha = self.image.resize((self.size, self.size), Image.LANCZOS)
        rgba = Image.new("RGBA", alpha.size, (*color, 0))
        rgba.putalpha(alpha)
        return rgba


def _wifi(p: Pen, off: bool = False) -> None:
    for r in (4.5, 9.0, 13.5):
        p.arc(12, 20, r, 225, 315, 1.9)
    p.dot(12, 19.2, 1.6)
    if off:
        p.line([(4.5, 4.5), (19.5, 19.5)], 1.9)


def _sliders(p: Pen) -> None:
    p.line([(4, 8), (11.5, 8)])
    p.line([(18.5, 8), (20, 8)])
    p.circle(15, 8, 2.6)
    p.line([(4, 16), (5.5, 16)])
    p.line([(12.5, 16), (20, 16)])
    p.circle(9, 16, 2.6)


def _question(p: Pen) -> None:
    p.arc(12, 9, 4.2, 180, 380, 1.9)
    a = math.radians(20)
    x, y = 12 + 4.2 * math.cos(a), 9 + 4.2 * math.sin(a)
    p.line([(x, y), (12, 14.2), (12, 15)], 1.9)
    p.dot(12, 19, 1.25)


def _agent(p: Pen) -> None:
    # Four-point spark: the common "AI" mark, drawn as a filled concave star.
    c, r, s = 12, 9.5, 2.4
    pts = []
    for i in range(8):
        a = math.radians(-90 + i * 45)
        rad = r if i % 2 == 0 else s
        pts.append((c + rad * math.cos(a), c + rad * math.sin(a)))
    p.polygon(pts)
    p.dot(19.5, 4.5, 1.4)


def _usb(p: Pen) -> None:
    p.line([(12, 3.5), (12, 20)])
    p.polygon([(12, 2), (14.2, 5.2), (9.8, 5.2)])
    p.line([(12, 15.5), (7, 12.5), (7, 10)])
    p.line([(12, 13), (17, 10), (17, 8)])
    p.circle(7, 8.6, 1.5, None)
    p.rrect(15.6, 6, 18.4, 8.8, 0.4, None)
    p.circle(12, 20, 1.9, None)


ICONS = {
    "back": lambda p: p.line([(15, 5), (8, 12), (15, 19)], 2.0),
    "chevron": lambda p: p.line([(9, 5), (16, 12), (9, 19)], 2.0),
    "plus": lambda p: (p.line([(12, 5), (12, 19)], 2.2), p.line([(5, 12), (19, 12)], 2.2)),
    "check": lambda p: p.line([(5, 12.5), (10, 17.5), (19, 7)], 2.0),
    "close": lambda p: (p.line([(6, 6), (18, 18)], 2.0), p.line([(18, 6), (6, 18)], 2.0)),
    "arrow": lambda p: (p.line([(4.5, 12), (19, 12)], 2.0), p.line([(13, 6), (19, 12), (13, 18)], 2.0)),
    "backspace": lambda p: (p.line([(21, 6), (9, 6), (3, 12), (9, 18), (21, 18), (21, 6)], 1.8),
                            p.line([(12.5, 9.5), (17.5, 14.5)], 1.8),
                            p.line([(17.5, 9.5), (12.5, 14.5)], 1.8)),
    "play": lambda p: p.polygon([(7.5, 4.5), (19.5, 12), (7.5, 19.5)]),
    "download": lambda p: (p.line([(12, 3.5), (12, 15)], 2.0), p.line([(7, 10), (12, 15), (17, 10)], 2.0),
                           p.line([(5, 20), (19, 20)], 2.0)),
    # Clockwise: 300 degree sweep ending at the top, chevron head pointing right.
    "refresh": lambda p: (p.arc(12, 12.5, 7.5, -30, 270, 2.0),
                          p.line([(9.2, 2.0), (12, 5.0), (9.2, 8.0)], 2.0)),
    "trash": lambda p: (p.line([(4, 7), (20, 7)]), p.line([(9, 7), (9, 4.5), (15, 4.5), (15, 7)]),
                        p.line([(6, 7), (7, 20), (17, 20), (18, 7)]),
                        p.line([(10, 11), (10, 16)]), p.line([(14, 11), (14, 16)])),
    "eye": lambda p: (p.arc(12, 18, 10.5, 215, 325), p.arc(12, 6, 10.5, 35, 145), p.circle(12, 12, 3.2)),
    "eye_off": lambda p: (p.arc(12, 18, 10.5, 215, 325), p.arc(12, 6, 10.5, 35, 145), p.circle(12, 12, 3.2),
                          p.line([(4, 4), (20, 20)])),
    "wifi": _wifi,
    "wifi_off": lambda p: _wifi(p, True),
    "settings": _sliders,
    "help": _question,
    "agent": _agent,
    "usb": _usb,
    "chip": lambda p: (p.rrect(6, 6, 18, 18, 2.5), p.rrect(9.5, 9.5, 14.5, 14.5, 1.0),
                       *[p.line([(x, 2.5), (x, 5)], 1.6) for x in (9.5, 14.5)],
                       *[p.line([(x, 19), (x, 21.5)], 1.6) for x in (9.5, 14.5)],
                       *[p.line([(2.5, y), (5, y)], 1.6) for y in (9.5, 14.5)],
                       *[p.line([(19, y), (21.5, y)], 1.6) for y in (9.5, 14.5)]),
    "id": lambda p: (p.rrect(3, 5.5, 21, 18.5, 2.5), p.circle(8.5, 11, 1.9), p.line([(5.8, 15.5), (11.2, 15.5)]),
                     p.line([(13.5, 10), (18, 10)]), p.line([(13.5, 14), (17, 14)])),
    "storage": lambda p: (p.earc(5, 3.5, 19, 8.5, 0, 360), p.line([(5, 6), (5, 18)]), p.line([(19, 6), (19, 18)]),
                          p.earc(5, 9.5, 19, 14.5, 0, 180), p.earc(5, 15.5, 19, 20.5, 0, 180)),
    "terminal": lambda p: (p.rrect(3, 4.5, 21, 19.5, 2.5), p.line([(7, 9), (10, 12), (7, 15)]),
                           p.line([(12.5, 15), (16.5, 15)])),
    "scan": lambda p: (p.line([(3.5, 8), (3.5, 3.5), (8, 3.5)]), p.line([(16, 3.5), (20.5, 3.5), (20.5, 8)]),
                       p.line([(3.5, 16), (3.5, 20.5), (8, 20.5)]), p.line([(16, 20.5), (20.5, 20.5), (20.5, 16)]),
                       p.line([(3.5, 12), (20.5, 12)])),
    "flag": lambda p: (p.line([(5.5, 21), (5.5, 3.5)]), p.line([(5.5, 4.5), (18.5, 4.5), (15.5, 9), (18.5, 13.5), (5.5, 13.5)])),
    "hash": lambda p: (p.line([(9.5, 3.5), (7.5, 20.5)]), p.line([(16.5, 3.5), (14.5, 20.5)]),
                       p.line([(4, 9), (20, 9)]), p.line([(3.5, 15), (19.5, 15)])),
    "support": lambda p: (p.circle(12, 12, 8.5, 1.9), p.circle(12, 12, 3.6, 1.9),
                          *[p.line([(12 + 4.4 * math.cos(math.radians(a)), 12 + 4.4 * math.sin(math.radians(a))),
                                    (12 + 7.6 * math.cos(math.radians(a)), 12 + 7.6 * math.sin(math.radians(a)))], 1.9)
                            for a in (45, 135, 225, 315)]),
    "power": lambda p: (p.arc(12, 13, 7.5, 300, 600, 2.0), p.line([(12, 3), (12, 11)], 2.0)),
    # Counter-clockwise mirror of refresh: starts at the top, head points left.
    "replay": lambda p: (p.arc(12, 12.5, 7.5, 270, 570, 2.0),
                         p.line([(14.8, 2.0), (12, 5.0), (14.8, 8.0)], 2.0)),
}


def _empty_grid(size: int, color) -> Image.Image:
    """3x3 dot-matrix tile used for the empty library state."""
    pen = Pen(size)
    for row in range(3):
        for col in range(3):
            filled = (row, col) in ((0, 0), (1, 1), (2, 2), (0, 2))
            x, y = 5 + col * 7, 5 + row * 7
            if filled:
                pen.rrect(x - 2.6, y - 2.6, x + 2.6, y + 2.6, 1.2, None)
            else:
                pen.rrect(x - 2.3, y - 2.3, x + 2.3, y + 2.3, 1.2, 1.2)
    return pen.result(color)


# (icon, size px, color name). Sizes match their on-screen boxes exactly.
ICON_OUTPUTS = [
    ("back", 22, "white"), ("help", 22, "white"), ("settings", 22, "white"),
    ("wifi", 18, "white"), ("wifi_off", 18, "grey"), ("agent", 18, "orange"), ("agent", 18, "grey"),
    ("usb", 18, "grey"), ("plus", 22, "black"), ("chevron", 18, "dim"), ("backspace", 26, "white"),
    ("arrow", 26, "white"), ("play", 20, "black"), ("download", 20, "black"), ("download", 20, "white"),
    ("refresh", 20, "white"), ("refresh", 22, "white"), ("trash", 20, "orange"), ("eye", 24, "white"),
    ("eye_off", 24, "white"), ("check", 40, "orange"), ("close", 40, "grey"), ("chip", 22, "grey"),
    ("id", 22, "grey"), ("storage", 22, "grey"), ("terminal", 22, "grey"), ("wifi", 22, "grey"),
    ("scan", 20, "grey"), ("flag", 24, "white"), ("agent", 24, "white"), ("hash", 24, "white"),
    ("support", 24, "white"), ("replay", 20, "white"), ("power", 20, "orange"), ("close", 20, "white"),
]
COLORS = {"white": WHITE, "grey": GREY, "dim": DIM, "black": BLACK, "orange": ORANGE}


def build_icons() -> None:
    out = ASSETS / "icons"
    out.mkdir(parents=True, exist_ok=True)
    for name, size, color in ICON_OUTPUTS:
        pen = Pen(size)
        ICONS[name](pen)
        pen.result(COLORS[color]).save(out / f"{name}-{size}-{color}.png", optimize=True)
    _empty_grid(56, GREY).save(out / "empty-56-grey.png", optimize=True)
    build_guide_device(out)


def build_guide_device(out: Path) -> None:
    """Line drawing of the device for the "how to enter" guide page.

    The AI key sits on the top edge and the power key on the bottom edge,
    right side, as described by the product owner. Exact key positions must
    be checked against the industrial design before release.
    """
    w, h, s = 200, 200, 8
    img = Image.new("RGBA", (w * s, h * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def box(x0, y0, x1, y1):
        return (x0 * s, y0 * s, x1 * s, y1 * s)

    d.rounded_rectangle(box(118 - 26, 8, 118 + 4, 22), 6 * s, fill=(*ORANGE, 255))   # AI key
    d.rounded_rectangle(box(130, 178, 160, 192), 6 * s, fill=(*ORANGE, 255))         # power key
    d.rounded_rectangle(box(22, 18, 178, 182), 30 * s, fill=(0, 0, 0, 255),
                        outline=(*WHITE, 255), width=3 * s)                           # body
    d.rounded_rectangle(box(40, 36, 160, 164), 16 * s, outline=(*DIM, 255), width=2 * s)
    # A tiny dot-matrix "V" on the screen hints at the Vibe Mode boot screen.
    for i, (cx, cy) in enumerate([(84, 84), (90, 96), (96, 108), (102, 120), (108, 108),
                                  (114, 96), (120, 84)]):
        r = 3.2
        d.ellipse(box(cx - r, cy - r, cx + r, cy + r), fill=(*ORANGE, 255) if i == 3 else (*WHITE, 255))
    img.resize((w, h), Image.LANCZOS).save(out / "guide-device-200.png", optimize=True)


# --------------------------------------------------------------------------
# QR codes: version 3, ECC M, 4 px modules, 4-module quiet zone = 148 px
# --------------------------------------------------------------------------
def build_qr() -> None:
    import qrcode

    out = ASSETS / "qr"
    out.mkdir(parents=True, exist_ok=True)
    for name, url in QR_CODES.items():
        if len(url.encode()) > 42:
            raise SystemExit(f"{name}: {url} exceeds QR version 3-M byte capacity")
        qr = qrcode.QRCode(version=3, error_correction=qrcode.constants.ERROR_CORRECT_M,
                           box_size=4, border=4, mask_pattern=0)
        qr.add_data(url, optimize=0)
        qr.make(fit=False)
        image = qr.make_image(fill_color="black", back_color="white").convert("1")
        assert image.size == (148, 148), image.size
        image.save(out / f"{name}-148.png", optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--google-fonts", type=Path,
                        help="google/fonts checkout root; omit to keep the committed font subsets")
    args = parser.parse_args()
    if args.google_fonts:
        build_fonts(args.google_fonts)
    build_icons()
    build_qr()


if __name__ == "__main__":
    main()
