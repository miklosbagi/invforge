"""Unit tests for the time model shared by the register ticker and
core/connectivity.py's offline-window watcher (core/server.py's
elapsed_seconds()) -- no asyncio, no network."""

from __future__ import annotations

import time

from invforge.core.scenario import Scenario
from invforge.core.server import elapsed_seconds
from invforge.profiles.sigenergy.firmwares.V100R001C21SPC116 import PROFILE


def _scenario_with_duration(duration_s: float) -> Scenario:
    return Scenario(
        "test-elapsed",
        {"timeseries": [{"t": 0, 30014: 1000}, {"t": duration_s, 30014: 0}]},
        PROFILE,
    )


def test_elapsed_seconds_before_duration_is_unwrapped():
    scenario = _scenario_with_duration(10.0)
    start_time = time.monotonic() - 5.0  # "5 seconds into the scenario"
    assert 4.9 < elapsed_seconds(scenario, start_time, speed=1.0) < 5.1


def test_elapsed_seconds_wraps_at_duration():
    scenario = _scenario_with_duration(10.0)
    start_time = time.monotonic() - 23.0  # 23s in on a 10s-duration scenario -> wraps to ~3s
    assert 2.9 < elapsed_seconds(scenario, start_time, speed=1.0) < 3.1


def test_elapsed_seconds_speed_multiplier():
    scenario = _scenario_with_duration(100.0)
    start_time = time.monotonic() - 2.0  # 2 real seconds at 10x speed -> ~20s elapsed
    assert 19.0 < elapsed_seconds(scenario, start_time, speed=10.0) < 21.0
