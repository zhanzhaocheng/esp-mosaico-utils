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
# Every size is a separate baked bitmap font in flash, so the design uses a
# short type scale; the layout check rejects any other size.
TYPE_SCALE = {"dot": [22, 32, 40, 56, 112], "medium": [12, 15, 17, 20, 24, 28], "sans": [13, 15]}

TOKENS = {
    "colors": {"background": BG, "card": CARD, "raised": RAISED, "tile": TILE, "outline": LINE,
               "divider": DIVIDER, "text": TEXT, "text_secondary": TEXT2, "text_tertiary": TEXT3,
               "accent": ACCENT, "primary_bg": PRIMARY_BG, "primary_fg": PRIMARY_FG},
    "fonts": FONTS,
    "line_height_em": LINE_EM,
    "type_scale": TYPE_SCALE,
    "radius": {"card": 20, "row": 16, "key": 18, "chip": 22, "pill": "h/2"},
    "margin": M,
    "min_touch": 44,
    "screen": {"corner_radius": SCREEN_R, "ai_key_center_x": AI_KEY_CX},
    "qr": {"version": 3, "ecc": "L", "quiet_zone_modules": 2, "modules": QR_MODULES,
           "min_module_px": 5, "dark": "#000000", "light": "#FFFFFF"},
    "motion": {"page_slide_px": 48, "page_slide_ms": 160, "easing": "ease_out"},
    "keyboard": {"bg_color": BG, "fg_color": TEXT, "key_color": TILE, "function_color": RAISED,
                 "ok_color": ACCENT, "ok_text_color": WHITE, "key_radius": 10, "font": "medium",
                 "font_size": 20, "function_font_size": 15},
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
            "home_title", "switch_filter"}


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
# Shared building blocks
# --------------------------------------------------------------------------
def circle_button(x, y, icon_name, action, name, size=48, icon_size=22, color="white"):
    return button(x, y, size, size, bg=BG, border=LINE, bw=2,
                  icon=f"assets/icons/{icon_name}-{icon_size}-{color}.png", action=action, name=name)


def header(title, subtitle, back="back", help_topic="topics", page=None, extra=None):
    """Back button, dot-matrix title and subtitle; ? and an optional extra button on the right."""
    objs = []
    if back:
        objs.append(circle_button(M, 16, "back", back, f"button_back_{page}"))
    right = W - M
    if help_topic:
        objs.append(circle_button(right - 48, 16, "help", f"help:{help_topic}", f"button_help_{page}"))
        right -= 56
    if extra:
        objs.append(extra(right - 48))
        right -= 56
    text_w = right - 80 - (8 if right < W - M else 0)
    objs.append(label(80, 18, text_w, title, "dot", 32, TEXT, name=f"{page}_title"))
    objs.append(label(80, 54, text_w, subtitle, "sans", 15, TEXT2, name=f"{page}_subtitle", dynamic=True))
    return objs


def primary(x, y, w, text, action, name, icon_name=None, h=56):
    return button(x, y, w, h, text, "medium", 17, PRIMARY_FG, PRIMARY_BG,
                  icon=f"assets/icons/{icon_name}-20-black.png" if icon_name else None,
                  action=action, name=name)


def secondary(x, y, w, text, action, name, icon_path=None, h=56, color=TEXT):
    return button(x, y, w, h, text, "medium", 17, color, BG, border=LINE, bw=2, icon=icon_path,
                  action=action, name=name)


def tile(x, y, size, letter, radius, dot_size, name=None, color=TEXT, bg=TILE):
    th = line_h("dot", dot_size)
    return [container(x, y, size, size, bg, radius, name=f"{name}_tile" if name else None),
            label(x, y + (size - th) // 2 + round(dot_size * 0.05), size, letter, "dot", dot_size,
                  color, "center", name=f"{name}_initial" if name else None, dynamic=True)]


CHIP_Y, CHIP_H = 114, 44


def chip(x, w, text, action, name, on, icon_name=None, icon_left=None):
    """Filter chip. GSP colours are static, so each chip has an _on and an _off object."""
    icon_path = None
    if icon_name:
        icon_path = f"assets/icons/{icon_name}-18-{'black' if on else 'white'}.png"
    return button(x, CHIP_Y, w, CHIP_H, text, "medium", 15, PRIMARY_FG if on else TEXT,
                  PRIMARY_BG if on else BG, border=None if on else LINE, bw=0 if on else 2,
                  icon=icon_path, action=action, name=f"{name}_{'on' if on else 'off'}", icon_gap=8,
                  icon_left=icon_left)


def chips(flt):
    in_category = flt not in ("all", "favorites")
    return [chip(M, 72, "All", "filter:all", "chip_all", flt == "all"),
            chip(96, 136, "Favorites", "filter:favorites", "chip_favorites", flt == "favorites",
                 "star_fill" if flt == "favorites" else "star"),
            chip(240, 176, CATEGORY_LABEL[flt] if in_category else "Categories", "go:categories",
                 "chip_category", in_category, "grid", icon_left=16)]


def qr_code(x, y, name, module, action, button_name):
    """QR image at an integer module size, with a transparent button to enlarge it."""
    size = QR_MODULES * module
    return [image(x, y, f"assets/qr/{name}.png", name=f"{button_name}_code", w=size, h=size, qr=True),
            button(x, y, size, size, bg=None, radius=0, action=action, name=button_name)]


def enlarge_hint(x, y, w, text="Tap the code to enlarge"):
    return [icon(x, y + 1, "expand", 16, "grey"), label(x + 22, y, w - 22, text, "sans", 13, TEXT2)]


def status_row(agent=True, wifi_on=True, battery="mid", preset=None):
    """Home status row: same icon order as the device's own status bar."""
    objs = [container(M, 29, 10, 10, ACCENT, 5),
            label(34, 24, 92, "VIBE MODE", "medium", 15, TEXT2)]
    if preset:
        objs.append(label(132, 26, 96, f"↓ {preset[0]}/{preset[1]}", "medium", 12, ACCENT,
                          name="home_preset", dynamic=True))
    objs.append(icon(258, 23, "wifi" if wifi_on else "wifi_off", 22, "white" if wifi_on else "grey",
                     "status_wifi"))
    objs.append(icon(288, 23, "robot", 22, "orange" if agent else "grey", "status_agent"))
    objs.append(icon(318, 23, f"battery_{battery}", 22, "orange" if battery == "low" else "white",
                     "status_battery"))
    objs.append(circle_button(368, 12, "help", "help:topics", "button_help_home", size=44))
    objs.append(circle_button(420, 12, "settings", "go:device", "button_device", size=44))
    return objs


