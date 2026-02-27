"""
Merge adjacent text lines into logical blocks (paragraphs).

Lines are merged when:
1. Vertical gap between consecutive lines is ≤ LINE_GAP_FACTOR × font size.
2. Lines share similar font characteristics (same font family).
3. No large horizontal shift suggesting a column break.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Maximum gap between lines (as multiple of font size) to still merge
LINE_GAP_FACTOR = 1.5
# Maximum change in x0 to still merge (pt) — prevents multi-column merging
X_SHIFT_TOLERANCE = 40.0


def build_blocks(lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge consecutive lines into text blocks (paragraphs).

    Returns
    -------
    list of block dicts:
        id, text, x0, y0, x1, y1, fontname, size, color, lines
    """
    if not lines:
        return []

    # Sort top-to-bottom by y0
    sorted_lines = sorted(lines, key=lambda ln: ln["y0"])

    blocks: List[List[Dict[str, Any]]] = []
    current_block: List[Dict[str, Any]] = [sorted_lines[0]]

    for ln in sorted_lines[1:]:
        prev = current_block[-1]

        # Vertical gap
        gap = ln["y0"] - prev["y1"]
        threshold = max(prev["size"] * LINE_GAP_FACTOR, 4.0)

        # Horizontal alignment check
        x_shift = abs(ln["x0"] - prev["x0"])

        # Font consistency
        same_font = _font_family(ln["fontname"]) == _font_family(prev["fontname"])

        if gap <= threshold and x_shift <= X_SHIFT_TOLERANCE and same_font:
            current_block.append(ln)
        else:
            blocks.append(current_block)
            current_block = [ln]

    if current_block:
        blocks.append(current_block)

    result: List[Dict[str, Any]] = []
    for block_lines in blocks:
        result.append(_merge_lines(block_lines))

    logger.debug("Built %d blocks from %d lines", len(result), len(lines))
    return result


def _merge_lines(lines: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge a group of lines into a block dict."""
    text = "\n".join(ln["text"] for ln in lines)

    # Collect all words from all lines
    all_words = []
    for ln in lines:
        all_words.extend(ln.get("words", []))

    # Dominant font for the block
    font_counts: Dict[str, int] = {}
    size_sum = 0.0
    for ln in lines:
        fn = ln["fontname"]
        font_counts[fn] = font_counts.get(fn, 0) + 1
        size_sum += ln["size"]

    dominant_font = max(font_counts, key=font_counts.get)  # type: ignore
    avg_size = round(size_sum / len(lines), 2)

    return {
        "id": str(uuid.uuid4()),
        "text": text,
        "x0": min(ln["x0"] for ln in lines),
        "y0": min(ln["y0"] for ln in lines),
        "x1": max(ln["x1"] for ln in lines),
        "y1": max(ln["y1"] for ln in lines),
        "fontname": dominant_font,
        "size": avg_size,
        "color": lines[0]["color"],
        "lines": lines,
        "words": all_words,
    }


def _font_family(fontname: str) -> str:
    """Normalise font name to family (strip Bold/Italic suffixes)."""
    name = fontname
    for suffix in ("-Bold", "-Italic", "-BoldItalic", ",Bold", ",Italic",
                    "-Regular", ",Regular", "+"):
        name = name.split(suffix)[0]
    return name.strip()
