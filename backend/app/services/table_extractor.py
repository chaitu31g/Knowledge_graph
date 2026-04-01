"""
Table Extractor — Phase 2

Dynamically extracts parameters from tables WITHOUT assuming any fixed schema.
Handles:
- Single value columns
- Min/Typ/Max columns (when they exist)
- Range values ("1.2 to 3.3")
- Value+Unit splitting
"""
import re
from typing import Optional

from app.models import ExtractedTable, ParameterRow
from app.utils import split_value_unit


# ── Column Classification ──────────────────────────────────────────

# Keywords that identify column roles (case-insensitive matching)
_PARAMETER_KEYWORDS = ["parameter", "characteristic", "description", "item", "name"]
_SYMBOL_KEYWORDS = ["symbol", "sym", "abbr"]
_UNIT_KEYWORDS = ["unit", "units"]
_CONDITION_KEYWORDS = ["condition", "conditions", "test condition", "note", "remark", "comment"]
_VALUE_KEYWORDS = ["value", "rating", "limit", "specification"]
_MIN_KEYWORDS = ["min", "minimum", "min."]
_TYP_KEYWORDS = ["typ", "typical", "typ.", "nom", "nominal"]
_MAX_KEYWORDS = ["max", "maximum", "max."]


def classify_columns(headers: list[str]) -> dict[int, str]:
    """
    Classify each column index to a role: parameter, symbol, unit, condition,
    min, typ, max, value, or unknown.

    Returns {col_index: role_name}
    """
    roles: dict[int, str] = {}

    for idx, header in enumerate(headers):
        h = header.lower().strip()
        if not h:
            roles[idx] = "unknown"
            continue

        if any(kw in h for kw in _PARAMETER_KEYWORDS):
            roles[idx] = "parameter"
        elif any(kw == h for kw in _SYMBOL_KEYWORDS):
            roles[idx] = "symbol"
        elif any(kw == h for kw in _UNIT_KEYWORDS):
            roles[idx] = "unit"
        elif any(kw in h for kw in _CONDITION_KEYWORDS):
            roles[idx] = "condition"
        elif any(kw == h for kw in _MIN_KEYWORDS):
            roles[idx] = "min"
        elif any(kw == h for kw in _TYP_KEYWORDS):
            roles[idx] = "typ"
        elif any(kw == h for kw in _MAX_KEYWORDS):
            roles[idx] = "max"
        elif any(kw in h for kw in _VALUE_KEYWORDS):
            roles[idx] = "value"
        else:
            roles[idx] = "unknown"

    # If no 'parameter' column found, first text-heavy column is likely parameter
    if "parameter" not in roles.values():
        roles[0] = "parameter"

    # If no value-type columns found, unclassified columns become 'value'
    has_value_cols = any(
        r in ("min", "typ", "max", "value") for r in roles.values()
    )
    if not has_value_cols:
        for idx, role in roles.items():
            if role == "unknown":
                roles[idx] = "value"
                break

    return roles


def extract_parameters(table: ExtractedTable) -> list[ParameterRow]:
    """
    Extract structured ParameterRow objects from a table.
    Fully dynamic — adapts to whatever columns exist.
    """
    if not table.headers or not table.rows:
        return []

    roles = classify_columns(table.headers)
    results: list[ParameterRow] = []

    for row in table.rows:
        # Build raw_cells mapping
        raw_cells = {}
        for idx, header in enumerate(table.headers):
            if idx < len(row):
                raw_cells[header] = row[idx]

        # Extract fields based on column roles
        param_name = ""
        symbol = ""
        unit = ""
        conditions = ""
        values: dict[str, str] = {}

        for idx, role in roles.items():
            if idx >= len(row):
                continue
            cell = row[idx].strip()
            if not cell:
                continue

            if role == "parameter":
                param_name = cell
            elif role == "symbol":
                symbol = cell
            elif role == "unit":
                unit = cell
            elif role == "condition":
                conditions = cell
            elif role in ("min", "typ", "max"):
                val, detected_unit = split_value_unit(cell)
                values[role] = val
                if detected_unit and not unit:
                    unit = detected_unit
            elif role == "value":
                val, detected_unit = split_value_unit(cell)
                header_name = table.headers[idx] if idx < len(table.headers) else "value"
                values[header_name] = val
                if detected_unit and not unit:
                    unit = detected_unit
            elif role == "unknown":
                # Store under original header name
                header_name = table.headers[idx] if idx < len(table.headers) else f"col_{idx}"
                values[header_name] = cell

        # Skip rows with no parameter name
        if not param_name:
            continue

        results.append(ParameterRow(
            raw_cells=raw_cells,
            parameter=param_name,
            symbol=symbol,
            values=values,
            unit=unit,
            conditions=conditions,
        ))

    return results
