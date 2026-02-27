"""
Main pipeline orchestrator for fast_vision.

Chains together:
1. Geometry extraction (chars → words → lines → blocks) [PDF]
   OR direct paragraph/table extraction [DOCX]
2. Table extraction
3. Vision API semantic tagging (optional)
4. Block matching + merging
5. Style normalisation
6. Schema v3.0 assembly
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any, Callable, Dict, List, Optional

from fast_vision.geometry.char_extractor import extract_chars_from_pdf
from fast_vision.geometry.word_builder import build_words
from fast_vision.geometry.line_builder import build_lines
from fast_vision.geometry.block_builder import build_blocks
from fast_vision.geometry.table_extractor import (
    extract_tables,
    deduplicate_blocks_from_tables,
)
from fast_vision.merger.block_matcher import match_blocks_to_tags
from fast_vision.merger.schema_assembler import assemble_document
from fast_vision.schema import LayoutDocument, SourceType
from fast_vision.styles.style_normalizer import normalize_styles
from fast_vision.vision.api_tagger import tag_all_pages

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
#  Unified entry point
# ═══════════════════════════════════════════════════════════════════════

def process_document(
    filepath: str,
    use_vision: bool = True,
    page_range: Optional[str] = None,
    progress_callback: Optional[Callable] = None,
) -> LayoutDocument:
    """Auto-detect input format (PDF or DOCX) and extract structured JSON.

    Parameters
    ----------
    filepath : path to the input file (.pdf or .docx)
    use_vision : if True, call Gemini/OpenAI for semantic classification
    page_range : optional comma-separated page range (1-indexed), e.g. "1,3-5"
    progress_callback : optional callable(pct: float, msg: str)

    Returns
    -------
    LayoutDocument validated Pydantic model (Schema v3.0)
    """
    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".pdf":
        return process_pdf(filepath, use_vision, page_range, progress_callback)
    elif ext in (".docx", ".doc"):
        return process_docx(filepath, use_vision, progress_callback)
    else:
        raise ValueError(f"Unsupported file format: '{ext}'. Supported: .pdf, .docx")


# ═══════════════════════════════════════════════════════════════════════
#  DOCX pipeline
# ═══════════════════════════════════════════════════════════════════════

def process_docx(
    docx_path: str,
    use_vision: bool = True,
    progress_callback: Optional[Callable] = None,
) -> LayoutDocument:
    """End-to-end DOCX → LayoutDocument (Schema v3.0) pipeline."""
    from fast_vision.geometry.docx_extractor import extract_from_docx

    doc_id = str(uuid.uuid4())

    # ─── Step 1: Extract from DOCX ───────────────────────────────────
    _progress(progress_callback, 0.05, "Extracting paragraphs and tables from DOCX...")
    pages_data, merged_blocks, tables_by_page = extract_from_docx(docx_path)

    total_pages = len(pages_data)
    total_blocks = sum(len(b) for b in merged_blocks.values())
    logger.info("DOCX extraction: %d blocks, %d pages from %s", total_blocks, total_pages, docx_path)

    # ─── Step 2: Vision API semantic tagging (optional) ──────────────
    if use_vision and total_blocks > 0:
        _progress(progress_callback, 0.35, "Sending blocks to Vision API for classification...")
        try:
            _refine_docx_blocks_via_api(
                merged_blocks,
                progress_callback=lambda pct, msg: _progress(
                    progress_callback, 0.35 + pct * 0.45, msg
                ),
            )
        except Exception as e:
            logger.warning("Vision API failed for DOCX, using style-based classification: %s", e)
    else:
        _progress(progress_callback, 0.50, "Using DOCX style-based classification (no Vision API)...")

    # ─── Step 3: Style normalisation ─────────────────────────────────
    _progress(progress_callback, 0.85, "Normalising styles...")
    all_blocks_for_styles = []
    for blocks in merged_blocks.values():
        all_blocks_for_styles.extend(blocks)
    _, global_styles = normalize_styles(all_blocks_for_styles)

    # ─── Step 4: Assemble final document ─────────────────────────────
    _progress(progress_callback, 0.92, "Assembling Schema v3.0 document...")
    doc = assemble_document(
        doc_id=doc_id,
        pages_data=pages_data,
        merged_blocks=merged_blocks,
        tables_by_page=tables_by_page,
        styles=global_styles,
        source_type=SourceType.docx,
    )

    _progress(progress_callback, 1.0, "Done!")
    logger.info(
        "DOCX document assembled: %d pages, %d blocks, %d tables",
        len(doc.pages), len(doc.blocks), len(doc.tables or []),
    )
    return doc


def _refine_docx_blocks_via_api(
    merged_blocks: Dict[int, List[Dict[str, Any]]],
    progress_callback: Optional[Callable] = None,
) -> None:
    """Use Vision API (text-only) to classify blocks and add rhetoric.

    Batches blocks and processes ALL batches in parallel via ThreadPoolExecutor.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from fast_vision.vision.prompts import (
        SEMANTIC_TAGGER_SYSTEM,
        SEMANTIC_TAGGER_USER_TEMPLATE,
    )

    BATCH_SIZE = 50   # blocks per API call
    TEXT_TRUNCATE = 80  # chars per block — enough for type/role classification
    MAX_WORKERS = 8    # parallel API calls

    has_openai = bool(os.environ.get("OPENAI_API_KEY"))
    has_gemini = bool(os.environ.get("GEMINI_API_KEY"))

    if not has_openai and not has_gemini:
        raise ValueError("No API keys found.")

    # Collect all blocks
    all_blocks_info = []
    block_map = []
    for page_idx in sorted(merged_blocks.keys()):
        for bi, block in enumerate(merged_blocks[page_idx]):
            all_blocks_info.append({
                "index": len(all_blocks_info),
                "text": block.get("text", "")[:TEXT_TRUNCATE],
                "font": block.get("fontname", ""),
                "size": block.get("size", 0),
            })
            block_map.append((page_idx, bi))

    if not all_blocks_info:
        return

    total = len(all_blocks_info)
    n_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
    logger.info("DOCX API tagging: %d blocks in %d parallel batches", total, n_batches)

    # Build batches
    batches = []
    for batch_i in range(n_batches):
        start = batch_i * BATCH_SIZE
        end = min(start + BATCH_SIZE, total)
        batch = [dict(b, index=i) for i, b in enumerate(all_blocks_info[start:end])]
        batches.append((start, end, batch))

    # Initialize client
    openai_client = None
    gemini_client = None
    if has_openai:
        import openai
        openai_client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    else:
        from google import genai
        gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

    def _call_api(batch_tuple):
        start, end, batch = batch_tuple
        user_msg = SEMANTIC_TAGGER_USER_TEMPLATE.format(
            n_blocks=len(batch),
            blocks_json=json.dumps(batch),
        )
        try:
            if openai_client:
                resp = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": SEMANTIC_TAGGER_SYSTEM},
                        {"role": "user", "content": user_msg},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                )
                return start, json.loads(resp.choices[0].message.content).get("blocks", [])
            elif gemini_client:
                from google.genai import types
                resp = gemini_client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=[f"{SEMANTIC_TAGGER_SYSTEM}\n\n{user_msg}"],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.0,
                    ),
                )
                return start, json.loads(resp.text).get("blocks", [])
        except Exception as e:
            logger.warning("Batch starting at %d failed: %s", start, e)
            return start, []

    # Fire all batches in parallel
    if progress_callback:
        progress_callback(0.1, f"Firing {n_batches} parallel API calls...")

    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, n_batches)) as pool:
        futures = {pool.submit(_call_api, b): b for b in batches}
        done_count = 0
        for future in as_completed(futures):
            start, tags = future.result()
            done_count += 1
            if progress_callback:
                progress_callback(done_count / n_batches, f"Received batch {done_count}/{n_batches}")

            for tag in tags:
                local_idx = tag.get("block_index")
                if local_idx is not None and 0 <= local_idx < BATCH_SIZE:
                    global_idx = start + local_idx
                    if global_idx < len(block_map):
                        page_idx, bi = block_map[global_idx]
                        block = merged_blocks[page_idx][bi]
                        block["block_type"] = tag.get("block_type", block.get("block_type", "paragraph"))
                        block["role"] = tag.get("role", block.get("role", "paragraph"))
                        block["reading_order"] = tag.get("reading_order", block.get("reading_order", global_idx))
                        block["rhetoric"] = tag.get("rhetoric")
                        block["rhetoric_features"] = tag.get("rhetoric_features")


