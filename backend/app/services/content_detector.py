"""
Content Detector — Phase 1.3

Detects content block types from extracted page data.
Types: text, table, graph (image with axes), diagram.
"""
from app.models import ParsedPage


def detect_content_types(page: ParsedPage) -> dict[str, int]:
    """
    Returns a summary of content types found on a page.
    """
    counts = {
        "text": len(page.texts),
        "table": len(page.tables),
        "graph": sum(1 for img in page.images if img.block_type == "graph"),
        "diagram": sum(1 for img in page.images if img.block_type == "diagram"),
        "image": sum(1 for img in page.images if img.block_type == "image"),
    }
    return counts


def is_specification_page(page: ParsedPage) -> bool:
    """Check if a page likely contains electrical specifications."""
    keywords = [
        "electrical characteristics", "absolute maximum", "recommended operating",
        "dc characteristics", "ac characteristics", "thermal", "specification",
    ]
    for text_block in page.texts:
        lower = text_block.content.lower()
        if any(kw in lower for kw in keywords):
            return True
    return len(page.tables) > 0
