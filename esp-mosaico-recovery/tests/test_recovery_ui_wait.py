"""Regression coverage for bounded polling of native UI state in simulated time."""
import itertools
import json

import pytest

from test_recovery_ui_host import FRAME_MS, Simulator


def simulator(tmp_path, states):
    sim = Simulator.__new__(Simulator)
    sim.directory = tmp_path
    sim.log_path = tmp_path / "sim.log"
    sim.log_path.write_text("simulator running", encoding="utf-8")
    sim.log = sim.log_path.open("a")
    sim.commands = []
    sequence = iter(states)

    def command(line):
        sim.commands.append(line)
        return json.dumps(next(sequence)) if line == "state" else "ok"

    sim.command = command
    return sim


def test_wait_advances_simulated_time_until_the_expected_state(tmp_path):
    sim = simulator(tmp_path, [{"page": 7}, {"page": 7}, {"page": 8}])
    assert sim.wait(page=8) == {"page": 8}
    assert sim.commands == ["state", "wait 3", "state", "wait 3", "state", "wait 20"]


def test_wait_is_bounded_in_simulated_time(tmp_path):
    sim = simulator(tmp_path, itertools.repeat({"page": 7}))
    with pytest.raises(pytest.fail.Exception, match="expected"):
        sim.wait(timeout=1, page=8)
    # One poll every three frames, through the whole simulated second.
    assert sim.commands.count("state") == 1000 // (3 * FRAME_MS) + 1


def test_update_can_complete_after_the_default_deadline(tmp_path):
    late = [{"page": 7, "progress": 900}] * 400 + [{"page": 8, "progress": 1000}]
    with pytest.raises(pytest.fail.Exception):
        simulator(tmp_path, late).wait(page=8, progress=1000)
    assert simulator(tmp_path, late).wait(timeout=45, page=8, progress=1000)["progress"] == 1000