# ═══════════════════════════════════════════════════════════════════════
#  PDF pipeline
# ═══════════════════════════════════════════════════════════════════════

def process_pdf(
    pdf_path: str,
    use_vision: bool = True,
    page_range: Optional[str] = None,
    progress_callback: Optional[Callable] = None,
) -> LayoutDocument:
    """End-to-end PDF → LayoutDocument (Schema v3.0) pipeline."""
    doc_id = str(uuid.uuid4())

    # ─── Step 1: Extract chars ───────────────────────────────────────
    _progress(progress_callback, 0.05, "Extracting characters from PDF...")
    pages_data = extract_chars_from_pdf(pdf_path)

    if page_range:
        pages_to_process = _parse_page_range(page_range, len(pages_data))
        pages_data = [p for p in pages_data if p["page_number"] in pages_to_process]

    total_pages = len(pages_data)
    logger.info("Processing %d pages from %s", total_pages, pdf_path)

    # ─── Step 2: Build geometry per page (parallel) ────────────────────
    from concurrent.futures import ThreadPoolExecutor, as_completed

    merged_blocks: Dict[int, List[Dict[str, Any]]] = {}
    tables_by_page: Dict[int, List[Dict[str, Any]]] = {}
    all_blocks_flat: List[Dict[str, Any]] = []

    def _build_page_geometry(page):
        page_idx = page["page_number"] - 1
        chars = page["chars"]
        words = build_words(chars)
        lines_list = build_lines(words)
        blocks = build_blocks(lines_list)
        tables = extract_tables(pdf_path, page["page_number"])
        blocks = deduplicate_blocks_from_tables(blocks, tables)
        return page_idx, blocks, tables

    _progress(progress_callback, 0.08, f"Building geometry for {total_pages} pages in parallel...")

    with ThreadPoolExecutor(max_workers=min(8, total_pages)) as pool:
        futures = {pool.submit(_build_page_geometry, p): p for p in pages_data}
        done = 0
        for future in as_completed(futures):
            page_idx, blocks, tables = future.result()
            merged_blocks[page_idx] = blocks
            tables_by_page[page_idx] = tables
            all_blocks_flat.extend(blocks)
            done += 1
            pct = 0.08 + 0.27 * (done / total_pages)
            _progress(progress_callback, pct, f"Geometry built for {done}/{total_pages} pages...")

    logger.info(
        "Geometry: %d blocks, %d tables across %d pages",
        len(all_blocks_flat),
        sum(len(t) for t in tables_by_page.values()),
        total_pages,
    )

    # ─── Step 3: Vision API semantic tagging ─────────────────────────
    if use_vision:
        _progress(progress_callback, 0.40, "Sending pages to Vision API for classification...")

        pages_blocks_input = [
            (page["page_number"] - 1, merged_blocks.get(page["page_number"] - 1, []))
            for page in pages_data
        ]

        def vision_progress(pct_inner: float, msg: str):
            overall = 0.40 + pct_inner * 0.40
            _progress(progress_callback, overall, msg)

        try:
            tags_by_page = tag_all_pages(
                pdf_path,
                pages_blocks_input,
                max_workers=min(total_pages, 8),
                progress_callback=vision_progress,
            )

            _progress(progress_callback, 0.82, "Matching geometry blocks to semantic tags...")
            for page_idx, blocks in merged_blocks.items():
                tags = tags_by_page.get(page_idx, [])
                merged_blocks[page_idx] = match_blocks_to_tags(blocks, tags)

        except Exception as e:
            logger.warning("Vision API failed, falling back to geometry-only: %s", e)
            for page_idx, blocks in merged_blocks.items():
                for i, b in enumerate(blocks):
                    b.setdefault("block_type", _guess_block_type(b))
                    b.setdefault("role", "paragraph")
                    b.setdefault("reading_order", i)
    else:
        _progress(progress_callback, 0.50, "Classifying blocks with heuristics (no Vision API)...")
        for page_idx, blocks in merged_blocks.items():
            for i, b in enumerate(blocks):
                b["block_type"] = _guess_block_type(b)
                b["role"] = _guess_role(b)
                b["reading_order"] = i

    # ─── Step 5: Style normalisation ─────────────────────────────────
    _progress(progress_callback, 0.88, "Normalising styles...")
    all_blocks_for_styles = []
    for blocks in merged_blocks.values():
        all_blocks_for_styles.extend(blocks)
    _, global_styles = normalize_styles(all_blocks_for_styles)

    # ─── Step 6: Assemble final document ─────────────────────────────
    _progress(progress_callback, 0.93, "Assembling Schema v3.0 document...")
    doc = assemble_document(
        doc_id=doc_id,
        pages_data=pages_data,
        merged_blocks=merged_blocks,
        tables_by_page=tables_by_page,
        styles=global_styles,
    )

    _progress(progress_callback, 1.0, "Done!")
    logger.info(
        "Document assembled: %d pages, %d blocks, %d tables",
        len(doc.pages), len(doc.blocks), len(doc.tables or []),
    )
    return doc


