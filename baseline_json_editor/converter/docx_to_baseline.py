"""
Direct DOCX → Baseline JSON conversion (NO API calls).

Uses mammoth to convert DOCX → HTML, then parses the HTML
directly into the BaselineDocument schema. This is instant
compared to the Vision API path.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup, NavigableString, Tag

from converter.schema import (
    BaselineBlock,
    BaselineDocument,
    BaselineMetadata,
    BaselinePage,
    BlockProperties,
)

logger = logging.getLogger(__name__)


def _tag_to_block_type(tag: Tag) -> str:
    """Map an HTML tag to a Baseline block_type."""
    name = tag.name.lower()
    if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
        return "SectionHeader"
    if name == "table":
        return "Table"
    if name in ("ul", "ol"):
        return "ListGroup"
    if name == "li":
        return "ListItem"
    if name in ("pre", "code"):
        return "Code"
    if name == "blockquote":
        return "Text"
    if name in ("img", "figure"):
        return "Figure"
    # p, div, span, etc.
    return "Text"


def _extract_inline_styles(tag: Tag) -> Dict[str, Any]:
    """Pull inline CSS style properties into BlockProperties fields."""
    props: Dict[str, Any] = {}
    style = tag.get("style", "")
    if not style:
        return props

    # color
    m = re.search(r'(?<![a-z-])color\s*:\s*([^;]+)', style)
    if m:
        props["color"] = m.group(1).strip()

    # background-color
    m = re.search(r'background-color\s*:\s*([^;]+)', style)
    if m:
        props["bg_color"] = m.group(1).strip()

    # font-family
    m = re.search(r'font-family\s*:\s*([^;]+)', style)
    if m:
        props["font_family"] = m.group(1).strip()

    # font-size
    m = re.search(r'font-size\s*:\s*([^;]+)', style)
    if m:
        props["font_size"] = m.group(1).strip()

    return props


def _get_text(tag: Tag) -> str:
    """Get clean text from a tag."""
    text = tag.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def _parse_table(table_tag: Tag, block_idx: int) -> BaselineBlock:
    """Parse an HTML <table> into a BaselineBlock with children rows/cells."""
    rows = table_tag.find_all("tr")
    children = []
    for r_idx, row in enumerate(rows):
        cells = row.find_all(["td", "th"])
        cell_children = []
        for c_idx, cell in enumerate(cells):
            cell_children.append(BaselineBlock(
                id=f"page_0/TableCell/{block_idx}_r{r_idx}_c{c_idx}",
                block_type="Text",
                content=_get_text(cell),
                html=str(cell),
            ))
        children.append(BaselineBlock(
            id=f"page_0/TableRow/{block_idx}_r{r_idx}",
            block_type="Text",
            content="",
            html=str(row),
            children=cell_children,
        ))

    props = BlockProperties(
        row_count=len(rows),
        column_count=len(rows[0].find_all(["td", "th"])) if rows else 0,
    )

    return BaselineBlock(
        id=f"page_0/Table/{block_idx}",
        block_type="Table",
        content=_get_text(table_tag),
        html=str(table_tag),
        properties=props,
        children=children,
    )


def _parse_list(list_tag: Tag, block_idx: int) -> BaselineBlock:
    """Parse <ul>/<ol> into a ListGroup with ListItem children."""
    list_type = "ordered" if list_tag.name == "ol" else "unordered"
    items = list_tag.find_all("li", recursive=False)
    children = []
    for i, li in enumerate(items):
        children.append(BaselineBlock(
            id=f"page_0/ListItem/{block_idx}_{i}",
            block_type="ListItem",
            content=_get_text(li),
            html=str(li),
        ))

    return BaselineBlock(
        id=f"page_0/ListGroup/{block_idx}",
        block_type="ListGroup",
        content="",
        html=str(list_tag),
        properties=BlockProperties(list_type=list_type),
        children=children,
    )


def convert_docx_direct(
    filepath: str,
    progress_callback=None,
) -> BaselineDocument:
    """
    Convert a DOCX file directly to BaselineDocument without any API calls.
    Uses mammoth for DOCX→HTML, then parses the HTML into blocks.
    """
    import mammoth

    if progress_callback:
        progress_callback(0.1, "Reading DOCX with mammoth...")

    logger.info(f"Direct DOCX conversion starting for: {filepath}")

    with open(filepath, "rb") as f:
        result = mammoth.convert_to_html(f)
        html_str = result.value

    if result.messages:
        for msg in result.messages:
            logger.warning(f"mammoth: {msg}")

    if progress_callback:
        progress_callback(0.4, "Parsing HTML structure into blocks...")

    soup = BeautifulSoup(html_str, "html.parser")

    blocks: List[BaselineBlock] = []
    block_type_counts: Dict[str, int] = {}
    block_idx = 0

    # Walk top-level elements
    for element in soup.children:
        if isinstance(element, NavigableString):
            text = str(element).strip()
            if not text:
                continue
            # Bare text node
            blocks.append(BaselineBlock(
                id=f"page_0/Text/{block_idx}",
                block_type="Text",
                content=text,
                html=text,
            ))
            block_type_counts["Text"] = block_type_counts.get("Text", 0) + 1
            block_idx += 1
            continue

        if not isinstance(element, Tag):
            continue

        tag_name = element.name.lower()

        # Skip empty tags
        text = _get_text(element)
        if not text and tag_name not in ("table", "ul", "ol", "img", "figure"):
            continue

        # Tables
        if tag_name == "table":
            block = _parse_table(element, block_idx)
            blocks.append(block)
            block_type_counts["Table"] = block_type_counts.get("Table", 0) + 1
            block_idx += 1
            continue

        # Lists
        if tag_name in ("ul", "ol"):
            block = _parse_list(element, block_idx)
            blocks.append(block)
            block_type_counts["ListGroup"] = block_type_counts.get("ListGroup", 0) + 1
            block_idx += 1
            continue

        # Headings
        if tag_name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag_name[1])
            style_props = _extract_inline_styles(element)
            style_props["heading_level"] = level
            props = BlockProperties(**style_props)

            blocks.append(BaselineBlock(
                id=f"page_0/SectionHeader/{block_idx}",
                block_type="SectionHeader",
                content=text,
                html=str(element),
                properties=props,
            ))
            block_type_counts["SectionHeader"] = block_type_counts.get("SectionHeader", 0) + 1
            block_idx += 1
            continue

        # Blockquotes
        if tag_name == "blockquote":
            style_props = _extract_inline_styles(element)
            style_props["blockquote"] = True
            blocks.append(BaselineBlock(
                id=f"page_0/Text/{block_idx}",
                block_type="Text",
                content=text,
                html=str(element),
                properties=BlockProperties(**style_props),
            ))
            block_type_counts["Text"] = block_type_counts.get("Text", 0) + 1
            block_idx += 1
            continue

        # Code blocks
        if tag_name in ("pre", "code"):
            blocks.append(BaselineBlock(
                id=f"page_0/Code/{block_idx}",
                block_type="Code",
                content=text,
                html=str(element),
            ))
            block_type_counts["Code"] = block_type_counts.get("Code", 0) + 1
            block_idx += 1
            continue

        # Images / Figures
        if tag_name in ("img", "figure"):
            blocks.append(BaselineBlock(
                id=f"page_0/Figure/{block_idx}",
                block_type="Figure",
                content=element.get("alt", ""),
                html=str(element),
            ))
            block_type_counts["Figure"] = block_type_counts.get("Figure", 0) + 1
            block_idx += 1
            continue

        # Default: paragraphs, divs, spans, etc.
        style_props = _extract_inline_styles(element)
        props = BlockProperties(**style_props) if style_props else None

        blocks.append(BaselineBlock(
            id=f"page_0/Text/{block_idx}",
            block_type="Text",
            content=text,
            html=str(element),
            properties=props,
        ))
        block_type_counts["Text"] = block_type_counts.get("Text", 0) + 1
        block_idx += 1

    if progress_callback:
        progress_callback(0.9, "Assembling Baseline Document...")

    filename = os.path.basename(filepath)
    title = os.path.splitext(filename)[0].replace("_", " ").replace("-", " ").title()

    # Split blocks roughly by an estimated capacity per page (e.g. ~35 blocks per page)
    # This prevents the DOCX from dumping everything into a single massive scrolling page.
    BLOCKS_PER_PAGE = 35
    pages: List[BaselinePage] = []
    
    if not blocks:
        # Create an empty page if no content
        pages.append(BaselinePage(page_number=1, width=612, height=792, blocks=[]))
    else:
        for i in range(0, len(blocks), BLOCKS_PER_PAGE):
            chunk = blocks[i : i + BLOCKS_PER_PAGE]
            # Rename the ids to match the new page number
            page_num = (i // BLOCKS_PER_PAGE) + 1
            for block in chunk:
                # Replace 'page_0/' with f'page_{page_num-1}/'
                block.id = block.id.replace("page_0/", f"page_{page_num-1}/")
                if block.children:
                    for child in block.children:
                        child.id = child.id.replace("page_0/", f"page_{page_num-1}/")

            pages.append(
                BaselinePage(
                    page_number=page_num,
                    width=612,
                    height=792,
                    blocks=chunk,
                )
            )

    if progress_callback:
        progress_callback(1.0, "Done!")

    logger.info(f"Direct DOCX conversion complete: {len(blocks)} blocks extracted into {len(pages)} pages.")

    return BaselineDocument(
        title=title,
        filename=filename,
        pages=pages,
        metadata=BaselineMetadata(
            total_pages=len(pages),
            block_type_counts=block_type_counts,
            converter_info="Direct (mammoth → HTML parser, no API)",
        ),
    )
