"""
Regex and text utilities for value/unit splitting and text cleaning.
"""
import re
from typing import Optional


# ── Value / Unit Splitting ──────────────────────────────────────────

# Common electrical/semiconductor units (order matters – longest first)
_UNIT_PATTERNS = [
    r"µA/MHz", r"μA/MHz", r"uA/MHz",
    r"mA/MHz",
    r"nA", r"µA", r"μA", r"uA", r"mA", r"A",
    r"nV", r"µV", r"μV", r"uV", r"mV", r"kV", r"V",
    r"nW", r"µW", r"μW", r"uW", r"mW", r"W",
    r"nF", r"µF", r"μF", r"uF", r"pF", r"F",
    r"nH", r"µH", r"μH", r"uH", r"mH", r"H",
    r"nS", r"µS", r"μS", r"uS", r"mS", r"S",
    r"ns", r"µs", r"μs", r"us", r"ms", r"s",
    r"MHz", r"kHz", r"Hz", r"GHz",
    r"MΩ", r"kΩ", r"Ω", r"MOhm", r"kOhm", r"Ohm",
    r"dBm", r"dB",
    r"°C", r"℃", r"K",
    r"ppm/°C", r"ppm/℃", r"ppm",
    r"LSB", r"Bits?", r"bits?",
    r"%",
]

_UNIT_RE = re.compile(
    r"^\s*([-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)\s*(" + "|".join(_UNIT_PATTERNS) + r")\s*$"
)

_RANGE_RE = re.compile(
    r"^\s*([-+]?\d+\.?\d*)\s*(?:to|~|–|—|-)\s*([-+]?\d+\.?\d*)\s*("
    + "|".join(_UNIT_PATTERNS)
    + r")?\s*$",
    re.IGNORECASE,
)


def split_value_unit(raw: str) -> tuple[str, str]:
    """
    Split a raw cell value into (value, unit).
    Returns (raw, "") if no unit detected.
    """
    if not raw or not raw.strip():
        return ("", "")

    raw = raw.strip()

    # Try direct value+unit match
    m = _UNIT_RE.match(raw)
    if m:
        return (m.group(1), m.group(2))

    # Try range match: "1.2 to 3.4 V"
    m = _RANGE_RE.match(raw)
    if m:
        val = f"{m.group(1)} to {m.group(2)}"
        unit = m.group(3) or ""
        return (val, unit)

    # No match — return as-is
    return (raw, "")


# ── Text Cleaning ───────────────────────────────────────────────────

def clean_text(text: str) -> str:
    """Remove excessive whitespace and control characters."""
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def extract_section_title(text: str) -> Optional[str]:
    """
    Try to extract a section title from the first line of a text block.
    Returns None if the first line doesn't look like a title.
    """
    lines = text.strip().split("\n")
    if not lines:
        return None
    first = lines[0].strip()
    # Heuristic: short line, possibly all-caps or title-case, no trailing period
    if len(first) < 80 and not first.endswith(".") and first[0].isupper():
        return first
    return None


def detect_component_name(texts: list[str]) -> str:
    """
    Try to detect the component/part name from the first few text blocks.
    Looks for patterns like part numbers (e.g., LM317, TPS54331).
    """
    part_number_re = re.compile(
        r"\b([A-Z]{2,5}\d{3,6}[A-Z]?(?:[-/][A-Z0-9]+)?)\b"
    )
    for text in texts[:5]:
        m = part_number_re.search(text)
        if m:
            return m.group(1)
    return ""
