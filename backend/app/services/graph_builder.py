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
from app.utils.normalization import normalize_lookup_text

logger = logging.getLogger(__name__)


_NORM_REMOVE_CHARS = [
    "\r",
    "\n",
    "\t",
    " ",
    "/",
    "-",
    "(",
    ")",
    "[",
    "]",
    "{",
    "}",
    ".",
    ",",
    ":",
    ";",
    "_",
]


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
            self._ensure_parameter_norm_names()

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
                        stats["parameters_stored"] += self._store_parameter(
                            session, component, table_uid, param
                        )

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
    ) -> int:
        """Store a single parameter with its values, unit, and conditions.

        The param uid includes both the parameter name AND the condition so
        that multi-condition rows (e.g. TA=25°C and TA=70°C for the same
        parameter) are stored as distinct nodes instead of colliding on MERGE.
        """
        entries = self._build_parameter_entries(param)
        if not entries:
            logger.debug(
                "Skipping incomplete parameter row: parameter=%r unit=%r values=%r",
                param.parameter,
                param.unit,
                param.values,
            )
            return 0

        condition_key = param.conditions.replace(" ", "") if param.conditions else "nocond"
        norm_name = normalize_lookup_text(param.parameter)
        stored_count = 0

        for entry in entries:
            value_type = entry["value_type"]
            value = entry["value"]
            unit = entry["unit"]
            param_uid = f"{table_uid}::{param.parameter}::{condition_key}::{value_type}"
            value_uid = f"{param_uid}::value"

            session.run(
                """
                MATCH (c:Component {name: $component})
                MATCH (tbl:Table {uid: $table_uid})
                MERGE (p:Parameter {uid: $param_uid})
                SET p.name = $name,
                    p.norm_name = $norm_name,
                    p.symbol = $symbol,
                    p.condition = $condition,
                    p.value = $value,
                    p.unit = $unit,
                    p.component = $component,
                    p.value_type = $value_type
                MERGE (c)-[:HAS_PARAMETER]->(p)
                MERGE (p)-[:BELONGS_TO]->(tbl)
                MERGE (v:Value {uid: $value_uid})
                SET v.value = $value,
                    v.value_type = $value_type,
                    v.condition = $condition
                MERGE (p)-[:HAS_VALUE]->(v)
                MERGE (u:Unit {name: $unit})
                MERGE (v)-[:HAS_UNIT]->(u)
                """,
                component=component,
                table_uid=table_uid,
                param_uid=param_uid,
                value_uid=value_uid,
                name=param.parameter,
                norm_name=norm_name,
                symbol=param.symbol,
                condition=param.conditions,
                value=value,
                unit=unit,
                value_type=value_type,
            )
            stored_count += 1

        return stored_count

    @staticmethod
    def _build_parameter_entries(param: ParameterRow) -> list[dict[str, str]]:
        """Return only complete value rows that can be stored and queried."""
        parameter = (param.parameter or "").strip()
        unit = (param.unit or "").strip()
        if not parameter or not unit:
            return []

        entries: list[dict[str, str]] = []
        for value_type, raw_value in param.values.items():
            value = (raw_value or "").strip()
            if not value:
                continue
            entries.append(
                {
                    "value_type": (value_type or "value").strip() or "value",
                    "value": value,
                    "unit": unit,
                }
            )
        return entries

    # ── Delete Helpers ───────────────────────────────────────────────

    def delete_component(self, component_name: str) -> int:
        """
        Delete a component and ALL its associated nodes from the graph.
        Cascades through: Parameter → Value → Unit, Table, TextBlock, etc.
        Returns the count of nodes deleted.
        """
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (c:Component {name: $name})
                OPTIONAL MATCH (c)-[:HAS_PARAMETER]->(p:Parameter)
                OPTIONAL MATCH (p)-[:HAS_VALUE]->(v:Value)
                OPTIONAL MATCH (v)-[:HAS_UNIT]->(u:Unit)
                OPTIONAL MATCH (p)-[:BELONGS_TO]->(tbl:Table)
                OPTIONAL MATCH (c)-[:HAS_TEXT]->(t:TextBlock)
                OPTIONAL MATCH (c)-[:HAS_GRAPH]->(g:GraphImage)
                OPTIONAL MATCH (c)-[:HAS_DIAGRAM]->(d:Diagram)
                DETACH DELETE c, p, v, tbl, t, g, d
                RETURN count(*) AS deleted
                """,
                name=component_name,
            ).single()
            deleted = result["deleted"] if result else 0
            logger.info("Deleted component '%s': %d nodes removed", component_name, deleted)
            return deleted

    def clear_all(self) -> int:
        """
        Delete EVERYTHING from the graph — all nodes and relationships.
        Returns count of deleted nodes.
        """
        with self.driver.session() as session:
            result = session.run(
                "MATCH (n) DETACH DELETE n RETURN count(*) AS deleted"
            ).single()
            deleted = result["deleted"] if result else 0
            logger.warning("⚠️  Cleared entire graph: %d nodes deleted", deleted)
            return deleted

    # ── Query Helpers ───────────────────────────────────────────────

    def get_all_components(self) -> list[str]:
        """Return all component names in the graph."""
        with self.driver.session() as session:
            result = session.run("MATCH (c:Component) RETURN c.name AS name")
            return [r["name"] for r in result]

    def query_parameter(self, param_name: str, component: str = "") -> list[dict]:
        """
        Query deterministic parameter rows and always return complete records.
        """
        normalized_param_name = normalize_lookup_text(param_name)
        normalized_component = component.strip().lower()
        normalized_name_expr = f"coalesce(p.norm_name, {self._cypher_normalize_expr('p.name')})"
        logger.info("Normalized parameter query: '%s'", normalized_param_name)

        sample_cypher = f"""
        MATCH (c:Component)-[:HAS_PARAMETER]->(p:Parameter)
        WHERE $component = '' OR toLower(c.name) CONTAINS $component
        RETURN p.name AS parameter,
               {normalized_name_expr} AS norm_name
        ORDER BY p.name
        LIMIT 5
        """

        cypher = f"""
        MATCH (c:Component)-[:HAS_PARAMETER]->(p:Parameter)
        OPTIONAL MATCH (p)-[:HAS_VALUE]->(v:Value)
        OPTIONAL MATCH (v)-[:HAS_UNIT]->(u:Unit)
        WITH p,
             c,
             {normalized_name_expr} AS norm_name,
             coalesce(p.value, v.value) AS row_value,
             coalesce(p.unit, u.name) AS row_unit,
             coalesce(p.condition, v.condition, '') AS row_condition
        WHERE norm_name CONTAINS $param_name
          AND row_value IS NOT NULL AND trim(row_value) <> ''
          AND row_unit IS NOT NULL AND trim(row_unit) <> ''
        """
        if normalized_component:
            cypher += " AND toLower(c.name) CONTAINS $component"

        cypher += """
        RETURN DISTINCT p.name AS parameter,
                        row_value AS value,
                        row_unit AS unit,
                        row_condition AS condition
        ORDER BY p.name, row_condition, row_value
        """

        with self.driver.session() as session:
            sample_rows = session.run(
                sample_cypher,
                component=normalized_component,
            ).data()
            logger.info("Sample normalized DB values: %s", sample_rows)

            rows = [
                dict(r)
                for r in session.run(
                    cypher,
                    param_name=normalized_param_name,
                    component=normalized_component,
                )
            ]
            logger.info("Matched %d parameter rows", len(rows))
            logger.info("Sample returned rows: %s", rows[:5])
            return rows

    @staticmethod
    def _cypher_normalize_expr(field_name: str) -> str:
        """Build a Cypher normalization expression for legacy rows."""
        expr = f"toLower(trim(coalesce({field_name}, '')))"
        for char in _NORM_REMOVE_CHARS:
            escaped = char.replace("\\", "\\\\").replace("'", "\\'")
            expr = f"replace({expr}, '{escaped}', '')"
        return expr

    def _ensure_parameter_norm_names(self):
        """Backfill normalized names for existing Parameter nodes."""
        cypher_norm_name = self._cypher_normalize_expr("p.name")
        with self.driver.session() as session:
            updated = session.run(
                f"""
                MATCH (p:Parameter)
                WHERE p.norm_name IS NULL OR p.norm_name = ''
                SET p.norm_name = {cypher_norm_name}
                RETURN count(p) AS updated
                """
            ).single()
        logger.info(
            "Parameter norm_name backfill updated %d nodes",
            updated["updated"] if updated else 0,
        )

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

    def query_images(self, search_term: str, component: str = "") -> list[dict]:
        """
        Search for images, graphs, and diagrams by title or description.
        """
        cypher = """
        MATCH (c:Component)-[:HAS_GRAPH|HAS_DIAGRAM]->(img)
        WHERE toLower(img.title) CONTAINS toLower($search)
           OR toLower(img.description) CONTAINS toLower($search)
        """
        if component:
            cypher += " AND toLower(c.name) CONTAINS toLower($component)"

        cypher += """
        RETURN c.name AS component,
               labels(img)[0] AS type,
               img.title AS title,
               img.description AS description,
               img.x_axis AS x_axis,
               img.y_axis AS y_axis,
               img.page AS page
        ORDER BY img.page
        LIMIT 10
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
