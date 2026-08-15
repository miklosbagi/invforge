"""Shared, thread-safe simulator state -- the Modbus ticker thread reads
it, the HTTP control API mutates it. Two modes:

- "scenario": ticker advances elapsed wall-clock time (scaled by `speed`)
  through a loaded Scenario's timeseries, looping at its duration.
- "manual": ticker does nothing; POST /state writes directly into the
  datastore and freezes it there until the next /scenario or /state call.
  This is what lets a test jump straight to "SoC=5%" without waiting
  through a ramp.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from .profile import Profile
from .scenario import Scenario


class SimState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.mode = "manual"  # start frozen/all-zero until a scenario or state is set
        self.scenario: Scenario | None = None
        self.scenario_start = time.monotonic()
        self.speed = 1.0

    def set_scenario(self, scenario: Scenario, speed: float = 1.0) -> None:
        with self.lock:
            self.scenario = scenario
            self.scenario_start = time.monotonic()
            self.speed = speed
            self.mode = "scenario"

    def freeze_manual(self) -> None:
        with self.lock:
            self.mode = "manual"

    def snapshot(self) -> tuple[str, Scenario | None, float, float]:
        with self.lock:
            return self.mode, self.scenario, self.scenario_start, self.speed


def list_scenarios(scenarios_dir: Path) -> dict[str, str]:
    """name -> relative path, for both recorded/ and synthetic/ under a
    profile's scenarios_dir."""
    found = {}
    for sub in ("recorded", "synthetic"):
        d = scenarios_dir / sub
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.yaml")):
            found[f.stem] = str(f.relative_to(scenarios_dir.parent))
    return found


def resolve_scenario_path(scenarios_dir: Path, name: str) -> Path:
    found = list_scenarios(scenarios_dir)
    if name not in found:
        raise KeyError(f"unknown scenario {name!r}, available: {sorted(found)}")
    return scenarios_dir.parent / found[name]


def resolve_scenario(name: str, profile: Profile) -> Scenario:
    """Resolve a scenario by name: the static YAML library is tried
    first -- an existing fixture always wins on a name collision, a
    deliberate escape hatch -- then the parametric generator (see
    core/generator.py). Raises KeyError if neither resolves the name,
    ValueError if the generator matched the name but the ramp it
    describes is invalid."""
    try:
        path = resolve_scenario_path(profile.scenarios_dir, name)
    except KeyError:
        from .generator import resolve_generated

        generated = resolve_generated(name, profile)
        if generated is not None:
            return generated
        raise
    return Scenario.from_yaml(path, profile)
