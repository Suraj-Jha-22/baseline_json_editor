"""
Extract raw character data from every page of a PDF using pdfplumber.

Each character dict includes:
  text, x0, y0, x1, y1, fontname, size, stroking_color, non_stroking_color
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import pdfplumber

logger = logging.getLogger(__name__)


def extract_chars_from_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    """Return a list of page dicts, each containing raw chars and dimensions.

    Returns
    -------
    [
        {
            "page_number": 1,          # 1-indexed
            "width": 612.0,
            "height": 792.0,
            "chars": [ {text, x0, y0, x1, y1, fontname, size, ...}, ... ]
        },
        ...
    ]
    """
    pages_data: List[Dict[str, Any]] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            chars = page.chars  # list[dict]
            cleaned: List[Dict[str, Any]] = []

            for c in chars:
                text = c.get("text", "")
                if not text or text.isspace() and text != " ":
                    continue
                cleaned.append({
                    "text": text,
                    "x0": float(c["x0"]),
                    "y0": float(c["top"]),
                    "x1": float(c["x1"]),
                    "y1": float(c["bottom"]),
                    "fontname": c.get("fontname", ""),
                    "size": round(float(c.get("size", 0)), 2),
                    "color": _extract_color(c),
                })

            pages_data.append({
                "page_number": page.page_number,  # already 1-indexed
                "width": float(page.width),
                "height": float(page.height),
                "chars": cleaned,
            })
            logger.debug(
                "Page %d: %d chars extracted (%.0f × %.0f pt)",
                page.page_number, len(cleaned), page.width, page.height,
            )

    return pages_data


def _extract_color(char_dict: Dict[str, Any]) -> str:
    """Best-effort extraction of text colour as hex string."""
    nsc = char_dict.get("non_stroking_color")
    if nsc is None:
        return "#000000"
    if isinstance(nsc, (list, tuple)):
        if len(nsc) == 3:
            r, g, b = [int(max(0, min(1, v)) * 255) for v in nsc]
            return f"#{r:02x}{g:02x}{b:02x}"
        if len(nsc) == 1:
            gray = int(max(0, min(1, nsc[0])) * 255)
            return f"#{gray:02x}{gray:02x}{gray:02x}"
        if len(nsc) == 4:
            c_, m_, y_, k_ = nsc
            r = int(255 * (1 - c_) * (1 - k_))
            g = int(255 * (1 - m_) * (1 - k_))
            b = int(255 * (1 - y_) * (1 - k_))
            return f"#{r:02x}{g:02x}{b:02x}"
    return "#000000"
