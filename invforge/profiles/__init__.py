"""Vendor/firmware profile registry. Each vendor subpackage exposes a
module-level `FIRMWARES: dict[str, invforge.core.profile.Profile]`,
keyed by the exact firmware string that Profile's own `firmware` field
carries; add it to `_load()` below to register it under `--vendor
<name>`.
"""

from __future__ import annotations

from invforge.core.profile import Profile


def _load() -> dict[str, dict[str, Profile]]:
    from . import sigenergy

    return {"sigenergy": sigenergy.FIRMWARES}


VENDORS: dict[str, dict[str, Profile]] = _load()


def get(vendor: str, firmware: str) -> Profile:
    try:
        firmwares = VENDORS[vendor]
    except KeyError:
        raise KeyError(f"unknown vendor {vendor!r}, available: {sorted(VENDORS)}") from None
    try:
        return firmwares[firmware]
    except KeyError:
        raise KeyError(f"unknown firmware {firmware!r} for vendor {vendor!r}, available: {sorted(firmwares)}") from None


def default_firmware(vendor: str) -> str:
    """Only resolvable when a vendor has exactly one confirmed firmware --
    once a second one is registered, --firmware becomes effectively
    required rather than silently guessed."""
    try:
        firmwares = VENDORS[vendor]
    except KeyError:
        raise KeyError(f"unknown vendor {vendor!r}, available: {sorted(VENDORS)}") from None
    if len(firmwares) != 1:
        raise KeyError(
            f"vendor {vendor!r} has {len(firmwares)} known firmwares, --firmware is required, "
            f"available: {sorted(firmwares)}"
        )
    return next(iter(firmwares))