def ai_cue(active=False):
    """Light cue on the screen edge directly below the physical AI key (top right)."""
    return container(AI_KEY_CX - 18, 3, 36, 4, ACCENT if active else LINE, 2, name="ai_cue")


def ai_toast(text):
    """Transient banner (~1.5 s) that covers the top row after an AI key press or an event."""
    return [container(M, 14, 448, 48, RAISED, 24, border=LINE, bw=2, name="ai_toast"),
            label(M, 14 + (48 - line_h("medium", 17)) // 2, 448, text, "medium", 17, TEXT,
                  "center", name="ai_toast_text", dynamic=True)]


def section(y, text):
    return label(M, y, 300, text, "medium", 12, TEXT2)


# --------------------------------------------------------------------------
# Rows (list templates). Apps: 60 px card + 6 px gap; networks: 60 + 8.
# Row objects carry the list viewport as "clip", exactly like a GSP list.
# --------------------------------------------------------------------------
APP_ITEM_H = 66
NET_ITEM_H = 68


def clipped(objs, viewport, row_of=None):
    for obj in objs:
        if viewport:
            obj["clip"] = list(viewport)
        if row_of:
            obj["row_of"] = row_of
    return objs


def app_row(x, y, app, viewport):
    objs = [container(x, y, 448, 60, CARD, 16, role="row")]
    objs += tile(x + 9, y + 9, 42, initial(app), 12, 22, name="apps")
    # Favorite badge on the tile corner; a text glyph so the row setter can blank it.
    objs.append(label(x + 39, y + 2, 22, "★" if app["id"] in FAV else " ", "medium", 15, ACCENT,
                      "center", name="apps_star"))
    objs.append(label(x + 64, y + 9, 246, app["name"], "medium", 17, TEXT, name="apps_name"))
    objs.append(label(x + 64, y + 35, 246, f"{CATEGORY_LABEL[app['category']]} · {app['id']}", "sans",
                      13, TEXT2, name="apps_detail"))
    objs.append(label(x + 314, y + 11, 96, "● CURRENT" if app["id"] == CURRENT else " ", "medium", 12,
                      ACCENT, "right", name="apps_badge_current"))
    # Most apps are official presets, so the list marks the exception.
    objs.append(label(x + 314, y + 34, 96, " " if app["official"] else "COMMUNITY", "medium", 12,
                      TEXT2, "right", name="apps_badge_source"))
    objs.append(icon(x + 418, y + 21, "chevron", 18, "dim"))
    return clipped(objs, viewport, "apps")


def network_row(x, y, ssid, detail, viewport):
    return clipped([container(x, y, 448, 60, CARD, 16, role="row"),
                    label(x + 18, y + 9, 360, ssid, "medium", 17, TEXT, name="networks_title"),
                    label(x + 18, y + 34, 360, detail, "sans", 13, TEXT2, name="networks_detail"),
                    icon(x + 414, y + 21, "chevron", 18, "dim")], viewport, "networks")


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------
LIST_Y, LIST_H = 168, 228


def home(flt="all", agent=True, apps=None, preset=None, wifi_on=True, battery="mid"):
    apps = LIBRARY if apps is None else apps
    shown = filtered(apps, flt)
    objs = status_row(agent, wifi_on, battery, preset)
    objs.append(label(M, 64, 330, FILTER_TITLES[flt], "dot", 40, TEXT, name="home_title", dynamic=True))
    objs.append(label(348, 64, 116, f"{len(shown):02d}", "dot", 40, ACCENT, "right", name="app_count",
                      dynamic=True))
    objs += chips(flt)
    if shown:
        viewport = (M, LIST_Y, 448, LIST_H)
        objs.append({"type": "list_viewport", "x": M, "y": LIST_Y, "w": 448, "h": LIST_H, "name": "apps",
                     "item_height": APP_ITEM_H, "row_template": "apps_row"})
        for i, app in enumerate(shown[:4]):
            objs += app_row(M, LIST_Y + i * APP_ITEM_H, app, viewport)
    else:
        title, body = EMPTY_COPY[flt if flt in EMPTY_COPY else "category"]
        objs.append(image(212, 192, "assets/icons/empty-56-grey.png", name="home_empty_icon"))
        objs.append(label(M, 262, 448, title, "medium", 20, TEXT, "center", name="home_empty_title",
                          dynamic=True))
        objs.append(label(40, 294, 400, body, "sans", 15, TEXT2, "center", name="home_empty_body",
                          dynamic=True))
    objs.append(primary(M, 404, 216, "Download app", "go:download", "button_download", "download"))
    objs.append(secondary(248, 404, 216, "Develop app", "go:develop", "button_develop",
                          "assets/icons/code-20-white.png"))
    objs.append(ai_cue())
    return objs


def quick_switch(index=1, flt="all"):
    objs = [o for o in home(flt) if o.get("name") != "ai_cue"]
    apps = filtered(LIBRARY, flt)
    app = apps[index]
    objs.append(container(0, 0, W, H, BG, 0, opacity=232, role="scrim"))
    objs.append(container(40, 60, 400, 360, CARD, 28, border=LINE, bw=2, name="switch_card"))
    objs.append(label(64, 83, 228, f"QUICK SWITCH · {FILTER_TITLES[flt]}", "medium", 12, TEXT2,
                      name="switch_filter", dynamic=True))
    objs.append(label(296, 78, 120, f"{index + 1}/{len(apps)}", "dot", 22, TEXT2, "right",
                      name="switch_position", dynamic=True))
    objs += tile(180, 114, 120, initial(app), 34, 56, name="switch")
    objs.append(label(56, 250, 368, app["name"], "medium", 24, TEXT, "center", name="switch_name",
                      dynamic=True))
    objs.append(label(56, 284, 368, f"{CATEGORY_LABEL[app['category']]} · {app['id']}", "sans", 15, TEXT2,
                      "center", name="switch_detail", dynamic=True))
    objs.append(progress(64, 322, 352, 4, 35, name="switch_hold"))
    objs.append(container(64, 346, 352, 1, DIVIDER))
    for i, (key, text) in enumerate((("AI ×2", "Next"), ("Hold AI", "Open"), ("AI", "Close"))):
        x = 64 + i * 120
        objs.append(label(x, 362, 112, key, "medium", 12, TEXT, "center"))
        objs.append(label(x, 382, 112, text, "sans", 13, TEXT2, "center"))
    objs.append(ai_cue(True))
    return objs


