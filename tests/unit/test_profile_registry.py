"""Unit tests for invforge.profiles' vendor/firmware resolution."""

from __future__ import annotations

import pytest

from invforge import profiles


def test_get_resolves_known_vendor_and_firmware():
    profile = profiles.get("sigenergy", "V100R001C21SPC116")
    assert profile.name == "sigenergy"
    assert profile.firmware == "V100R001C21SPC116"


def test_get_unknown_vendor_lists_available():
    with pytest.raises(KeyError, match="unknown vendor 'bogus'.*sigenergy"):
        profiles.get("bogus", "whatever")


def test_get_unknown_firmware_lists_available():
    with pytest.raises(KeyError, match="unknown firmware 'bogus'.*V100R001C21SPC116"):
        profiles.get("sigenergy", "bogus")


def test_default_firmware_resolves_when_exactly_one():
    assert profiles.default_firmware("sigenergy") == "V100R001C21SPC116"


def test_default_firmware_unknown_vendor():
    with pytest.raises(KeyError, match="unknown vendor 'bogus'"):
        profiles.default_firmware("bogus")
