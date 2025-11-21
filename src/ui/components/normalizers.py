from __future__ import annotations

import re
from typing import Optional


def normalize_cadastral_ref(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = re.sub(r"[^A-Za-z0-9]", "", value).upper()
    return cleaned


def normalize_address(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = re.sub(r"\s+", " ", value.strip())
    return value.upper()


def validate_nif(nif: Optional[str]) -> bool:
    """Basic Spanish NIF/NIE validation."""
    if not nif:
        return False
    nif = nif.strip().upper()
    if not re.match(r"^[0-9XYZ][0-9]{7}[A-Z]$", nif):
        return False
    letters = "TRWAGMYFPDXBNJZSQVHLCKE"
    # Replace NIE leading letters
    if nif[0] == "X":
        number = "0" + nif[1:-1]
    elif nif[0] == "Y":
        number = "1" + nif[1:-1]
    elif nif[0] == "Z":
        number = "2" + nif[1:-1]
    else:
        number = nif[:-1]
    try:
        expected = letters[int(number) % 23]
    except ValueError:
        return False
    return expected == nif[-1]


__all__ = ["normalize_cadastral_ref", "normalize_address", "validate_nif"]
