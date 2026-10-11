#!/usr/bin/env python3
"""Build the Vibe Mode 0.3 design: layout data, mockups and layout checks.

Every page state is described once with GSP 1.4.0 primitives (layer content as
containers, labels, buttons, images, a progress bar and the native keyboard).
The same data produces ``layout.json`` (the source for the Phase B scene),
the PNG mockups and the clickable prototype (``build_prototype.py``).

Mockups are approximate design renders made with Pillow and the subset fonts;
they are not GSP simulator or device screenshots. Requires Pillow. Run
``generate_assets.py`` first.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from sample_data import (CATEGORIES, CATEGORY_LABEL, CURRENT, FAVORITES, PRESETS, STORE_ONLY,
                         STORE_UPDATES)

DESIGN = Path(__file__).resolve().parents[1]
W = H = 480
M = 16  # outer margin
# The visible screen has large rounded corners (product photo). 40 px is an
# assumption until the display drawing is checked; layouts keep every visible
# object inside it.
SCREEN_R = 40
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
    "dot": "assets/fonts/Doto-Black.subset.ttf",
    "sans": "assets/fonts/NotoSansSC-Regular.subset.ttf",
    "medium": "assets/fonts/NotoSansSC-Medium.subset.ttf",
}
# Line height per em, from the subset fonts' vertical metrics.
LINE_EM = {"dot": 1.0, "sans": 1.25, "medium": 1.25}
# Readability on the real screen: 480 x 480 on a 2.1-inch diagonal is 37.7 mm
# wide, about 323 ppi, so 1 px = 0.079 mm. Text below 22 px (1.7 mm) and touch
# targets below 72 px (5.7 mm) are rejected by the layout check, and only the
# sizes on this scale are allowed.
PX_MM = 2.1 * 25.4 / math.sqrt(2) / 480  # 0.0786 mm per pixel
TYPE_SCALE = {"dot": [32, 40, 44, 64, 120], "medium": [22, 28, 34], "sans": [22, 26]}
MIN_TEXT, MIN_TOUCH, MIN_ICON = 22, 72, 28

TOKENS = {
    "colors": {"background": BG, "card": CARD, "raised": RAISED, "tile": TILE, "outline": LINE,
               "divider": DIVIDER, "text": TEXT, "text_secondary": TEXT2, "text_tertiary": TEXT3,
               "accent": ACCENT, "primary_bg": PRIMARY_BG, "primary_fg": PRIMARY_FG},
    "fonts": FONTS,
    "line_height_em": LINE_EM,
    "type_scale": TYPE_SCALE,
    "radius": {"card": 20, "row": 16, "key": 18, "chip": 22, "pill": "h/2"},
    "margin": M,
    "min_touch": MIN_TOUCH,
    "readability": {"diagonal_inch": 2.1, "px_mm": round(PX_MM, 4), "min_text_px": MIN_TEXT,
                    "body_text_px": 26, "min_touch_px": MIN_TOUCH, "min_icon_px": MIN_ICON},
    "screen": {"corner_radius": SCREEN_R, "ai_key_center_x": AI_KEY_CX},
    "qr": {"version": 3, "ecc": "L", "quiet_zone_modules": 2, "modules": QR_MODULES,
           "min_module_px": 5, "dark": "#000000", "light": "#FFFFFF"},
    "motion": {"page_slide_px": 48, "page_slide_ms": 160, "easing": "ease_out"},
    "keyboard": {"bg_color": BG, "fg_color": TEXT, "key_color": TILE, "function_color": RAISED,
                 "ok_color": ACCENT, "ok_text_color": WHITE, "key_radius": 10, "font": "medium",
                 "font_size": 22, "function_font_size": 22},
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


# Single-line labels showing app names, SSIDs, versions or store text truncate
# with an ellipsis (GSP `overflow: "ellipsis"`) instead of clipping mid-glyph.
ELLIPSIS = {"apps_name", "apps_detail", "detail_name", "detail_meta", "detail_facts", "switch_name",
            "switch_detail", "progress_detail", "result_caption", "wifi_connection", "wifi_detail",
            "networks_title", "device_wifi", "device_city", "password_subtitle", "ai_toast_text",
            "launch_title", "running_title", "qr_full_title", "qr_full_url", "city_display",
            "home_title", "switch_filter", "about_name", "about_facts", "apps_detail_current",
            "city_value", "token_value", "device_summary", "device_token", "progress_bytes"}


def label(x, y, w, text, font="sans", size=16, color=TEXT, align="left", h=None, name=None,
          bg=None, radius=0, dynamic=False, wrap=False):
    lines = text.count("\n") + 1
    obj = {"type": "label", "x": x, "y": y, "w": w, "h": h or line_h(font, size, lines),
           "text": text, "font": font, "size": size, "color": color, "align": align,
           "name": name, "bg": bg, "radius": radius, "dynamic": dynamic,
           "overflow": "ellipsis" if name in ELLIPSIS or wrap else "clip"}
    if wrap:
        # Word-wrapped store text, top aligned, ellipsis on the last line that fits.
        obj["wrap"] = True
    return obj


def button(x, y, w, h, text="", font="medium", size=17, color=TEXT, bg=RAISED, radius=None,
           border=None, bw=0, icon=None, action=None, name=None, icon_gap=10, icon_left=None):
    obj = {"type": "button", "x": x, "y": y, "w": w, "h": h, "text": text, "font": font,
           "size": size, "color": color, "bg": bg, "radius": h // 2 if radius is None else radius,
           "border": border, "border_width": bw, "action": action, "name": name, "icon": None}
    if icon:
        size_px = int(Path(icon).stem.split("-")[1])
        if icon_left is not None:
            # Fixed icon at the left; dynamic text centred in the remaining area.
            ix = x + icon_left
            obj["text_offset"] = (size_px + icon_gap) / 2
            obj["text_area"] = w - 2 * icon_left - size_px - icon_gap
        elif text:
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


def progress(x, y, w, h, value, name="progress"):
    return {"type": "progress", "x": x, "y": y, "w": w, "h": h, "value": value, "bg": TILE,
            "fg": ACCENT, "radius": h // 2, "name": name}


def keyboard(y=231, name="password_keyboard"):
    return {"type": "keyboard", "x": 0, "y": y, "w": W, "h": 233, "name": name, **TOKENS["keyboard"]}


# --------------------------------------------------------------------------
# Text measurement
# --------------------------------------------------------------------------
_FONT_CACHE: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def font_for(font: str, size: int) -> ImageFont.FreeTypeFont:
    key = (font, size)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ImageFont.truetype(str(DESIGN / FONTS[font]), size)
    return _FONT_CACHE[key]


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
def sort_key(app):
    # Official first, then numeric ID ascending (shorter IDs first).
    return (not app["official"], len(app["id"]), app["id"])


LIBRARY = sorted(PRESETS, key=sort_key)
BY_ID = {app["id"]: app for app in PRESETS + STORE_ONLY}
FAV = set(FAVORITES)
FILTER_TITLES = {"all": "MY APPS", "favorites": "FAVORITES",
                 **{key: text.upper() for key, text, _ in CATEGORIES}}
NETWORKS = [
    ("Studio-5G", "Secured · Strong signal"),
    ("Maker Lab", "Secured · Good signal"),
    ("Espressif-Guest", "Open · Good signal"),
    ("Home-2.4G", "Secured · Weak signal"),
]
TOKEN = "3f9a1c07e2b84d6a95c1f0e7d2a4b8c6" + "0d5e9f2a7c3b1e8d4f6a0c9b2e7d5a13"  # Wi-Fi link pairing
AI_TOKEN = "sk-demo-3b9f2c7e1a4d8f6b0c5e9a2d7f1b4c8e"  # shared LLM token (sample)
EMPTY_COPY = {
    "all": ["No apps yet", "Download an app by its ID, or develop\nyour own with your AI agent."],
    "favorites": ["No favorites yet", "Open an app and tap ☆ to add it here."],
    "category": ["Nothing here yet", "Find more apps on Mosaico Ideas."],
}


def filtered(apps, flt):
    if flt == "all":
        return list(apps)
    if flt == "favorites":
        return [a for a in apps if a["id"] in FAV]
    return [a for a in apps if a["category"] == flt]


def initial(app) -> str:
    return app["name"][0].upper()


# --------------------------------------------------------------------------
# Shared building blocks (sizes from the 2.1-inch rules in TOKENS["readability"])
# --------------------------------------------------------------------------
BTN = 72      # minimum touch target: 5.7 mm on this 323 ppi screen
ICON = 32     # icon size inside buttons


def circle_button(x, y, icon_name, action, name, size=BTN, icon_size=ICON, color="white"):
    return button(x, y, size, size, bg=BG, border=LINE, bw=2,
                  icon=f"assets/icons/{icon_name}-{icon_size}-{color}.png", action=action, name=name)


def header(title, back="back", help_topic="topics", page=None, extra=None):
    """72 px back button, dot-matrix title; ? and an optional extra button on the right."""
    objs = []
    if back:
        objs.append(circle_button(M, 14, "back", back, f"button_back_{page}"))
    right = W - M
    if help_topic:
        objs.append(circle_button(right - BTN, 14, "help", f"help:{help_topic}", f"button_help_{page}"))
        right -= BTN + 8
    if extra:
        objs.append(extra(right - BTN))
        right -= BTN + 8
    x0 = M + BTN + 12 if back else M
    objs.append(label(x0, 30, right - x0 - 8, title, "dot", 40, TEXT, name=f"{page}_title"))
    return objs


def primary(x, y, w, text, action, name, icon_name=None, h=80):
    return button(x, y, w, h, text, "medium", 28, PRIMARY_FG, PRIMARY_BG,
                  icon=f"assets/icons/{icon_name}-{ICON}-black.png" if icon_name else None,
                  action=action, name=name)


def secondary(x, y, w, text, action, name, icon_path=None, h=80, color=TEXT, border=LINE, bg=BG):
    return button(x, y, w, h, text, "medium", 28, color, bg, border=border, bw=2 if border else 0,
                  icon=icon_path, action=action, name=name)


def stack_button(x, y, w, h, icon_path, text, action, name, color=TEXT, bg=BG, border=LINE):
    """Icon above a short label: three of these fit one row at 2.1 inches."""
    obj = button(x, y, w, h, text, "medium", 22, color, bg, border=border, bw=2 if border else 0,
                 radius=20, action=action, name=name)
    obj["icon"] = {"image": icon_path, "x": x + (w - ICON) // 2, "y": y + 14, "w": ICON, "h": ICON}
    obj["text_dy"] = (y + 52 + line_h("medium", 22) / 2) - (y + h / 2)
    return obj


def tile(x, y, size, letter, radius, dot_size, name=None, color=TEXT, bg=TILE):
    th = line_h("dot", dot_size)
    return [container(x, y, size, size, bg, radius, name=f"{name}_tile" if name else None),
            label(x, y + (size - th) // 2 + round(dot_size * 0.05), size, letter, "dot", dot_size,
                  color, "center", name=f"{name}_initial" if name else None, dynamic=True)]


def qr_code(x, y, name, module, action, button_name):
    """QR image at an integer module size, with a transparent button to enlarge it."""
    size = QR_MODULES * module
    return [image(x, y, f"assets/qr/{name}.png", name=f"{button_name}_code", w=size, h=size, qr=True),
            button(x, y, size, size, bg=None, radius=0, action=action, name=button_name)]


def card_row(y, icon_name, title, value, action=None, name=None, value_name=None, icon_color="grey",
             h=80, value_color=TEXT2):
    """Two-line list row: 28 px label over a 22 px value, chevron when it opens something."""
    objs = []
    if action:
        objs.append(button(M, y, 448, h, bg=CARD, radius=20, action=action, name=name))
    else:
        objs.append(container(M, y, 448, h, CARD, 20, name=name))
    objs.append(icon(32, y + (h - ICON) // 2, icon_name, ICON, icon_color))
    objs.append(label(80, y + 8, 330, title, "medium", 28, TEXT))
    objs.append(label(80, y + 44, 330, value, "sans", 22, value_color, name=value_name, dynamic=True))
    if action:
        objs.append(icon(420, y + (h - 28) // 2, "chevron", 28, "dim"))
    return objs


def status_strip(agent=True, wifi_on=True, battery="mid", preset=None):
    """Home status strip: same icon order as the device's own status bar."""
    objs = [container(M + 4, 26, 10, 10, ACCENT, 5),
            label(36, 17, 130, "VIBE MODE", "medium", 22, TEXT2)]
    if preset:
        objs.append(label(170, 17, 120, f"↓ {preset[0]}/{preset[1]}", "medium", 22, ACCENT,
                          name="home_preset", dynamic=True))
    objs.append(icon(330, 17, "wifi" if wifi_on else "wifi_off", 28, "white" if wifi_on else "grey",
                     "status_wifi"))
    objs.append(icon(368, 17, "robot", 28, "orange" if agent else "grey", "status_agent"))
    objs.append(icon(406, 17, f"battery_{battery}", 28, "orange" if battery == "low" else "white",
                     "status_battery"))
    return objs


