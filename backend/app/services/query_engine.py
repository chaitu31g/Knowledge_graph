"""
Query Engine — Phase 5

Classifies user queries and routes them to the appropriate data source:
- Parameter query → Knowledge Graph (Cypher)
- Feature/text query → Text search in graph
"""
import re
import logging
from app.models import QueryRequest, QueryResponse
from app.services.graph_builder import graph_builder

logger = logging.getLogger(__name__)

# ── Query Execution ─────────────────────────────────────────────────

def execute_query(request: QueryRequest) -> QueryResponse:
    """
    Execute a unified query.
    Instead of guessing if the user wants parameters or text,
    we search BOTH and pass the combined context to the AI.
    """
    search_term = _extract_search_term(request.query)
    logger.info("Unified query executing for: '%s' (component: %s)", search_term, request.component)

    param_results = graph_builder.query_parameter(
        param_name=search_term,
        component=request.component,
    )

    text_results = graph_builder.query_text(
        search_term=search_term,
        component=request.component,
    )

    image_results = graph_builder.query_images(
        search_term=search_term,
        component=request.component,
    )
    
    if not param_results and not text_results and not image_results:
        return QueryResponse(
            type="text",
            data={"message": f"No data found matching '{search_term}'."},
            source="Knowledge Graph & Text Search — no match",
        )

    # Build the combined data payload
    combined_data = {}
    
    if param_results:
        combined_data["table"] = _results_to_table(param_results)
        
    if text_results:
        combined_text = "\n\n".join(
            f"[Page {r['page']}, Section {r['section']}] {r['content']}" for r in text_results
        )
        combined_data["text"] = {
            "content": combined_text,
            "sections": list(set(r["section"] for r in text_results if r["section"])),
            "pages": list(set(r["page"] for r in text_results if r["page"])),
        }

    if image_results:
        combined_images = "\n\n".join(
            f"[Page {r['page']}, {r['type'].upper()}]: '{r['title']}' - {r['description']}" for r in image_results
        )
        combined_data["images"] = combined_images

    sources = []
    if param_results:
        sources.append(f"{len(param_results)} parameter rows")
    if text_results:
        sources.append(f"{len(text_results)} text blocks")
    if image_results:
        sources.append(f"{len(image_results)} images/graphs")

    return QueryResponse(
        type="mixed",
        data=combined_data,
        source="Knowledge Graph — " + ", ".join(sources),
    )

# ── Helpers ─────────────────────────────────────────────────────────

def _extract_search_term(query: str) -> str:
    """
    Extract the most likely search term from a natural language query.
    Strips common question words and returns the core term(s).
    """
    q = query.strip()
    # Remove common question prefixes
    prefixes = [
        r"what is the\s+", r"what's the\s+", r"what are the\s+",
        r"tell me about\s+", r"show me\s+", r"find\s+",
        r"what is\s+", r"how much\s+", r"how many\s+",
        r"value of\s+", r"get\s+", r"give me\s+",
    ]
    for prefix in prefixes:
        q = re.sub(prefix, "", q, flags=re.IGNORECASE)

    # Remove trailing question marks and common suffixes
    q = re.sub(r"\?+$", "", q)
    q = re.sub(r"\s+of this (component|chip|ic|device)$", "", q, flags=re.IGNORECASE)
    q = re.sub(r"\s+for this (component|chip|ic|device)$", "", q, flags=re.IGNORECASE)

    return q.strip()


def _results_to_table(results: list[dict]) -> dict:
    """
    Convert graph query results into a clean table.
    Each result row is one complete record: parameter + value + unit + condition.
    Condition is now carried directly on the row (not merged from a shared node).
    """
    columns = ["component", "parameter", "symbol", "value", "unit", "condition", "page"]

    rows = []
    for r in results:
        # Only include rows that actually have a value and unit
        if not r.get("value") or not r.get("unit"):
            continue
        rows.append({
            "component":  r.get("component") or "",
            "parameter":  r.get("parameter") or "",
            "symbol":     r.get("symbol") or "",
            "value":      r.get("value") or "",
            "unit":       r.get("unit") or "",
            "condition":  r.get("condition") or "",
            "page":       r.get("page") or "",
        })

    return {
        "columns": columns,
        "rows": rows,
    }
