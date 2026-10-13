#!/usr/bin/env python3
"""Build the Vibe Mode design (v10): layout data, mockups and layout checks.

The root is a Home / Ideas pager (3x2 circular Idea icons per page plus a
"+ Add Idea" cell) under a status bar (product name, badge, Wi-Fi, USB,
battery). Sub-pages have no status bar: a header with Back sits at the top, and
every list uses one row component (80 px card, 56 px tinted tile or Idea icon,
always-visible scrollbar, swipe-left Delete with Undo). Every page
state is described once with GSP 1.4.0 primitives (containers, labels, buttons,
images, a progress bar and the native keyboard). The same data produces
``layout.json`` (the source for the Phase B scene), the PNG mockups and the
clickable prototype (``build_prototype.py``).

Mockups are approximate design renders made with Pillow and the subset fonts;
they are not GSP simulator or device screenshots. Requires Pillow and
fontTools. Run ``generate_assets.py`` first.
"""
from __future__ import annotations

import itertools
import json
import math
import re
import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

from i18n import CATEGORY_ZH, LANGS, ZH, has_cjk, translate
from sample_data import (CATEGORIES, CATEGORY_LABEL, CURRENT, GLYPHS, NAND_CAPACITY_MB, PRESETS,
                         PRODUCT, SHARED_SAMPLE, STORE_ONLY, STORE_UPDATES, VERSION)

LANG = "en"  # the build runs once per UI language; set_lang() switches


def set_lang(lang: str) -> None:
    global LANG
    LANG = lang


def loc(text: str) -> str:
    """English UI text in the current build language (see tools/i18n.py)."""
    return translate(text, LANG)

DESIGN = Path(__file__).resolve().parents[1]
W = H = 480
M = 16  # outer margin
# Product drawing: 38.8 mm square active display and 60 px corner radius.
SCREEN_R = 60
QR_MODULES = 33  # version 3 (29 modules) plus a 2-module quiet zone on each side

# Root pages (Home, Ideas): the status bar owns y < 56. Sub-pages have no status bar:
# their header (back circle and title) sits at the top and content starts at y = 96.
NAV_Y, NAV_H = 14, 40  # content centre y = 34
CONTENT_Y = 56
ROOT_PAGES = {"home", "ideas"}
SUB_TITLE_Y = 20
SUB_CONTENT_Y = 96

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
TEXT3 = "#5C5C5C"  # disabled only
ACCENT = "#FF4C01"
PRIMARY_BG = "#F2F2F2"
PRIMARY_FG = "#000000"
WHITE = "#FFFFFF"
CREAM = "#E9E2D6"   # the device body colour; list-tile icons use it
DANGER = "#E5484D"  # destructive actions only (Delete, Forget); orange stays "attention"


