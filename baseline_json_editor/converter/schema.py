"""
Pydantic models for the Baseline JSON schema.

The schema separates STRUCTURE (immutable) from CONTENT (editable).
- block_type, bbox, children, properties → locked (schema)
- content → editable by the user
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BlockProperties(BaseModel):
    """Specific formatting properties for a block."""
    heading_level: Optional[int] = Field(default=None, description="Heading level (1-6) for SectionHeaders")
    row_count: Optional[int] = Field(default=None, description="Number of rows for Tables")
    column_count: Optional[int] = Field(default=None, description="Number of columns for Tables")
    list_type: Optional[str] = Field(default=None, description="'ordered' or 'unordered' for Lists")
    language: Optional[str] = Field(default=None, description="Programming language for Code blocks")
    blockquote: Optional[bool] = Field(default=None, description="True if text is a blockquote")
    has_images: Optional[bool] = Field(default=None, description="True if block contains images")
    image_keys: Optional[List[str]] = Field(default=None, description="List of image identifiers")
    color: Optional[str] = Field(default=None, description="Primary text color (from style='color: ...')")
    bg_color: Optional[str] = Field(default=None, description="Background color (from style='background-color: ...')")
    font_family: Optional[str] = Field(default=None, description="Font family (from style='font-family: ...')")
    font_size: Optional[str] = Field(default=None, description="Font size (from style='font-size: ...')")


class BaselineBlock(BaseModel):
    """A single document block (paragraph, heading, table, etc.)."""

    id: str = Field(description="Unique block identifier (e.g. 'page_0/SectionHeader/0')")
    block_type: str = Field(description="Block type from Marker (SectionHeader, Text, Table, etc.)")
    content: str = Field(default="", description="Editable text content of this block")
    html: str = Field(default="", description="Original HTML representation from Marker")
    properties: Optional[BlockProperties] = Field(
        default=None,
        description="Read-only formatting properties (heading_level, blockquote, etc.)",
    )
    bbox: List[float] = Field(
        default_factory=list,
        description="Bounding box [x1, y1, x2, y2] — not editable",
    )
    section_hierarchy: Optional[Dict[str, str]] = Field(
        default=None,
        description="Section nesting path (e.g. {1: 'Chapter 1', 2: 'Introduction'})",
    )
    children: List[BaselineBlock] = Field(
        default_factory=list,
        description="Nested child blocks — structure is not editable",
    )


class BaselinePage(BaseModel):
    """A single page of the document."""

    page_number: int
    width: float = 0.0
    height: float = 0.0
    blocks: List[BaselineBlock] = Field(default_factory=list)


class BaselineMetadata(BaseModel):
    """Document-level metadata."""

    total_pages: int = 0
    block_type_counts: Dict[str, int] = Field(default_factory=dict)
    table_of_contents: List[Dict[str, Any]] = Field(default_factory=list)
    converter_info: str = "marker-pdf"


class BaselineDocument(BaseModel):
    """Root model for the baseline JSON schema."""

    title: str = Field(default="Untitled Document", description="Editable document title")
    filename: str = ""
    schema_version: str = "1.0.0"
    pages: List[BaselinePage] = Field(default_factory=list)
    metadata: BaselineMetadata = Field(default_factory=BaselineMetadata)
