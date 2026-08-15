"""HTTP+JSON control API for the simulator -- the test runner's remote
control channel. Chosen over gRPC deliberately: this is low-throughput,
single-consumer, and this way it's `curl`-able for free while debugging a
failed test.

Endpoints:
  GET  /health              -> {"status": "ok"}
  GET  /scenarios            -> {"library": {name: relative_path, ...},
                                  "generators": [<naming-pattern>, ...]}
  POST /scenario {name, speed=1.0}
      Loads and starts playing back a named scenario's timeseries.
      `name` resolves against the static YAML library first, then the
      parametric generator (see core/generator.py) if no library
      fixture matches -- e.g. "linear-drain-100-to-0-60s".
  POST /state {registers: {"<address>": <raw>, "<unit>:<address>": <raw>, ...}}
      Instant override -- writes directly into the datastore right now
      and freezes the ticker (mode="manual") so nothing overwrites it
      until the next /scenario or /state call. A bare address key is
      assumed to mean the profile's default_unit; use "<unit>:<address>"
      to target another unit explicitly.
  GET  /state                -> current raw+decoded value of every known
                                 register on every unit, plus connectivity
                                 status, for debugging a failed test.
  POST /fault {"connectivity": "offline"|"online"|"auto"}
      On-demand connection-level fault injection -- forces the Modbus
      TCP listener offline/online, or clears back to scenario-driven
      ("auto"). Sticky: takes precedence over a scenario's own
      `offline:` windows until cleared or a new scenario is loaded (see
      /scenario, which resets it to "auto").
"""

from __future__ import annotations

from typing import Literal, TypeGuard

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from . import server as sim_server
from .connectivity import ConnectivityController
from .profile import Profile
from .registers import DType, RegisterDef, decode_numeric, normalize_scenario_value
from .state import SimState, list_scenarios, resolve_scenario


class ScenarioRequest(BaseModel):
    name: str
    speed: float = 1.0


class StateRequest(BaseModel):
    registers: dict[str, object]  # "<address>" or "<unit>:<address>" -> raw int | [hi, lo]


class FaultRequest(BaseModel):
    connectivity: Literal["offline", "online", "auto"]


def create_app(
    profile: Profile,
    blocks: dict[int, sim_server.IllegalAwareBlock],
    state: SimState,
    connectivity: ConnectivityController,
) -> FastAPI:
    app = FastAPI(title=f"invforge control API ({profile.name})")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/scenarios")
    def scenarios() -> dict[str, object]:
        generator_patterns = ["linear-<drain|charge>-<start>-to-<end>-<duration>s"] if profile.ramp_builder else []
        return {"library": list_scenarios(profile.scenarios_dir), "generators": generator_patterns}

    @app.post("/scenario")
    def load_scenario(req: ScenarioRequest) -> dict[str, object]:
        try:
            scenario = resolve_scenario(req.name, profile)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        sim_server.apply_exceptions(blocks, scenario)
        sim_server.write_scenario_statics(blocks, profile, scenario)
        state.set_scenario(scenario, speed=req.speed)
        connectivity.set_override(None)  # a fresh scenario starts in "auto" -- no stale forced fault carries over
        return {"loaded": req.name, "duration": scenario.duration(), "speed": req.speed}

    @app.post("/fault")
    def set_fault(req: FaultRequest) -> dict[str, object]:
        override = {"offline": True, "online": False, "auto": None}[req.connectivity]
        try:
            connectivity.set_override(override)
        except TimeoutError as e:
            raise HTTPException(status_code=500, detail=f"connectivity change did not apply in time: {e}") from e
        return {"connectivity": req.connectivity}

    @app.post("/state")
    def set_state(req: StateRequest) -> dict[str, object]:
        by_unit: dict[int, dict[int, int]] = {}
        for key, raw_value in req.registers.items():
            unit, addr = _parse_key(key, profile.default_unit)
            reg = profile.find(unit, addr)
            if reg is None:
                raise HTTPException(status_code=400, detail=f"unknown register {unit}:{addr}")
            if reg.dtype == DType.STRING:
                raise HTTPException(
                    status_code=400, detail=f"{reg.name} is a string register, use /scenario static instead"
                )
            if not _is_raw_register_value(raw_value):
                raise HTTPException(
                    status_code=400, detail=f"{reg.name}: expected an int or [hi, lo] word list, got {raw_value!r}"
                )
            by_unit.setdefault(unit, {})[addr] = normalize_scenario_value(reg, raw_value)
        for unit, values in by_unit.items():
            sim_server.write_manual_registers(blocks, profile, unit, values)
        state.freeze_manual()
        applied = {f"{u}:{a}": v for u, vals in by_unit.items() for a, v in vals.items()}
        return {"applied": applied, "mode": "manual"}

    @app.get("/state")
    def get_state() -> dict[str, object]:
        out = {}
        for unit, block in blocks.items():
            for reg in profile.registers_for(unit):
                out[f"{unit}:{reg.name}"] = _read_register(block, reg)
        mode, scenario, _, speed = state.snapshot()
        return {
            "mode": mode,
            "scenario": scenario.name if scenario else None,
            "speed": speed,
            "connectivity": connectivity.status(),
            "registers": out,
        }

    return app


def _parse_key(key: str, default_unit: int) -> tuple[int, int]:
    if ":" in key:
        unit_s, addr_s = key.split(":", 1)
        return int(unit_s), int(addr_s)
    return default_unit, int(key)


def _is_raw_register_value(value: object) -> TypeGuard[int | list[int]]:
    """A POST /state raw value is either a bare int or a [hi, lo] word
    list -- the same shape normalize_scenario_value() expects."""
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return isinstance(value, list) and all(isinstance(v, int) and not isinstance(v, bool) for v in value)


def _read_register(block: sim_server.IllegalAwareBlock, reg: RegisterDef) -> dict[str, object]:
    if not block.validate(reg.address, reg.count):
        return {"address": reg.address, "illegal": True}
    raw_words = block.getValues(reg.address, reg.count)
    if reg.dtype == DType.STRING:
        raw_bytes = b""
        for w in raw_words:
            raw_bytes += bytes([(w >> 8) & 0xFF, w & 0xFF])
        text = raw_bytes.decode("utf-8", errors="replace").rstrip("\x00")
        return {"address": reg.address, "text": text}
    decoded = decode_numeric(reg, raw_words)
    return {"address": reg.address, "raw": raw_words, "decoded": decoded}