def category_tiles():
    tiles = [("all", "All apps", "grid", len(LIBRARY)),
             ("favorites", "Favorites", "star", len(filtered(LIBRARY, "favorites")))]
    tiles += [(key, text, ic, len(filtered(LIBRARY, key))) for key, text, ic in CATEGORIES]
    return tiles


def categories(selected="all"):
    objs = header("CATEGORIES", "Find apps by type", page="categories", help_topic="start")
    for i, (key, text, ic, n) in enumerate(category_tiles()):
        x, y = M + (i % 2) * 232, 88 + (i // 2) * 88
        objs.append(button(x, y, 216, 80, bg=CARD, radius=20, action=f"filter:{key}", name=f"category_{key}"))
        objs.append(icon(x + 16, y + 16, ic, 22, "white"))
        objs.append(label(x + 112, y + 15, 88, f"{n:02d}", "dot", 22, TEXT2, "right",
                          name=f"category_{key}_count", dynamic=True))
        objs.append(label(x + 16, y + 46, 184, text, "medium", 17, TEXT))
        if key == selected:
            # One ring; the controller moves it onto the selected tile.
            objs.append(container(x, y, 216, 80, None, 20, border=ACCENT, bw=2, name="category_selected"))
    return objs


def download(digits="", status="Enter the app ID", error=""):
    objs = header("DOWNLOAD", "Get an app by its ID", page="download", help_topic="ids")
    objs += qr_code(M, 88, "ideas", 6, "qr:ideas", "button_qr_ideas")
    objs.append(label(M, 296, 198, "Scan to browse apps", "medium", 15, TEXT))
    objs.append(label(M, 319, 198, "mosaico-ideas.espressif.com", "sans", 13, TEXT2))
    objs += enlarge_hint(M, 346, 198)
    for i, text in enumerate(("Pick an app on your phone", "Type its ID on the keypad")):
        y = 384 + i * 30
        objs.append(label(M, y - 3, 22, str(i + 1), "dot", 22, ACCENT))
        objs.append(label(40, y, 178, text, "sans", 13, TEXT2))
    # ID display: up to 8 digits use the large face; longer IDs switch to the
    # compact label (the other label holds a blank glyph, as 0.2 does).
    objs.append(container(226, 88, 238, 80, CARD, 20))
    shown = digits + "·" * max(0, 6 - len(digits)) if len(digits) <= 8 else " "
    objs.append(label(234, 96, 222, shown, "dot", 40, TEXT, "center", name="id_digits", dynamic=True))
    objs.append(label(234, 105, 222, digits if len(digits) > 8 else " ", "dot", 22, TEXT, "center",
                      name="id_digits_compact", dynamic=True))
    objs.append(label(234, 140, 222, " " if error else status, "sans", 13, TEXT2, "center",
                      name="id_status", dynamic=True))
    objs.append(label(234, 140, 222, error or " ", "sans", 13, ACCENT, "center", name="id_error",
                      dynamic=True))
    keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "del", "0", "go"]
    for i, key in enumerate(keys):
        x, y = 226 + (i % 3) * 82, 180 + (i // 3) * 68
        if key == "del":
            objs.append(button(x, y, 74, 60, bg=BG, border=LINE, bw=2, radius=18,
                               icon="assets/icons/backspace-26-white.png", action="key:del", name="key_del"))
        elif key == "go":
            objs.append(button(x, y, 74, 60, bg=ACCENT, radius=18, icon="assets/icons/arrow-26-white.png",
                               action="key:go", name="key_go"))
        else:
            objs.append(button(x, y, 74, 60, key, "dot", 32, TEXT, RAISED, radius=18,
                               action=f"key:{key}", name=f"key_{key}"))
    return objs


DEVELOP_STEPS = [
    ("Vibe-code it", "Tell your AI agent what to build.\nIt writes the code for you."),
    ("Install over USB", "Plug in a data cable, then install\nfrom your agent or the website."),
    ("Share on Mosaico Ideas", "Publish it to get an app ID that\nanyone can download."),
]


def status_value(x, y, w, on_text, off_text, on, name):
    """Paired labels: orange when on, grey when off (static colours per object)."""
    return label(x, y, w, on_text if on else off_text, "medium", 15, ACCENT if on else TEXT2, "right",
                 name=f"{name}_{'on' if on else 'off'}", dynamic=True)


def develop(usb=True, agent=True):
    objs = header("DEVELOP", "Make your own app with AI", page="develop", help_topic="topics")
    objs += qr_code(M, 88, "develop", 5, "qr:develop", "button_qr_develop")
    objs.append(label(M, 261, 165, "Vibe-coding guide", "medium", 15, TEXT))
    objs += enlarge_hint(M, 286, 165, "Tap to enlarge")
    for i, (title, body) in enumerate(DEVELOP_STEPS):
        y = 88 + i * 68
        objs.append(label(197, y - 1, 24, str(i + 1), "dot", 22, ACCENT))
        objs.append(label(227, y - 1, 237, title, "medium", 17, TEXT))
        objs.append(label(227, y + 23, 237, body, "sans", 13, TEXT2))
    objs.append(container(M, 306, 448, 144, CARD, 20))
    rows = [("usb", "USB data cable", ("Plugged in", "Not plugged in"), usb, "develop_usb"),
            ("robot", "AI agent or website", ("Connected", "Waiting"), agent, "develop_link")]
    for i, (ic, text, values, on, name) in enumerate(rows):
        y = 306 + i * 48
        if i:
            objs.append(container(66, y, 382, 1, DIVIDER))
        objs.append(icon(32, y + 13, ic, 22, "grey"))
        objs.append(label(66, y + 14, 180, text, "medium", 15, TEXT))
        objs.append(status_value(244, y + 14, 204, *values, on, name))
    y = 402
    objs.append(container(66, y, 382, 1, DIVIDER))
    objs.append(button(M, y, 448, 48, bg=None, radius=0, action="go:wifi_link", name="button_wifi_link"))
    objs.append(icon(32, y + 13, "wifi", 22, "grey"))
    objs.append(label(66, y + 14, 130, "Wi-Fi link", "medium", 15, TEXT))
    objs.append(label(196, y + 14, 224, "192.168.1.20:7777", "sans", 15, TEXT2, "right",
                      name="develop_endpoint", dynamic=True))
    objs.append(icon(428, y + 15, "chevron", 18, "dim"))
    return objs


def wifi_link():
    objs = header("WI-FI LINK", "Install over your network", page="wifilink", help_topic="topics")
    objs.append(container(M, 88, 448, 160, CARD, 20))
    objs.append(label(32, 102, 200, "ADDRESS", "medium", 12, TEXT2))
    objs.append(label(32, 120, 416, "192.168.1.20:7777", "medium", 24, TEXT, name="wifilink_endpoint",
                      dynamic=True))
    objs.append(container(32, 162, 416, 1, DIVIDER))
    objs.append(label(32, 174, 200, "TOKEN", "medium", 12, TEXT2))
    objs.append(label(32, 190, 416, f"{TOKEN[:32]}\n{TOKEN[32:]}", "sans", 15, TEXT, name="wifilink_token",
                      dynamic=True))
    objs.append(label(M, 266, 448, "Your AI agent can install apps over Wi-Fi\nwith this address and token.",
                      "sans", 15, TEXT2))
    objs.append(label(M, 316, 448, "Keep the token private.", "sans", 15, ACCENT))
    return objs


def detail(mode="current", confirm=False, app=None):
    remote = mode in ("remote_new", "remote_update")
    if app is None:
        app = {"current": BY_ID[CURRENT], "local": BY_ID["100009"], "remote_new": BY_ID["238114"],
               "remote_update": dict(BY_ID["100006"], version=STORE_UPDATES["100006"])}[mode]
    fav = app["id"] in FAV
    subtitle = "On Mosaico Ideas" if remote else "Saved on this device"
    extra = None
    if not remote:
        def extra(x):
            if fav:
                return circle_button(x, 16, "star_fill", "app:favorite", "button_favorite_on", color="orange")
            return circle_button(x, 16, "star", "app:favorite", "button_favorite_off")
    objs = header("APP", subtitle, page="detail", help_topic="ids", extra=extra)
    objs += tile(M, 88, 64, initial(app), 18, 40, name="detail")
    objs.append(label(92, 87, 372, app["name"], "medium", 20, TEXT, name="detail_name", dynamic=True))
    objs.append(label(92, 115, 200, app["id"], "dot", 22, ACCENT, name="detail_id", dynamic=True))
    objs.append(label(92, 140, 372, f"v{app['version']} · {app['size']}", "sans", 15, TEXT2,
                      name="detail_meta", dynamic=True))
    # The app's own page on Mosaico Ideas: the device encodes the store URL at runtime.
    objs += qr_code(M, 170, f"app-{app['id']}", 5, "qr:app", "button_qr_app")
    objs.append(label(197, 170, 267, app["summary"], "sans", 15, TEXT2, h=line_h("sans", 15, 4),
                      name="detail_summary", dynamic=True, wrap=True))
    objs.append(container(197, 250, 267, 1, DIVIDER))
    source = "Official" if app["official"] else "Community"
    objs.append(label(197, 258, 267, f"{CATEGORY_LABEL[app['category']]} · {source}", "sans", 15, TEXT2,
                      name="detail_facts", dynamic=True))
    local = BY_ID.get(app["id"])
    status = {"current": "● Current app", "local": "Saved · not running", "remote_new": "Not on this device",
              "remote_update": f"Update · v{local['version'] if local else '?'} → v{app['version']}"}[mode]
    accent = mode in ("current", "remote_update")
    objs.append(label(197, 283, 267, status, "medium", 15, ACCENT if accent else TEXT,
                      name="detail_status_accent" if accent else "detail_status", dynamic=True))
    objs += enlarge_hint(197, 314, 267, "Scan for the full description")
    if remote:
        objs.append(primary(M, 344, 448, "Download & run", "store:run", "button_primary", "download", h=52))
        objs.append(secondary(M, 404, 216, "Download only", "store:keep", "button_secondary",
                              "assets/icons/download-20-white.png", h=52))
        objs.append(secondary(248, 404, 216, "Cancel", "back", "button_tertiary", h=52))
    else:
        text = "Open" if mode == "current" else "Run this app"
        objs.append(primary(M, 344, 448, text, "app:run", "button_primary", "play", h=52))
        objs.append(secondary(M, 404, 216, "Update", "app:update", "button_secondary",
                              "assets/icons/refresh-20-white.png", h=52))
        if confirm:
            objs.append(button(248, 404, 216, 52, "Tap again to delete", "medium", 15, WHITE, ACCENT,
                               action="app:delete", name="button_delete_confirm"))
        else:
            objs.append(secondary(248, 404, 216, "Delete", "app:delete_ask", "button_tertiary",
                                  "assets/icons/trash-20-orange.png", h=52, color=ACCENT))
    return objs


def qr_full(name="app-100001", title="Scan with your phone camera",
            url="mosaico-ideas.espressif.com/app/100001"):
    """Any QR code, enlarged to 12 px modules. Tap anywhere or press AI to close."""
    size = QR_MODULES * 12
    return [image((W - size) // 2, 14, f"assets/qr/{name}.png", name="qr_full_code", w=size, h=size, qr=True),
            label(M, 420, 448, title, "medium", 15, TEXT, "center", name="qr_full_title", dynamic=True),
            label(M, 441, 448, url, "sans", 13, TEXT2, "center", name="qr_full_url", dynamic=True),
            button(0, 0, W, H, bg=None, radius=0, action="back", name="button_qr_close")]


def progress_page(kind="agent"):
    spec = {
        "agent": ("FROM YOUR AI AGENT · USB", "Installing your app", "hello_world · v0.2.1",
                  42, "1.20 MB of 2.85 MB", "236 KB/s", "Step 1 of 2 · Receiving", False),
        "download": ("FROM MOSAICO IDEAS", "Downloading", "Retro Snake · v1.0.3",
                     67, "0.61 MB of 0.92 MB", "512 KB/s", "File 2 of 3", True),
        "install": ("FROM YOUR LIBRARY", "Switching apps", "Weather Station · v2.0.1",
                    88, "2.11 MB of 2.40 MB", "1.6 MB/s", "Step 2 of 2 · Writing", False),
    }[kind]
    caption, title, detail_text, pct, size_text, rate, step, cancel = spec
    objs = [label(M, 31, 448, caption, "medium", 12, ACCENT, name="progress_caption", dynamic=True),
            label(M, 52, 448, title, "medium", 28, TEXT, name="progress_title", dynamic=True),
            label(M, 92, 448, detail_text, "sans", 15, TEXT2, name="progress_detail", dynamic=True),
            label(M, 126, 448, f"{pct}%", "dot", 112, TEXT, "center", name="progress_percent", dynamic=True),
            progress(M, 252, 448, 8, pct),
            label(M, 274, 280, size_text, "sans", 15, TEXT2, name="progress_bytes", dynamic=True),
            label(296, 274, 168, rate, "medium", 15, TEXT, "right", name="progress_rate", dynamic=True),
            label(M, 302, 448, step, "sans", 13, TEXT3, name="progress_step", dynamic=True)]
    objs.append(container(M, 352, 448, 1, DIVIDER))
    objs.append(icon(M + 2, 368, "power", 20, "orange"))
    objs.append(label(46, 368, 300, "Keep the device powered", "sans", 15, TEXT2))
    if cancel:
        objs.append(secondary(M, 404, 448, "Cancel download", "store:cancel", "button_cancel"))
    else:
        objs.append(label(M, 420, 448, "The device restarts into the app when done", "sans", 13, TEXT3,
                          "center"))
    return objs


def result(kind="installed"):
    spec = {
        "installed": (True, "App installed", "Pixel Pet · v1.2.0", "Restarting into your app…", None),
        "saved": (True, "Saved to My Apps", "Retro Snake · v1.0.3",
                  "Open it any time from My Apps.", "Open now"),
        "failed": (False, "Couldn't download", "Retro Snake · v1.0.3",
                   "The connection dropped. Check Wi-Fi\nand try again.", "Try again"),
    }[kind]
    ok, title, caption, body, second = spec
    objs = [container(192, 72, 96, 96, BG, 48, border=ACCENT if ok else TEXT3, bw=3, name="result_ring"),
            icon(220, 100, "check" if ok else "close", 40, "orange" if ok else "grey", "result_icon"),
            label(M, 190, 448, title, "medium", 28, TEXT, "center", name="result_title", dynamic=True),
            label(M, 232, 448, caption, "sans", 15, TEXT2, "center", name="result_caption", dynamic=True),
            label(40, 270, 400, body, "sans", 15, TEXT2, "center", name="result_detail", dynamic=True)]
    if second:
        objs.append(secondary(M, 396, 216, second, "result:second", "button_result_second"))
        objs.append(primary(248, 396, 216, "Done", "go:home", "button_done"))
    else:
        objs.append(primary(M, 396, 448, "Done", "go:home", "button_done"))
    if not ok:
        objs.append(circle_button(W - M - 48, 16, "help", "help:fix", "button_help_result"))
    return objs


HELP_TOPICS = [
    ("start", "flag", "Getting started", "Enter Vibe Mode, AI key, favorites"),
    ("develop", "code", "Develop apps", "Vibe coding, USB install, sharing"),
    ("ids", "hash", "App IDs & sharing", "Find, share and download apps"),
    ("fix", "support", "Troubleshooting", "Wi-Fi, failed installs, recovery"),
]
HELP_TEXT = {
    "start": ("Getting started", "flag", "help-start",
              ["Hold AI, then double-press\npower to come back here.",
               "Press AI to go back.\nDouble-press AI to switch.",
               "Star apps to find them\nfast in Favorites."]),
    "develop": ("Develop apps", "code", "develop",
                ["Vibe-code with your AI\nagent on a computer.",
                 "Install over a USB data\ncable; watch it here.",
                 "Share on Mosaico Ideas\nto get an app ID."]),
    "ids": ("App IDs & sharing", "hash", "help-ids",
            ["Every app has a number ID,\nusually 6 digits.",
             "Share an app by telling\nfriends its ID.",
             "The same ID always gets\nthe newest version."]),
    "fix": ("Troubleshooting", "support", "help-fix",
            ["Check Wi-Fi and try\nagain.",
             "Keep the device powered\nwhile installing.",
             "Still stuck? Scan for the\nrecovery guide."]),
}
# Short form of each QR payload, shown under the code.
QR_URLS = {
    "ideas": "mosaico-ideas.espressif.com",
    "develop": "mosaico.espressif.com/guide/vibe-coding",
    "help-start": "mosaico.espressif.com/vibe/start",
    "help-ids": "mosaico.espressif.com/vibe/ids",
    "help-fix": "mosaico.espressif.com/vibe/fix",
}


def help_topics():
    objs = header("HELP", "Scan a code to read the guide", page="help", help_topic=None)
    for i, (key, icon_name, title, desc) in enumerate(HELP_TOPICS):
        y = 88 + i * 76
        objs.append(button(M, y, 448, 68, bg=CARD, radius=18, action=f"help:{key}", name=f"topic_{key}"))
        objs.append(icon(34, y + 22, icon_name, 24, "white"))
        objs.append(label(72, y + 11, 330, title, "medium", 17, TEXT))
        objs.append(label(72, y + 38, 330, desc, "sans", 13, TEXT2))
        objs.append(icon(418, y + 25, "chevron", 18, "dim"))
    objs.append(secondary(M, 404, 448, "Replay guide", "guide:1", "button_replay",
                          "assets/icons/replay-20-white.png"))
    return objs


def help_topic(key="start"):
    title, icon_name, qr_name, points = HELP_TEXT[key]
    objs = header("HELP", "Scan for the full guide", back="back", page="topic", help_topic=None)
    objs += qr_code(M, 88, qr_name, 6, f"qr:{qr_name}", "button_qr_topic")
    host, _, path = QR_URLS[qr_name].partition("/")
    objs.append(label(M, 294, 198, f"{host}\n/{path}" if path else host, "sans", 13, TEXT2, "center",
                      name="topic_url", dynamic=True))
    objs += enlarge_hint(M + 44, 336, 154, "Tap to enlarge")
    objs.append(icon(226, 92, icon_name, 24, "white", "topic_icon"))
    objs.append(label(226, 124, 238, title, "medium", 20, TEXT, name="topic_title", dynamic=True))
    y = 124 + line_h("medium", 20) + 14
    for i, point in enumerate(points):
        objs.append(container(226, y + 8, 6, 6, ACCENT, 3))
        objs.append(label(240, y, 224, point, "sans", 15, TEXT2, name=f"topic_point_{i}", dynamic=True))
        y += line_h("sans", 15, point.count("\n") + 1) + 12
    objs.append(secondary(M, 404, 448, "All help topics", "help:topics", "button_topics"))
    return objs


def wifi(pending=False):
    sub = "Connect to continue your download" if pending else "Apps use this network too"
    objs = header("WI-FI", sub, page="wifi", help_topic="fix")
    objs.append(container(M, 88, 448, 72, CARD, 20))
    objs.append(icon(34, 113, "wifi", 22, "grey"))
    objs.append(label(68, 96, 280, "Studio-5G", "medium", 20, TEXT, name="wifi_connection", dynamic=True))
    objs.append(label(68, 123, 280, "Connected · 192.168.1.20", "sans", 15, TEXT2, name="wifi_detail",
                      dynamic=True))
    objs.append(secondary(360, 102, 92, "Forget", "wifi:forget", "button_forget", h=44))
    objs[-1]["size"] = 15
    objs.append(label(M, 186, 300, "NETWORKS · 4", "medium", 12, TEXT2, name="wifi_scan", dynamic=True))
    objs.append(button(368, 172, 96, 44, "Scan", "medium", 15, TEXT, BG, border=LINE, bw=2,
                       icon="assets/icons/refresh-20-white.png", action="wifi:scan", name="button_scan",
                       icon_gap=6))
    viewport = (M, 228, 448, 228)
    objs.append({"type": "list_viewport", "x": M, "y": 228, "w": 448, "h": 228, "name": "networks",
                 "item_height": NET_ITEM_H, "row_template": "networks_row"})
    for i, (ssid, info) in enumerate(NETWORKS[:4]):
        objs += network_row(M, 228 + i * NET_ITEM_H, ssid, info, viewport)
    return objs


def text_entry(page, title, subtitle, display, placeholder, note, hint, toggle=None, note_color=TEXT2):
    """Keyboard entry page shared by the Wi-Fi password, the city and the AI token."""
    objs = header(title, subtitle, page=page, help_topic=None)
    objs.append(container(M, 88, 448, 64, CARD, 18))
    objs.append(label(34, 108, 340, display or placeholder, "medium", 20, TEXT if display else TEXT3,
                      name=f"{page}_display", dynamic=True))
    if toggle is not None:
        objs.append(button(392, 96, 56, 48, bg=RAISED, radius=16,
                           icon=f"assets/icons/{'eye' if toggle else 'eye_off'}-24-white.png",
                           action=f"{page}:toggle", name=f"button_toggle_{page}"))
    objs.append(label(M, 165, 448, note, "sans", 15, note_color, name=f"{page}_note", dynamic=True))
    objs.append(label(M, 196, 448, hint, "sans", 13, TEXT3))
    objs.append(keyboard(name=f"{page}_keyboard"))
    return objs


def password(masked=True, error=""):
    return text_entry("password", "PASSWORD", "Studio-5G", "••••••••••" if masked else "makers2026",
                      "Type the Wi-Fi password", error or " ", "Up to 64 characters", toggle=masked,
                      note_color=ACCENT)


def city():
    return text_entry("city", "CITY", "Shared with all apps", "Shanghai", "Type your city",
                      "Apps use it for weather and local info.", "Up to 40 characters")


def token():
    masked = "•" * 12 + AI_TOKEN[-4:]
    return text_entry("token", "AI TOKEN", "Shared with all apps", masked, "Type your token",
                      "Every app on this device can read it.", "Long token? Set it from your computer.",
                      toggle=True, note_color=ACCENT)


def device():
    objs = header("DEVICE", "Vibe Mode 0.3.0 · ESP32-S31", page="device", help_topic="fix")
    objs.append(section(84, "SHARED WITH APPS"))
    objs.append(container(M, 104, 448, 144, CARD, 20))
    shared = [("wifi", "Wi-Fi", "Studio-5G", "go:wifi", "device_wifi"),
              ("pin", "City", "Shanghai", "go:city", "device_city"),
              ("key", "AI token", f"Set · ends in {AI_TOKEN[-4:]}", "go:token", "device_token")]
    for i, (ic, text, value, action, value_name) in enumerate(shared):
        y = 104 + i * 48
        if i:
            objs.append(container(66, y, 382, 1, DIVIDER))
        objs.append(button(M, y, 448, 48, bg=None, radius=0, action=action, name=f"button_{value_name}"))
        objs.append(icon(32, y + 13, ic, 22, "grey"))
        objs.append(label(66, y + 14, 130, text, "medium", 15, TEXT))
        objs.append(label(196, y + 14, 224, value, "sans", 15, TEXT2, "right", name=value_name, dynamic=True))
        objs.append(icon(428, y + 15, "chevron", 18, "dim"))
    objs.append(label(M, 253, 448, "Every app can read these. Only Vibe Mode can change them.", "sans", 13,
                      TEXT3))
    objs.append(section(282, "THIS DEVICE"))
    objs.append(container(M, 302, 448, 144, CARD, 20))
    rows = [("chip", "Vibe Mode", "0.3.0", "device_version"),
            ("id", "MAC address", "30:ED:A0:F4:60:56", "device_mac"),
            ("storage", "App storage", f"{len(LIBRARY)} apps · {sum(float(a['size'].split()[0]) for a in LIBRARY):.1f} MB used",
             "device_storage")]
    for i, (ic, text, value, value_name) in enumerate(rows):
        y = 302 + i * 48
        if i:
            objs.append(container(66, y, 382, 1, DIVIDER))
        objs.append(icon(32, y + 13, ic, 22, "grey"))
        objs.append(label(66, y + 14, 150, text, "medium", 15, TEXT))
        objs.append(label(206, y + 14, 242, value, "sans", 15, TEXT2, "right", name=value_name, dynamic=True))
    objs.append(label(M, 451, 448, "App downloads send this device's MAC and version.", "sans", 13, TEXT3,
                      "center"))
    return objs


def guide(step=1):
    objs = [label(M, 26, 120, f"0{step}/04", "dot", 22, TEXT2, name="guide_step", dynamic=True),
            button(W - M - 92, 16, 92, 44, "Skip", "medium", 15, TEXT2, BG, action="guide:done",
                   name="button_skip")]
    if step == 1:
        title_w = int(text_width("VIBE MODE", "dot", 56))
        objs.append(label(M, 100, 448, "VIBE MODE", "dot", 56, TEXT))
        objs.append(container(M + title_w + 6, 133, 12, 12, ACCENT, 6))
        objs.append(label(M, 192, 448, "A safe home for\nyour apps", "medium", 28, TEXT))
        objs.append(label(M, 286, 448, "Your AI agent installs apps here, and you\n"
                          "can watch every step. Switch apps, get new\nones by ID, and come back any time.",
                          "sans", 15, TEXT2))
    elif step == 2:
        objs.append(label(M, 76, 448, "Coming back here", "medium", 24, TEXT))
        objs += guide_device(M, 120)
        # Step numbers sit next to the ringed keys in the drawing.
        objs.append(label(M + 164, 125, 22, "1", "dot", 22, ACCENT))
        objs.append(label(M + 164, 291, 22, "2", "dot", 22, ACCENT))
        steps = (("1", "Hold the AI key", "Top edge, on the right.\nKeep holding it."),
                 ("2", "Double-press power", "Bottom edge, on the right.\nThe device restarts."),
                 ("3", "Release AI", "When the Vibe Mode\nscreen appears."))
        for i, (num, head, sub) in enumerate(steps):
            y = 124 + i * 76
            objs.append(label(234, y - 2, 30, num, "dot", 32, ACCENT))
            objs.append(label(268, y + 1, 196, head, "medium", 17, TEXT))
            objs.append(label(268, y + 26, 196, sub, "sans", 13, TEXT2))
    elif step == 3:
        objs.append(label(M, 76, 448, "Two ways to get apps", "medium", 24, TEXT))
        cards = (("download", "Download", "Type an app ID from\nMosaico Ideas, or scan\nto browse."),
                 ("code", "Develop", "Vibe-code with your AI\nagent, install over USB,\nthen share it."))
        for i, (ic, head, body) in enumerate(cards):
            x = M + i * 232
            objs.append(container(x, 120, 216, 196, CARD, 20))
            objs.append(icon(x + 18, 138, ic, 24, "white"))
            objs.append(label(x + 18, 174, 180, head, "medium", 20, TEXT))
            objs.append(label(x + 18, 206, 184, body, "sans", 15, TEXT2))
        objs.append(label(M, 340, 448, "Tap ☆ on any app to keep it in Favorites.", "sans", 15, TEXT2,
                          "center"))
    else:
        objs.append(label(M, 76, 448, "Your AI key", "medium", 24, TEXT))
        rows = [("AI", "Go back"), ("AI ×2", "Switch apps"), ("Hold AI", "Open the selected app")]
        for i, (key, text) in enumerate(rows):
            y = 124 + i * 60
            objs.append(button(M, y, 112, 44, key, "medium", 15, TEXT, RAISED, name=f"guide_key_{i}"))
            objs.append(label(144, y + 12, 320, text, "sans", 15, TEXT))
        objs.append(container(M, 316, 448, 1, DIVIDER))
        objs.append(circle_button(M, 334, "help", "help:topics", "guide_help_sample", size=44))
        objs.append(label(72, 346, 392, "Tap ? on any page for help and QR guides.", "sans", 15, TEXT2))
    if step > 1:
        objs.append(secondary(M, 404, 140, "Back", f"guide:{step - 1}", "button_guide_back"))
        objs.append(primary(164, 404, 300, "Start" if step == 4 else "Next",
                            "guide:done" if step == 4 else f"guide:{step + 1}", "button_guide_next"))
    else:
        objs.append(primary(M, 404, 448, "Next", "guide:2", "button_guide_next"))
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
    objs = [container(x + kx - 6, y + ky - 6, kw + 12, kh + 12, None, 9, border=ACCENT, bw=2, name=name)
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
    objs = tile(180, 120, 120, initial(app), 34, 56, name="launch")
    objs.append(label(M, 262, 448, f"Opening {app['name']}", "medium", 24, TEXT, "center",
                      name="launch_title", dynamic=True))
    objs.append(label(M, 298, 448, "Restarting into your app…", "sans", 15, TEXT2, "center"))
    return objs


def app_running(app=None):
    """Prototype only: stands in for the user's app after Vibe Mode hands over."""
    app = app or BY_ID[CURRENT]
    objs = [container(0, 0, W, H, "#0A0A0A", 0, role="background")]
    objs += tile(180, 96, 120, initial(app), 34, 56, name="running", bg=RAISED)
    objs.append(label(M, 236, 448, app["name"], "medium", 24, TEXT, "center", name="running_title",
                      dynamic=True))
    objs.append(label(M, 274, 448, "Your app is running", "sans", 15, TEXT2, "center"))
    objs.append(label(40, 330, 400, "To come back: hold AI, then double-press power.", "sans", 13,
                      TEXT3, "center"))
    objs.append(secondary(96, 380, 288, "Simulate the gesture", "proto:return", "button_return"))
    return objs


def prototype_extras():
    extras = [{"id": f"help-topic-{key}", "page": "help_topic", "objects": help_topic(key)}
              for key in HELP_TEXT]
    extras.append({"id": "wifi-pending", "page": "wifi", "objects": wifi(True)})
    extras.append({"id": "home-category-empty", "page": "home",
                   "objects": home("motor", apps=[a for a in LIBRARY if a["category"] != "motor"])})
    extras.append({"id": "launching", "page": "launching", "objects": launching()})
    extras.append({"id": "app-running", "page": "app_running", "objects": app_running()})
    for extra in extras:
        if extra["page"] != "app_running" and not any(o.get("name") == "ai_cue" for o in extra["objects"]):
            extra["objects"].append(ai_cue())
    templates = {"apps_row": app_row(0, 0, LIBRARY[0], None),
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
    add_state("home-ai-hint", "home", "Home · AI pressed (hint toast)",
              hint + [ai_cue(True)] + ai_toast("Double-press AI to switch apps"))
    add_state("quick-switch", "home", "Quick switch (AI ×2)", quick_switch())
    add_state("categories", "categories", "Categories", categories("smart-home"))
    add_state("download", "download", "Download · empty", download())
    add_state("download-typing", "download", "Download · typing", download("2381", "Tap → to look it up"))
    add_state("download-error", "download", "Download · not found",
              download("404040", error="No app with this ID"))
    add_state("develop", "develop", "Develop app", develop())
    add_state("wifi-link", "wifi_link", "Develop · Wi-Fi link", wifi_link())
    add_state("detail-current", "detail", "Detail · current app (favorite)", detail("current"))
    add_state("detail-local", "detail", "Detail · saved app", detail("local", app=BY_ID["100012"]))
    add_state("detail-delete", "detail", "Detail · delete confirmation",
              detail("local", True, app=BY_ID["100012"]))
    add_state("detail-remote", "detail", "Detail · found on Mosaico Ideas", detail("remote_new"))
    add_state("detail-update", "detail", "Detail · update available", detail("remote_update"))
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
    add_state("password", "password", "Wi-Fi password", password())
    add_state("device", "device", "Device · shared settings", device())
    add_state("city", "city", "City (shared)", city())
    add_state("token", "token", "AI token (shared)", token())
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
        top = y + (h - lh * len(lines)) / 2
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
            shift = Image.open(DESIGN / "assets/icons/back-22-white.png").rotate(-90)
            img.paste(shift, (int(kx) + 17, int(ky) + 14), shift)
        elif text == "del":
            bs = Image.open(DESIGN / "assets/icons/backspace-26-white.png")
            img.paste(bs, (int(kx) + 15, int(ky) + 12), bs)
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
            if t == "button" and (w < 44 or h < 44):
                problems.append(f"{where} touch target {w}x{h} is below 44x44")
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
COPY = [
    (222, "sans", 13, ["Enter the app ID", "Tap → to look it up", "Looking up…",
                       "Type an app ID first", "No app with this ID", "This app was removed",
                       "Not available for this device", "Download not allowed",
                       "Store is busy. Try again soon.", "Can't reach the store. Check Wi-Fi.",
                       "Storage unavailable", "Not enough storage"]),
    (448, "medium", 17, ["Double-press AI to switch apps", "Double-press AI, then hold to open",
                         "No apps in this list", "Download cancelled", "Connect Wi-Fi to check for updates",
                         "Added to Favorites", "Removed from Favorites", "AI agent connected",
                         "City saved", "AI token saved", "AI token cleared", "Getting your preset apps"]),
    (330, "dot", 40, list(FILTER_TITLES.values())),
    (122, "medium", 15, [text for _, text, _ in CATEGORIES] + ["Categories", "Other"]),
    (96, "medium", 12, ["↓ 20/20"]),
    (228, "medium", 12, [f"QUICK SWITCH · {t}" for t in FILTER_TITLES.values()]),
    (184, "medium", 17, ["All apps", "Favorites", "Other"] + [text for _, text, _ in CATEGORIES]),
    (267, "medium", 15, ["Update · v10.12.3 → v10.13.0", "Update available", "Saved · not running",
                         "Not on this device", "● Current app"]),
    (267, "sans", 15, [f"{text} · Community" for _, text, _ in CATEGORIES] + ["Other · Community"]),
    (246, "sans", 13, ["Communication · 1234567890123456"]),
    (448, "medium", 12, ["FROM YOUR AI AGENT · WI-FI", "FROM YOUR AI AGENT · USB", "FROM THE WEBSITE · USB",
                         "FROM YOUR COMPUTER · USB", "FROM MOSAICO IDEAS", "FROM YOUR LIBRARY"]),
    (448, "medium", 28, ["Installing your app", "Downloading", "Switching apps", "Couldn't install the app",
                         "Couldn't download", "Saved to My Apps", "App installed"]),
    (400, "sans", 15, ["The connection dropped. Check Wi-Fi", "Open it any time from My Apps.",
                       "Restarting into your app…"]),
    (448, "sans", 15, ["Use at least 8 characters", "Wrong password. Try again.", "Type a city name first"]),
    (224, "sans", 15, ["Set · ends in 4c8e", "Not set", "Not connected", "Studio-5G"]),
    (242, "sans", 15, ["24 apps · 312.4 MB used", "30:ED:A0:F4:60:56"]),
    (204, "medium", 15, ["Plugged in", "Not plugged in", "Connected", "Waiting"]),
    (224, "sans", 15, ["192.168.100.200:7777", "Connect Wi-Fi first"]),
    (300, "medium", 12, ["NETWORKS · 16", "SCANNING…"]),
    (268, "sans", 15, ["On Mosaico Ideas", "Saved on this device"]),
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
    """Sample store summaries fit the detail page untruncated (ASCII, <= 120 chars, 4 lines)."""
    problems = []
    for app in PRESETS + STORE_ONLY:
        if len(app["summary"]) > 120 or not app["summary"].isascii():
            problems.append(f"summary of {app['id']} must be ASCII and <= 120 characters")
        if wrap_lines(app["summary"], "sans", 15, 267, 4)[1]:
            problems.append(f"summary of {app['id']} needs more than 4 lines at 267 px")
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
    used |= {"back-22-white.png", "backspace-26-white.png", "battery_full-22-white.png",
             "battery_charging-22-white.png", "eye_off-24-white.png"}
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
                            "favorites": FAVORITES, "current": CURRENT, "filter_titles": FILTER_TITLES,
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
