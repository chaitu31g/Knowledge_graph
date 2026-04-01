"""
PDF Parser — Phase 1

Extracts text, tables, and images from PDF datasheets.
- PyMuPDF (fitz) → text blocks + images
- pdfplumber  → table detection and extraction
"""
import os
import fitz  # PyMuPDF
import pdfplumber
from typing import Optional

from app.models import (
    ParsedDocument, ParsedPage, ExtractedText,
    ExtractedTable, ExtractedImage,
)
from app.utils import clean_text, extract_section_title, detect_component_name


def parse_pdf(filepath: str) -> ParsedDocument:
    """
    Full PDF parse: text (PyMuPDF) + tables (pdfplumber) + images (PyMuPDF).
    Returns a ParsedDocument with all pages.
    """
    filename = os.path.basename(filepath)
    all_texts_raw: list[str] = []

    # ── Pass 1: PyMuPDF for text + images ───────────────────────────
    fitz_doc = fitz.open(filepath)
    total_pages = len(fitz_doc)

    pages: dict[int, ParsedPage] = {}
    for page_idx in range(total_pages):
        page_num = page_idx + 1
        fitz_page = fitz_doc[page_idx]

        parsed_page = ParsedPage(page=page_num)

        # ── Text blocks ────────────────────────────────────────────
        blocks = fitz_page.get_text("blocks")
        current_section = ""
        for block in blocks:
            # block = (x0, y0, x1, y1, text, block_no, block_type)
            if block[6] == 0:  # text block
                raw = block[4]
                cleaned = clean_text(raw)
                if not cleaned:
                    continue

                all_texts_raw.append(cleaned)

                # Detect section title
                title = extract_section_title(cleaned)
                if title and len(cleaned) < 100:
                    current_section = title

                # Classify text block
                block_type = _classify_text_block(cleaned, current_section)

                parsed_page.texts.append(ExtractedText(
                    page=page_num,
                    section=current_section,
                    content=cleaned,
                    block_type=block_type,
                ))

        # ── Images ──────────────────────────────────────────────────
        image_list = fitz_page.get_images(full=True)
        for img_idx, img_info in enumerate(image_list):
            xref = img_info[0]
            # Classify image: graph (axes detected) vs diagram vs generic
            img_block_type = "image"
            img_title = ""
            img_desc = ""
            img_axes = None

            # Try to infer from surrounding text
            nearby_text = _get_nearby_text_for_image(
                fitz_page, img_info, blocks
            )
            if nearby_text:
                img_title = nearby_text.get("title", "")
                img_desc = nearby_text.get("description", "")
                if _looks_like_graph(nearby_text):
                    img_block_type = "graph"
                    img_axes = nearby_text.get("axes")
                elif _looks_like_diagram(nearby_text):
                    img_block_type = "diagram"

            parsed_page.images.append(ExtractedImage(
                page=page_num,
                image_index=img_idx,
                block_type=img_block_type,
                title=img_title,
                description=img_desc,
                axes=img_axes,
            ))

        pages[page_num] = parsed_page

    fitz_doc.close()

    # ── Pass 2: pdfplumber for tables ───────────────────────────────
    with pdfplumber.open(filepath) as pdf:
        for page_idx, plumber_page in enumerate(pdf.pages):
            page_num = page_idx + 1
            if page_num not in pages:
                pages[page_num] = ParsedPage(page=page_num)

            tables = plumber_page.extract_tables()
            for table in tables:
                if not table or len(table) < 2:
                    continue

                extracted = _process_raw_table(table, page_num, pages[page_num])
                if extracted:
                    pages[page_num].tables.append(extracted)

    # ── Build final document ────────────────────────────────────────
    component_name = detect_component_name(all_texts_raw)

    return ParsedDocument(
        filename=filename,
        total_pages=total_pages,
        pages=[pages[i] for i in sorted(pages.keys())],
        component_name=component_name,
    )


