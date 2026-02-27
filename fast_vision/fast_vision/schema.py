"""
Pydantic v2 models for Layout and Tone Aware Document Schema v3.0.

Matches the JSON Schema at:
  https://your-org.ai/schemas/layout-tone-document.schema.json

All bbox coordinates are in PDF points (1 pt = 1/72 inch).
"""

from __future__ import annotations

import hashlib
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Enums ────────────────────────────────────────────────────────────

class SourceType(str, Enum):
    pdf = "pdf"
    docx = "docx"
    html = "html"
    image = "image"


class BlockType(str, Enum):
    heading = "heading"
    paragraph = "paragraph"
    list_item = "list_item"
    table = "table"
    figure = "figure"
    caption = "caption"
    header = "header"
    footer = "footer"
    page_number = "page_number"
    code_block = "code_block"


class RoleType(str, Enum):
    title = "title"
    section_title = "section_title"
    subsection_title = "subsection_title"
    paragraph = "paragraph"
    list_item = "list_item"
    table = "table"
    figure = "figure"
    caption = "caption"
    header = "header"
    footer = "footer"


class WeightType(str, Enum):
    normal = "normal"
    bold = "bold"


class AlignType(str, Enum):
    left = "left"
    center = "center"
    right = "right"
    justify = "justify"


class RelationType(str, Enum):
    next = "next"
    parent = "parent"
    child = "child"
    caption_of = "caption_of"


class ToneType(str, Enum):
    formal = "formal"
    neutral = "neutral"
    conversational = "conversational"
    legal = "legal"
    compliance = "compliance"
    academic = "academic"


class VoiceType(str, Enum):
    active = "active"
    passive = "passive"
    mixed = "mixed"


class ModalityType(str, Enum):
    mandatory = "mandatory"
    advisory = "advisory"
    descriptive = "descriptive"


class TenseType(str, Enum):
    present = "present"
    past = "past"
    future = "future"
    mixed = "mixed"


class DomainType(str, Enum):
    legal = "legal"
    banking = "banking"
    technical = "technical"
    general = "general"


class PageUnit(str, Enum):
    pt = "pt"
    px = "px"


# ── Sub-models ───────────────────────────────────────────────────────

class Rhetoric(BaseModel):
    """Rhetorical / tone classification per block."""
    tone: Optional[ToneType] = None
    voice: Optional[VoiceType] = None
    modality: Optional[ModalityType] = None
    tense: Optional[TenseType] = None
    domain: Optional[DomainType] = None

    model_config = ConfigDict(extra="forbid")


class RhetoricFeatures(BaseModel):
    """Computed numeric rhetoric features per block."""
    avg_sentence_length: Optional[float] = None
    modal_density: Optional[float] = None
    passive_ratio: Optional[float] = None
    legal_term_density: Optional[float] = None

    model_config = ConfigDict(extra="forbid")


class Style(BaseModel):
    """Normalised font / formatting style."""
    font_family: Optional[str] = None
    size: Optional[float] = None
    weight: Optional[WeightType] = None
    italic: Optional[bool] = None
    underline: Optional[bool] = None
    color: Optional[str] = None
    align: Optional[AlignType] = None

    model_config = ConfigDict(extra="forbid")

    def compute_hash(self) -> str:
        """Deterministic 12-char hash for deduplication."""
        s = f"{self.font_family}|{self.size}|{self.weight}|{self.italic}|{self.color}"
        return hashlib.sha256(s.encode()).hexdigest()[:12]


# ── Core models ──────────────────────────────────────────────────────

class DocumentMeta(BaseModel):
    """Top-level document metadata."""
    document_id: str
    schema_version: str = "3.0"
    source: SourceType = SourceType.pdf
    page_count: Optional[int] = None


class Page(BaseModel):
    """Physical page dimensions."""
    page_number: int = Field(ge=1)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    rotation: int = Field(default=0)
    unit: PageUnit = PageUnit.pt


class Block(BaseModel):
    """A document block (paragraph, heading, table-ref, etc.)."""
    id: str
    type: BlockType
    role: Optional[RoleType] = None
    page: int = Field(ge=1)
    bbox: List[float] = Field(min_length=4, max_length=4)
    bbox_norm: Optional[List[float]] = Field(default=None, min_length=4, max_length=4)
    reading_order: int = Field(ge=0)
    z_index: int = 0
    parent: Optional[str] = None
    children: Optional[List[str]] = None
    text: Optional[str] = None
    style_id: Optional[str] = None
    html: Optional[str] = None
    html_template: Optional[str] = None
    rhetoric: Optional[Rhetoric] = None
    rhetoric_features: Optional[RhetoricFeatures] = None


class Span(BaseModel):
    """Inline run within a block (font/style change boundary)."""
    id: str
    block_id: str
    text: str
    bbox: List[float] = Field(min_length=4, max_length=4)
    bbox_norm: Optional[List[float]] = Field(default=None, min_length=4, max_length=4)
    style_id: Optional[str] = None


class Token(BaseModel):
    """Individual word-level token with bbox."""
    text: str
    bbox: List[float] = Field(min_length=4, max_length=4)
    bbox_norm: Optional[List[float]] = Field(default=None, min_length=4, max_length=4)
    block_id: str
    span_id: Optional[str] = None


class TableCell(BaseModel):
    """Single cell in a table grid."""
    row: int = Field(ge=0)
    col: int = Field(ge=0)
    row_span: int = Field(default=1, ge=1)
    col_span: int = Field(default=1, ge=1)
    text: str = ""
    bbox: List[float] = Field(min_length=4, max_length=4)
    bbox_norm: Optional[List[float]] = Field(default=None, min_length=4, max_length=4)
    style_id: Optional[str] = None


class Table(BaseModel):
    """Structured table with cell grid."""
    id: str
    page: int = Field(ge=1)
    rows: int = Field(ge=1)
    cols: int = Field(ge=1)
    bbox: Optional[List[float]] = Field(default=None, min_length=4, max_length=4)
    cells: List[TableCell]


class Edge(BaseModel):
    """Reading graph edge between blocks."""
    from_id: str = Field(alias="from")
    to: str
    relation: RelationType

    model_config = ConfigDict(populate_by_name=True)


# ── Root document ────────────────────────────────────────────────────

class LayoutDocument(BaseModel):
    """Root container — Layout and Tone Aware Document Schema v3.0."""
    document: DocumentMeta
    pages: List[Page]
    blocks: List[Block]
    spans: Optional[List[Span]] = None
    tokens: Optional[List[Token]] = None
    tables: Optional[List[Table]] = None
    styles: Optional[Dict[str, Style]] = None
    reading_graph: Optional[List[Edge]] = None
