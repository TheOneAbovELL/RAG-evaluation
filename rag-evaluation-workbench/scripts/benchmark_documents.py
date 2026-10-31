"""Scale benchmark for large source documents: loading, chunking, BM25 indexing and query latency.

    uv run python scripts/benchmark_documents.py                    # 100, 1000 and 5000 paragraphs, and a 200-page PDF
    uv run python scripts/benchmark_documents.py --sizes 500 2000   # custom text sizes

Documents are synthetic (random words from the bundled example text, so term statistics are realistic) and are written to a
temporary folder; nothing is uploaded. Reported per document: file size, chunks produced, time to load and chunk, time to build
the BM25 index, and the median and 95th-percentile latency of a top-3 query (50 queries, built from words in the document).
Python-level peak memory is measured in a separate pass with ``tracemalloc`` (it excludes memory allocated by C
extensions), so the tracer does not distort the timings.
"""

from __future__ import annotations

import argparse
import random
import statistics
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

import pymupdf

from rag_workbench.config import EXAMPLES_DIR
from rag_workbench.documents import load_chunks
from rag_workbench.retrieval import BM25Retriever

SEED = 12345


def vocabulary() -> list[str]:
    text = (EXAMPLES_DIR / "documents" / "honeybees.md").read_text(encoding="utf-8")
    return sorted({w.strip(".,;:!?()'\"").lower() for w in text.split() if w.strip(".,;:!?()'\"").isalpha()})


def write_text(path: Path, paragraphs: int, vocab: list[str], rng: random.Random) -> None:
    blocks = ["# Synthetic benchmark document"]
    for _ in range(paragraphs):
        sentences = [" ".join(rng.choices(vocab, k=rng.randint(8, 16))).capitalize() + "." for _ in range(rng.randint(2, 4))]
        blocks.append(" ".join(sentences))
    path.write_text("\n\n".join(blocks), encoding="utf-8")


def write_pdf(path: Path, pages: int, vocab: list[str], rng: random.Random) -> None:
    doc = pymupdf.open()
    for _ in range(pages):
        page = doc.new_page(width=595, height=842)
        y = 56
        for _ in range(8):
            text = " ".join(" ".join(rng.choices(vocab, k=rng.randint(8, 14))).capitalize() + "." for _ in range(3))
            page.insert_textbox(pymupdf.Rect(56, y, 539, y + 80), text, fontsize=10)
            y += 90
    doc.save(path)


def bench(path: Path, vocab: list[str], rng: random.Random) -> dict:
    # Timings first, with no tracer running (tracemalloc slows Python code several-fold); memory in a separate pass.
    started = time.perf_counter()
    chunks = load_chunks(path)
    load_s = time.perf_counter() - started
    started = time.perf_counter()
    retriever = BM25Retriever(chunks)
    index_s = time.perf_counter() - started
    queries = [" ".join(rng.choices(vocab, k=6)) + "?" for _ in range(50)]
    latencies = []
    for query in queries:
        started = time.perf_counter()
        hits = retriever.retrieve(query, 3)
        latencies.append((time.perf_counter() - started) * 1000)
        assert len(hits) == 3
    tracemalloc.start()
    BM25Retriever(load_chunks(path)).retrieve(queries[0], 3)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    latencies.sort()
    return {"file": path.name, "mb": path.stat().st_size / 1e6, "chunks": len(chunks), "load_s": load_s, "index_s": index_s,
            "p50_ms": statistics.median(latencies), "p95_ms": latencies[int(0.95 * len(latencies)) - 1],
            "peak_mb": peak / 1e6}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sizes", type=int, nargs="+", default=[100, 1000, 5000], help="paragraphs per text document")
    parser.add_argument("--pdf-pages", type=int, default=200, help="pages of the synthetic PDF (0 to skip)")
    args = parser.parse_args(argv)
    vocab, rng = vocabulary(), random.Random(SEED)
    rows = []
    with tempfile.TemporaryDirectory(prefix="ragwb-docbench-", ignore_cleanup_errors=True) as tmp:
        for size in args.sizes:
            path = Path(tmp) / f"doc-{size}.md"
            write_text(path, size, vocab, rng)
            rows.append(bench(path, vocab, rng))
        if args.pdf_pages:
            path = Path(tmp) / f"doc-{args.pdf_pages}p.pdf"
            write_pdf(path, args.pdf_pages, vocab, rng)
            rows.append(bench(path, vocab, rng))
    print(f"{'document':<18}{'MB':>7}{'chunks':>8}{'load s':>8}{'index s':>9}{'p50 ms':>8}{'p95 ms':>8}{'peak MB':>9}")
    for r in rows:
        print(f"{r['file']:<18}{r['mb']:>7.2f}{r['chunks']:>8}{r['load_s']:>8.2f}{r['index_s']:>9.3f}{r['p50_ms']:>8.2f}"
              f"{r['p95_ms']:>8.2f}{r['peak_mb']:>9.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
