"""
Query Router — User query endpoint.
"""
import logging
from fastapi import APIRouter

from app.models import QueryRequest, QueryResponse
from app.services.query_engine import execute_query
from app.services.ai_client import format_with_qwen
from app.services.graph_builder import graph_builder

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def query_datasheet(request: QueryRequest):
    """
    Query the knowledge graph.
    Classifies the query, routes to the right source, optionally
    formats with Qwen.
    """
    logger.info("Query received: %s (component: %s)", request.query, request.component)

    # Execute query against knowledge graph
    response = execute_query(request)

    # Optionally format with Qwen
    if response.data:
        ai_answer = await format_with_qwen(request.query, response.data)
        if ai_answer:
            response.ai_answer = ai_answer

    return response


@router.get("/components")
async def list_components():
    """Return all component names in the knowledge graph."""
    components = graph_builder.get_all_components()
    return {"components": components}


@router.get("/component/{name}/summary")
async def component_summary(name: str):
    """Get a summary of stored data for a specific component."""
    summary = graph_builder.get_component_summary(name)
    return summary
