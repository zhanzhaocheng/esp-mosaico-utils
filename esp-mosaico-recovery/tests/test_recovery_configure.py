"""Recovery configures without the GSP compiler bootstrap or a Python gsp module."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

RECOVERY = Path(__file__).resolve().parents[1] / "firmware/recovery"


def test_recovery_configures_without_gsp_compiler(tmp_path):
    cmake = shutil.which("cmake")
    if cmake is None:
        pytest.skip("CMake is required for the Recovery configure regression")
    fake_idf = tmp_path / "idf"
    entry = fake_idf / "tools/cmake/project.cmake"
    entry.parent.mkdir(parents=True)
    # Stop at the IDF boundary, before component downloads or firmware compilation.
    entry.write_text(
        'file(WRITE "${CMAKE_BINARY_DIR}/resolved-gspc.txt" "${GSPC_EXECUTABLE}")\n'
        'message(FATAL_ERROR "test reached IDF configuration boundary")\n',
        encoding="utf-8",
    )
    environment = dict(os.environ, IDF_PATH=str(fake_idf), XDG_CACHE_HOME=str(tmp_path / "cache"))
    for name in ("GSPC_EXECUTABLE", "GSPC_CACHE_DIR"):
        environment.pop(name, None)
    build = tmp_path / "build"
    result = subprocess.run([cmake, "-S", str(RECOVERY), "-B", str(build)], env=environment,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            universal_newlines=True, timeout=60)
    assert "test reached IDF configuration boundary" in result.stdout, result.stdout
    assert (build / "resolved-gspc.txt").read_text(encoding="utf-8") == "", result.stdout
    assert not (tmp_path / "cache").exists(), "Recovery configure must not fetch GSP tools"


def test_recovery_sources_do_not_use_gsp():
    for path in sorted((RECOVERY / "main").glob("*")) + sorted((RECOVERY / "components/vibe_view").rglob("*.[ch]")):
        text = path.read_text(encoding="utf-8")
        assert "esp_gsp" not in text and "gsp_add_bundle" not in text, path
    manifest = (RECOVERY / "main/idf_component.yml").read_text(encoding="utf-8")
    assert "esp-gsp" not in manifest
