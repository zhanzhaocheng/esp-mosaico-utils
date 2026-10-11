#!/usr/bin/env python3
"""Build the Vibe Mode 0.3 design: layout data, mockups and layout checks.

Every page state is described once with GSP 1.4.0 primitives (layer content as
containers, labels, buttons, images, a progress bar and the native keyboard).
The same data produces ``layout.json`` (the source for the Phase B scene),
the PNG mockups and the clickable prototype (``build_prototype.py``).

Mockups are approximate design renders made with Pillow and the subset fonts;
they are not GSP simulator or device screenshots. Requires Pillow.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DESIGN = Path(__file__).resolve().parents[1]
W = H = 480
M = 16  # outer margin

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

TOKENS = {
    "colors": {"background": BG, "card": CARD, "raised": RAISED, "tile": TILE, "outline": LINE,
               "divider": DIVIDER, "text": TEXT, "text_secondary": TEXT2, "text_tertiary": TEXT3,
               "accent": ACCENT, "primary_bg": PRIMARY_BG, "primary_fg": PRIMARY_FG},
    "fonts": FONTS,
    "line_height_em": LINE_EM,
    "radius": {"card": 20, "row": 18, "key": 18, "pill": "h/2"},
    "margin": M,
    "min_touch": 48,
    "motion": {"page_slide_px": 48, "page_slide_ms": 160, "easing": "ease_out"},
    "keyboard": {"bg_color": BG, "fg_color": TEXT, "key_color": TILE, "function_color": RAISED,
                 "ok_color": ACCENT, "ok_text_color": WHITE, "key_radius": 10,
                 "font_size": 22, "function_font_size": 16},
}


def line_h(font: str, size: int, lines: int = 1) -> int:
    return math.ceil(LINE_EM[font] * size * lines)


# --------------------------------------------------------------------------
# Primitive constructors (GSP widget vocabulary)
# --------------------------------------------------------------------------
def container(x, y, w, h, bg=None, radius=0, border=None, bw=0, name=None, opacity=255, role=None):
    return {"type": "container", "x": x, "y": y, "w": w, "h": h, "bg": bg, "radius": radius,
            "border": border, "border_width": bw, "name": name, "opacity": opacity, "role": role}


# Single-line labels showing app names, SSIDs or versions truncate with an
# ellipsis (GSP `overflow: "ellipsis"`) instead of clipping mid-glyph.
ELLIPSIS = {"apps_name", "apps_detail", "detail_name", "detail_meta", "switch_name", "switch_detail",
            "progress_detail", "result_caption", "wifi_connection", "wifi_detail", "networks_title",
            "device_wifi", "password_subtitle", "ai_toast_text", "launch_title", "running_title"}


def label(x, y, w, text, font="sans", size=16, color=TEXT, align="left", h=None, name=None,
          bg=None, radius=0, dynamic=False):
    lines = text.count("\n") + 1
    return {"type": "label", "x": x, "y": y, "w": w, "h": h or line_h(font, size, lines),
            "text": text, "font": font, "size": size, "color": color, "align": align,
            "name": name, "bg": bg, "radius": radius, "dynamic": dynamic,
            "overflow": "ellipsis" if name in ELLIPSIS else "clip"}


def button(x, y, w, h, text="", font="medium", size=17, color=TEXT, bg=RAISED, radius=None,
           border=None, bw=0, icon=None, action=None, name=None, icon_gap=10):
    obj = {"type": "button", "x": x, "y": y, "w": w, "h": h, "text": text, "font": font,
           "size": size, "color": color, "bg": bg, "radius": h // 2 if radius is None else radius,
           "border": border, "border_width": bw, "action": action, "name": name, "icon": None}
    if icon:
        # Icon sits left of the centered text, or centered when there is no text.
        size_px = int(Path(icon).stem.split("-")[1])
        if text:
            tw = text_width(text, font, size)
            total = size_px + icon_gap + tw
            ix = x + (w - total) / 2
            obj["text_offset"] = (size_px + icon_gap) / 2
        else:
            ix = x + (w - size_px) / 2
        obj["icon"] = {"image": icon, "x": round(ix), "y": round(y + (h - size_px) / 2),
                       "w": size_px, "h": size_px}
    return obj


def image(x, y, path, name=None, w=None, h=None):
    with Image.open(DESIGN / path) as im:
        iw, ih = im.size
    return {"type": "image", "x": x, "y": y, "w": w or iw, "h": h or ih, "image": path, "name": name}


def icon(x, y, name, size, color, obj_name=None):
    return image(x, y, f"assets/icons/{name}-{size}-{color}.png", name=obj_name)


def progress(x, y, w, h, value, name="progress"):
    return {"type": "progress", "x": x, "y": y, "w": w, "h": h, "value": value, "bg": TILE,
            "fg": ACCENT, "radius": h // 2, "name": name}


def keyboard(y=231):
    return {"type": "keyboard", "x": 0, "y": y, "w": W, "h": 233, "name": "password_keyboard",
            **TOKENS["keyboard"]}


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


# --------------------------------------------------------------------------
# Shared building blocks
# --------------------------------------------------------------------------
def circle_button(x, y, icon_name, action, name, size=48, icon_size=22):
    return button(x, y, size, size, bg=BG, border=LINE, bw=2,
                  icon=f"assets/icons/{icon_name}-{icon_size}-white.png", action=action, name=name)


def header(title, subtitle, back="back", help_topic="topics", page=None):
    objs = []
    if back:
        objs.append(circle_button(M, 16, "back", back, f"button_back_{page}"))
    objs.append(label(80, 18, 300, title, "dot", 32, TEXT, name=f"{page}_title"))
    objs.append(label(80, 54, 320, subtitle, "sans", 15, TEXT2, name=f"{page}_subtitle",
                      dynamic=True))
    if help_topic:
        objs.append(circle_button(W - M - 48, 16, "help", f"help:{help_topic}", f"button_help_{page}"))
    return objs


def primary(x, y, w, text, action, name, icon_name=None, h=56):
    return button(x, y, w, h, text, "medium", 18, PRIMARY_FG, PRIMARY_BG,
                  icon=f"assets/icons/{icon_name}-20-black.png" if icon_name else None,
                  action=action, name=name)


def secondary(x, y, w, text, action, name, icon_path=None, h=56, color=TEXT):
    return button(x, y, w, h, text, "medium", 17, color, BG, border=LINE, bw=2, icon=icon_path,
                  action=action, name=name)


def tile(x, y, size, initial, radius, dot_size, name=None, color=TEXT, bg=TILE):
    th = line_h("dot", dot_size)
    return [container(x, y, size, size, bg, radius, name=f"{name}_tile" if name else None),
            label(x, y + (size - th) // 2 + round(dot_size * 0.05), size, initial, "dot", dot_size,
                  color, "center", name=f"{name}_initial" if name else None, dynamic=True)]


# --------------------------------------------------------------------------
# Sample content (illustrative only)
# --------------------------------------------------------------------------
APPS = [
    {"id": "100001", "name": "Pixel Pet", "version": "1.2.0", "size": "1.8 MB", "official": True, "current": True},
    {"id": "100002", "name": "Weather Station", "version": "2.0.1", "size": "2.4 MB", "official": True},
    {"id": "100005", "name": "Voice Notes", "version": "0.9.0", "size": "3.1 MB", "official": True},
    {"id": "238114", "name": "Retro Snake", "version": "1.0.3", "size": "0.9 MB", "official": False},
    {"id": "507219", "name": "Lo-fi Clock", "version": "1.1.0", "size": "1.2 MB", "official": False},
]
NETWORKS = [
    ("Studio-5G", "Secured · Strong signal"),
    ("Maker Lab", "Secured · Good signal"),
    ("Espressif-Guest", "Open · Good signal"),
    ("Home-2.4G", "Secured · Weak signal"),
]
TOKEN = "3f9a1c07e2b84d6a95c1f0e7d2a4b8c6" + "0d5e9f2a7c3b1e8d4f6a0c9b2e7d5a13"


# --------------------------------------------------------------------------
# Rows (list templates). Apps: 66 px card + 8 px gap; networks: 60 + 8.
# Row objects carry the list viewport as "clip", exactly like a GSP list.
# --------------------------------------------------------------------------
APP_ITEM_H = 74
NET_ITEM_H = 68


def clipped(objs, viewport, row_of=None):
    for obj in objs:
        if viewport:
            obj["clip"] = list(viewport)
        if row_of:
            obj["row_of"] = row_of
    return objs


def app_row(x, y, app, viewport):
    objs = [container(x, y, 448, 66, CARD, 18, role="row")]
    objs += tile(x + 11, y + 11, 44, app["name"][0].upper(), 13, 26, name="apps")
    objs.append(label(x + 68, y + 10, 250, app["name"], "medium", 19, TEXT, name="apps_name"))
    objs.append(label(x + 68, y + 37, 250, f"ID {app['id']} · v{app['version']}", "sans", 14, TEXT2,
                      name="apps_detail"))
    objs.append(label(x + 318, y + 12, 90, "● CURRENT" if app.get("current") else " ", "medium", 13,
                      ACCENT, "right", name="apps_badge_current"))
    objs.append(label(x + 318, y + 38, 90, "OFFICIAL" if app["official"] else " ", "medium", 12,
                      TEXT2, "right", name="apps_badge_official"))
    objs.append(icon(x + 418, y + 24, "chevron", 18, "dim"))
    return clipped(objs, viewport, "apps")


def network_row(x, y, ssid, detail, viewport):
    return clipped([container(x, y, 448, 60, CARD, 16, role="row"),
                    label(x + 18, y + 8, 360, ssid, "medium", 18, TEXT, name="networks_title"),
                    label(x + 18, y + 34, 360, detail, "sans", 13, TEXT2, name="networks_detail"),
                    icon(x + 414, y + 21, "chevron", 18, "dim")], viewport, "networks")


def ai_cue(active=False):
    """Light cue directly below the physical AI key (assumed top center)."""
    return container(W // 2 - 18, 4, 36, 4, ACCENT if active else LINE, 2, name="ai_cue")


def ai_toast(text):
    """Transient banner (~1.5 s) that covers the top row after an AI key press."""
    return [container(M, 14, 448, 48, RAISED, 24, border=LINE, bw=2, name="ai_toast"),
            label(M, 14 + (48 - line_h("medium", 16)) // 2, 448, text, "medium", 16, TEXT,
                  "center", name="ai_toast_text", dynamic=True)]


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------
def home(state="apps", agent="usb", count=None, apps=APPS, preset=None, wifi_on=True):
    objs = []
    # Status row: wordmark, then Wi-Fi, help and device buttons.
    objs.append(container(M, 31, 10, 10, ACCENT, 5))
    objs.append(label(34, 26, 140, "VIBE MODE", "medium", 15, TEXT2))
    objs.append(button(316, 16, 44, 44, bg=BG, border=LINE, bw=2,
                       icon="assets/icons/wifi-18-white.png" if wifi_on else "assets/icons/wifi_off-18-grey.png",
                       action="go:wifi", name="button_wifi"))
    objs.append(circle_button(368, 16, "help", "help:topics", "button_help_home", size=44))
    objs.append(circle_button(W - M - 44, 16, "settings", "go:device", "button_device", size=44))
    # Title row.
    n = len(apps) if count is None else count
    objs.append(label(M, 76, 300, "MY APPS", "dot", 40, TEXT))
    objs.append(label(W - M - 120, 76, 120, f"{n:02d}", "dot", 40, ACCENT, "right",
                      name="app_count", dynamic=True))
    # Status line: agent link takes priority, then preset progress, then idle hint.
    if agent:
        dot_color, status = ACCENT, "Agent connected · USB" if agent == "usb" else "Agent connected · Wi-Fi"
    elif preset:
        dot_color, status = ACCENT, f"Preparing apps · {preset[0]} of {preset[1]}"
    else:
        dot_color, status = TEXT3, "Ready for your AI agent · plug in USB"
    # GSP colors are static per object: two dots, one visible (visibility binds).
    live = dot_color == ACCENT
    objs.append(container(M, 129, 8, 8, ACCENT, 4, name="status_dot_live") if live else
                container(M, 129, 8, 8, TEXT3, 4, name="status_dot_idle"))
    objs.append(label(30, 122, 420, status, "sans", 15, TEXT2, name="home_status", dynamic=True))
    if state == "apps":
        viewport = (M, 152, 448, 240)
        objs.append({"type": "list_viewport", "x": M, "y": 152, "w": 448, "h": 240, "name": "apps",
                     "item_height": APP_ITEM_H, "row_template": "apps_row"})
        for i, app in enumerate(apps[:4]):
            objs += app_row(M, 152 + i * APP_ITEM_H, app, viewport)
    elif state == "empty":
        objs.append(image(212, 178, "assets/icons/empty-56-grey.png"))
        objs.append(label(M, 250, 448, "No apps yet", "medium", 22, TEXT, "center"))
        objs.append(label(40, 288, 400, "Add an app with its ID, or ask your\nAI agent to build one for you.",
                          "sans", 15, TEXT2, "center"))
    objs.append(button(M, 404, 448, 56, "Add app", "medium", 18, PRIMARY_FG, PRIMARY_BG,
                       icon="assets/icons/plus-22-black.png", action="go:add", name="button_add"))
    objs.append(ai_cue())
    return objs


def quick_switch(index=1, apps=APPS, hold=35):
    objs = [o for o in home() if o.get("name") != "ai_cue"]
    objs.append(container(0, 0, W, H, BG, 0, opacity=232, role="scrim"))
    objs.append(container(40, 60, 400, 360, CARD, 28, border=LINE, bw=2, name="switch_card"))
    objs.append(label(64, 82, 200, "QUICK SWITCH", "medium", 13, TEXT2))
    objs.append(label(296, 78, 120, f"{index + 1}/{len(apps)}", "dot", 22, TEXT2, "right",
                      name="switch_position", dynamic=True))
    app = apps[index]
    objs += tile(180, 114, 120, app["name"][0].upper(), 34, 68, name="switch")
    objs.append(label(56, 250, 368, app["name"], "medium", 24, TEXT, "center", name="switch_name",
                      dynamic=True))
    objs.append(label(56, 284, 368, f"ID {app['id']} · v{app['version']}", "sans", 14, TEXT2, "center",
                      name="switch_detail", dynamic=True))
    objs.append(progress(64, 322, 352, 4, hold, name="switch_hold"))
    objs.append(container(64, 346, 352, 1, DIVIDER))
    for i, (key, text) in enumerate((("AI ×2", "Next"), ("Hold AI", "Open"), ("AI", "Close"))):
        x = 64 + i * 120
        objs.append(label(x, 362, 112, key, "medium", 13, TEXT, "center"))
        objs.append(label(x, 382, 112, text, "sans", 13, TEXT2, "center"))
    objs.append(ai_cue(True))
    return objs


def add(digits="", status="Enter the app ID", error=""):
    objs = header("ADD APP", "Download any app by its ID", page="add", help_topic="ids")
    objs.append(container(M, 88, 192, 192, WHITE, 20))
    objs.append(image(38, 110, "assets/qr/ideas-148.png", name="ideas_qr"))
    objs.append(icon(M, 296, "scan", 20, "grey"))
    objs.append(label(44, 294, 164, "Scan to browse", "medium", 16, TEXT))
    objs.append(label(M, 322, 192, "mosaico-ideas.espressif.com", "sans", 12, TEXT2))
    objs.append(label(M, 352, 24, "1", "dot", 24, ACCENT))
    objs.append(label(44, 354, 164, "Pick an app on\nyour phone", "sans", 14, TEXT2))
    objs.append(label(M, 404, 24, "2", "dot", 24, ACCENT))
    objs.append(label(44, 406, 164, "Type its ID on\nthe keypad", "sans", 14, TEXT2))
    # ID display.
    objs.append(container(224, 88, 240, 88, CARD, 20))
    # Up to 8 digits use the large face; longer IDs switch to the compact label
    # (the other label holds a blank glyph, as the 0.2 pairing code does).
    shown = digits + "·" * max(0, 6 - len(digits)) if len(digits) <= 8 else " "
    objs.append(label(232, 102, 224, shown, "dot", 40, TEXT, "center", name="id_digits", dynamic=True))
    objs.append(label(232, 111, 224, digits if len(digits) > 8 else " ", "dot", 22, TEXT, "center",
                      name="id_digits_compact", dynamic=True))
    objs.append(label(232, 150, 224, " " if error else status, "sans", 13, TEXT2, "center",
                      name="id_status", dynamic=True))
    objs.append(label(232, 150, 224, error or " ", "sans", 13, ACCENT, "center",
                      name="id_error", dynamic=True))
    # Keypad: 3 x 4 keys of 72 x 60.
    keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "del", "0", "go"]
    for i, key in enumerate(keys):
        x, y = 224 + (i % 3) * 84, 188 + (i // 3) * 68
        if key == "del":
            objs.append(button(x, y, 72, 60, bg=BG, border=LINE, bw=2, radius=18,
                               icon="assets/icons/backspace-26-white.png", action="key:del",
                               name="key_del"))
        elif key == "go":
            objs.append(button(x, y, 72, 60, bg=ACCENT, radius=18, icon="assets/icons/arrow-26-white.png",
                               action="key:go", name="key_go"))
        else:
            objs.append(button(x, y, 72, 60, key, "dot", 30, TEXT, RAISED, radius=18,
                               action=f"key:{key}", name=f"key_{key}"))
    return objs


def detail(mode="current", confirm=False):
    app = dict(APPS[0] if mode == "current" else APPS[1])
    remote = mode in ("remote_new", "remote_update")
    if mode == "remote_new":
        app = {"id": "238114", "name": "Retro Snake", "version": "1.0.3", "size": "0.9 MB", "official": False}
    if mode == "remote_update":
        app = dict(APPS[2], version="1.0.0")
    subtitle = "From the app store" if remote else "Saved on this device"
    objs = header("APP", subtitle, page="detail", help_topic="ids")
    objs += tile(M, 88, 96, app["name"][0].upper(), 28, 56, name="detail")
    objs.append(label(128, 92, 336, app["name"], "medium", 24, TEXT, name="detail_name", dynamic=True))
    objs.append(label(128, 128, 336, app["id"], "dot", 28, ACCENT, name="detail_id", dynamic=True))
    objs.append(label(128, 164, 336, f"v{app['version']} · {app['size']}", "sans", 15, TEXT2,
                      name="detail_meta", dynamic=True))
    objs.append(container(M, 200, 448, 112, CARD, 20))
    objs.append(label(32, 218, 150, "Source", "sans", 15, TEXT2))
    objs.append(label(200, 218, 248, "Official" if app["official"] else "Community", "medium", 15, TEXT,
                      "right", name="detail_source", dynamic=True))
    objs.append(container(32, 256, 416, 1, DIVIDER))
    status = {"current": "Current app", "local": "Saved · not running",
              "remote_new": "Not on this device", "remote_update": "Update · v0.9.0 → v1.0.0"}[mode]
    objs.append(label(32, 274, 150, "Status", "sans", 15, TEXT2))
    accent = mode in ("current", "remote_update")
    objs.append(label(200, 274, 248, " " if accent else status, "medium", 15, TEXT, "right",
                      name="detail_status", dynamic=True))
    objs.append(label(200, 274, 248, status if accent else " ", "medium", 15, ACCENT, "right",
                      name="detail_status_accent", dynamic=True))
    if remote:
        objs.append(primary(M, 328, 448, "Download & run", "store:run", "button_primary", "download"))
        objs.append(secondary(M, 396, 216, "Download only", "store:keep", "button_secondary",
                              "assets/icons/download-20-white.png"))
        objs.append(secondary(248, 396, 216, "Cancel", "back", "button_tertiary"))
    else:
        text = "Open" if mode == "current" else "Switch to this app"
        objs.append(primary(M, 328, 448, text, "app:run", "button_primary", "play"))
        objs.append(secondary(M, 396, 216, "Update", "app:update", "button_secondary",
                              "assets/icons/refresh-20-white.png"))
        if confirm:
            objs.append(button(248, 396, 216, 56, "Tap again to delete", "medium", 15, WHITE, ACCENT,
                               action="app:delete", name="button_delete_confirm"))
        else:
            objs.append(secondary(248, 396, 216, "Delete", "app:delete_ask", "button_tertiary",
                                  "assets/icons/trash-20-orange.png", color=ACCENT))
    return objs


def progress_page(kind="agent"):
    spec = {
        "agent": ("FROM YOUR AI AGENT · USB", "Installing your app", "hello_world · v0.2.1",
                  42, "1.20 MB of 2.85 MB", "236 KB/s", "Step 1 of 2 · Receiving", False),
        "download": ("FROM THE APP STORE", "Downloading", "Retro Snake · v1.0.3",
                     67, "0.61 MB of 0.92 MB", "512 KB/s", "File 2 of 3", True),
        "install": ("FROM YOUR LIBRARY", "Switching apps", "Weather Station · v2.0.1",
                    88, "2.11 MB of 2.40 MB", "1.6 MB/s", "Step 2 of 2 · Writing", False),
    }[kind]
    caption, title, detail_text, pct, size_text, rate, step, cancel = spec
    objs = [label(M, 30, 448, caption, "medium", 13, ACCENT, name="progress_caption", dynamic=True),
            label(M, 52, 448, title, "medium", 28, TEXT, name="progress_title", dynamic=True),
            label(M, 92, 448, detail_text, "sans", 15, TEXT2, name="progress_detail", dynamic=True),
            label(M, 126, 448, f"{pct}%", "dot", 112, TEXT, "center", name="progress_percent", dynamic=True),
            progress(M, 252, 448, 8, pct),
            label(M, 274, 280, size_text, "sans", 15, TEXT2, name="progress_bytes", dynamic=True),
            label(296, 274, 168, rate, "medium", 15, TEXT, "right", name="progress_rate", dynamic=True),
            label(M, 302, 448, step, "sans", 14, TEXT3, name="progress_step", dynamic=True)]
    objs.append(container(M, 352, 448, 1, DIVIDER))
    objs.append(icon(M + 2, 368, "power", 20, "orange"))
    objs.append(label(46, 368, 300, "Keep the device powered", "sans", 15, TEXT2))
    if cancel:
        objs.append(secondary(M, 404, 448, "Cancel download", "store:cancel", "button_cancel"))
    else:
        objs.append(label(M, 420, 448, "The device restarts into the app when done", "sans", 14, TEXT3,
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
    ("start", "flag", "Getting started", "Enter Vibe Mode, use the AI key"),
    ("agent", "agent", "Build with your AI agent", "Deploy apps from your computer"),
    ("ids", "hash", "App IDs & sharing", "Find, share and download apps"),
    ("fix", "support", "Troubleshooting", "Wi-Fi, failed installs, recovery"),
]
HELP_TEXT = {
    "start": ("Getting started", "flag", "mosaico.espressif.com\n/vibe/start",
              ["Hold AI, then double-press\npower to come back here.",
               "Press AI to go back.\nDouble-press AI to switch.",
               "Tap an app, then Open\nor Switch to run it."]),
    "agent": ("Build with your AI agent", "agent", "mosaico.espressif.com\n/vibe/agent",
              ["Plug in USB and ask your\nagent to deploy your app.",
               "This screen shows every\nstep while it installs.",
               "If it fails, your last app\nstays safe."]),
    "ids": ("App IDs & sharing", "hash", "mosaico.espressif.com\n/vibe/ids",
            ["Every app has a number ID,\nusually 6 digits.",
             "Share an app by telling\nfriends its ID.",
             "The same ID always gets\nthe newest version."]),
    "fix": ("Troubleshooting", "support", "mosaico.espressif.com\n/vibe/fix",
            ["Check Wi-Fi and try\nagain.",
             "Keep the device powered\nwhile installing.",
             "Still stuck? Scan for the\nrecovery guide."]),
}


def help_topics():
    objs = header("HELP", "Scan a code to read the guide", page="help", help_topic=None)
    for i, (key, icon_name, title, desc) in enumerate(HELP_TOPICS):
        y = 88 + i * 76
        objs.append(button(M, y, 448, 68, bg=CARD, radius=18, action=f"help:{key}", name=f"topic_{key}"))
        objs.append(icon(34, y + 22, icon_name, 24, "white"))
        objs.append(label(72, y + 11, 330, title, "medium", 17, TEXT))
        objs.append(label(72, y + 38, 330, desc, "sans", 14, TEXT2))
        objs.append(icon(418, y + 25, "chevron", 18, "dim"))
    objs.append(secondary(M, 404, 448, "Replay guide", "guide:1", "button_replay",
                          "assets/icons/replay-20-white.png"))
    return objs


def help_topic(key="start"):
    title, icon_name, url, points = HELP_TEXT[key]
    objs = header("HELP", "Scan for the full guide", back="back", page="topic", help_topic=None)
    objs.append(container(M, 88, 192, 192, WHITE, 20))
    objs.append(image(38, 110, f"assets/qr/help-{key}-148.png", name="topic_qr"))
    objs.append(label(M, 292, 192, url, "sans", 12, TEXT2, "center", name="topic_url", dynamic=True))
    objs.append(icon(224, 92, icon_name, 24, "white", "topic_icon"))
    objs.append(label(224, 124, 240, title.replace(" your ", "\nyour ") if len(title) > 20 else title,
                      "medium", 18, TEXT, name="topic_title", dynamic=True))
    y = 124 + line_h("medium", 18, 2 if len(title) > 20 else 1) + 14
    for i, point in enumerate(points):
        objs.append(container(224, y + 8, 6, 6, ACCENT, 3))
        objs.append(label(238, y, 226, point, "sans", 14, TEXT2, name=f"topic_point_{i}", dynamic=True))
        y += line_h("sans", 14, point.count("\n") + 1) + 12
    objs.append(secondary(M, 404, 448, "All help topics", "help:topics", "button_topics"))
    return objs


def wifi(pending=False):
    sub = "Connect to continue your download" if pending else "Connect to download apps"
    objs = header("WI-FI", sub, page="wifi", help_topic="fix")
    objs.append(container(M, 88, 448, 72, CARD, 20))
    objs.append(icon(34, 113, "wifi", 22, "grey"))
    objs.append(label(68, 98, 280, "Studio-5G", "medium", 19, TEXT, name="wifi_connection", dynamic=True))
    objs.append(label(68, 125, 280, "Connected · 192.168.1.20", "sans", 14, TEXT2, name="wifi_detail",
                      dynamic=True))
    objs.append(secondary(360, 102, 92, "Forget", "wifi:forget", "button_forget", h=44))
    objs[-1]["size"] = 15
    objs.append(label(M, 186, 300, "NETWORKS · 4", "medium", 13, TEXT2, name="wifi_scan", dynamic=True))
    objs.append(button(368, 172, 96, 44, "Scan", "medium", 14, TEXT, BG, border=LINE, bw=2,
                       icon="assets/icons/refresh-20-white.png", action="wifi:scan", name="button_scan",
                       icon_gap=6))
    viewport = (M, 228, 448, 244)
    objs.append({"type": "list_viewport", "x": M, "y": 228, "w": 448, "h": 244, "name": "networks",
                 "item_height": NET_ITEM_H, "row_template": "networks_row"})
    for i, (ssid, info) in enumerate(NETWORKS[:4]):
        objs += network_row(M, 228 + i * NET_ITEM_H, ssid, info, viewport)
    return objs


def password(masked=True, error=""):
    objs = header("PASSWORD", "Studio-5G", page="password", help_topic=None)
    objs.append(container(M, 88, 448, 64, CARD, 18))
    objs.append(label(34, 108, 340, "••••••••••" if masked else "makers2026", "medium", 20, TEXT,
                      name="password_display", dynamic=True))
    objs.append(button(392, 96, 56, 48, bg=RAISED, radius=16,
                       icon=f"assets/icons/{'eye' if masked else 'eye_off'}-24-white.png",
                       action="password:toggle", name="button_toggle_password"))
    objs.append(label(M, 166, 448, error or " ", "sans", 14, ACCENT, name="password_error", dynamic=True))
    objs.append(label(M, 196, 448, "Up to 64 characters", "sans", 13, TEXT3))
    objs.append(keyboard())
    return objs


def device():
    objs = header("DEVICE", "Vibe Mode 0.3.0 · ESP32-S31", page="device", help_topic="fix")
    objs.append(container(M, 88, 448, 224, CARD, 20))
    rows = [("wifi", "Wi-Fi", "Studio-5G", True, "device_wifi"),
            ("chip", "Vibe Mode", "0.3.0", False, "device_version"),
            ("id", "MAC address", "30:ED:A0:F4:60:56", False, "device_mac"),
            ("storage", "App storage", "5 apps · 9.4 MB used", False, "device_storage")]
    for i, (ic, name, value, link, value_name) in enumerate(rows):
        y = 88 + i * 56
        if link:
            objs.append(button(M, y, 448, 56, bg=CARD, radius=20, action="go:wifi", name="button_device_wifi"))
        if i:
            objs.append(container(66, y, 382, 1, DIVIDER))
        objs.append(icon(32, y + 17, ic, 22, "grey"))
        objs.append(label(66, y + 18, 150, name, "medium", 15, TEXT))
        objs.append(label(206, y + 18, 214 if link else 242, value, "sans", 15, TEXT2, "right",
                          name=value_name, dynamic=True))
        if link:
            objs.append(icon(428, y + 19, "chevron", 18, "dim"))
    objs.append(container(M, 324, 448, 108, CARD, 20))
    objs.append(icon(32, 338, "terminal", 22, "grey"))
    objs.append(label(66, 340, 200, "DEVELOPER", "medium", 13, TEXT2))
    objs.append(label(32, 368, 416, "Wi-Fi link  192.168.1.20:7777", "sans", 14, TEXT,
                      name="device_endpoint", dynamic=True))
    objs.append(label(32, 390, 416, f"Token  {TOKEN[:32]}\n             {TOKEN[32:]}", "sans", 12, TEXT3,
                      name="device_token", dynamic=True))
    objs.append(label(M, 444, 448, "App downloads send this device's MAC and version for statistics.",
                      "sans", 12, TEXT3, "center"))
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
        objs.append(image(M, 120, "assets/icons/guide-device-200.png"))
        # Step numbers sit next to the highlighted keys in the drawing.
        objs.append(label(M + 128, 110, 20, "1", "dot", 20, ACCENT))
        objs.append(label(M + 164, 294, 20, "2", "dot", 20, ACCENT))
        steps = (("1", "Hold the AI key", "On the top edge. Keep\nholding it."),
                 ("2", "Double-press power", "Bottom right. The device\nrestarts."),
                 ("3", "Release AI", "When the Vibe Mode\nscreen appears."))
        for i, (num, head, sub) in enumerate(steps):
            y = 124 + i * 76
            objs.append(label(236, y, 28, num, "dot", 28, ACCENT))
            objs.append(label(268, y + 2, 196, head, "medium", 16, TEXT))
            objs.append(label(268, y + 26, 196, sub, "sans", 13, TEXT2))
    elif step == 3:
        objs.append(label(M, 76, 448, "Get new apps", "medium", 24, TEXT))
        objs.append(container(48, 124, 136, 136, WHITE, 18))
        objs.append(image(56, 132, "assets/qr/ideas-148.png", w=120, h=120))
        objs.append(icon(212, 181, "arrow", 26, "white"))
        objs.append(container(264, 140, 168, 104, CARD, 20))
        objs.append(label(264, 172, 168, "100001", "dot", 34, TEXT, "center"))
        objs.append(label(M, 288, 448, "Browse apps on your phone, then type the\n"
                          "app ID here. Share an app by sharing its ID.", "sans", 15, TEXT2, "center"))
    else:
        objs.append(label(M, 76, 448, "Your AI key", "medium", 24, TEXT))
        rows = [("AI", "Go back"), ("AI ×2", "Switch apps"), ("Hold AI", "Open the selected app")]
        for i, (key, text) in enumerate(rows):
            y = 124 + i * 60
            objs.append(button(M, y, 112, 44, key, "medium", 15, TEXT, RAISED, name=f"guide_key_{i}"))
            objs.append(label(144, y + 11, 320, text, "sans", 17, TEXT))
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


def launching(app=APPS[0]):
    """Restart into an app that is already installed: no Flash write."""
    objs = tile(180, 120, 120, app["name"][0].upper(), 34, 68, name="launch")
    objs.append(label(M, 262, 448, f"Opening {app['name']}", "medium", 24, TEXT, "center",
                      name="launch_title", dynamic=True))
    objs.append(label(M, 298, 448, "Restarting into your app…", "sans", 15, TEXT2, "center"))
    return objs


def app_running(app=APPS[0]):
    """Prototype only: stands in for the user's app after Vibe Mode hands over."""
    objs = [container(0, 0, W, H, "#0A0A0A", 0)]
    objs += tile(180, 96, 120, app["name"][0].upper(), 34, 68, name="running", bg=RAISED)
    objs.append(label(M, 236, 448, app["name"], "medium", 26, TEXT, "center", name="running_title",
                      dynamic=True))
    objs.append(label(M, 274, 448, "Your app is running", "sans", 15, TEXT2, "center"))
    objs.append(label(40, 330, 400, "To come back: hold AI, then double-press power.", "sans", 14,
                      TEXT3, "center"))
    objs.append(secondary(96, 380, 288, "Simulate the gesture", "proto:return", "button_return"))
    return objs


