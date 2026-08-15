from pathlib import Path

from invforge.core.profile import Profile

from .ramps import build_ramp_scenario_data
from .registers import DEFAULT_UNIT, REGISTERS

FIRMWARE = "V100R001C21SPC116"

# Confirmed empirically against real hardware (2026-08-14): a solo
# (count=1) read starting at 30281 (general_alarm7) fails with
# IllegalAddress, but a range read covering it that starts at or before
# 30280 succeeds. Unexplained by the spec text; reproduced here rather
# than silently working around it. See registers.py's module docstring.
NON_ANCHOR_ADDRESSES = frozenset({30281})

PROFILE = Profile(
    name="sigenergy",
    firmware=FIRMWARE,
    registers=REGISTERS,
    default_unit=DEFAULT_UNIT,
    scenarios_dir=Path(__file__).parent / "scenarios",
    ramp_builder=build_ramp_scenario_data,
    non_anchor_addresses=NON_ANCHOR_ADDRESSES,
)
