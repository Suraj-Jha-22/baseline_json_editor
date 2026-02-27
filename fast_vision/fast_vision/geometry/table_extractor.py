"""
Extract structured tables from PDF pages using pdfplumber's built-in
table detection (line-intersection algorithm).

Each table is returned as a dict with: id, page, rows, cols, bbox, cells.
Also provides deduplication to remove text blocks that overlap with detected tables.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

import pdfplumber

logger = logging.getLogger(__name__)


def extract_tables(pdf_path: str, page_number: int) -> List[Dict[str, Any]]:
    """Detect and extract tables from a single page.

    Parameters
    ----------
    pdf_path : path to the PDF file
    page_number : 1-indexed page number

    Returns
    -------
    list of table dicts with keys: id, page, rows, cols, bbox, cells, block_type
    """
    tables_out: List[Dict[str, Any]] = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            if page_number > len(pdf.pages):
                return []

            page = pdf.pages[page_number - 1]  # 0-indexed internally

            detected = page.find_tables()
            if not detected:
                return []

            for tbl in detected:
                tbl_bbox = tbl.bbox  # (x0, y0, x1, y1) — already in pt
                data = tbl.extract()
                if not data:
                    continue

                num_rows = len(data)
                num_cols = max(len(row) for row in data) if data else 0

                cells: List[Dict[str, Any]] = []
                for r, row in enumerate(data):
                    for c, cell_text in enumerate(row or []):
                        # pdfplumber doesn't give per-cell bboxes natively,
                        # so we approximate from the table grid.
                        cell_bbox = _approx_cell_bbox(tbl_bbox, num_rows, num_cols, r, c)
                        cells.append({
                            "row": r,
                            "col": c,
                            "row_span": 1,
                            "col_span": 1,
                            "text": (cell_text or "").strip(),
                            "bbox": list(cell_bbox),
                        })

                tables_out.append({
                    "id": str(uuid.uuid4()),
                    "page": page_number,
                    "rows": num_rows,
                    "cols": num_cols,
                    "bbox": list(tbl_bbox),
                    "cells": cells,
                    "block_type": "table",
                })

    except Exception as e:
        logger.warning("Table extraction failed on page %d: %s", page_number, e)

    logger.debug("Page %d: found %d tables", page_number, len(tables_out))
    return tables_out


def _approx_cell_bbox(
    table_bbox: tuple,
    n_rows: int,
    n_cols: int,
    row: int,
    col: int,
) -> tuple:
    """Approximate a cell's bounding box by dividing the table evenly."""
    x0, y0, x1, y1 = table_bbox
    col_w = (x1 - x0) / max(n_cols, 1)
    row_h = (y1 - y0) / max(n_rows, 1)
    return (
        round(x0 + col * col_w, 2),
        round(y0 + row * row_h, 2),
        round(x0 + (col + 1) * col_w, 2),
        round(y0 + (row + 1) * row_h, 2),
    )


def deduplicate_blocks_from_tables(
    text_blocks: List[Dict[str, Any]],
    tables: List[Dict[str, Any]],
    overlap_threshold: float = 0.5,
) -> List[Dict[str, Any]]:
    """Remove text blocks that significantly overlap with detected tables."""
    if not tables:
        return text_blocks

    clean: List[Dict[str, Any]] = []
    for block in text_blocks:
        bx0, by0, bx1, by1 = block["x0"], block["y0"], block["x1"], block["y1"]
        block_area = max((bx1 - bx0) * (by1 - by0), 0.01)

        overlaps = False
        for table in tables:
            tx0, ty0, tx1, ty1 = table["bbox"]
            ix0 = max(bx0, tx0)
            iy0 = max(by0, ty0)
            ix1 = min(bx1, tx1)
            iy1 = min(by1, ty1)
            inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
            if inter / block_area > overlap_threshold:
                overlaps = True
                break

        if not overlaps:
            clean.append(block)

    removed = len(text_blocks) - len(clean)
    if removed:
        logger.debug("Removed %d text blocks overlapping with tables", removed)
    return clean
