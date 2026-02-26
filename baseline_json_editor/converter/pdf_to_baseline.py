"""
Core conversion logic: Document → Baseline JSON.

Uses Marker's PdfConverter to process the document, then transforms
the Marker JSON output into our BaselineDocument schema.

PERFORMANCE OPTIMIZATIONS:
- Models are cached via Streamlit's @st.cache_resource (loaded once)
- Converter instance is reused across calls
- pdftext_workers=1 to avoid multiprocessing overhead in Streamlit
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from bs4 import BeautifulSoup

from converter.schema import (
    BaselineBlock,
    BaselineDocument,
    BaselineMetadata,
    BaselinePage,
    BlockProperties,
)


def extract_text_from_html(html: str) -> str:
    """Strip HTML tags and return clean text content."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_properties_from_block(block: dict) -> Dict[str, Any]:
    """Extract formatting / structural properties from a Marker JSON block."""
    props: Dict[str, Any] = {}
    block_type = block.get("block_type", "")

    if "SectionHeader" in block_type:
        html = block.get("html", "")
        level_match = re.search(r"<h(\d)", html)
        if level_match:
            props["heading_level"] = int(level_match.group(1))

    if "Table" in block_type:
        html = block.get("html", "")
        soup = BeautifulSoup(html, "html.parser")
        rows = soup.find_all("tr")
        props["row_count"] = len(rows)
        if rows:
            cols = rows[0].find_all(["td", "th"])
            props["column_count"] = len(cols)

    if "ListItem" in block_type or "ListGroup" in block_type:
        html = block.get("html", "")
        if "<ol" in html:
            props["list_type"] = "ordered"
        else:
            props["list_type"] = "unordered"

    if "Code" in block_type:
        html = block.get("html", "")
        lang_match = re.search(r'class="language-(\w+)"', html)
        if lang_match:
            props["language"] = lang_match.group(1)

    if "blockquote" in block.get("html", "").lower():
        props["blockquote"] = True

    return props


def marker_block_to_baseline(block: dict, page_num: int) -> BaselineBlock:
    """Transform a single Marker JSON block into a BaselineBlock."""
    block_type = block.get("block_type", "Unknown")
    html = block.get("html", "")
    content = extract_text_from_html(html)
    properties = extract_properties_from_block(block)
    bbox = block.get("bbox", [])

    section_hierarchy = block.get("section_hierarchy")
    if section_hierarchy:
        section_hierarchy = {str(k): str(v) for k, v in section_hierarchy.items()}

    children_data = block.get("children", [])
    children = []
    if children_data:
        for child in children_data:
            children.append(marker_block_to_baseline(child, page_num))

    if children and not content:
        content = ""

    images = block.get("images")
    if images:
        properties["has_images"] = True
        properties["image_keys"] = list(images.keys())

    block_props = BlockProperties(**properties) if properties else None

    return BaselineBlock(
        id=block.get("id", f"page_{page_num}/{block_type}/auto"),
        block_type=block_type,
        content=content,
        html=html,
        properties=block_props,
        bbox=bbox,
        section_hierarchy=section_hierarchy,
        children=children,
    )


# ────────────────────────────────────────────────────────────
# Cached model loading (only loaded ONCE per session)
# ────────────────────────────────────────────────────────────

_cached_models = None
_cached_converter = None


def get_cached_models():
    """Load Marker AI models once and cache them globally."""
    global _cached_models
    if _cached_models is None:
        from marker.models import create_model_dict
        _cached_models = create_model_dict()
    return _cached_models


def get_cached_converter(
    page_range: Optional[str] = None,
    force_ocr: bool = False,
    use_llm: bool = False,
):
    """Get or create a PdfConverter (models are cached)."""
    from marker.config.parser import ConfigParser
    from marker.converters.pdf import PdfConverter

    cli_options: Dict[str, Any] = {
        "output_format": "json",
        "force_ocr": force_ocr,
        "use_llm": use_llm,
    }
    if page_range:
        cli_options["page_range"] = page_range

    config_parser = ConfigParser(cli_options)
    config_dict = config_parser.generate_config_dict()
    config_dict["pdftext_workers"] = 1

    model_dict = get_cached_models()

    converter = PdfConverter(
        config=config_dict,
        artifact_dict=model_dict,
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
        llm_service=config_parser.get_llm_service(),
    )
    return converter, config_parser


def convert_document_to_baseline(
    filepath: str,
    page_range: Optional[str] = None,
    force_ocr: bool = False,
    use_llm: bool = False,
    progress_callback=None,
) -> BaselineDocument:
    """
    Convert a document file to a BaselineDocument.

    Uses cached Marker models so only the first conversion is slow.
    Subsequent conversions reuse loaded models.
    """
    from marker.output import text_from_rendered

    if progress_callback:
        progress_callback(0.1, "Loading AI models (cached after first run)...")
    logger.info("Loading Marker AI models (cached after first run)...")

    converter, config_parser = get_cached_converter(
        page_range=page_range,
        force_ocr=force_ocr,
        use_llm=use_llm,
    )

    if progress_callback:
        progress_callback(0.3, "Running document conversion pipeline...")
    logger.info(f"Running Marker document conversion pipeline for: {filepath}")

    rendered = converter(filepath)

    if progress_callback:
        progress_callback(0.8, "Building baseline JSON schema...")
    logger.info("Conversion finished. Building baseline JSON schema...")

    text_json, ext, _ = text_from_rendered(rendered)
    marker_output = json.loads(text_json)

    # Build baseline document
    filename = os.path.basename(filepath)
    title = os.path.splitext(filename)[0].replace("_", " ").replace("-", " ").title()

    pages: List[BaselinePage] = []
    block_type_counts: Dict[str, int] = {}

    children = marker_output.get("children", [])
    logger.info(f"Parsing {len(children)} pages from Marker JSON output...")
    for page_idx, page_block in enumerate(children):
        page_blocks: List[BaselineBlock] = []

        page_children = page_block.get("children", [])
        for block_data in page_children:
            baseline_block = marker_block_to_baseline(block_data, page_idx)
            page_blocks.append(baseline_block)

            bt = baseline_block.block_type
            block_type_counts[bt] = block_type_counts.get(bt, 0) + 1

        page_bbox = page_block.get("bbox", [0, 0, 612, 792])
        width = page_bbox[2] - page_bbox[0] if len(page_bbox) >= 4 else 612
        height = page_bbox[3] - page_bbox[1] if len(page_bbox) >= 4 else 792

        pages.append(
            BaselinePage(
                page_number=page_idx + 1,
                width=width,
                height=height,
                blocks=page_blocks,
            )
        )

    toc = []
    metadata = marker_output.get("metadata", {})
    if "table_of_contents" in metadata:
        toc = metadata["table_of_contents"]

    if progress_callback:
        progress_callback(1.0, "Done!")

    return BaselineDocument(
        title=title,
        filename=filename,
        pages=pages,
        metadata=BaselineMetadata(
            total_pages=len(pages),
            block_type_counts=block_type_counts,
            table_of_contents=toc,
        ),
    )
