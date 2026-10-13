#!/usr/bin/env python3
"""Build the Vibe Mode 0.3 design: layout data, mockups and layout checks.

Every page state is described once with GSP 1.4.0 primitives (layer content as
containers, labels, buttons, images, a progress bar and the native keyboard).
The same data produces ``layout.json`` (the source for the Phase B scene),
the PNG mockups and the clickable prototype (``build_prototype.py``).

Mockups are approximate design renders made with Pillow and the subset fonts;
they are not GSP simulator or device screenshots. Requires Pillow and
fontTools. Run ``generate_assets.py`` first.
"""
from __future__ import annotations

import itertools
import json
import math
import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

from sample_data import (AI_TOKEN_KIND, CATEGORIES, CATEGORY_LABEL, CURRENT, FAVORITES,
                         NAND_CAPACITY_MB, PRESETS, RECENT, STORE_ONLY, STORE_UPDATES)

DESIGN = Path(__file__).resolve().parents[1]
W = H = 480
M = 16  # outer margin
# Product drawing: 38.8 mm square active display and 60 px corner radius.
SCREEN_R = 60
# Centre of the AI key above the screen's top edge: about 3/4 of the body width
# (product photo), which is x = 372 on the screen with the prototype's bezel.
AI_KEY_CX = 372
QR_MODULES = 33  # version 3 (29 modules) plus a 2-module quiet zone on each side

# --------------------------------------------------------------------------
# Tokens
# --------------------------------------------------------------------------
BG = "#000000"
CARD = "#141414"
RAISED = "#1E1E1E"
TILE = "#262626"
LINE = "#3A3A3A"
DIVIDER = "#262626"
TEXT = "#F2F2F2"
TEXT2 = "#9A9A9A"
TEXT3 = "#5C5C5C"
ACCENT = "#FF4C01"
PRIMARY_BG = "#F2F2F2"
PRIMARY_FG = "#000000"
WHITE = "#FFFFFF"

FONTS = {
    # Semantic keys kept stable for the implementation handoff. "dot" is the
    # display role; the dot-matrix look comes from bitmaps only.
    "dot": "assets/fonts/ArchivoExtended-SemiBold.subset.ttf",
    "sans": "assets/fonts/Inter-Regular.subset.ttf",
    "medium": "assets/fonts/ArchivoExtended-Medium.subset.ttf",
}
# Line height per em, from the subset fonts' vertical metrics.
LINE_EM = {"dot": 1.15, "sans": 1.2, "medium": 1.15}
PX_MM = 38.8 / 480
TYPE_SCALE = {"sans": [16, 18, 24], "medium": [18, 22, 28],
              "dot": [18, 22, 28, 40, 88]}
MIN_TEXT, MIN_TOUCH, MIN_ICON = 16, 84, 20
DENSE_TOUCH = 72
DANGER_TOUCH = 96
DANGER_GAP = 24
ROW_H, ROW_PITCH = 72, 80

TOKENS = {
    "colors": {"background": BG, "card": CARD, "raised": RAISED, "tile": TILE, "outline": LINE,
               "divider": DIVIDER, "text": TEXT, "text_secondary": TEXT2, "text_tertiary": TEXT3,
               "accent": ACCENT, "primary_bg": PRIMARY_BG, "primary_fg": PRIMARY_FG},
    "fonts": FONTS,
    "line_height_em": LINE_EM,
    "type_scale": TYPE_SCALE,
    "radius": {"card": 20, "row": 18, "key": 20, "sheet": 32, "pill": "h/2"},
    "margin": M,
    "min_touch": MIN_TOUCH,
    "dense_touch": DENSE_TOUCH,
    "danger_touch": DANGER_TOUCH,
    "danger_gap": DANGER_GAP,
    "row": {"height": ROW_H, "pitch": ROW_PITCH},
    "readability": {"screen_width_mm": 38.8, "px_mm": round(PX_MM, 4), "min_text_px": MIN_TEXT,
                    "body_text_px": 18, "min_touch_px": MIN_TOUCH, "min_icon_px": MIN_ICON},
    "screen": {"corner_radius": SCREEN_R, "ai_key_center_x": AI_KEY_CX},
    "qr": {"version": 3, "ecc": "L", "quiet_zone_modules": 2, "modules": QR_MODULES,
           "min_module_px": 5, "dark": "#000000", "light": "#FFFFFF"},
    "motion": {"page_slide_px": 48, "page_slide_ms": 260, "sheet_ms": 300,
               "easing": "cubic-bezier(.32,.72,0,1)"},
    "keyboard": {"bg_color": BG, "fg_color": TEXT, "key_color": TILE, "function_color": RAISED,
                 "ok_color": ACCENT, "ok_text_color": WHITE, "key_radius": 10, "font": "medium",
                 "font_size": 18, "function_font_size": 18},
    # Product photo: cream body, light grey keys, orange AI key.
    "hardware": {"body": "#E9E2D6", "body_edge": "#C4BBAC", "key": "#CFCAC2", "key_edge": "#A09A92",
                 "ai_key": ACCENT},
}


def line_h(font: str, size: int, lines: int = 1) -> int:
    return math.ceil(LINE_EM[font] * size * lines)


# --------------------------------------------------------------------------
# Primitive constructors (GSP widget vocabulary)
# --------------------------------------------------------------------------
def container(x, y, w, h, bg=None, radius=0, border=None, bw=0, name=None, opacity=255, role=None):
    return {"type": "container", "x": x, "y": y, "w": w, "h": h, "bg": bg, "radius": radius,
            "border": border, "border_width": bw, "name": name, "opacity": opacity, "role": role}


def label(x, y, w, text, font="sans", size=16, color=TEXT, align="left", h=None, name=None,
          bg=None, radius=0, wrap=False, ellipsis=False):
    """Single-line labels that show app names, SSIDs or store text pass
    ``ellipsis=True`` (GSP ``overflow: "ellipsis"``) so they never clip mid-glyph."""
    lines = text.count("\n") + 1
    obj = {"type": "label", "x": x, "y": y, "w": w, "h": h or line_h(font, size, lines),
           "text": text, "font": font, "size": size, "color": color, "align": align,
           "name": name, "bg": bg, "radius": radius,
           "overflow": "ellipsis" if ellipsis or wrap else "clip"}
    if wrap:
        obj["wrap"] = True
    return obj


def button(x, y, w, h, text="", font="medium", size=22, color=TEXT, bg=RAISED, radius=None,
           border=None, bw=0, icon=None, action=None, name=None, icon_gap=10):
    obj = {"type": "button", "x": x, "y": y, "w": w, "h": h, "text": text, "font": font,
           "size": size, "color": color, "bg": bg, "radius": h // 2 if radius is None else radius,
           "border": border, "border_width": bw, "action": action, "name": name, "icon": None}
    if icon:
        size_px = int(Path(icon).stem.split("-")[1])
        if text:
            # Icon sits left of the centred text.
            tw = text_width(text, font, size)
            ix = x + (w - (size_px + icon_gap + tw)) / 2
            obj["text_offset"] = (size_px + icon_gap) / 2
        else:
            ix = x + (w - size_px) / 2
        obj["icon"] = {"image": icon, "x": round(ix), "y": round(y + (h - size_px) / 2),
                       "w": size_px, "h": size_px}
    return obj


def image(x, y, path, name=None, w=None, h=None, qr=False):
    with Image.open(DESIGN / path) as im:
        iw, ih = im.size
    obj = {"type": "image", "x": x, "y": y, "w": w or iw, "h": h or ih, "image": path, "name": name}
    if qr:
        obj["qr"] = True
    return obj


def icon(x, y, name, size, color, obj_name=None):
    return image(x, y, f"assets/icons/{name}-{size}-{color}.png", name=obj_name)


def progress(x, y, w, h, value, name="progress", fg=ACCENT):
    return {"type": "progress", "x": x, "y": y, "w": w, "h": h, "value": value, "bg": TILE,
            "fg": fg, "radius": h // 2, "name": name}


def keyboard(y=222, name="keyboard"):
    return {"type": "keyboard", "x": 0, "y": y, "w": W, "h": 233, "name": name, **TOKENS["keyboard"]}


# --------------------------------------------------------------------------
# Text measurement and glyph coverage
# --------------------------------------------------------------------------
_FONT_CACHE: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}
_CMAP: dict[str, set[int]] = {}


def font_for(font: str, size: int) -> ImageFont.FreeTypeFont:
    key = (font, size)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ImageFont.truetype(str(DESIGN / FONTS[font]), size)
    return _FONT_CACHE[key]


def missing_glyphs(text: str, font: str) -> list[str]:
    if font not in _CMAP:
        _CMAP[font] = set(TTFont(DESIGN / FONTS[font]).getBestCmap())
    return sorted({ch for ch in text if ch != "\n" and ord(ch) not in _CMAP[font]})


def text_width(text: str, font: str, size: int) -> float:
    f = font_for(font, size)
    return max((f.getlength(line) for line in text.split("\n")), default=0)


def ellipsize(text: str, f, width: float) -> str:
    if f.getlength(text) <= width:
        return text
    while text and f.getlength(text + "…") > width:
        text = text[:-1]
    return text.rstrip() + "…"


def wrap_lines(text: str, font: str, size: int, width: float, max_lines: int) -> tuple[list[str], bool]:
    """Greedy word wrap; returns (lines, truncated)."""
    f = font_for(font, size)
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if f.getlength(trial) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    if len(lines) <= max_lines:
        return lines, False
    kept = lines[:max_lines]
    kept[-1] = ellipsize(kept[-1] + "…", f, width)
    return kept, True


# --------------------------------------------------------------------------
# Sample content (illustrative only; see sample_data.py)
# --------------------------------------------------------------------------
LIBRARY = sorted(PRESETS, key=lambda app: (
    0 if app["id"] == CURRENT else 1 if app["id"] in RECENT else 2,
    RECENT.index(app["id"]) if app["id"] in RECENT else int(app["id"])))
BY_ID = {app["id"]: app for app in PRESETS + STORE_ONLY}
FAV = set(FAVORITES)
FILTER_LABELS = {"all": "My apps", "recent": "Recent", "favorites": "Favorites", **CATEGORY_LABEL}
CATEGORY_ICON = {key: ic for key, _, ic in CATEGORIES}
TILE_KEYS = set(CATEGORY_LABEL) | {"community", "other"}
NETWORKS = [
    ("Studio-5G", True, "Strong"),
    ("Maker Lab", True, "Good"),
    ("Espressif-Guest", False, "Good"),
    ("Home-2.4G", True, "Weak"),
    ("Cafe Corner", True, "Weak"),
]
TOKEN = "3f9a1c07e2b84d6a95c1f0e7d2a4b8c6" + "0d5e9f2a7c3b1e8d4f6a0c9b2e7d5a13"  # Wi-Fi link pairing
AI_TOKEN = "sk-demo-3b9f2c7e1a4d8f6b0c5e9a2d7f1b4c8e"  # shared LLM token (sample)
EMPTY_COPY = {
    "all": ("empty", "No apps yet", "Download an app by its ID,\nor develop your own."),
    "favorites": ("star", "No favorites yet", "Open an app and tap the star\nto add it here."),
    "category": ("folder", "Nothing here yet", "Find more apps on\nMosaico Ideas."),
}
HELP_TOPICS = [
    ("start", "flag", "Getting started"),
    ("develop", "code", "Develop apps"),
    ("ids", "hash", "App IDs & sharing"),
    ("fix", "support", "Troubleshooting"),
]
QR_URLS = {
    "ideas": "mosaico-ideas.espressif.com",
    "develop": "mosaico.espressif.com/guide/vibe-coding",
    "help-start": "mosaico.espressif.com/vibe/start",
    "help-ids": "mosaico.espressif.com/vibe/ids",
    "help-fix": "mosaico.espressif.com/vibe/fix",
}


