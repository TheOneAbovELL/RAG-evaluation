import pytest
from conftest import REAL_PDF

from rag_workbench.documents import DocumentError, file_sha256, load_chunks


def test_real_pdf_chunks():
    chunks = load_chunks(REAL_PDF)
    assert len(chunks) == 11  # title + one block per paragraph
    assert chunks[0].id == "p1-b1"
    assert chunks[0].text == "Honeybees: Life Inside the Colony"
    assert chunks[1].text.startswith("Honeybees are social insects")
    assert all("\n" not in c.text for c in chunks)
    assert len({c.id for c in chunks}) == len(chunks)


def test_text_document_split_on_blank_lines(tmp_path):
    path = tmp_path / "doc.md"
    path.write_text("First para\nwraps.\n\n\nSecond para.\r\n\r\nThird.", encoding="utf-8")
    chunks = load_chunks(path)
    assert [c.text for c in chunks] == ["First para wraps.", "Second para.", "Third."]
    assert [c.id for c in chunks] == ["p1-b1", "p1-b2", "p1-b3"]


def test_long_blocks_are_split_on_sentences(tmp_path):
    path = tmp_path / "doc.txt"
    path.write_text(" ".join(f"Sentence number {i} is here." for i in range(40)), encoding="utf-8")
    chunks = load_chunks(path, max_chars=200)
    assert len(chunks) > 1
    assert all(len(c.text) <= 200 for c in chunks)
    assert " ".join(c.text for c in chunks).count("Sentence number") == 40


def test_errors(tmp_path):
    with pytest.raises(DocumentError, match="not found"):
        load_chunks(tmp_path / "missing.pdf")
    (tmp_path / "x.docx").write_bytes(b"x")
    with pytest.raises(DocumentError, match="Unsupported"):
        load_chunks(tmp_path / "x.docx")
    (tmp_path / "empty.txt").write_text("  \n\n ", encoding="utf-8")
    with pytest.raises(DocumentError, match="No extractable text"):
        load_chunks(tmp_path / "empty.txt")
    (tmp_path / "big.txt").write_text("a" * 100, encoding="utf-8")
    with pytest.raises(DocumentError, match="limit"):
        load_chunks(tmp_path / "big.txt", max_bytes=10)
    (tmp_path / "bad.pdf").write_bytes(b"not a pdf")
    with pytest.raises(DocumentError, match="Could not open PDF"):
        load_chunks(tmp_path / "bad.pdf")
    (tmp_path / "latin1.txt").write_bytes("caf\xe9".encode("latin-1"))
    with pytest.raises(DocumentError, match="UTF-8"):
        load_chunks(tmp_path / "latin1.txt")


def test_sha256_is_stable(tmp_path):
    path = tmp_path / "a.txt"
    path.write_bytes(b"abc")
    assert file_sha256(path) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
