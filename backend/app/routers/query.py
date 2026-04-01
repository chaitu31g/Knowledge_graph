"""
Query Router — User query endpoint.

Flow:
1. User sends question
2. Query engine classifies and fetches from Knowledge Graph
3. Qwen AI formats the structured data into a clean answer
4. Returns both structured data (for tables) and AI answer (for natural language)
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
    1. Classifies the query (parameter vs text)
    2. Fetches structured data from Neo4j
    3. Sends data to Qwen 3.5 4B for clean natural language formatting
    4. Returns both raw data + AI answer
    """
    logger.info("Query received: %s (component: %s)", request.query, request.component)

    # Step 1: Get structured data from knowledge graph
    response = execute_query(request)

    # Step 2: Format with Qwen AI (if data was found)
    if response.data:
        try:
            ai_answer = await format_with_qwen(request.query, response.data)
            if ai_answer:
                response.ai_answer = ai_answer
                logger.info("AI answer generated (%d chars)", len(ai_answer))
            else:
                logger.info("No AI answer — Qwen not configured or returned empty")
        except Exception as e:
            logger.error("Qwen formatting failed: %s", e)
            # Don't fail the whole request — still return raw data

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
