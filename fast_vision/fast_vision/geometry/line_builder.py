"""
Group words into text lines based on vertical proximity and baseline alignment.

Words are assigned to a line if their vertical centre falls within the line's
y-band (tolerance = half the font size).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def build_lines(words: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Cluster words into horizontal text lines.

    Returns
    -------
    list of line dicts:
        text, x0, y0, x1, y1, fontname, size, color, words
    """
    if not words:
        return []

    # Sort by vertical position first, then horizontal
    sorted_words = sorted(words, key=lambda w: (w["y0"], w["x0"]))

    lines: List[List[Dict[str, Any]]] = []
    current_line: List[Dict[str, Any]] = [sorted_words[0]]

    for w in sorted_words[1:]:
        ref = current_line[0]
        ref_mid_y = (ref["y0"] + ref["y1"]) / 2.0
        w_mid_y = (w["y0"] + w["y1"]) / 2.0
        tolerance = max(ref["size"] * 0.6, 3.0)

        if abs(w_mid_y - ref_mid_y) <= tolerance:
            current_line.append(w)
        else:
            lines.append(current_line)
            current_line = [w]

    if current_line:
        lines.append(current_line)

    result: List[Dict[str, Any]] = []
    for line_words in lines:
        # Sort left-to-right within the line
        line_words.sort(key=lambda w: w["x0"])
        result.append(_merge_words(line_words))

    logger.debug("Built %d lines from %d words", len(result), len(words))
    return result


def _merge_words(words: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge words into a single line dict."""
    text = " ".join(w["text"] for w in words)

    # Dominant font
    font_counts: Dict[str, int] = {}
    size_sum = 0.0
    for w in words:
        fn = w["fontname"]
        font_counts[fn] = font_counts.get(fn, 0) + 1
        size_sum += w["size"]

    dominant_font = max(font_counts, key=font_counts.get)  # type: ignore
    avg_size = round(size_sum / len(words), 2)

    return {
        "text": text,
        "x0": min(w["x0"] for w in words),
        "y0": min(w["y0"] for w in words),
        "x1": max(w["x1"] for w in words),
        "y1": max(w["y1"] for w in words),
        "fontname": dominant_font,
        "size": avg_size,
        "color": words[0]["color"],
        "words": words,
    }
