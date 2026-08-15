from invforge.core.profile import Profile


def _load_firmwares() -> dict[str, Profile]:
    from .firmwares import V100R001C21SPC116

    return {p.firmware: p for p in [V100R001C21SPC116.PROFILE]}


FIRMWARES: dict[str, Profile] = _load_firmwares()
