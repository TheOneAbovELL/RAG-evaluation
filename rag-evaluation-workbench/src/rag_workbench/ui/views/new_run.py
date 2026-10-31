"""Configure and launch an evaluation run, with validation before anything executes."""

import pandas as pd
import streamlit as st

from rag_workbench.config import ConfigError
from rag_workbench.datasets import SUPPORTED_SUFFIXES as DATASET_SUFFIXES
from rag_workbench.datasets import DatasetError, validate_file
from rag_workbench.documents import SUPPORTED_SUFFIXES as DOCUMENT_SUFFIXES
from rag_workbench.documents import DocumentError, load_chunks
from rag_workbench.metrics import DEFAULT_OFFLINE_METRICS, METRIC_SPECS
from rag_workbench.metrics.semantic import semantic_available
from rag_workbench.models import RunConfig
from rag_workbench.reporting import metric_label
from rag_workbench.runner import Progress
from rag_workbench.services import bundled_datasets, list_files, save_upload
from rag_workbench.storage import StorageError
from rag_workbench.ui.auth import can, current_user
from rag_workbench.ui.components import short_path, status_badge
from rag_workbench.ui.state import context_or_stop, select_run

ctx = context_or_stop()
s = ctx.settings
has_key = s.has_openai_key

st.title("New evaluation")
if not can(s, "run"):
    st.warning("Your account is read-only (viewer): it can browse results but not start evaluations.")
    st.stop()
st.caption("Choose the data, the pipeline and the metrics. Everything is validated before the run starts; "
           "results are saved case by case, so a stopped run keeps what it finished.")

# ------------------------------------------------------------------ data
st.header("1 · Data")
left, right = st.columns(2)
with left:
    upload = st.file_uploader("Upload a dataset (.jsonl or .csv)", type=[x.lstrip(".") for x in DATASET_SUFFIXES],
                              key="dataset_upload",
                              help="JSONL rows: {\"question\": ..., \"expected_answer\": ..., \"id\": ...}. "
                                   f"CSV needs a 'question' column. Size limit: {s.max_dataset_bytes / 1e6:g} MB.")
    if upload is not None and st.session_state.get("_dataset_upload_id") != upload.file_id:
        try:  # saved once per new upload, so a later manual selection is not overridden on rerun
            saved = save_upload(s, upload.name, upload.getvalue(), allowed_suffixes=DATASET_SUFFIXES,
                                max_bytes=s.max_dataset_bytes)
            st.session_state["dataset_choice"] = str(saved)
            st.session_state["_dataset_upload_id"] = upload.file_id
        except ValueError as exc:
            st.error(str(exc))
    datasets = list_files(s, DATASET_SUFFIXES, bundled_datasets(s))
    if not datasets:
        st.error("No dataset found. Upload one above.")
        st.stop()
    names = [str(p) for p in datasets]
    current = st.session_state.get("dataset_choice")
    dataset_path = st.selectbox("Dataset", names, index=names.index(current) if current in names else 0,
                                format_func=lambda p: short_path(p, s.project_root))
    report = validate_file(dataset_path, max_bytes=s.max_dataset_bytes, max_cases=s.max_cases,
                           max_field_chars=s.max_field_chars)
    if report.ok:
        st.success(f"{len(report.cases)} cases · {report.n_with_reference} with reference answers")
    else:
        st.error("This dataset cannot be used:\n\n" + "\n".join(f"- {e}" for e in report.errors[:10]))
    if report.warnings:
        with st.expander(f"{len(report.warnings)} warning(s)"):
            for w in report.warnings:
                st.markdown(f"- {w}")
    if report.cases:
        with st.expander("Preview"):
            st.dataframe(pd.DataFrame([c.model_dump() for c in report.cases[:20]]), hide_index=True)

with right:
    doc_upload = st.file_uploader("Upload a source document (.pdf, .txt, .md)",
                                  type=[x.lstrip(".") for x in DOCUMENT_SUFFIXES], key="document_upload")
    if doc_upload is not None and st.session_state.get("_document_upload_id") != doc_upload.file_id:
        try:
            saved = save_upload(s, doc_upload.name, doc_upload.getvalue(), allowed_suffixes=DOCUMENT_SUFFIXES,
                                max_bytes=s.max_document_bytes)
            st.session_state["document_choice"] = str(saved)
            st.session_state["_document_upload_id"] = doc_upload.file_id
        except ValueError as exc:
            st.error(str(exc))
    documents = list_files(s, DOCUMENT_SUFFIXES, [s.default_document])
    doc_names = [str(p) for p in documents]
    current_doc = st.session_state.get("document_choice")
    document_path = st.selectbox("Document", doc_names,
                                 index=doc_names.index(current_doc) if current_doc in doc_names else 0,
                                 format_func=lambda p: short_path(p, s.project_root))
    try:
        chunks = load_chunks(document_path, max_bytes=s.max_document_bytes)
        st.success(f"{len(chunks)} chunks extracted")
    except DocumentError as exc:
        chunks = []
        st.error(str(exc))

