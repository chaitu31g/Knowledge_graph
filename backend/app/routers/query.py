"""
Query Router - User query endpoint.
"""
import logging

from fastapi import APIRouter

from app.models import QueryRequest, QueryResponse
from app.services.graph_builder import graph_builder
from app.services.query_engine import execute_query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def query_datasheet(request: QueryRequest):
    """Query deterministic parameter rows from Neo4j."""
    logger.info("Query received: %s (component: %s)", request.query, request.component)
    return execute_query(request)


@router.get("/components")
async def list_components():
    """Return all component names in the knowledge graph."""
    components = graph_builder.get_all_components()
    return {"components": components}


@router.get("/component/{name}/summary")
async def component_summary(name: str):
    """Get a summary of stored data for a specific component."""
    return graph_builder.get_component_summary(name)


@router.delete("/component/{name}")
async def delete_component(name: str):
    """
    Delete a specific component and ALL its associated data from the graph.
    Removes: Component, Parameter, Value, Unit, Condition, Table, TextBlock nodes.
    """
    deleted = graph_builder.delete_component(name)
    return {
        "status": "deleted",
        "component": name,
        "nodes_deleted": deleted,
    }


@router.delete("/graph/clear")
async def clear_all():
    """
    Delete everything from the graph.
    Use with caution - this removes all components and their data.
    """
    deleted = graph_builder.clear_all()
    return {
        "status": "cleared",
        "nodes_deleted": deleted,
    }


@router.get("/debug/graph/{component}")
async def debug_graph(component: str):
    """
    Debug endpoint - returns raw Neo4j records for a component.
    Shows exactly what is stored: parameter names, values, units, conditions.
    """
    with graph_builder.driver.session() as session:
        all_params = session.run(
            """
            MATCH (c:Component)-[:HAS_PARAMETER]->(p:Parameter)
            WHERE toLower(c.name) CONTAINS toLower($comp)
            RETURN p.name AS parameter,
                   p.value AS value,
                   p.unit AS unit,
                   p.condition AS condition
            ORDER BY p.name
            LIMIT 100
            """,
            comp=component,
        ).data()

        linked_values = session.run(
            """
            MATCH (c:Component)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE]->(v:Value)
            OPTIONAL MATCH (v)-[:HAS_UNIT]->(u:Unit)
            WHERE toLower(c.name) CONTAINS toLower($comp)
            RETURN p.name AS parameter,
                   v.value AS value,
                   u.name AS unit,
                   v.condition AS condition
            ORDER BY p.name
            LIMIT 100
            """,
            comp=component,
        ).data()

    return {
        "component": component,
        "stored_parameter_rows": len(all_params),
        "parameter_rows_sample": all_params[:20],
        "linked_value_rows": linked_values[:20],
    }
