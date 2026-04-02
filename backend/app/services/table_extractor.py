"""
Table Extractor — Phase 2

Dynamically extracts parameters from tables WITHOUT assuming any fixed schema.
Handles:
- Single value columns
- Min/Typ/Max columns (when they exist)
- Range values ("1.2 to 3.3")
- Value+Unit splitting
- Multi-row parameter entries (parameter propagation)
- Junk/symbol row filtering
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


# ── Junk Filter ────────────────────────────────────────────────────────

# Known garbage fragments produced by broken PDF table extraction
_JUNK_FRAGMENTS = {
    "limited by", "resistanc", "single puls", "parameter", "symbol",
    "condition", "conditions", "value", "unit", "min", "typ", "max",
    "note", "remarks", "item", "id", "vds", "vgs", "rds", "i d",
    "v ds", "r ds(on),max",
}


def _is_junk_param(name: str) -> bool:
    """
    Return True if the parameter name is clearly a junk/symbol row
    that should not be stored as a real parameter.
    """
    n = name.strip().lower()

    # Empty
    if not n:
        return True

    # Known garbage fragments (exact match)
    if n in _JUNK_FRAGMENTS:
        return True

    # Pure electrical symbols: 1–6 chars, all uppercase + digits/brackets
    # e.g. "ID", "VGS", "VDS", "RDS", "CISS"
    if re.match(r'^[A-Z][A-Z0-9()\-]{0,5}$', name.strip()):
        return True

    # Starts with a known symbol prefix pattern like "I D", "V DS"
    if re.match(r'^[IVRCQP]\s+[A-Z]', name.strip()):
        return True

    return False


# ── Parameter Extraction ───────────────────────────────────────────────

def extract_parameters(table: ExtractedTable) -> list[ParameterRow]:
    """
    Extract structured ParameterRow objects from a table.
    Fully dynamic — adapts to whatever columns exist.

    Key behaviours:
    - Parameter propagation: if a row has no parameter cell, it inherits
      the last seen parameter. This handles multi-row entries like:

        Continuous drain current | ID | TA=25°C | 0.23 | A
                                 |    | TA=70°C | 0.18 |

      Both rows are captured, the second inheriting the parameter + unit.

    - Symbol carry-forward: symbol (e.g. ID) persists across continuation rows.
    - Unit carry-forward: unit persists when continuation rows omit it.
    - Junk filtering: skips rows that are pure symbols or garbage fragments
      (e.g. "I D", "V DS", "limited by", "resistanc", "single puls").
    """
    if not table.headers or not table.rows:
        return []

    roles = classify_columns(table.headers)
    results: list[ParameterRow] = []

    # ── Carry-forward state ─────────────────────────────────────────
    last_param: str = ""
    last_symbol: str = ""
    last_unit: str = ""

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

        # ── Parameter propagation ───────────────────────────────────
        if param_name:
            # This row introduces a new parameter — filter junk first
            if _is_junk_param(param_name):
                continue
            # Update carry-forward state
            last_param = param_name
            if symbol:
                last_symbol = symbol
            if unit:
                last_unit = unit
        else:
            # Continuation row — inherit last seen parameter context
            if not last_param:
                continue  # No parameter context yet — skip
            param_name = last_param
            if not symbol:
                symbol = last_symbol
            if not unit:
                unit = last_unit

        # Refresh carry-forward if this row provided new symbol/unit
        if unit:
            last_unit = unit
        if symbol:
            last_symbol = symbol

        # Skip pure parameter-name rows with no values/conditions
        # (they only serve to set carry-forward state)
        if not values and not conditions:
            continue

        # Skip rows that have values but no unit — incomplete, can't store
        if values and not unit:
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
