"""Browse datasets and documents, and try retrieval interactively (offline BM25)."""

import pandas as pd
import streamlit as st

from rag_workbench.datasets import SUPPORTED_SUFFIXES as DATASET_SUFFIXES
from rag_workbench.datasets import validate_file
from rag_workbench.documents import SUPPORTED_SUFFIXES as DOCUMENT_SUFFIXES
from rag_workbench.documents import DocumentError, load_chunks
from rag_workbench.retrieval import BM25Retriever
from rag_workbench.services import bundled_datasets, list_files
from rag_workbench.ui.components import short_path
from rag_workbench.ui.state import context_or_stop

ctx = context_or_stop()
s = ctx.settings
st.title("Datasets & retrieval")

tab_ds, tab_doc, tab_play = st.tabs(["Datasets", "Document chunks", "Retrieval playground"])


def short(path) -> str:
    return short_path(path, s.project_root)


with tab_ds:
    datasets = list_files(s, DATASET_SUFFIXES, bundled_datasets(s))
    if not datasets:
        st.info("No datasets found.")
    else:
        path = st.selectbox("Dataset", datasets, format_func=short, key="data_dataset")
        report = validate_file(path, max_bytes=s.max_dataset_bytes, max_cases=s.max_cases,
                               max_field_chars=s.max_field_chars)
        c = st.columns(4)
        c[0].metric("Cases", len(report.cases))
        c[1].metric("With reference", report.n_with_reference)
        c[2].metric("Errors", len(report.errors))
        c[3].metric("Warnings", len(report.warnings))
        for e in report.errors:
            st.error(str(e))
        for w in report.warnings:
            st.warning(str(w))
        if report.cases:
            df = pd.DataFrame([{"id": x.id, "question": x.question, "expected_answer": x.expected_answer,
                                "question words": len(x.question.split()),
                                "reference words": len((x.expected_answer or "").split())} for x in report.cases])
            st.dataframe(df, hide_index=True)
        st.caption(f"sha256 `{report.sha256}`")
        with st.expander("Dataset format"):
            st.markdown("**JSONL** — one object per line:\n\n"
                        "```json\n{\"id\": \"q1\", \"question\": \"What do drones do?\", "
                        "\"expected_answer\": \"They mate with queens from other colonies.\", "
                        "\"metadata\": {\"topic\": \"drones\"}}\n```\n"
                        "`question` is required; `expected_answer` is needed for reference-based metrics; `id` "
                        "defaults to `case-NNN`.\n\n**CSV** — header with a `question` column, optional "
                        "`expected_answer` and `id`; other columns become metadata.")

with tab_doc:
    documents = list_files(s, DOCUMENT_SUFFIXES, [s.default_document])
    doc = st.selectbox("Document", documents, format_func=short, key="data_document")
    try:
        chunks = load_chunks(doc, max_bytes=s.max_document_bytes)
        st.caption(f"{len(chunks)} chunks · {sum(len(c.text) for c in chunks):,} characters")
        st.dataframe(pd.DataFrame([{"id": c.id, "page": c.page, "chars": len(c.text), "text": c.text}
                                   for c in chunks]), hide_index=True,
                     column_config={"text": st.column_config.TextColumn(width="large")})
    except DocumentError as exc:
        chunks = []
        st.error(str(exc))

with tab_play:
    st.caption("Type a question to see which chunks BM25 would retrieve and their scores. This is the offline "
               "retriever; embedding retrieval needs an API key and is not shown here to avoid cost.")
    if not chunks:
        st.info("Select a document with extractable text first.")
    else:
        query = st.text_input("Query", "How is nectar turned into honey?", key="play_query")
        k = st.slider("k", 1, min(10, len(chunks)), min(3, len(chunks)), key="play_k")
        if query.strip():
            retriever = BM25Retriever(chunks)
            hits = retriever.retrieve(query, k)
            if all(h.score == 0 for h in hits):
                st.warning("No chunk shares a content word with the query; results are in document order.")
            for h in hits:
                with st.container(border=True):
                    st.caption(f"rank {h.rank} · {h.chunk_id} · page {h.page} · BM25 {h.score:.3f}")
                    st.text(h.text)
