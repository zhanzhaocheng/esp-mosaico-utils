#!/usr/bin/env python3
"""Compile ui/main.json into Vibe View C tables and an asset blob.

Outputs are committed under ui/generated so firmware builds need neither
Pillow nor FreeType and stay byte-for-byte reproducible. Rerun this tool after
editing the scene, its fonts or images; tests compare inputs.sha256.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import zlib

TOOL = Path(__file__).resolve()
RECOVERY = TOOL.parents[1]
DEFAULT_SCENE = RECOVERY / "ui" / "main.json"
DEFAULT_OUT = RECOVERY / "ui" / "generated"

TYPES = {
    "layer": 0, "label": 1, "container": 2, "button": 3, "list": 4,
    "keyboard": 5, "image": 6, "progress": 7, "template": 8,
}
ALIGN = {"left": 0, "center": 1, "right": 2}
FLAG_HIDDEN = 0x01
FLAG_BG = 0x02
NONE = 0xFFFF
NO_INDEX = 0xFF
IMAGE_L1 = 1
IMAGE_A8 = 2
KEYBOARD_FUNCTION_LABELS = ("#+=", "123")
PRINTABLE = "".join(chr(c) for c in range(32, 127))


def rgb565(color):
    value = int(color.lstrip("#"), 16)
    r, g, b = (value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def identifier(name):
    return "".join(c if c.isalnum() else "_" for c in name).upper()


def c_string(text):
    out = []
    for byte in text.encode("utf-8"):
        char = chr(byte)
        if char == "\\":
            out.append("\\\\")
        elif char == '"':
            out.append('\\"')
        elif char == "\n":
            out.append("\\n")
        elif 32 <= byte < 127:
            out.append(char)
        else:
            out.append("\\%03o" % byte)
    return '"' + "".join(out) + '"'


def input_files(scene_path, scene):
    base = scene_path.parent
    files = [TOOL, scene_path, base / scene["font"]]
    for item in scene["objects"]:
        if item["type"] == "image":
            files.append(base / item["image"])
        for key in ("shift_icon", "delete_icon"):
            if item.get(key):
                files.append(base / item[key])
    return files


def input_digest(scene_path):
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256()
    for path in input_files(scene_path, scene):
        digest.update(path.name.encode("utf-8") + b"\0")
        # Normalize line endings so Windows checkouts produce the same digest.
        data = path.read_bytes()
        if path.suffix in (".py", ".json"):
            data = data.replace(b"\r\n", b"\n")
        digest.update(hashlib.sha256(data).digest())
    return digest.hexdigest()


class Scene:
    def __init__(self, path):
        self.path = path
        self.data = json.loads(path.read_text(encoding="utf-8"))
        self.objects = self.data["objects"]
        self.default_size = self.data.get("default_font_size", 20)
        self.strings = []
        self.string_index = {}
        self.binds = []
        self.actions = []
        self.images = []  # (key, path, tint)
        self.glyphs = {}  # font size -> set of code points
        self.templates = []
        self.lists = []
        self.keyboards = []
        self.named = {}
        self._analyze()

    def string(self, text):
        if text not in self.string_index:
            self.string_index[text] = len(self.strings)
            self.strings.append(text)
        return self.string_index[text]

    def bind(self, name):
        if name not in self.binds:
            self.binds.append(name)
        return self.binds.index(name)

    def action(self, name):
        if name not in self.actions:
            self.actions.append(name)
        return self.actions.index(name)

    def image(self, path):
        key = str(path)
        for index, (existing, _) in enumerate(self.images):
            if existing == key:
                return index
        self.images.append((key, path))
        return len(self.images) - 1

    def need(self, size, text):
        self.glyphs.setdefault(size, set(" ")).update(text)

    def template_of(self, index):
        while index >= 0:
            item = self.objects[index]
            if "template" in item:
                return item["template"]
            index = item["parent"]
        return None

    def _analyze(self):
        base = self.path.parent
        for index, item in enumerate(self.objects):
            if "template" in item and item["template"] not in [t["name"] for t in self.templates]:
                self.templates.append({"name": item["template"], "root": index})
            if item.get("name"):
                self.named[item["name"]] = index
        template_names = [t["name"] for t in self.templates]
        for index, item in enumerate(self.objects):
            kind = item["type"]
            size = item.get("font_size", self.default_size)
            if kind in ("label", "button"):
                self.need(size, item.get("text", ""))
                self.need(size, item.get("font_charset", ""))
            if kind == "list":
                self.lists.append(index)
            if kind == "keyboard":
                self.keyboards.append(index)
                self.need(size, PRINTABLE)
                function_size = item.get("function_font_size", size)
                for key in ("shift_label", "delete_label", "ok_label", "symbols_label",
                            "letters_label", "space_label"):
                    self.need(function_size, item.get(key, ""))
                for label in KEYBOARD_FUNCTION_LABELS:
                    self.need(function_size, label)
                for key in ("shift_icon", "delete_icon"):
                    if item.get(key):
                        self.image(base / item[key])
                self.action(item["name"] + "_key")
            if kind == "image":
                self.image(base / item["image"])
            if item.get("bind"):
                self.bind(item["bind"])
            for event in item.get("events", []):
                if event.get("event") == "click" and event.get("action") == "call":
                    self.action(event["target_name"])
            if "template" in item and item.get("callback"):
                self.action(item["callback"])
            if kind == "list" and item["row_template"] not in template_names:
                raise ValueError("list %s uses unknown template %s" % (item["name"], item["row_template"]))
        self.sizes = sorted(self.glyphs)

    def font_index(self, size):
        return self.sizes.index(size)

    def position(self, index):
        """Absolute for scene objects, relative to the root inside templates."""
        item = self.objects[index]
        if "template" in item:
            return 0, 0
        x, y = item["x"], item["y"]
        parent = item["parent"]
        while parent >= 0 and "template" not in self.objects[parent]:
            x += self.objects[parent]["x"]
            y += self.objects[parent]["y"]
            parent = self.objects[parent]["parent"]
        return x, y

    def children(self, index):
        return [i for i, item in enumerate(self.objects) if item["parent"] == index]

    def draw_order(self, roots):
        order, ends = [], {}

        def visit(index):
            order.append(index)
            for child in self.children(index):
                visit(child)
            ends[index] = len(order)

        for root in roots:
            visit(root)
        return order, ends


def render_fonts(scene):
    from PIL import Image, ImageDraw, ImageFont

    fonts = []
    path = scene.path.parent / scene.data["font"]
    for size in scene.sizes:
        font = ImageFont.truetype(str(path), size)
        ascent, descent = font.getmetrics()
        glyphs, bitmap = [], bytearray()
        for codepoint in sorted(ord(c) for c in scene.glyphs[size]):
            char = chr(codepoint)
            left, top, right, bottom = font.getbbox(char)
            advance = int(round(font.getlength(char)))
            width, height = max(0, right - left), max(0, bottom - top)
            offset = len(bitmap)
            if width and height:
                image = Image.new("L", (width, height), 0)
                ImageDraw.Draw(image).text((-left, -top), char, font=font, fill=255)
                pixels = image.load()
                for y in range(height):
                    row = [(pixels[x, y] * 15 + 127) // 255 for x in range(width)]
                    if width % 2:
                        row.append(0)
                    bitmap.extend((row[i] << 4) | row[i + 1] for i in range(0, len(row), 2))
            for value, low, high in ((width, 0, 255), (height, 0, 255), (left, -128, 127),
                                     (top - ascent, -128, 127), (advance, 0, 255)):
                if not low <= value <= high:
                    raise ValueError("glyph U+%04X at %d px exceeds the font record" % (codepoint, size))
            glyphs.append((codepoint, offset, width, height, left, top - ascent, advance))
        fonts.append({"size": size, "ascent": ascent, "descent": descent,
                      "glyphs": glyphs, "bitmap": bytes(bitmap)})
    return fonts


def convert_image(path):
    from PIL import Image

    image = Image.open(str(path))
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = rgba.load()
    colors = {pixels[x, y] for y in range(height) for x in range(width)}
    if all(a == 255 for _, _, _, a in colors) and colors <= {(0, 0, 0, 255), (255, 255, 255, 255)}:
        data = bytearray()
        for y in range(height):
            byte, bits = 0, 0
            for x in range(width):
                byte = (byte << 1) | (1 if pixels[x, y][0] else 0)
                bits += 1
                if bits == 8:
                    data.append(byte)
                    byte, bits = 0, 0
            if bits:
                data.append(byte << (8 - bits))
        return width, height, IMAGE_L1, bytes(data)
    return width, height, IMAGE_A8, bytes(pixels[x, y][3] for y in range(height) for x in range(width))


def align4(data):
    data.extend(b"\0" * (-len(data) % 4))


def build_assets(scene):
    fonts = render_fonts(scene)
    images = [convert_image(path) for _, path in scene.images]
    header_size = 28
    blob = bytearray(header_size)
    font_table = len(blob)
    blob.extend(b"\0" * 4 * len(fonts))
    image_table = len(blob)
    blob.extend(b"\0" * 4 * len(images))
    align4(blob)
    for index, font in enumerate(fonts):
        align4(blob)
        struct.pack_into("<I", blob, font_table + 4 * index, len(blob))
        record = len(blob)
        blob.extend(b"\0" * 20)
        glyph_offset = len(blob)
        for codepoint, offset, width, height, x_off, y_off, advance in font["glyphs"]:
            blob.extend(struct.pack("<IIBBbbB3x", codepoint, offset, width, height, x_off, y_off, advance))
        bitmap_offset = len(blob)
        blob.extend(font["bitmap"])
        struct.pack_into("<HHhhHHII", blob, record, font["size"], len(font["glyphs"]),
                         font["ascent"], font["descent"], font["ascent"] + font["descent"], 0,
                         glyph_offset, bitmap_offset)
    for index, (width, height, kind, data) in enumerate(images):
        align4(blob)
        struct.pack_into("<I", blob, image_table + 4 * index, len(blob))
        blob.extend(struct.pack("<HHB3xII", width, height, kind, len(blob) + 16, len(data)))
        blob.extend(data)
    align4(blob)
    crc = zlib.crc32(bytes(blob[header_size:])) & 0xFFFFFFFF
    struct.pack_into("<4sHHHHIIII", blob, 0, b"VVA1", 1, len(fonts), len(images), 0,
                     len(blob), font_table, image_table, crc)
    return bytes(blob), crc, fonts, images


def emit(scene, crc):
    objects = scene.objects
    template_names = [t["name"] for t in scene.templates]
    scene_roots = [i for i, item in enumerate(objects) if item["parent"] < 0 and "template" not in item]
    draw_order, scene_ends = scene.draw_order(scene_roots)
    template_order, template_ends, template_defs = [], {}, []
    for template in scene.templates:
        order, ends = scene.draw_order([template["root"]])
        first = len(template_order)
        template_order.extend(order)
        template_ends.update({k: v + first for k, v in ends.items()})
        root = objects[template["root"]]
        binds = [scene.bind(objects[i]["bind"]) for i in order if objects[i].get("bind")]
        if len(binds) > 4:
            raise ValueError("template %s has more than four binds" % template["name"])
        template_defs.append((template["root"], scene.action(root["callback"]) if root.get("callback") else NONE,
                              first, len(order), binds))

    def object_row(index):
        item = objects[index]
        kind = "template" if "template" in item else item["type"]
        template = scene.template_of(index)
        size = item.get("font_size", scene.default_size)
        has_text = kind in ("label", "button")
        flags = FLAG_HIDDEN if item.get("hidden") else 0
        if item.get("bg_color") and kind != "progress":
            flags |= FLAG_BG
        x, y = scene.position(index)
        subtree_end = scene_ends[index] if template is None else template_ends[index]
        action = NONE
        for event in item.get("events", []):
            if event.get("event") == "click" and event.get("action") == "call":
                action = scene.action(event["target_name"])
        if "template" in item and item.get("callback"):
            action = scene.action(item["callback"])
        if kind == "keyboard":
            action = scene.action(item["name"] + "_key")
        ref = NONE
        if kind == "list":
            ref = scene.lists.index(index)
        elif kind == "keyboard":
            ref = scene.keyboards.index(index)
        elif kind == "image":
            ref = scene.image(scene.path.parent / item["image"])
        elif kind == "template":
            ref = template_names.index(item["template"])
        elif kind == "progress":
            ref = int(item.get("value", 0))
        fields = [
            "VV_OBJ_" + kind.upper(),
            str(scene.font_index(size)) if has_text else "VV_NO_INDEX",
            "VV_ALIGN_" + item.get("text_align", "center" if kind == "button" else "left").upper(),
            str(flags), str(item["parent"]), str(x), str(y), str(item["w"]), str(item["h"]),
            "0x%04X" % rgb565(item.get("fg_color", "#FFFFFF")),
            "0x%04X" % rgb565(item.get("bg_color", "#000000")),
            str(item.get("radius", 0)),
            str(template_names.index(template)) if template is not None else "VV_NO_INDEX",
            "VIBE_BIND_" + identifier(item["bind"]) if item.get("bind") else "VV_NONE",
            "VIBE_ACT_" + identifier(scene.actions[action]) if action != NONE else "VV_NONE",
            str(scene.string(item.get("text", ""))) if has_text else "VV_NONE",
            str(ref) if ref != NONE else "VV_NONE",
            str(subtree_end),
        ]
        label = item.get("name") or item.get("template") or item.get("text", "")[:24]
        label = "".join(c for c in label if " " <= c <= "~" and c != "*")
        return "    {%s}, /* %d %s %s */" % (", ".join(fields), index, item["type"], label)

    rows = [object_row(i) for i in range(len(objects))]

    list_rows = []
    for index in scene.lists:
        item = objects[index]
        slots = int(math.ceil(item["h"] / float(item["item_height"]))) + 1
        list_rows.append("    {%d, %d, %d, %d}, /* %s */" % (
            index, template_names.index(item["row_template"]), slots, item["item_height"], item["name"]))

    template_rows = []
    for (root, action, first, count, binds), template in zip(template_defs, scene.templates):
        bind_text = ", ".join("VIBE_BIND_" + identifier(scene.binds[b]) for b in binds) or "0"
        template_rows.append("    {%d, %s, %d, %d, %d, {%s}}, /* %s */" % (
            root, "VIBE_ACT_" + identifier(scene.actions[action]) if action != NONE else "VV_NONE",
            first, count, len(binds), bind_text, template["name"]))

    keyboard_rows = []
    base = scene.path.parent
    for index in scene.keyboards:
        item = objects[index]
        size = item.get("font_size", scene.default_size)
        function_size = item.get("function_font_size", size)

        def color(key, default):
            return "0x%04X" % rgb565(item.get(key, default))

        icon = lambda key: str(scene.image(base / item[key])) if item.get(key) else "VV_NO_INDEX"
        fields = [str(index), "VIBE_ACT_" + identifier(item["name"] + "_key"),
                  color("bg_color", "#000000"), color("key_color", "#555555"), color("fg_color", "#FFFFFF"),
                  color("function_color", "#333333"), color("function_text_color", "#FFFFFF"),
                  color("delete_color", "#333333"), color("delete_text_color", "#FFFFFF"),
                  color("space_color", "#555555"), color("space_text_color", "#FFFFFF"),
                  color("ok_color", "#FF4C01"), color("ok_text_color", "#FFFFFF"),
                  str(item.get("key_radius", 8)), str(scene.font_index(size)), str(scene.font_index(function_size)),
                  icon("shift_icon"), icon("delete_icon")]
        fields += [str(scene.string(item.get(key, ""))) for key in
                   ("shift_label", "delete_label", "ok_label", "symbols_label", "letters_label", "space_label")]
        keyboard_rows.append("    {%s}, /* %s */" % (", ".join(fields), item["name"]))

    bind_objects = []
    for name in scene.binds:
        bind_objects.append(next(i for i, item in enumerate(objects) if item.get("bind") == name))

    source = ["// Generated by tools/gen_vibe_view.py from ui/main.json; do not edit.",
              '#include "vibe_scene.h"', "",
              "static const char *const strings[] = {"]
    source += ["    %s," % c_string(text) for text in scene.strings]
    source += ["};", "", "static const vv_object_def_t objects[] = {"] + rows + ["};", ""]
    source += ["static const uint16_t draw_order[] = {"]
    source += ["    " + ", ".join(str(i) for i in draw_order[n:n + 16]) + "," for n in range(0, len(draw_order), 16)]
    source += ["};", "", "static const uint16_t template_order[] = {"]
    source += ["    " + ", ".join(str(i) for i in template_order) + ",", "};", ""]
    source += ["static const vv_list_def_t lists[] = {"] + list_rows + ["};", ""]
    source += ["static const vv_template_def_t templates[] = {"] + template_rows + ["};", ""]
    source += ["static const vv_keyboard_def_t keyboards[] = {"] + keyboard_rows + ["};", ""]
    source += ["static const uint16_t bind_objects[] = {"]
    source += ["    %d, /* %s */" % (obj, name) for obj, name in zip(bind_objects, scene.binds)]
    source += ["};", "",
               "const vv_scene_t vibe_scene = {",
               "    .width = %d, .height = %d, .background = 0x%04X," % (
                   scene.data["w"], scene.data["h"], rgb565(scene.data.get("screen_bg", "#000000"))),
               "    .object_count = %d, .objects = objects," % len(objects),
               "    .draw_count = %d, .draw_order = draw_order, .template_order = template_order," % len(draw_order),
               "    .list_count = %d, .lists = lists," % len(scene.lists),
               "    .template_count = %d, .templates = templates," % len(scene.templates),
               "    .keyboard_count = %d, .keyboards = keyboards," % len(scene.keyboards),
               "    .string_count = %d, .strings = strings," % len(scene.strings),
               "    .bind_count = %d, .bind_objects = bind_objects," % len(scene.binds),
               "    .assets_crc32 = 0x%08XU," % crc,
               "};", ""]

    header = ["// Generated by tools/gen_vibe_view.py from ui/main.json; do not edit.",
              "#pragma once", '#include "vv_scene_def.h"', "",
              "enum {"]
    header += ["    VIBE_BIND_%s = %d," % (identifier(name), i) for i, name in enumerate(scene.binds)]
    header += ["    VIBE_BIND_COUNT = %d," % len(scene.binds), "};", "", "enum {"]
    header += ["    VIBE_ACT_%s = %d," % (identifier(name), i) for i, name in enumerate(scene.actions)]
    header += ["    VIBE_ACT_COUNT = %d," % len(scene.actions), "};", "", "enum {"]
    header += ["    VIBE_OBJ_%s = %d," % (identifier(name), i) for name, i in sorted(scene.named.items(), key=lambda kv: kv[1])]
    header += ["};", "", "extern const vv_scene_t vibe_scene;", ""]
    return "\n".join(header), "\n".join(source)


def write_text(path, text):
    with open(str(path), "w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def generate(scene_path, out_dir):
    scene = Scene(scene_path)
    blob, crc, fonts, images = build_assets(scene)
    header, source = emit(scene, crc)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_text(out_dir / "vibe_scene.h", header)
    write_text(out_dir / "vibe_scene.c", source)
    (out_dir / "vibe_assets.bin").write_bytes(blob)
    write_text(out_dir / "inputs.sha256", input_digest(scene_path) + "\n")
    return {
        "assets_bytes": len(blob),
        "fonts": [(f["size"], len(f["glyphs"]), len(f["bitmap"])) for f in fonts],
        "images": [(w, h, kind, len(data)) for w, h, kind, data in images],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", type=Path, default=DEFAULT_SCENE)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    report = generate(args.scene.resolve(), args.out_dir.resolve())
    print("assets: %d bytes" % report["assets_bytes"])
    for size, count, bitmap in report["fonts"]:
        print("font %2d px: %3d glyphs, %6d bitmap bytes" % (size, count, bitmap))
    for width, height, kind, size in report["images"]:
        print("image %dx%d %s: %d bytes" % (width, height, "L1" if kind == IMAGE_L1 else "A8", size))


if __name__ == "__main__":
    main()
