#!/usr/bin/env python3
"""Inline layout.json, the subset fonts and the icons into prototype/index.html.

Run build_design.py first. The output is one self-contained HTML page with no
network access, suitable for opening locally or publishing as a private page.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

DESIGN = Path(__file__).resolve().parents[1]


def b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def main() -> None:
    layout = json.loads((DESIGN / "layout.json").read_text(encoding="utf-8"))
    assets = {}
    for folder in ("assets/icons", "assets/mosaic", "assets/ideas", "assets/anim", "assets/qr", "assets/ui"):
        for path in sorted((DESIGN / folder).glob("*.png")):
            assets[f"{folder}/{path.name}"] = "data:image/png;base64," + b64(path)
    fonts = DESIGN / "assets/fonts"

    def script_json(value) -> str:
        # Keep "</script>" sequences inside strings from closing the element.
        return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

    page = (DESIGN / "tools/prototype.template.html").read_text(encoding="utf-8")
    replacements = {
        "__FONT_DOT__": b64(fonts / "ArchivoExtended-SemiBold.subset.ttf"),
        "__FONT_SANS__": b64(fonts / "Inter-Regular.subset.ttf"),
        "__FONT_MEDIUM__": b64(fonts / "ArchivoExtended-Medium.subset.ttf"),
        "__FONT_SC_REGULAR__": b64(fonts / "NotoSansSC-Regular.subset.otf"),
        "__FONT_SC_MEDIUM__": b64(fonts / "NotoSansSC-Medium.subset.otf"),
        "__FONT_SC_BOLD__": b64(fonts / "NotoSansSC-Bold.subset.otf"),
        "__LAYOUT__": script_json(layout),
        "__ASSETS__": script_json(assets),
    }
    for key, value in replacements.items():
        if key not in page:
            raise SystemExit(f"template is missing {key}")
        page = page.replace(key, value)
    out = DESIGN / "prototype/index.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"{out.relative_to(DESIGN)}: {len(page) / 1024:.0f} KiB")


if __name__ == "__main__":
    main()
