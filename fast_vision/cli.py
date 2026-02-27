#!/usr/bin/env python3
"""
fast_vision CLI — Extract structured JSON from PDFs and DOCX files.

Usage:
    python cli.py input.pdf -o output.json
    python cli.py input.docx -o output.json
    python cli.py input.pdf --no-vision -o output.json
    python cli.py input.pdf --pages 1,3-5 -o output.json
"""

from __future__ import annotations

import argparse
import logging
import sys

from dotenv import load_dotenv


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="fast_vision — SOTA PDF/DOCX → Schema v3.0 JSON extractor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", help="Path to the input file (.pdf or .docx)")
    parser.add_argument("-o", "--output", default=None, help="Output JSON path (default: stdout)")
    parser.add_argument("--no-vision", action="store_true", help="Skip Vision API (geometry/style + heuristics only)")
    parser.add_argument("--pages", default=None, help="Page range, e.g. '1,3-5,10' (PDF only)")
    parser.add_argument("--indent", type=int, default=2, help="JSON indent level (default: 2)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    from fast_vision.pipeline import process_document

    def progress(pct: float, msg: str):
        bar_width = 30
        filled = int(bar_width * pct)
        bar = "█" * filled + "░" * (bar_width - filled)
        sys.stderr.write(f"\r  [{bar}] {pct*100:5.1f}%  {msg}")
        sys.stderr.flush()
        if pct >= 1.0:
            sys.stderr.write("\n")

    doc = process_document(
        filepath=args.input,
        use_vision=not args.no_vision,
        page_range=args.pages,
        progress_callback=progress,
    )

    # Serialize with aliases (from → from_id)
    json_str = doc.model_dump_json(
        indent=args.indent,
        by_alias=True,
        exclude_none=True,
    )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(json_str)
        logging.getLogger(__name__).info("Wrote %d bytes to %s", len(json_str), args.output)
    else:
        print(json_str)


if __name__ == "__main__":
    main()
