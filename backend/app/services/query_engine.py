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

# ── Query Classification ────────────────────────────────────────────

# Keywords that indicate a structured parameter query
_PARAMETER_INDICATORS = [
    r"voltage", r"current", r"power", r"frequency", r"temperature",
    r"resistance", r"capacitance", r"inductance", r"impedance",
    r"gain", r"offset", r"noise", r"bandwidth", r"slew rate",
    r"propagation delay", r"rise time", r"fall time",
    r"threshold", r"hysteresis", r"leakage",
    r"supply", r"quiescent", r"standby", r"shutdown",
    r"output high", r"output low", r"input high", r"input low",
    r"vcc", r"vdd", r"vss", r"vee", r"gnd",
    r"absolute maximum", r"rating",
    r"min\b", r"max\b", r"typ\b", r"typical",
    r"what is the", r"what's the", r"value of",
    r"how much", r"how many",
    r"specification", r"spec\b",
    r"ESD",
]

# Keywords that indicate a text/feature query
_TEXT_INDICATORS = [
    r"feature", r"description", r"overview", r"application",
    r"what does", r"what is", r"explain", r"describe",
    r"how does it work", r"purpose", r"function",
    r"pin\s*out", r"package",
    r"advantage", r"benefit",
    r"compatible", r"replacement",
    r"tell me about",
]


def classify_query(query: str) -> str:
    """
    Classify a user query as 'parameter' or 'text'.
    Returns "parameter" or "text".
    """
    q = query.lower().strip()

    param_score = 0
    text_score = 0

    for pattern in _PARAMETER_INDICATORS:
        if re.search(pattern, q, re.IGNORECASE):
            param_score += 1

    for pattern in _TEXT_INDICATORS:
        if re.search(pattern, q, re.IGNORECASE):
            text_score += 1

    # Default to parameter if no clear winner
    if param_score >= text_score:
        return "parameter"
    return "text"


# ── Query Execution ─────────────────────────────────────────────────

def execute_query(request: QueryRequest) -> QueryResponse:
    """
    Execute a user query — classify, route, and return structured response.
    """
    query_type = classify_query(request.query)
    logger.info("Query classified as '%s': %s", query_type, request.query)

    if query_type == "parameter":
        return _execute_parameter_query(request)
    else:
        return _execute_text_query(request)


def _execute_parameter_query(request: QueryRequest) -> QueryResponse:
    """
    Execute a parameter query against the knowledge graph.
    Extracts the likely parameter name from the query and searches.
    """
    # Extract key terms from query
    search_term = _extract_search_term(request.query)

    results = graph_builder.query_parameter(
        param_name=search_term,
        component=request.component,
    )

    if not results:
        # Broaden search — try individual words
        words = search_term.split()
        for word in words:
            if len(word) > 2:
                results = graph_builder.query_parameter(
                    param_name=word,
                    component=request.component,
                )
                if results:
                    break

    if results:
        # Group by parameter for table display
        table_data = _results_to_table(results)
        return QueryResponse(
            type="table",
            data=table_data,
            source=f"Knowledge Graph — matched {len(results)} records",
        )
    else:
        return QueryResponse(
            type="text",
            data={"message": f"No parameters found matching '{search_term}'. Try a different query."},
            source="Knowledge Graph — no match",
        )


def _execute_text_query(request: QueryRequest) -> QueryResponse:
    """Execute a text/feature query."""
    search_term = _extract_search_term(request.query)

    results = graph_builder.query_text(
        search_term=search_term,
        component=request.component,
    )

    if results:
        # Combine text blocks
        combined = "\n\n".join(
            f"[Page {r['page']}] {r['content']}" for r in results
        )
        return QueryResponse(
            type="text",
            data={
                "content": combined,
                "sections": list(set(r["section"] for r in results if r["section"])),
                "pages": list(set(r["page"] for r in results if r["page"])),
            },
            source=f"Text search — {len(results)} blocks found",
        )
    else:
        return QueryResponse(
            type="text",
            data={"message": f"No text content found matching '{search_term}'."},
            source="Text search — no match",
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
