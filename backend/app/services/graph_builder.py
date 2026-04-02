"""
Graph Builder — Phase 3 & 4

Builds/updates the Neo4j Knowledge Graph from parsed PDF data.

Node types:
    Component, Parameter, Value, Unit, Condition, Table,
    TextBlock, GraphImage, Diagram

Relationships:
    (Component)-[:HAS_PARAMETER]->(Parameter)
    (Parameter)-[:HAS_VALUE]->(Value)
    (Value)-[:HAS_UNIT]->(Unit)
    (Parameter)-[:HAS_CONDITION]->(Condition)
    (Parameter)-[:BELONGS_TO]->(Table)
    (Component)-[:HAS_TEXT]->(TextBlock)
    (Component)-[:HAS_GRAPH]->(GraphImage)
    (Component)-[:HAS_DIAGRAM]->(Diagram)
"""
import logging
from neo4j import GraphDatabase, Driver

from app.config import settings
from app.models import ParsedDocument, ParameterRow, ExtractedTable

logger = logging.getLogger(__name__)


class GraphBuilder:
    """Manages the Neo4j connection and graph construction."""

    def __init__(self):
        self._driver: Driver | None = None

    def connect(self):
        """Open a Neo4j driver connection."""
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )
            logger.info("Connected to Neo4j at %s", settings.NEO4J_URI)

    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None

    @property
    def driver(self) -> Driver:
        if self._driver is None:
            self.connect()
        return self._driver

    # ── Schema Constraints ──────────────────────────────────────────

    def create_constraints(self):
        """Create uniqueness constraints for core node types."""
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Component) REQUIRE c.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Table) REQUIRE t.uid IS UNIQUE",
        ]
        with self.driver.session() as session:
            for cypher in constraints:
                session.run(cypher)
        logger.info("Neo4j constraints created")

    # ── Full Ingestion ──────────────────────────────────────────────

    def ingest_document(
        self,
        doc: ParsedDocument,
        parameters_by_table: dict[int, list[ParameterRow]],
    ) -> dict:
        """
        Ingest an entire parsed document into the knowledge graph.
        Returns stats dict.
        """
        self.create_constraints()

        component = doc.component_name or doc.filename
        stats = {
            "parameters_stored": 0,
            "text_blocks_stored": 0,
            "images_found": 0,
        }

        with self.driver.session() as session:
            # ── Component node ──────────────────────────────────────
            session.run(
                "MERGE (c:Component {name: $name}) "
                "SET c.filename = $filename, c.total_pages = $pages",
                name=component,
                filename=doc.filename,
                pages=doc.total_pages,
            )

            # ── Process each page ───────────────────────────────────
            table_index = 0
            for page in doc.pages:
                # ── Text blocks ─────────────────────────────────────
                for text_block in page.texts:
                    session.run(
                        """
                        MATCH (c:Component {name: $component})
                        CREATE (t:TextBlock {
                            content: $content,
                            page: $page,
                            section: $section,
                            block_type: $block_type
                        })
                        CREATE (c)-[:HAS_TEXT]->(t)
                        """,
                        component=component,
                        content=text_block.content,
                        page=text_block.page,
                        section=text_block.section,
                        block_type=text_block.block_type,
                    )
                    stats["text_blocks_stored"] += 1

                # ── Tables + Parameters ─────────────────────────────
                for table in page.tables:
                    table_uid = f"{doc.filename}::p{page.page}::t{table_index}"
                    table_index += 1

                    # Create Table node
                    session.run(
                        """
                        MATCH (c:Component {name: $component})
                        MERGE (tbl:Table {uid: $uid})
                        SET tbl.page = $page,
                            tbl.section = $section,
                            tbl.headers = $headers
                        MERGE (c)-[:HAS_TABLE]->(tbl)
                        """,
                        component=component,
                        uid=table_uid,
                        page=page.page,
                        section=table.section,
                        headers=table.headers,
                    )

                    # Parameters for this table
                    params = parameters_by_table.get(table_index - 1, [])
                    for param in params:
                        self._store_parameter(
                            session, component, table_uid, param
                        )
                        stats["parameters_stored"] += 1

                # ── Images / Graphs / Diagrams ──────────────────────
                for img in page.images:
                    stats["images_found"] += 1
                    if img.block_type == "graph":
                        session.run(
                            """
                            MATCH (c:Component {name: $component})
                            CREATE (g:GraphImage {
                                page: $page,
                                title: $title,
                                description: $desc,
                                x_axis: $x_axis,
                                y_axis: $y_axis
                            })
                            CREATE (c)-[:HAS_GRAPH]->(g)
                            """,
                            component=component,
                            page=img.page,
                            title=img.title,
                            desc=img.description,
                            x_axis=img.axes.get("x", "") if img.axes else "",
                            y_axis=img.axes.get("y", "") if img.axes else "",
                        )
                    elif img.block_type == "diagram":
                        session.run(
                            """
                            MATCH (c:Component {name: $component})
                            CREATE (d:Diagram {
                                page: $page,
                                title: $title,
                                description: $desc
                            })
                            CREATE (c)-[:HAS_DIAGRAM]->(d)
                            """,
                            component=component,
                            page=img.page,
                            title=img.title,
                            desc=img.description,
                        )

        return stats

    def _store_parameter(
        self, session, component: str, table_uid: str, param: ParameterRow
    ):
        """Store a single parameter with its values, unit, and conditions.

        The param uid includes both the parameter name AND the condition so
        that multi-condition rows (e.g. TA=25°C and TA=70°C for the same
        parameter) are stored as distinct nodes instead of colliding on MERGE.
        """
        # Include condition in uid to avoid MERGE collision for multi-row params
        condition_key = param.conditions.replace(" ", "") if param.conditions else "nocond"
        param_uid = f"{table_uid}::{param.parameter}::{condition_key}"

        session.run(
            """
            MATCH (c:Component {name: $component})
            MATCH (tbl:Table {uid: $table_uid})
            MERGE (p:Parameter {uid: $param_uid})
            SET p.name = $name,
                p.symbol = $symbol,
                p.condition = $condition
            MERGE (c)-[:HAS_PARAMETER]->(p)
            MERGE (p)-[:BELONGS_TO]->(tbl)
            """,
            component=component,
            table_uid=table_uid,
            param_uid=param_uid,
            name=param.parameter,
            symbol=param.symbol,
            condition=param.conditions,
        )

        # Create Value nodes (one per value column)
        for val_type, val_str in param.values.items():
            if not val_str:
                continue
            session.run(
                """
                MATCH (p:Parameter {uid: $param_uid})
                CREATE (v:Value {
                    value: $value,
                    value_type: $value_type,
                    condition: $condition
                })
                CREATE (p)-[:HAS_VALUE]->(v)
                """,
                param_uid=param_uid,
                value=val_str,
                value_type=val_type,
                condition=param.conditions,
            )

            # Unit node (shared across the graph)
            if param.unit:
                session.run(
                    """
                    MATCH (p:Parameter {uid: $param_uid})-[:HAS_VALUE]->(v:Value {value: $value, value_type: $value_type})
                    MERGE (u:Unit {name: $unit})
                    MERGE (v)-[:HAS_UNIT]->(u)
                    """,
                    param_uid=param_uid,
                    value=val_str,
                    value_type=val_type,
                    unit=param.unit,
                )

    # ── Query Helpers ───────────────────────────────────────────────

    def get_all_components(self) -> list[str]:
        """Return all component names in the graph."""
        with self.driver.session() as session:
            result = session.run("MATCH (c:Component) RETURN c.name AS name")
            return [r["name"] for r in result]

    def query_parameter(self, param_name: str, component: str = "") -> list[dict]:
        """
        Query parameters by name (case-insensitive contains).
        Returns only rows that have a valid value AND unit.
        Condition is read directly from the Value node (stored at ingest time).
        """
        cypher = """
        MATCH (c:Component)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE]->(v:Value)
        MATCH (v)-[:HAS_UNIT]->(u:Unit)
        OPTIONAL MATCH (p)-[:BELONGS_TO]->(tbl:Table)
        WHERE toLower(p.name) CONTAINS toLower($param_name)
          AND u.name IS NOT NULL AND u.name <> ''
          AND v.value IS NOT NULL AND v.value <> ''
        """
        if component:
            cypher += " AND toLower(c.name) CONTAINS toLower($component)"

        cypher += """
        RETURN c.name          AS component,
               p.name          AS parameter,
               p.symbol        AS symbol,
               v.value         AS value,
               v.value_type    AS value_type,
               u.name          AS unit,
               v.condition     AS condition,
               tbl.page        AS page
        ORDER BY c.name, p.name, v.value_type
        """

        with self.driver.session() as session:
            result = session.run(cypher, param_name=param_name, component=component)
            return [dict(r) for r in result]

    def query_text(self, search_term: str, component: str = "") -> list[dict]:
        """
        Search text blocks by content (case-insensitive contains).
        """
        cypher = """
        MATCH (c:Component)-[:HAS_TEXT]->(t:TextBlock)
        WHERE toLower(t.content) CONTAINS toLower($search)
        """
        if component:
            cypher += " AND toLower(c.name) CONTAINS toLower($component)"

        cypher += """
        RETURN c.name AS component,
               t.content AS content,
               t.section AS section,
               t.block_type AS block_type,
               t.page AS page
        ORDER BY t.page
        LIMIT 20
        """

        with self.driver.session() as session:
            result = session.run(cypher, search=search_term, component=component)
            return [dict(r) for r in result]

    def get_component_summary(self, component: str) -> dict:
        """Get a summary of all data stored for a component."""
        with self.driver.session() as session:
            params = session.run(
                """
                MATCH (c:Component {name: $name})-[:HAS_PARAMETER]->(p)
                RETURN count(p) AS count
                """,
                name=component,
            ).single()
            texts = session.run(
                """
                MATCH (c:Component {name: $name})-[:HAS_TEXT]->(t)
                RETURN count(t) AS count
                """,
                name=component,
            ).single()
            tables = session.run(
                """
                MATCH (c:Component {name: $name})-[:HAS_TABLE]->(t)
                RETURN count(t) AS count
                """,
                name=component,
            ).single()

            return {
                "component": component,
                "parameters": params["count"] if params else 0,
                "text_blocks": texts["count"] if texts else 0,
                "tables": tables["count"] if tables else 0,
            }


# ── Module-level singleton ──────────────────────────────────────────

graph_builder = GraphBuilder()