def prototype_extras():
    extras = [{"id": f"help-topic-{key}", "page": "help_topic", "objects": help_topic(key)}
              for key in HELP_TEXT]
    extras.append({"id": "wifi-pending", "page": "wifi", "objects": wifi(True)})
    extras.append({"id": "launching", "page": "launching", "objects": launching()})
    extras.append({"id": "app-running", "page": "app_running", "objects": app_running()})
    for extra in extras:
        if extra["page"] not in ("app_running",):
            extra["objects"].append(ai_cue())
    templates = {"apps_row": app_row(0, 0, APPS[0], None),
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
    add_state("home", "home", "Home · agent connected", home())
    add_state("home-empty", "home", "Home · empty, waiting for an agent",
              home("empty", agent=None, count=0, wifi_on=False))
    add_state("home-preset", "home", "Home · preparing preset apps",
              home(agent=None, preset=(2, 5), apps=APPS[:2]))
    hint = [o for o in home(agent=None) if o.get("name") != "ai_cue"]
    add_state("home-ai-hint", "home", "Home · AI pressed (hint toast)",
              hint + [ai_cue(True)] + ai_toast("Double-press AI to switch apps"))
    add_state("quick-switch", "home", "Quick switch (AI ×2)", quick_switch())
    add_state("add", "add", "Add app · empty", add())
    add_state("add-typing", "add", "Add app · typing", add("2381", "Tap → to look it up"))
    add_state("add-error", "add", "Add app · not found", add("404040", error="No app with this ID"))
    add_state("detail-current", "detail", "Detail · current app", detail("current"))
    add_state("detail-local", "detail", "Detail · saved app", detail("local"))
    add_state("detail-delete", "detail", "Detail · delete confirmation", detail("local", True))
    add_state("detail-remote", "detail", "Detail · found in the store", detail("remote_new"))
    add_state("detail-update", "detail", "Detail · update available", detail("remote_update"))
    add_state("progress-agent", "progress", "Progress · from the AI agent", progress_page("agent"))
    add_state("progress-download", "progress", "Progress · store download", progress_page("download"))
    add_state("progress-install", "progress", "Progress · switching apps", progress_page("install"))
    add_state("result-installed", "result", "Result · installed", result("installed"))
    add_state("result-saved", "result", "Result · saved", result("saved"))
    add_state("result-failed", "result", "Result · failed", result("failed"))
    add_state("help", "help", "Help topics", help_topics())
    add_state("help-topic", "help_topic", "Help topic with QR", help_topic("start"))
    add_state("wifi", "wifi", "Wi-Fi", wifi())
    add_state("password", "password", "Wi-Fi password", password())
    add_state("device", "device", "Device", device())
    return s


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
def rgb(color: str):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def ellipsize(text: str, f, width: float) -> str:
    if f.getlength(text) <= width:
        return text
    while text and f.getlength(text + "…") > width:
        text = text[:-1]
    return text.rstrip() + "…"


def draw_text(img, draw, obj, text, box, color, align="left", offset=0.0):
    f = font_for(obj["font"], obj["size"])
    x, y, w, h = box
    lh = LINE_EM[obj["font"]] * obj["size"]
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


def draw_keyboard(img, draw, kb):
    x0, y0 = kb["x"], kb["y"]
    f = font_for("sans", kb["font_size"])
    ff = font_for("medium", kb["function_font_size"])
    rows = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]
    key_h, pitch = 50, 59
    for r, keys in enumerate(rows):
        n = len(keys)
        kw = 42
        gap = 5.6
        width = n * kw + (n - 1) * gap
        start = (W - width) / 2 if r < 2 else 72
        for i, ch in enumerate(keys):
            kx = start + i * (kw + gap)
            ky = y0 + 4 + r * pitch
            draw.rounded_rectangle((kx, ky, kx + kw, ky + key_h), kb["key_radius"], fill=rgb(kb["key_color"]))
            tw = f.getlength(ch)
            draw.text((kx + (kw - tw) / 2, ky + (key_h - 1.25 * kb["font_size"]) / 2), ch, font=f,
                      fill=rgb(kb["fg_color"]))
    # Function keys.
    ky = y0 + 4 + 2 * pitch
    for kx, kw, label_text, color in ((8, 56, "⇧", kb["function_color"]), (416, 56, "⌫", kb["function_color"])):
        draw.rounded_rectangle((kx, ky, kx + kw, ky + key_h), kb["key_radius"], fill=rgb(color))
    for path, kx in (("assets/icons/backspace-26-white.png", 431), ):
        pass
    shift = Image.open(DESIGN / "assets/icons/back-22-white.png").rotate(-90)
    img.paste(shift, (8 + 17, ky + 14), shift)
    bs = Image.open(DESIGN / "assets/icons/backspace-26-white.png")
    img.paste(bs, (416 + 15, ky + 12), bs)
    ky = y0 + 4 + 3 * pitch
    specs = ((8, 88, "123", kb["function_color"], kb["fg_color"]),
             (104, 272, "space", kb["key_color"], kb["fg_color"]),
             (384, 88, "GO", kb["ok_color"], kb["ok_text_color"]))
    for kx, kw, text, color, tcolor in specs:
        draw.rounded_rectangle((kx, ky, kx + kw, ky + key_h), kb["key_radius"], fill=rgb(color))
        tw = ff.getlength(text)
        draw.text((kx + (kw - tw) / 2, ky + (key_h - 1.25 * kb["function_font_size"]) / 2), text, font=ff,
                  fill=rgb(tcolor))


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
    return img


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
def check(states) -> list[str]:
    problems = []
    for st in states:
        for obj in st["objects"]:
            t = obj["type"]
            if t == "list_viewport":
                continue
            x, y, w, h = obj["x"], obj["y"], obj["w"], obj["h"]
            where = f"{st['id']}:{obj.get('name') or t}:{obj.get('text', obj.get('image', ''))!r}"
            if not obj.get("clip") and (x < 0 or y < 0 or x + w > W or y + h > H):
                problems.append(f"{where} outside the screen ({x},{y},{w},{h})")
            if t == "button" and (w < 44 or h < 44):
                problems.append(f"{where} touch target {w}x{h} is below 44x44")
            if t in ("label", "button") and obj.get("text"):
                lines = obj["text"].split("\n")
                need = line_h(obj["font"], obj["size"], len(lines))
                if t == "label" and h < need:
                    problems.append(f"{where} height {h} < line height {need}")
                avail = w - (2 * obj.get("text_offset", 0) + (obj["icon"]["w"] if obj.get("icon") else 0)
                             if t == "button" else 0)
                width = text_width(obj["text"], obj["font"], obj["size"])
                if width > avail and obj.get("overflow") != "ellipsis":
                    problems.append(f"{where} text width {width:.0f} > {avail:.0f}")
    return problems + check_copy()


