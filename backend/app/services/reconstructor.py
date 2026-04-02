"""
Reconstructor — Qwen-Powered Table Fragment Reconstruction

Takes raw, fragmented ParameterRow objects from the table extractor and
sends them through Qwen to produce clean, complete structured rows.

Falls back to original extracted data if:
- Qwen is not loaded
- Qwen returns invalid JSON
- Qwen returns empty results
"""
import json
import logging
from app.models import ExtractedTable, ParameterRow
from app.services.ai_client import _is_loaded, _generate_local, is_qwen_available

logger = logging.getLogger(__name__)


# ── Prompt Builder ───────────────────────────────────────────────────

def _build_reconstruction_prompt(extracted_data: list[dict]) -> str:
    """Build the deterministic reconstruction prompt with actual data injected."""
    return f"""##############################
### SYSTEM ROLE ###
##############################

You are a deterministic data reconstruction engine for semiconductor datasheets.

You are NOT an AI assistant.
You must NOT think, infer, or guess.

Your ONLY task is to reorganize fragmented table data into complete structured rows.

##############################
### OBJECTIVE ###
##############################

Convert fragmented table records into structured rows with schema:

{{
  "parameter": "...",
  "value": "...",
  "unit": "...",
  "condition": "..."
}}

##############################
### STRICT RULES ###
##############################

1. Use ONLY the provided data
2. Do NOT hallucinate or guess missing values
3. Do NOT use external knowledge
4. Do NOT combine unrelated rows

##############################
### RECONSTRUCTION LOGIC ###
##############################

- If a row contains a parameter → it applies to following rows until a new parameter appears
- Merge fragments to form complete rows
- Attach condition, value, and unit correctly

MULTIPLE CONDITIONS:
- If same parameter has multiple conditions → create separate rows

VALID ROW:
- Must contain parameter + value + unit
- If missing → discard

IGNORE:
- Symbol-only rows (e.g., ID, VGS)

##############################
### INPUT DATA ###
##############################

{json.dumps(extracted_data, indent=2)}

##############################
### OUTPUT FORMAT ###
##############################

Return ONLY a JSON array:

[
  {{
    "parameter": "...",
    "value": "...",
    "unit": "...",
    "condition": "..."
  }}
]

No explanation.
No extra text.

##############################
### FINAL VALIDATION ###
##############################

- No missing value/unit
- No hallucinated data
- Only valid rows
"""


# ── Fragment Converter ───────────────────────────────────────────────

def _param_rows_to_fragments(params: list[ParameterRow]) -> list[dict]:
    """
    Convert ParameterRow objects into flat fragment dicts that Qwen can reason about.
    Preserves all information — parameter, values, unit, condition.
    """
    fragments = []
    for p in params:
        frag: dict = {}
        if p.parameter:
            frag["parameter"] = p.parameter
        if p.symbol:
            frag["symbol"] = p.symbol
        if p.unit:
            frag["unit"] = p.unit
        if p.conditions:
            frag["condition"] = p.conditions
        # Flatten values dict into individual fragment entries
        for value_type, value in p.values.items():
            if value:
                frag[f"value_{value_type}"] = value
        # If there's only one value key, simplify to "value"
        value_keys = [k for k in frag if k.startswith("value_")]
        if len(value_keys) == 1:
            frag["value"] = frag.pop(value_keys[0])
        if frag:
            fragments.append(frag)
    return fragments


# ── Reconstructed Row → ParameterRow ────────────────────────────────

def _reconstructed_to_param_row(item: dict, page: int = 0, section: str = "") -> ParameterRow:
    """Convert a Qwen-reconstructed dict back into a ParameterRow."""
    param = str(item.get("parameter", "")).strip()
    value = str(item.get("value", "")).strip()
    unit = str(item.get("unit", "")).strip()
    condition = str(item.get("condition", "")).strip()

    return ParameterRow(
        raw_cells=item,
        parameter=param,
        symbol="",
        values={"value": value} if value else {},
        unit=unit,
        conditions=condition,
    )


