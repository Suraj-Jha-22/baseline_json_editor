"""
Style normalizer — deduplicate and hash font styles across the document.

Collects (font_family, size, weight, color) tuples from all blocks,
hashes them into unique style IDs, and assigns style_id to each block.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


def normalize_styles(
    blocks: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Assign style_id to every block and return the global styles dict.

    Returns
    -------
    (blocks_with_style_ids, styles_dict)
    """
    styles: Dict[str, Dict[str, Any]] = {}

    for block in blocks:
        font = block.get("fontname", "unknown")
        size = block.get("size", 0.0)
        color = block.get("color", "#000000")

        # Determine weight from font name
        fn_lower = font.lower()
        weight = "bold" if "bold" in fn_lower else "normal"
        italic = "italic" in fn_lower or "oblique" in fn_lower

        # Determine alignment heuristically (if we have page width)
        align = "left"  # default

        style_obj = {
            "font_family": _clean_font_name(font),
            "size": round(size, 1),
            "weight": weight,
            "italic": italic,
            "underline": False,
            "color": color,
            "align": align,
        }

        style_id = _hash_style(style_obj)
        block["style_id"] = style_id

        if style_id not in styles:
            styles[style_id] = style_obj

    logger.debug("Normalised %d blocks into %d unique styles", len(blocks), len(styles))
    return blocks, styles


def _hash_style(style: Dict[str, Any]) -> str:
    """12-char deterministic hash of a style dict."""
    key = f"{style['font_family']}|{style['size']}|{style['weight']}|{style['italic']}|{style['color']}"
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def _clean_font_name(fontname: str) -> str:
    """Remove encoding prefixes like ABCDEF+ from embedded font names."""
    if "+" in fontname:
        fontname = fontname.split("+", 1)[1]
    return fontname
