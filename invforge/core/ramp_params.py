"""RampParams lives in its own module, separate from generator.py, so
that profile.py (which needs the type for Profile.ramp_builder) doesn't
have to import back into generator.py (which imports profile.py) --
avoids a cyclic import rather than working around one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class RampParams:
    direction: Literal["drain", "charge"]
    start_pct: float
    end_pct: float
    duration_s: float
