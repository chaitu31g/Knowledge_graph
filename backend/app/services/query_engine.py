"""
Query Engine - Phase 5

Deterministic parameter retrieval from Neo4j.
"""
import logging
import re

from app.models import QueryRequest, QueryResponse
from app.services.graph_builder import graph_builder
from app.utils.normalization import normalize_lookup_text

logger = logging.getLogger(__name__)


def execute_query(request: QueryRequest) -> QueryResponse:
    """Execute deterministic parameter retrieval from Neo4j."""
    search_term = _extract_search_term(request.query)
    normalized_search_term = normalize_lookup_text(search_term)
    logger.info(
        "Parameter query executing for: '%s' (normalized: '%s', component: %s)",
        search_term,
        normalized_search_term,
        request.component,
    )

    param_results = graph_builder.query_parameter(
        param_name=normalized_search_term,
        component=request.component,
    )

    return QueryResponse(
        type="table",
        data=param_results,
        source=f"Neo4j parameter lookup - {len(param_results)} rows",
    )


def _extract_search_term(query: str) -> str:
    """
    Extract the most likely search term from a natural language query.
    Strips common question words and returns the core term(s).
    """
    q = query.strip()
    prefixes = [
        r"what is the\s+",
        r"what's the\s+",
        r"what are the\s+",
        r"tell me about\s+",
        r"show me\s+",
        r"find\s+",
        r"what is\s+",
        r"how much\s+",
        r"how many\s+",
        r"value of\s+",
        r"get\s+",
        r"give me\s+",
    ]
    for prefix in prefixes:
        q = re.sub(prefix, "", q, flags=re.IGNORECASE)

    q = re.sub(r"\?+$", "", q)
    q = re.sub(r"\s+of this (component|chip|ic|device)$", "", q, flags=re.IGNORECASE)
    q = re.sub(r"\s+for this (component|chip|ic|device)$", "", q, flags=re.IGNORECASE)

    return q.strip()