# Every dynamic string variant from the copy table (README section 8), measured
# against its label. Names and SSIDs ellipsize, so only fixed copy is listed.
COPY = [
    (224, "sans", 13, ["Enter the app ID", "Tap → to look it up", "Looking up 1234567890123456…",
                       "Type an app ID first", "No app with this ID", "This app was removed",
                       "Not available for this device", "Download not allowed",
                       "Store is busy. Try again soon.", "Can't reach the store. Check Wi-Fi.",
                       "Storage unavailable", "Not enough storage"]),
    (420, "sans", 15, ["Ready for your AI agent · plug in USB", "Agent connected · Wi-Fi",
                       "Preparing apps · 12 of 12", "Storage unavailable"]),
    (448, "medium", 16, ["Double-press AI to switch apps", "Double-press AI, then hold to open",
                         "No apps yet. Add one first.", "Download cancelled",
                         "Connect Wi-Fi to check for updates"]),
    (248, "medium", 15, ["Update · v10.12.3 → v10.13.0", "Update available", "Saved · not running",
                         "Not on this device", "Current app"]),
    (250, "sans", 14, ["ID 1234567890123456 · v10.12.3-beta"]),
    (448, "medium", 13, ["FROM YOUR AI AGENT · WI-FI", "FROM YOUR AI AGENT · USB", "FROM THE APP STORE",
                         "FROM YOUR LIBRARY", "FROM USB"]),
    (448, "medium", 28, ["Installing your app", "Downloading", "Switching apps", "Couldn't install the app",
                         "Couldn't download", "Saved to My Apps", "App installed"]),
    (400, "sans", 15, ["The connection dropped. Check Wi-Fi", "Open it any time from My Apps.",
                       "Restarting into your app…"]),
    (448, "sans", 14, ["Use at least 8 characters", "Wrong password. Try again."]),
    (242, "sans", 15, ["24 apps · 312.4 MB used", "30:ED:A0:F4:60:56"]),
    (300, "medium", 13, ["NETWORKS · 16", "SCANNING…"]),
]


