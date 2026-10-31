"""Build the project book: single-file Markdown manuscript, HTML and PDF.

    uv run --group docs python docs/project-book/tools/build_book.py [--no-pdf]

Inputs:  docs/project-book/chapters/*.md (in file-name order), with ``<!-- include: path -->`` directives
         resolved relative to the chapters folder (headings of included files are demoted by two levels).
Outputs: docs/project-book/PROJECT_BOOK.md         single-file Markdown edition
         docs/project-book/build/project-book.html  HTML edition (intermediate for the PDF)
         docs/project-book/RAG_Evaluation_Workbench_Project_Book.pdf
Then validates the PDF with PyMuPDF: page count, presence of every Part heading, and renders sample pages to
docs/project-book/build/pages/ for visual inspection.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import markdown

BOOK = Path(__file__).resolve().parents[1]
CHAPTERS = BOOK / "chapters"
BUILD = BOOK / "build"
MANUSCRIPT = BOOK / "PROJECT_BOOK.md"
PDF = BOOK / "RAG_Evaluation_Workbench_Project_Book.pdf"
INCLUDE = re.compile(r"^<!-- include: (?P<path>[^ ]+) -->\s*$", re.M)
BROWSERS = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", "google-chrome", "chromium", "msedge"]
PARTS = ["Part I ", "Part II ", "Part III ", "Part IV ", "Part V ", "Part VI ", "Part VII ", "Part VIII ", "Part IX ",
         "Part X ", "Part XI ", "Part XII ", "Part XIII ", "Part XIV ", "Part XV ", "Part XVI "]

CSS = """
@page { size: A4; margin: 18mm 16mm 20mm 16mm;
        @bottom-center { content: counter(page); font: 9pt 'Segoe UI', Arial, sans-serif; color: #666; } }
@page :first { @bottom-center { content: none; } }
html { font: 10.5pt/1.5 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; color: #1d1f23; }
body { max-width: 178mm; margin: 0 auto; }
h1 { font-size: 22pt; margin: 0 0 10pt; padding-bottom: 6pt; border-bottom: 2px solid #3b5bdb; break-before: page; }
h1:first-of-type { break-before: avoid; }
h2 { font-size: 15pt; margin: 18pt 0 6pt; color: #1c3d9b; break-after: avoid; }
h3 { font-size: 12pt; margin: 14pt 0 4pt; break-after: avoid; }
h4 { font-size: 10.5pt; margin: 10pt 0 3pt; break-after: avoid; }
p, li { orphans: 3; widows: 3; }
code { font: 8.8pt 'Cascadia Mono', Consolas, monospace; background: #f1f3f5; padding: 0 2px; border-radius: 2px; }
pre { background: #f6f8fa; border: 1px solid #e1e4e8; padding: 6pt 8pt; overflow-wrap: anywhere; white-space: pre-wrap;
      font-size: 8.3pt; line-height: 1.35; break-inside: avoid; }
pre code { background: none; padding: 0; font-size: inherit; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt; font-size: 8.6pt; break-inside: auto; }
th, td { border: 1px solid #d0d7de; padding: 3pt 5pt; vertical-align: top; text-align: left; overflow-wrap: anywhere; }
th { background: #eef2ff; }
tr { break-inside: avoid; }
img { max-width: 100%; max-height: 200mm; width: auto; object-fit: contain; display: block; margin: 8pt auto 2pt;
      border: 1px solid #e1e4e8; break-inside: avoid; }  /* tall screenshots shrink to fit beside their heading */
blockquote { margin: 6pt 0; padding: 4pt 10pt; border-left: 3px solid #fab005; background: #fff9db; }
.toc { font-size: 9.5pt; }
.toc ul { list-style: none; padding-left: 12pt; margin: 0; }
.toc > ul > li { margin-top: 4pt; font-weight: 600; }
.toc > ul > li li { font-weight: 400; }
.toc a { color: inherit; text-decoration: none; }
.cover { text-align: center; padding-top: 60mm; }
.cover h1 { border: none; font-size: 30pt; break-before: avoid; }
a { color: #1c3d9b; }
"""


def demote(text: str, levels: int = 2) -> str:
    out, in_code = [], False
    for line in text.splitlines():
        if line.startswith("```"):
            in_code = not in_code
        if not in_code and re.match(r"^#{1,6} ", line):
            out.append("#" * levels + line)
        else:
            out.append(line)
    return "\n".join(out)


def assemble() -> str:
    parts = []
    for chapter in sorted(CHAPTERS.glob("*.md")):
        text = chapter.read_text(encoding="utf-8")

        def include(match: re.Match, folder: Path = chapter.parent) -> str:
            target = (folder / match.group("path")).resolve()
            return demote(target.read_text(encoding="utf-8")).strip() + "\n"

        parts.append(INCLUDE.sub(include, text).strip() + "\n")
    return "\n\n".join(parts)


def to_manuscript(text: str) -> str:
    """Single-file edition lives in docs/project-book/, so asset links lose their leading '../'."""
    return text.replace("](../figures/", "](figures/").replace("](../screenshots/", "](screenshots/")


def to_html(text: str) -> str:
    md = markdown.Markdown(extensions=["tables", "fenced_code", "toc", "sane_lists", "attr_list"],
                           extension_configs={"toc": {"toc_depth": "1-2", "permalink": False}})
    body = md.convert(text)
    toc = md.toc
    title = "RAG Evaluation Workbench — The Project Book"
    cover = ("<section class='cover'><h1>RAG Evaluation Workbench</h1>"
             "<p style='font-size:15pt'>The Project Book</p>"
             "<p>Engineering, operation and methodology of a retrieval-augmented question-answering evaluation "
             "system</p><p>Version 1.4.1 · 2026-10-31</p></section>")
    toc_html = f"<h1 id='contents'>Contents</h1><div class='toc'>{toc}</div>"
    # Fixed-width SVG figures scale to the page width.
    body = re.sub(r"<img ([^>]*?)src=\"([^\"]+\.svg)\"", r'<img \1style="width:100%" src="\2"', body)
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>{title}</title>"
            f"<style>{CSS}</style></head><body>{cover}{toc_html}{body}</body></html>")


def find_browser() -> str:
    for candidate in BROWSERS:
        if Path(candidate).is_file() or shutil.which(candidate):
            return candidate
    raise SystemExit("Chrome or Edge is required to print the PDF (use --no-pdf to skip)")


def print_pdf(html: Path) -> None:
    profile = tempfile.mkdtemp(prefix="ragwb-book-")
    try:
        subprocess.run([find_browser(), "--headless=new", "--disable-gpu", "--no-first-run",
                        f"--user-data-dir={profile}", "--no-pdf-header-footer", "--generate-pdf-document-outline", "--allow-file-access-from-files",
                        "--virtual-time-budget=20000", f"--print-to-pdf={PDF}", html.as_uri()],
                       check=True, capture_output=True, timeout=300)
    finally:
        shutil.rmtree(profile, ignore_errors=True)


def validate_pdf(text: str) -> None:
    """Every Part must exist as a level-1 heading in the source, and each must start a PDF page (h1 breaks)."""
    import pymupdf

    headings = [line[2:].strip() for line in text.splitlines() if line.startswith("# Part ")]
    missing_source = [p.strip() for p in PARTS if not any(h.startswith(p) for h in headings)]
    with pymupdf.open(PDF) as doc:
        page_tops = []
        for page in doc:
            words = page.get_text().split()
            if words and words[0].isdigit():  # the footer page number is extracted first
                words = words[1:]
            page_tops.append(" ".join(words[:12]))
        not_page_top = [h for h in headings if not any(top.startswith(" ".join(h.split()[:4])) for top in page_tops)]
        print(f"PDF: {PDF.name}, {doc.page_count} pages, {PDF.stat().st_size / 1e6:.1f} MB, "
              f"{len(doc.get_toc())} bookmarks")
        print(f"Part headings found: {len(headings)}; missing from source: {missing_source or 'none'}; "
              f"not starting a page: {not_page_top or 'none'}")
        pages_dir = BUILD / "pages"
        shutil.rmtree(pages_dir, ignore_errors=True)
        pages_dir.mkdir(parents=True)
        for number in sorted({1, 2, 3, doc.page_count // 4, doc.page_count // 2, 3 * doc.page_count // 4,
                              doc.page_count}):
            doc[number - 1].get_pixmap(dpi=60).save(pages_dir / f"page-{number:03d}.png")
        print(f"sample pages rendered to {pages_dir.relative_to(BOOK.parent.parent)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-pdf", action="store_true")
    args = parser.parse_args()
    text = assemble()
    MANUSCRIPT.write_text(to_manuscript(text), encoding="utf-8")
    words = len(re.findall(r"\w+", text))
    print(f"manuscript: {MANUSCRIPT.name}, {len(text.splitlines())} lines, ~{words:,} words")
    BUILD.mkdir(exist_ok=True)
    html = BUILD / "project-book.html"
    html.write_text(to_html(text), encoding="utf-8")
    if not args.no_pdf:
        print_pdf(html)
        validate_pdf(text)


if __name__ == "__main__":
    main()
