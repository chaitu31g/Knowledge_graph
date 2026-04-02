"""
AI Client — Qwen 3.5 4B Integration

Supports two modes of operation:
1. Local in-process: Downloads and loads Qwen 3.5 4B directly via HuggingFace transformers (recommended for Colab/GPU).
2. HTTP Endpoint: Sends data to an external Qwen API (if QWEN_API_URL is set).
"""
import json
import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

# ── Local Model State ───────────────────────────────────────────────
_model = None
_tokenizer = None
_is_loaded = False


def init_qwen_local():
    """
    Initialize Qwen 3.5 4B locally within the FastAPI process.
    Called during app startup if ENABLE_LOCAL_QWEN is True.
    """
    global _model, _tokenizer, _is_loaded
    if not settings.ENABLE_LOCAL_QWEN:
        logger.info("Local Qwen 3.5 4B is disabled via config.")
        return

    logger.info("Initializing local Qwen 3.5 4B model (this may take a few minutes)...")
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        # Qwen2.5-4B does NOT exist — real sizes: 0.5B, 1.5B, 3B, 7B, 32B
        # Use 7B for best quality on Colab T4, or 3B if you hit OOM
        model_name = getattr(settings, "QWEN_MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct")
        _tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        
        # Load efficiently on Colab GPU if available
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto" if torch.cuda.is_available() else None,
            trust_remote_code=True,
        )
        if not torch.cuda.is_available():
            _model = _model.to(device)
            
        _is_loaded = True
        logger.info(f"✅ Local Qwen2.5 4B-Instruct successfully loaded on {device}")
    except ImportError as e:
        logger.error(f"❌ Failed to load Qwen: missing package — {e}. Install with: pip install transformers torch")
    except Exception as e:
        logger.error(f"❌ Failed to load local Qwen model: {type(e).__name__}: {e}")


def is_qwen_available() -> bool:
    """Check if Qwen is available (either local or via API)."""
    return _is_loaded or bool(settings.QWEN_API_URL)


# ── System Prompt & Formatting ──────────────────────────────────────

SYSTEM_PROMPT = """You are an expert electronics assistant.

You are given extracted data from a semiconductor datasheet via a Knowledge Graph.
The data may be structured parameter tables OR unstructured text sections.

Your job is to generate a clean, concise, and accurate answer based ONLY on the provided data.

## STRICT RULES
1. DO NOT hallucinate or guess missing values
2. DO NOT add any external knowledge
3. DO NOT include unrelated parameters
4. ONLY use the provided data
5. If the provided data is empty or irrelevant, respond exactly: "No relevant data found."

## FORMATTING RULES

### FOR PARAMETER TABLES:
1. Start with the parameter name (bold)
2. Provide a short 1-line explanation of what this parameter means
3. You MUST list ALL values provided in the data. PDF tables often merge multiple values into a single cell using newlines (e.g., "0.23\\n0.18\\n0.92"). You must separate and list every single value.
4. List values with their corresponding conditions and units. If a condition is missing or unaligned for a value, list the value anyway and just state "Condition unspecified" or pair it logically.

### FOR TEXT / DESCRIPTIONS / FEATURES / APPLICATIONS:
1. Synthesize the provided text blocks into a clean, readable summary.
2. Group related points using bullet points.
3. Do not invent features not explicitly stated in the text.
"""


def _build_user_message(query: str, data: dict) -> str:
    """Build the user message with query + structured data."""
    formatted_context = ""

    # Check if it's the new unified mixed payload
    if "table" in data or "text" in data:
        if "table" in data:
            tbl = data["table"]
            rows = []
            for row in tbl["rows"]:
                record = {col: row.get(col, "") for col in tbl["columns"] if row.get(col)}
                if record:
                    rows.append(record)
            if rows:
                formatted_context += f"--- PARAMETER TABLE DATA ---\n"
                formatted_context += json.dumps(rows, indent=2) + "\n\n"

        if "text" in data:
            formatted_context += f"--- EXTRACTED TEXT BLOCKS ---\n"
            formatted_context += data["text"].get("content", "") + "\n\n"

        if "images" in data:
            formatted_context += f"--- DIAGRAMS & GRAPHS ---\n"
            formatted_context += data["images"] + "\n\n"
            
    # Legacy table fallback
    elif "rows" in data and "columns" in data:
        rows = []
        for row in data["rows"]:
            record = {col: row.get(col, "") for col in data["columns"] if row.get(col)}
            if record:
                rows.append(record)
        formatted_context = json.dumps(rows, indent=2)
    # Generic fallback
    else:
        formatted_context = json.dumps(data, indent=2)

    return (
        f"User question: {query}\n\n"
        f"Datasheet Retrieval Context:\n{formatted_context}\n"
        f"Generate a clean, accurate answer using ONLY the data above. "
        f"Do not add any information that is not present in the data."
    )


# ── API / Interface ─────────────────────────────────────────────────

def _generate_local(query: str, data: dict) -> str:
    """Generate answer using the locally loaded HuggingFace model."""
    import torch
    user_msg = _build_user_message(query, data)
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
    
    # Properly format messages for Qwen chat template
    text = _tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = _tokenizer([text], return_tensors="pt").to(_model.device)
    
    try:
        with torch.no_grad():
            outputs = _model.generate(
                **inputs,
                max_new_tokens=512,
                temperature=0.1,  # Keep it technical and deterministic
                top_p=0.9,
                do_sample=True,
            )
        # Decode only the generated response
        generated = outputs[0][inputs.input_ids.shape[-1]:]
        return _tokenizer.decode(generated, skip_special_tokens=True).strip()
    except Exception as e:
        logger.error(f"Local Qwen generation failed: {e}")
        return ""


async def format_with_qwen(query: str, structured_data: dict) -> str:
    """
    Format data into a Chat response.
    Tries Local model first, falls back to API.
    """
    # Short-circuit ONLY if the graph explicitly returned a no-results/error message
    # (i.e. dict with ONLY a "message" key and no real data)
    if isinstance(structured_data, dict) and list(structured_data.keys()) == ["message"]:
        msg = structured_data["message"].lower()
        if "no " in msg or "not found" in msg or "error" in msg:
            return ""

    if not is_qwen_available():
        logger.info("Qwen not configured — AI formatting disabled")
        return ""

    # Priority 1: Use strictly local in-process model
    # Run in a thread pool so blocking inference doesn't stall the async event loop
    if _is_loaded:
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _generate_local, query, structured_data)

    # Priority 2: Use external HTTP API endpoint
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
    except Exception as e:
        logger.error(f"Qwen API request failed: {e}")
        return ""