# ═══════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════

def _progress(callback: Optional[Callable], pct: float, msg: str) -> None:
    if callback:
        callback(pct, msg)


def _parse_page_range(page_range: str, total: int) -> set:
    """Parse '1,3-5,10' into a set of 1-indexed page numbers."""
    result = set()
    for part in page_range.split(","):
        part = part.strip()
        if "-" in part:
            try:
                a, b = part.split("-", 1)
                for p in range(int(a), int(b) + 1):
                    if 1 <= p <= total:
                        result.add(p)
            except ValueError:
                pass
        else:
            try:
                p = int(part)
                if 1 <= p <= total:
                    result.add(p)
            except ValueError:
                pass
    return result if result else set(range(1, total + 1))


def _guess_block_type(block: Dict[str, Any]) -> str:
    """Heuristic block type from font properties (no Vision API)."""
    size = block.get("size", 0)
    fontname = block.get("fontname", "").lower()
    text = block.get("text", "")

    if size >= 14 or ("bold" in fontname and size >= 12):
        return "heading"

    word_count = len(text.split())
    if word_count <= 3:
        if text.strip().isdigit():
            return "page_number"

    if text.lstrip().startswith(("•", "-", "–", "▪", "◦")) or (
        len(text) > 2 and text[0].isdigit() and text[1] in ".)"
    ):
        return "list_item"

    return "paragraph"


def _guess_role(block: Dict[str, Any]) -> str:
    """Heuristic role from block_type."""
    bt = block.get("block_type", "paragraph")
    role_map = {
        "heading": "section_title",
        "paragraph": "paragraph",
        "list_item": "list_item",
        "table": "table",
        "figure": "figure",
        "caption": "caption",
        "header": "header",
        "footer": "footer",
        "page_number": "footer",
        "code_block": "paragraph",
    }
    return role_map.get(bt, "paragraph")
