"""Unit tests for the parametric ramp-scenario generator
(core/generator.py) against the Sigenergy profile's ramp_builder."""

from __future__ import annotations

import pytest

from invforge.core.generator import resolve_generated
from invforge.profiles.sigenergy.firmwares.V100R001C21SPC116 import PROFILE


def test_non_matching_name_returns_none():
    assert resolve_generated("2026-08-13-idle-disconnected", PROFILE) is None
    assert resolve_generated("not-a-ramp-at-all", PROFILE) is None


def test_valid_drain_ramp_interpolates_between_endpoints():
    scenario = resolve_generated("linear-drain-100-to-0-60s", PROFILE)
    assert scenario is not None
    assert scenario.duration() == 60.0
    v0 = scenario.value_at(247, 30014, 0.0)
    v_mid = scenario.value_at(247, 30014, 30.0)
    v_end = scenario.value_at(247, 30014, 60.0)
    assert v0 == 1000  # 100.0% raw
    assert v_end == 0
    assert 0 < v_mid < 1000


def test_valid_charge_ramp():
    scenario = resolve_generated("linear-charge-20-to-80-30s", PROFILE)
    assert scenario is not None
    assert scenario.value_at(247, 30014, 0.0) == 200
    assert scenario.value_at(247, 30014, 30.0) == 800


def test_duration_must_be_positive():
    with pytest.raises(ValueError, match="duration must be > 0"):
        resolve_generated("linear-drain-100-to-0-0s", PROFILE)


def test_drain_direction_must_actually_decrease():
    with pytest.raises(ValueError, match="direction 'drain'"):
        resolve_generated("linear-drain-0-to-100-60s", PROFILE)


def test_charge_direction_must_actually_increase():
    with pytest.raises(ValueError, match="direction 'charge'"):
        resolve_generated("linear-charge-100-to-0-60s", PROFILE)