def filtered(apps, flt):
    if flt == "all":
        return list(apps)
    if flt == "favorites":
        return [a for a in apps if a["id"] in FAV]
    if flt == "recent":
        ids = {CURRENT, *RECENT}
        return [a for a in apps if a["id"] in ids]
    return [a for a in apps if a["category"] == flt]


def tile_key(app) -> str:
    return app["category"] if app["category"] in TILE_KEYS else "other"


def tile(x, y, app, size, name):
    return image(x, y, f"assets/mosaic/tile_{tile_key(app)}-{size}.png", name=name)


def hero(x, y, key, size, name):
    return image(x, y, f"assets/mosaic/hero_{key}-{size}.png", name=name)


def row_detail(app) -> str:
    text = CATEGORY_LABEL.get(app["category"], "Other")
    return text if app["official"] else f"{text} · Community"


def mb(app) -> float:
    return float(app["size"].split()[0])


# --------------------------------------------------------------------------
# Shared building blocks
# --------------------------------------------------------------------------
def touch(x, y, w, h, action, name, touch_class="default"):
    """Invisible hit area (a transparent GSP button)."""
    obj = button(x, y, w, h, bg=None, radius=min(w, h) // 2, action=action, name=name)
    obj["touch_class"] = touch_class
    return obj


def circle(x, y, icon_name, action, name, color="white"):
    """64 px visible circle centred in an 84 px hit area at (x, y)."""
    return [container(x + 10, y + 10, 64, 64, BG, 32, border=LINE, bw=2, name=f"{name}_visual"),
            icon(x + 26, y + 26, icon_name, 32, color, f"{name}_icon"),
            touch(x, y, 84, 84, action, name)]


def header(title, page, mark=None, right=None, back="back", font="dot", size=28):
    """Back circle, title and an optional right circle. Only first-level pages
    (reached from Home) carry the orange page mark next to the title."""
    objs = circle(6, 6, "back", back, f"button_back_{page}") if back else []
    left = 104 if back else 32
    if mark:
        objs.append(icon(left, 32, mark, 32, "orange", f"{page}_title_icon"))
        left += 42
    right_edge = 456
    if right:
        icon_name, action, name, *color = right
        objs += circle(390, 6, icon_name, action, name, *(color or ["white"]))
        right_edge = 384
    th = line_h(font, size)
    objs.append(label(left, 48 - th // 2, right_edge - left, title, font, size, TEXT,
                      name=f"{page}_title", ellipsis=True))
    return objs


def primary(x, y, w, text, action, name, icon_name=None):
    return button(x, y, w, 84, text, "medium", 22, PRIMARY_FG, PRIMARY_BG,
                  icon=f"assets/icons/{icon_name}-32-black.png" if icon_name else None,
                  action=action, name=name)


def secondary(x, y, w, text, action, name, icon_name=None):
    return button(x, y, w, 84, text, "medium", 22, TEXT, BG, border=LINE, bw=2,
                  icon=f"assets/icons/{icon_name}-32-white.png" if icon_name else None,
                  action=action, name=name)


def danger(y, text, action, name, icon_name="trash", fill=0.0):
    """Hold-to-confirm: 96 px tall, 24 px from the edges, 600 ms hold. The orange
    fill grows from the left while held; the button itself has no background so
    the fill sits under its label."""
    objs = []
    if fill:
        objs.append(container(24, y, round(432 * fill), 96, ACCENT, 48, opacity=96, name=f"{name}_fill"))
    obj = button(24, y, 432, 96, text, "medium", 22, ACCENT, None, border=ACCENT, bw=2,
                 icon=f"assets/icons/{icon_name}-32-orange.png", action=action, name=name)
    obj.update(danger=True, hold_ms=600)
    return objs + [obj]


def row_button(y, action, name, x=16, w=448, h=ROW_H, bg=CARD):
    obj = button(x, y, w, h, bg=bg, radius=18 if h == ROW_H else 20, action=action, name=name)
    obj["touch_class"] = "dense"
    return obj


def settings_row(y, icon_name, title, value, action, name, value_name=None, value_color=TEXT2,
                 chevron=True):
    """Two-line row: 20 px icon, medium 22 title over a sans 16 value."""
    objs = [row_button(y, action, name) if action else container(16, y, 448, ROW_H, CARD, 18)]
    objs += [icon(36, y + 26, icon_name, 20, "white"),
             label(72, y + 11, 336, title, "medium", 22, TEXT),
             label(72, y + 41, 336, value, "sans", 16, value_color, name=value_name, ellipsis=True)]
    if chevron and action:
        objs.append(icon(424, y + 26, "chevron", 20, "dim"))
    return objs


def link_row(y, title, sub, icon_name, action, name):
    """Card that opens another page: 32 px icon, title, one-line hint, chevron."""
    return [row_button(y, action, name, h=80),
            icon(36, y + 24, icon_name, 32, "white"),
            label(84, y + 13, 324, title, "medium", 22, TEXT),
            label(84, y + 43, 324, sub, "sans", 16, TEXT2, ellipsis=True),
            icon(424, y + 30, "chevron", 20, "dim")]


def section(y, text, name=None, color=TEXT2):
    return label(32, y, 416, text, "medium", 18, color, name=name, ellipsis=True)


def status_dot(x, y, color, name=None):
    return container(x, y, 10, 10, color, 5, name=name)


def clipped(objs, viewport, row_of=None):
    for obj in objs:
        obj["clip"] = list(viewport)
        if row_of:
            obj["row_of"] = row_of
    return objs


def relative(objs, dx, dy):
    """Row template: coordinates relative to the list viewport, no clip."""
    out = []
    for o in objs:
        o = json.loads(json.dumps(o))
        o.pop("clip", None)
        o.pop("row_of", None)
        o["x"] -= dx
        o["y"] -= dy
        if o.get("icon"):
            o["icon"]["x"] -= dx
            o["icon"]["y"] -= dy
        out.append(o)
    return out


def list_fade(y, name):
    """Fade over the cut-off row; the controller hides it at the end of the list."""
    return image(M, y, "assets/ui/list-fade.png", name=name)


def toast(text):
    """Transient banner (~1.6 s) over the top row; tap to dismiss or follow it."""
    return [container(16, 10, 448, 72, RAISED, 36, border=LINE, bw=2, name="toast"),
            label(40, 33, 400, text, "medium", 22, TEXT, "center", name="toast_text", ellipsis=True)]


# --------------------------------------------------------------------------
# Home
# --------------------------------------------------------------------------
LIST_Y, LIST_H = 128, 256


def status_strip(agent=True, wifi_on=True, low_battery=False, badge="↑ 2"):
    objs = [status_dot(28, 21, ACCENT),
            label(46, 15, 150, "VIBE MODE", "medium", 18, TEXT2)]
    objs.append(label(212, 15, 100, badge or " ", "medium", 18, ACCENT, "right", name="status_badge"))
    objs += [icon(324, 12, "wifi" if wifi_on else "wifi_off", 28, "white" if wifi_on else "grey", "status_wifi"),
             icon(360, 12, "robot", 28, "orange" if agent else "grey", "status_agent"),
             icon(396, 12, "battery_low" if low_battery else "battery_mid", 28,
                  "orange" if low_battery else "white", "status_battery")]
    return objs


def app_row(y, app, viewport):
    current = app["id"] == CURRENT
    update = app["id"] in STORE_UPDATES
    hi = "Current app" if current else "↑ Update available" if update else " "
    objs = [container(16, y, 448, ROW_H, CARD, 18, role="row"),
            tile(24, y + 8, app, 56, "apps_tile"),
            label(92, y + 11, 284, app["name"], "medium", 22, TEXT, name="apps_name", ellipsis=True),
            label(92, y + 41, 284, " " if current or update else row_detail(app), "sans", 16, TEXT2,
                  name="apps_detail", ellipsis=True),
            label(92, y + 41, 284, hi, "sans", 16, ACCENT, name="apps_detail_hi"),
            image(384, y + 26, "assets/icons/star_fill-20-grey.png" if app["id"] in FAV
                  else "assets/ui/blank-20.png", name="apps_star"),
            icon(424, y + 26, "chevron", 20, "dim")]
    return clipped(objs, viewport, "apps")


def home(flt="all", apps=None, agent=True, wifi_on=True, low_battery=False, badge="↑ 2"):
    apps = LIBRARY if apps is None else apps
    shown = filtered(apps, flt)
    objs = status_strip(agent, wifi_on, low_battery, badge)
    objs += [container(16, 46, 280, 72, BG, 36, border=LINE, bw=2, name="button_filter_visual"),
             label(40, 69, 212, FILTER_LABELS.get(flt, "Other"), "medium", 22, TEXT,
                   name="home_title", ellipsis=True),
             icon(262, 72, "chevron_down", 20, "white"),
             touch(16, 40, 280, 84, "drawer:open", "button_filter")]
    objs += circle(304, 40, "help", "go:help", "button_help")
    objs += circle(388, 40, "chip", "go:device", "button_device")
    viewport = (16, LIST_Y, 448, LIST_H)
    if shown:
        objs.append({"type": "list_viewport", "x": 16, "y": LIST_Y, "w": 448, "h": LIST_H,
                     "name": "apps", "item_height": ROW_PITCH, "row_template": "apps_row",
                     "count": len(shown)})
        for i, app in enumerate(shown[:4]):
            objs += app_row(LIST_Y + i * ROW_PITCH, app, viewport)
        if len(shown) * ROW_PITCH - 8 > LIST_H:
            objs.append(list_fade(LIST_Y + LIST_H - 24, "apps_fade"))
    else:
        key = "all" if flt == "all" else "favorites" if flt == "favorites" else "category"
        pic, title, body = EMPTY_COPY[key]
        objs += [hero(200, 148, pic, 80, "home_empty_icon"),
                 label(24, 246, 432, title, "medium", 22, TEXT, "center", name="home_empty_title"),
                 label(24, 282, 432, body, "sans", 18, TEXT2, "center", name="home_empty_body")]
    objs.append(primary(16, 388, 216, "Download", "go:download", "button_download", "download"))
    objs.append(secondary(248, 388, 216, "Develop", "go:develop", "button_develop", "code"))
    return objs


BROWSE = [("all", "All apps", "grid"), ("recent", "Recent", "clock"), ("favorites", "Favorites", "star"),
          *[(key, text, ic) for key, text, ic in CATEGORIES]]
SHEET_Y = 104


def browse(selected="all"):
    """Bottom sheet over Home: three shortcuts and the six categories, with counts."""
    objs = home(selected)
    objs += [container(0, 0, 480, 480, BG, 0, opacity=200, role="scrim"),
             touch(0, 0, 480, SHEET_Y, "drawer:close", "button_sheet_close"),
             container(0, SHEET_Y, 480, 480 - SHEET_Y + 32, RAISED, 32, role="sheet", name="sheet"),
             container(216, SHEET_Y + 10, 48, 5, TEXT3, 3, name="sheet_handle"),
             label(32, SHEET_Y + 26, 300, "BROWSE", "medium", 18, TEXT2, name="sheet_title")]
    for i, (key, text, ic) in enumerate(BROWSE):
        x, y = 24 + (i % 3) * 148, SHEET_Y + 60 + (i // 3) * 96
        count = len(filtered(LIBRARY, key))
        active = key == selected
        objs += [button(x, y, 136, 88, bg=CARD, radius=20, border=ACCENT if active else None,
                        bw=3 if active else 0, action=f"filter:{key}", name=f"category_{key}"),
                 icon(x + 16, y + 14, ic, 32, "orange" if active else "white", f"category_{key}_icon"),
                 label(x + 64, y + 20, 56, str(count), "sans", 16, TEXT2, "right",
                       name=f"category_{key}_count"),
                 label(x + 16, y + 54, 108, text, "sans", 18, TEXT, name=f"category_{key}_label")]
    return objs


def quick_switch(index=1):
    app = LIBRARY[index]
    objs = home()
    objs += [container(0, 0, 480, 480, BG, 0, opacity=210, role="scrim"),
             container(24, 48, 432, 372, RAISED, 32, border=LINE, bw=2, name="switch_card"),
             label(48, 68, 240, "MY APPS", "medium", 18, TEXT2, name="switch_filter", ellipsis=True),
             label(328, 68, 104, f"{index + 1:02d}/{len(LIBRARY):02d}", "medium", 18, TEXT2, "right",
                   name="switch_position"),
             tile(180, 100, app, 120, "switch_tile"),
             label(48, 234, 384, app["name"], "medium", 28, TEXT, "center", name="switch_name", ellipsis=True),
             label(48, 274, 384, row_detail(app), "sans", 18, TEXT2, "center", name="switch_detail",
                   ellipsis=True),
             progress(72, 314, 336, 8, 0, name="switch_hold"),
             label(48, 342, 192, "AI", "medium", 18, TEXT, "center"),
             label(48, 366, 192, "Next app", "sans", 16, TEXT2, "center"),
             label(240, 342, 192, "Hold AI", "medium", 18, TEXT, "center"),
             label(240, 366, 192, "Open it", "sans", 16, TEXT2, "center"),
             container(239, 344, 2, 42, DIVIDER),
             touch(24, 48, 432, 372, "qs:open", "button_switch_open")]
    return objs


# --------------------------------------------------------------------------
# Download (keypad) and Develop
# --------------------------------------------------------------------------
KEYPAD = [["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"], ["del", "0", "go"]]


def download(digits="", looking=False, error=""):
    objs = header("DOWNLOAD", "download", "page_download",
                  right=("qr", "qr:ideas", "button_qr_ideas"))
    objs.append(container(16, 88, 448, 68, CARD, 20, border=ACCENT if error else None,
                          bw=2 if error else 0, name="id_card"))
    if error or looking:
        objs += [label(32, 95, 416, digits, "dot", 22, TEXT, "center", name="id_digits_small"),
                 label(32, 125, 416, error or "Looking up…", "sans", 16, ACCENT if error else TEXT2,
                       "center", name="id_status_small")]
    elif digits:
        objs.append(label(32, 99, 416, digits, "dot", 40, TEXT, "center", name="id_digits"))
    else:
        objs.append(label(32, 111, 416, "Type the app ID", "sans", 18, TEXT2, "center", name="id_status"))
    for r, row in enumerate(KEYPAD):
        for c, key in enumerate(row):
            x, y = 16 + c * 152, 164 + r * 78
            if key == "del":
                b = button(x, y, 144, 72, bg=RAISED, radius=20, icon="assets/icons/backspace-32-white.png",
                           action="key:del", name="key_del")
            elif key == "go":
                b = button(x, y, 144, 72, "Go", "medium", 22, WHITE, ACCENT, radius=20,
                           action="key:go", name="key_go")
            else:
                b = button(x, y, 144, 72, key, "dot", 28, TEXT, TILE, radius=20,
                           action=f"key:{key}", name=f"key_{key}")
            b["touch_class"] = "numpad"
            objs.append(b)
    return objs


def develop(usb=True, agent=True):
    ready = usb and agent
    status = ("USB connected · Agent ready" if ready else
              "USB connected · Waiting for agent" if usb else "Plug in a USB cable")
    objs = header("DEVELOP", "develop", "page_develop")
    objs += link_row(100, "Vibe-code an app", "Scan for the step-by-step guide", "code",
                     "qr:develop", "button_vibe_guide")
    objs += [container(16, 192, 448, 104, CARD, 20, border=ACCENT if ready else None, bw=2 if ready else 0,
                       name="develop_usb_card"),
             icon(36, 208, "usb", 32, "white" if usb else "grey"),
             label(84, 205, 360, "Install over USB", "medium", 22, TEXT),
             status_dot(84, 241, ACCENT if ready else TEXT2 if usb else TEXT3, "develop_status_dot"),
             label(102, 236, 342, status, "sans", 16, ACCENT if ready else TEXT2, name="develop_status"),
             label(84, 260, 360, "Ask your agent to install it here.", "sans", 16, TEXT2)]
    objs += link_row(308, "Share your app", "Publish it on Mosaico Ideas", "share",
                     "qr:ideas", "button_share")
    objs.append(label(24, 410, 432, "To come back: hold AI, press power twice.", "sans", 16, TEXT3,
                      "center"))
    return objs


# --------------------------------------------------------------------------
# App detail: two vertical pages (actions, then About)
# --------------------------------------------------------------------------
DETAIL = {
    # mode: (status, dot colour, primary text, primary action, primary icon, left secondary)
    "current": ("Current app", ACCENT, "Open app", "app:run", "play", ("Update", "app:update", "refresh")),
    "local": ("On this device", TEXT2, "Open app", "app:run", "play", ("Update", "app:update", "refresh")),
    "remote_new": ("Not on this device", TEXT3, "Download & open", "store:run", "download",
                   ("Save", "store:keep", "download")),
    "remote_update": ("Update available", ACCENT, "Update & open", "store:run", "refresh",
                      ("Save", "store:keep", "download")),
    "nospace": ("Not enough space", ACCENT, "Free up space", "go:storage", "storage", None),
}


def detail_lines(app, mode):
    if mode == "remote_update":
        local = BY_ID[app["id"]]["version"]
        return f"{row_detail(app)} · v{local}", f"New v{STORE_UPDATES[app['id']]} · {app['size']}"
    if mode == "nospace":
        return f"{row_detail(app)} · v{app['version']}", f"Needs {app['size']} · 0.4 MB free"
    return f"{row_detail(app)} · v{app['version']}", f"{app['size']} · ID {app['id']}"


def detail_header(app):
    fav = app["id"] in FAV
    return header(app["name"], "detail", font="dot", size=22,
                  right=("star_fill" if fav else "star", "app:favorite", "button_favorite",
                         "orange" if fav else "white"))


def detail(mode="current", app=None):
    app = app or BY_ID[{"current": CURRENT, "local": "100012", "remote_new": "238114",
                        "remote_update": "100006", "nospace": "238114"}[mode]]
    status, dot, ptext, paction, picon, second = DETAIL[mode]
    meta, meta2 = detail_lines(app, mode)
    objs = detail_header(app)
    objs += [tile(24, 100, app, 96, "detail_tile"),
             status_dot(136, 114, dot, "detail_status_dot"),
             label(154, 106, 302, status, "medium", 22, ACCENT if dot == ACCENT else TEXT,
                   name="detail_status", ellipsis=True),
             label(136, 140, 320, meta, "sans", 18, TEXT2, name="detail_meta", ellipsis=True),
             label(136, 166, 320, meta2, "sans", 18, ACCENT if mode == "nospace" else TEXT2,
                   name="detail_meta2", ellipsis=True),
             primary(16, 212, 448, ptext, paction, "button_primary", picon)]
    if second:
        objs.append(secondary(16, 308, 216, second[0], second[1], "button_secondary", second[2]))
        objs.append(secondary(248, 308, 216, "QR code", "qr:app", "button_qr_app", "qr"))
    else:
        objs.append(secondary(16, 308, 448, "QR code", "qr:app", "button_qr_app", "qr"))
    objs += [label(160, 408, 160, "About this app", "sans", 16, TEXT2, "center"),
             icon(230, 432, "chevron_down", 20, "dim"),
             touch(160, 396, 160, 84, "detail:2", "button_more")]
    return objs


def detail_about(mode="current", app=None, hold=0.0):
    app = app or BY_ID[{"current": CURRENT, "local": "100012", "remote_new": "238114"}[mode]]
    local = mode in ("current", "local")
    lines, _ = wrap_lines(app["summary"], "sans", 18, 432, 3)
    objs = detail_header(app)
    objs.append(label(24, 100, 432, "\n".join(lines), "sans", 18, TEXT, name="detail_summary",
                      h=line_h("sans", 18, 3), wrap=True))
    for i, (key, value) in enumerate((("Version", f"v{app['version']}"), ("Size", app["size"]),
                                      ("Source", "Official" if app["official"] else "Community"))):
        x = 24 + i * 144
        objs += [label(x, 184, 136, key, "sans", 16, TEXT2),
                 label(x, 206, 136, value, "sans", 18, TEXT, name=f"detail_{key.lower()}")]
    objs += [row_button(248, "qr:app", "button_qr_row"),
             icon(36, 274, "qr", 20, "white"),
             label(72, 259, 336, "Show QR code", "medium", 22, TEXT),
             label(72, 289, 336, "Open this app on your phone", "sans", 16, TEXT2),
             icon(424, 274, "chevron", 20, "dim")]
    if local:
        objs += danger(360, "Keep holding…" if hold else "Hold to delete", "hold:delete", "button_delete",
                       fill=hold)
    else:
        objs.append(label(24, 392, 432, "Not on this device yet.", "sans", 16, TEXT3, "center"))
    return objs


def qr_full(name="app-100001", title="Pixel Pet", url="mosaico-ideas.espressif.com/app/100001"):
    return [image(58, 14, f"assets/qr/{name}.png", name="qr_full_code", w=363, h=363, qr=True),
            label(24, 386, 432, title, "medium", 22, TEXT, "center", name="qr_full_title", ellipsis=True),
            label(24, 416, 432, url, "sans", 16, TEXT2, "center", name="qr_full_url", ellipsis=True),
            label(24, 440, 432, "Tap anywhere to close", "sans", 16, TEXT3, "center"),
            touch(0, 0, 480, 480, "back", "button_qr_close")]


# --------------------------------------------------------------------------
# Progress and results
# --------------------------------------------------------------------------
PROGRESS = {
    "agent": ("FROM YOUR AI AGENT · USB", "Installing your app", "hello_world · v0.2.1", 46,
              "1.31 of 2.85 MB · 236 KB/s", "Step 1 of 2 · Receiving", False),
    "download": ("FROM MOSAICO IDEAS", "Downloading", "Retro Snake · v1.0.3", 62,
                 "0.56 of 0.90 MB · 512 KB/s", "File 2 of 3", True),
    "install": ("FROM YOUR LIBRARY", "Switching apps", "Weather Station · v2.0.1", 81,
                "1.94 of 2.40 MB · 1.6 MB/s", "Step 2 of 2 · Checking", False),
    "update": ("FROM MOSAICO IDEAS", "Resuming update", "Voice Notes · v1.1.0", 38,
               "1.22 of 3.20 MB · 512 KB/s", "Continued where it stopped", True),
}


def progress_page(kind="download"):
    caption, title, detail_text, pct, size_text, step, cancel = PROGRESS[kind]
    objs = [label(24, 36, 432, caption, "medium", 18, TEXT2, "center", name="progress_caption"),
            label(24, 62, 432, title, "medium", 28, TEXT, "center", name="progress_title"),
            label(24, 100, 432, detail_text, "sans", 18, TEXT2, "center", name="progress_detail", ellipsis=True),
            image(224, 148, "assets/anim/spin32-00.png", name="progress_spinner"),
            label(24, 188, 432, f"{pct}%", "dot", 88, TEXT, "center", name="progress_percent"),
            progress(40, 304, 400, 12, pct),
            label(24, 326, 432, size_text, "sans", 16, TEXT2, "center", name="progress_bytes"),
            label(24, 350, 432, step, "sans", 16, TEXT2, "center", name="progress_step")]
    if cancel:
        objs.append(secondary(16, 388, 448, "Cancel", "store:cancel", "button_cancel"))
    else:
        objs.append(label(24, 410, 432, "Keep the device powered on.", "sans", 16, TEXT3, "center"))
    return objs


RESULTS = {
    # kind: (pictogram, title, caption, detail, left button, right button)
    "installed": ("check", "App installed", "Weather Station · v2.0.1", "Opening in 3 s",
                  ("Stay here", "result:stay"), ("Open now", "result:open")),
    "saved": ("saved", "Saved to My apps", "Retro Snake · v1.0.3", "Open it any time from the list.",
              ("Open now", "result:open"), ("Done", "result:done")),
    "updated": ("check", "Update complete", "Voice Notes · v1.1.0", "Your settings were kept.",
                ("Open now", "result:open"), ("Done", "result:done")),
    "failed": ("cross", "Couldn't download", "Retro Snake · v1.0.3", "The connection dropped.\nCheck Wi-Fi and try again.",
               ("Done", "result:done"), ("Try again", "result:retry")),
    "nospace": ("full", "Not enough storage", "Retro Snake needs 0.9 MB", "Delete an app you don't use\nto make room.",
                ("Cancel", "result:done"), ("Free up space", "go:storage")),
    "battery": ("battery", "Battery low", "Charge to 20% to switch apps", "Switching writes to flash and\nmust not be interrupted.",
                None, ("OK", "result:done")),
}


def result(kind="installed", elapsed=1):
    pic, title, caption, detail_text, left, right = RESULTS[kind]
    objs = [hero(180, 56, pic, 120, "result_hero"),
            label(24, 196, 432, title, "medium", 28, TEXT, "center", name="result_title"),
            label(24, 236, 432, caption, "sans", 18, TEXT2, "center", name="result_caption", ellipsis=True),
            label(24, 264, 432, detail_text, "sans", 18, TEXT2 if kind != "installed" else TEXT, "center",
                  h=line_h("sans", 18, 2), name="result_detail")]
    if kind == "installed":
        objs += [container(210 + i * 24, 300, 12, 12, ACCENT if i < elapsed else TILE, 6,
                           name=f"result_dot_{i + 1}") for i in range(3)]
    if left:
        objs.append(secondary(16, 388, 216, left[0], left[1], "button_result_left"))
        objs.append(primary(248, 388, 216, right[0], right[1], "button_result_right"))
    else:
        objs.append(primary(16, 388, 448, right[0], right[1], "button_result_right"))
    return objs


def launching(app=None, running=False):
    app = app or BY_ID["100009"]
    if running:
        return [tile(180, 92, app, 120, "running_tile"),
                label(24, 232, 432, app["name"], "medium", 28, TEXT, "center", name="running_title",
                      ellipsis=True),
                label(24, 272, 432, "Your app is running.", "sans", 18, TEXT2, "center"),
                label(24, 388, 432, "To come back to Vibe Mode:\nhold AI and press power twice.",
                      "sans", 16, TEXT3, "center")]
    return [tile(180, 112, app, 120, "launch_tile"),
            label(24, 256, 432, f"Opening {app['name']}", "medium", 28, TEXT, "center", name="launch_title",
                  ellipsis=True),
            label(24, 296, 432, "Restarting…", "sans", 18, TEXT2, "center"),
            image(224, 344, "assets/anim/spin32-00.png", name="launch_spinner")]


def boot():
    return [hero(180, 140, "vibe", 120, "boot_logo"),
            label(24, 284, 432, "VIBE MODE", "dot", 28, TEXT, "center")]


# --------------------------------------------------------------------------
# Help
# --------------------------------------------------------------------------
def help_page():
    objs = header("HELP", "help", "page_help")
    vp = (16, 92, 448, 388)
    objs.append({"type": "list_viewport", "x": 16, "y": 92, "w": 448, "h": 388, "name": "help",
                 "item_height": ROW_PITCH, "row_template": None, "count": 5})
    rows = []
    for i, (key, ic, title) in enumerate(HELP_TOPICS + [("replay", "replay", "Replay the intro")]):
        y = 100 + i * ROW_PITCH
        rows += [row_button(y, "guide:1" if key == "replay" else f"help:{key}", f"button_help_{key}"),
                 icon(36, y + 26, "refresh" if key == "replay" else ic, 20, "white"),
                 label(72, y + 23, 320, title, "medium", 22, TEXT),
                 icon(424, y + 26, "chevron" if key == "replay" else "qr", 20,
                      "dim" if key == "replay" else "grey")]
    return objs + clipped(rows, vp, "help")


# --------------------------------------------------------------------------
# Wi-Fi
# --------------------------------------------------------------------------
NET_Y, NET_H = 222, 242


def network_row(y, ssid, secured, signal, viewport):
    return clipped([container(16, y, 448, ROW_H, CARD, 18, role="row"),
                    icon(36, y + 26, "lock" if secured else "wifi", 20, "grey", "networks_icon"),
                    label(72, y + 11, 336, ssid, "medium", 22, TEXT, name="networks_title", ellipsis=True),
                    label(72, y + 41, 336, f"{'Secured' if secured else 'Open'} · {signal} signal", "sans", 16,
                          TEXT2, name="networks_detail"),
                    icon(424, y + 26, "chevron", 20, "dim")], viewport, "networks")


def wifi(state="connected", pending=""):
    """state: connected | off | connecting. ``pending`` names the task that resumes."""
    objs = header("WI-FI", "wifi", right=("refresh", "wifi:scan", "button_scan"))
    if state == "connected":
        objs += [row_button(96, "go:wifi_network", "button_wifi_current", h=80),
                 icon(36, 120, "wifi", 32, "orange", "wifi_icon"),
                 label(84, 109, 324, "Studio-5G", "medium", 22, TEXT, name="wifi_connection", ellipsis=True),
                 label(84, 139, 324, "Connected · 192.168.1.20", "sans", 16, TEXT2, name="wifi_detail"),
                 icon(424, 126, "chevron", 20, "dim")]
        others = [n for n in NETWORKS if n[0] != "Studio-5G"]
    else:
        connecting = state == "connecting"
        objs += [container(16, 96, 448, 80, CARD, 20, border=ACCENT if pending or connecting else None,
                           bw=2 if pending or connecting else 0, name="wifi_card"),
                 image(36, 120, "assets/anim/spin32-00.png", name="wifi_spinner") if connecting
                 else icon(36, 120, "wifi_off", 32, "grey", "wifi_icon"),
                 label(84, 109, 340, "Maker Lab" if connecting else "Not connected", "medium", 22, TEXT,
                       name="wifi_connection", ellipsis=True),
                 label(84, 139, 340, "Connecting…" if connecting else pending or "Pick a network below",
                       "sans", 16, ACCENT if pending or connecting else TEXT2, name="wifi_detail", ellipsis=True)]
        others = NETWORKS
    objs.append(section(192, f"{'OTHER NETWORKS' if state == 'connected' else 'NETWORKS'} · {len(others)}",
                        "wifi_section"))
    vp = (16, NET_Y, 448, NET_H)
    objs.append({"type": "list_viewport", "x": 16, "y": NET_Y, "w": 448, "h": NET_H, "name": "networks",
                 "item_height": ROW_PITCH, "row_template": "networks_row", "count": len(others)})
    for i, (ssid, secured, signal) in enumerate(others[:4]):
        objs += network_row(NET_Y + i * ROW_PITCH, ssid, secured, signal, vp)
    return objs


def info_card(y, rows, name):
    """Read-only facts: label on the left, value on the right, 64 px per row."""
    objs = [container(16, y, 448, 64 * len(rows), CARD, 20, name=name)]
    for i, (key, value, value_name) in enumerate(rows):
        ry = y + i * 64
        objs += [label(36, ry + 21, 160, key, "sans", 18, TEXT2),
                 label(196, ry + 21, 248, value, "sans", 18, TEXT, "right", name=value_name, ellipsis=True)]
        if i:
            objs.append(container(36, ry, 408, 1, DIVIDER))
    return objs


def wifi_network():
    objs = header("Studio-5G", "wifi_network", font="dot", size=22)
    objs += info_card(96, [("Signal", "Strong", "network_signal"), ("Security", "WPA2", "network_security"),
                           ("IP address", "192.168.1.20", "network_ip")], "network_card")
    objs.append(label(24, 304, 432, "Apps lose Wi-Fi until you reconnect.", "sans", 16, TEXT2, "center"))
    objs += danger(360, "Hold to forget", "hold:forget", "button_forget", "wifi_off")
    return objs


def entry_page(page, title, display, placeholder, note, toggle=True, note_color=TEXT2, spinner=False):
    """Keyboard page: value card, one note line, the native keyboard. GO saves."""
    objs = header(title, page)
    objs.append(container(16, 92, 448, 72, CARD, 20, name=f"{page}_card"))
    objs.append(label(36, 115, 332 if toggle else 408, display or placeholder, "medium", 22,
                      TEXT if display else TEXT3, name=f"{page}_display", ellipsis=True))
    if toggle:
        objs += [icon(408, 112, "eye", 32, "white", f"{page}_eye"),
                 touch(380, 86, 84, 84, f"{page}:toggle", f"button_toggle_{page}")]
    if spinner:
        objs.append(image(32, 176, "assets/anim/spin32-00.png", name=f"{page}_spinner"))
    objs.append(label(72 if spinner else 32, 182, 384 if spinner else 416, note, "sans", 16, note_color,
                      name=f"{page}_note", ellipsis=True))
    objs.append(keyboard(222, f"{page}_keyboard"))
    return objs


def password(state="typing"):
    if state == "connecting":
        return entry_page("password", "PASSWORD", "••••••••••", "Type the password",
                          "Connecting to Maker Lab…", note_color=ACCENT, spinner=True)
    if state == "error":
        return entry_page("password", "PASSWORD", "•••••••••", "Type the password",
                          "Wrong password. Try again.", note_color=ACCENT)
    return entry_page("password", "PASSWORD", "", "Type the password", "For Maker Lab · 8 or more characters")


# --------------------------------------------------------------------------
# Device and its sub-pages
# --------------------------------------------------------------------------
def device():
    objs = header("DEVICE", "device", "page_device")
    vp = (16, 92, 448, 388)
    objs.append({"type": "list_viewport", "x": 16, "y": 92, "w": 448, "h": 388, "name": "device",
                 "item_height": ROW_PITCH, "row_template": None, "count": 7})
    used = sum(mb(a) for a in LIBRARY)
    rows = [section(100, "SHARED WITH APPS")]
    rows += settings_row(128, "wifi", "Wi-Fi", "Studio-5G", "go:wifi", "button_device_wifi", "device_wifi")
    rows += settings_row(208, "pin", "City", "Shanghai", "go:city", "button_device_city", "device_city")
    rows += settings_row(288, "robot", "Mosaico AI", "On · included", "go:token", "button_device_ai", "device_ai")
    rows.append(section(376, "THIS DEVICE"))
    rows += settings_row(404, "refresh", "App updates", f"{len(STORE_UPDATES)} available", "go:updates",
                         "button_device_updates", "device_updates", ACCENT)
    rows += settings_row(484, "storage", "App storage", f"{used:.1f} of {NAND_CAPACITY_MB:.0f} MB used",
                         "go:storage", "button_device_storage", "device_storage")
    rows += settings_row(564, "key", "Wi-Fi link", "Ready · 192.168.1.20", "go:wifi_link",
                         "button_device_link", "device_link")
    rows += settings_row(644, "info", "Vibe Mode 0.3.0", "MAC 30:ED:A0:F4:60:56", None, "device_about",
                         "device_about")
    rows.append(label(24, 732, 432, "Downloads send the MAC and version\nto check compatibility.",
                      "sans", 16, TEXT3, "center"))
    return objs + clipped(rows, vp, "device")


def wifi_link(visible=False):
    objs = header("WI-FI LINK", "wifi_link")
    objs += [label(24, 96, 432, "Your computer can reach this device\nover Wi-Fi instead of USB.", "sans", 18,
                   TEXT2, h=line_h("sans", 18, 2)),
             container(16, 156, 448, 160, CARD, 20),
             label(36, 172, 300, "Address", "sans", 16, TEXT2),
             label(36, 194, 408, "192.168.1.20:7777", "medium", 22, TEXT, name="wifilink_endpoint"),
             container(36, 236, 408, 1, DIVIDER),
             label(36, 252, 300, "Pairing code", "sans", 16, TEXT2),
             label(36, 274, 332, TOKEN[:12] + "…" + TOKEN[-4:] if visible else "•••• •••• •••• 5a13",
                   "medium", 22, TEXT, name="wifilink_token", ellipsis=True),
             icon(408, 262, "eye_off" if visible else "eye", 32, "white", "wifilink_eye"),
             touch(380, 236, 84, 84, "wifi_link:toggle", "button_toggle_pairing"),
             label(24, 336, 432, "Your agent pairs over USB on its own.\nNever share this code.", "sans", 16,
                   TEXT3, "center", h=line_h("sans", 16, 2))]
    return objs


UPDATE_APPS = [BY_ID[i] for i in STORE_UPDATES]


def update_row(y, app, sub, hi, viewport):
    return clipped([container(16, y, 448, ROW_H, CARD, 18, role="row"),
                    tile(24, y + 8, app, 56, "updates_tile"),
                    label(92, y + 11, 316, app["name"], "medium", 22, TEXT, name="updates_name", ellipsis=True),
                    label(92, y + 41, 316, sub, "sans", 16, TEXT2, name="updates_sub", ellipsis=True),
                    label(92, y + 41, 316, hi, "sans", 16, ACCENT, name="updates_sub_hi"),
                    icon(424, y + 26, "chevron", 20, "dim")], viewport, "updates")


def updates(state="available"):
    """available | running | done | offline"""
    objs = header("UPDATES", "updates")
    if state in ("done", "offline"):
        offline = state == "offline"
        objs += [hero(180, 100, "wifi" if offline else "check", 120, "updates_hero"),
                 label(24, 240, 432, "Can't check now" if offline else "All up to date", "medium", 28, TEXT,
                       "center", name="updates_title"),
                 label(24, 280, 432, "Connect Wi-Fi to look for updates." if offline else "Checked just now.",
                       "sans", 18, TEXT2, "center", name="updates_note")]
        if offline:
            objs.append(primary(16, 372, 448, "Connect Wi-Fi", "go:wifi", "button_updates_wifi", "wifi"))
        return objs
    running = state == "running"
    objs.append(label(24, 96, 432, "Updating 1 of 2 in the background" if running else
                      f"{len(UPDATE_APPS)} apps can be updated", "sans", 18, ACCENT if running else TEXT2,
                      name="updates_summary"))
    vp = (16, 128, 448, 232)
    objs.append({"type": "list_viewport", "x": 16, "y": 128, "w": 448, "h": 232, "name": "updates",
                 "item_height": ROW_PITCH, "row_template": "updates_row", "count": len(UPDATE_APPS)})
    for i, app in enumerate(UPDATE_APPS):
        new = STORE_UPDATES[app["id"]]
        if running:
            sub, hi = (" ", "Downloading · 40%") if i == 0 else (f"Waiting · v{new}", " ")
        else:
            sub, hi = f"v{app['version']} to v{new} · {app['size']}", " "
        objs += update_row(128 + i * ROW_PITCH, app, sub, hi, vp)
    if running:
        objs.append(secondary(16, 372, 448, "Keep using Vibe Mode", "back", "button_updates_continue"))
    else:
        objs.append(primary(16, 372, 448, "Update all", "updates:all", "button_update_all", "download"))
    return objs


STORAGE_SORTED = sorted(LIBRARY, key=lambda a: -mb(a))


def storage_row(y, app, viewport):
    return clipped([container(16, y, 448, ROW_H, CARD, 18, role="row"),
                    tile(24, y + 8, app, 56, "storage_tile"),
                    label(92, y + 11, 224, app["name"], "medium", 22, TEXT, name="storage_name", ellipsis=True),
                    label(92, y + 41, 224, row_detail(app), "sans", 16, TEXT2, name="storage_sub", ellipsis=True),
                    label(316, y + 25, 96, app["size"], "sans", 18, TEXT, "right", name="storage_size"),
                    icon(424, y + 26, "chevron", 20, "dim")], viewport, "storage")


def storage(full=False):
    used = NAND_CAPACITY_MB - 0.5 if full else sum(mb(a) for a in LIBRARY)
    objs = header("STORAGE", "storage")
    objs += [label(24, 96, 432, f"{used:.1f} MB of {NAND_CAPACITY_MB:.0f} MB used", "medium", 22, TEXT,
                   name="storage_summary"),
             progress(24, 132, 432, 12, round(used / NAND_CAPACITY_MB * 100), "storage_bar",
                      ACCENT if full else TEXT),
             label(24, 154, 432, "Almost full · delete an app to make room" if full else
                   f"{NAND_CAPACITY_MB - used:.1f} MB free · {len(LIBRARY)} apps", "sans", 16,
                   ACCENT if full else TEXT2, name="storage_legend"),
             section(194, "LARGEST FIRST · TAP TO DELETE")]
    vp = (16, 224, 448, 248)
    objs.append({"type": "list_viewport", "x": 16, "y": 224, "w": 448, "h": 248, "name": "storage",
                 "item_height": ROW_PITCH, "row_template": "storage_row", "count": len(LIBRARY)})
    for i, app in enumerate(STORAGE_SORTED[:4]):
        objs += storage_row(224 + i * ROW_PITCH, app, vp)
    return objs


def link_line(y, usb, agent, name, idle):
    ready = usb and agent
    text = "USB connected · Agent ready" if ready else "USB connected · Waiting for agent" if usb else idle
    return [icon(32, y, "usb", 20, "orange" if ready else "grey"),
            label(62, y - 1, 394, text, "sans", 16, ACCENT if ready else TEXT2, name=name)]


def city(usb=True, agent=True):
    objs = header("CITY", "city")
    objs += [container(16, 96, 448, 104, CARD, 20),
             label(36, 112, 408, "Shared with all apps", "sans", 16, TEXT2),
             label(36, 140, 408, "Shanghai", "medium", 28, TEXT, name="city_value", ellipsis=True)]
    objs += link_line(222, usb, agent, "city_link", "Plug in USB to set it from your computer")
    objs += [label(24, 256, 432, "Ask your agent to set it,\nor type it on this device.", "sans", 18, TEXT2,
                   h=line_h("sans", 18, 2)),
             secondary(16, 372, 448, "Type on device", "go:city_input", "button_city_type")]
    return objs


TOKEN_STATES = {
    "mosaico": (ACCENT, "Mosaico AI is on", "Included with this device", "Every app can use it."),
    "own": (ACCENT, "Using your own key", "Key ends in 4c8e", "Every app can read it."),
    "none": (TEXT3, "Mosaico AI is off", "Apps can't use AI right now", "Turning it on is free."),
}


def token(kind=AI_TOKEN_KIND, usb=True, agent=True):
    dot, title, sub, note = TOKEN_STATES[kind]
    objs = header("MOSAICO AI", "token")
    objs += [container(16, 96, 448, 108, CARD, 20, name="token_card"),
             status_dot(36, 117, dot, "token_dot"),
             label(56, 109, 388, title, "medium", 22, TEXT, name="token_title"),
             label(36, 143, 408, sub, "sans", 16, TEXT2, name="token_sub"),
             label(36, 169, 408, note, "sans", 16, TEXT2, name="token_note")]
    objs += link_line(220, usb, agent, "token_link", "Or plug in USB to set a key from your computer")
    if kind == "mosaico":
        objs.append(secondary(16, 252, 448, "Use my own key", "go:own_key", "button_own_key"))
        objs += danger(360, "Hold to turn off", "hold:turnoff", "button_turn_off", "power")
    elif kind == "own":
        objs.append(secondary(16, 252, 448, "Edit key", "go:own_key", "button_own_key"))
        objs += danger(360, "Hold to remove key", "hold:clear", "button_clear_key")
    else:
        objs.append(primary(16, 252, 448, "Turn on Mosaico AI", "token:claim", "button_claim", "robot"))
        objs.append(secondary(16, 348, 448, "Use my own key", "go:own_key", "button_own_key"))
    return objs


# --------------------------------------------------------------------------
# First-run guide (5 steps)
# --------------------------------------------------------------------------
GUIDE_STEPS = 5


def guide_chrome(step):
    objs = []
    x0 = (W - (GUIDE_STEPS * 8 + (GUIDE_STEPS - 1) * 8 + 12)) // 2
    x = x0
    for i in range(1, GUIDE_STEPS + 1):
        w = 20 if i == step else 8
        objs.append(container(x, 32, w, 8, ACCENT if i == step else TILE, 4, name=f"guide_dot_{i}"))
        x += w + 8
    if step < GUIDE_STEPS:
        objs += [label(388, 26, 60, "Skip", "medium", 18, TEXT2, "right"),
                 touch(372, 6, 96, 84, "guide:done", "button_guide_skip")]
    return objs


def guide_device(x, y):
    """Front view of the device built from containers (no bitmap in flash).

    Matches the product photo: cream body, black screen with large rounded
    corners, the orange AI key on the top edge at about 3/4 of the width and two
    grey keys on the bottom edge at 1/4 and 3/4; the right one is power. The
    two gesture keys get an orange ring; the body covers the ring's inner half.
    """
    hw = TOKENS["hardware"]
    ai_key, keys = (120, 15, 34, 15), [(46, 170, 34, 15), (120, 170, 34, 15)]
    objs = [container(x + kx - 6, y + ky - 6, kw + 12, kh + 12, None, 9, border=ACCENT, bw=3, name=name)
            for (kx, ky, kw, kh), name in ((ai_key, "guide_ring_ai"), (keys[1], "guide_ring_power"))]
    objs.append(container(x + ai_key[0], y + ai_key[1], ai_key[2], ai_key[3], hw["ai_key"], 4))
    for kx, ky, kw, kh in keys:
        objs.append(container(x + kx, y + ky, kw, kh, hw["key"], 4, border=hw["key_edge"], bw=1))
    objs.append(container(x + 26, y + 24, 148, 152, hw["body"], 36, border=hw["body_edge"], bw=2))
    objs.append(container(x + 40, y + 38, 120, 124, "#080808", 26))
    for i, (cx, cy) in enumerate([(84, 82), (90, 94), (96, 106), (102, 118), (108, 106), (114, 94), (120, 82)]):
        objs.append(container(x + cx - 3, y + cy - 3, 6, 6, ACCENT if i == 3 else TEXT, 3))
    return objs


def guide_nav(step, last_text="Next"):
    nxt = f"guide:{step + 1}" if step < GUIDE_STEPS else "guide:done"
    if step == 1:
        return [primary(16, 388, 448, "Get started", nxt, "button_guide_next")]
    return [secondary(16, 388, 216, "Back", f"guide:{step - 1}", "button_guide_back"),
            primary(248, 388, 216, last_text, nxt, "button_guide_next")]


def guide(step):
    objs = guide_chrome(step)
    if step == 1:
        objs += [hero(180, 76, "vibe", 120, "guide_hero"),
                 label(24, 216, 432, "A safe home\nfor your apps", "medium", 28, TEXT, "center"),
                 label(24, 292, 432, "Your AI agent installs apps here.\nOpen or switch them any time.",
                       "sans", 18, TEXT2, "center")]
    elif step == 2:
        objs.append(label(24, 64, 432, "Coming back here", "medium", 28, TEXT, "center"))
        objs += guide_device(12, 124)
        for i, (head, sub) in enumerate((("Hold AI", "Top edge, right"), ("Press power twice", "Bottom edge, right"),
                                         ("Let go of AI", "Vibe Mode opens"))):
            y = 150 + i * 66
            objs += [label(232, y, 24, str(i + 1), "dot", 22, ACCENT),
                     label(262, y + 2, 194, head, "sans", 18, TEXT),
                     label(262, y + 26, 194, sub, "sans", 16, TEXT2)]
    elif step == 3:
        objs.append(label(24, 64, 432, "Get apps two ways", "medium", 28, TEXT, "center"))
        for i, (ic, head, body) in enumerate((("download", "Download", "Type an app ID from Mosaico Ideas."),
                                              ("code", "Develop", "Ask your AI agent to build one. It installs over USB."))):
            x = 16 + i * 232
            objs += [container(x, 120, 216, 200, CARD, 24),
                     icon(x + 20, 140, ic, 32, "orange"),
                     label(x + 20, 188, 176, head, "medium", 22, TEXT),
                     label(x + 20, 224, 176, body, "sans", 16, TEXT2, h=line_h("sans", 16, 5), wrap=True)]
    elif step == 4:
        objs.append(label(24, 64, 432, "The AI key", "medium", 28, TEXT, "center"))
        for i, (key, action) in enumerate((("AI", "Go back"), ("AI ×2", "Switch apps"),
                                           ("Hold AI", "Open the picked app"))):
            y = 124 + i * 68
            objs += [container(24, y, 128, 52, TILE, 26),
                     label(24, y + 15, 128, key, "medium", 18, TEXT, "center"),
                     label(172, y + 15, 284, action, "sans", 18, TEXT)]
        objs.append(label(24, 334, 432, "It's the orange key on the top edge.", "sans", 16, TEXT2, "center"))
    else:
        objs += [hero(180, 76, "wifi", 120, "guide_hero"),
                 label(24, 216, 432, "Connect Wi-Fi", "medium", 28, TEXT, "center"),
                 label(24, 258, 432, "To download apps, get updates\nand turn on Mosaico AI.", "sans", 18, TEXT2,
                       "center")]
        return objs + [secondary(16, 388, 216, "Later", "guide:done", "button_guide_later"),
                       primary(248, 388, 216, "Connect", "guide:wifi", "button_guide_wifi", "wifi")]
    return objs + guide_nav(step)


# --------------------------------------------------------------------------
# Prototype-only states and row templates
# --------------------------------------------------------------------------
def prototype_extras():
    extras = [
        {"id": "develop-unplugged", "page": "develop", "objects": develop(False, False)},
        {"id": "boot", "page": "boot", "objects": boot()},
    ]
    vp = (16, 0, 448, 80)
    templates = {
        "apps_row": relative(app_row(0, LIBRARY[1], vp), 16, 0),
        "networks_row": relative(network_row(0, "Maker Lab", True, "Good", vp), 16, 0),
        "updates_row": relative(update_row(0, UPDATE_APPS[0], "v1.0.0 to v1.1.0", " ", vp), 16, 0),
        "storage_row": relative(storage_row(0, LIBRARY[0], vp), 16, 0),
    }
    return extras, templates


# --------------------------------------------------------------------------
# States (one mockup each)
# --------------------------------------------------------------------------
def build_states():
    states = []

    def add(sid, page, title, objects, **meta):
        states.append({"id": sid, "page": page, "title": title, "objects": objects, **meta})

    for step in range(1, GUIDE_STEPS + 1):
        add(f"guide-{step}", "guide", f"Guide {step}/{GUIDE_STEPS}", guide(step))
    add("home", "home", "Home · recent first", home())
    add("home-favorites", "home", "Home · Favorites", home("favorites"))
    add("home-category", "home", "Home · Smart home", home("smart-home"))
    add("home-empty", "home", "Home · no apps", home(apps=[], wifi_on=False, low_battery=True, badge=None))
    add("home-favorites-empty", "home", "Home · no favorites",
        home("favorites", apps=[a for a in LIBRARY if a["id"] not in FAV], badge=None))
    add("home-category-empty", "home", "Home · empty category",
        home("motor", apps=[a for a in LIBRARY if a["category"] != "motor"], badge=None))
    add("home-hint", "home", "Home · AI hint", home(agent=False) + toast("Press AI twice to switch apps"))
    add("home-updating", "home", "Home · updating in background", home(badge="↓ 1/2"))
    add("browse", "home", "Browse · bottom sheet", browse("all"))
    add("quick-switch", "quick_switch", "Quick switch", quick_switch())
    add("download", "download", "Download · empty", download())
    add("download-typing", "download", "Download · typing", download("238114"))
    add("download-lookup", "download", "Download · looking up", download("238114", True))
    add("download-error", "download", "Download · not found", download("404040", False, "No app with this ID"))
    add("develop", "develop", "Develop · USB and agent ready", develop())
    add("develop-waiting", "develop", "Develop · waiting for agent", develop(True, False))
    add("detail-current", "detail", "Detail · current app", detail("current"), flow_page=1)
    add("detail-local", "detail", "Detail · on this device", detail("local"), flow_page=1)
    add("detail-remote", "detail", "Detail · from the store", detail("remote_new"), flow_page=1)
    add("detail-update", "detail", "Detail · update available", detail("remote_update"), flow_page=1)
    add("detail-nospace", "detail", "Detail · not enough space", detail("nospace"), flow_page=1)
    add("detail-about", "detail", "Detail page 2 · About", detail_about("local"), flow_page=2)
    add("detail-about-remote", "detail", "Detail page 2 · store app", detail_about("remote_new"), flow_page=2)
    add("detail-delete-hold", "detail", "Detail page 2 · holding delete", detail_about("local", hold=0.58),
        flow_page=2)
    add("qr-full", "qr", "QR code · full screen", qr_full())
    for kind, title in (("agent", "AI agent install"), ("download", "download"), ("install", "switch app"),
                        ("update", "resumed update")):
        add(f"progress-{kind}", "progress", f"Progress · {title}", progress_page(kind))
    for kind, title in (("installed", "installed"), ("saved", "saved"), ("updated", "updated"),
                        ("failed", "failed"), ("nospace", "no space"), ("battery", "low battery")):
        add(f"result-{kind}", "result", f"Result · {title}", result(kind))
    add("help", "help", "Help · topics", help_page())
    add("help-qr", "qr", "Help · topic QR", qr_full("help-start", "Getting started", QR_URLS["help-start"]))
    add("wifi", "wifi", "Wi-Fi · connected", wifi())
    add("wifi-off", "wifi", "Wi-Fi · not connected", wifi("off"))
    add("wifi-pending", "wifi", "Wi-Fi · resumes a task", wifi("off", "Connect to look up 238114"))
    add("wifi-connecting", "wifi", "Wi-Fi · connecting", wifi("connecting"))
    add("wifi-network", "wifi_network", "Wi-Fi · this network", wifi_network())
    add("password", "password", "Password", password())
    add("password-connecting", "password", "Password · connecting", password("connecting"))
    add("password-error", "password", "Password · wrong", password("error"))
    add("device", "device", "Device", device())
    add("wifi-link", "wifi_link", "Wi-Fi link", wifi_link())
    add("updates", "updates", "Updates · available", updates())
    add("updates-running", "updates", "Updates · in the background", updates("running"))
    add("updates-done", "updates", "Updates · all done", updates("done"))
    add("updates-offline", "updates", "Updates · offline", updates("offline"))
    add("storage", "storage", "Storage", storage())
    add("storage-full", "storage", "Storage · almost full", storage(True))
    add("city", "city", "City", city())
    add("city-input", "city_input", "City · keyboard",
        entry_page("city_input", "CITY", "Shanghai", "Type your city", "Saved for every app", toggle=False))
    add("token-mosaico", "token", "Mosaico AI · on", token("mosaico"))
    add("token-own", "token", "Mosaico AI · own key", token("own"))
    add("token-none", "token", "Mosaico AI · off", token("none"))
    add("own-key", "own_key", "Own key · keyboard",
        entry_page("own_key", "OWN KEY", "", "Paste or type your key", "Starts with sk- · every app can read it"))
    add("launching", "launching", "Opening an app", launching())
    add("app-running", "app_running", "Your app is running", launching(running=True))
    return states



# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
def rgb(color: str):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def draw_text(img, draw, obj, text, box, color, align="left", offset=0.0):
    f = font_for(obj["font"], obj["size"])
    x, y, w, h = box
    lh = LINE_EM[obj["font"]] * obj["size"]
    if obj.get("wrap"):
        lines, _ = wrap_lines(text, obj["font"], obj["size"], w, max(1, int(h // lh)))
        top = y
    else:
        if obj.get("overflow") == "ellipsis":
            text = ellipsize(text, f, w)
        lines = text.split("\n")
        top = y + (h - lh * len(lines)) / 2 + obj.get("text_dy", 0)
    for i, line in enumerate(lines):
        tw = f.getlength(line)
        if align == "center":
            tx = x + (w - tw) / 2 + offset
        elif align == "right":
            tx = x + w - tw
        else:
            tx = x
        draw.text((tx, top + i * lh), line, font=f, fill=rgb(color))


def keyboard_keys(kb):
    """Key rectangles of the native keyboard (geometry identical to 0.2)."""
    y0 = kb["y"]
    keys = []
    key_h, pitch = 50, 59
    for r, chars in enumerate(["qwertyuiop", "asdfghjkl", "zxcvbnm"]):
        n, kw, gap = len(chars), 42, 5.6
        start = (W - (n * kw + (n - 1) * gap)) / 2 if r < 2 else 72
        for i, ch in enumerate(chars):
            keys.append((start + i * (kw + gap), y0 + 4 + r * pitch, kw, key_h, ch, kb["key_color"], None))
    ky = y0 + 4 + 2 * pitch
    keys.append((8, ky, 56, key_h, "shift", kb["function_color"], None))
    keys.append((416, ky, 56, key_h, "del", kb["function_color"], None))
    ky = y0 + 4 + 3 * pitch
    keys.append((16, ky, 80, key_h, "123", kb["function_color"], kb["fg_color"]))
    keys.append((104, ky, 272, key_h, "space", kb["key_color"], kb["fg_color"]))
    keys.append((384, ky, 80, key_h, "GO", kb["ok_color"], kb["ok_text_color"]))
    return keys


def draw_keyboard(img, draw, kb):
    f = font_for(kb["font"], kb["font_size"])
    ff = font_for(kb["font"], kb["function_font_size"])
    for kx, ky, kw, kh, text, color, tcolor in keyboard_keys(kb):
        draw.rounded_rectangle((kx, ky, kx + kw, ky + kh), kb["key_radius"], fill=rgb(color))
        if text == "shift":
            shift = Image.open(DESIGN / "assets/icons/back-28-white.png").rotate(-90)
            img.paste(shift, (int(kx) + 14, int(ky) + 11), shift)
        elif text == "del":
            bs = Image.open(DESIGN / "assets/icons/backspace-28-white.png")
            img.paste(bs, (int(kx) + 14, int(ky) + 11), bs)
        else:
            face, size = (ff, kb["function_font_size"]) if tcolor else (f, kb["font_size"])
            tw = face.getlength(text)
            draw.text((kx + (kw - tw) / 2, ky + (kh - 1.25 * size) / 2), text, font=face,
                      fill=rgb(tcolor or kb["fg_color"]))


def screen_mask(scale: int = 4) -> Image.Image:
    mask = Image.new("L", (W * scale, H * scale), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W * scale - 1, H * scale - 1), SCREEN_R * scale, fill=255)
    return mask.resize((W, H), Image.LANCZOS)


def render(state) -> Image.Image:
    img = Image.new("RGB", (W, H), rgb(BG))
    objects = state["objects"]
    i = 0
    while i < len(objects):
        clip = objects[i].get("clip")
        if not clip:
            img = paint(img, [objects[i]])
            i += 1
            continue
        # Paint a run of rows sharing one list viewport, then keep only the viewport.
        j = i
        while j < len(objects) and objects[j].get("clip") == clip:
            j += 1
        layer = paint(img.copy(), objects[i:j])
        x, y, w, h = clip
        img.paste(layer.crop((x, y, x + w, y + h)), (x, y))
        i = j
    out = img.convert("RGBA")
    out.putalpha(screen_mask())
    return out


def paint(img: Image.Image, objects) -> Image.Image:
    draw = ImageDraw.Draw(img)
    for obj in objects:
        t = obj["type"]
        x, y, w, h = obj["x"], obj["y"], obj["w"], obj["h"]
        if t in ("container", "button") or (t == "label" and obj.get("bg")):
            fill = obj.get("bg")
            if obj.get("opacity", 255) < 255 and fill:
                overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                ImageDraw.Draw(overlay).rounded_rectangle((x, y, x + w - 1, y + h - 1), obj.get("radius", 0),
                                                          fill=(*rgb(fill), obj["opacity"]))
                img.paste(Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"))
                draw = ImageDraw.Draw(img)
            elif fill or obj.get("border"):
                draw.rounded_rectangle((x, y, x + w - 1, y + h - 1), obj.get("radius", 0),
                                       fill=rgb(fill) if fill else None,
                                       outline=rgb(obj["border"]) if obj.get("border") else None,
                                       width=obj.get("border_width") or 0)
        if t == "button":
            if obj.get("icon"):
                ic = obj["icon"]
                im = Image.open(DESIGN / ic["image"]).convert("RGBA")
                img.paste(im, (ic["x"], ic["y"]), im)
            if obj.get("text"):
                draw_text(img, draw, obj, obj["text"], (x, y, w, h), obj["color"], "center",
                          obj.get("text_offset", 0.0))
        elif t == "label":
            draw_text(img, draw, obj, obj["text"], (x, y, w, h), obj["color"], obj["align"])
        elif t == "image":
            im = Image.open(DESIGN / obj["image"]).convert("RGBA")
            if im.size != (w, h):
                im = im.resize((w, h), Image.NEAREST)
            img.paste(im, (x, y), im)
        elif t == "progress":
            draw.rounded_rectangle((x, y, x + w - 1, y + h - 1), obj["radius"], fill=rgb(obj["bg"]))
            fw = max(h, round(w * obj["value"] / 100))
            if obj["value"] > 0:
                draw.rounded_rectangle((x, y, x + fw - 1, y + h - 1), obj["radius"], fill=rgb(obj["fg"]))
        elif t == "keyboard":
            draw_keyboard(img, draw, obj)
    return img


# --------------------------------------------------------------------------
# Layout checks
# --------------------------------------------------------------------------
def inside_screen(px: float, py: float) -> bool:
    if px < -0.01 or py < -0.01 or px > W + 0.01 or py > H + 0.01:
        return False
    cx = min(max(px, SCREEN_R), W - SCREEN_R)
    cy = min(max(py, SCREEN_R), H - SCREEN_R)
    return math.hypot(px - cx, py - cy) <= SCREEN_R + 0.01


def outline(x, y, w, h, r):
    r = min(r or 0, w / 2, h / 2)
    pts = []
    for cx, cy, a0 in ((x + r, y + r, 180), (x + w - r, y + r, 270), (x + w - r, y + h - r, 0),
                       (x + r, y + h - r, 90)):
        for k in range(7):
            a = math.radians(a0 + k * 15)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def visible_shapes(obj):
    """Rounded rectangles an object actually paints; none for invisible hit areas."""
    t = obj["type"]
    if t == "keyboard":
        return [(kx, ky, kw, kh, obj["key_radius"]) for kx, ky, kw, kh, *_ in keyboard_keys(obj)]
    if t == "container":
        if obj.get("role") in ("scrim", "background", "row", "sheet") or not (obj.get("bg") or obj.get("border")):
            return []
        return [(obj["x"], obj["y"], obj["w"], obj["h"], obj.get("radius", 0))]
    if t == "button":
        if not (obj.get("bg") or obj.get("border") or obj.get("text") or obj.get("icon")):
            return []
        return [(obj["x"], obj["y"], obj["w"], obj["h"], obj.get("radius", 0))]
    if t == "label" and not obj.get("bg"):
        text = obj["text"]
        if not text.strip():
            return []
        tw = min(obj["w"], text_width(text, obj["font"], obj["size"]))
        x = obj["x"] + {"left": 0, "center": (obj["w"] - tw) / 2, "right": obj["w"] - tw}[obj["align"]]
        return [(x, obj["y"], tw, obj["h"], 0)]
    return [(obj["x"], obj["y"], obj["w"], obj["h"], obj.get("radius", 0))]


def hit_rect(o):
    return o["x"], o["y"], o["x"] + o["w"], o["y"] + o["h"]


def top_layer_buttons(objs):
    """Tappable buttons on the topmost layer: everything after the last scrim,
    except rows inside scrolling lists (they move under the viewport)."""
    start = max((i for i, o in enumerate(objs) if o.get("role") == "scrim"), default=-1) + 1
    return [o for o in objs[start:] if o["type"] == "button" and o.get("action") and not o.get("clip")]


def check(states, extras=()) -> list[str]:
    problems = []
    for st in list(states) + list(extras):
        for obj in st["objects"]:
            t = obj["type"]
            if t == "list_viewport":
                continue
            x, y, w, h = obj["x"], obj["y"], obj["w"], obj["h"]
            where = f"{st['id']}:{obj.get('name') or t}:{obj.get('text', obj.get('image', ''))!r}"
            if not obj.get("clip"):
                if x < 0 or y < 0 or x + w > W or y + h > H:
                    if obj.get("role") != "sheet":
                        problems.append(f"{where} outside the screen ({x},{y},{w},{h})")
                for shape in visible_shapes(obj):
                    if not all(inside_screen(px, py) for px, py in outline(*shape)):
                        problems.append(f"{where} crosses the rounded screen corner {shape[:4]}")
                        break
            if t == "button" and obj.get("action"):
                touch_min = DENSE_TOUCH if obj.get("touch_class") in ("dense", "numpad") else MIN_TOUCH
                if w < touch_min or h < touch_min:
                    problems.append(f"{where} touch target {w}x{h} is below {touch_min}x{touch_min}")
                if obj.get("danger"):
                    if h < DANGER_TOUCH:
                        problems.append(f"{where} danger target height {h} is below {DANGER_TOUCH}")
                    if x < 24 or W - (x + w) < 24 or y < 24 or H - (y + h) < 24:
                        problems.append(f"{where} danger target must stay 24 px from screen edges")
                    if obj.get("hold_ms") != 600:
                        problems.append(f"{where} danger target must hold for 600 ms")
            icon_path = obj.get("image") if t == "image" else (obj.get("icon") or {}).get("image")
            if icon_path and "/icons/" in icon_path and int(Path(icon_path).stem.split("-")[1]) < MIN_ICON:
                problems.append(f"{where} icon is below {MIN_ICON} px")
            if icon_path and not (DESIGN / icon_path).exists():
                problems.append(f"{where} image {icon_path} does not exist")
            if t == "image" and obj.get("qr") and (w != h or w % QR_MODULES or w // QR_MODULES < 5):
                problems.append(f"{where} QR size {w}x{h} is not a whole module size >= 5 px")
            if t in ("label", "button") and obj.get("text"):
                if obj["size"] not in TYPE_SCALE[obj["font"]]:
                    problems.append(f"{where} uses {obj['font']} {obj['size']} px, outside the type scale")
                missing = missing_glyphs(obj["text"], obj["font"])
                if missing:
                    problems.append(f"{where} has no glyph for {''.join(missing)!r} in {obj['font']}")
            if t == "keyboard" and {obj["font_size"], obj["function_font_size"]} - set(TYPE_SCALE[obj["font"]]):
                problems.append(f"{where} keyboard fonts are outside the type scale")
            if t in ("label", "button") and obj.get("text"):
                lines = obj["text"].split("\n")
                need = line_h(obj["font"], obj["size"], len(lines))
                if t == "label" and h < need:
                    problems.append(f"{where} height {h} < line height {need}")
                if obj.get("wrap"):
                    continue
                if t == "button":
                    avail = w - 32 - 2 * obj.get("text_offset", 0)
                else:
                    avail = w
                width = text_width(obj["text"], obj["font"], obj["size"])
                if width > avail and obj.get("overflow") != "ellipsis":
                    problems.append(f"{where} text width {width:.0f} > {avail:.0f}")
        buttons = top_layer_buttons(st["objects"])
        for a, b in itertools.combinations(buttons, 2):
            ax0, ay0, ax1, ay1 = hit_rect(a)
            bx0, by0, bx1, by1 = hit_rect(b)
            if min(ax1, bx1) > max(ax0, bx0) and min(ay1, by1) > max(ay0, by0):
                problems.append(f"{st['id']}: touch areas of {a.get('name')} and {b.get('name')} overlap")
            for d, o in ((a, b), (b, a)):
                if d.get("danger") and not o.get("danger"):
                    dx0, dy0, dx1, dy1 = hit_rect(d)
                    ox0, oy0, ox1, oy1 = hit_rect(o)
                    gap = max(ox0 - dx1, dx0 - ox1, oy0 - dy1, dy0 - oy1)
                    if gap < DANGER_GAP and not o.get("name", "").startswith("button_back"):
                        problems.append(f"{st['id']}: {o.get('name')} is {gap} px from {d.get('name')} "
                                        f"(hold buttons need {DANGER_GAP} px)")
    return problems + check_copy() + check_store_text()


# Dynamic strings measured in their real roles. App names and SSIDs ellipsize.
TOASTS = [
    "Press AI twice to switch apps", "No apps in this list", "AI agent connected",
    "Added to Favorites", "Removed from Favorites", "Download cancelled", "City saved",
    "Key saved", "Key removed", "Mosaico AI turned off", "Mosaico AI is on", "Wi-Fi forgotten",
    "Updates will resume on Wi-Fi", "2 updates · tap to see", "Apps updated", "Up to date",
    "Connect Wi-Fi first", "Deleted Weather Station", "Installing · please wait", "Tap Cancel to stop",
    "Cancelled", "Hold to confirm", "Connected to Espressif-Guest", "12 updates · tap to see",
]
DOWNLOAD_ERRORS = [
    "Type an app ID first", "No app with this ID", "This app was removed", "Not for this device",
    "Download not allowed", "Store is busy. Try later.", "Can't reach the store", "Not enough storage",
]
COPY = [
    (400, "medium", 22, TOASTS),
    (416, "sans", 16, ["Looking up…"] + DOWNLOAD_ERRORS),
    (302, "medium", 22, [s for s, *_ in DETAIL.values()]),
    (320, "sans", 18, ["Smart home · v10.12.3", "New v10.13.0 · 312.4 MB", "Needs 12.5 MB · 0.4 MB free",
                       "Chat · Community · v2.1.0"]),
    (432, "medium", 18, [p[0] for p in PROGRESS.values()] + ["FROM THE WEBSITE · USB", "FROM YOUR AI AGENT · WI-FI"]),
    (432, "medium", 28, [p[1] for p in PROGRESS.values()] + [r[1] for r in RESULTS.values()]),
    (432, "sans", 16, ["312.40 of 312.40 MB · 1.6 MB/s", "Continued where it stopped"]),
    (432, "sans", 18, ["Opening in 1 s", "Updating 2 of 2 in the background"]),
    (324, "sans", 16, ["Connected · 192.168.100.200", "Connect to look up 238114", "Connect to update Voice Notes",
                       "Connect to turn on Mosaico AI", "Connect to get updates"]),
    (316, "sans", 16, ["Downloading · 100%", "Waiting · v10.13.0", "Updated to v10.13.0"]),
    (336, "sans", 16, ["Not connected", "On · included", "Off · tap to turn on", "Own key · ends in 4c8e",
                       "2 available", "Up to date", "33.2 of 64 MB used", "Ready · 192.168.100.200",
                       "Off · connect Wi-Fi first"]),
    (394, "sans", 16, ["USB connected · Waiting for agent", "Plug in USB to set it from your computer"]),
    (100, "medium", 18, ["↑ 12", "↓ 10/12"]),
]


def check_copy() -> list[str]:
    problems = []
    for width, font, size, texts in COPY:
        for text in texts:
            w = text_width(text, font, size)
            if w > width:
                problems.append(f"copy {text!r} is {w:.0f} px wide in a {width} px label")
            missing = missing_glyphs(text, font)
            if missing:
                problems.append(f"copy {text!r} has no glyph for {''.join(missing)!r}")
    return problems


def check_store_text() -> list[str]:
    """Store summaries are bounded ASCII and fit the three lines on detail page 2."""
    problems = []
    for app in PRESETS + STORE_ONLY:
        if len(app["summary"]) > 120 or not app["summary"].isascii():
            problems.append(f"summary of {app['id']} must be ASCII and <= 120 characters")
        if wrap_lines(app["summary"], "sans", 18, 432, 3)[1]:
            problems.append(f"summary of {app['id']} needs more than three lines")
    return problems


def unused_images(states, extras, templates) -> list[str]:
    used = set()

    def walk(objs):
        for o in objs:
            for path in (o.get("image"), (o.get("icon") or {}).get("image")):
                if path:
                    used.add(Path(path).name)
    for st in list(states) + list(extras):
        walk(st["objects"])
    for objs in templates.values():
        walk(objs)
    # Swapped in at runtime by the prototype and the keyboard.
    used |= {"back-28-white.png", "backspace-28-white.png", "battery_full-28-white.png",
             "battery_charging-28-white.png", "eye_off-32-white.png", "wifi_off-28-grey.png",
             "robot-28-grey.png", "star_fill-32-orange.png", "star-32-white.png", "wifi-20-grey.png",
             "lock-20-grey.png", "usb-20-grey.png", "usb-20-orange.png", "wifi_off-32-grey.png",
             "eye_off-32-white.png"}
    used |= {f"{ic}-32-{c}.png" for _, _, ic in BROWSE for c in ("white", "orange")}
    # App tiles and heroes are picked per app at runtime; only line icons are reported.
    pngs = list((DESIGN / "assets/icons").glob("*.png"))
    return sorted(p.name for p in pngs if p.name not in used)


def layout_tables(states) -> str:
    """Human-readable appendix: every named or interactive object per page."""
    lines = ["# 附录：逐页布局表", "",
             "由 `tools/build_design.py` 生成，与 `layout.json` 和页面图一致；坐标单位为 480×480 逻辑像素。",
             "只列出有名称（阶段 B 需要绑定或更新）或可点击的对象；装饰对象见 `layout.json`。", ""]
    seen = set()
    for st in states:
        if st["page"] in seen and not st["id"].startswith(("guide", "progress", "result", "detail")):
            continue
        seen.add(st["page"])
        lines += [f"## {st['id']} — {st['title']}", "", f"![{st['id']}](mockups/{st['id']}.png)", "",
                  "| 名称 | 类型 | x, y, w, h | 样式 | 内容 / 动作 |", "|---|---|---|---|---|"]
        for o in st["objects"]:
            if o["type"] == "list_viewport":
                lines.append(f"| `{o['name']}` | list | {o['x']}, {o['y']}, {o['w']}, {o['h']} | "
                             f"行距 {o['item_height']} | 行模板 `{o['row_template'] or '固定行'}` |")
                continue
            if (o.get("row_of") and o.get("row_of") in ("apps", "networks", "updates", "storage")) \
                    or not (o.get("name") or o.get("action")):
                continue
            style = ""
            if o["type"] in ("label", "button") and o.get("text"):
                style = f"{o['font']} {o['size']}px {o['color']}" + (" 换行" if o.get("wrap") else "")
            elif o["type"] == "image" and o.get("qr"):
                style = f"QR，每模块 {o['w'] // QR_MODULES} px"
            elif o.get("bg"):
                style = o["bg"]
            if o.get("danger"):
                style += " 长按 600 ms"
            content = (o.get("text") or "").replace("\n", " ⏎ ").replace("|", "\\|")
            if o.get("action"):
                content += f"{' → ' if content else '→ '}`{o['action']}`"
            if o["type"] == "image":
                content = o["image"].split("/")[-1]
            lines.append(f"| `{o.get('name') or '—'}` | {o['type']} | {o['x']}, {o['y']}, {o['w']}, {o['h']} | "
                         f"{style} | {content} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    states = build_states()
    out = DESIGN / "mockups"
    out.mkdir(exist_ok=True)
    for stale in out.glob("*.png"):
        stale.unlink()
    renders = {st["id"]: render(st) for st in states}
    for sid, im in renders.items():
        im.save(out / f"{sid}.png", optimize=True)
    # Contact sheet: 4 columns at half size with captions.
    cols, scale, pad, cap = 4, 0.5, 16, 26
    cw, ch = int(W * scale), int(H * scale)
    rows = math.ceil(len(states) / cols)
    sheet = Image.new("RGB", (pad + cols * (cw + pad), pad + rows * (ch + cap + pad)), rgb("#0B0B0B"))
    d = ImageDraw.Draw(sheet)
    cf = ImageFont.truetype(str(DESIGN / FONTS["sans"]), 13)
    for i, st in enumerate(states):
        cx = pad + (i % cols) * (cw + pad)
        cy = pad + (i // cols) * (ch + cap + pad)
        small = renders[st["id"]].resize((cw, ch), Image.LANCZOS)
        d.rounded_rectangle((cx - 1, cy - 1, cx + cw, cy + ch), int(SCREEN_R * scale) + 1,
                            outline=rgb("#2A2A2A"))
        sheet.paste(small, (cx, cy), small)
        d.text((cx, cy + ch + 6), st["title"], font=cf, fill=rgb(TEXT2))
    sheet.save(out / "00-overview.png", optimize=True)
    extras, templates = prototype_extras()
    layout = {"schema": "vibe-mode-design/6", "screen": {"w": W, "h": H}, "tokens": TOKENS,
              "states": states,
              "prototype": {"states": extras, "row_templates": templates,
                            "row_heights": {"apps": ROW_PITCH, "networks": ROW_PITCH, "updates": ROW_PITCH,
                                            "storage": ROW_PITCH},
                            "categories": [{"id": k, "label": t, "icon": i} for k, t, i in CATEGORIES],
                            "browse": [{"id": k, "label": t, "icon": i} for k, t, i in BROWSE],
                            "apps": PRESETS, "store_only": STORE_ONLY, "store_updates": STORE_UPDATES,
                            "favorites": FAVORITES, "current": CURRENT, "recent": RECENT,
                            "nand_capacity_mb": NAND_CAPACITY_MB, "ai_token_kind": AI_TOKEN_KIND,
                            "filter_labels": FILTER_LABELS, "empty_copy": EMPTY_COPY,
                            "networks": [{"ssid": s, "secured": sec, "signal": sig} for s, sec, sig in NETWORKS],
                            "qr_urls": QR_URLS, "wifi_link_token": TOKEN, "ai_token": AI_TOKEN,
                            "interactions": {
                                "danger_hold_ms": 600, "quick_hold_ms": 600, "quick_idle_ms": 4000,
                                "double_press_ms": 350, "ai_hint_max": 3, "toast_ms": 1600,
                                "edge_back_start_px": 24, "edge_back_commit_px": 96,
                                "edge_back_flick_px_ms": 0.45, "page_swipe_px": 56,
                                "backspace_clear_ms": 600, "install_countdown_s": 3,
                                "page_easing": "cubic-bezier(.32,.72,0,1)", "page_ms": 260, "sheet_ms": 300,
                            },
                            "detail_flow": {"axis": "vertical", "pages": 2, "snap": True}}}
    (DESIGN / "layout.json").write_text(json.dumps(layout, indent=1, ensure_ascii=False) + "\n",
                                        encoding="utf-8")
    (DESIGN / "layout-tables.md").write_text(layout_tables(states), encoding="utf-8")
    problems = check(states, extras)
    for p in problems:
        print("check:", p)
    for name in unused_images(states, extras, templates):
        print("note: unused image", name)
    print(f"{len(states)} states rendered; {len(problems)} layout issues")
    return 1 if problems and "--strict" in sys.argv else 0


if __name__ == "__main__":
    raise SystemExit(main())
