"""Vendor-agnostic register model shared by every profile.

A vendor profile (invforge/profiles/<vendor>/) supplies a list of
RegisterDef plus a default Modbus unit id; this module only knows how to
encode/decode/interpolate values generically, with no vendor-specific
knowledge.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DType(Enum):
    U16 = "U16"
    S16 = "S16"
    U32 = "U32"
    S32 = "S32"
    STRING = "STRING"


@dataclass(frozen=True)
class RegisterDef:
    address: int
    name: str
    count: int  # in 16-bit registers
    dtype: DType
    unit: int  # Modbus slave/unit id this register lives on
    gain: float = 1
    dynamic: bool = False  # tickable by a scenario timeseries vs. fixed-at-load static


def encode_numeric(reg: RegisterDef, decoded_value: float) -> list[int]:
    """decoded (real-world) value -> raw 16-bit register words, big-endian."""
    raw = round(decoded_value * reg.gain)
    if reg.dtype in (DType.U16, DType.S16):
        return [raw & 0xFFFF]
    if reg.dtype in (DType.U32, DType.S32):
        raw &= 0xFFFFFFFF
        return [(raw >> 16) & 0xFFFF, raw & 0xFFFF]
    raise ValueError(f"encode_numeric called on non-numeric register {reg.name}")


def encode_string(reg: RegisterDef, text: str) -> list[int]:
    data = text.encode("utf-8")
    data = data[: reg.count * 2].ljust(reg.count * 2, b"\x00")
    return [(data[i] << 8) | data[i + 1] for i in range(0, len(data), 2)]


def combine_words(reg: RegisterDef, words: list[int]) -> int:
    """Raw 16-bit words -> a single combined integer (sign-applied for
    S32/S16, gain NOT applied) -- the natural unit to linearly interpolate
    a ramp scenario in, since it's just the wire value."""
    if reg.dtype in (DType.U16, DType.S16):
        v = words[0]
        if reg.dtype == DType.S16 and v >= 0x8000:
            v -= 0x10000
        return v
    combined = (words[0] << 16) | words[1]
    if reg.dtype == DType.S32 and combined >= 0x80000000:
        combined -= 0x100000000
    return combined


def split_to_words(reg: RegisterDef, combined: int) -> list[int]:
    """Inverse of combine_words."""
    if reg.dtype in (DType.U16, DType.S16):
        return [combined & 0xFFFF]
    combined &= 0xFFFFFFFF
    return [(combined >> 16) & 0xFFFF, combined & 0xFFFF]


def normalize_scenario_value(reg: RegisterDef, value: int | list[int]) -> int:
    """A scenario YAML numeric entry is either a bare int (single-register
    fields) or a [hi, lo] word list (multi-register fields) -- always the
    raw wire value, never gain-divided. Normalize either shape to the
    combined-integer form combine_words()/split_to_words() work in."""
    if isinstance(value, list):
        return combine_words(reg, value)
    return combine_words(reg, [value & 0xFFFF]) if reg.count == 1 else value


def decode_numeric(reg: RegisterDef, raw_words: list[int]) -> float:
    if reg.dtype in (DType.U16, DType.S16):
        v = raw_words[0]
        if reg.dtype == DType.S16 and v >= 0x8000:
            v -= 0x10000
    else:
        combined = (raw_words[0] << 16) | raw_words[1]
        v = combined
        if reg.dtype == DType.S32 and v >= 0x80000000:
            v -= 0x100000000
    return v / reg.gain
