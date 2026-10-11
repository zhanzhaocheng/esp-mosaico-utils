"""Committed Vibe View outputs must match ui/main.json and cover every glyph it uses."""
import importlib.util
from pathlib import Path
import struct
import zlib

RECOVERY = Path(__file__).resolve().parents[1] / "firmware/recovery"
SCENE = RECOVERY / "ui/main.json"
GENERATED = RECOVERY / "ui/generated"
SPEC = importlib.util.spec_from_file_location("gen_vibe_view", str(RECOVERY / "tools/gen_vibe_view.py"))
gen = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gen)


def read_fonts(blob):
    magic, version, font_count, _, _, total, fonts_offset, _, crc = struct.unpack_from("<4sHHHHIIII", blob, 0)
    assert magic == b"VVA1" and version == 1 and total == len(blob)
    assert zlib.crc32(blob[28:]) & 0xFFFFFFFF == crc
    fonts = {}
    for index in range(font_count):
        offset = struct.unpack_from("<I", blob, fonts_offset + 4 * index)[0]
        size, count, _, _, _, _, glyphs, _ = struct.unpack_from("<HHhhHHII", blob, offset)
        fonts[size] = [struct.unpack_from("<I", blob, glyphs + 16 * g)[0] for g in range(count)]
    return fonts, crc


def test_generated_outputs_match_their_inputs():
    recorded = (GENERATED / "inputs.sha256").read_text(encoding="utf-8").strip()
    assert recorded == gen.input_digest(SCENE), \
        "ui/main.json, its fonts or images changed: run tools/gen_vibe_view.py and commit ui/generated"


def test_assets_cover_every_scene_glyph_and_match_the_scene():
    scene = gen.Scene(SCENE)
    fonts, crc = read_fonts((GENERATED / "vibe_assets.bin").read_bytes())
    assert sorted(fonts) == scene.sizes
    for size, needed in scene.glyphs.items():
        codepoints = fonts[size]
        assert codepoints == sorted(codepoints), size  # Runtime binary search.
        missing = sorted({ord(c) for c in needed} - set(codepoints))
        assert not missing, (size, ["U+%04X" % c for c in missing])
    assert ".assets_crc32 = 0x%08XU," % crc in (GENERATED / "vibe_scene.c").read_text(encoding="utf-8")


def test_scene_tables_regenerate_identically(tmp_path):
    gen.generate(SCENE, tmp_path)
    assert (tmp_path / "vibe_scene.h").read_text(encoding="utf-8") == \
        (GENERATED / "vibe_scene.h").read_text(encoding="utf-8")

    def without_crc(text):
        return "\n".join(line for line in text.splitlines() if ".assets_crc32" not in line)

    # Glyph bitmaps, hence the CRC, may differ between FreeType releases.
    assert without_crc((tmp_path / "vibe_scene.c").read_text(encoding="utf-8")) == \
        without_crc((GENERATED / "vibe_scene.c").read_text(encoding="utf-8"))