def _tint(color: str, k: float) -> str:
    a = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(CARD[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(k * x + (1 - k) * y):02X}" for x, y in zip(a, b))


# List tiles: one monochrome family (cream on graphite) so rows read as a set; the
# orange tile marks the one thing on a page that wants attention; muted = unavailable.
TINTS = {"neutral": CREAM, "accent": ACCENT, "muted": TEXT2}
TINT_BG = {"neutral": "#232323", "accent": _tint(ACCENT, 0.16), "muted": "#1A1A1A"}
TINT_ICON = {"neutral": "cream", "accent": "orange", "muted": "grey"}

FONTS = {
    # Semantic keys kept stable for the implementation handoff. "dot" is the
    # display role; the dot-matrix look comes from bitmaps only.
    "dot": "assets/fonts/ArchivoExtended-SemiBold.subset.ttf",
    "sans": "assets/fonts/Inter-Regular.subset.ttf",
    "medium": "assets/fonts/ArchivoExtended-Medium.subset.ttf",
}
# Chinese text uses Noto Sans SC in the same three roles (display → Bold). A label whose
# text contains Chinese is drawn entirely in the CJK face; Latin-only labels keep the
# Latin faces, so digits and Idea names look the same in both languages.
FONTS_CJK = {
    "dot": "assets/fonts/NotoSansSC-Bold.subset.otf",
    "sans": "assets/fonts/NotoSansSC-Regular.subset.otf",
    "medium": "assets/fonts/NotoSansSC-Medium.subset.otf",
}


def font_file(font: str, text: str = "") -> str:
    return FONTS_CJK[font] if has_cjk(text) else FONTS[font]
# Line height per em, from the subset fonts' vertical metrics.
LINE_EM = {"dot": 1.15, "sans": 1.2, "medium": 1.15}
PX_MM = 38.8 / 480
# medium 16 is the navigation badge only.
TYPE_SCALE = {"sans": [16, 18, 24], "medium": [16, 18, 22, 28],
              "dot": [18, 22, 28, 40, 88]}
MIN_TEXT, MIN_TOUCH, MIN_ICON = 16, 84, 20
DENSE_TOUCH = 72
DANGER_TOUCH = 96
DANGER_GAP = 24
DANGER_HOLD_MS = 3000  # press and hold to delete an Idea or forget Wi-Fi
# One list row everywhere: 80 px card, 8 px gap, 56 px leading tile or Idea icon.
ROW_H, ROW_PITCH, LEAD = 80, 88, 56
LIST_BOTTOM = 464  # scrolling lists end here (fade over the last 24 px)
SWIPE_W = 96  # Delete revealed behind a row swiped left
SWIPE_SHIFT = SWIPE_W + 8
SCROLL_X, SCROLL_W, SCROLL_BOTTOM = 468, 4, 444  # scroll indicator, clear of the R60 corner
TOAST_X, TOAST_Y, TOAST_W, TOAST_H = 72, 400, 336, 56
UNDO_MS, TOAST_MS = 4000, 1800
SCREEN_OFF = [("1 min", 60), ("3 min", 180), ("5 min", 300), ("10 min", 600), ("Never", 0)]
AI_KEY_X = 372  # the AI key's centre along the top screen edge (screen coordinates, device upright)
POWER_KEY_X = 372  # the power key sits right below it on the bottom edge
BOOT_KEY_X = 108   # Boot is bottom left

TOKENS = {
    "colors": {"background": BG, "card": CARD, "raised": RAISED, "tile": TILE, "outline": LINE,
               "divider": DIVIDER, "text": TEXT, "text_secondary": TEXT2, "text_disabled": TEXT3,
               "accent": ACCENT, "danger": DANGER, "cream": CREAM, "primary_bg": PRIMARY_BG,
               "primary_fg": PRIMARY_FG},
    "fonts": FONTS,
    "fonts_cjk": FONTS_CJK,
    "line_height_em": LINE_EM,
    "type_scale": TYPE_SCALE,
    "radius": {"card": 20, "row": 18, "key": 20, "sheet": 32, "pill": "h/2"},
    "margin": M,
    "min_touch": MIN_TOUCH,
    "dense_touch": DENSE_TOUCH,
    "danger_touch": DANGER_TOUCH,
    "danger_gap": DANGER_GAP,
    "row": {"height": ROW_H, "pitch": ROW_PITCH, "lead": LEAD, "radius": 20, "lead_radius": 16},
    "tints": {"icon": TINTS, "tile": TINT_BG},
    "swipe": {"action_w": SWIPE_W, "shift": SWIPE_SHIFT},
    "scrollbar": {"x": SCROLL_X, "w": SCROLL_W, "bottom": SCROLL_BOTTOM, "track": TILE, "thumb": TEXT2},
    # Pages with a bottom action row (or the keypad) show the toast higher so it never
    # covers their buttons.
    "toast": {"x": TOAST_X, "y": TOAST_Y, "w": TOAST_W, "h": TOAST_H, "ms": TOAST_MS, "undo_ms": UNDO_MS,
              "lift": {"idea_info": 284, "result": 300, "shared_entry": 300, "help_topic": 300, "about": 300,
                       "progress": 300, "wifi_network": 268, "download": 100}},
    "chrome": {"nav_y": NAV_Y, "nav_h": NAV_H, "content_y": CONTENT_Y, "root_pages": sorted(ROOT_PAGES),
               "header_y": SUB_TITLE_Y, "sub_content_y": SUB_CONTENT_Y, "list_bottom": LIST_BOTTOM,
               "pager_y": 440},
    "readability": {"screen_width_mm": 38.8, "px_mm": round(PX_MM, 4), "min_text_px": MIN_TEXT,
                    "body_text_px": 18, "min_touch_px": MIN_TOUCH, "min_icon_px": MIN_ICON},
    "screen": {"corner_radius": SCREEN_R},
    "qr": {"version": 3, "ecc": "L", "quiet_zone_modules": 2, "modules": QR_MODULES,
           "min_module_px": 5, "dark": "#000000", "light": "#FFFFFF"},
    # Haptic patterns (on, off, on … ms) fire on touch-down, never on release. One short
    # tick per key; a double tick when Go is accepted; a softer single buzz when it is not.
    "haptics": {"key": [8], "confirm": [8, 45, 8], "reject": [24], "clear": [14],
                # A download, update, switch or save finished (before the next screen shows).
                "success": [14, 70, 22], "error": [40, 60, 40],
                "notes": "LRA at resonance with active braking; 8 ms ticks feel crisp, not buzzy"},
    # The square UI never re-lays out: the QSPI panel turns the scan (MADCTL MV/MX/MY via
    # esp_lcd_panel_swap_xy / mirror) and touch coordinates get the same transform.
    "orientation": {"steps_deg": [0, 90, 180, 270], "switch_at_deg": 60, "hysteresis_deg": 15,
                    "settle_ms": 300, "ignore_flat_g": 0.8, "crossfade_ms": 120,
                    "hold_while": ["finger down", "keyboard page", "3 s hold"], "setting": "Display → Auto-rotate"},
    # Physical AI key: feedback is fixed to the device edge under the key (not to the UI).
    "key_feedback": {"bar": [AI_KEY_X - 32, 4, 64, 8], "chip_y": 20, "grow_ms": 80, "hold_ms": 500, "fade_ms": 160,
                     "actions": {"home": "Lock", "ideas": "Home", "sub_page": "Back", "dialog": "Close",
                                 "asleep": "Wake"}},
    "screen_off": {"options_s": [s for _, s in SCREEN_OFF], "default_s": 180, "backlight_pct": 10,
                   "wifi": "off while asleep, reconnects on wake",
                   "no_sleep_while": ["download / install / switch", "background updates", "an Idea running"],
                   "wake": ["touch", "IMU motion", "any key"]},
    "motion": {"page_slide_px": 48, "page_slide_ms": 260, "sheet_ms": 300,
               "easing": "cubic-bezier(.32,.72,0,1)"},
    "keyboard": {"bg_color": BG, "fg_color": TEXT, "key_color": TILE, "function_color": RAISED,
                 "ok_color": ACCENT, "ok_text_color": WHITE, "ok_disabled_color": RAISED,
                 "ok_disabled_text_color": TEXT3, "key_radius": 10, "font": "medium",
                 "font_size": 18, "function_font_size": 18},
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
    """Single-line labels that show Idea names, SSIDs or store text pass
    ``ellipsis=True`` (GSP ``overflow: "ellipsis"``) so they never clip mid-glyph.
    Text is given in English and stored in the build language."""
    text = loc(text)
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
    text = loc(text)
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


def keyboard(y=224, name="keyboard", go=False):
    """Native keyboard. GO is orange only when the input is valid (``go``); otherwise it
    is drawn like a function key with dim text, and pressing it explains what's missing."""
    return {"type": "keyboard", "x": 0, "y": y, "w": W, "h": 233, "name": name, "go_enabled": go,
            "space_label": loc("space"), "go_label": loc("GO"), **TOKENS["keyboard"]}


# --------------------------------------------------------------------------
# Text measurement and glyph coverage
# --------------------------------------------------------------------------
_FONT_CACHE: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}
_CMAP: dict[str, set[int]] = {}


def font_for(font: str, size: int, text: str = "") -> ImageFont.FreeTypeFont:
    path = font_file(font, text)
    key = (path, size)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ImageFont.truetype(str(DESIGN / path), size)
    return _FONT_CACHE[key]


def missing_glyphs(text: str, font: str) -> list[str]:
    path = font_file(font, text)
    if path not in _CMAP:
        _CMAP[path] = set(TTFont(DESIGN / path).getBestCmap())
    return sorted({ch for ch in text if ch != "\n" and ord(ch) not in _CMAP[path]})


def text_width(text: str, font: str, size: int) -> float:
    text = loc(text)
    f = font_for(font, size, text)
    return max((f.getlength(line) for line in text.split("\n")), default=0)


def ellipsize(text: str, f, width: float) -> str:
    if f.getlength(text) <= width:
        return text
    while text and f.getlength(text + "…") > width:
        text = text[:-1]
    return text.rstrip() + "…"


# Chinese breaks between any two characters, Latin between words; closing punctuation
# never starts a line.
_TOKENS = re.compile(r"[\u3000-\u9fff\uff00-\uffef]|[^\s\u3000-\u9fff\uff00-\uffef]+|\s+")
_NO_LINE_START = set("，。、：；？！）」』…·")


def wrap_lines(text: str, font: str, size: int, width: float, max_lines: int) -> tuple[list[str], bool]:
    """Greedy wrap; returns (lines, truncated)."""
    text = loc(text)
    f = font_for(font, size, text)
    lines = []
    for para in text.split("\n"):  # a hand-placed line break always wins
        line = ""
        for tok in _TOKENS.findall(para):
            if tok.isspace():
                line += " " if line else ""
                continue
            trial = line + tok
            if f.getlength(trial.rstrip()) <= width or not line.strip() or tok in _NO_LINE_START:
                line = trial
            else:
                lines.append(line.rstrip())
                line = tok
        lines.append(line.rstrip())
    if len(lines) <= max_lines:
        return lines, False
    kept = lines[:max_lines]
    kept[-1] = ellipsize(kept[-1] + "…", f, width)
    return kept, True


# --------------------------------------------------------------------------
# Sample content (illustrative only; see sample_data.py)
# --------------------------------------------------------------------------
BY_ID = {idea["id"]: idea for idea in PRESETS + STORE_ONLY}
IDEAS_PER_PAGE = 6
GRID_X = (88, 240, 392)  # icon centres
GRID_ICON_Y = (72, 248)
SIGNAL_RANK = {"Strong": 0, "Good": 1, "Weak": 2}
SIGNAL_ICON = {"Strong": 3, "Good": 2, "Weak": 1}
_NETWORKS = [
    ("Studio-5G", True, "Strong"),
    ("Maker Lab", True, "Good"),
    ("Espressif-Guest", False, "Good"),
    ("Home-2.4G", True, "Weak"),
    ("Cafe Corner", True, "Weak"),
]
NETWORKS = sorted(_NETWORKS, key=lambda n: SIGNAL_RANK[n[2]])
IP_ADDRESS = "192.168.1.20"
MAC_ADDRESS = "30:ED:A0:F4:60:56"
QR_URLS = {
    "ideas": "mosaico-ideas.espressif.com",
    "develop": "mosaico.espressif.com/guide/vibe-coding",
    "help-start": "mosaico.espressif.com/vibe/start",
    "help-ids": "mosaico.espressif.com/vibe/ids",
    "help-fix": "mosaico.espressif.com/vibe/fix",
    "vibe-update": "mosaico.espressif.com/vibe/update",
}


def idea_page_count(n_ideas: int) -> int:
    """Ideas pages: n Ideas plus the + Add Idea cell, six cells per page."""
    return math.ceil((n_ideas + 1) / IDEAS_PER_PAGE)


def pager_total(n_ideas: int) -> int:
    """Home is the first page; the rest are Idea pages."""
    return idea_page_count(n_ideas) + 1


def mb(idea) -> float:
    return float(idea["size"].split()[0])


def row_detail(idea) -> str:
    text = CATEGORY_LABEL.get(idea["category"], "Other")
    if LANG == "zh":
        text = CATEGORY_ZH.get(text, text)
    return text if idea["official"] else f"{text} · {loc('Community')}"


def used_mb(ideas=PRESETS) -> float:
    return sum(mb(i) for i in ideas)


def idea_icon(x, y, idea, size=108, name=None):
    if idea.get("icon"):  # a Mosaico launcher icon (copied from mosaico-ui, resized only)
        return image(x, y, f"assets/ideas/{idea['icon']}-{size}.png", name=name, w=size, h=size)
    return image(x, y, f"assets/mosaic/idea_{idea['glyph']}-{size}.png", name=name, w=size, h=size)


def hero(x, y, key, size, name):
    return image(x, y, f"assets/mosaic/hero_{key}-{size}.png", name=name)


# --------------------------------------------------------------------------
# Shared building blocks
# --------------------------------------------------------------------------
def touch(x, y, w, h, action, name, touch_class="default"):
    """Invisible hit area (a transparent GSP button)."""
    obj = button(x, y, w, h, bg=None, radius=min(w, h) // 2, action=action, name=name)
    obj["touch_class"] = touch_class
    return obj


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


def navbar(badge="", wifi_on=True, usb=True, low_battery=False, accent=False, agent=False):
    """Status bar, on the root pages only (Home and the Ideas pages): product name, a
    centred badge for attention states and toasts, Wi-Fi / USB / battery. Sub-pages have
    no status bar; their header starts at the top so the content gets the space."""
    usb_color = "orange" if usb and agent else "white" if usb else "grey"
    objs = [label(44, 22, 130, PRODUCT, "sans", 16, TEXT2, name="nav_product", ellipsis=True),
            label(176, 23, 164, badge or " ", "medium", 16, ACCENT if accent else TEXT2, "center",
                  name="nav_badge", ellipsis=True),
            icon(348, 24, "wifi" if wifi_on else "wifi_off", 20, "white" if wifi_on else "grey", "nav_wifi"),
            icon(380, 24, "usb" if usb else "usb_off", 20, usb_color, "nav_usb"),
            icon(412, 24, "battery_low" if low_battery else "battery_mid", 20,
                 "orange" if low_battery else "white", "nav_battery")]
    for obj in objs:
        obj["role"] = "nav"
    return objs


def pager_dots(page_index, total, y=440):
    """Home is page 0; the Idea pages follow. Active dot is wide and orange."""
    widths = [20 if i == page_index else 8 for i in range(total)]
    x = (W - (sum(widths) + 8 * (total - 1))) // 2
    objs = []
    for i, w in enumerate(widths):
        objs.append(container(x, y, w, 8, ACCENT if i == page_index else TILE, 4, name=f"pager_dot_{i}"))
        x += w + 8
    return objs


def circle(x, y, icon_name, action, name, badge=None):
    """56 px round header button with an 84 px hit area centred on it. ``icon_name``
    "spinner" shows the busy ring; ``badge`` is a small orange count on the corner."""
    objs = [container(x, y, 56, 56, RAISED, 28, name=f"{name}_visual")]
    if icon_name == "spinner":
        objs.append(image(x + 12, y + 12, "assets/anim/spin32-00.png", name=f"{name}_spinner"))
    else:
        objs.append(icon(x + 12, y + 12, icon_name, 32, "white", f"{name}_icon"))
    if badge:
        bw = max(24, math.ceil(text_width(badge, "medium", 16)) + 12)
        objs.append(label(x + 60 - bw, y - 4, bw, badge, "medium", 16, PRIMARY_FG, "center", h=24,
                          name=f"{name}_badge", bg=ACCENT, radius=12))
    objs.append(touch(x - 14, y - 14, 84, 84, action, name))
    return objs


def header(title, page, right=(), size=28, name=None):
    """Sub-page header at the top of the screen: back circle, title and up to two round
    actions on the right (the first spec is the rightmost). A spec is
    (icon, action, name[, badge])."""
    objs = circle(16, SUB_TITLE_Y, "back", "back", f"button_back_{page}")
    right_edge = 456
    for k, (icon_name, action, bname, *badge) in enumerate(right):
        x = 408 - 84 * k
        objs += circle(x, SUB_TITLE_Y, icon_name, action, bname, badge[0] if badge else None)
        right_edge = x - 12
    th = line_h("medium", size)
    objs.append(label(88, SUB_TITLE_Y + 28 - th // 2, right_edge - 88, title, "medium", size, TEXT,
                      name=name or f"{page}_title", ellipsis=True))
    return objs


def title_size(title, right_count=0) -> int:
    """28 px when the title fits beside the header buttons, else 22 (long Idea names)."""
    right_edge = 456 if not right_count else 408 - 84 * (right_count - 1) - 12
    return 28 if text_width(title, "medium", 28) <= right_edge - 88 else 22


def primary(x, y, w, text, action, name, icon_name=None):
    return button(x, y, w, 84, text, "medium", 22, PRIMARY_FG, PRIMARY_BG,
                  icon=f"assets/icons/{icon_name}-32-black.png" if icon_name else None,
                  action=action, name=name)


def secondary(x, y, w, text, action, name, icon_name=None):
    return button(x, y, w, 84, text, "medium", 22, TEXT, RAISED,
                  icon=f"assets/icons/{icon_name}-32-white.png" if icon_name else None,
                  action=action, name=name)


def delete_button(x, y, w, action, name, text="Delete", disabled=False, h=84):
    """Tap-to-delete (shared entries); the page closes and a toast offers Undo for 4 s."""
    obj = button(x, y, w, h, text, "medium", 22, TEXT3 if disabled else DANGER, RAISED,
                 action=action, name=name)
    if disabled:
        obj["disabled"] = True
    return obj


def danger(y, text, action, name, icon_name="trash", fill=0.0):
    """Hold-to-confirm for Forget Wi-Fi: 96 px tall, 24 px from the edges, 3 s hold. A red
    fill grows from the left while it is held; letting go cancels."""
    objs = [container(24, y, 432, 96, CARD, 48, name=f"{name}_track"),
            container(24, y, round(432 * fill), 96, DANGER, 48, opacity=110, name=f"{name}_fill")]
    obj = button(24, y, 432, 96, text, "medium", 22, DANGER, None, border=DANGER, bw=2,
                 icon=f"assets/icons/{icon_name}-32-red.png", action=action, name=name)
    obj.update(danger=True, hold_ms=DANGER_HOLD_MS)
    return objs + [obj]


def row_button(y, action, name, x=16, w=448, h=ROW_H, bg=CARD):
    obj = button(x, y, w, h, bg=bg, radius=20, action=action, name=name)
    obj["touch_class"] = "dense"
    return obj


def lead_tile(x, y, icon_name, tint, prefix=None):
    """56 px rounded tile: cream icon on graphite (neutral), orange (accent) or grey (muted)."""
    return [container(x, y, LEAD, LEAD, TINT_BG[tint], 16, name=f"{prefix}_tile" if prefix else None),
            icon(x + 12, y + 12, icon_name, 32, TINT_ICON[tint], f"{prefix}_icon" if prefix else None)]


def list_row(y, title, sub, lead, action=None, name=None, sub_color=TEXT2, trail="chevron",
             prefix=None, title_name=None, sub_name=None, x=16, lock=None):
    """The one list row used on every page: 80 px card, 56 px leading visual (a tinted
    tile ``("tile", icon, tint)`` or an Idea icon ``("idea", idea)``), medium 22 title
    over a sans 16 line, trailing chevron (or QR hint). Rows inside a scrolling list pass
    ``prefix`` so their objects become row-template fields; the list owns the hit area."""
    w = 448

    def field(f):
        return f"{prefix}_{f}" if prefix else None

    objs = [row_button(y, action, name, x=x, w=w) if action
            else container(x, y, w, ROW_H, CARD, 20, role="row")]
    if lead[0] == "idea":
        objs.append(idea_icon(x + 12, y + 12, lead[1], LEAD, field("icon")))
    else:
        objs += lead_tile(x + 12, y + 12, lead[1], lead[2], prefix)
    tx = x + 12 + LEAD + 16
    trail_x = x + w - 40
    tw = trail_x - 12 - tx - (32 if lock is not None else 0)
    objs += [label(tx, y + 14, tw, title, "medium", 22, TEXT, name=title_name or field("title"), ellipsis=True),
             label(tx, y + 46, tw, sub, "sans", 16, sub_color, name=sub_name or field("sub"), ellipsis=True)]
    if lock is not None:
        objs.append(icon(trail_x - 32, y + 30, "lock", 20, "grey", field("lock")) if lock
                    else image(trail_x - 32, y + 30, "assets/ui/blank-20.png", name=field("lock")))
    if trail:
        objs.append(icon(trail_x, y + 30, trail, 20, "dim" if trail == "chevron" else "grey", field("trail")))
    return objs


def swipe_action(y, viewport, kind):
    """Delete revealed behind a list row swiped left (the row slides by SWIPE_SHIFT)."""
    x = 16 + 448 - SWIPE_W
    return clipped([container(x, y, SWIPE_W, ROW_H, DANGER, 20, name=f"{kind}_delete_bg"),
                    icon(x + 32, y + 12, "trash", 32, "white", f"{kind}_delete_icon"),
                    label(x, y + 48, SWIPE_W, "Delete", "medium", 16, WHITE, "center",
                          name=f"{kind}_delete_label"),
                    touch(x, y, SWIPE_W, ROW_H, f"swipe:{kind}", "button_swipe_delete", "dense")],
                   viewport, kind)


def scrollbar(name, vp_y, vp_h, count, scroll=0):
    """Always-visible scroll indicator right of a list, drawn only when rows overflow."""
    content = count * ROW_PITCH - (ROW_PITCH - ROW_H)
    if content <= vp_h:
        return []
    y0, y1 = vp_y + 4, min(vp_y + vp_h - 4, SCROLL_BOTTOM)
    track = y1 - y0
    th = max(32, round(track * vp_h / content))
    ty = y0 + round((track - th) * scroll / (content - vp_h))
    return [container(SCROLL_X, y0, SCROLL_W, track, TILE, 2, name=f"{name}_scroll_track", role="scrollbar"),
            container(SCROLL_X, ty, SCROLL_W, th, TEXT2, 2, name=f"{name}_scroll_thumb", role="scrollbar")]


def toast(text, undo=False):
    """Bottom toast on sub-pages (root pages flash the status-bar badge instead). With
    ``undo`` it carries Undo for 4 s; the delete is committed when the toast closes."""
    objs = [container(TOAST_X, TOAST_Y, TOAST_W, TOAST_H, TILE, 28, border=LINE, bw=1, name="toast",
                      role="toast"),
            label(TOAST_X + 24, TOAST_Y + 17, TOAST_W - 48 - (88 if undo else 0), text, "sans", 18, TEXT,
                  "left" if undo else "center", name="toast_text", ellipsis=True)]
    if undo:
        objs += [label(TOAST_X + TOAST_W - 104, TOAST_Y + 18, 80, "Undo", "medium", 18, ACCENT, "center",
                       name="toast_undo"),
                 touch(TOAST_X + TOAST_W - 108, TOAST_Y - 14, 96, 84, "toast:undo", "button_undo")]
    return objs


def section(y, text, name=None, color=TEXT2):
    return label(32, y, 416, text, "medium", 18, color, name=name, ellipsis=True)


def status_dot(x, y, color, name=None):
    return container(x, y, 10, 10, color, 5, name=name)


def list_fade(y, name):
    """Fade over the cut-off row; the controller hides it at the end of the list. It only
    darkens pixels, so it may run into the masked screen corner."""
    obj = image(M, y, "assets/ui/list-fade.png", name=name)
    obj["role"] = "fade"
    return obj


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


def list_viewport(name, x, y, w, h, template, count, swipe=False):
    return {"type": "list_viewport", "x": x, "y": y, "w": w, "h": h, "name": name,
            "item_height": ROW_PITCH, "row_template": template, "count": count, "swipe": swipe,
            "scrollbar": [SCROLL_X, y + 4, SCROLL_W, min(y + h - 4, SCROLL_BOTTOM) - (y + 4)]}


# --------------------------------------------------------------------------
# Home and the Ideas grid
# --------------------------------------------------------------------------
def home_card(x, icon_name, title, sub, action, name):
    """Shortcut tile: icon + title + quiet subtitle so the three doors read as a set."""
    return [button(x, 300, 144, 120, bg=CARD, radius=20, action=action, name=name),
            icon(x + 56, 316, icon_name, 32, "white", f"{name}_icon"),
            label(x + 8, 360, 128, title, "medium", 18, TEXT, "center", name=f"{name}_label"),
            label(x + 8, 386, 128, sub, "sans", 16, TEXT2, "center", name=f"{name}_sub")]


def wifi_alert(y=232):
    """Offline on Home: a red pill with an alert mark that opens Wi-Fi directly (replaces the intro)."""
    text = "Wi-Fi not connected"
    tw = math.ceil(text_width(text, "medium", 18))
    w = 20 + 20 + 8 + tw + 8 + 20 + 16
    x = (W - w) // 2
    return [container(x, y, w, 48, _tint(DANGER, 0.2), 24, border=DANGER, bw=1, name="home_wifi_alert"),
            icon(x + 20, y + 14, "alert", 20, "red", "home_wifi_alert_icon"),
            label(x + 48, y + 13, tw + 2, text, "medium", 18, DANGER, name="home_wifi_alert_text"),
            icon(x + w - 36, y + 14, "chevron", 20, "red"),
            touch(x - 8, y - 18, w + 16, 84, "go:wifi", "button_home_wifi")]


def page_label(k: int, n_ideas: int = len(PRESETS)) -> str:
    """Shown in the status-bar centre for a moment after the pager lands on a page."""
    return "Home" if k == 0 else f"Ideas {k}/{idea_page_count(n_ideas)}"


def home(offline=False, n_ideas=len(PRESETS), toast=None, hint=False, show_label=False):
    """Status-bar centre is empty at rest: no update badge (updates show on the Idea
    tiles and in Manage). It flashes the page name after a page change, or a toast.
    ``hint``: first-use triangle at the right edge that nudges left (swipe for Ideas)."""
    badge = toast or (page_label(0) if show_label else "")
    objs = navbar(badge, wifi_on=not offline, accent=bool(toast))
    objs.append(image(180, 60, "assets/anim/home-00.png", name="home_hero"))
    wa = text_width("Make Ideas ", "dot", 28)
    x0 = round((W - text_width("Make Ideas Run", "dot", 28)) / 2)
    objs += [label(x0, 184, math.ceil(wa), "Make Ideas", "dot", 28, TEXT, name="home_title_a"),
             label(x0 + round(wa), 184, math.ceil(text_width("Run", "dot", 28)) + 2, "Run", "dot", 28,
                   ACCENT, name="home_title_b"),
             ]
    if offline:
        objs += wifi_alert()
    else:
        objs.append(label(40, 224, 400, "Download or build Ideas,\nthen run them here.", "sans", 18, TEXT2,
                          "center", name="home_intro"))
    objs += home_card(16, "code", "Develop", "Build one", "go:develop", "button_develop")
    objs += home_card(168, "grid", "Manage", "All Ideas", "go:manage", "button_manage")
    objs += home_card(320, "settings", "Settings", "Device", "go:settings", "button_settings")
    if hint:
        objs.append(icon(436, 208, "tri_left", 24, "orange", "pager_hint"))
    objs += pager_dots(0, pager_total(n_ideas))
    return objs


def idea_cell(col, row, idea):
    """Circular icon, optional current ring and update badge, two-line name, hit area."""
    cx, iy = GRID_X[col], GRID_ICON_Y[row]
    iid = idea["id"]
    objs = []
    if iid == CURRENT:
        objs.append(container(cx - 58, iy - 4, 116, 116, None, 58, border=ACCENT, bw=3,
                              name=f"idea_ring_{iid}"))
    objs.append(idea_icon(cx - 54, iy, idea, 108, f"idea_icon_{iid}"))
    if iid in STORE_UPDATES:
        objs.append(label(cx + 32, iy + 4, 24, "↑", "sans", 16, BG, "center", h=24, name=f"idea_badge_{iid}",
                          bg=ACCENT, radius=12))
    objs.append(label(cx - 72, iy + 116, 144, idea["name"], "medium", 18, TEXT, "center",
                      h=line_h("medium", 18, 2), name=f"idea_name_{iid}", wrap=True))
    objs.append(touch(cx - 76, iy - 6, 152, 170, f"idea:{iid}", f"button_idea_{iid}"))
    return objs


def add_cell(col, row):
    """Last cell: a graphite circle with a big white plus, so it reads as an action rather
    than another Idea. Opens Manage → Download Idea."""
    cx, iy = GRID_X[col], GRID_ICON_Y[row]
    return [container(cx - 54, iy, 108, 108, TILE, 54, name="idea_add_visual"),
            icon(cx - 28, iy + 26, "plus", 56, "white", "idea_add_icon"),
            label(cx - 72, iy + 116, 144, "Add Idea", "medium", 18, TEXT, "center",
                  h=line_h("medium", 18, 2), name="idea_add_name", wrap=True),
            touch(cx - 76, iy - 6, 152, 170, "go:add_idea", "button_add_idea")]


def ideas_page(k, ideas=None, toast=None, show_label=True):
    ideas = PRESETS if ideas is None else ideas
    chunk = ideas[(k - 1) * IDEAS_PER_PAGE:k * IDEAS_PER_PAGE]
    # Drawn at the moment the page lands: the centre names the page, then clears.
    objs = navbar(toast or (page_label(k, len(ideas)) if show_label else ""), accent=bool(toast))
    for i, idea in enumerate(chunk):
        objs += idea_cell(i % 3, i // 3, idea)
    if len(chunk) < IDEAS_PER_PAGE:
        objs += add_cell(len(chunk) % 3, len(chunk) // 3)
    objs += pager_dots(k, pager_total(len(ideas)))
    return objs


def ideas_empty():
    objs = navbar("")
    objs += [container(186, 92, 108, 108, TILE, 54, name="idea_add_visual"),
             icon(212, 118, "plus", 56, "white", "idea_add_icon"),
             label(168, 208, 144, "Add Idea", "medium", 18, TEXT, "center", name="idea_add_name"),
             label(24, 264, 432, "No Ideas yet", "medium", 28, TEXT, "center", name="ideas_empty_title"),
             label(40, 310, 400, "Type an ID from Mosaico Ideas,\nor ask your agent to build one.", "sans", 18,
                   TEXT2, "center", h=line_h("sans", 18, 2), name="ideas_empty_body"),
             touch(164, 86, 152, 160, "go:add_idea", "button_add_idea")]
    objs += pager_dots(1, pager_total(0))
    return objs


def chip(x, y, text, fg, bg, name=None):
    w = math.ceil(text_width(text, "medium", 16)) + 28
    return label(x, y, w, text, "medium", 16, fg, "center", h=36, name=name, bg=bg, radius=18), w


def key_marker(key, text, fg, bg, tone):
    """Arrow on the screen edge pointing straight at a physical key, plus a chip saying what
    to do with it. ``key``: "ai" (top edge) or "power" (bottom edge); both sit at x = 372."""
    w = math.ceil(text_width(text, "medium", 16)) + 28
    cx = AI_KEY_X if key == "ai" else POWER_KEY_X
    if key == "ai":
        arrow = icon(cx - 12, 8, "arrow_up", 24, tone, "confirm_key_ai_arrow")
        chip_y = 38
    else:
        arrow = icon(cx - 12, 448, "arrow_down", 24, tone, "confirm_key_power_arrow")
        chip_y = 410
    return [arrow, label(cx - w // 2, chip_y, w, text, "medium", 16, fg, "center", h=32,
                         name=f"confirm_key_{key}_chip", bg=bg, radius=16)]


CONFIRM_BACK = "To come back to Vibe Mode, hold AI and\npress power twice."


def confirm_open(idea, checked=False, warn=None):
    """Asked before an Idea takes over the screen. Full screen, no nested boxes: what happens,
    how to come back, and arrows at the screen edges pointing at the two keys involved
    (AI on top, power at the bottom). "Don't show this again" sets vibe_prefs/open_confirm.
    ``warn`` replaces the subtitle when the running build is not saved yet."""
    objs = [container(0, 0, W, H, BG, 0, name="confirm_scrim", role="scrim")]
    dialog = key_marker("ai", "Hold AI", PRIMARY_FG, ACCENT, "orange")
    back_lines = len(loc(CONFIRM_BACK).split("\n"))
    dialog += [idea_icon(24, 92, idea, LEAD, "confirm_icon"),
               label(96, 94, 360, f"Open {idea['name']}?", "medium", 22, TEXT, name="confirm_title", ellipsis=True),
               label(96, 126, 360, warn or "Vibe Mode closes while it runs.", "sans", 16, ACCENT if warn else TEXT2,
                     name="confirm_sub", ellipsis=True),
               label(24, 172 + (2 - back_lines) * line_h("sans", 18) // 2, 432, CONFIRM_BACK, "sans", 18, TEXT,
                     h=line_h("sans", 18, back_lines), name="confirm_back"),
               secondary(24, 232, 208, "Cancel", "confirm:cancel", "button_confirm_cancel"),
               primary(248, 232, 208, "Open", "confirm:open", "button_confirm_open", "play"),
               container(48, 350, 28, 28, ACCENT if checked else None, 8, border=None if checked else TEXT2,
                         bw=0 if checked else 2, name="confirm_skip_box")]
    if checked:
        dialog.append(icon(52, 354, "check", 20, "black", "confirm_skip_check"))
    dialog += [label(92, 353, 300, "Don't show this again", "sans", 18, TEXT, name="confirm_skip_label"),
               touch(24, 328, 432, 72, "confirm:toggle", "button_confirm_skip", "dense")]
    dialog += key_marker("power", "Press twice", TEXT, LINE, "white")
    for o in dialog:
        o["role"] = "dialog"
    return objs + dialog


# --------------------------------------------------------------------------
# Manage
# --------------------------------------------------------------------------
MANAGE_LIST_Y = 148
MANAGE_LIST_H = LIST_BOTTOM - MANAGE_LIST_Y


def manage_order(ideas):
    """Current Idea first, then Ideas with an update, then install order."""
    return sorted(ideas, key=lambda i: (i["id"] != CURRENT, i["id"] not in STORE_UPDATES))


def manage_sub(idea, state=None):
    if state:
        return state
    iid = idea["id"]
    if iid == CURRENT:
        return "Current", ACCENT
    if iid in STORE_UPDATES:
        return f"Update to v{STORE_UPDATES[iid]}", ACCENT
    return f"v{idea['version']} · {idea['size']}", TEXT2


def manage_row(y, idea, viewport, state=None, x=16):
    sub, color = manage_sub(idea, state)
    return clipped(list_row(y, idea["name"], sub, ("idea", idea), sub_color=color, prefix="manage", x=x),
                   viewport, "manage")


def manage(updates=True, ideas=None, updating=False, swipe=None, undo=None):
    """Header: + (download) and an update button whose badge counts pending updates (tap =
    update all; it spins while updating). Storage summary, then the Idea list: rows swipe
    left to reveal Delete, and a toast offers Undo."""
    ideas = PRESETS if ideas is None else ideas
    used = used_mb(ideas)
    full = used > NAND_CAPACITY_MB - 1
    pending = [iid for iid in STORE_UPDATES if any(i["id"] == iid for i in ideas)] if updates else []
    right = [("plus", "go:download", "button_add_download")]
    if pending:
        right.append(("spinner" if updating else "upgrade", "update:all", "button_update_all", str(len(pending))))
    objs = header("Manage", "manage", right=right)
    objs += [label(24, 96, 432, f"{len(ideas)} Ideas · {used:.1f} of {NAND_CAPACITY_MB:.0f} MB used", "sans", 18,
                   TEXT, name="manage_summary", ellipsis=True),
             progress(24, 128, 432, 6, round(used / NAND_CAPACITY_MB * 100), "manage_bar", ACCENT if full else TEXT)]
    vp = (16, MANAGE_LIST_Y, 448, MANAGE_LIST_H)
    objs.append(list_viewport("manage", *vp, "manage_row", len(ideas), swipe=True))
    for i, idea in enumerate(manage_order(ideas)[:4]):
        y = MANAGE_LIST_Y + i * ROW_PITCH
        state = None
        if updating and idea["id"] in pending:
            state = ("Updating · 40%", ACCENT) if idea["id"] == pending[0] else ("Waiting", TEXT2)
        if swipe == i:
            objs += swipe_action(y, vp, "manage")
            objs += manage_row(y, idea, vp, state, x=16 - SWIPE_SHIFT)
        else:
            objs += manage_row(y, idea, vp, state)
    objs.append(list_fade(LIST_BOTTOM - 24, "manage_fade"))
    objs += scrollbar("manage", MANAGE_LIST_Y, MANAGE_LIST_H, len(ideas))
    if undo:
        objs += toast(f"Deleted {undo}", undo=True)
    return objs


# --------------------------------------------------------------------------
# Idea info: one screen, actions at the bottom
# --------------------------------------------------------------------------
INFO_IDEA = {"local": "100012", "update": "100006", "remote": "238114", "nospace": "507219",
             "current": CURRENT}
INFO_STATUS = {  # mode: (status, highlighted)
    "local": ("On this device", False),
    "update": ("Update available", True),
    "remote": ("Not on this device", False),
    "nospace": ("Not enough space", True),
    "current": ("Current Idea", True),
}
ACTION_Y = 380  # bottom action row (84 px buttons) on results, Help, About, shared entry
INFO_ACTION_Y = 360  # Idea info: 96 px buttons, because Delete is a hold target
DELETE_REST = (296, INFO_ACTION_Y, 160, 96)
DELETE_HELD = (144, INFO_ACTION_Y, 312, 96)  # Open shrinks to an icon, Delete widens
OPEN_REST = (24, INFO_ACTION_Y, 248, 96)
OPEN_HELD = (24, INFO_ACTION_Y, 96, 96)


def info_button(rect, text, action, name, icon_name=None, primary_style=True):
    x, y, w, h = rect
    return button(x, y, w, h, text, "medium", 22, PRIMARY_FG if primary_style else TEXT,
                  PRIMARY_BG if primary_style else RAISED,
                  icon=f"assets/icons/{icon_name}-32-{'black' if primary_style else 'white'}.png" if icon_name else None,
                  action=action, name=name)


def info_actions(idea, mode, held=None):
    """Idea info actions. On the device: Open beside a Delete that must be held for 3 s.
    While held, Open shrinks to an icon, Delete widens with a red fill as the timer, and
    a popup says what happens; letting go early cancels and restores the row."""
    if mode == "remote":
        return [info_button((24, INFO_ACTION_Y, 432, 96), "Download", "idea:download", "button_download", "download")]
    if mode == "nospace":
        return [info_button((24, INFO_ACTION_Y, 432, 96), "Free up space", "go:manage", "button_free_space")]
    objs = [info_button(OPEN_REST if held is None else OPEN_HELD, "Open" if held is None else "", "idea:open",
                        "button_open", "play")]
    if mode == "current":
        objs.append(delete_button(*DELETE_REST[:3], "idea:delete", "button_delete", disabled=True, h=96))
        return objs
    x, y, w, h = DELETE_REST if held is None else DELETE_HELD
    fill = held or 0.0
    text = "Delete" if held is None else f"Keep holding · {max(1, math.ceil(DANGER_HOLD_MS / 1000 * (1 - fill)))} s"
    objs += [container(x, y, w, h, RAISED, 48, name="button_delete_track"),
             container(x, y, round(w * fill), h, DANGER, 48, opacity=235, name="button_delete_fill")]
    b = button(x, y, w, h, text, "medium", 22, DANGER if held is None else TEXT, None, action="hold:delete",
               name="button_delete")
    b.update(danger=True, hold_ms=DANGER_HOLD_MS,
             hold_expand={"rect": list(DELETE_HELD), "partner": "button_open", "partner_rect": list(OPEN_HELD)})
    objs.append(b)
    if held is not None:
        objs += delete_popup(idea)
    return objs


def delete_popup(idea):
    """Shown while Delete is held: the page above the buttons dims, the popup names the Idea."""
    return [container(0, 0, W, INFO_ACTION_Y - 16, BG, 0, opacity=215, name="delete_dim", role="dim"),
            container(40, 232, 400, 104, TILE, 24, border=LINE, bw=1, name="delete_popup"),
            icon(64, 252, "trash", 32, "red", "delete_popup_icon"),
            label(112, 250, 312, f"Delete {idea['name']}?", "medium", 22, TEXT, name="delete_popup_title",
                  ellipsis=True),
            label(112, 284, 312, "Keep holding for 3 s. Let go to cancel.", "sans", 16, TEXT2,
                  name="delete_popup_body", ellipsis=True)]


def idea_info(mode="local", held=None):
    idea = BY_ID[INFO_IDEA[mode]]
    iid = idea["id"]
    status, hi = INFO_STATUS[mode]
    meta = f"{row_detail(idea)} · v{idea['version']}"
    meta2 = f"Needs {idea['size']} · 0.4 MB free" if mode == "nospace" else f"{idea['size']} · ID {iid}"
    objs = header(idea["name"], "info", right=[("qr", "qr:idea", "button_qr_idea")],
                  size=title_size(idea["name"], 1))
    y0 = SUB_CONTENT_Y
    objs += [idea_icon(24, y0, idea, 96, "info_icon"),
             status_dot(136, y0 + 13, ACCENT if hi else TEXT2, "info_status_dot"),
             label(154, y0 + 6, 302, status, "medium", 22, TEXT, name="info_status", ellipsis=True),
             label(136, y0 + 44, 320, meta, "sans", 18, TEXT2, name="info_meta", ellipsis=True),
             label(136, y0 + 70, 320, meta2, "sans", 18, ACCENT if mode == "nospace" else TEXT2,
                   name="info_meta2", ellipsis=True)]
    n_lines = 2 if mode == "update" else 3  # the update row needs the third line's room
    lines, _ = wrap_lines(idea["summary"], "sans", 18, 432, n_lines)
    objs.append(label(24, 204, 432, "\n".join(lines), "sans", 18, TEXT, h=line_h("sans", 18, n_lines), wrap=True,
                      name="info_summary"))
    if mode == "update":
        objs += list_row(256, f"Update to v{STORE_UPDATES[iid]}", "New version on Mosaico Ideas",
                         ("tile", "upgrade", "accent"), "idea:update", "button_update",
                         title_name="info_update_title", sub_name="info_update_sub")
    return objs + info_actions(idea, mode, held)


# --------------------------------------------------------------------------
# Keyboard pages and the Download keypad
# --------------------------------------------------------------------------
def entry_page(page, title, display, placeholder, note, toggle=False, note_color=TEXT2, spinner=False, go=None):
    """Keyboard page: value card, one note line (hints and errors), the native keyboard."""
    objs = header(title, page, size=title_size(title))
    objs.append(container(16, 96, 448, 64, CARD, 20, name=f"{page}_card"))
    objs.append(label(36, 115, 332 if toggle else 408, display or placeholder, "medium", 22,
                      TEXT if display else TEXT2, name=f"{page}_display", ellipsis=True))
    if toggle:
        objs += [icon(412, 112, "eye", 32, "white", f"{page}_eye"),
                 touch(380, 86, 84, 84, f"{page}:toggle", f"button_toggle_{page}")]
    if spinner:
        objs.append(image(32, 172, "assets/anim/spin32-00.png", name=f"{page}_spinner"))
    objs.append(label(72 if spinner else 32, 178, 384 if spinner else 416, note, "sans", 16, note_color,
                      name=f"{page}_note", ellipsis=True))
    objs.append(keyboard(224, f"{page}_keyboard", bool(display) if go is None else go))
    return objs


KEYPAD = [["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"], ["del", "0", "go"]]
SLOT_W, SLOT_H, SLOT_GAP, SLOT_GROUP, SLOT_Y = 44, 56, 8, 20, 92
KEY_X = (136, 240, 344)  # key centres
KEY_Y0, KEY_PITCH, KEY_VW, KEY_VH, KEY_GROW = 180, 72, 88, 56, 6


def slot_x(i: int) -> int:
    x0 = (W - (6 * SLOT_W + 4 * SLOT_GAP + SLOT_GROUP)) // 2
    return x0 + i * (SLOT_W + SLOT_GAP) + (SLOT_GROUP - SLOT_GAP if i >= 3 else 0)


def group_id(digits: str) -> str:
    return " ".join(digits[i:i + 3] for i in range(0, len(digits), 3))


def download(digits="", looking=False, error="", offline=False, pressed=None):
    """Six digit slots (3 + 3) with the next slot outlined, one status line, and a
    compact dialer: 88×56 pill keys on a 104×72 hit grid. Go turns orange once all six
    digits are in. A pressed key grows by 6 px on each side (``pressed``)."""
    objs = header("Download Idea", "download", right=[("qr", "qr:ideas", "button_qr_ideas")])
    if offline:
        objs += [hero(180, 112, "wifi", 120, "download_hero"),
                 label(24, 248, 432, "Wi-Fi is off", "medium", 28, TEXT, "center", name="download_offline_title"),
                 label(24, 288, 432, "Connect Wi-Fi to download Ideas.", "sans", 18, TEXT2, "center",
                       name="download_offline_note"),
                 primary(24, ACTION_Y, 432, "Connect Wi-Fi", "go:wifi", "button_connect_wifi", "wifi")]
        return objs
    for i in range(6):
        x = slot_x(i)
        active = i == len(digits) and not looking and not error
        border = ACCENT if error or active else None
        objs += [container(x, SLOT_Y, SLOT_W, SLOT_H, CARD, 14, border=border, bw=2 if border else 0,
                           name=f"id_slot_{i}_box"),
                 label(x, SLOT_Y, SLOT_W, digits[i] if i < len(digits) else " ", "dot", 28, TEXT, "center",
                       h=SLOT_H, name=f"id_slot_{i}")]
    status = error or ("Looking up…" if looking else "Enter the 6-digit ID from Mosaico Ideas")
    objs.append(label(24, 156, 432, status, "sans", 16, ACCENT if error else TEXT2, "center",
                      name="id_status", ellipsis=True))
    for r, row in enumerate(KEYPAD):
        for c, key in enumerate(row):
            cx, hy = KEY_X[c], KEY_Y0 + r * KEY_PITCH
            vx, vy = cx - KEY_VW // 2, hy + (KEY_PITCH - KEY_VH) // 2
            vname = f"key_{key}_visual"
            vw, vh, bg = KEY_VW, KEY_VH, TILE
            if key == pressed:
                vx, vy, vw, vh, bg = vx - KEY_GROW, vy - KEY_GROW, vw + 2 * KEY_GROW, vh + 2 * KEY_GROW, LINE
            if key == "del":
                objs += [container(vx, vy, vw, vh, LINE if key == pressed else None, vh // 2, name=vname),
                         icon(cx - 16, hy + 20, "backspace", 32, "white", "key_del_icon")]
            elif key == "go":
                ready = len(digits) == 6 and not looking
                go = label(vx, vy, vw, "Go", "medium", 22, WHITE if ready else TEXT3, "center", h=vh,
                           name=vname, bg=ACCENT if ready else RAISED, radius=vh // 2)
                if not ready:
                    go["disabled"] = True
                objs.append(go)
            else:
                objs.append(label(vx, vy, vw, key, "dot", 28, TEXT, "center", h=vh, name=vname, bg=bg,
                                  radius=vh // 2))
            objs.append(touch(cx - 52, hy, 104, KEY_PITCH, f"key:{key}", f"key_{key}", "numpad"))
    return objs


# --------------------------------------------------------------------------
# Develop
# --------------------------------------------------------------------------
def develop(usb=True, agent=True):
    ready = usb and agent
    status = ("USB connected · Agent ready" if ready else
              "USB connected · Waiting for agent" if usb else "Plug in a USB cable")
    objs = header("Develop", "develop")
    objs += list_row(96, "Vibe-code an Idea", "Scan for the step-by-step guide", ("tile", "code", "accent"),
                     "qr:develop", "button_vibe_guide", trail="qr")
    y = 192
    objs += [container(16, y, 448, 112, CARD, 20, border=ACCENT if ready else None, bw=2 if ready else 0,
                       name="develop_usb_card")]
    objs += lead_tile(28, y + 12, "usb", "neutral" if usb else "muted", "develop_usb")
    objs += [label(100, y + 14, 344, "Install over USB", "medium", 22, TEXT),
             status_dot(100, y + 51, ACCENT if ready else TEXT2, "develop_status_dot"),
             label(118, y + 46, 326, status, "sans", 16, ACCENT if ready else TEXT2, name="develop_status",
                   ellipsis=True),
             label(100, y + 74, 344, "Ask your agent to install it here.", "sans", 16, TEXT2)]
    # The agent installs into the run slot only; saving copies it to NAND so switching to
    # another Idea later doesn't lose it.
    built = usb and agent
    objs += list_row(320, "Save to NAND flash", "hello_world · keep it for later" if built
                     else "Install an Idea over USB first", ("tile", "storage", "neutral" if built else "muted"),
                     "dev:save", "button_save_nand", prefix="develop_save")
    objs.append(label(24, 420, 432, "To come back: hold AI, press power twice.", "sans", 16, TEXT2, "center"))
    return objs


# --------------------------------------------------------------------------
# Progress, results, launching
# --------------------------------------------------------------------------
PLUS_IDEA = {"glyph": "plus", "name": "hello_world"}
PROGRESS = {
    # kind: title, Idea (None = placeholder), detail, pct, bytes, phase, cancel
    "download": ("Downloading", "238114", None, 62, "0.56 of 0.90 MB · 512 KB/s", "Step 1 of 2 · Download", True),
    "install": ("Installing", "238114", None, 81, "0.90 of 0.90 MB · Writing", "Step 2 of 2 · Install", False),
    "switch": ("Switching Ideas", "100009", None, 24, "0.58 of 2.40 MB · Preparing", "Step 1 of 2 · Prepare", True),
    "agent": ("From your agent", None, "hello_world · v0.2.1", 46, "1.31 of 2.85 MB · 236 KB/s",
              "Step 1 of 2 · Receiving", False),
}


def progress_page(kind="download"):
    title, iid, detail_text, pct, size_text, phase, cancel = PROGRESS[kind]
    idea = BY_ID[iid] if iid else PLUS_IDEA
    if iid:
        detail_text = f"{idea['name']} · v{idea['version']}"
    objs = [idea_icon(32, 48, idea, 96, "progress_icon"),
            label(144, 56, 312, title, "medium", 22, TEXT, name="progress_title", ellipsis=True),
            label(144, 90, 312, detail_text, "sans", 18, TEXT2, name="progress_detail", ellipsis=True),
            label(144, 118, 312, phase, "sans", 16, TEXT2, name="progress_phase", ellipsis=True),
            label(24, 168, 432, f"{pct}%", "dot", 88, TEXT, "center", name="progress_percent"),
            progress(40, 280, 400, 12, pct),
            label(24, 300, 432, size_text, "sans", 16, TEXT2, "center", name="progress_bytes", ellipsis=True)]
    if cancel:
        objs.append(secondary(24, ACTION_Y, 432, "Cancel", "progress:cancel", "button_cancel"))
    else:
        objs.append(label(24, 404, 432, "Keep the device on until this finishes.", "sans", 16, TEXT2, "center"))
    return objs


RESULTS = {
    # kind: pictogram, title, caption, detail, left button, right button
    "saved": ("saved", "Idea saved", "Rolling Maze · v1.0.3", "Find it on your Ideas pages.",
              ("Done", "result:done"), ("Open", "result:open")),
    "failed": ("cross", "Couldn't download", "Rolling Maze · v1.0.3",
               "The connection dropped.\nCheck Wi-Fi and try again.",
               ("Done", "result:done"), ("Try again", "result:retry")),
    "nospace": ("full", "Not enough storage", "Rolling Maze needs 0.9 MB",
                "Delete an Idea you don't use\nto make room.",
                ("Cancel", "result:done"), ("Manage", "go:manage")),
    "battery": ("battery", "Battery low", "Charge to 20% to switch Ideas",
                "Switching writes to flash and\nmust not be interrupted.", None, ("OK", "result:done")),
}


def result(kind="saved"):
    pic, title, caption, detail_text, left, right = RESULTS[kind]
    objs = [hero(180, 48, pic, 120, "result_hero"),
            label(24, 184, 432, title, "medium", 28, TEXT, "center", name="result_title", ellipsis=True),
            label(24, 226, 432, caption, "sans", 18, TEXT2, "center", name="result_caption", ellipsis=True),
            label(24, 254, 432, detail_text, "sans", 18, TEXT2, "center", h=line_h("sans", 18, 2),
                  name="result_detail")]
    if left:
        objs.append(secondary(24, ACTION_Y, 208, left[0], left[1], "button_result_left"))
        objs.append(primary(248, ACTION_Y, 208, right[0], right[1], "button_result_right"))
    else:
        objs.append(primary(24, ACTION_Y, 432, right[0], right[1], "button_result_right"))
    return objs


def launching(idea=None, running=False):
    idea = idea or BY_ID["100009"]
    if running:
        return [idea_icon(186, 76, idea, 108, "running_icon"),
                label(24, 208, 432, idea["name"], "medium", 28, TEXT, "center", name="running_title",
                      ellipsis=True),
                label(24, 248, 432, "Your Idea is running.", "sans", 18, TEXT2, "center"),
                label(24, 380, 432, "To come back to Vibe Mode:\nhold AI and press power twice.",
                      "sans", 16, TEXT2, "center", h=line_h("sans", 16, 2))]
    return [idea_icon(186, 80, idea, 108, "launch_icon"),
            label(24, 212, 432, f"Opening {idea['name']}", "medium", 28, TEXT, "center", name="launch_title",
                  ellipsis=True),
            label(24, 252, 432, "Restarting…", "sans", 18, TEXT2, "center"),
            image(208, 316, "assets/anim/spin64-00.png", name="launch_spinner")]


def boot():
    return [hero(180, 140, "vibe", 120, "boot_logo"),
            label(24, 284, 432, PRODUCT, "dot", 28, TEXT, "center", name="boot_title")]


# --------------------------------------------------------------------------
# Settings, Help, About, QR
# --------------------------------------------------------------------------
SETTINGS_ROWS = [  # icon, title, sub, target view, button name, sub-label name
    ("wifi", "Wi-Fi", "Studio-5G", "wifi", "button_wifi", "settings_wifi"),
    ("display", "Display", "Screen off after 3 min", "display", "button_display", "settings_display"),
    ("key", "Shared info", f"{len(SHARED_SAMPLE)} entries", "shared", "button_shared", "settings_shared"),
    ("help", "Help", "How-to guides and fixes", "help", "button_help", "settings_help"),
    ("globe", "Language", "English", "language", "button_language", "settings_language"),
    ("chip", "About", PRODUCT, "about", "button_about", "settings_about"),
]
SETTINGS_Y = SUB_CONTENT_Y
SETTINGS_H = LIST_BOTTOM - SETTINGS_Y


def settings_row(y, row, viewport):
    ic, title, sub, *_ = row
    return clipped(list_row(y, title, sub, ("tile", ic, "neutral"), prefix="settings"), viewport, "settings")


def settings(offline=False):
    """Five rows, so Settings scrolls like every other list (scrollbar + fade)."""
    objs = header("Settings", "settings")
    vp = (16, SETTINGS_Y, 448, SETTINGS_H)
    objs.append(list_viewport("settings", *vp, "settings_row", len(SETTINGS_ROWS)))
    for i, row in enumerate(SETTINGS_ROWS[:5]):
        if offline and i == 0:
            row = ("wifi_off",) + row[1:2] + ("Not connected",) + row[3:]
        if row[3] == "language":
            row = row[:2] + (LANGS[LANG],) + row[3:]
        objs += settings_row(SETTINGS_Y + i * ROW_PITCH, row, vp)
    objs.append(list_fade(LIST_BOTTOM - 24, "settings_fade"))
    objs += scrollbar("settings", SETTINGS_Y, SETTINGS_H, len(SETTINGS_ROWS))
    return objs


def switch(x, y, on, name):
    """52×32 toggle: orange track with the knob right when on, grey track when off."""
    return [container(x, y, 52, 32, ACCENT if on else LINE, 16, name=f"{name}_track"),
            container(x + (23 if on else 3), y + 3, 26, 26, WHITE, 13, name=f"{name}_knob")]


def language_page():
    """Two chips, each language named in its own script so anyone can find theirs."""
    objs = header("Language", "language")
    for i, (code, name) in enumerate(LANGS.items()):
        on = code == LANG
        objs.append(button(24 + i * 224, SUB_CONTENT_Y + 8, 208, 84, name, "medium", 22,
                           PRIMARY_FG if on else TEXT, PRIMARY_BG if on else RAISED, radius=24,
                           action=f"lang:{code}", name=f"button_lang_{code}"))
    objs.append(label(24, 212, 432, "The whole interface switches right away.\nIdea names stay as published.",
                      "sans", 16, TEXT2, "center", h=line_h("sans", 16, 2), name="language_note"))
    return objs


def display_page(timeout=180, rotate=True):
    """Screen-off timeout as five chips (one tap, no sub-page) and Auto-rotate as a switch."""
    objs = header("Display", "display")
    objs.append(section(SUB_CONTENT_Y, "SCREEN OFF AFTER", "display_section"))
    for i, (text, secs) in enumerate(SCREEN_OFF):
        x, y = 24 + (i % 3) * 148, 128 + (i // 3) * 92
        on = secs == timeout
        objs.append(button(x, y, 136, 84, text, "medium", 22, PRIMARY_FG if on else TEXT, PRIMARY_BG if on else RAISED,
                           radius=24, action=f"display:timeout:{secs}", name=f"button_timeout_{secs}"))
    objs += list_row(320, "Auto-rotate", "Follows how you hold it", ("tile", "rotate", "neutral"),
                     "display:rotate", "button_rotate", trail=None, sub_name="display_rotate_sub")
    objs += switch(396, 344, rotate, "rotate_switch")
    objs.append(label(24, 416, 432, "Wi-Fi turns off while the screen is off.", "sans", 16, TEXT2, "center",
                      name="display_note"))
    return objs


def sleep_page():
    """Screen off: Wi-Fi off, backlight at 10 %, one static frame. Tap, motion or any key wakes."""
    wa = text_width("Make Ideas ", "dot", 28)
    x0 = round((W - text_width("Make Ideas Run", "dot", 28)) / 2)
    return [image(180, 104, "assets/anim/home-00.png", name="sleep_logo"),
            label(x0, 236, math.ceil(wa), "Make Ideas", "dot", 28, TEXT, name="sleep_title_a"),
            label(x0 + round(wa), 236, math.ceil(text_width("Run", "dot", 28)) + 2, "Run", "dot", 28, ACCENT,
                  name="sleep_title_b"),
            label(24, 280, 432, PRODUCT, "sans", 18, TEXT2, "center", name="sleep_product"),
            label(24, 404, 432, "Tap or pick up to wake", "sans", 16, TEXT2, "center", name="sleep_hint"),
            touch(0, 0, W, H, "wake", "button_wake")]


def boot_tip():
    """Shown while Boot is held in Vibe Mode: Boot is only for updating Vibe Mode itself."""
    objs = header("Update Vibe Mode", "boot_tip", size=title_size("Update Vibe Mode"))
    objs += [label(24, SUB_CONTENT_Y, 432, "Only needed to install a new Vibe Mode version.", "sans", 18, TEXT,
                   name="boot_tip_body"),
             label(24, SUB_CONTENT_Y + 28, 432, "To enter update mode:", "sans", 16, TEXT2, name="boot_tip_how")]
    boot_chip, w1 = chip(24, 156, "Hold Boot", PRIMARY_FG, ACCENT, "boot_tip_chip_boot")
    plus = label(24 + w1 + 8, 163, 16, "+", "sans", 18, TEXT2, "center")
    power_chip, _ = chip(24 + w1 + 32, 156, "Press power twice", TEXT, LINE, "boot_tip_chip_power")
    size = 5 * QR_MODULES  # 165 px
    host, path = QR_URLS["vibe-update"].split("/", 1)
    objs += [boot_chip, plus, power_chip,
             container(24, 212, size + 18, size + 18, WHITE, 18, name="boot_tip_qr_card"),
             image(33, 221, "assets/qr/vibe-update.png", name="boot_tip_qr", w=size, h=size, qr=True),
             label(228, 216, 228, "Scan for the steps\nand what's new.", "sans", 18, TEXT, h=line_h("sans", 18, 2),
                   name="boot_tip_qr_text"),
             label(228, 268, 228, f"{host}/\n{path}", "sans", 16, TEXT2, h=line_h("sans", 16, 2),
                   name="boot_tip_url"),
             primary(228, ACTION_Y, 228, "Got it", "back", "button_boot_tip_ok")]
    return objs


def update_mode():
    """Entered with Boot held + power pressed twice. Not part of Vibe Mode's stack: power restarts."""
    size = 5 * QR_MODULES
    return [label(24, 40, 432, "Update mode", "dot", 28, TEXT, "center", name="update_title"),
            label(40, 82, 400, "Open the page below on a computer and\nfollow the steps to update Vibe Mode.",
                  "sans", 18, TEXT2, "center", h=line_h("sans", 18, 2), name="update_body"),
            container(148, 140, size + 18, size + 18, WHITE, 18, name="update_qr_card"),
            image(157, 149, "assets/qr/vibe-update.png", name="update_qr", w=size, h=size, qr=True),
            label(24, 340, 432, QR_URLS["vibe-update"], "sans", 16, TEXT2, "center", name="update_url"),
            label(24, 404, 432, "Press power to restart", "sans", 16, TEXT2, "center", name="update_hint")]


# AI key feedback, like an iPhone side button: an orange capsule under the key on the
# screen edge (device-fixed, so it follows the key when the UI rotates) and a chip that
# names what the press did.


def ai_feedback(action="Back"):
    w = math.ceil(text_width(action, "medium", 16)) + 28
    objs = [container(AI_KEY_X - 32, 4, 64, 8, ACCENT, 4, name="ai_feedback_bar"),
            label(AI_KEY_X - w // 2, 20, w, action, "medium", 16, TEXT, "center", h=32, name="ai_feedback_chip",
                  bg=RAISED, radius=16)]
    for o in objs:
        o["role"] = "keyfeedback"
    return objs


HELP_TOPICS = [
    # key, title, QR, icon, tint, one-line hint
    ("start", "Getting started", "help-start", "flag", "neutral", "Set up and run your first Idea"),
    ("develop", "Develop Ideas", "develop", "code", "neutral", "Build one with your AI agent"),
    ("ids", "Idea IDs & sharing", "help-ids", "hash", "neutral", "Find, download and share"),
    ("fix", "Troubleshooting", "help-fix", "support", "neutral", "Wi-Fi, storage, stuck Ideas"),
]
HELP_STEPS = [
    "Plug in USB and ask your agent to build an Idea.",
    "Or download one: open Manage, tap +, type its ID.",
    "Tap an Idea to open it. To come back, hold AI and press power twice.",
]
HELP_TOPIC_STEPS = {
    "start": HELP_STEPS,
    "develop": ["Open the Vibe-coding guide and\nfollow it in your AI agent.",
                "Plug in USB. The agent installs the\nIdea over the cable.",
                "Check Develop for USB and agent status."],
    "ids": ["Every Idea has a 6-digit ID shown\non Mosaico Ideas.",
            "Open Manage, tap +, type the ID\nand press Go.",
            "Share your own Idea to get an ID\nfor friends."],
    "fix": ["No Wi-Fi? Open Settings and\nconnect first.",
            "Not enough space? Delete an Idea\nin Manage.",
            "Stuck inside an Idea? Hold AI and\npress power twice."],
}
HELP_STEP_W = 392


def help_page():
    objs = header("Help", "help")
    for i, (key, title, _, ic, tint, hint) in enumerate(HELP_TOPICS):
        objs += list_row(SUB_CONTENT_Y + i * ROW_PITCH, title, hint, ("tile", ic, tint), f"help:{key}",
                         f"button_help_{key}")
    return objs


def help_topic():
    objs = header("Getting started", "help_topic", size=title_size("Idea IDs & sharing"))
    for i, text in enumerate(HELP_STEPS):
        y = 108 + i * 72
        lines, _ = wrap_lines(text, "sans", 18, HELP_STEP_W, 2)
        objs += [label(24, y, 24, str(i + 1), "dot", 22, ACCENT),
                 label(64, y, HELP_STEP_W, "\n".join(lines), "sans", 18, TEXT, h=line_h("sans", 18, 2), wrap=True,
                       name=f"help_step_{i + 1}")]
    objs.append(secondary(24, ACTION_Y, 432, "Full guide on your phone", "qr:help-start", "button_help_qr", "qr"))
    return objs


def about():
    objs = header("About", "about")
    used = used_mb()
    objs += info_card(SUB_CONTENT_Y, [("Version", f"v{VERSION}", "about_version"),
                                      ("MAC", MAC_ADDRESS, "about_mac"),
                                      ("Storage", f"{used:.1f} of {NAND_CAPACITY_MB:.0f} MB", "about_storage")],
                      "about_card")
    objs.append(secondary(24, ACTION_Y, 432, "Browse Mosaico Ideas", "qr:ideas", "button_about_qr", "qr"))
    return objs


QR_INFO = {  # QR asset: page title, what the code opens
    "develop": ("Vibe-coding guide", "Step-by-step guide to build an Idea with your AI agent."),
    "ideas": ("Mosaico Ideas", "Browse Ideas, find their 6-digit IDs and share your own."),
    "help-start": ("Getting started", "Set up your device and run your first Idea."),
    "help-ids": ("Idea IDs & sharing", "How Idea IDs work and how to share your own Idea."),
    "help-fix": ("Troubleshooting", "Fixes for Wi-Fi, storage and Ideas that get stuck."),
}
IDEA_QR_TEXT = "This Idea's page: details, updates and a link to share it."
QR_STEPS = ("Open your camera", "Point it at the code")
QR_SIZE = 6 * QR_MODULES  # 198 px, 6 px per module


def qr_page(name="develop", title=None, desc=None, url=None):
    """Sub-page with a back button: a modest white QR card on the left, what it opens and
    how to scan it on the right, and the address underneath."""
    title = title or QR_INFO[name][0]
    desc = desc or QR_INFO[name][1]
    url = url or QR_URLS[name]
    objs = header(title, "qr", size=title_size(title))
    card = 24, 112, QR_SIZE + 18
    objs += [container(card[0], card[1], card[2], card[2], WHITE, 20, name="qr_card"),
             image(card[0] + 9, card[1] + 9, f"assets/qr/{name}.png", name="qr_code", w=QR_SIZE, h=QR_SIZE,
                   qr=True)]
    lines, _ = wrap_lines(desc, "sans", 18, 196, 4)
    objs.append(label(260, card[1] + 4, 196, "\n".join(lines), "sans", 18, TEXT, h=line_h("sans", 18, 4),
                      wrap=True, name="qr_desc"))
    for i, step in enumerate(QR_STEPS):
        y = card[1] + 124 + i * 44
        objs += [label(260, y, 20, str(i + 1), "dot", 18, ACCENT),
                 label(284, y, 172, step, "sans", 16, TEXT2, h=line_h("sans", 16, 2), wrap=True)]
    objs += [container(24, 352, 432, 56, CARD, 16, name="qr_url_card"),
             icon(44, 370, "globe", 20, "grey"),
             label(76, 370, 364, url, "sans", 16, TEXT2, name="qr_url", ellipsis=True)]
    return objs


# --------------------------------------------------------------------------
# Wi-Fi
# --------------------------------------------------------------------------
NET_Y = 228
NET_H = LIST_BOTTOM - NET_Y


def network_row(y, ssid, secured, signal, viewport):
    return clipped(list_row(y, ssid, f"{'Secured' if secured else 'Open'} · {signal}",
                            ("tile", f"signal_{SIGNAL_ICON[signal]}", "neutral"), prefix="networks", lock=secured),
                   viewport, "networks")


def wifi(state="connected", pending=""):
    """state: connected | off | connecting. ``pending`` names the task that resumes."""
    connecting = state == "connecting"
    objs = header("Wi-Fi", "wifi", right=[("refresh", "wifi:scan", "button_scan")])
    if state == "connected":
        objs += list_row(SUB_CONTENT_Y, "Studio-5G", f"Connected · {IP_ADDRESS}", ("tile", "wifi", "neutral"),
                         "go:wifi_network", "button_wifi_current", title_name="wifi_connection",
                         sub_name="wifi_detail")
        others = [n for n in NETWORKS if n[0] != "Studio-5G"]
    else:
        hot = bool(pending) or connecting
        objs.append(container(16, SUB_CONTENT_Y, 448, ROW_H, CARD, 20, border=ACCENT if hot else None,
                              bw=2 if hot else 0, name="wifi_card"))
        if connecting:
            objs += [container(28, 108, LEAD, LEAD, TINT_BG["neutral"], 16),
                     image(40, 120, "assets/anim/spin32-00.png", name="wifi_spinner")]
        else:
            objs += lead_tile(28, 108, "wifi_off", "muted", "wifi")
        objs += [label(100, 110, 340, "Maker Lab" if connecting else "Not connected", "medium", 22, TEXT,
                       name="wifi_connection", ellipsis=True),
                 label(100, 142, 340, "Connecting…" if connecting else pending or "Pick a network below",
                       "sans", 16, ACCENT if hot else TEXT2, name="wifi_detail", ellipsis=True)]
        others = NETWORKS
    objs.append(section(196, f"{'OTHER NETWORKS' if state == 'connected' else 'NETWORKS'} · {len(others)}",
                        "wifi_section"))
    vp = (16, NET_Y, 448, NET_H)
    objs.append(list_viewport("networks", *vp, "network_row", len(others)))
    for i, (ssid, secured, signal) in enumerate(others[:3]):
        objs += network_row(NET_Y + i * ROW_PITCH, ssid, secured, signal, vp)
    objs.append(list_fade(LIST_BOTTOM - 24, "networks_fade"))
    objs += scrollbar("networks", NET_Y, NET_H, len(others))
    return objs


def wifi_network():
    objs = header("Studio-5G", "wifi_network", size=title_size("Studio-5G"))
    objs += info_card(SUB_CONTENT_Y, [("Signal", "Strong", "network_signal"), ("Security", "WPA2", "network_security"),
                                      ("IP address", IP_ADDRESS, "network_ip")], "network_card")
    objs.append(label(24, 304, 432, "After forgetting, Ideas stay offline until you reconnect.", "sans", 16, TEXT2, "center"))
    objs += danger(344, "Hold to forget", "hold:forget", "button_forget", "wifi_off")
    return objs


def password(state="typing"):
    if state == "connecting":
        return entry_page("password", "Password", "••••••••••", "Type the password",
                          "Connecting to Maker Lab…", toggle=True, note_color=ACCENT, spinner=True, go=True)
    if state == "error":
        return entry_page("password", "Password", "", "Type the password",
                          "Wrong password. Try again.", toggle=True, note_color=ACCENT)
    return entry_page("password", "Password", "", "Type the password", "For Maker Lab · 8 or more characters",
                      toggle=True)


# --------------------------------------------------------------------------
# Shared info: user key/value pairs in sysmeta/shared (Wi-Fi lives in Settings)
# --------------------------------------------------------------------------
SHARED_Y = SUB_CONTENT_Y
SHARED_H = LIST_BOTTOM - SHARED_Y


def is_secret(key: str) -> bool:
    return any(w in key for w in ("key", "token", "secret", "pass", "pwd"))


def shared_value(entry) -> str:
    return "••••••••" if is_secret(entry["key"]) else entry["value"]


def shared_row(y, entry, viewport, x=16):
    return clipped(list_row(y, entry["key"], shared_value(entry),
                            ("tile", "lock" if is_secret(entry["key"]) else "key", "neutral"),
                            prefix="shared", x=x), viewport, "shared")


def shared(entries=None, swipe=None):
    entries = SHARED_SAMPLE if entries is None else entries
    objs = header("Shared info", "shared", right=[("plus", "go:shared_add", "button_add_entry"),
                                                  ("help", "go:shared_help", "button_shared_help")])
    if not entries:
        objs += [hero(200, 128, "empty", 80, "shared_empty_icon"),
                 label(24, 228, 432, "No shared info yet", "medium", 22, TEXT, "center", name="shared_empty_title"),
                 label(40, 266, 400, "Save a value once, like your city,\nand every Idea can read it.", "sans", 18,
                       TEXT2, "center", h=line_h("sans", 18, 2), name="shared_empty_body"),
                 secondary(24, ACTION_Y, 432, "Add entry", "go:shared_add", "button_add_first", "plus")]
        return objs
    vp = (16, SHARED_Y, 448, SHARED_H)
    objs.append(list_viewport("shared", *vp, "shared_row", len(entries), swipe=True))
    for i, entry in enumerate(entries[:5]):
        y = SHARED_Y + i * ROW_PITCH
        if swipe == i:
            objs += swipe_action(y, vp, "shared")
            objs += shared_row(y, entry, vp, x=16 - SWIPE_SHIFT)
        else:
            objs += shared_row(y, entry, vp)
    objs += scrollbar("shared", SHARED_Y, SHARED_H, len(entries))
    return objs


def shared_entry(entry=None):
    """Both the key and the value can be edited; Delete closes the page with Undo."""
    entry = entry or SHARED_SAMPLE[0]
    objs = header(entry["key"], "shared_entry", size=title_size(entry["key"]))
    objs += list_row(SUB_CONTENT_Y, "Key", entry["key"], ("tile", "key", "neutral"), "go:shared_key",
                     "button_edit_key", sub_name="entry_key")
    objs += list_row(SUB_CONTENT_Y + ROW_PITCH, "Value", shared_value(entry), ("tile", "id", "neutral"),
                     "go:shared_value", "button_edit_value", sub_name="entry_value")
    objs.append(label(24, 292, 432, f"Ideas read it as shared/{entry['key']}", "sans", 16, TEXT2, "center",
                      name="entry_hint", ellipsis=True))
    objs.append(delete_button(24, ACTION_Y, 432, "entry:delete", "button_delete_entry", "Delete entry"))
    return objs


SHARED_HELP = ("Shared info is a short list of keys and values kept on this device. Every Idea "
               "can read it, so you only enter things like your city or an API key once.")
SHARED_EXAMPLES = [("city", "Weather"), ("api_key", "Skills")]


def shared_help():
    objs = header("About shared info", "shared_help", size=title_size("About shared info"))
    lines, _ = wrap_lines(SHARED_HELP, "sans", 18, 432, 4)
    objs.append(label(24, SUB_CONTENT_Y, 432, "\n".join(lines), "sans", 18, TEXT, h=line_h("sans", 18, 4),
                      wrap=True, name="shared_help_body"))
    objs.append(section(200, "FOR EXAMPLE"))
    objs.append(container(16, 228, 448, 64 * len(SHARED_EXAMPLES), CARD, 20, name="shared_help_card"))
    for i, (key, reader) in enumerate(SHARED_EXAMPLES):
        y = 228 + i * 64
        if i:
            objs.append(container(36, y, 408, 1, DIVIDER))
        objs += [label(36, y + 21, 160, key, "medium", 18, TEXT),
                 label(196, y + 22, 248, f"read by {reader}", "sans", 16, TEXT2, "right", ellipsis=True)]
    objs.append(label(24, 372, 432, "Keys: a–z, 0–9 and _, up to 15 characters.\n"
                                    "Values: up to 256 characters.", "sans", 16, TEXT2, "center",
                      h=line_h("sans", 16, 2), name="shared_help_rules"))
    return objs


# --------------------------------------------------------------------------
# States (one mockup each)
# --------------------------------------------------------------------------
def build_states():
    states = []

    def add(sid, page, title, objects, **meta):
        states.append({"id": sid, "page": page, "title": title, "objects": objects, **meta})

    add("home", "home", "Home", home())
    add("home-first", "home", "Home · first use, swipe hint", home(hint=True, show_label=True))
    add("home-offline", "home", "Home · offline", home(offline=True))
    add("home-ai-key", "home", "Home · AI pressed (locks)", home() + ai_feedback("Lock"))
    add("sleep", "sleep", "Screen off (10 % backlight, Wi-Fi off)", sleep_page(), backlight=10)
    for k in range(1, idea_page_count(len(PRESETS)) + 1):
        add(f"ideas-{k}", "ideas", f"Ideas · page {k}/{idea_page_count(len(PRESETS))}", ideas_page(k))
    add("ideas-empty", "ideas", "Ideas · none yet", ideas_empty())
    add("ideas-confirm", "ideas", "Ideas · confirm before opening",
        ideas_page(1, show_label=False) + confirm_open(BY_ID["100002"]))
    add("manage", "manage", "Manage", manage())
    add("manage-updating", "manage", "Manage · updating", manage(updating=True))
    add("manage-swipe", "manage", "Manage · swiped to delete", manage(swipe=1))
    add("manage-undo", "manage", "Manage · deleted, Undo",
        manage(ideas=[i for i in PRESETS if i["id"] != "100002"], undo="Clock"))
    add("manage-uptodate", "manage", "Manage · up to date", manage(updates=False))
    for mode, title in (("local", "on this device"), ("update", "update available"),
                        ("remote", "from the store"), ("nospace", "not enough space"),
                        ("current", "current Idea")):
        add(f"idea-info-{mode}", "idea_info", f"Idea info · {title}", idea_info(mode))
    add("idea-info-deleting", "idea_info", "Idea info · holding Delete (3 s)", idea_info("local", held=0.6))
    add("download", "download", "Download · empty", download())
    add("download-typing", "download", "Download · typing, key 1 held down", download("2381", pressed="1"))
    add("download-ready", "download", "Download · six digits, Go ready", download("238114"))
    add("download-lookup", "download", "Download · looking up", download("238114", True))
    add("download-error", "download", "Download · not found", download("404040", error="No Idea with this ID"))
    add("download-offline", "download", "Download · offline", download(offline=True))
    add("progress-download", "progress", "Progress · download and install", progress_page("download"))
    add("progress-install", "progress", "Progress · installing", progress_page("install"))
    add("progress-switch", "progress", "Progress · switching Ideas", progress_page("switch"))
    add("progress-agent", "progress", "Progress · AI agent install", progress_page("agent"))
    for kind, title in (("saved", "saved"), ("failed", "failed"), ("nospace", "no space"),
                        ("battery", "low battery")):
        add(f"result-{kind}", "result", f"Result · {title}", result(kind))
    add("launching", "launching", "Opening an Idea", launching())
    add("running", "app_running", "Your Idea is running", launching(running=True))
    add("boot", "boot", "Boot", boot())
    add("boot-tip", "boot_tip", "Boot key held · update tip", boot_tip())
    add("update-mode", "update_mode", "Vibe Mode update mode", update_mode())
    add("develop", "develop", "Develop · USB and agent ready", develop())
    add("develop-unplugged", "develop", "Develop · unplugged", develop(False, False))
    add("develop-waiting", "develop", "Develop · waiting for agent", develop(True, False))
    add("settings", "settings", "Settings", settings())
    add("settings-ai-key", "settings", "Settings · AI pressed (back)", settings() + ai_feedback("Back"))
    add("display", "display", "Display · screen off and auto-rotate", display_page())
    add("display-never", "display", "Display · never off, rotation locked", display_page(0, False))
    add("language", "language", "Language", language_page())
    add("wifi", "wifi", "Wi-Fi · connected", wifi())
    add("wifi-off", "wifi", "Wi-Fi · not connected", wifi("off"))
    add("wifi-pending", "wifi", "Wi-Fi · resumes a task", wifi("off", "Connect to look up 238114"))
    add("wifi-connecting", "wifi", "Wi-Fi · connecting", wifi("connecting"))
    add("wifi-network", "wifi_network", "Wi-Fi · this network", wifi_network())
    add("password", "password", "Password", password())
    add("password-connecting", "password", "Password · connecting", password("connecting"))
    add("password-error", "password", "Password · wrong", password("error"))
    add("shared", "shared", "Shared info", shared())
    add("shared-swipe", "shared", "Shared info · swiped to delete", shared(swipe=2))
    add("shared-empty", "shared", "Shared info · empty", shared([]))
    add("shared-help", "shared_help", "Shared info · what it is", shared_help())
    add("shared-entry", "shared_entry", "Shared info · entry", shared_entry())
    add("shared-add-key", "shared_add", "Shared info · new key",
        entry_page("shared_add_key", "New key", "", "Key", "a–z, 0–9 and _ · up to 15 characters"))
    add("shared-add-value", "shared_add", "Shared info · new value",
        entry_page("shared_add_value", "Value", "Shanghai", "Value", "Value for city · up to 256 characters"))
    add("shared-edit-key", "shared_add", "Shared info · rename key",
        entry_page("shared_add_key", "Rename key", "city", "Key", "Ideas that use city need the new name"))
    add("help", "help", "Help · topics", help_page())
    add("help-topic", "help_topic", "Help · topic", help_topic())
    add("about", "about", "About", about())
    add("qr-develop", "qr", "QR code · vibe-coding guide", qr_page("develop"))
    idea = BY_ID["100001"]
    add("qr-idea", "qr", "QR code · an Idea", qr_page("idea-100001", idea["name"], IDEA_QR_TEXT,
                                                      idea["url"].replace("https://", "")))
    return states


# --------------------------------------------------------------------------
# Prototype-only states and row templates
# --------------------------------------------------------------------------
def prototype_extras():
    extras = [
        {"id": "home-toast", "page": "home", "objects": home(toast="Saved")},
        {"id": "ideas-toast", "page": "ideas", "objects": ideas_page(1, toast="Cancelled")},
        {"id": "settings-toast", "page": "settings", "objects": settings() + toast("Can't delete the current Idea")},
    ]
    vp = (16, 0, 448, ROW_H)
    templates = {
        "manage_row": relative(manage_row(0, PRESETS[1], vp), 16, 0),
        "network_row": relative(network_row(0, "Maker Lab", True, "Good", vp), 16, 0),
        "settings_row": relative(settings_row(0, SETTINGS_ROWS[0], vp), 16, 0),
        "ai_feedback": ai_feedback("Back"),
        "shared_row": relative(shared_row(0, SHARED_SAMPLE[0], vp), 16, 0),
        "swipe_action": relative(swipe_action(0, vp, "row"), 16, 0),
        "toast": toast("Saved"),
        "toast_undo": toast("Deleted Clock", undo=True),
        "confirm": confirm_open(BY_ID["100002"]),
        "confirm_check": [o for o in confirm_open(BY_ID["100002"], checked=True)
                          if (o.get("name") or "").startswith("confirm_skip")],
        "delete_popup": delete_popup(BY_ID["100012"]),
    }
    return extras, templates


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
def rgb(color: str):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def draw_text(img, draw, obj, text, box, color, align="left", offset=0.0):
    f = font_for(obj["font"], obj["size"], text)
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
    keys.append((104, ky, 272, key_h, kb.get("space_label", "space"), kb["key_color"], kb["fg_color"]))
    go = kb.get("go_enabled")
    keys.append((384, ky, 80, key_h, kb.get("go_label", "GO"), kb["ok_color"] if go else kb["ok_disabled_color"],
                 kb["ok_text_color"] if go else kb["ok_disabled_text_color"]))
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
            face = font_for(kb["font"], size, text)
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
        # Paint a run of objects sharing one viewport, then keep only the viewport.
        j = i
        while j < len(objects) and objects[j].get("clip") == clip:
            j += 1
        layer = paint(img.copy(), objects[i:j])
        x, y, w, h = clip
        img.paste(layer.crop((x, y, x + w, y + h)), (x, y))
        i = j
    if state.get("backlight"):
        # Mockup preview of a dimmed backlight (the layout itself keeps full colours).
        img = Image.eval(img, lambda v: round(v * (0.25 + 0.75 * state["backlight"] / 100)))
    out = img.convert("RGBA")
    out.putalpha(screen_mask())
    return out


def paint(img: Image.Image, objects) -> Image.Image:
    draw = ImageDraw.Draw(img)
    for obj in objects:
        t = obj["type"]
        x, y, w, h = obj["x"], obj["y"], obj["w"], obj["h"]
        if t in ("container", "button", "progress", "image") and (w <= 0 or h <= 0):
            continue  # an empty hold-fill has no pixels
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
        if obj.get("role") in ("scrim", "dim", "background", "row", "sheet") or not (obj.get("bg") or obj.get("border")):
            return []
        if obj["w"] <= 0:
            return []
        return [(obj["x"], obj["y"], obj["w"], obj["h"], obj.get("radius", 0))]
    if t == "button":
        if not (obj.get("bg") or obj.get("border") or obj.get("text") or obj.get("icon")):
            return []
        return [(obj["x"], obj["y"], obj["w"], obj["h"], obj.get("radius", 0))]
    if obj.get("role") == "fade":
        return []
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


def fully_visible(o) -> bool:
    """True for unclipped objects and for clipped ones that lie inside their viewport."""
    clip = o.get("clip")
    if not clip:
        return True
    cx, cy, cw, ch = clip
    return o["x"] >= cx and o["y"] >= cy and o["x"] + o["w"] <= cx + cw and o["y"] + o["h"] <= cy + ch


def top_layer_buttons(objs):
    """Tappable buttons on the topmost layer: everything after the last scrim,
    except rows that are cut off by their scrolling viewport."""
    start = max((i for i, o in enumerate(objs) if o.get("role") == "scrim"), default=-1) + 1
    return [o for o in objs[start:] if o["type"] == "button" and o.get("action") and fully_visible(o)]


def is_nav(obj) -> bool:
    return obj.get("role") == "nav" or (obj.get("name") or "").startswith("nav_")


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
            # Root pages: the status bar owns everything above CONTENT_Y.
            # Sub-pages: no status bar at all; the header takes the top of the screen.
            if st["page"] in ROOT_PAGES:
                if (not is_nav(obj) and not obj.get("clip") and obj.get("role") not in ("sheet", "scrim", "dim", "dialog", "keyfeedback")
                        and any(shape[1] < CONTENT_Y for shape in visible_shapes(obj))):
                    problems.append(f"{where} has visible content above y={CONTENT_Y} (status bar only)")
            elif is_nav(obj):
                problems.append(f"{where}: sub-pages have no status bar")
            if t == "button" and obj.get("action"):
                touch_min = DENSE_TOUCH if obj.get("touch_class") in ("dense", "numpad") else MIN_TOUCH
                if w < touch_min or h < touch_min:
                    problems.append(f"{where} touch target {w}x{h} is below {touch_min}x{touch_min}")
                if obj.get("danger"):
                    if h < DANGER_TOUCH:
                        problems.append(f"{where} danger target height {h} is below {DANGER_TOUCH}")
                    if fully_visible(obj) and (x < 24 or W - (x + w) < 24 or y < 24 or H - (y + h) < 24):
                        problems.append(f"{where} danger target must stay 24 px from screen edges")
                    if obj.get("hold_ms") != DANGER_HOLD_MS:
                        problems.append(f"{where} danger target must hold for {DANGER_HOLD_MS} ms")
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
                if obj["color"] == TEXT3 and not obj.get("disabled"):
                    problems.append(f"{where} uses the disabled colour {TEXT3} on enabled text")
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


# Dynamic strings measured in their real roles. Idea names and SSIDs ellipsize.
# Root pages flash messages in the status-bar badge (164 px, medium 16); sub-pages
# show them in the bottom toast (288 px plain, 200 px next to Undo).
NAV_MESSAGES = [
    "Home", "Ideas 12/12", "Saved", "Cancelled", "Updated", "Up to date",
    "Connected", "Agent ready", "Please wait", "Updating · wait", "Updates paused",
]
TOASTS = [
    "Saved", "Cancelled", "Updated", "Up to date", "Connected", "Forgotten", "Please wait", "Hold to confirm",
    "Updating · wait", "Updates paused", "Agent ready", "Wrong password", "Open another Idea first",
    "Can't delete the current Idea", "Finish the update first", "Hold for 3 s to delete", "Not deleted",
    "Already saved", "Install an Idea over USB first", "Hold for 3 s to forget", "Not forgotten",
    "Screen off after 10 min", "Screen stays on", "Auto-rotate on", "Auto-rotate off",
]
DOWNLOAD_ERRORS = [
    "Enter the 6-digit ID from Mosaico Ideas", "Type all 6 digits", "No Idea with this ID", "This Idea was removed", "Not for this device",
    "Download not allowed", "Store is busy. Try later.", "Can't reach the store", "Not enough storage",
]
ROW_SUBS = [  # second line of a list row (312 px; 280 px next to a lock icon)
    "v10.12.3 · 312.4 MB", "Update to v10.13.0", "Updating · 100%", "Waiting", "Paused · no Wi-Fi", "Current",
    "Connected · 192.168.100.200", "Scan for the step-by-step guide", "Publish it on Mosaico Ideas",
    "New version on Mosaico Ideas", "How-to guides and fixes", "12 entries", "hello_world · keep it for later",
    "Install an Idea over USB first", "hello_world is saved", "Screen off after 10 min", "Screen stays on",
    "Follows how you hold it", "Stays in this orientation",
    *[t[5] for t in HELP_TOPICS], "sk-demo-4c8e9a12b3", "••••••••",
]
COPY = [
    (164, "medium", 16, NAV_MESSAGES),
    (TOAST_W - 48, "sans", 18, TOASTS),
    (432, "sans", 16, ["Looking up…"] + DOWNLOAD_ERRORS),
    (302, "medium", 22, [s for s, _ in INFO_STATUS.values()]),
    (320, "sans", 18, ["Smart home · Community · v10.12.3", "Needs 12.5 MB · 0.4 MB free",
                       "Chat · Community · v2.1.0", "312.4 MB · ID 100012"]),
    (312, "medium", 22, [p[0] for p in PROGRESS.values()] + ["Update to v10.13.0"]),
    (312, "sans", 16, [p[5] for p in PROGRESS.values()] + ["Step 2 of 2 · Install"]),
    (432, "sans", 16, [p[4] for p in PROGRESS.values()] + ["312.40 of 312.40 MB · 1.6 MB/s"]),
    (432, "medium", 28, [r[1] for r in RESULTS.values()] + ["Idea updated"]),
    (432, "sans", 18, ["Opening in 1 s", "Connect Wi-Fi to download Ideas."]),
    (340, "sans", 16, ["Not connected", "Connecting…", "Pick a network below", "Connect to look up 238114",
                       "Connect to update Typhoon Monitor", "Connect to get updates"]),
    (312, "sans", 16, ROW_SUBS),
    (280, "sans", 16, ["Secured · Strong", "Open · Good", "Secured · Weak"]),
    (416, "sans", 16, ["a–z, 0–9 and _ · up to 15 characters", "Value for city · up to 256 characters",
                       "Ideas that use city need the new name", "Key already used", "Type a key first",
                       "Type a value first", "Use 8 or more characters", "Max 256 characters",
                       "Use a–z, 0–9 and _ only"]),
    (432, "sans", 16, ["After forgetting, Ideas stay offline until you reconnect.", "To come back: hold AI, press power twice.",
                       "Ideas read it as shared/abcdefghijklmno"]),
    (326, "sans", 16, ["USB connected · Waiting for agent", "USB connected · Agent ready", "Plug in a USB cable"]),
    (360, "sans", 16, ["Vibe Mode closes while it runs.", "Unsaved hello_world will be replaced."]),
    (312, "sans", 16, ["Keep holding for 3 s. Let go to cancel."]),
    (DELETE_HELD[2] - 32, "medium", 22, ["Keep holding · 3 s"]),
]


def check_copy() -> list[str]:
    problems = []
    for width, font, size, texts in COPY:
        for text in texts:
            text = loc(text)
            w = text_width(text, font, size)
            if w > width:
                problems.append(f"copy {text!r} is {w:.0f} px wide in a {width} px label")
            missing = missing_glyphs(text, font)
            if missing:
                problems.append(f"copy {text!r} has no glyph for {''.join(missing)!r}")
    for text in [info[1] for info in QR_INFO.values()] + [IDEA_QR_TEXT]:
        if wrap_lines(text, "sans", 18, 196, 4)[1]:
            problems.append(f"QR description {text!r} needs more than four lines")
    if wrap_lines(SHARED_HELP, "sans", 18, 432, 4)[1]:
        problems.append("shared info explanation needs more than four lines")
    return problems


# Words that stay in English inside the Chinese UI (product terms, units, protocol names).
KEEP_LATIN = {"Vibe", "Mode", "Mosaico", "Ideas", "Idea", "AI", "Agent", "Wi-Fi", "USB", "NAND", "IMU", "Boot",
              "MB", "KB", "MAC", "ID", "IP", "WPA", "API", "English", "Coding", "GO", "ABC", "s"}


def check_untranslated(states, templates) -> list[str]:
    """Chinese build: every visible string must be Chinese apart from names and kept terms."""
    names = {i["name"] for i in PRESETS + STORE_ONLY} | {"hello_world", PRODUCT}
    names |= {n[0] for n in NETWORKS} | {e["key"] for e in SHARED_SAMPLE} | {e["value"] for e in SHARED_SAMPLE}
    names |= set(QR_URLS.values()) | {i["url"].replace("https://", "") for i in PRESETS + STORE_ONLY}
    problems = []
    objs = [(st["id"], o) for st in states for o in st["objects"]]
    objs += [(f"template {k}", o) for k, v in templates.items() for o in v]
    for where, o in objs:
        text = o.get("text") or ""
        if not text.strip() or o["type"] not in ("label", "button"):
            continue
        rest = re.sub(r"https?://\S+|[\w.-]+\.(com|cn)/?\s*[\w/.-]*|shared/\w+", " ", text)
        for n in sorted(names, key=len, reverse=True):
            rest = rest.replace(n, " ")
        rest = re.sub(r"v\d[\w.]*|([0-9A-F]{2}:){5}[0-9A-F]{2}|\b[a-z]–[a-z]\b|\d[\d.:]*", " ", rest)
        words = [w for w in re.findall(r"[A-Za-z][A-Za-z\-]*", rest) if w not in KEEP_LATIN]
        if words:
            problems.append(f"zh {where}: untranslated {text!r}")
    return sorted(set(problems))


def check_templates(templates) -> list[str]:
    """Row templates, toasts and dialogs are drawn only by the prototype; their images must exist too."""
    problems = []
    for name, objs in templates.items():
        for o in objs:
            for path in (o.get("image"), (o.get("icon") or {}).get("image")):
                if path and not (DESIGN / path).exists():
                    problems.append(f"template {name}: image {path} does not exist")
    return problems


def check_store_text() -> list[str]:
    """Store summaries fit three lines, Idea names fit the two-line grid label and every
    Idea has its glyph, icons and QR code."""
    problems = []
    for idea in PRESETS + STORE_ONLY:
        iid = idea["id"]
        if len(idea["summary"]) > 120 or not idea["summary"].isascii():
            problems.append(f"summary of {iid} must be ASCII and <= 120 characters")
        if wrap_lines(idea["summary"], "sans", 18, 432, 3)[1]:
            problems.append(f"summary of {iid} needs more than three lines")
        if len(idea["name"]) > 24:
            problems.append(f"name of {iid} is longer than 24 characters")
        if wrap_lines(idea["name"], "medium", 18, 144, 2)[1]:
            problems.append(f"name of {iid} needs more than two lines in the Ideas grid")
        for size in (56, 96, 108):
            if not (DESIGN / f"assets/ideas/{idea['icon']}-{size}.png").exists():
                problems.append(f"{iid} is missing its icon {idea['icon']}-{size}.png")
        if not (DESIGN / f"assets/qr/idea-{iid}.png").exists():
            problems.append(f"{iid} is missing its QR code")
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
    used |= {"back-28-white.png", "backspace-28-white.png", "battery_full-20-white.png",
             "battery_charging-20-white.png", "battery_low-20-orange.png", "eye_off-32-white.png",
             "wifi-20-white.png", "wifi_off-20-grey.png", "usb-20-white.png", "usb-20-grey.png",
             "usb-20-orange.png", "signal_0-20-grey.png", "signal_1-20-white.png",
             "signal_2-20-white.png", "signal_3-20-white.png", "lock-20-grey.png",
             "wifi-32-orange.png", "wifi_off-32-grey.png", "usb-32-grey.png", "usb-32-white.png",
             "signal_1-32-blue.png", "signal_3-32-blue.png", "key-32-teal.png", "lock-32-teal.png",
             "refresh-32-white.png", "trash-32-black.png"}
    pngs = list((DESIGN / "assets/icons").glob("*.png"))
    return sorted(p.name for p in pngs if p.name not in used)


def layout_tables(states) -> str:
    """Human-readable appendix: every named or interactive object per page."""
    lines = ["# 附录：逐页布局表", "",
             "由 `tools/build_design.py` 生成，与 `layout.json` 和页面图一致；坐标单位为 480×480 逻辑像素。",
             "只列出有名称（阶段 B 需要绑定或更新）或可点击的对象；装饰对象见 `layout.json`。", ""]
    seen = set()
    for st in states:
        if st["page"] in seen and not st["id"].startswith(("progress", "result", "idea-info", "ideas-1",
                                                           "download", "wifi", "shared", "manage", "qr")):
            continue
        seen.add(st["page"])
        lines += [f"## {st['id']} — {st['title']}", "", f"![{st['id']}](mockups/{st['id']}.png)", "",
                  "| 名称 | 类型 | x, y, w, h | 样式 | 内容 / 动作 |", "|---|---|---|---|---|"]
        for o in st["objects"]:
            if o["type"] == "list_viewport":
                lines.append(f"| `{o['name']}` | list | {o['x']}, {o['y']}, {o['w']}, {o['h']} | "
                             f"行距 {o['item_height']} | 行模板 `{o['row_template'] or '固定行'}` |")
                continue
            if o.get("row_of") or not (o.get("name") or o.get("action")):
                continue
            style = ""
            if o["type"] in ("label", "button") and o.get("text"):
                style = f"{o['font']} {o['size']}px {o['color']}" + (" 换行" if o.get("wrap") else "")
            elif o["type"] == "image" and o.get("qr"):
                style = f"QR，每模块 {o['w'] // QR_MODULES} px"
            elif o.get("bg"):
                style = o["bg"]
            if o.get("danger"):
                style += f" 长按 {o['hold_ms']} ms"
            content = (o.get("text") or "").replace("\n", " ⏎ ").replace("|", "\\|")
            if o.get("action"):
                content += f"{' → ' if content else '→ '}`{o['action']}`"
            if o["type"] == "image":
                content = o["image"].split("/")[-1]
            lines.append(f"| `{o.get('name') or '—'}` | {o['type']} | {o['x']}, {o['y']}, {o['w']}, {o['h']} | "
                         f"{style} | {content} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def networks_json():
    return [{"ssid": s, "secured": sec, "signal": sig} for s, sec, sig in NETWORKS]


def render_all(states, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
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


_CJK_PUNCT = set("，。、：；？！）」』…·「『（ ")


def cjk_line_problems(text: str, font: str, size: int, width: float, align: str = "left") -> list[str]:
    """Chinese line breaks. A last line of one or two characters reads as a slip; a line
    wider than its box gets re-broken by the browser; a key name such as "AI 键" must not
    be split; and in left-aligned copy a hand break that leaves a short line looks cut
    off. Write such copy as one flowing line, or break at a comma where the first line
    is nearly full."""
    if not has_cjk(text):
        return []
    paras = text.split("\n")
    lines = [l for para in paras for l in (wrap_lines(para, font, size, width, 99)[0] or [""])]
    out = [f"line wider than {width:.0f} px: “{l}”" for l in lines if text_width(l, font, size) > width + 0.5]
    if len(lines) > 1 and len([c for c in lines[-1] if c not in _CJK_PUNCT]) <= 2:
        out.append(f"last line is only “{lines[-1]}”")
    out += [f"splits the key name “{a.split()[-1]} 键”" for a, b in zip(lines, lines[1:]) if b.startswith("键") and a.strip()]
    if align == "left":
        out += [f"short hand-broken line “{p}”" for p in paras[:-1] if text_width(p, font, size) < 0.75 * width]
    return out


def check_cjk_lines(states, templates) -> list[str]:
    problems = []
    objs = [(st["id"], o) for st in states for o in st["objects"]]
    objs += [(f"template {k}", o) for k, v in templates.items() for o in v]
    for where, o in objs:
        if o["type"] == "label" and o.get("overflow") != "ellipsis" and o.get("text"):
            problems += [f"{where}/{o.get('name')}: {p}"
                         for p in cjk_line_problems(o["text"], o["font"], o["size"], o["w"], o.get("align", "left"))]
    for idea in PRESETS + STORE_ONLY:
        problems += [f"summary of {idea['id']}: {p}" for p in cjk_line_problems(loc(idea["summary"]), "sans", 18, 432)]
    for key, steps in HELP_TOPIC_STEPS.items():
        for n, step in enumerate(steps, 1):
            problems += [f"help {key} step {n}: {p}" for p in cjk_line_problems(loc(step), "sans", 18, HELP_STEP_W)]
    return problems


def build_locale(lang: str):
    set_lang(lang)
    states = build_states()
    extras, templates = prototype_extras()
    problems = check(states, extras) + check_templates(templates)
    if lang == "zh":
        problems += check_untranslated(states, templates) + check_cjk_lines(states, templates)
    return states, extras, templates, [f"[{lang}] {p}" for p in problems]


def main() -> int:
    zh_states, zh_extras, zh_templates, zh_problems = build_locale("zh")
    render_all(zh_states, DESIGN / "mockups/zh")
    states, extras, templates, problems = build_locale("en")   # English last: it is the source
    render_all(states, DESIGN / "mockups")
    problems += zh_problems
    layout = {"schema": "vibe-mode-design/11", "screen": {"w": W, "h": H}, "tokens": TOKENS,
              "states": states,
              "locales": {"zh": {"name": LANGS["zh"], "states": zh_states}},
              "prototype": {"states": extras, "row_templates": templates,
                            "locales": {"zh": {"states": zh_extras, "row_templates": zh_templates}},
                            "i18n": {"zh": ZH, "category_zh": CATEGORY_ZH, "langs": LANGS},
                            "row_heights": {"manage": ROW_PITCH, "networks": ROW_PITCH, "shared": ROW_PITCH,
                                            "settings": ROW_PITCH},
                            "categories": [{"id": k, "label": t, "icon": i} for k, t, i in CATEGORIES],
                            "ideas": PRESETS, "store_only": STORE_ONLY, "store_updates": STORE_UPDATES,
                            "current": CURRENT, "nand_capacity_mb": NAND_CAPACITY_MB,
                            "shared_sample": SHARED_SAMPLE, "product": PRODUCT, "version": VERSION,
                            "networks": networks_json(), "qr_urls": QR_URLS,
                            "qr_info": {k: {"title": t, "desc": d} for k, (t, d) in QR_INFO.items()},
                            "idea_qr_text": IDEA_QR_TEXT,
                            "help_topics": [{"key": k, "title": t, "qr": q, "steps": HELP_TOPIC_STEPS[k]}
                                            for k, t, q, *_ in HELP_TOPICS],
                            "settings_rows": [{"icon": i, "title": t, "sub": sub, "go": g, "button": b, "sub_name": n}
                                              for i, t, sub, g, b, n in SETTINGS_ROWS],
                            "screen_off": [{"label": t, "s": v} for t, v in SCREEN_OFF],
                            "pager": {"page_count": pager_total(len(PRESETS)), "ideas_per_page": IDEAS_PER_PAGE,
                                      "ideas_pages": idea_page_count(len(PRESETS)), "y": 440,
                                      "active_w": 20, "inactive_w": 8, "dot_h": 8, "gap": 8},
                            "grid": {"centers_x": list(GRID_X), "icon_y": list(GRID_ICON_Y), "icon": 108,
                                     "hit": [152, 170]},
                            "interactions": {
                                "danger_hold_ms": DANGER_HOLD_MS,
                                "edge_back_start_px": 24, "edge_back_commit_px": 96,
                                "edge_back_flick_px_ms": 0.45,
                                "page_ms": 260, "nav_flash_ms": 1200, "nav_toast_ms": 2400,
                                "toast_ms": TOAST_MS, "undo_ms": UNDO_MS, "page_label_ms": 2000,
                                "swipe_shift_px": SWIPE_SHIFT, "swipe_commit_px": SWIPE_SHIFT // 2,
                                "switch_cancel_ms": 1500, "pager_swipe_px": 56,
                                "page_easing": "cubic-bezier(.32,.72,0,1)",
                            }}}
    (DESIGN / "layout.json").write_text(json.dumps(layout, indent=1, ensure_ascii=False) + "\n",
                                        encoding="utf-8")
    (DESIGN / "layout-tables.md").write_text(layout_tables(states), encoding="utf-8")
    for p in problems:
        print("check:", p)
    for name in unused_images(states + zh_states, extras + zh_extras, {**templates, **zh_templates}):
        print("note: unused image", name)
    print(f"{len(states)} states × 2 languages rendered; {len(problems)} layout issues")
    return 1 if problems and "--strict" in sys.argv else 0


if __name__ == "__main__":
    raise SystemExit(main())
