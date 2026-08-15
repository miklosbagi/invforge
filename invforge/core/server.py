"""Fake Modbus TCP datastore construction and the background register
ticker. Vendor-agnostic: builds one datastore block per unit id present
in a Profile's registers. No CLI/argparse here (see __main__.py) -- this
module is a library used by the control API and by
core/connectivity.py, which owns the actual Modbus TCP server's
online/offline lifecycle.
"""

from __future__ import annotations

import threading
import time

from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext, ModbusSlaveContext

from .profile import Profile
from .registers import DType, encode_string, split_to_words
from .scenario import Scenario
from .state import SimState


class IllegalAwareBlock(ModbusSequentialDataBlock):  # type: ignore[misc]
    """Same as ModbusSequentialDataBlock, but with two ways an address can
    still fail validation despite being in the block's numeric range:

    - `illegal_addresses`: scenario-driven (see apply_exceptions()) --
      e.g. a register a real device 400s on for a specific captured
      scenario. Any address in the requested range fails the read.
    - `non_anchor_addresses`: profile-driven, permanent regardless of
      scenario -- addresses real firmware rejects as a read's STARTING
      address specifically (confirmed empirically for at least one
      Sigenergy register), even though covering them via a range read
      that starts elsewhere works fine. Only the requested start address
      is checked against this set, not the whole range.
    """

    def __init__(
        self,
        address: int,
        values: list[int],
        illegal_addresses: set[int] | None = None,
        non_anchor_addresses: frozenset[int] = frozenset(),
    ) -> None:
        super().__init__(address, values)
        self.illegal_addresses = illegal_addresses or set()
        self.non_anchor_addresses = non_anchor_addresses

    def validate(self, address: int, count: int = 1) -> bool:
        for a in range(address, address + count):
            if a in self.illegal_addresses:
                return False
        if address in self.non_anchor_addresses:
            return False
        return bool(super().validate(address, count))


def build_blocks(profile: Profile) -> dict[int, IllegalAwareBlock]:
    """Empty (all-zero) datastore block per unit id in the profile. Illegal
    addresses (e.g. a register a real device 400s on) get set separately
    via apply_exceptions(), since they can vary per scenario."""
    blocks: dict[int, IllegalAwareBlock] = {}
    for unit in profile.units:
        regs = profile.registers_for(unit)
        start = min(r.address for r in regs)
        end = max(r.address + r.count for r in regs)  # exclusive
        blocks[unit] = IllegalAwareBlock(start, [0] * (end - start), non_anchor_addresses=profile.non_anchor_addresses)
    return blocks


def build_context(blocks: dict[int, IllegalAwareBlock]) -> ModbusServerContext:
    slaves = {unit: ModbusSlaveContext(hr=block, zero_mode=True) for unit, block in blocks.items()}
    return ModbusServerContext(slaves=slaves, single=False)


def apply_exceptions(blocks: dict[int, IllegalAwareBlock], scenario: Scenario) -> None:
    for unit, block in blocks.items():
        block.illegal_addresses = set((scenario.exceptions.get(unit) or {}).keys())


def write_scenario_statics(blocks: dict[int, IllegalAwareBlock], profile: Profile, scenario: Scenario) -> None:
    """One-time write of every register's t=0 value (covers both
    genuinely-static registers and any dynamic register the scenario only
    defined in its `static:` block) plus any identification strings."""
    for unit, block in blocks.items():
        for reg in profile.registers_for(unit):
            if reg.dtype == DType.STRING:
                text = (scenario.static.get(unit) or {}).get(reg.address)
                if text is None:
                    continue
                block.setValues(reg.address, encode_string(reg, str(text)))
            else:
                raw = scenario.value_at(unit, reg.address, 0.0)
                if raw is None:
                    continue
                assert isinstance(raw, int), f"{reg.name} is non-STRING but scenario value is {type(raw)}"
                block.setValues(reg.address, split_to_words(reg, raw))


def write_manual_registers(
    blocks: dict[int, IllegalAwareBlock], profile: Profile, unit: int, values: dict[int, int]
) -> None:
    """POST /state -- direct, immediate write, no scenario/interpolation."""
    block = blocks.get(unit)
    if block is None:
        return
    for address, raw in values.items():
        reg = profile.find(unit, address)
        if reg is None or reg.dtype == DType.STRING:
            continue
        block.setValues(reg.address, split_to_words(reg, raw))


def elapsed_seconds(scenario: Scenario, start_time: float, speed: float) -> float:
    """Elapsed time into a scenario's playback, wrapped to its duration
    once it loops -- the one time model both the register ticker and
    core/connectivity.py's offline-window watcher use, so they can never
    disagree about "what time is it" within a running scenario."""
    elapsed = (time.monotonic() - start_time) * speed
    duration = scenario.duration()
    if duration > 0 and elapsed > duration:
        elapsed = elapsed % duration
    return elapsed


def run_ticker(
    state: SimState,
    blocks: dict[int, IllegalAwareBlock],
    profile: Profile,
    tick_interval: float,
    stop_event: threading.Event,
) -> None:
    while not stop_event.is_set():
        mode, scenario, start_time, speed = state.snapshot()
        if mode == "scenario" and scenario is not None:
            elapsed = elapsed_seconds(scenario, start_time, speed)
            for unit, block in blocks.items():
                for reg in profile.registers_for(unit):
                    if not reg.dynamic:
                        continue
                    raw = scenario.value_at(unit, reg.address, elapsed)
                    if raw is None:
                        continue
                    assert isinstance(raw, int), f"{reg.name} is dynamic but scenario value is {type(raw)}"
                    block.setValues(reg.address, split_to_words(reg, raw))
        # mode == "manual": ticker does nothing, datastore already holds
        # whatever /state wrote directly.
        stop_event.wait(tick_interval)