def ai_cue(active=False):
    """Light cue on the screen edge directly below the physical AI key (top right)."""
    return container(AI_KEY_CX - 18, 3, 36, 4, ACCENT if active else LINE, 2, name="ai_cue")


def ai_toast(text):
    """Transient banner (~1.5 s) over the top row: AI key hints, events and errors."""
    return [container(M, 10, 448, 76, RAISED, 38, border=LINE, bw=2, name="ai_toast"),
            label(M + 16, 10 + (76 - line_h("medium", 28)) // 2, 416, text, "medium", 28, TEXT,
                  "center", name="ai_toast_text", dynamic=True)]


# --------------------------------------------------------------------------
# Rows (list templates). Apps: 88 px card + 8 px gap; networks: 88 + 8.
# Row objects carry the list viewport as "clip", exactly like a GSP list.
# --------------------------------------------------------------------------
APP_ITEM_H = 96
NET_ITEM_H = 96


def clipped(objs, viewport, row_of=None):
    for obj in objs:
        if viewport:
            obj["clip"] = list(viewport)
        if row_of:
            obj["row_of"] = row_of
    return objs


def row_detail(app):
    if not app["official"]:
        return f"Community app · {app['id']}"
    return f"{CATEGORY_LABEL[app['category']]} · {app['id']}"