# ── Internal helpers ────────────────────────────────────────────────

def _classify_text_block(text: str, section: str) -> str:
    """Classify a text block into: text, feature, description, application."""
    section_lower = section.lower()
    text_lower = text.lower()

    if any(kw in section_lower for kw in ["feature", "highlight", "key benefit"]):
        return "feature"
    if any(kw in section_lower for kw in ["description", "overview", "general"]):
        return "description"
    if any(kw in section_lower for kw in ["application", "typical use"]):
        return "application"

    # Content-based heuristics
    if text_lower.startswith("•") or text_lower.startswith("–") or text_lower.startswith("-"):
        return "feature"

    return "text"


def _process_raw_table(
    raw_table: list[list[Optional[str]]],
    page_num: int,
    parsed_page: ParsedPage,
) -> Optional[ExtractedTable]:
    """
    Process a raw pdfplumber table into an ExtractedTable.
    STRICT: headers are taken EXACTLY as they appear.
    """
    if not raw_table or len(raw_table) < 2:
        return None

    # First row = headers
    headers = [str(h).strip() if h else "" for h in raw_table[0]]

    # Skip tables with all-empty headers
    if all(h == "" or h == "None" for h in headers):
        # Try second row as header
        if len(raw_table) >= 3:
            headers = [str(h).strip() if h else "" for h in raw_table[1]]
            raw_table = raw_table[1:]
        else:
            return None

    # Clean "None" strings
    headers = [h if h != "None" else "" for h in headers]

    # Data rows
    rows = []
    for row in raw_table[1:]:
        cells = [str(c).strip() if c else "" for c in row]
        # Skip completely empty rows
        if all(c == "" or c == "None" for c in cells):
            continue
        # Clean "None" strings
        cells = [c if c != "None" else "" for c in cells]
        rows.append(cells)

    if not rows:
        return None

    # Detect section context
    section = ""
    if parsed_page.texts:
        # Use the most recent section title before this table
        section = parsed_page.texts[-1].section

    return ExtractedTable(
        page=page_num,
        section=section,
        headers=headers,
        rows=rows,
    )


def _get_nearby_text_for_image(
    fitz_page, img_info, text_blocks
) -> Optional[dict]:
    """
    Try to find text near an image that might be its caption/title.
    Returns dict with 'title', 'description', 'axes' if found.
    """
    # This is a heuristic approach — look for "Figure" or "Fig." text
    result = {}
    for block in text_blocks:
        if block[6] != 0:  # only text blocks
            continue
        text = str(block[4]).strip()
        text_lower = text.lower()
        if any(kw in text_lower for kw in ["figure", "fig.", "fig "]):
            result["title"] = text[:200]
            result["description"] = text[:500]
            # Check for axis labels
            if "vs" in text_lower or "versus" in text_lower:
                parts = text.split("vs")
                if len(parts) == 2:
                    result["axes"] = {
                        "y": parts[0].strip()[-30:],
                        "x": parts[1].strip()[:30],
                    }
            break
    return result if result else None


def _looks_like_graph(nearby_text: dict) -> bool:
    """Check if nearby text suggests this image is a graph/chart."""
    title = nearby_text.get("title", "").lower()
    desc = nearby_text.get("description", "").lower()
    combined = title + " " + desc
    graph_keywords = ["vs", "versus", "graph", "chart", "plot", "curve", "frequency", "response"]
    return any(kw in combined for kw in graph_keywords)


def _looks_like_diagram(nearby_text: dict) -> bool:
    """Check if nearby text suggests this image is a circuit/block diagram."""
    title = nearby_text.get("title", "").lower()
    desc = nearby_text.get("description", "").lower()
    combined = title + " " + desc
    diagram_keywords = ["diagram", "schematic", "circuit", "block diagram", "pin", "package", "layout"]
    return any(kw in combined for kw in diagram_keywords)
