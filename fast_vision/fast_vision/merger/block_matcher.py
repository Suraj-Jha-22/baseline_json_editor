"""
Match geometry-sourced blocks to Vision API semantic annotations.

Uses text similarity (SequenceMatcher) to find the best correspondence
between deterministic geometry blocks and the API's semantic tags.
"""

from __future__ import annotations

import logging
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def match_blocks_to_tags(
    blocks: List[Dict[str, Any]],
    tags: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Transfer semantic tags onto geometry blocks via fuzzy text matching.

    Parameters
    ----------
    blocks : geometry-sourced block dicts (with text, bbox, etc.)
    tags : Vision API tag dicts (block_index, block_type, role, rhetoric, etc.)

    Returns
    -------
    blocks with added keys: block_type, role, reading_order, rhetoric, rhetoric_features
    """
    if not tags:
        # Fallback: assign default types
        for i, b in enumerate(blocks):
            b.setdefault("block_type", "paragraph")
            b.setdefault("role", "paragraph")
            b.setdefault("reading_order", i)
        return blocks

    # Build index map from tag.block_index → tag
    index_map: Dict[int, Dict[str, Any]] = {}
    for tag in tags:
        idx = tag.get("block_index")
        if idx is not None:
            index_map[idx] = tag

    # First pass: direct index matching
    matched = set()
    for i, block in enumerate(blocks):
        if i in index_map:
            _apply_tag(block, index_map[i], i)
            matched.add(i)

    # Second pass: fuzzy match unmatched blocks to remaining tags
    unmatched_blocks = [(i, b) for i, b in enumerate(blocks) if i not in matched]
    unmatched_tags = [t for t in tags if t.get("block_index") not in matched]

    if unmatched_blocks and unmatched_tags:
        for i, block in unmatched_blocks:
            best_tag = _find_best_tag(block, unmatched_tags)
            if best_tag:
                _apply_tag(block, best_tag, i)
                unmatched_tags.remove(best_tag)
            else:
                block.setdefault("block_type", "paragraph")
                block.setdefault("role", "paragraph")
                block.setdefault("reading_order", i)

    # Final pass: assign defaults to any still-untagged blocks
    for i, block in enumerate(blocks):
        block.setdefault("block_type", "paragraph")
        block.setdefault("role", "paragraph")
        block.setdefault("reading_order", i)

    return blocks


def _apply_tag(block: Dict[str, Any], tag: Dict[str, Any], fallback_order: int) -> None:
    """Apply semantic tag fields onto a block dict."""
    block["block_type"] = tag.get("block_type", "paragraph")
    block["role"] = tag.get("role", "paragraph")
    block["reading_order"] = tag.get("reading_order", fallback_order)
    block["rhetoric"] = tag.get("rhetoric")
    block["rhetoric_features"] = tag.get("rhetoric_features")


def _find_best_tag(
    block: Dict[str, Any],
    tags: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Find the tag whose text best matches the block text."""
    block_text = block.get("text", "")
    if not block_text:
        return None

    best_score = 0.0
    best_tag = None

    for tag in tags:
        tag_text = tag.get("text", "")
        if not tag_text:
            continue
        score = SequenceMatcher(None, block_text[:200], tag_text[:200]).ratio()
        if score > best_score:
            best_score = score
            best_tag = tag

    return best_tag if best_score > 0.4 else None
