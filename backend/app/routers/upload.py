"""
Upload Router — PDF upload and ingestion endpoint.
"""
import os
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException

from app.config import settings
from app.models import UploadResponse
from app.services.pdf_parser import parse_pdf
from app.services.table_extractor import extract_parameters
from app.services.graph_builder import graph_builder

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["upload"])


@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    """
    Upload a PDF datasheet → parse → extract parameters → build knowledge graph.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Save uploaded file
    filepath = os.path.join(settings.UPLOAD_DIR, file.filename)
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)
    logger.info("Saved uploaded PDF: %s (%d bytes)", file.filename, len(content))

    try:
        # ── Phase 1: Parse PDF ──────────────────────────────────────
        logger.info("Parsing PDF: %s", file.filename)
        doc = parse_pdf(filepath)
        logger.info(
            "Parsed %d pages, found %d tables, %d text blocks",
            doc.total_pages,
            sum(len(p.tables) for p in doc.pages),
            sum(len(p.texts) for p in doc.pages),
        )

        # ── Phase 2: Extract parameters from tables ─────────────────
        parameters_by_table: dict[int, list] = {}
        table_index = 0
        total_tables = 0
        for page in doc.pages:
            for table in page.tables:
                total_tables += 1
                params = extract_parameters(table)
                parameters_by_table[table_index] = params
                logger.info(
                    "Table %d (page %d): %d headers, %d rows → %d parameters",
                    table_index, page.page,
                    len(table.headers), len(table.rows), len(params),
                )
                table_index += 1

        # ── Phase 3 & 4: Build Knowledge Graph ──────────────────────
        logger.info("Building knowledge graph for: %s", doc.component_name)
        stats = graph_builder.ingest_document(doc, parameters_by_table)

        return UploadResponse(
            filename=doc.filename,
            total_pages=doc.total_pages,
            tables_found=total_tables,
            parameters_stored=stats["parameters_stored"],
            text_blocks_stored=stats["text_blocks_stored"],
            images_found=stats["images_found"],
            component_name=doc.component_name or doc.filename,
            message=f"Successfully ingested {doc.filename} into knowledge graph",
        )

    except Exception as e:
        logger.exception("Error processing PDF: %s", file.filename)
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")
