"""Source-document loading and chunking.

PDFs are split into PyMuPDF text blocks (which yields one block per paragraph for typical single-column
PDFs). Plain-text and Markdown files
are split on blank lines. Overly long blocks are split further on sentence boundaries so that a
chunk never exceeds ``max_chars``.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

from .models import Chunk
from .text import normalize_whitespace, split_sentences

log = logging.getLogger(__name__)

SUPPORTED_SUFFIXES = {".pdf", ".txt", ".md"}
DEFAULT_MAX_CHUNK_CHARS = 2_000


class DocumentError(ValueError):
    """Raised when a document cannot be read or contains no extractable text."""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 16), b""):
            digest.update(block)
    return digest.hexdigest()


def load_chunks(path: str | Path, *, max_chars: int = DEFAULT_MAX_CHUNK_CHARS,
                max_bytes: int | None = None) -> list[Chunk]:
    """Read ``path`` and return its chunks in reading order, with stable ids ``p{page}-b{n}``."""
    path = Path(path)
    if not path.is_file():
        raise DocumentError(f"Document not found: {path}")
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise DocumentError(f"Unsupported document type {suffix!r}; use one of {sorted(SUPPORTED_SUFFIXES)}")
    size = path.stat().st_size
    if max_bytes is not None and size > max_bytes:
        raise DocumentError(f"Document is {size:,} bytes; the limit is {max_bytes:,} bytes")

    if suffix == ".pdf":
        raw_blocks = _pdf_blocks(path)
    else:
        raw_blocks = _text_blocks(path)

    chunks: list[Chunk] = []
    counters: dict[int, int] = {}
    for page, text in raw_blocks:
        for piece in _split_long(text, max_chars):
            counters[page] = counters.get(page, 0) + 1
            chunks.append(Chunk(id=f"p{page}-b{counters[page]}", text=piece, page=page, source=path.name))
    if not chunks:
        raise DocumentError(f"No extractable text found in {path.name}")
    log.info("Loaded %d chunks from %s", len(chunks), path.name)
    return chunks


HEADING_MAX_WORDS = 12
_SENTENCE_END = (".", "!", "?", ":", ";", '"', "\u201d", ")")


def is_heading(text: str) -> bool:
    """Heuristic: a short block that does not end like a sentence (``"Life Inside the Colony"``).

    Short list items or captions without punctuation also match, which is why heading removal is opt-in.
    """
    stripped = text.strip()
    return 0 < len(stripped.split()) <= HEADING_MAX_WORDS and not stripped.endswith(_SENTENCE_END)


def drop_headings(chunks: list[Chunk]) -> list[Chunk]:
    """Chunks without heading-like blocks (all chunks are kept if every one looks like a heading)."""
    kept = [c for c in chunks if not is_heading(c.text)]
    return kept or chunks


def _pdf_blocks(path: Path) -> list[tuple[int, str]]:
    import pymupdf  # imported lazily: heavy native module

    try:
        doc = pymupdf.open(path)
    except Exception as exc:  # pymupdf raises several internal error types
        raise DocumentError(f"Could not open PDF {path.name}: {exc}") from exc
    blocks: list[tuple[int, str]] = []
    with doc:
        pages = cast("Iterable[Any]", doc)  # pymupdf's stubs do not declare Document iterable
        for page_index, page in enumerate(pages, start=1):
            # Each block is (x0, y0, x1, y1, text, block_no, block_type); type 0 is text.
            page_blocks = [b for b in page.get_text("blocks") if b[6] == 0]
            page_blocks.sort(key=lambda b: (b[1], b[0]))  # top-to-bottom, then left-to-right
            for block in page_blocks:
                text = normalize_whitespace(block[4])
                if text:
                    blocks.append((page_index, text))
    return blocks


_ATX_MARKER = re.compile(r"^#{1,6}\s+")


def _text_blocks(path: Path) -> list[tuple[int, str]]:
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise DocumentError(f"{path.name} is not valid UTF-8 text") from exc
    paragraphs = [normalize_whitespace(p) for p in content.replace("\r\n", "\n").split("\n\n")]
    if path.suffix.lower() == ".md":  # '# Title' is markup, not text: keep the words, drop the marker
        paragraphs = [_ATX_MARKER.sub("", p, count=1) for p in paragraphs]
    return [(1, p) for p in paragraphs if p]


def _split_long(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    pieces: list[str] = []
    current = ""
    for original in split_sentences(text):
        sentence = original
        while len(sentence) > max_chars:  # a single enormous "sentence": hard split
            pieces.append(sentence[:max_chars])
            sentence = sentence[max_chars:]
        if current and len(current) + 1 + len(sentence) > max_chars:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces
