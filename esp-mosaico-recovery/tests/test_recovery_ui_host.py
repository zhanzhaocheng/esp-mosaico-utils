"""Exercise the production Vibe View scene and C controller through native input."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest
from PIL import Image
import zxingcpp

ROOT = Path(__file__).resolve().parents[1]
RECOVERY = ROOT / "firmware/recovery"
FRAME_MS = 16
BINDS = dict(re.findall(r"VIBE_BIND_(\w+) = (\d+),",
                        (RECOVERY / "ui/generated/vibe_scene.h").read_text(encoding="utf-8")))


class Simulator:
    """Drive the native simulator over stdin/stdout with simulated time."""

    def __init__(self, directory, executable, scenario=""):
        self.directory = directory
        self.log_path = directory / "sim.log"
        self.log = self.log_path.open("w")
        self.process = subprocess.Popen(
            [str(executable)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log,
            env=dict(os.environ, VIBE_SIM_SCENARIO=scenario), universal_newlines=True, bufsize=1)
        try:
            ready = self.process.stdout.readline().strip()
            assert ready == "ready", self.diagnostics()
        except BaseException:
            self.close()
            raise

    def diagnostics(self):
        self.log.flush()
        return self.log_path.read_text()

    def command(self, line):
        assert self.process.poll() is None, self.diagnostics()
        self.process.stdin.write(line + "\n")
        self.process.stdin.flush()
        reply = self.process.stdout.readline()
        assert reply, "simulator exited: " + self.diagnostics()
        reply = reply.rstrip("\n")
        assert not reply.startswith("error"), (line, reply)
        return reply

    def frames(self, count):
        self.command("wait %d" % count)

    def advance(self, seconds):
        self.frames(int(seconds * 1000 / FRAME_MS) + 1)

    def state(self):
        return json.loads(self.command("state"))

    def wait(self, *, timeout=15, **expected):
        """Poll state while simulated time advances; timeout is simulated seconds."""
        actual, elapsed = {}, 0
        while elapsed <= timeout * 1000:
            actual = self.state()
            if all(actual.get(k) == v for k, v in expected.items()):
                # Let already-enqueued visibility and list updates paint.
                self.frames(20)
                return actual
            self.frames(3)
            elapsed += 3 * FRAME_MS
        pytest.fail("expected %r; observed %r; %s" % (expected, actual, self.diagnostics()))

    def tap(self, x, y):
        self.command("tap %d %d" % (x, y))
        self.frames(8)

    def text(self, bind):
        return self.command("text " + BINDS[bind])

    def drag(self, x, start_y, end_y, step=10):
        self.command("press %d %d" % (x, start_y))
        self.frames(1)
        direction = -step if end_y < start_y else step
        for y in range(start_y + direction, end_y + direction, direction):
            self.command("move %d %d" % (x, y))
            self.frames(1)
        self.command("release")
        self.frames(60)

    def screenshot(self, path, image_format):
        self.command("screenshot %s %s" % (image_format, path))

    def capture(self, name):
        self.screenshot(self.directory / (name + ".png"), "png")

    def open_bridge(self):
        # Same public controller entry used by the device's queued USB RPC.
        self.control("open-bridge")

    def control(self, command):
        self.command("control " + command)
        self.frames(20)

    def close(self):
        if self.process.poll() is None:
            try:
                self.process.stdin.write("quit\n")
                self.process.stdin.flush()
                self.process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                self.process.kill()
                self.process.wait()
        for stream in (self.process.stdin, self.process.stdout):
            if stream:
                stream.close()
        self.log.close()


def build_simulator(build):
    cmake = shutil.which("cmake")
    assert cmake, "The native Vibe View simulator requires CMake and a C compiler"
    configure = [cmake, "-S", str(RECOVERY / "pc"), "-B", str(build), "-DCMAKE_BUILD_TYPE=Release"]
    if shutil.which("ninja"):
        configure += ["-G", "Ninja"]
    for command in (configure, [cmake, "--build", str(build), "--config", "Release"]):
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                universal_newlines=True, timeout=300)
        assert result.returncode == 0, result.stdout
    name = "vibe_sim.exe" if os.name == "nt" else "vibe_sim"
    candidates = sorted(build.rglob(name))
    assert candidates, "simulator executable was not produced"
    return candidates[0]


@pytest.fixture(scope="module")
def native_build(tmp_path_factory):
    return build_simulator(tmp_path_factory.mktemp("vibe-native-build"))


@pytest.fixture
def sim(tmp_path, native_build, request):
    instance = Simulator(tmp_path, native_build, scenario=getattr(request, "param", ""))
    try:
        yield instance
    finally:
        instance.close()


def test_keyboard_limits_masking_and_cancel(sim):
    sim.capture("home")
    sim.tap(240, 390)
    sim.wait(page=1, pending=True)
    sim.capture("wifi")
    sim.tap(180, 251)
    sim.wait(page=2, password_length=0, password_visible=False)
    sim.capture("keyboard")
    for _ in range(65):
        sim.tap(35, 258)  # native q key; the 65th character must be rejected
    sim.wait(password_length=64)
    sim.capture("password-masked")
    sim.tap(431, 376)  # Backspace
    sim.wait(password_length=63)
    sim.tap(414, 146)
    sim.wait(password_visible=True)
    sim.tap(38, 36)
    sim.wait(page=1, password_length=0, password_visible=False, pending=True)
    sim.tap(38, 36)
    sim.wait(page=0, pending=False, bridge_running=False)


def test_download_wifi_continuation_and_cancel(sim):
    sim.tap(240, 390)
    sim.wait(page=1, pending=True)
    sim.tap(180, 251)
    sim.wait(page=2)
    for _ in range(8):
        sim.tap(35, 258)
    sim.wait(password_length=8)
    sim.tap(420, 435)  # GO
    sim.wait(page=4, pending=False, network=2, bridge_running=True, password_length=0)
    sim.capture("download-ideas")
    sim.wait(bridge_open_calls=1)
    sim.open_bridge()
    sim.open_bridge()
    sim.wait(page=4, bridge_running=True, bridge_open_calls=1)
    sim.tap(240, 444)
    sim.wait(page=0, bridge_running=False)
    sim.tap(75, 445)  # ordinary Wi-Fi entry never starts a download
    sim.wait(page=1, pending=False, bridge_running=False)


@pytest.mark.parametrize("sim", ["prefetched"], indirect=True)
def test_prefetched_code_reused_after_back_and_explicit_cancel(sim):
    sim.wait(page=0, bridge_prefetch_calls=1, bridge_open_calls=0,
             bridge_running=True, bridge_active=False, code_ready=True)
    sim.tap(240, 390)
    sim.wait(page=4, bridge_active=True, code_ready=True, bridge_open_calls=1)
    sim.capture("prefetched-code")
    sim.tap(38, 36)
    sim.wait(page=0, bridge_running=True, bridge_active=False, code_ready=True)
    sim.tap(240, 390)
    sim.wait(page=4, bridge_active=True, bridge_open_calls=2, bridge_prefetch_calls=1)
    sim.tap(240, 444)
    sim.wait(page=0, bridge_running=False, bridge_active=False, code_ready=False)
    sim.tap(240, 390)
    sim.wait(page=4, bridge_running=True, bridge_open_calls=3, bridge_prefetch_calls=1)


def test_wifi_cards_and_labels_survive_navigation_and_rescan(sim):
    def check_frame(name):
        sim.capture(name)
        path = sim.directory / (name + ".ppm")
        sim.screenshot(path, "ppm")
        with path.open("rb") as frame:
            assert frame.readline().strip() == b"P6"
            assert frame.readline().split() == [b"480", b"480"]
            assert frame.readline().strip() == b"255"
            pixels = frame.read()
        assert len(pixels) == 480 * 480 * 3

        def region(x1, y1, x2, y2):
            return [pixels[(y * 480 + x) * 3:(y * 480 + x) * 3 + 3]
                    for y in range(y1, y2) for x in range(x1, x2)]

        # Actual rendered glyphs, not just successful visibility callbacks.
        for box, minimum in [((190, 12, 290, 60), 200),  # Wi-Fi
                             ((20, 20, 50, 50), 5),    # Back
                             ((360, 102, 438, 145), 200),  # Forget
                             ((363, 176, 450, 208), 200)]:  # Rescan
            assert sum(min(rgb) > 160 for rgb in region(*box)) > minimum, name
        # Three complete cards, separated from each other and the footer.
        for y in (288, 360, 434):
            assert all(max(rgb) == 0 for rgb in region(48, y, 430, y + 2)), name
        for y in (280, 352, 424):
            assert all(min(rgb) >= 24 for rgb in region(80, y, 380, y + 2)), name

    for cycle in range(3):
        sim.tap(75, 445)
        sim.wait(page=1)
        check_frame("wifi-entry-%d" % cycle)
        sim.tap(180, 251)
        sim.wait(page=2)
        sim.tap(38, 36)
        sim.wait(page=1)
        sim.tap(410, 190)
        sim.wait(page=1)
        check_frame("wifi-rescan-%d" % cycle)
        sim.tap(38, 36)
        sim.wait(page=0)


def test_nand_update_and_result_acknowledgement(sim):
    sim.tap(370, 446)
    sim.wait(page=5)
    sim.capture("nand")
    sim.tap(150, 170)
    sim.wait(page=6)
    sim.capture("confirm")
    sim.tap(350, 430)
    sim.wait(page=7)
    sim.capture("update")
    # Twenty service ticks of 250 ms complete the simulated NAND component.
    sim.wait(timeout=45, page=8, progress=1000)
    sim.capture("result")
    sim.tap(240, 409)
    sim.wait(page=0)
    sim.advance(.6)
    sim.wait(page=0)  # an acknowledged terminal result must not reopen


@pytest.mark.parametrize("sim", ["wifi-fail-once"], indirect=True)
def test_network_failure_and_retry_preserve_download_intent(sim):
    sim.tap(240, 390)
    sim.wait(page=1, pending=True)
    for expected_network in (3, 2):
        sim.tap(180, 251)
        sim.wait(page=2, password_length=0)
        for _ in range(8):
            sim.tap(35, 258)
        sim.tap(420, 435)
        if expected_network == 3:
            sim.wait(page=1, network=3, pending=True, password_length=0)
            sim.capture("network-failure")
        else:
            sim.wait(page=4, network=2, pending=False, bridge_running=True)


@pytest.mark.parametrize("sim", ["update-fail"], indirect=True)
def test_update_failure_returns_home_without_reopening(sim):
    sim.tap(370, 446)
    sim.wait(page=5)
    sim.tap(150, 170)
    sim.wait(page=6)
    sim.tap(350, 430)
    sim.wait(page=8, progress=500)
    sim.capture("update-failure")
    sim.tap(240, 409)
    sim.wait(page=0)
    sim.advance(.6)
    sim.wait(page=0)


@pytest.mark.parametrize("sim", ["empty"], indirect=True)
def test_empty_lists_remain_navigable(sim):
    sim.tap(75, 445)
    sim.wait(page=1, pending=False)
    sim.capture("wifi-empty")
    sim.tap(180, 251)
    sim.wait(page=1)
    sim.tap(38, 36)
    sim.wait(page=0)
    sim.tap(370, 446)
    sim.wait(page=5)
    sim.capture("nand-empty")
    sim.tap(150, 170)
    sim.wait(page=5)
    sim.tap(38, 36)
    sim.wait(page=0)


@pytest.mark.parametrize("sim", ["prefetched", "long-code", "waiting-code"], indirect=True)
def test_download_qr_decodes_from_native_frame_and_code_survives_navigation(sim):
    sim.tap(240, 390)
    sim.wait(page=4)
    sim.capture("ideas-qr")
    frame = Image.open(sim.directory / "ideas-qr.png")
    codes = zxingcpp.read_barcodes(frame)
    assert [code.text for code in codes] == ["https://mosaico-ideas.espressif.com/"]
    snapshot = sim.wait(page=4)
    if snapshot["code_length"] == 15:
        # Worst-case wide characters must have visible ink and side margins.
        assert frame.crop((40, 328, 440, 362)).getbbox()
        pixels = frame.convert("RGB")
        for x in (36, 443):
            assert all(max(pixels.getpixel((x, y))) < 100 for y in range(321, 372))
    sim.tap(38, 36)
    sim.wait(page=0, bridge_running=True, bridge_active=False)
    sim.tap(240, 390)
    sim.wait(page=4, bridge_running=True, bridge_active=True)
    sim.control("expire-code")
    sim.wait(renewed_code=True)
    sim.tap(240, 444)
    sim.wait(page=0, bridge_running=False, code_ready=False)


def test_ota_telemetry_component_transition_stall_retry_and_terminal_states(sim):
    def sample(ms, received, total=4*1024*1024, component=1, completed=0,
               receiving=1, job=1, component_received=None, terminal=0):
        if component_received is None:
            component_received = received
        sim.control("transfer %d %d %d %d 2 %d %d %d %d 2097152 %d" %
                    (ms, received, total, component, completed, receiving, job, component_received, terminal))
        return sim.wait(sample_ms=ms)

    sample(0, 0)
    sim.wait(page=7, progress=0, rate_valid=False)
    sample(1000, 1024*1024)
    sim.wait(progress=250, rate_valid=True, rate_bps=1024*1024)
    sim.capture("ota-downloading")
    sample(2000, 1024*1024)
    sim.wait(progress=250, rate_bps=0)
    sim.capture("ota-stalled")
    sample(2250, 2*1024*1024, receiving=0)
    sim.wait(progress=500, rate_valid=False)
    sim.capture("ota-component-verified")
    sample(2500, 2*1024*1024, component=2, completed=1, component_received=0)
    sim.wait(progress=500, rate_valid=False, component_id=2)
    sample(3500, 3*1024*1024, component=2, completed=1, component_received=1024*1024)
    sim.wait(progress=750, rate_valid=True, rate_bps=1024*1024)
    sim.capture("ota-second-component")
    sample(3750, 2*1024*1024, component=2, completed=1, component_received=0)
    sim.wait(progress=500, rate_valid=False)  # retry rolls back only the active payload
    sample(4000, 0, total=0, job=2)
    sim.wait(progress=0, rate_valid=False)
    sim.capture("ota-unknown-size")
    sample(5000, 1024, total=0, job=2)
    sim.wait(rate_valid=True, rate_bps=1024)
    sample(6000, 4*1024*1024, component=0, completed=2, receiving=0, job=3)
    sim.wait(page=7, progress=1000, rate_valid=False)
    sim.capture("ota-committing")
    sample(7000, 4*1024*1024, component=0, completed=2, receiving=0, job=3, terminal=2)
    sim.wait(page=8, progress=1000, rate_valid=False)
    sim.capture("ota-failed-after-transfer")
    sim.tap(240, 409)
    sim.wait(page=0)


def test_wifi_list_drag_scroll_selects_offscreen_network(sim):
    sim.tap(75, 445)
    sim.wait(page=1)
    sim.drag(240, 420, 190)
    sim.capture("wifi-scrolled")
    sim.tap(180, 251)  # The first visible card is now the fourth network.
    sim.wait(page=2)
    assert sim.text("SSID") == "Studio network 4"
    sim.tap(38, 36)
    sim.wait(page=1)
    sim.drag(240, 240, 430)  # Scroll back to the top.
    sim.tap(180, 251)
    sim.wait(page=2)
    assert sim.text("SSID") == "Studio network 1"


def test_keyboard_symbol_pages_and_shift(sim):
    sim.tap(75, 445)
    sim.wait(page=1)
    sim.tap(180, 251)
    sim.wait(page=2)
    sim.tap(47, 434)   # Mode key: symbols page.
    sim.tap(24, 260)   # 1
    sim.tap(36, 376)   # More symbols.
    sim.capture("keyboard-more-symbols")
    sim.tap(24, 260)   # [
    sim.tap(225, 434)  # Space
    sim.tap(47, 434)   # Letters again.
    sim.tap(36, 376)   # Shift.
    sim.tap(24, 260)   # Q
    sim.tap(36, 376)   # Shift off.
    sim.tap(24, 260)   # q
    sim.wait(password_length=5)
    sim.tap(414, 146)  # Show the typed password.
    sim.wait(password_visible=True)
    assert sim.text("PASSWORD_DISPLAY") == "1[ Qq"
    sim.tap(431, 376)  # Backspace removes the last character.
    sim.wait(password_length=4)
    assert sim.text("PASSWORD_DISPLAY") == "1[ Q"
