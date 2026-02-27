"""
Schema assembler — transforms merged block dicts into the final
LayoutDocument Pydantic model (Schema v3.0).

Computes: normalized bboxes, spans, tokens, tables, reading graph edges.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from fast_vision.schema import (
    AlignType,
    Block,
    BlockType,
    DocumentMeta,
    Edge,
    LayoutDocument,
    Page,
    Rhetoric,
    RhetoricFeatures,
    RoleType,
    SourceType,
    Span,
    Style,
    Table,
    TableCell,
    Token,
    WeightType,
)

logger = logging.getLogger(__name__)

# Valid enum values for safe mapping
_VALID_TYPES = {e.value for e in BlockType}
_VALID_ROLES = {e.value for e in RoleType}


def assemble_document(
    doc_id: str,
    pages_data: List[Dict[str, Any]],
    merged_blocks: Dict[int, List[Dict[str, Any]]],
    tables_by_page: Dict[int, List[Dict[str, Any]]],
    styles: Dict[str, Dict[str, Any]],
    source_type: SourceType = SourceType.pdf,
) -> LayoutDocument:
    """Build the final LayoutDocument from all extracted data.

    Parameters
    ----------
    doc_id : unique document identifier
    pages_data : list of page dicts from char_extractor or docx_extractor
    merged_blocks : dict mapping page_index (0-based) → list of block dicts
    tables_by_page : dict mapping page_index (0-based) → list of table dicts
    styles : global styles dict
    source_type : source format (pdf, docx, html, image)
    """
    pages: List[Page] = []
    all_blocks: List[Block] = []
    all_spans: List[Span] = []
    all_tokens: List[Token] = []
    all_tables: List[Table] = []
    all_edges: List[Edge] = []
    pydantic_styles: Dict[str, Style] = {}

    # Convert styles
    for sid, sdict in styles.items():
        pydantic_styles[sid] = Style(
            font_family=sdict.get("font_family"),
            size=sdict.get("size"),
            weight=_safe_weight(sdict.get("weight")),
            italic=sdict.get("italic", False),
            underline=sdict.get("underline", False),
            color=sdict.get("color"),
            align=_safe_align(sdict.get("align")),
        )

    prev_block_id: Optional[str] = None

    for page_data in pages_data:
        page_num = page_data["page_number"]
        page_w = page_data["width"]
        page_h = page_data["height"]
        page_idx = page_num - 1

        pages.append(Page(
            page_number=page_num,
            width=page_w,
            height=page_h,
            rotation=0,
        ))

        # Process text blocks
        blocks = merged_blocks.get(page_idx, [])
        # Sort by reading_order
        blocks.sort(key=lambda b: b.get("reading_order", 0))

        for block_dict in blocks:
            block_id = block_dict.get("id", str(uuid.uuid4()))
            bbox = [block_dict["x0"], block_dict["y0"], block_dict["x1"], block_dict["y1"]]
            bbox_norm = _normalize_bbox(bbox, page_w, page_h)

            block_type = _safe_block_type(block_dict.get("block_type", "paragraph"))
            role = _safe_role(block_dict.get("role", "paragraph"))
            text = block_dict.get("text", "")

            # Build rhetoric
            rhetoric = None
            rhetoric_raw = block_dict.get("rhetoric")
            if rhetoric_raw and isinstance(rhetoric_raw, dict):
                rhetoric = _build_rhetoric(rhetoric_raw)

            rhetoric_features = None
            rf_raw = block_dict.get("rhetoric_features")
            if rf_raw and isinstance(rf_raw, dict):
                rhetoric_features = _build_rhetoric_features(rf_raw)

            # HTML template
            html_tag = _html_tag_for_type(block_type)
            html_template = f"<{html_tag}>{{{{text}}}}</{html_tag}>"
            html_content = f"<{html_tag}>{text}</{html_tag}>"

            block = Block(
                id=block_id,
                type=block_type,
                role=role,
                page=page_num,
                bbox=bbox,
                bbox_norm=bbox_norm,
                reading_order=block_dict.get("reading_order", 0),
                z_index=0,
                parent=None,
                children=None,
                text=text,
                style_id=block_dict.get("style_id"),
                html=html_content,
                html_template=html_template,
                rhetoric=rhetoric,
                rhetoric_features=rhetoric_features,
            )
            all_blocks.append(block)

            # Build spans (one span per block for now)
            span_id = f"s-{block_id}"
            all_spans.append(Span(
                id=span_id,
                block_id=block_id,
                text=text,
                bbox=bbox,
                bbox_norm=bbox_norm,
                style_id=block_dict.get("style_id"),
            ))

            # Build tokens from words
            for word in block_dict.get("words", []):
                w_bbox = [word["x0"], word["y0"], word["x1"], word["y1"]]
                all_tokens.append(Token(
                    text=word["text"],
                    bbox=w_bbox,
                    bbox_norm=_normalize_bbox(w_bbox, page_w, page_h),
                    block_id=block_id,
                    span_id=span_id,
                ))

            # Reading graph edge
            if prev_block_id:
                all_edges.append(Edge(
                    **{"from": prev_block_id, "to": block_id, "relation": "next"}
                ))
            prev_block_id = block_id

        # Process tables
        for tbl_dict in tables_by_page.get(page_idx, []):
            tbl_id = tbl_dict["id"]
            tbl_bbox = tbl_dict.get("bbox")
            cells = []
            for cell_dict in tbl_dict.get("cells", []):
                c_bbox = cell_dict["bbox"]
                cells.append(TableCell(
                    row=cell_dict["row"],
                    col=cell_dict["col"],
                    row_span=cell_dict.get("row_span", 1),
                    col_span=cell_dict.get("col_span", 1),
                    text=cell_dict.get("text", ""),
                    bbox=c_bbox,
                    bbox_norm=_normalize_bbox(c_bbox, page_w, page_h),
                ))

            all_tables.append(Table(
                id=tbl_id,
                page=page_num,
                rows=tbl_dict["rows"],
                cols=tbl_dict["cols"],
                bbox=tbl_bbox,
                cells=cells,
            ))

            # Add a block entry for the table
            if tbl_bbox:
                table_block = Block(
                    id=tbl_id,
                    type=BlockType.table,
                    role=RoleType.table,
                    page=page_num,
                    bbox=tbl_bbox,
                    bbox_norm=_normalize_bbox(tbl_bbox, page_w, page_h),
                    reading_order=len(all_blocks),
                    text="[TABLE]",
                )
                all_blocks.append(table_block)

                if prev_block_id:
                    all_edges.append(Edge(
                        **{"from": prev_block_id, "to": tbl_id, "relation": "next"}
                    ))
                prev_block_id = tbl_id

    return LayoutDocument(
        document=DocumentMeta(
            document_id=doc_id,
            schema_version="3.0",
            source=source_type,
            page_count=len(pages),
        ),
        pages=pages,
        blocks=all_blocks,
        spans=all_spans if all_spans else None,
        tokens=all_tokens if all_tokens else None,
        tables=all_tables if all_tables else None,
        styles=pydantic_styles if pydantic_styles else None,
        reading_graph=all_edges if all_edges else None,
    )


# ── Helpers ──────────────────────────────────────────────────────────

def _normalize_bbox(bbox: List[float], page_w: float, page_h: float) -> List[float]:
    """Normalise absolute bbox to [0, 1] range."""
    if page_w <= 0 or page_h <= 0:
        return [0.0, 0.0, 0.0, 0.0]
    return [
        round(bbox[0] / page_w, 6),
        round(bbox[1] / page_h, 6),
        round(bbox[2] / page_w, 6),
        round(bbox[3] / page_h, 6),
    ]


def _safe_block_type(val: str) -> BlockType:
    """Map raw string to BlockType enum, default paragraph."""
    if val in _VALID_TYPES:
        return BlockType(val)
    return BlockType.paragraph


def _safe_role(val: str) -> RoleType:
    """Map raw string to RoleType enum, default paragraph."""
    if val in _VALID_ROLES:
        return RoleType(val)
    return RoleType.paragraph


def _safe_weight(val: Optional[str]) -> Optional[WeightType]:
    if val in ("normal", "bold"):
        return WeightType(val)
    return None


def _safe_align(val: Optional[str]) -> Optional[AlignType]:
    if val in ("left", "center", "right", "justify"):
        return AlignType(val)
    return None


def _html_tag_for_type(block_type: BlockType) -> str:
    """Map block type to a semantic HTML tag."""
    mapping = {
        BlockType.heading: "h2",
        BlockType.paragraph: "p",
        BlockType.list_item: "li",
        BlockType.table: "table",
        BlockType.figure: "figure",
        BlockType.caption: "figcaption",
        BlockType.header: "header",
        BlockType.footer: "footer",
        BlockType.page_number: "span",
        BlockType.code_block: "pre",
    }
    return mapping.get(block_type, "p")


def _build_rhetoric(raw: Dict[str, Any]) -> Optional[Rhetoric]:
    """Safely build Rhetoric from raw dict."""
    try:
        return Rhetoric(
            tone=raw.get("tone"),
            voice=raw.get("voice"),
            modality=raw.get("modality"),
            tense=raw.get("tense"),
            domain=raw.get("domain"),
        )
    except Exception:
        return None


def _build_rhetoric_features(raw: Dict[str, Any]) -> Optional[RhetoricFeatures]:
    """Safely build RhetoricFeatures from raw dict."""
    try:
        return RhetoricFeatures(
            avg_sentence_length=raw.get("avg_sentence_length"),
            modal_density=raw.get("modal_density"),
            passive_ratio=raw.get("passive_ratio"),
            legal_term_density=raw.get("legal_term_density"),
        )
    except Exception:
        return None
