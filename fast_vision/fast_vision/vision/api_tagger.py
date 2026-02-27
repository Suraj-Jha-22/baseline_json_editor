"""
Vision API semantic tagger.

Sends page images + extracted text blocks to Gemini 2.0 Flash or GPT-4o-mini
for semantic classification (block type, role, reading order, rhetoric).
Uses ThreadPoolExecutor for parallel page processing.
"""

from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from PIL import Image

from fast_vision.vision.page_renderer import image_to_base64, render_page
from fast_vision.vision.prompts import (
    SEMANTIC_TAGGER_SYSTEM,
    SEMANTIC_TAGGER_USER_TEMPLATE,
)

logger = logging.getLogger(__name__)
load_dotenv()


def tag_page_gemini(
    image: Image.Image,
    blocks_summary: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Classify blocks using Gemini 2.0 Flash."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

    user_msg = SEMANTIC_TAGGER_USER_TEMPLATE.format(
        n_blocks=len(blocks_summary),
        blocks_json=json.dumps(blocks_summary),  # compact, no indent
    )

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[image, f"{SEMANTIC_TAGGER_SYSTEM}\n\n{user_msg}"],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.0,
        ),
    )

    try:
        result = json.loads(response.text)
        return result.get("blocks", [])
    except (json.JSONDecodeError, AttributeError) as e:
        logger.error("Gemini response parse error: %s", e)
        return []


def tag_page_openai(
    image_b64: str,
    blocks_summary: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Classify blocks using GPT-4o-mini."""
    import openai

    client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    user_msg = SEMANTIC_TAGGER_USER_TEMPLATE.format(
        n_blocks=len(blocks_summary),
        blocks_json=json.dumps(blocks_summary),  # compact, no indent
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SEMANTIC_TAGGER_SYSTEM},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_msg},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                    },
                ],
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
    )

    try:
        content = response.choices[0].message.content
        result = json.loads(content)
        return result.get("blocks", [])
    except (json.JSONDecodeError, AttributeError, IndexError) as e:
        logger.error("OpenAI response parse error: %s", e)
        return []


def _build_blocks_summary(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build a token-efficient summary of blocks for the Vision API prompt."""
    summary = []
    for i, b in enumerate(blocks):
        text = b.get("text", "")
        # Truncate to save tokens — 120 chars is enough for classification
        if len(text) > 120:
            text = text[:120] + "..."
        summary.append({
            "index": i,
            "text": text,
            "font": b.get("fontname", ""),
            "size": b.get("size", 0),
        })
    return summary


def tag_all_pages(
    pdf_path: str,
    pages_blocks: List[Tuple[int, List[Dict[str, Any]]]],
    max_workers: int = 8,
    progress_callback: Optional[Any] = None,
) -> Dict[int, List[Dict[str, Any]]]:
    """Tag all pages in parallel using the available Vision API.

    Parameters
    ----------
    pdf_path : path to PDF
    pages_blocks : list of (page_index_0based, blocks) tuples
    max_workers : thread pool size
    progress_callback : optional callable(pct, msg)

    Returns
    -------
    dict mapping page_index → list of semantic tag dicts
    """
    has_openai = bool(os.environ.get("OPENAI_API_KEY"))
    has_gemini = bool(os.environ.get("GEMINI_API_KEY"))

    if not has_openai and not has_gemini:
        raise ValueError("Neither OPENAI_API_KEY nor GEMINI_API_KEY found.")

    engine = "OpenAI (GPT-4o-mini)" if has_openai else "Gemini (2.0 Flash)"
    logger.info("Using Vision API engine: %s", engine)

    def process_page(page_idx: int, blocks: List[Dict[str, Any]]) -> Tuple[int, List[Dict[str, Any]]]:
        summary = _build_blocks_summary(blocks)
        if not summary:
            return (page_idx, [])

        try:
            img = render_page(pdf_path, page_idx)
            if has_openai:
                b64 = image_to_base64(img)
                tags = tag_page_openai(b64, summary)
            else:
                tags = tag_page_gemini(img, summary)
            return (page_idx, tags)
        except Exception as e:
            logger.error("Vision API failed for page %d: %s", page_idx, e)
            return (page_idx, [])

    results: Dict[int, List[Dict[str, Any]]] = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_page, pi, blks): pi
            for pi, blks in pages_blocks
        }

        completed = 0
        total = len(futures)
        for future in as_completed(futures):
            completed += 1
            page_idx, tags = future.result()
            results[page_idx] = tags
            if progress_callback:
                progress_callback(
                    completed / total,
                    f"Tagged page {completed}/{total} via {engine}",
                )

    return results
