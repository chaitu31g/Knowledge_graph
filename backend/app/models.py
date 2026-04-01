"""
Pydantic models for request/response schemas.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Optional


# ── PDF Parsing Models ──────────────────────────────────────────────

class ExtractedTable(BaseModel):
    """A single table extracted from a PDF page."""
    page: int
    section: str = ""
    headers: list[str]
    rows: list[list[str]]


class ExtractedText(BaseModel):
    """A block of text extracted from a PDF page."""
    page: int
    section: str = ""
    content: str
    block_type: str = "text"  # text | feature | description | application


class ExtractedImage(BaseModel):
    """An image/graph/diagram extracted from a PDF page."""
    page: int
    image_index: int
    block_type: str = "image"  # image | graph | diagram
    title: str = ""
    description: str = ""
    axes: Optional[dict[str, str]] = None  # {"x": "...", "y": "..."}


class ParsedPage(BaseModel):
    """All content extracted from a single PDF page."""
    page: int
    texts: list[ExtractedText] = []
    tables: list[ExtractedTable] = []
    images: list[ExtractedImage] = []


class ParsedDocument(BaseModel):
    """All content extracted from an entire PDF."""
    filename: str
    total_pages: int
    pages: list[ParsedPage] = []
    component_name: str = ""


# ── Table Extraction Models ─────────────────────────────────────────

class ParameterRow(BaseModel):
    """A single parameter extracted from a table — fully dynamic columns."""
    raw_cells: dict[str, str] = Field(
        default_factory=dict,
        description="Original header→value mapping, exactly as in the PDF"
    )
    parameter: str = ""
    symbol: str = ""
    values: dict[str, str] = Field(
        default_factory=dict,
        description="Dynamic value columns, e.g. {'min': '1.2', 'typ': '1.5', 'max': '1.8'} or {'value': '3.3'}"
    )
    unit: str = ""
    conditions: str = ""


# ── Knowledge Graph Models ──────────────────────────────────────────

class GraphNode(BaseModel):
    """Generic graph node."""
    label: str
    properties: dict[str, Any] = {}


class GraphRelationship(BaseModel):
    """Generic graph relationship."""
    source_label: str
    source_key: dict[str, Any]
    target_label: str
    target_key: dict[str, Any]
    rel_type: str
    properties: dict[str, Any] = {}


# ── Query Models ────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    """User query from the frontend."""
    query: str
    component: str = ""  # optional component filter


class QueryResponse(BaseModel):
    """Structured query response."""
    type: str  # "table" | "text"
    data: Any
    source: str = ""  # provenance info
    ai_answer: str = ""  # Qwen-formatted answer


# ── Upload Response ─────────────────────────────────────────────────

class UploadResponse(BaseModel):
    """Response after PDF upload and ingestion."""
    filename: str
    total_pages: int
    tables_found: int
    parameters_stored: int
    text_blocks_stored: int
    images_found: int
    component_name: str
    message: str