def app_row(x, y, app, viewport):
    current = app["id"] == CURRENT
    objs = [container(x, y, 448, 88, CARD, 20, role="row")]
    objs += tile(x + 12, y + 12, 64, initial(app), 16, 32, name="apps")
    # Favorite badge on the tile corner; a text glyph so the row setter can blank it.
    objs.append(label(x + 58, y + 1, 30, "★" if app["id"] in FAV else " ", "medium", 22, ACCENT,
                      "center", name="apps_star"))
    objs.append(label(x + 92, y + 10, 306, app["name"], "medium", 28, TEXT, name="apps_name"))
    # Static colours: the current app writes its line into the orange twin.
    objs.append(label(x + 92, y + 48, 306, " " if current else row_detail(app), "sans", 22, TEXT2,
                      name="apps_detail"))
    objs.append(label(x + 92, y + 48, 306, "● Current app" if current else " ", "sans", 22, ACCENT,
                      name="apps_detail_current"))
    objs.append(icon(x + 404, y + 30, "chevron", 28, "dim"))
    return clipped(objs, viewport, "apps")


def network_row(x, y, ssid, detail, viewport):
    return clipped([container(x, y, 448, 88, CARD, 20, role="row"),
                    label(x + 20, y + 10, 370, ssid, "medium", 28, TEXT, name="networks_title"),
                    label(x + 20, y + 48, 370, detail, "sans", 22, TEXT2, name="networks_detail"),
                    icon(x + 404, y + 30, "chevron", 28, "dim")], viewport, "networks")


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------
LIST_Y, LIST_H = 140, 240
FILTER_LABELS = {"all": "All apps", "favorites": "Favorites", **CATEGORY_LABEL}


