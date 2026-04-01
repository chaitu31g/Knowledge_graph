"""
Upload Router — PDF upload and ingestion with real-time progress streaming.
"""
import os
import json
import logging
import asyncio
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse

from app.config import settings
from app.models import UploadResponse
from app.services.pdf_parser import parse_pdf
from app.services.table_extractor import extract_parameters
from app.services.graph_builder import graph_builder

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["upload"])


def _sse_event(data: dict) -> str:
    """Format a dict as a Server-Sent Event line."""
    return f"data: {json.dumps(data)}\n\n"


@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """
    Upload PDF → stream processing progress via SSE → return final result.
    Each step sends a status update so the frontend can show what's happening.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Save uploaded file
    filepath = os.path.join(settings.UPLOAD_DIR, file.filename)
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    file_size_mb = len(content) / (1024 * 1024)
    logger.info("Saved uploaded PDF: %s (%.1f MB)", file.filename, file_size_mb)

    async def process_and_stream():
        try:
            # ── Step 1: File saved ──────────────────────────────────
            yield _sse_event({
                "step": 1,
                "total_steps": 6,
                "status": "processing",
                "message": f"📄 File received: {file.filename} ({file_size_mb:.1f} MB)",
                "detail": "Saved to server",
            })
            await asyncio.sleep(0.1)

            # ── Step 2: Parse PDF text + images ─────────────────────
            yield _sse_event({
                "step": 2,
                "total_steps": 6,
                "status": "processing",
                "message": "🔍 Extracting text and images from PDF...",
                "detail": "Using PyMuPDF for text blocks and image detection",
            })
            await asyncio.sleep(0.1)

            doc = parse_pdf(filepath)
            total_texts = sum(len(p.texts) for p in doc.pages)
            total_images = sum(len(p.images) for p in doc.pages)
            total_tables_raw = sum(len(p.tables) for p in doc.pages)

            yield _sse_event({
                "step": 2,
                "total_steps": 6,
                "status": "done",
                "message": f"✅ Parsed {doc.total_pages} pages",
                "detail": f"Found {total_texts} text blocks, {total_images} images, {total_tables_raw} tables",
            })
            await asyncio.sleep(0.1)

            # ── Step 3: Detect component name ───────────────────────
            yield _sse_event({
                "step": 3,
                "total_steps": 6,
                "status": "processing",
                "message": f"🏷️ Component detected: {doc.component_name or 'Unknown'}",
                "detail": "Identified part number from header text",
            })
            await asyncio.sleep(0.1)

            # ── Step 4: Extract parameters from tables ──────────────
            yield _sse_event({
                "step": 4,
                "total_steps": 6,
                "status": "processing",
                "message": f"📊 Extracting parameters from {total_tables_raw} tables...",
                "detail": "Dynamic column detection, value/unit splitting",
            })
            await asyncio.sleep(0.1)

            parameters_by_table: dict[int, list] = {}
            table_index = 0
            total_tables = 0
            total_params = 0

            for page in doc.pages:
                for table in page.tables:
                    total_tables += 1
                    params = extract_parameters(table)
                    parameters_by_table[table_index] = params
                    total_params += len(params)

                    yield _sse_event({
                        "step": 4,
                        "total_steps": 6,
                        "status": "processing",
                        "message": f"📊 Table {total_tables}: {len(params)} parameters extracted",
                        "detail": f"Page {page.page} — {len(table.headers)} columns, {len(table.rows)} rows",
                    })
                    table_index += 1
                    await asyncio.sleep(0.05)

            yield _sse_event({
                "step": 4,
                "total_steps": 6,
                "status": "done",
                "message": f"✅ Extracted {total_params} parameters from {total_tables} tables",
                "detail": "All tables processed with dynamic schema detection",
            })
            await asyncio.sleep(0.1)

            # ── Step 5: Build Knowledge Graph ───────────────────────
            yield _sse_event({
                "step": 5,
                "total_steps": 6,
                "status": "processing",
                "message": "🧠 Building Knowledge Graph in Neo4j...",
                "detail": "Creating Component, Parameter, Value, Unit, Condition nodes",
            })
            await asyncio.sleep(0.1)

            stats = graph_builder.ingest_document(doc, parameters_by_table)

            yield _sse_event({
                "step": 5,
                "total_steps": 6,
                "status": "done",
                "message": f"✅ Knowledge Graph built: {stats['parameters_stored']} parameters stored",
                "detail": f"{stats['text_blocks_stored']} text blocks, {stats['images_found']} images indexed",
            })
            await asyncio.sleep(0.1)

            # ── Step 6: Complete ────────────────────────────────────
            result = {
                "filename": doc.filename,
                "total_pages": doc.total_pages,
                "tables_found": total_tables,
                "parameters_stored": stats["parameters_stored"],
                "text_blocks_stored": stats["text_blocks_stored"],
                "images_found": stats["images_found"],
                "component_name": doc.component_name or doc.filename,
                "message": f"Successfully ingested {doc.filename} into knowledge graph",
            }

            yield _sse_event({
                "step": 6,
                "total_steps": 6,
                "status": "complete",
                "message": "🎉 Ingestion complete!",
                "detail": f"{doc.component_name or doc.filename} is ready to query",
                "result": result,
            })

        except Exception as e:
            logger.exception("Error processing PDF: %s", file.filename)
            yield _sse_event({
                "step": -1,
                "total_steps": 6,
                "status": "error",
                "message": f"❌ Error: {str(e)}",
                "detail": "Check backend logs for details",
            })

    return StreamingResponse(
        process_and_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
