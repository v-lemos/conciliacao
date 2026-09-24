"""Strict parsing helpers for monetary values shared across file formats."""

import math
import re

import pandas as pd


def parse_amount(value):
    """Parse a monetary value; return None for blanks and reject malformed values."""
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"Montante inválido: {value!r}")
        return number

    text = str(value).strip().replace("€", "").replace(" ", "")
    if not text:
        return None
    if not re.fullmatch(r"[+-]?(?:\d{1,3}(?:\.\d{3})+|\d+)?(?:,\d+|\.\d+)?", text):
        raise ValueError(f"Montante inválido: {value!r}")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        number = float(text)
    except ValueError as exc:
        raise ValueError(f"Montante inválido: {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"Montante inválido: {value!r}")
    return number
