"""
AI Client — Phase 6

Client for the Qwen 3.5 4B model running in Google Colab.
Sends structured data to Qwen for natural language formatting ONLY.
"""
import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a precise technical assistant for semiconductor datasheets.
You receive structured data extracted from a knowledge graph and must format it into
a clear, accurate natural language answer.

RULES:
1. ONLY use the data provided — DO NOT add any information.
2. If data is missing, say "not found in the datasheet".
3. Always include units when available.
4. Always include conditions/test conditions when available.
5. For tables, present data in a clean, readable format.
6. Never guess or approximate values.
"""


async def format_with_qwen(query: str, structured_data: dict) -> str:
    """
    Send structured data to the Qwen model in Colab for NL formatting.

    Args:
        query: The original user query
        structured_data: Data from the knowledge graph

    Returns:
        Formatted natural language answer from Qwen
    """
    if not settings.QWEN_API_URL:
        logger.warning("QWEN_API_URL not configured — returning raw data")
        return ""

    payload = {
        "query": query,
        "system_prompt": SYSTEM_PROMPT,
        "data": structured_data,
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
