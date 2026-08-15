"""A vendor profile: the set of registers, their units, and where a
profile's scenario fixtures live. Everything vendor-specific lives in
invforge/profiles/<vendor>/; this dataclass is what the vendor-agnostic
core (scenario.py, server.py, control_api.py) consumes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .ramp_params import RampParams
from .registers import RegisterDef


@dataclass(frozen=True)
class Profile:
    name: str
    firmware: str
    registers: list[RegisterDef]
    scenarios_dir: Path
    default_unit: int  # unit assumed when a scenario/control-API request omits one
    ramp_builder: Callable[[RampParams], dict[str, object]] | None = None
    # Addresses that are real, individually-documented registers but that
    # this firmware rejects as the STARTING address of a Modbus read
    # (any count) -- only valid when covered by a range read that starts
    # elsewhere. Confirmed empirically against real hardware for at least
    # one address (Sigenergy's general_alarm7, 30281); mechanism kept
    # generic since it's a real firmware behavior, not scenario data.
    non_anchor_addresses: frozenset[int] = frozenset()

    _by_unit_address: dict[int, dict[int, RegisterDef]] = field(init=False, repr=False, compare=False)
    _by_name: dict[str, RegisterDef] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        by_unit: dict[int, dict[int, RegisterDef]] = {}
        by_name: dict[str, RegisterDef] = {}
        for reg in self.registers:
            by_unit.setdefault(reg.unit, {})[reg.address] = reg
            by_name[reg.name] = reg
        object.__setattr__(self, "_by_unit_address", by_unit)
        object.__setattr__(self, "_by_name", by_name)

    @property
    def units(self) -> list[int]:
        return sorted(self._by_unit_address)

    def by_address(self, unit: int) -> dict[int, RegisterDef]:
        return self._by_unit_address.get(unit, {})

    def registers_for(self, unit: int) -> list[RegisterDef]:
        return list(self._by_unit_address.get(unit, {}).values())

    def find(self, unit: int, address: int) -> RegisterDef | None:
        return self._by_unit_address.get(unit, {}).get(address)

    def find_by_name(self, name: str) -> RegisterDef | None:
        return self._by_name.get(name)