def home(flt="all", agent=True, apps=None, preset=None, wifi_on=True, battery="mid"):
    apps = LIBRARY if apps is None else apps
    shown = filtered(apps, flt)
    objs = status_strip(agent, wifi_on, battery, preset)
    # One list picker instead of three small chips: tap to choose All, Favorites or a category.
    objs.append(button(M, 56, 288, BTN, bg=BG, border=LINE, bw=2, radius=36, action="go:categories",
                       name="button_filter"))
    objs.append(label(40, 56 + (BTN - 35) // 2, 218, FILTER_LABELS[flt], "medium", 28, TEXT,
                      name="home_title", dynamic=True))
    objs.append(icon(262, 56 + (BTN - 28) // 2, "chevron_down", 28, "white"))
    objs.append(circle_button(312, 56, "help", "help:topics", "button_help_home"))
    objs.append(circle_button(392, 56, "settings", "go:device", "button_device"))
    if shown:
        viewport = (M, LIST_Y, 448, LIST_H)
        objs.append({"type": "list_viewport", "x": M, "y": LIST_Y, "w": 448, "h": LIST_H, "name": "apps",
                     "item_height": APP_ITEM_H, "row_template": "apps_row", "count": len(shown)})
        for i, app in enumerate(shown[:3]):
            objs += app_row(M, LIST_Y + i * APP_ITEM_H, app, viewport)
    else:
        title, body = EMPTY_COPY[flt if flt in EMPTY_COPY else "category"]
        objs.append(image(212, 160, "assets/icons/empty-56-grey.png", name="home_empty_icon"))
        objs.append(label(M, 232, 448, title, "medium", 28, TEXT, "center", name="home_empty_title",
                          dynamic=True))
        objs.append(label(M, 276, 448, body, "sans", 22, TEXT2, "center", name="home_empty_body",
                          dynamic=True))
    objs.append(primary(M, 388, 216, "Download", "go:download", "button_download", "download"))
    objs.append(secondary(248, 388, 216, "Develop", "go:develop", "button_develop",
                          f"assets/icons/code-{ICON}-white.png"))
    objs.append(ai_cue())
    return objs


def quick_switch(index=1, flt="all"):
    objs = [o for o in home(flt) if o.get("name") != "ai_cue"]
    apps = filtered(LIBRARY, flt)
    app = apps[index]
    objs.append(container(0, 0, W, H, BG, 0, opacity=235, role="scrim"))
    objs.append(container(24, 40, 432, 400, CARD, 32, border=LINE, bw=2, name="switch_card"))
    objs.append(label(48, 60, 260, FILTER_LABELS[flt].upper(), "medium", 22, TEXT2,
                      name="switch_filter", dynamic=True))
    objs.append(label(312, 56, 120, f"{index + 1}/{len(apps)}", "dot", 32, TEXT2, "right",
                      name="switch_position", dynamic=True))
    objs += tile(180, 104, 120, initial(app), 34, 64, name="switch")
    objs.append(label(40, 238, 400, app["name"], "medium", 34, TEXT, "center", name="switch_name",
                      dynamic=True))
    objs.append(label(40, 286, 400, row_detail(app), "sans", 22, TEXT2, "center", name="switch_detail",
                      dynamic=True))
    objs.append(progress(48, 330, 384, 6, 35, name="switch_hold"))
    objs.append(container(48, 350, 384, 1, DIVIDER))
    for i, (key, text) in enumerate((("AI ×2", "Next"), ("Hold AI", "Open"), ("AI", "Close"))):
        x = 48 + i * 128
        objs.append(label(x, 362, 128, key, "medium", 22, TEXT, "center"))
        objs.append(label(x, 392, 128, text, "sans", 22, TEXT2, "center"))
    objs.append(ai_cue(True))
    return objs


def category_tiles():
    tiles = [("all", "All apps", "grid", len(LIBRARY)),
             ("favorites", "Favorites", "star", len(filtered(LIBRARY, "favorites")))]
    tiles += [(key, text, ic, len(filtered(LIBRARY, key))) for key, text, ic in CATEGORIES]
    return tiles


def categories(selected="all"):
    objs = header("SHOW", page="categories", help_topic="start")
    for i, (key, text, ic, n) in enumerate(category_tiles()):
        x, y = M + (i % 2) * 232, 96 + (i // 2) * 92
        objs.append(button(x, y, 216, 84, bg=CARD, radius=20, action=f"filter:{key}", name=f"category_{key}"))
        objs.append(icon(x + 16, y + 12, ic, ICON, "white"))
        objs.append(label(x + 120, y + 12, 80, f"{n:02d}", "dot", 32, TEXT2, "right",
                          name=f"category_{key}_count", dynamic=True))
        objs.append(label(x + 12, y + 47, 198, text, "sans", 26, TEXT))
        if key == selected:
            # One ring; the controller moves it onto the selected tile.
            objs.append(container(x, y, 216, 84, None, 20, border=ACCENT, bw=3, name="category_selected"))
    return objs


def download(digits="", looking=False):
    scan = lambda x: circle_button(x, 14, "qr", "qr:ideas", "button_browse")  # noqa: E731
    objs = header("DOWNLOAD", page="download", help_topic=None, extra=scan)
    objs.append(container(M, 96, 448, 64, CARD, 20))
    # Digits (large or compact) and the status line share the card; the
    # unused labels hold a blank glyph. Errors appear as the banner.
    status = "Looking up…" if looking else ("Type the app ID" if not digits else " ")
    big = digits if digits and len(digits) <= 8 and not looking else " "
    objs.append(label(24, 106, 432, big, "dot", 44, TEXT, "center", name="id_digits", dynamic=True))
    objs.append(label(24, 112, 432, digits if len(digits) > 8 and not looking else " ", "dot", 32, TEXT,
                      "center", name="id_digits_compact", dynamic=True))
    objs.append(label(24, 112, 432, status, "sans", 26, TEXT2, "center", name="id_status", dynamic=True))
    keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "del", "0", "go"]
    for i, key in enumerate(keys):
        x, y = M + (i % 3) * 152, 168 + (i // 3) * 76
        if key == "del":
            objs.append(button(x, y, 144, 72, bg=BG, border=LINE, bw=2, radius=20,
                               icon=f"assets/icons/backspace-{ICON}-white.png", action="key:del", name="key_del"))
        elif key == "go":
            objs.append(button(x, y, 144, 72, bg=ACCENT, radius=20, icon=f"assets/icons/arrow-{ICON}-white.png",
                               action="key:go", name="key_go"))
        else:
            objs.append(button(x, y, 144, 72, key, "dot", 40, TEXT, RAISED, radius=20,
                               action=f"key:{key}", name=f"key_{key}"))
    return objs


DEVELOP_STEPS = [
    ("code", "Vibe-code it", "Scan for the guide", "qr:develop"),
    ("usb", "Install over USB", "From your agent or the website", None),
    ("share", "Share on Mosaico Ideas", "Get an ID anyone can use", "qr:ideas"),
]


def develop(usb=True, agent=True):
    objs = header("DEVELOP", page="develop", help_topic="develop")
    text = ("USB connected · AI agent ready" if agent else "USB connected · waiting for agent") if usb \
        else "Plug in a USB data cable"
    on = usb and agent
    objs.append(label(M, 96, 448, f"● {text}", "sans", 22, ACCENT if on else TEXT2,
                      name="develop_status_on" if on else "develop_status_off", dynamic=True))
    for i, (ic, title, sub, action) in enumerate(DEVELOP_STEPS):
        y = 132 + i * 96
        if action:
            objs.append(button(M, y, 448, 88, bg=CARD, radius=20, action=action, name=f"button_step_{i + 1}"))
        else:
            objs.append(container(M, y, 448, 88, CARD, 20))
        objs.append(icon(32, y + 28, ic, ICON, "white"))
        objs.append(label(80, y + 10, 330, title, "medium", 28, TEXT))
        objs.append(label(80, y + 48, 330, sub, "sans", 22, TEXT2))
        if action:
            objs.append(icon(420, y + 30, "chevron", 28, "dim"))
    return objs


def wifi_link():
    objs = header("WI-FI LINK", page="wifilink", help_topic="develop")
    objs.append(container(M, 96, 448, 264, CARD, 20))
    objs.append(label(32, 108, 300, "ADDRESS", "medium", 22, TEXT2))
    objs.append(label(32, 140, 416, "192.168.1.20:7777", "medium", 28, TEXT, name="wifilink_endpoint",
                      dynamic=True))
    objs.append(container(32, 188, 416, 1, DIVIDER))
    objs.append(label(32, 200, 300, "TOKEN", "medium", 22, TEXT2))
    token_lines = "\n".join(TOKEN[i:i + 16] for i in range(0, 64, 16))
    objs.append(label(32, 230, 416, token_lines, "sans", 22, TEXT, name="wifilink_token", dynamic=True))
    objs.append(label(M, 372, 448, "Your AI agent uses these to\ninstall over Wi-Fi.", "sans", 22, TEXT2))
    objs.append(label(M, 432, 448, "Keep the token private.", "sans", 22, ACCENT))
    return objs


def detail_app(mode):
    return {"current": BY_ID[CURRENT], "local": BY_ID["100012"], "remote_new": BY_ID["238114"],
            "remote_update": dict(BY_ID["100006"], version=STORE_UPDATES["100006"])}[mode]


def facts(app):
    source = "Official" if app["official"] else "Community"
    return f"{CATEGORY_LABEL[app['category']]} · {source} · v{app['version']} · {app['size']}"


def detail(mode="current", confirm=False, app=None):
    remote = mode in ("remote_new", "remote_update")
    app = app or detail_app(mode)
    extra = None
    if not remote:
        def extra(x):
            if app["id"] in FAV:
                return circle_button(x, 14, "star_fill", "app:favorite", "button_favorite_on", color="orange")
            return circle_button(x, 14, "star", "app:favorite", "button_favorite_off")
    objs = header("APP", page="detail", help_topic=None, extra=extra)
    objs += tile(M, 96, 96, initial(app), 24, 64, name="detail")
    objs.append(label(128, 100, 336, app["name"], "medium", 34, TEXT, name="detail_name", dynamic=True))
    objs.append(label(128, 148, 220, app["id"], "dot", 32, ACCENT, name="detail_id", dynamic=True))
    local = BY_ID.get(app["id"])
    status = {"current": "● Current app", "local": "Saved · not running", "remote_new": "Not on this device",
              "remote_update": f"Update v{local['version'] if local else '?'} → v{app['version']}"}[mode]
    accent = mode in ("current", "remote_update")
    objs.append(label(M, 204, 448, status, "medium", 28, ACCENT if accent else TEXT,
                      name="detail_status_accent" if accent else "detail_status", dynamic=True))
    objs.append(label(M, 244, 448, facts(app), "sans", 22, TEXT2, name="detail_facts", dynamic=True))
    info = f"assets/icons/info-{ICON}-white.png"
    if remote:
        objs.append(primary(M, 288, 448, "Download & run", "store:run", "button_primary", "download"))
        objs.append(stack_button(M, 376, 144, 88, f"assets/icons/download-{ICON}-white.png", "Save only",
                                 "store:keep", "button_secondary"))
        objs.append(stack_button(168, 376, 144, 88, info, "About", "go:about", "button_about"))
        objs.append(stack_button(320, 376, 144, 88, f"assets/icons/close-{ICON}-white.png", "Cancel",
                                 "back", "button_tertiary"))
    else:
        objs.append(primary(M, 288, 448, "Open" if mode == "current" else "Run this app", "app:run",
                            "button_primary", "play"))
        objs.append(stack_button(M, 376, 144, 88, f"assets/icons/refresh-{ICON}-white.png", "Update",
                                 "app:update", "button_secondary"))
        if confirm:
            objs.append(stack_button(168, 376, 144, 88, f"assets/icons/trash-{ICON}-white.png", "Tap again",
                                     "app:delete", "button_delete_confirm", color=WHITE, bg=ACCENT, border=None))
        else:
            objs.append(stack_button(168, 376, 144, 88, f"assets/icons/trash-{ICON}-orange.png", "Delete",
                                     "app:delete_ask", "button_tertiary", color=ACCENT))
        objs.append(stack_button(320, 376, 144, 88, info, "About", "go:about", "button_about"))
    return objs


SUMMARY_W, SUMMARY_LINES = 238, 7


def about(app=None):
    """Second detail screen: store summary and the app's Mosaico Ideas QR code."""
    app = app or BY_ID[CURRENT]
    objs = header("ABOUT", page="about", help_topic=None)
    objs.append(label(M, 96, 448, app["name"], "medium", 28, TEXT, name="about_name", dynamic=True))
    objs += qr_code(M, 140, f"app-{app['id']}", 6, "qr:app", "button_qr_app")
    objs.append(label(226, 140, SUMMARY_W, app["summary"], "sans", 26, TEXT2,
                      h=line_h("sans", 26, SUMMARY_LINES), name="about_summary", dynamic=True, wrap=True))
    objs.append(icon(M, 350, "expand", 28, "grey"))
    objs.append(label(52, 350, 170, "Tap to enlarge", "sans", 22, TEXT2))
    objs.append(label(M, 404, 448, facts(app), "sans", 22, TEXT2, name="about_facts", dynamic=True))
    return objs


def qr_full(name="app-100001", title="Pixel Pet on Mosaico Ideas", url="mosaico-ideas.espressif.com/app/100001"):
    """Any QR code, enlarged to 11 px modules. Tap anywhere or press AI to close."""
    size = QR_MODULES * 11
    return [image((W - size) // 2, 10, f"assets/qr/{name}.png", name="qr_full_code", w=size, h=size, qr=True),
            label(M, 382, 448, title, "medium", 28, TEXT, "center", name="qr_full_title", dynamic=True),
            label(M, 422, 448, url, "sans", 22, TEXT2, "center", name="qr_full_url", dynamic=True),
            button(0, 0, W, H, bg=None, radius=0, action="back", name="button_qr_close")]


def progress_page(kind="agent"):
    spec = {
        "agent": ("FROM YOUR AI AGENT · USB", "Installing your app", "hello_world · v0.2.1",
                  42, "1.20 of 2.85 MB · 236 KB/s", "Step 1 of 2 · Receiving", False),
        "download": ("FROM MOSAICO IDEAS", "Downloading", "Retro Snake · v1.0.3",
                     67, "0.61 of 0.92 MB · 512 KB/s", "File 2 of 3", True),
        "install": ("FROM YOUR LIBRARY", "Switching apps", "Weather Station · v2.0.1",
                    88, "2.11 of 2.40 MB · 1.6 MB/s", "Step 2 of 2 · Writing", False),
    }[kind]
    caption, title, detail_text, pct, size_text, step, cancel = spec
    objs = [label(M, 22, 448, caption, "medium", 22, ACCENT, name="progress_caption", dynamic=True),
            label(M, 56, 448, title, "medium", 34, TEXT, name="progress_title", dynamic=True),
            label(M, 104, 448, detail_text, "sans", 26, TEXT2, name="progress_detail", dynamic=True),
            label(M, 148, 448, f"{pct}%", "dot", 120, TEXT, "center", name="progress_percent", dynamic=True),
            progress(M, 282, 448, 10, pct),
            label(M, 304, 448, size_text, "sans", 22, TEXT2, name="progress_bytes", dynamic=True),
            label(M, 336, 448, step, "sans", 22, TEXT3, name="progress_step", dynamic=True)]
    if cancel:
        objs.append(secondary(M, 388, 448, "Cancel download", "store:cancel", "button_cancel"))
    else:
        objs.append(icon(M, 396, "power", 28, "orange"))
        objs.append(label(54, 393, 410, "Keep the device powered", "sans", 26, TEXT2))
    return objs


def result(kind="installed"):
    spec = {
        "installed": (True, "App installed", "Pixel Pet · v1.2.0", "Restarting into your app…", None),
        "saved": (True, "Saved to My Apps", "Retro Snake · v1.0.3", "Open it any time\nfrom the list.",
                  "Open now"),
        "failed": (False, "Couldn't download", "Retro Snake · v1.0.3",
                   "The connection dropped.\nCheck Wi-Fi and try again.", "Try again"),
    }[kind]
    ok, title, caption, body, second = spec
    objs = [container(180, 40, 120, 120, BG, 60, border=ACCENT if ok else TEXT3, bw=4, name="result_ring"),
            icon(216, 76, "check" if ok else "close", 48, "orange" if ok else "grey", "result_icon"),
            label(M, 180, 448, title, "medium", 34, TEXT, "center", name="result_title", dynamic=True),
            label(M, 228, 448, caption, "sans", 26, TEXT2, "center", name="result_caption", dynamic=True),
            label(40, 270, 400, body, "sans", 22, TEXT2, "center", name="result_detail", dynamic=True)]
    if second:
        objs.append(secondary(M, 388, 216, second, "result:second", "button_result_second"))
        objs.append(primary(248, 388, 216, "Done", "go:home", "button_done"))
    else:
        objs.append(primary(M, 388, 448, "Done", "go:home", "button_done"))
    if not ok:
        objs.append(circle_button(W - M - BTN, 14, "help", "help:fix", "button_help_result"))
    return objs


HELP_TOPICS = [
    ("start", "flag", "Getting started"),
    ("develop", "code", "Develop apps"),
    ("ids", "hash", "App IDs & sharing"),
    ("fix", "support", "Troubleshooting"),
]
HELP_TEXT = {key: (title, ic, {"develop": "develop"}.get(key, f"help-{key}")) for key, ic, title in HELP_TOPICS}
# Short form of each QR payload, shown under the code.
QR_URLS = {
    "ideas": "mosaico-ideas.espressif.com",
    "develop": "mosaico.espressif.com/guide/vibe-coding",
    "help-start": "mosaico.espressif.com/vibe/start",
    "help-ids": "mosaico.espressif.com/vibe/ids",
    "help-fix": "mosaico.espressif.com/vibe/fix",
}


def help_topics():
    replay = lambda x: circle_button(x, 14, "replay", "guide:1", "button_replay")  # noqa: E731
    objs = header("HELP", page="help", help_topic=None, extra=replay)
    for i, (key, icon_name, title) in enumerate(HELP_TOPICS):
        y = 96 + i * 92
        objs.append(button(M, y, 448, 84, bg=CARD, radius=20, action=f"help:{key}", name=f"topic_{key}"))
        objs.append(icon(32, y + 26, icon_name, ICON, "white"))
        objs.append(label(80, y + 24, 330, title, "medium", 28, TEXT))
        objs.append(icon(420, y + 28, "chevron", 28, "dim"))
    return objs


def help_topic(key="start"):
    title, icon_name, qr_name = HELP_TEXT[key]
    objs = header("HELP", back="back", page="topic", help_topic=None)
    objs.append(icon(M, 99, icon_name, ICON, "white", "topic_icon"))
    objs.append(label(60, 96, 404, title, "medium", 28, TEXT, name="topic_title", dynamic=True))
    objs += qr_code(108, 140, qr_name, 8, f"qr:{qr_name}", "button_qr_topic")
    objs.append(label(M, 414, 448, QR_URLS[qr_name], "sans", 22, TEXT2, "center", name="topic_url",
                      dynamic=True))
    return objs


def wifi(pending=False):
    objs = header("WI-FI", page="wifi", help_topic="fix")
    objs.append(container(M, 96, 448, 88, CARD, 20))
    objs.append(icon(32, 124, "wifi", ICON, "grey"))
    objs.append(label(76, 104, 252, "Studio-5G", "medium", 28, TEXT, name="wifi_connection", dynamic=True))
    objs.append(label(76, 142, 252, "Connected", "sans", 22, TEXT2, name="wifi_detail", dynamic=True))
    objs.append(secondary(336, 104, 116, "Forget", "wifi:forget", "button_forget", h=72))
    objs[-1]["size"] = 22
    if pending:
        objs.append(label(M, 210, 360, "PICK ONE TO CONTINUE", "medium", 22, ACCENT, name="wifi_scan_accent",
                          dynamic=True))
    else:
        objs.append(label(M, 210, 360, "NETWORKS · 4", "medium", 22, TEXT2, name="wifi_scan", dynamic=True))
    objs.append(circle_button(392, 192, "refresh", "wifi:scan", "button_scan"))
    viewport = (M, 272, 448, 192)
    objs.append({"type": "list_viewport", "x": M, "y": 272, "w": 448, "h": 192, "name": "networks",
                 "item_height": NET_ITEM_H, "row_template": "networks_row", "count": len(NETWORKS)})
    for i, (ssid, info) in enumerate(NETWORKS[:2]):
        objs += network_row(M, 272 + i * NET_ITEM_H, ssid, info, viewport)
    return objs


def text_entry(page, title, display, placeholder, note, toggle=None, note_color=TEXT2):
    """Fallback keyboard page shared by the Wi-Fi password, the city and the AI token."""
    objs = header(title, page=page, help_topic=None)
    objs.append(container(M, 96, 448, 72, CARD, 20))
    objs.append(label(32, 114, 336 if toggle is not None else 416, display or placeholder, "medium", 28,
                      TEXT if display else TEXT3, name=f"{page}_display", dynamic=True))
    if toggle is not None:
        objs.append(button(376, 96, 88, 72, bg=RAISED, radius=20,
                           icon=f"assets/icons/{'eye' if toggle else 'eye_off'}-{ICON}-white.png",
                           action=f"{page}:toggle", name=f"button_toggle_{page}"))
    objs.append(label(M, 182, 448, note, "sans", 22, note_color, name=f"{page}_note", dynamic=True))
    objs.append(keyboard(name=f"{page}_keyboard"))
    return objs


def password(masked=True, error=""):
    return text_entry("password", "PASSWORD", "••••••••••" if masked else "makers2026", "Type the password",
                      error or "Or set it from your computer.", toggle=masked,
                      note_color=ACCENT if error else TEXT2)


def city_input():
    return text_entry("city_input", "CITY", "Shanghai", "Type your city", "Letters and spaces, up to 40.")


def token_input():
    return text_entry("token_input", "AI TOKEN", "•" * 8 + AI_TOKEN[-4:], "Type your token",
                      "Every app can read it.", toggle=True, note_color=ACCENT)


def from_computer(y, h, lines):
    """Card that points to the main way of setting shared values: the computer over USB."""
    return [container(M, y, 448, h, CARD, 20),
            icon(32, y + 20, "usb", ICON, "white"),
            label(76, y + 16, 372, lines, "sans", 26, TEXT)]


def city():
    objs = header("CITY", page="city", help_topic=None)
    objs.append(container(M, 96, 448, 96, CARD, 20))
    objs.append(label(32, 106, 416, "Shared with all apps", "sans", 22, TEXT2))
    objs.append(label(32, 138, 416, "Shanghai", "medium", 34, TEXT, name="city_value", dynamic=True))
    objs += from_computer(208, 164, "Set it from your computer:\nask your AI agent while\nthe USB cable is in.")
    objs.append(secondary(M, 388, 448, "Type on device", "go:city_input", "button_type_city"))
    return objs


def token():
    objs = header("AI TOKEN", page="token", help_topic=None)
    objs.append(container(M, 96, 448, 124, CARD, 20))
    objs.append(label(32, 106, 416, "Shared with all apps", "sans", 22, TEXT2))
    objs.append(label(32, 138, 416, f"Set · ends in {AI_TOKEN[-4:]}", "medium", 28, TEXT, name="token_value",
                      dynamic=True))
    objs.append(label(32, 180, 416, "Every app can read it.", "sans", 22, ACCENT))
    objs += from_computer(232, 140, "Paste it on your computer:\nask your AI agent over USB.")
    objs.append(secondary(M, 388, 216, "Type it", "go:token_input", "button_type_token"))
    objs.append(secondary(248, 388, 216, "Clear", "token:clear", "button_clear_token", color=ACCENT))
    return objs


def device():
    objs = header("DEVICE", page="device", help_topic="fix")
    objs.append(label(M, 94, 448, "Shared with every app", "sans", 22, TEXT2))
    used = sum(float(a["size"].split()[0]) for a in LIBRARY)
    rows = [(128, "wifi", "Wi-Fi", "Studio-5G", "go:wifi", "button_device_wifi", "device_wifi"),
            (216, "pin", "City", "Shanghai", "go:city", "button_device_city", "device_city"),
            (304, "key", "AI token", f"Set · ends in {AI_TOKEN[-4:]}", "go:token", "button_device_token",
             "device_token"),
            (392, "chip", "This device", f"Vibe Mode 0.3.0 · {len(LIBRARY)} apps", "go:device_info",
             "button_device_info", "device_summary")]
    for y, ic, title, value, action, name, value_name in rows:
        objs += card_row(y, ic, title, value, action, name, value_name)
    objs[-1]["name"] = None
    assert used > 0
    return objs


def device_info():
    objs = header("THIS DEVICE", page="info", help_topic=None)
    used = sum(float(a["size"].split()[0]) for a in LIBRARY)
    objs += card_row(96, "chip", "Vibe Mode", "0.3.0 · ESP32-S31", value_name="device_version")
    objs += card_row(184, "id", "MAC address", "30:ED:A0:F4:60:56", value_name="device_mac")
    objs += card_row(272, "storage", "App storage", f"{len(LIBRARY)} apps · {used:.1f} MB used",
                     value_name="device_storage")
    objs += card_row(360, "wifi", "Wi-Fi link", "192.168.1.20:7777", "go:wifi_link", "button_wifi_link",
                     "device_endpoint")
    objs.append(label(M, 446, 448, "Downloads send MAC and version.", "sans", 22, TEXT3, "center"))
    return objs


def guide(step=1):
    objs = [label(20, 26, 140, f"0{step}/04", "dot", 32, TEXT2, name="guide_step", dynamic=True),
            button(344, 12, 120, BTN, "Skip", "medium", 28, TEXT2, BG, action="guide:done", name="button_skip")]
    if step == 1:
        title_w = int(text_width("VIBE MODE", "dot", 64))
        objs.append(label(M, 104, 448, "VIBE MODE", "dot", 64, TEXT))
        objs.append(container(M + title_w + 6, 150, 14, 14, ACCENT, 7))
        objs.append(label(M, 190, 448, "A safe home for\nyour apps", "medium", 34, TEXT))
        objs.append(label(M, 292, 448, "Your AI agent installs apps here.\nSwitch or download apps any time.",
                          "sans", 26, TEXT2))
    elif step == 2:
        objs.append(label(M, 88, 448, "Coming back here", "medium", 34, TEXT))
        objs += guide_device(M, 140)
        # Step numbers sit next to the ringed keys in the drawing.
        objs.append(label(M + 166, 143, 28, "1", "dot", 32, ACCENT))
        objs.append(label(M + 166, 300, 28, "2", "dot", 32, ACCENT))
        steps = (("1", "Hold AI", "Top edge, right"), ("2", "Press power", "Bottom right ×2"),
                 ("3", "Release AI", "On this screen"))
        for i, (num, head, sub) in enumerate(steps):
            y = 148 + i * 80
            objs.append(label(236, y, 32, num, "dot", 32, ACCENT))
            objs.append(label(276, y - 2, 188, head, "medium", 28, TEXT))
            objs.append(label(276, y + 34, 188, sub, "sans", 22, TEXT2))
    elif step == 3:
        objs.append(label(M, 88, 448, "Two ways to get apps", "medium", 34, TEXT))
        cards = (("download", "Download", "Type an app ID\nfrom Mosaico\nIdeas."),
                 ("code", "Develop", "Vibe-code it,\ninstall over USB,\nshare it."))
        for i, (ic, head, body) in enumerate(cards):
            x = M + i * 232
            objs.append(container(x, 148, 216, 224, CARD, 20))
            objs.append(icon(x + 18, 166, ic, ICON, "white"))
            objs.append(label(x + 18, 210, 184, head, "medium", 28, TEXT))
            objs.append(label(x + 18, 254, 184, body, "sans", 22, TEXT2))
    else:
        objs.append(label(M, 88, 448, "Your AI key", "medium", 34, TEXT))
        rows = [("AI", "Go back"), ("AI ×2", "Switch apps"), ("Hold AI", "Open the app")]
        for i, (key, text) in enumerate(rows):
            y = 148 + i * 80
            objs.append(container(M, y, 128, 64, RAISED, 32, name=f"guide_key_{i}"))
            objs.append(label(M, y + (64 - 35) // 2, 128, key, "medium", 28, TEXT, "center"))
            objs.append(label(160, y + (64 - 33) // 2, 304, text, "sans", 26, TEXT))
    if step > 1:
        objs.append(secondary(M, 388, 140, "Back", f"guide:{step - 1}", "button_guide_back"))
        objs.append(primary(164, 388, 300, "Start" if step == 4 else "Next",
                            "guide:done" if step == 4 else f"guide:{step + 1}", "button_guide_next"))
    else:
        objs.append(primary(M, 388, 448, "Next", "guide:2", "button_guide_next"))
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
    # A dot-matrix "V" with the orange accent dot: the Vibe Mode screen.
    for i, (cx, cy) in enumerate([(84, 82), (90, 94), (96, 106), (102, 118), (108, 106), (114, 94), (120, 82)]):
        objs.append(container(x + cx - 3, y + cy - 3, 6, 6, ACCENT if i == 3 else TEXT, 3))
    return objs


def launching(app=None):
    """Restart into an app that is already installed: no Flash write."""
    app = app or BY_ID[CURRENT]
    objs = tile(180, 110, 120, initial(app), 34, 64, name="launch")
    objs.append(label(M, 254, 448, f"Opening {app['name']}", "medium", 34, TEXT, "center",
                      name="launch_title", dynamic=True))
    objs.append(label(M, 306, 448, "Restarting into your app…", "sans", 26, TEXT2, "center"))
    return objs


def app_running(app=None):
    """Prototype only: stands in for the user's app after Vibe Mode hands over."""
    app = app or BY_ID[CURRENT]
    objs = [container(0, 0, W, H, "#0A0A0A", 0, role="background")]
    objs += tile(180, 70, 120, initial(app), 34, 64, name="running", bg=RAISED)
    objs.append(label(M, 210, 448, app["name"], "medium", 34, TEXT, "center", name="running_title",
                      dynamic=True))
    objs.append(label(M, 260, 448, "Your app is running", "sans", 26, TEXT2, "center"))
    objs.append(label(40, 310, 400, "To come back: hold AI,\nthen double-press power.", "sans", 22,
                      TEXT3, "center"))
    objs.append(secondary(96, 388, 288, "Back to Vibe Mode", "proto:return", "button_return"))
    return objs


def prototype_extras():
    extras = [{"id": f"help-topic-{key}", "page": "help_topic", "objects": help_topic(key)}
              for key in HELP_TEXT]
    extras.append({"id": "home-category-empty", "page": "home",
                   "objects": home("motor", apps=[a for a in LIBRARY if a["category"] != "motor"])})
    extras.append({"id": "city-input", "page": "city_input", "objects": city_input()})
    extras.append({"id": "token-input", "page": "token_input", "objects": token_input()})
    extras.append({"id": "launching", "page": "launching", "objects": launching()})
    extras.append({"id": "app-running", "page": "app_running", "objects": app_running()})
    for extra in extras:
        if extra["page"] != "app_running" and not any(o.get("name") == "ai_cue" for o in extra["objects"]):
            extra["objects"].append(ai_cue())
    templates = {"apps_row": app_row(0, 0, LIBRARY[1], None),
                 "networks_row": network_row(0, 0, *NETWORKS[0], None)}
    return extras, templates


# --------------------------------------------------------------------------
# States (one mockup each)
# --------------------------------------------------------------------------
def build_states():
    s = []

    def add_state(sid, page, title, objs):
        if not any(o.get("name") == "ai_cue" for o in objs):
            objs.append(ai_cue())
        s.append({"id": sid, "page": page, "title": title, "objects": objs})

    for i in range(1, 5):
        add_state(f"guide-{i}", "guide", f"Guide {i}/4", guide(i))
    add_state("home", "home", "Home · all apps, agent connected", home())
    add_state("home-favorites", "home", "Home · Favorites", home("favorites", agent=False))
    add_state("home-category", "home", "Home · one category", home("smart-home", agent=False))
    add_state("home-preset", "home", "Home · getting preset apps",
              home(agent=False, preset=(3, 20), apps=LIBRARY[:3]))
    add_state("home-favorites-empty", "home", "Home · no favorites yet",
              home("favorites", agent=False, apps=[a for a in LIBRARY if a["id"] not in FAV]))
    add_state("home-empty", "home", "Home · empty library",
              home(agent=False, apps=[], wifi_on=False, battery="low"))
    hint = [o for o in home(agent=False) if o.get("name") != "ai_cue"]
    add_state("home-ai-hint", "home", "Home · AI pressed (hint banner)",
              hint + [ai_cue(True)] + ai_toast("Press AI twice to switch"))
    add_state("quick-switch", "home", "Quick switch (AI ×2)", quick_switch())
    add_state("categories", "categories", "Show: all, favorites, categories", categories("smart-home"))
    add_state("download", "download", "Download · empty", download())
    add_state("download-typing", "download", "Download · typing", download("2381"))
    add_state("download-lookup", "download", "Download · looking up", download("238114", looking=True))
    add_state("download-error", "download", "Download · not found (banner)",
              download("404040") + ai_toast("No app with this ID"))
    add_state("develop", "develop", "Develop", develop())
    add_state("detail-current", "detail", "Detail · current app (favorite)", detail("current"))
    add_state("detail-local", "detail", "Detail · saved app", detail("local"))
    add_state("detail-delete", "detail", "Detail · delete confirmation", detail("local", True))
    add_state("detail-remote", "detail", "Detail · found on Mosaico Ideas", detail("remote_new"))
    add_state("detail-update", "detail", "Detail · update available", detail("remote_update"))
    add_state("about", "about", "About · summary and app QR", about())
    add_state("qr-full", "qr", "Any QR code, enlarged", qr_full())
    add_state("progress-agent", "progress", "Progress · from the AI agent", progress_page("agent"))
    add_state("progress-download", "progress", "Progress · download", progress_page("download"))
    add_state("progress-install", "progress", "Progress · switching apps", progress_page("install"))
    add_state("result-installed", "result", "Result · installed", result("installed"))
    add_state("result-saved", "result", "Result · saved", result("saved"))
    add_state("result-failed", "result", "Result · failed", result("failed"))
    add_state("help", "help", "Help topics", help_topics())
    add_state("help-topic", "help_topic", "Help topic with QR", help_topic("develop"))
    add_state("wifi", "wifi", "Wi-Fi", wifi())
    add_state("wifi-pending", "wifi", "Wi-Fi · to continue a download", wifi(True))
    add_state("password", "password", "Wi-Fi password", password())
    add_state("device", "device", "Device · shared settings", device())
    add_state("device-info", "device_info", "This device", device_info())
    add_state("wifi-link", "wifi_link", "Wi-Fi link", wifi_link())
    add_state("city", "city", "City (set from the computer)", city())
    add_state("token", "token", "AI token (set from the computer)", token())
    return s


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
    keys.append((8, ky, 88, key_h, "123", kb["function_color"], kb["fg_color"]))
    keys.append((104, ky, 272, key_h, "space", kb["key_color"], kb["fg_color"]))
    keys.append((384, ky, 88, key_h, "GO", kb["ok_color"], kb["ok_text_color"]))
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
        if obj.get("role") in ("scrim", "background", "row") or not (obj.get("bg") or obj.get("border")):
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
                    problems.append(f"{where} outside the screen ({x},{y},{w},{h})")
                for shape in visible_shapes(obj):
                    if not all(inside_screen(px, py) for px, py in outline(*shape)):
                        problems.append(f"{where} crosses the rounded screen corner {shape[:4]}")
                        break
            if t == "button" and (w < MIN_TOUCH or h < MIN_TOUCH):
                problems.append(f"{where} touch target {w}x{h} is below {MIN_TOUCH}x{MIN_TOUCH}")
            icon_path = obj.get("image") if t == "image" else (obj.get("icon") or {}).get("image")
            if icon_path and "/icons/" in icon_path and int(Path(icon_path).stem.split("-")[1]) < MIN_ICON:
                problems.append(f"{where} icon is below {MIN_ICON} px")
            if t == "image" and obj.get("qr") and (w != h or w % QR_MODULES or w // QR_MODULES < 5):
                problems.append(f"{where} QR size {w}x{h} is not a whole module size >= 5 px")
            if t in ("label", "button") and obj.get("text") and obj["size"] not in TYPE_SCALE[obj["font"]]:
                problems.append(f"{where} uses {obj['font']} {obj['size']} px, outside the type scale")
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
                    avail = obj.get("text_area") or (w - 2 * obj.get("text_offset", 0)
                                                     - (obj["icon"]["w"] if obj.get("icon") else 0))
                else:
                    avail = w
                width = text_width(obj["text"], obj["font"], obj["size"])
                if width > avail and obj.get("overflow") != "ellipsis":
                    problems.append(f"{where} text width {width:.0f} > {avail:.0f}")
    return problems + check_copy() + check_store_text()


# Every dynamic string variant from the copy table (README section 8), measured
# against its label. Names and SSIDs ellipsize, so only fixed copy is listed.
TOASTS = ["Press AI twice to switch", "Press twice, then hold", "No apps in this list", "AI agent connected",
          "Added to Favorites", "Removed from Favorites", "Download cancelled", "Connect Wi-Fi first",
          "Getting preset apps", "City saved", "AI token saved", "AI token cleared", "Type an app ID first",
          "No app with this ID", "This app was removed", "Not for this device", "Download not allowed",
          "Store is busy. Try later.", "Can't reach the store", "Storage unavailable", "Not enough storage"]
COPY = [
    (416, "medium", 28, TOASTS),
    (432, "sans", 26, ["Type the app ID", "Looking up…"]),
    (218, "medium", 28, list(FILTER_LABELS.values()) + ["Other"]),
    (198, "sans", 26, ["All apps", "Favorites", "Other"] + [text for _, text, _ in CATEGORIES]),
    (120, "medium", 22, ["↓ 20/20"]),
    (260, "medium", 22, [t.upper() for t in FILTER_LABELS.values()]),
    (448, "medium", 28, ["Update v10.12.3 → v10.13.0", "Update available", "Saved · not running",
                         "Not on this device", "● Current app"]),
    (306, "sans", 22, ["Communication · 123456", "Community app · 123456", "● Current app"]),
    (448, "medium", 22, ["FROM YOUR AI AGENT · WI-FI", "FROM YOUR AI AGENT · USB", "FROM THE WEBSITE · USB",
                         "FROM YOUR COMPUTER · USB", "FROM MOSAICO IDEAS", "FROM YOUR LIBRARY"]),
    (448, "medium", 34, ["Installing your app", "Downloading", "Switching apps", "Couldn't install the app",
                         "Couldn't download", "Saved to My Apps", "App installed"]),
    (448, "sans", 22, ["312.40 of 312.40 MB · 1.6 MB/s", "Step 2 of 2 · Verifying", "File 3 of 3 · Checking",
                       "Use at least 8 characters", "Wrong password. Try again.", "Or set it from your computer.",
                       "Type a city name first", "● USB connected · AI agent ready",
                       "● USB connected · waiting for agent", "● Plug in a USB data cable"]),
    (400, "sans", 22, ["The connection dropped.", "Check Wi-Fi and try again.", "Restarting into your app…"]),
    (330, "sans", 22, ["Set · ends in 4c8e", "Not set", "Not connected", "Vibe Mode 0.3.0 · 24 apps",
                       "24 apps · 312.4 MB used", "Connect Wi-Fi first", "192.168.100.200:7777"]),
    (360, "medium", 22, ["NETWORKS · 16", "SCANNING…", "PICK ONE TO CONTINUE"]),
    (252, "sans", 22, ["Connected", "Connecting…", "Choose a network", "Not connected"]),
]


def check_copy() -> list[str]:
    problems = []
    for width, font, size, texts in COPY:
        for text in texts:
            w = text_width(text, font, size)
            if w > width:
                problems.append(f"copy {text!r} is {w:.0f} px wide in a {width} px label")
    return problems


def check_store_text() -> list[str]:
    """Sample store summaries fit the About page untruncated (ASCII, <= 120 chars)."""
    problems = []
    for app in PRESETS + STORE_ONLY:
        if len(app["summary"]) > 120 or not app["summary"].isascii():
            problems.append(f"summary of {app['id']} must be ASCII and <= 120 characters")
        if wrap_lines(app["summary"], "sans", 26, SUMMARY_W, SUMMARY_LINES)[1]:
            problems.append(f"summary of {app['id']} needs more than {SUMMARY_LINES} lines")
    return problems


def unused_icons(states, extras, templates) -> list[str]:
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
    # Images the keyboard and the prototype swap in at runtime.
    used |= {"back-28-white.png", "backspace-28-white.png", "battery_full-28-white.png",
             "battery_charging-28-white.png", "eye_off-32-white.png", "wifi_off-28-grey.png",
             "robot-28-grey.png", "star_fill-32-orange.png", "trash-32-white.png"}
    return sorted(p.name for p in (DESIGN / "assets/icons").glob("*.png") if p.name not in used)


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
                             f"行高 {o['item_height']} | 行模板 `{o['row_template']}` |")
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
    cf = font_for("medium", 13)
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
    layout = {"schema": "vibe-mode-design/2", "screen": {"w": W, "h": H}, "tokens": TOKENS,
              "states": states,
              "prototype": {"states": extras, "row_templates": templates,
                            "row_heights": {"apps": APP_ITEM_H, "networks": NET_ITEM_H},
                            "categories": [{"id": k, "label": t, "icon": i} for k, t, i in CATEGORIES],
                            "apps": PRESETS, "store_only": STORE_ONLY, "store_updates": STORE_UPDATES,
                            "favorites": FAVORITES, "current": CURRENT, "filter_labels": FILTER_LABELS,
                            "empty_copy": EMPTY_COPY, "qr_urls": QR_URLS, "wifi_link_token": TOKEN,
                            "ai_token": AI_TOKEN}}
    (DESIGN / "layout.json").write_text(json.dumps(layout, indent=1, ensure_ascii=False) + "\n",
                                        encoding="utf-8")
    (DESIGN / "layout-tables.md").write_text(layout_tables(states), encoding="utf-8")
    problems = check(states, extras)
    for p in problems:
        print("check:", p)
    for name in unused_icons(states, extras, templates):
        print("note: unused icon", name)
    print(f"{len(states)} states rendered; {len(problems)} layout issues")
    return 1 if problems and "--strict" in sys.argv else 0


if __name__ == "__main__":
    raise SystemExit(main())
