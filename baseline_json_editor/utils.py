"""
Utility functions for the Baseline JSON Editor.
Page rendering, serialization helpers, etc.
"""

from __future__ import annotations

import io
from typing import Any, Dict, List

import pypdfium2
from PIL import Image
from streamlit.runtime.uploaded_file_manager import UploadedFile

from converter.schema import BaselineBlock, BaselineDocument


def open_pdf(pdf_file: UploadedFile):
    """Open a PDF from an uploaded file."""
    stream = io.BytesIO(pdf_file.getvalue())
    return pypdfium2.PdfDocument(stream)


def get_page_image(pdf_file: UploadedFile, page_num: int, dpi: int = 96) -> Optional[Image.Image]:
    """Render a page from an uploaded file as a PIL Image."""
    if pdf_file.type and "pdf" in pdf_file.type:
        doc = open_pdf(pdf_file)
        page = doc[page_num]
        img = page.render(scale=dpi / 72).to_pil().convert("RGB")
        return img
    elif pdf_file.type and ("image/" in pdf_file.type):
        return Image.open(pdf_file).convert("RGB")
    return None


def get_page_count(pdf_file: UploadedFile) -> int:
    """Return the number of pages in the uploaded file."""
    if pdf_file.type and "pdf" in pdf_file.type:
        try:
            doc = open_pdf(pdf_file)
            return len(doc)
        except Exception:
            return 1
    return 1


def flatten_blocks(blocks: List[BaselineBlock]) -> List[BaselineBlock]:
    """Flatten a nested block tree into a flat list (depth-first)."""
    flat = []
    for block in blocks:
        flat.append(block)
        if block.children:
            flat.extend(flatten_blocks(block.children))
    return flat


def count_editable_fields(doc: BaselineDocument) -> int:
    """Count total editable content fields in the document."""
    count = 0
    for page in doc.pages:
        all_blocks = flatten_blocks(page.blocks)
        for block in all_blocks:
            if block.content:
                count += 1
    return count


def apply_content_edits(doc_dict: dict, edits: Dict[str, str]) -> dict:
    """
    Apply user content edits to a serialized baseline document dict.

    edits: mapping of block_id → new_content
    """
    if not edits:
        return doc_dict

    def _apply_to_blocks(blocks: List[dict]):
        for block in blocks:
            block_id = block.get("id", "")
            if block_id in edits:
                block["content"] = edits[block_id]
            children = block.get("children", [])
            if children:
                _apply_to_blocks(children)

    for page in doc_dict.get("pages", []):
        _apply_to_blocks(page.get("blocks", []))

    # Also apply title edit
    if "__title__" in edits:
        doc_dict["title"] = edits["__title__"]

    return doc_dict

def clear_document_content(doc: BaselineDocument) -> BaselineDocument:
    """
    Returns a deep copy of the BaselineDocument with all text content explicitly
    wiped to empty strings, leaving only the structural schema and formatting properties.
    """
    # Create a deep copy using Pydantic's serialization
    import json
    empty_doc = BaselineDocument.model_validate_json(doc.model_dump_json())
    empty_doc.title = ""
    
    def _clear_blocks(blocks: List[BaselineBlock]):
        for block in blocks:
            block.content = ""
            if block.children:
                _clear_blocks(block.children)
                
    for page in empty_doc.pages:
        _clear_blocks(page.blocks)
        
    return empty_doc


def build_export_json(doc: BaselineDocument, edits: Dict[str, str]) -> dict:
    """Build the final JSON dict for export, with edits applied."""
    doc_dict = doc.model_dump()
    doc_dict = apply_content_edits(doc_dict, edits)

    # Remove raw HTML from export to keep it clean
    def _strip_html(blocks: List[dict]):
        for block in blocks:
            block.pop("html", None)
            children = block.get("children", [])
            if children:
                _strip_html(children)

    for page in doc_dict.get("pages", []):
        _strip_html(page.get("blocks", []))

    return doc_dict


def get_block_icon(block_type: str) -> str:
    """Return an emoji icon for a block type."""
    icons = {
        "SectionHeader": "📑",
        "Text": "📝",
        "Table": "📊",
        "ListItem": "📋",
        "ListGroup": "📋",
        "Code": "💻",
        "Equation": "🔢",
        "Figure": "🖼️",
        "Picture": "🖼️",
        "Caption": "💬",
        "Footnote": "📌",
        "Form": "📝",
        "Handwriting": "✍️",
        "TableOfContents": "📖",
        "Reference": "🔗",
        "Page": "📄",
        "ComplexRegion": "🧩",
    }
    return icons.get(block_type, "📦")