# -------------------------------------------------------------- pipeline
st.header("2 · Pipeline")
c1, c2, c3, c4 = st.columns(4)
provider = c1.radio("Provider", ["offline", "openai"], horizontal=True, key="provider",
                    format_func={"offline": "Offline", "openai": "OpenAI"}.get,
                    help="Offline: extractive baseline that copies the best-matching sentences (not an LLM).")
if provider == "openai" and not has_key:
    c1.warning("OPENAI_API_KEY is not set. Add it to `.env` and restart to use OpenAI.")
pipeline_options = ["rag", "agent"] if provider == "openai" else ["rag"]
pipeline = c2.radio("Pipeline", pipeline_options, horizontal=True, key="pipeline_mode",
                    format_func={"rag": "Retrieve → generate", "agent": "Tool-calling agent"}.get,
                    help="The agent decides when and how to search (tool-calling agent design). Retrieve → generate "
                         "always answers from exactly the top-k chunks.")
retriever_options = ["bm25"] + (["embedding", "hybrid"] if has_key else []) + (
    ["local", "hybrid-local"] if semantic_available() else [])
retriever = c3.radio("Retriever", retriever_options, horizontal=True, key="retriever",
                     format_func={"bm25": "BM25 (offline)", "embedding": "API embeddings",
                                  "hybrid": "Hybrid (BM25 + API embeddings)", "local": "Local embeddings",
                                  "hybrid-local": "Hybrid (BM25 + local embeddings)"}.get,
                     help="Hybrid fuses the BM25 and dense rankings by reciprocal rank. Local embeddings run on this "
                          "machine with no API key (optional fastembed package).")
max_k = max(1, min(10, len(chunks) or 10))
k = c4.slider("Chunks per query (k)", 1, max_k, min(3, max_k), key="k")

o1, o2 = st.columns(2)
generator_model: str | None
if provider == "openai":
    generator_model = o1.text_input("Generator model", s.generator_model, key="generator_model")
    answer_sentences = 2
else:
    generator_model = None
    answer_sentences = o1.number_input("Sentences per extractive answer", 1, 10, 2, key="answer_sentences")

# --------------------------------------------------------------- metrics
st.header("3 · Metrics")
available = [m for m, spec in METRIC_SPECS.items()
             if (has_key or not spec.requires_openai) and (semantic_available() or not spec.requires_local_model)]
metrics = st.multiselect("Metrics", available, default=[m for m in DEFAULT_OFFLINE_METRICS if m in available],
                         format_func=metric_label, key="metrics",
                         help="Lexical metrics are offline word-overlap measures. Judge metrics ask an OpenAI "
                              "model (via DeepEval) and cost API calls.")
if not semantic_available():
    st.caption("Semantic metrics (local embedding model) are optional: `uv sync --extra semantic` enables them.")
if not has_key:
    st.caption("Judge metrics (answer relevancy, faithfulness, context relevancy, correctness) need OPENAI_API_KEY.")
judge_model = None
if any(METRIC_SPECS[m].requires_openai for m in metrics):
    judge_model = st.text_input("Judge model", s.judge_model, key="judge_model")
thresholds = {}
with st.expander("Pass thresholds"):
    tcols = st.columns(3)
    for i, m in enumerate(metrics):
        thresholds[m] = tcols[i % 3].number_input(metric_label(m), 0.0, 1.0, METRIC_SPECS[m].default_threshold,
                                                  0.05, key=f"threshold_{m}")

with st.expander("Advanced"):
    a1, a2, a3 = st.columns(3)
    workers = a1.number_input("Parallel cases", 1, 32, 1 if provider == "offline" else s.max_workers, key="workers")
    n_cases = len(report.cases) if report.ok else 1
    limit = a2.number_input("Evaluate first N cases (0 = all)", 0, max(n_cases, 1), 0, key="limit")
    seed = a3.number_input("Seed", 0, 10_000, 0, key="seed")
    failure_rate = 0.0
    if provider == "offline":
        failure_rate = st.slider("Inject failures (fraction of cases)", 0.0, 1.0, 0.0, 0.05, key="failure_rate",
                                 help="Testing aid: makes the offline generator fail deterministically on some "
                                      "cases so you can see how failures are recorded.")
    skip_headings = st.checkbox("Skip heading-like blocks (e.g. the document title)", key="skip_headings",
                                help="Removes short blocks that do not end like a sentence from the chunks, so a "
                                     "title cannot be retrieved as if it were evidence.")
    min_evidence = 0.0
    if provider == "offline":
        min_evidence = st.slider("Abstain below this evidence share (offline baseline)", 0.0, 1.0, 0.0, 0.05,
                                 key="min_evidence",
                                 help="0 = always answer. Otherwise the baseline returns the abstention sentence "
                                      "unless its sentences cover this share of the question's content terms.")
    notes = st.text_area("Notes", key="notes", placeholder="What are you testing with this run?")

