"""
Render PDF pages as JPEG images for the Vision API.

Uses pypdfium2 (Apache 2.0 / BSD) for fast, GPU-free rendering.
"""

from __future__ import annotations

import base64
import io
import logging

import pypdfium2
from PIL import Image

logger = logging.getLogger(__name__)


def render_page(pdf_path: str, page_index: int, dpi: int = 200) -> Image.Image:
    """Render a single PDF page as a PIL Image.

    Parameters
    ----------
    pdf_path : path to the PDF
    page_index : 0-indexed page number
    dpi : render resolution (higher = better accuracy, more tokens)
    """
    doc = pypdfium2.PdfDocument(pdf_path)
    page = doc[page_index]
    bitmap = page.render(scale=dpi / 72)
    img = bitmap.to_pil().convert("RGB")
    logger.debug("Rendered page %d at %d DPI → %dx%d", page_index, dpi, img.width, img.height)
    return img


def image_to_base64(image: Image.Image, quality: int = 85) -> str:
    """Encode a PIL Image as base64 JPEG string."""
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def get_total_pages(pdf_path: str) -> int:
    """Return the number of pages in a PDF."""
    doc = pypdfium2.PdfDocument(pdf_path)
    return len(doc)
