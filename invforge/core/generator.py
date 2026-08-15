"""Parametric scenario generator -- computes common linear ramp
scenarios on the fly (e.g. "linear-drain-100-to-0-60s") instead of
requiring a hand-written YAML file per exact numeric variant. Purely
additive to the static YAML library (core/scenario.py's
Scenario.from_yaml) -- see state.py's resolve_scenario() for how the two
are combined; an existing YAML of the same name always wins.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .profile import Profile
from .scenario import Scenario

_RAMP_RE = re.compile(
    r"^linear-(?P<direction>drain|charge)-(?P<start>\d+(?:\.\d+)?)-to-"
    r"(?P<end>\d+(?:\.\d+)?)-(?P<duration>\d+(?:\.\d+)?)s$"
)


@dataclass(frozen=True)
class RampParams:
    direction: Literal["drain", "charge"]
    start_pct: float
    end_pct: float
    duration_s: float


def resolve_generated(name: str, profile: Profile) -> Scenario | None:
    """None if `name` doesn't match the generator's naming convention, or
    the profile has no ramp_builder -- caller falls back to the static
    YAML library. Raises ValueError for a name that matches the pattern
    but describes an invalid ramp (an HTTP/CLI-boundary input, validated
    here rather than trusted)."""
    if profile.ramp_builder is None:
        return None
    match = _RAMP_RE.match(name)
    if match is None:
        return None

    direction_str = match["direction"]
    direction: Literal["drain", "charge"]
    if direction_str == "drain":
        direction = "drain"
    elif direction_str == "charge":
        direction = "charge"
    else:
        raise AssertionError(f"regex guarantees drain|charge, got {direction_str!r}")

    params = RampParams(
        direction=direction,
        start_pct=float(match["start"]),
        end_pct=float(match["end"]),
        duration_s=float(match["duration"]),
    )
    if params.duration_s <= 0:
        raise ValueError(f"{name!r}: duration must be > 0")
    if params.direction == "drain" and params.start_pct < params.end_pct:
        raise ValueError(f"{name!r}: direction 'drain' but {params.start_pct} -> {params.end_pct} increases")
    if params.direction == "charge" and params.start_pct > params.end_pct:
        raise ValueError(f"{name!r}: direction 'charge' but {params.start_pct} -> {params.end_pct} decreases")

    return Scenario(name, profile.ramp_builder(params), profile)