# ------------------------------------------------------------------- run
st.header("4 · Run")
default_name = f"{provider}-{pipeline}-{retriever}-k{k}"
name = st.text_input("Run name", default_name, max_chars=120, key="run_name")

problems = []
if not report.ok:
    problems.append("the dataset has validation errors")
if not chunks:
    problems.append("the document has no usable text")
if not metrics:
    problems.append("no metric is selected")
if provider == "openai" and not has_key:
    problems.append("OpenAI is selected but OPENAI_API_KEY is not set")
if not name.strip():
    problems.append("the run needs a name")
if problems:
    st.warning("Cannot start yet: " + "; ".join(problems) + ".")

if provider == "openai" or judge_model:
    st.info("This run calls the OpenAI API and may incur cost. "
            f"About {len(report.cases[:limit or None]) if report.ok else 0} generation call(s)"
            f"{' plus judge calls for each selected judge metric' if judge_model else ''}.")

if st.button("Run evaluation", type="primary", disabled=bool(problems), key="start_run"):
    try:
        # Widget values are plain strings; model_validate checks them against the Literal-typed fields.
        config = RunConfig.model_validate({
            "name": name.strip(), "dataset_path": dataset_path, "document_path": document_path,
            "provider": provider, "pipeline": pipeline, "retriever": retriever, "k": int(k), "metrics": metrics,
            "thresholds": thresholds, "generator_model": generator_model, "judge_model": judge_model,
            "embedding_model": (s.local_embedding_model if retriever in ("local", "hybrid-local")
                                else s.embedding_model if retriever != "bm25" else None),
            "max_workers": int(workers), "max_retries": s.max_retries, "request_timeout_s": s.request_timeout_s,
            "case_timeout_s": s.case_timeout_s,
            "max_answer_sentences": int(answer_sentences), "limit": int(limit) or None, "notes": notes or None,
            "offline_failure_rate": float(failure_rate), "seed": int(seed), "min_evidence": float(min_evidence),
            "skip_headings": bool(skip_headings), "started_by": current_user()})
        runner = ctx.runner()
        prepared = runner.prepare(config)
    except (ConfigError, DatasetError, DocumentError, ValueError) as exc:
        st.error(f"Configuration rejected: {exc}")
        st.stop()

    bar = st.progress(0.0, text="Starting…")
    log_box = st.empty()
    recent: list[str] = []

    def on_progress(p: Progress) -> None:
        bar.progress(p.done / p.total, text=f"{p.done}/{p.total} cases")
        mark = "✓" if p.status == "ok" else "✗"
        recent.append(f"{mark} {p.case_id}" + ("" if p.status == "ok" else f" — {p.message}"))
        log_box.code("\n".join(recent[-8:]), language=None)

    try:
        with st.spinner("Evaluating… (use Streamlit's Stop button to cancel; finished cases are kept)"):
            run = runner.execute(prepared, progress=on_progress)
    except StorageError as exc:
        st.error(f"Could not save results: {exc}")
        st.stop()
    select_run(run.id)
    st.session_state["last_finished_run"] = run.id
    bar.progress(1.0, text="Done")
    summary = run.summary
    if summary is None:  # execute() always stores one; guard keeps the page safe if that ever changes
        st.error("The run finished without a summary.")
        st.stop()
    message = (f"Run **{run.name}** finished: {status_badge(run.status)} · "
               f"{summary.n_ok}/{summary.n_cases} cases succeeded")
    (st.success if run.status == "completed" else st.warning)(message)
    if summary.n_error:
        st.caption("Failed cases are recorded with their error message; open the results to see them.")
    cols = st.columns(min(4, len(summary.metrics)) or 1)
    for i, (m, ms) in enumerate(summary.metrics.items()):
        cols[i % len(cols)].metric(metric_label(m), "—" if ms.mean is None else f"{ms.mean:.3f}",
                                   help=f"{ms.n_scored} scored, {ms.n_skipped} skipped, {ms.n_error} errors")
    st.page_link("src/rag_workbench/ui/views/results.py", label="Inspect this run", icon=":material/table_view:")
