"""
Smoke tests for fast_vision pipeline.

Tests:
1. Schema model validation
2. Import chain
3. Geometry pipeline (if a test PDF is available)
"""

from __future__ import annotations

import json
import os
import uuid

import pytest

from fast_vision.schema import (
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
)


class TestSchemaModels:
    """Verify Pydantic models match Schema v3.0."""

    def test_document_meta(self):
        meta = DocumentMeta(document_id="test-123", schema_version="3.0", source="pdf", page_count=5)
        assert meta.document_id == "test-123"
        assert meta.source == SourceType.pdf

    def test_page(self):
        page = Page(page_number=1, width=612.0, height=792.0)
        assert page.rotation == 0
        assert page.unit.value == "pt"

    def test_block_with_rhetoric(self):
        block = Block(
            id="blk-001",
            type=BlockType.paragraph,
            role=RoleType.paragraph,
            page=1,
            bbox=[72.0, 100.0, 540.0, 120.0],
            bbox_norm=[0.117, 0.126, 0.882, 0.151],
            reading_order=0,
            text="This is a test paragraph.",
            rhetoric=Rhetoric(
                tone="formal",
                voice="active",
                modality="descriptive",
                tense="present",
                domain="general",
            ),
            rhetoric_features=RhetoricFeatures(
                avg_sentence_length=5.0,
                modal_density=0.0,
                passive_ratio=0.0,
                legal_term_density=0.0,
            ),
        )
        assert block.type == BlockType.paragraph
        assert block.rhetoric.tone.value == "formal"
        assert block.rhetoric_features.avg_sentence_length == 5.0

    def test_style(self):
        style = Style(font_family="Arial", size=12.0, weight="bold", italic=False, color="#000000")
        sid = style.compute_hash()
        assert isinstance(sid, str)
        assert len(sid) == 12

    def test_table_cell(self):
        cell = TableCell(row=0, col=0, text="Hello", bbox=[0, 0, 100, 50])
        assert cell.row_span == 1
        assert cell.col_span == 1

    def test_table(self):
        table = Table(
            id="tbl-001",
            page=1,
            rows=2,
            cols=2,
            cells=[
                TableCell(row=0, col=0, text="A", bbox=[0, 0, 50, 25]),
                TableCell(row=0, col=1, text="B", bbox=[50, 0, 100, 25]),
                TableCell(row=1, col=0, text="C", bbox=[0, 25, 50, 50]),
                TableCell(row=1, col=1, text="D", bbox=[50, 25, 100, 50]),
            ],
        )
        assert len(table.cells) == 4

    def test_edge_alias(self):
        edge = Edge(**{"from": "blk-001", "to": "blk-002", "relation": "next"})
        dumped = edge.model_dump(by_alias=True)
        assert "from" in dumped
        assert dumped["from"] == "blk-001"

    def test_full_document_roundtrip(self):
        doc = LayoutDocument(
            document=DocumentMeta(document_id=str(uuid.uuid4()), source="pdf", page_count=1),
            pages=[Page(page_number=1, width=612.0, height=792.0)],
            blocks=[
                Block(
                    id="blk-001",
                    type="heading",
                    role="title",
                    page=1,
                    bbox=[72.0, 72.0, 540.0, 100.0],
                    reading_order=0,
                    text="Test Document",
                ),
                Block(
                    id="blk-002",
                    type="paragraph",
                    role="paragraph",
                    page=1,
                    bbox=[72.0, 110.0, 540.0, 200.0],
                    reading_order=1,
                    text="This is body text.",
                ),
            ],
            reading_graph=[
                Edge(**{"from": "blk-001", "to": "blk-002", "relation": "next"}),
            ],
        )

        # Serialize → deserialize roundtrip
        json_str = doc.model_dump_json(by_alias=True, exclude_none=True, indent=2)
        parsed = json.loads(json_str)

        assert parsed["document"]["schema_version"] == "3.0"
        assert len(parsed["blocks"]) == 2
        assert parsed["blocks"][0]["type"] == "heading"
        assert parsed["reading_graph"][0]["from"] == "blk-001"


class TestGeometryImports:
    """Verify all geometry modules import cleanly."""

    def test_char_extractor_import(self):
        from fast_vision.geometry.char_extractor import extract_chars_from_pdf
        assert callable(extract_chars_from_pdf)

    def test_word_builder_import(self):
        from fast_vision.geometry.word_builder import build_words
        assert callable(build_words)

    def test_line_builder_import(self):
        from fast_vision.geometry.line_builder import build_lines
        assert callable(build_lines)

    def test_block_builder_import(self):
        from fast_vision.geometry.block_builder import build_blocks
        assert callable(build_blocks)

    def test_table_extractor_import(self):
        from fast_vision.geometry.table_extractor import extract_tables
        assert callable(extract_tables)


class TestVisionImports:
    """Verify vision modules import cleanly."""

    def test_page_renderer_import(self):
        from fast_vision.vision.page_renderer import render_page, image_to_base64
        assert callable(render_page)
        assert callable(image_to_base64)

    def test_api_tagger_import(self):
        from fast_vision.vision.api_tagger import tag_all_pages
        assert callable(tag_all_pages)


class TestPipelineImport:
    """Verify the main pipeline imports."""

    def test_pipeline_import(self):
        from fast_vision.pipeline import process_pdf
        assert callable(process_pdf)


class TestWordBuilder:
    """Unit test word builder with synthetic data."""

    def test_basic_word_building(self):
        from fast_vision.geometry.word_builder import build_words

        chars = [
            {"text": "H", "x0": 10, "y0": 100, "x1": 18, "y1": 112, "fontname": "Arial", "size": 12, "color": "#000"},
            {"text": "i", "x0": 18, "y0": 100, "x1": 22, "y1": 112, "fontname": "Arial", "size": 12, "color": "#000"},
            {"text": " ", "x0": 22, "y0": 100, "x1": 26, "y1": 112, "fontname": "Arial", "size": 12, "color": "#000"},
            {"text": "W", "x0": 40, "y0": 100, "x1": 52, "y1": 112, "fontname": "Arial", "size": 12, "color": "#000"},
            {"text": "o", "x0": 52, "y0": 100, "x1": 60, "y1": 112, "fontname": "Arial", "size": 12, "color": "#000"},
        ]
        words = build_words(chars)
        assert len(words) >= 2  # "Hi " and "Wo" at minimum


class TestStyleNormalizer:
    """Unit test style normalizer."""

    def test_deduplication(self):
        from fast_vision.styles.style_normalizer import normalize_styles

        blocks = [
            {"fontname": "Arial", "size": 12, "color": "#000000"},
            {"fontname": "Arial", "size": 12, "color": "#000000"},
            {"fontname": "Times-Bold", "size": 14, "color": "#333333"},
        ]
        updated_blocks, styles = normalize_styles(blocks)
        # Two unique styles (Arial 12 and Times-Bold 14)
        assert len(styles) == 2
        assert all("style_id" in b for b in updated_blocks)