# ── JSON Extraction ──────────────────────────────────────────────────

def _extract_json_array(text: str) -> list[dict] | None:
    """
    Robustly extract a JSON array from Qwen's raw output text.
    Handles cases where Qwen wraps output in markdown code fences.
    """
    # Strip markdown code fences if present
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Remove first and last fence lines
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    # Find the first [ and last ]
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return None

    json_str = text[start:end + 1]
    try:
        result = json.loads(json_str)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError as e:
        logger.warning("JSON parse error from Qwen output: %s", e)
    return None


# ── Main Entry Point ─────────────────────────────────────────────────

def reconstruct_table_params(
    params: list[ParameterRow],
    table: ExtractedTable,
) -> list[ParameterRow]:
    """
    Attempt to reconstruct fragmented ParameterRows using Qwen.

    Steps:
    1. Convert ParameterRows → flat fragments
    2. Build reconstruction prompt
    3. Run Qwen inference (sync, called from thread-pool context)
    4. Parse Qwen JSON output
    5. Validate — discard rows missing parameter/value/unit
    6. Convert back to ParameterRow objects
    7. Fall back to originals if anything fails

    Args:
        params: Raw ParameterRow list from table_extractor
        table:  The source ExtractedTable (for page/section context)

    Returns:
        Reconstructed ParameterRow list (or original if Qwen unavailable/fails)
    """
    if not params:
        return params

    # Skip if Qwen not loaded — no API fallback for reconstruction
    if not _is_loaded:
        logger.debug("Qwen not loaded — skipping reconstruction for table on page %d", table.page)
        return params

    # Build fragment input
    fragments = _param_rows_to_fragments(params)
    if not fragments:
        return params

    logger.info(
        "🔧 Running Qwen reconstruction on %d fragments from page %d table",
        len(fragments), table.page
    )

    # Build and run prompt
    prompt = _build_reconstruction_prompt(fragments)
    try:
        # _generate_local expects (query, data) — pass prompt as query, empty dict as data
        # We override the message building by passing a pre-built prompt directly
        raw_output = _run_reconstruction(prompt)
    except Exception as e:
        logger.error("Qwen reconstruction inference failed: %s", e)
        return params

    if not raw_output:
        logger.warning("Qwen returned empty output — using original extraction")
        return params

    # Parse JSON
    reconstructed = _extract_json_array(raw_output)
    if reconstructed is None:
        logger.warning("Qwen output was not valid JSON — using original extraction")
        logger.debug("Raw Qwen output: %s", raw_output[:500])
        return params

    # Validate and filter rows
    valid_rows = []
    for item in reconstructed:
        p = str(item.get("parameter", "")).strip()
        v = str(item.get("value", "")).strip()
        u = str(item.get("unit", "")).strip()
        if p and v and u:
            valid_rows.append(_reconstructed_to_param_row(item, page=table.page, section=table.section))

    if not valid_rows:
        logger.warning("Qwen returned 0 valid rows — using original extraction")
        return params

    logger.info(
        "✅ Qwen reconstruction: %d fragments → %d clean rows",
        len(fragments), len(valid_rows)
    )
    return valid_rows


# ── Direct Prompt Runner ──────────────────────────────────────────────

def _run_reconstruction(prompt: str) -> str:
    """
    Run the reconstruction prompt directly through the loaded Qwen model.
    Uses a lightweight message structure — no system prompt injection needed
    since the full prompt is self-contained.
    """
    import torch
    from app.services.ai_client import _tokenizer, _model

    messages = [
        {"role": "user", "content": prompt},
    ]

    text = _tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = _tokenizer([text], return_tensors="pt").to(_model.device)

    with torch.no_grad():
        outputs = _model.generate(
            **inputs,
            max_new_tokens=1024,   # Reconstruction may produce many rows
            temperature=0.01,      # Near-zero temp for deterministic output
            top_p=0.95,
            do_sample=True,
        )

    generated = outputs[0][inputs.input_ids.shape[-1]:]
    return _tokenizer.decode(generated, skip_special_tokens=True).strip()
