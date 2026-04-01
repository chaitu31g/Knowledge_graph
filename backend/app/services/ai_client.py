"""
AI Client — Qwen 3.5 4B Integration

In local mode: sends HTTP request to Qwen API endpoint.
In Colab mode: this file gets patched to call the model directly.

The system prompt enforces strict rules:
- ONLY use provided data
- NEVER hallucinate
- Format as clean electronics assistant answers
"""
import json
import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

def is_qwen_available() -> bool:
    """Check if Qwen API URL is configured."""
    return bool(settings.QWEN_API_URL)

SYSTEM_PROMPT = """You are an expert electronics assistant.

You are given structured data extracted from a semiconductor datasheet via a Knowledge Graph.

Your job is to generate a clean, concise, and accurate answer based ONLY on the provided data.

## STRICT RULES
1. DO NOT hallucinate or guess missing values
2. DO NOT add any external knowledge
3. DO NOT include unrelated parameters
4. ONLY use the provided structured data
5. If no data is provided, respond: "No structured data found"

## OUTPUT FORMAT
1. Start with the parameter name (bold if possible)
2. Provide a short 1-line explanation of what this parameter means
3. List all values clearly with conditions and units

## EXAMPLE OUTPUT

**Continuous Drain Current (ID):**

This parameter defines the maximum continuous current the device can handle under specified conditions.

* At T_A = 25°C: 0.23 A
* At T_A = 70°C: 0.18 A

## SPECIAL CASES
- If multiple rows exist: list them clearly with bullet points
- If only one value: give a single clean sentence
- If conditions are missing: just show the value with unit
- For tables with min/typ/max: show all columns clearly
"""


def _build_user_message(query: str, data: dict) -> str:
    """Build the user message with query + structured data."""
    # Format the data cleanly for the model
    if "rows" in data and "columns" in data:
        # Table data — format as structured records
        formatted_rows = []
        for row in data["rows"]:
            record = {}
            for col in data["columns"]:
                val = row.get(col, "")
                if val:
                    record[col] = val
            if record:
                formatted_rows.append(record)

        data_str = json.dumps({
            "type": "parameter_table",
            "columns": data["columns"],
            "records": formatted_rows,
        }, indent=2)
    else:
        data_str = json.dumps(data, indent=2)

    return (
        f"User question: {query}\n\n"
        f"Knowledge Graph Data:\n{data_str}\n\n"
        f"Generate a clean, accurate answer using ONLY the data above. "
        f"Do not add any information that is not present in the data."
    )


async def format_with_qwen(query: str, structured_data: dict) -> str:
    """
    Send structured data to Qwen for natural language formatting.

    Returns formatted answer string, or empty string if Qwen is unavailable.
    """
    # If data is just an error message, don't bother with AI
    if isinstance(structured_data, dict) and "message" in structured_data:
        if "no " in structured_data["message"].lower() or "error" in structured_data["message"].lower():
            return ""

    if not settings.QWEN_API_URL:
        logger.info("QWEN_API_URL not configured — AI formatting disabled")
        return ""

    user_msg = _build_user_message(query, structured_data)

    payload = {
        "query": query,
        "system_prompt": SYSTEM_PROMPT,
        "data": structured_data,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings.QWEN_API_URL}/generate",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
            return result.get("answer", result.get("text", ""))
    except httpx.ConnectError:
        logger.error("Cannot connect to Qwen API at %s", settings.QWEN_API_URL)
        return ""
    except httpx.HTTPStatusError as e:
        logger.error("Qwen API error: %s", e.response.text)
        return ""
    except Exception as e:
        logger.error("Qwen API unexpected error: %s", e)
        return ""