def check_copy() -> list[str]:
    problems = []
    for width, font, size, texts in COPY:
        for text in texts:
            w = text_width(text, font, size)
            if w > width:
                problems.append(f"copy {text!r} is {w:.0f} px wide in a {width} px label")
    return problems


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
                style = f"{o['font']} {o['size']}px {o['color']}"
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
    for st in states:
        render(st).save(out / f"{st['id']}.png", optimize=True)
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
        sheet.paste(render(st).resize((cw, ch), Image.LANCZOS), (cx, cy))
        d.rectangle((cx - 1, cy - 1, cx + cw, cy + ch), outline=rgb("#2A2A2A"))
        d.text((cx, cy + ch + 6), st["title"], font=cf, fill=rgb(TEXT2))
    sheet.save(out / "00-overview.png", optimize=True)
    extras, templates = prototype_extras()
    layout = {"schema": "vibe-mode-design/1", "screen": {"w": W, "h": H}, "tokens": TOKENS,
              "states": states, "prototype": {"states": extras, "row_templates": templates,
                                              "row_heights": {"apps": APP_ITEM_H, "networks": NET_ITEM_H}}}
    (DESIGN / "layout.json").write_text(json.dumps(layout, indent=1, ensure_ascii=False) + "\n",
                                        encoding="utf-8")
    (DESIGN / "layout-tables.md").write_text(layout_tables(states), encoding="utf-8")
    problems = check(states)
    for p in problems:
        print("check:", p)
    print(f"{len(states)} states rendered; {len(problems)} layout issues")
    return 1 if problems and "--strict" in sys.argv else 0


if __name__ == "__main__":
    raise SystemExit(main())
