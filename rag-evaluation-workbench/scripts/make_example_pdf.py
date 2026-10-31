"""Render the example Markdown document to PDF (so the PDF extraction path has a bundled example).

    uv run python scripts/make_example_pdf.py [name]   # name defaults to honeybees

Reads examples/documents/<name>.md (a `# Title` line followed by blank-line separated paragraphs) and writes
examples/documents/<name>.pdf: A4, one text block per paragraph, so `documents.load_chunks` yields one chunk per
paragraph. The output is deterministic apart from PDF metadata timestamps.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
DOCUMENTS = ROOT / "examples" / "documents"
MARGIN, GAP, FONT_SIZE, TITLE_SIZE = 56, 12, 11, 18


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("name", nargs="?", default="honeybees", help="document name without extension")
    source = DOCUMENTS / f"{parser.parse_args().name}.md"
    target = source.with_suffix(".pdf")
    text = source.read_text(encoding="utf-8").strip()
    title, *paragraphs = [block.strip() for block in text.split("\n\n") if block.strip()]
    title = title.lstrip("# ").strip()
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)  # A4 in points
    y = MARGIN
    page.insert_text((MARGIN, y + TITLE_SIZE), title, fontsize=TITLE_SIZE, fontname="hebo")
    y += TITLE_SIZE + 2 * GAP
    for paragraph in paragraphs:
        while True:
            rect = pymupdf.Rect(MARGIN, y, page.rect.width - MARGIN, page.rect.height - MARGIN)
            spare = page.insert_textbox(rect, paragraph, fontsize=FONT_SIZE, fontname="helv", lineheight=1.35)
            if spare >= 0:
                y += rect.height - spare + GAP
                break
            page = doc.new_page(width=595, height=842)  # did not fit: nothing was written, retry on a new page
            y = MARGIN
    doc.set_metadata({"title": title, "creator": "RAG Evaluation Workbench example generator"})
    doc.save(target, garbage=4, deflate=True)
    print(f"wrote {target.relative_to(ROOT)} ({doc.page_count} pages, {len(paragraphs)} paragraphs)")


if __name__ == "__main__":
    main()
