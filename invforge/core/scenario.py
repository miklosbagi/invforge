"""Scenario YAML loading + playback (elapsed-time -> current register state).
Vendor-agnostic: takes a Profile to resolve register addresses per unit.

Format (see any profile's scenarios/recorded/*.yaml for a real example):

    static:
      unit_<n>: { <address>: <raw int|word-list|string>, ... }
    timeseries:
      - t: <seconds>
        <address>: <raw int|word-list>   # omit a register at a sample to
        ...                               # mean "not sampled here", not
                                           # "zero" -- carries forward.
                                           # Applies to the profile's
                                           # default_unit.
    exceptions:
      unit_<n>: { <address>: {function_code: <n>, exception_code: <n>} }
    offline:
      - { start: <seconds>, end: <seconds> }   # Modbus TCP connection
        ...                                      # is unreachable during
                                                   # each [start, end)
                                                   # window, elapsed
                                                   # scenario time.

All numeric values are RAW wire values (pre-gain), never the decoded
real-world value -- a bare int for single-register fields, a [hi, lo] word
list for multi-register (S32/U32) fields.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import yaml

from .profile import Profile
from .registers import DType, RegisterDef, normalize_scenario_value


@dataclass
class RegisterTimeseries:
    reg: RegisterDef
    samples: list[tuple[float, int]] = field(default_factory=list)  # (t, combined_raw)

    def value_at(self, t: float) -> int:
        if not self.samples:
            raise ValueError(f"no samples at all for {self.reg.name}")
        times = [s[0] for s in self.samples]
        idx = bisect_right(times, t) - 1
        if idx < 0:
            return self.samples[0][1]
        if idx >= len(self.samples) - 1:
            return self.samples[-1][1]
        t0, v0 = self.samples[idx]
        t1, v1 = self.samples[idx + 1]
        if t1 == t0:
            return v1
        frac = (t - t0) / (t1 - t0)
        return round(v0 + frac * (v1 - v0))


class Scenario:
    def __init__(self, name: str, data: dict[str, object], profile: Profile) -> None:
        """Build a scenario from already-loaded data -- the same shape a
        scenario YAML parses into (see module docstring), whether it
        actually came from YAML (via from_yaml()) or was computed on the
        fly by a generator (see core/generator.py). Keeping one
        constructor for both means generated and loaded scenarios are
        never two implementations that could drift apart."""
        self.name = name
        self.profile = profile

        self.static: dict[int, dict[int, int | str]] = {}  # unit -> address -> raw
        # `data`'s shape is established by its two producers (YAML parse
        # in from_yaml(), or a generator's own construction) -- the casts
        # below describe that established shape rather than re-validating
        # a trust boundary already covered there.
        raw_exceptions = cast("dict[str, dict[int, dict[str, int]]]", data.get("exceptions") or {})
        self.exceptions = {_unit_from_key(k): v for k, v in raw_exceptions.items()}
        self._series: dict[int, dict[int, RegisterTimeseries]] = {}  # unit -> address -> series

        raw_static = cast("dict[str, dict[int | str, object]]", data.get("static") or {})
        for unit_key, block in raw_static.items():
            unit = _unit_from_key(unit_key)
            self.static[unit] = {}
            for addr, value in (block or {}).items():
                reg = profile.find(unit, int(addr))
                if reg is None:
                    continue
                if reg.dtype == DType.STRING:
                    self.static[unit][int(addr)] = str(value)
                else:
                    self.static[unit][int(addr)] = normalize_scenario_value(reg, cast("int | list[int]", value))

        # timeseries entries apply to the profile's default_unit
        unit = profile.default_unit
        raw_timeseries = cast("list[dict[str, object]]", data.get("timeseries") or [])
        for sample in raw_timeseries:
            t = float(str(sample["t"]).lstrip("~"))
            for key, value in sample.items():
                if key == "t" or value is None:
                    continue
                addr = int(key)
                reg = profile.find(unit, addr)
                if reg is None or reg.dtype == DType.STRING:
                    continue
                series = self._series.setdefault(unit, {}).setdefault(addr, RegisterTimeseries(reg))
                series.samples.append((t, normalize_scenario_value(reg, cast("int | list[int]", value))))

        for unit_series in self._series.values():
            for series in unit_series.values():
                series.samples.sort(key=lambda s: s[0])

        raw_offline = cast("list[dict[str, float]]", data.get("offline") or [])
        self.offline_windows: list[tuple[float, float]] = []
        for window in raw_offline:
            start, end = float(window["start"]), float(window["end"])
            if start < 0:
                raise ValueError(f"{name!r}: offline window start {start} must be >= 0")
            if end <= start:
                raise ValueError(f"{name!r}: offline window end {end} must be > start {start}")
            self.offline_windows.append((start, end))

    @classmethod
    def from_yaml(cls, path: str | Path, profile: Profile) -> Scenario:
        path = Path(path)
        with path.open() as f:
            data = yaml.safe_load(f) or {}
        return cls(path.stem, data, profile)

    def duration(self) -> float:
        max_t = 0.0
        for unit_series in self._series.values():
            for series in unit_series.values():
                if series.samples:
                    max_t = max(max_t, series.samples[-1][0])
        for _start, end in self.offline_windows:
            max_t = max(max_t, end)
        return max_t

    def is_offline_at(self, t: float) -> bool:
        return any(start <= t < end for start, end in self.offline_windows)

    def value_at(self, unit: int, address: int, t: float) -> int | str | None:
        """Combined raw value (or string) for one register at elapsed time
        t, or None if this register isn't defined for this unit at all
        (caller should then fall back to a static default / illegal
        address, per the datastore's own construction)."""
        series = (self._series.get(unit) or {}).get(address)
        if series is not None:
            return series.value_at(t)
        if address in (self.static.get(unit) or {}):
            return self.static[unit][address]
        return None


def _unit_from_key(key: str) -> int:
    # "unit_247" -> 247
    return int(str(key).rsplit("_", 1)[-1])
