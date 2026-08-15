"""Engine-level smoke tests for the Sigenergy profile -- exercises the
vendor-agnostic core (profile/scenario/server) against real fixtures,
without opening a network socket."""

from __future__ import annotations

from invforge.core import server as sim_server
from invforge.core.registers import decode_numeric
from invforge.core.scenario import Scenario
from invforge.profiles.sigenergy.firmwares.V100R001C21SPC116 import PROFILE


def _load(name: str) -> Scenario:
    path = PROFILE.scenarios_dir / ("recorded" if "202" in name else "synthetic") / f"{name}.yaml"
    return Scenario.from_yaml(path, PROFILE)


def test_all_fixtures_load():
    for sub in ("recorded", "synthetic"):
        for path in sorted((PROFILE.scenarios_dir / sub).glob("*.yaml")):
            Scenario.from_yaml(path, PROFILE)  # must not raise


def test_recorded_capture_decodes_expected_soc_and_identity():
    scenario = _load("2026-08-13-idle-disconnected")
    blocks = sim_server.build_blocks(PROFILE)
    sim_server.apply_exceptions(blocks, scenario)
    sim_server.write_scenario_statics(blocks, PROFILE, scenario)

    soc_reg = PROFILE.find(247, 30014)
    words = blocks[247].getValues(30014, 1)
    assert decode_numeric(soc_reg, words) == 36.3

    model_reg = PROFILE.find(1, 30500)
    words = blocks[1].getValues(30500, model_reg.count)
    raw = b""
    for w in words:
        raw += bytes([(w >> 8) & 0xFF, w & 0xFF])
    assert raw.decode("utf-8").rstrip("\x00") == "SigenStor EC 12.0 TP"


def test_general_alarm_7_solo_read_fails_but_range_read_succeeds():
    """general_alarm7 (30281) is a real, in-range register (spec-
    confirmed, see registers.py's module docstring) -- but the real
    device rejects it as a read's *starting* address specifically,
    reproduced here via Profile.non_anchor_addresses, not a per-scenario
    exception. A solo read must still fail (matching real hardware);
    unlike the old modeling, a range read starting before it must now
    succeed (also matching real hardware, and previously broken --
    a blanket scenario-level `exceptions:` entry would have rejected
    this too, which is what got fixed)."""
    scenario = _load("2026-08-13-live-eps-discharge")
    blocks = sim_server.build_blocks(PROFILE)
    sim_server.apply_exceptions(blocks, scenario)
    sim_server.write_scenario_statics(blocks, PROFILE, scenario)

    assert blocks[247].validate(30281, 1) is False
    assert blocks[247].validate(30280, 2) is True


def test_exceptions_block_disables_an_in_range_register():
    """Regression test: a scenario's `exceptions:` block is keyed by
    "unit_<n>" strings, which must resolve to the block's int unit id
    (247) to have any effect. 30014 (ess_soc) is a real, in-range
    register, so this can only pass if the "unit_247" -> 247 key
    conversion actually runs."""
    scenario = Scenario(
        "test-exceptions-inline",
        {"exceptions": {"unit_247": {30014: {"function_code": 3, "exception_code": 2}}}},
        PROFILE,
    )
    blocks = sim_server.build_blocks(PROFILE)
    sim_server.apply_exceptions(blocks, scenario)

    assert blocks[247].validate(30014, 1) is False
    assert blocks[247].validate(30047, 1) is True  # an unrelated in-range register stays valid


def test_ramp_scenario_interpolates_soc_down():
    scenario = _load("ramp-discharge-100-to-0")
    v0 = scenario.value_at(247, 30014, 0.0)
    v_mid = scenario.value_at(247, 30014, 15.0)
    v_end = scenario.value_at(247, 30014, 60.0)
    assert v0 == 1000  # 100.0% raw
    assert 500 < v_mid < 1000
    assert v_end == 0
