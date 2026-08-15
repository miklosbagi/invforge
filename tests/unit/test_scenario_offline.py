"""Unit tests for Scenario's offline: window parsing/validation and
is_offline_at()/duration() -- no server, no network."""

from __future__ import annotations

import pytest

from invforge.core.scenario import Scenario
from invforge.profiles.sigenergy.firmwares.V100R001C21SPC116 import PROFILE


def _scenario(offline_windows: list[dict[str, float]]) -> Scenario:
    return Scenario("test-offline-inline", {"offline": offline_windows}, PROFILE)


def test_is_offline_at_respects_window_bounds():
    scenario = _scenario([{"start": 3, "end": 8}])
    assert scenario.is_offline_at(0) is False
    assert scenario.is_offline_at(2.999) is False
    assert scenario.is_offline_at(3) is True
    assert scenario.is_offline_at(7.999) is True
    assert scenario.is_offline_at(8) is False  # end is exclusive
    assert scenario.is_offline_at(100) is False


def test_no_offline_section_means_never_offline():
    scenario = Scenario("test-no-offline", {}, PROFILE)
    assert scenario.is_offline_at(0) is False
    assert scenario.is_offline_at(1000) is False
    assert scenario.duration() == 0.0


def test_duration_covers_the_last_offline_window_end():
    scenario = _scenario([{"start": 3, "end": 8}])
    assert scenario.duration() == 8.0


def test_multiple_windows():
    scenario = _scenario([{"start": 3, "end": 5}, {"start": 10, "end": 12}])
    assert scenario.is_offline_at(4) is True
    assert scenario.is_offline_at(7) is False
    assert scenario.is_offline_at(11) is True
    assert scenario.duration() == 12.0


def test_rejects_negative_start():
    with pytest.raises(ValueError, match="must be >= 0"):
        _scenario([{"start": -1, "end": 5}])


def test_rejects_end_not_after_start():
    with pytest.raises(ValueError, match="must be > start"):
        _scenario([{"start": 5, "end": 5}])
    with pytest.raises(ValueError, match="must be > start"):
        _scenario([{"start": 5, "end": 3}])
