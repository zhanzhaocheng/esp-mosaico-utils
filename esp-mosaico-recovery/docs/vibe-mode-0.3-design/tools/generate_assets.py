#!/usr/bin/env python3
"""Regenerate the Vibe Mode 0.3 design assets: font subsets, icons and QR codes.

Design tooling only; firmware builds do not run this script. Requirements:
Pillow, fonttools and qrcode (``pip install pillow fonttools qrcode``).

Font sources are the OFL variable fonts from https://github.com/google/fonts:
``ofl/doto/Doto[ROND,wght].ttf`` and ``ofl/notosanssc/NotoSansSC[wght].ttf``
(checked against google/fonts commit bd8f81ddb5c74d5c8897b36ad88b440266245103).
Pass the checkout root with ``--google-fonts``; icons and QR codes need no
external input. Each output is deterministic for the same tool versions.

QR codes are written at one pixel per module (33 x 33 px for version 3 with a
2-module quiet zone). Layouts scale them by an integer factor with
nearest-neighbour sampling, as the firmware's runtime QR encoder will.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw

from sample_data import QR_APPS

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
NOTO_EXTRA = "·•…—–‹›→←↑↓×°✓●○★☆"
DOTO_EXTRA = "·•…—–×°"

# QR payloads. "develop" is the official vibe-coding guide; the help links are
# placeholders the website can redirect until the documentation URLs are
# confirmed. Every payload must stay <= 53 bytes (QR version 3, ECC L).
QR_CODES = {
    "ideas": "https://mosaico-ideas.espressif.com/",
    "develop": "https://mosaico.espressif.com/guide/vibe-coding/",
    "help-start": "https://mosaico.espressif.com/vibe/start",
    "help-ids": "https://mosaico.espressif.com/vibe/ids",
    "help-fix": "https://mosaico.espressif.com/vibe/fix",
}
QR_CODES.update({f"app-{app['id']}": app["url"] for app in QR_APPS})
QR_VERSION, QR_BORDER = 3, 2
QR_MODULES = 17 + 4 * QR_VERSION + 2 * QR_BORDER  # 33


# --------------------------------------------------------------------------
# Fonts
# --------------------------------------------------------------------------
def _instance(source: Path, axes: dict[str, float]):
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer

    # Keep the source timestamp so rebuilt subsets are byte-identical.
    font = TTFont(source, recalcTimestamp=False)
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


def _robot(p: Pen) -> None:
    # Same mark as the device's own status bar: the AI agent link.
    p.rrect(4.5, 8.5, 19.5, 19.5, 3.5, 1.8)
    p.line([(12, 8.5), (12, 5.2)], 1.8)
    p.dot(12, 4.0, 1.6)
    p.dot(9.2, 14, 1.6)
    p.dot(14.8, 14, 1.6)
    p.line([(2.2, 12.5), (2.2, 15.5)], 1.8)
    p.line([(21.8, 12.5), (21.8, 15.5)], 1.8)


def _battery(level: float | None):
    def draw(p: Pen) -> None:
        p.rrect(2.5, 7.5, 19.5, 16.5, 2.4, 1.6)
        p.rrect(20.6, 10.2, 22.4, 13.8, 0.8, None)
        if level is None:  # charging bolt
            p.polygon([(12.6, 8.6), (7.6, 12.6), (10.6, 12.6), (9.4, 15.4), (14.4, 11.4), (11.4, 11.4)])
        elif level > 0:
            p.rrect(4.6, 9.6, 4.6 + 12.8 * level, 14.4, 1.0, None)
    return draw


def _star_points(cx=12.0, cy=12.7, outer=9.4, inner=3.9):
    pts = []
    for i in range(10):
        a = math.radians(-90 + i * 36)
        r = outer if i % 2 == 0 else inner
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def _star(fill: bool):
    def draw(p: Pen) -> None:
        pts = _star_points()
        if fill:
            p.polygon(pts)
            for x, y in pts[::2]:
                p.dot(x, y, 0.9)
        else:
            p.line(pts + pts[:1], 1.7)
    return draw


def _gear(p: Pen) -> None:
    pts = []
    for i in range(8):
        a = i * 45
        for da, r in ((-16, 6.9), (-8, 9.6), (8, 9.6), (16, 6.9)):
            t = math.radians(a + da)
            pts.append((12 + r * math.cos(t), 12 + r * math.sin(t)))
    p.line(pts + pts[:1], 1.6)
    p.circle(12, 12, 2.8, 1.6)


def _pin(p: Pen) -> None:
    cx, cy, r = 12, 9.5, 6.6
    a0, a1 = 140, 400
    p.arc(cx, cy, r, a0, a1, 1.8)
    for a in (a0, a1):
        t = math.radians(a)
        p.line([(cx + r * math.cos(t), cy + r * math.sin(t)), (12, 21)], 1.8)
    p.circle(cx, cy, 2.3, 1.8)


def _speaker(p: Pen) -> None:
    p.line([(3.5, 9.5), (7.5, 9.5), (12.5, 5), (12.5, 19), (7.5, 14.5), (3.5, 14.5), (3.5, 9.5)], 1.7)
    p.arc(12.5, 12, 4.2, -45, 45, 1.7)
    p.arc(12.5, 12, 7.8, -50, 50, 1.7)


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
    "robot": _robot,
    "usb": _usb,
    "battery_full": _battery(1.0),
    "battery_mid": _battery(0.55),
    "battery_low": _battery(0.18),
    "battery_charging": _battery(None),
    "star": _star(False),
    "star_fill": _star(True),
    "code": lambda p: (p.line([(8, 7), (3.5, 12), (8, 17)], 2.0), p.line([(16, 7), (20.5, 12), (16, 17)], 2.0),
                       p.line([(13.6, 4.8), (10.4, 19.2)], 2.0)),
    "pin": _pin,
    "key": lambda p: (p.circle(7.5, 12, 4.2, 1.8), p.line([(11.7, 12), (21, 12)], 1.8),
                      p.line([(17.6, 12), (17.6, 15.6)], 1.8), p.line([(20.6, 12), (20.6, 14.8)], 1.8)),
    "grid": lambda p: [p.rrect(x, y, x + 6.5, y + 6.5, 1.6, 1.7) for x in (4, 13.5) for y in (4, 13.5)],
    "house": lambda p: (p.line([(3.5, 11.5), (12, 4), (20.5, 11.5)], 1.8),
                        p.line([(6, 9.6), (6, 20), (18, 20), (18, 9.6)], 1.8),
                        p.line([(10, 20), (10, 14.5), (14, 14.5), (14, 20)], 1.8)),
    "sensor": lambda p: p.line([(2.5, 12.5), (7, 12.5), (9.6, 6), (14, 19), (16.4, 12.5), (21.5, 12.5)], 1.8),
    "display": lambda p: (p.rrect(3, 4.5, 21, 16.5, 2.2, 1.8), p.line([(12, 16.5), (12, 19.8)], 1.8),
                          p.line([(8, 20), (16, 20)], 1.8)),
    "audio": _speaker,
    "chat": lambda p: (p.rrect(3.5, 4.5, 20.5, 15.8, 3.4, 1.8), p.line([(8.4, 15.8), (6.6, 20.4), (12.6, 15.8)], 1.8)),
    "motor": _gear,
    "expand": lambda p: (p.line([(4, 9), (4, 4), (9, 4)], 1.9), p.line([(15, 4), (20, 4), (20, 9)], 1.9),
                         p.line([(4, 15), (4, 20), (9, 20)], 1.9), p.line([(20, 15), (20, 20), (15, 20)], 1.9)),
    "chip": lambda p: (p.rrect(6, 6, 18, 18, 2.5), p.rrect(9.5, 9.5, 14.5, 14.5, 1.0),
                       *[p.line([(x, 2.5), (x, 5)], 1.6) for x in (9.5, 14.5)],
                       *[p.line([(x, 19), (x, 21.5)], 1.6) for x in (9.5, 14.5)],
                       *[p.line([(2.5, y), (5, y)], 1.6) for y in (9.5, 14.5)],
                       *[p.line([(19, y), (21.5, y)], 1.6) for y in (9.5, 14.5)]),
    "id": lambda p: (p.rrect(3, 5.5, 21, 18.5, 2.5), p.circle(8.5, 11, 1.9), p.line([(5.8, 15.5), (11.2, 15.5)]),
                     p.line([(13.5, 10), (18, 10)]), p.line([(13.5, 14), (17, 14)])),
    "storage": lambda p: (p.earc(5, 3.5, 19, 8.5, 0, 360), p.line([(5, 6), (5, 18)]), p.line([(19, 6), (19, 18)]),
                          p.earc(5, 9.5, 19, 14.5, 0, 180), p.earc(5, 15.5, 19, 20.5, 0, 180)),
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
    # Headers, status row and navigation.
    ("back", 22, "white"), ("help", 22, "white"), ("settings", 22, "white"), ("chevron", 18, "dim"),
    ("wifi", 22, "white"), ("wifi_off", 22, "grey"), ("robot", 22, "orange"), ("robot", 22, "grey"),
    ("battery_full", 22, "white"), ("battery_mid", 22, "white"), ("battery_low", 22, "orange"),
    ("battery_charging", 22, "white"),
    # Library filters, rows and favorites.
    ("star", 18, "white"), ("star_fill", 18, "black"), ("grid", 18, "white"), ("grid", 18, "black"),
    ("star", 22, "white"),
    ("star_fill", 22, "orange"), ("grid", 22, "white"),
    *[(name, 22, "white") for name in ("display", "audio", "house", "sensor", "chat", "motor")],
    # Actions.
    ("download", 20, "black"), ("download", 20, "white"), ("code", 20, "white"), ("play", 20, "black"),
    ("refresh", 20, "white"), ("trash", 20, "orange"), ("replay", 20, "white"), ("backspace", 26, "white"),
    ("arrow", 26, "white"), ("expand", 16, "grey"), ("eye", 24, "white"), ("eye_off", 24, "white"),
    # Pages: develop, device, help, guide, progress and results.
    ("usb", 22, "grey"), ("wifi", 22, "grey"), ("pin", 22, "grey"), ("key", 22, "grey"),
    ("chip", 22, "grey"), ("id", 22, "grey"), ("storage", 22, "grey"), ("flag", 24, "white"),
    ("code", 24, "white"), ("hash", 24, "white"), ("support", 24, "white"), ("download", 24, "white"),
    ("power", 20, "orange"), ("check", 40, "orange"), ("close", 40, "grey"),
]
COLORS = {"white": WHITE, "grey": GREY, "dim": DIM, "black": BLACK, "orange": ORANGE}


def build_icons() -> None:
    out = ASSETS / "icons"
    out.mkdir(parents=True, exist_ok=True)
    for stale in out.glob("*.png"):
        stale.unlink()
    for name, size, color in ICON_OUTPUTS:
        pen = Pen(size)
        ICONS[name](pen)
        pen.result(COLORS[color]).save(out / f"{name}-{size}-{color}.png", optimize=True)
    _empty_grid(56, GREY).save(out / "empty-56-grey.png", optimize=True)


# --------------------------------------------------------------------------
# QR codes: version 3, ECC L, 2-module quiet zone, one pixel per module
# --------------------------------------------------------------------------
def build_qr() -> None:
    import qrcode

    out = ASSETS / "qr"
    out.mkdir(parents=True, exist_ok=True)
    for stale in out.glob("*.png"):
        stale.unlink()
    for name, url in QR_CODES.items():
        if len(url.encode()) > 53:
            raise SystemExit(f"{name}: {url} exceeds the QR version 3-L byte capacity (53)")
        qr = qrcode.QRCode(version=QR_VERSION, error_correction=qrcode.constants.ERROR_CORRECT_L,
                           box_size=1, border=QR_BORDER)
        qr.add_data(url, optimize=0)
        qr.make(fit=False)
        image = qr.make_image(fill_color="black", back_color="white").convert("1")
        assert image.size == (QR_MODULES, QR_MODULES), image.size
        image.save(out / f"{name}.png", optimize=True)


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
