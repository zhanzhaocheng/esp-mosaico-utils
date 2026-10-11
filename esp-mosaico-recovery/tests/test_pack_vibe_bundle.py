"""The embedded stream must remain ROM-compatible zlib and lossless."""
import os
from pathlib import Path
import re
import subprocess
import sys
import zlib


def test_embedded_bundle_is_lossless_and_never_larger_than_zlib(tmp_path):
    tool = Path(__file__).resolve().parents[1] / "firmware/recovery/tools/pack_vibe_bundle.py"
    # Include binary values, repeated record-like and glyph-like data.
    raw = bytes(range(256)) * 32 + b"glyph\x00font\x00bind\x00" * 1024
    source = tmp_path / "vibe_assets.bin"
    output = tmp_path / "bundle.c"
    source.write_bytes(raw)
    # zopfli needs Python 3.10+; CI points this at its build interpreter.
    python = os.environ.get("RECOVERY_BUILD_PYTHON") or os.environ.get("GSP_BUILD_PYTHON") or sys.executable
    result = subprocess.run([python, str(tool), str(source), str(output)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    text = output.read_text()
    data = bytes(int(value, 16) for value in re.findall(r"0x([0-9a-f]{2})", text))
    assert zlib.decompress(data) == raw
    assert len(data) <= len(zlib.compress(raw, 9))
    assert "vibe_bundle_size = %d;" % len(raw) in text
    assert "vibe_bundle_compressed_size = %d;" % len(data) in text
