"""
Cluster extracted characters into words based on horizontal gaps.

Algorithm:
1. Sort chars by (y0, x0)  — top-to-bottom, left-to-right.
2. Walk chars; if horizontal gap between consecutive chars on same baseline
   exceeds a threshold (fraction of font size), start a new word.
3. Each word gets: text, merged bbox, dominant font info.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# If horizontal gap > GAP_FACTOR × avg_char_width → new word
GAP_FACTOR = 0.35


def build_words(chars: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Cluster characters into words.

    Parameters
    ----------
    chars : list of char dicts with keys: text, x0, y0, x1, y1, fontname, size, color

    Returns
    -------
    list of word dicts:
        text, x0, y0, x1, y1, fontname, size, color
    """
    if not chars:
        return []

    # Sort top-to-bottom, then left-to-right
    sorted_chars = sorted(chars, key=lambda c: (round(c["y0"], 1), c["x0"]))

    words: List[Dict[str, Any]] = []
    current: List[Dict[str, Any]] = [sorted_chars[0]]

    for c in sorted_chars[1:]:
        prev = current[-1]

        # Check vertical alignment — same baseline within tolerance
        y_overlap = min(prev["y1"], c["y1"]) - max(prev["y0"], c["y0"])
        min_height = min(prev["y1"] - prev["y0"], c["y1"] - c["y0"])
        same_line = y_overlap > 0 and (y_overlap / max(min_height, 0.1)) > 0.5

        if same_line:
            gap = c["x0"] - prev["x1"]
            avg_width = (prev["x1"] - prev["x0"] + c["x1"] - c["x0"]) / 2.0
            threshold = max(avg_width * GAP_FACTOR, prev["size"] * 0.25)

            if gap <= threshold:
                current.append(c)
                continue

        # Flush current word
        words.append(_merge_chars(current))
        current = [c]

    if current:
        words.append(_merge_chars(current))

    logger.debug("Built %d words from %d chars", len(words), len(chars))
    return words


def _merge_chars(chars: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge a run of chars into one word dict."""
    text = "".join(c["text"] for c in chars)

    # Dominant font = mode of fontnames
    font_counts: Dict[str, int] = {}
    size_sum = 0.0
    for c in chars:
        fn = c["fontname"]
        font_counts[fn] = font_counts.get(fn, 0) + 1
        size_sum += c["size"]

    dominant_font = max(font_counts, key=font_counts.get)  # type: ignore
    avg_size = round(size_sum / len(chars), 2)

    return {
        "text": text,
        "x0": min(c["x0"] for c in chars),
        "y0": min(c["y0"] for c in chars),
        "x1": max(c["x1"] for c in chars),
        "y1": max(c["y1"] for c in chars),
        "fontname": dominant_font,
        "size": avg_size,
        "color": chars[0]["color"],
    }
