"""Generate the project book's SVG figures into docs/project-book/figures/.

    uv run python docs/project-book/tools/diagrams.py

Box-and-arrow figures are declared below by hand (they describe the design); the module dependency
figure is derived from the package's actual ``import`` statements with :mod:`ast`, so it cannot drift
from the code.
"""

from __future__ import annotations

import ast
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "project-book" / "figures"
PKG = ROOT / "src" / "rag_workbench"

FONT = "font-family='Segoe UI, Helvetica, Arial, sans-serif'"
COLORS = {"ui": "#dbe4ff", "core": "#e6fcf5", "data": "#fff4e6", "ext": "#f1f3f5", "store": "#f3f0ff"}
STROKE = "#495057"


class Svg:
    def __init__(self, width: int, height: int, title: str):
        self.w, self.h = width, height
        self.parts = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' "
                      f"viewBox='0 0 {width} {height}' {FONT} font-size='13'>",
                      f"<title>{escape(title)}</title>",
                      "<defs><marker id='arrow' viewBox='0 0 10 10' refX='9' refY='5' markerWidth='7' "
                      f"markerHeight='7' orient='auto-start-reverse'><path d='M0,0 L10,5 L0,10 z' fill='{STROKE}'/>"
                      "</marker></defs>",
                      f"<rect width='{width}' height='{height}' fill='white'/>"]

    def box(self, x, y, w, h, label, kind="core", sub=None, bold=True):
        self.parts.append(f"<rect x='{x}' y='{y}' width='{w}' height='{h}' rx='8' fill='{COLORS[kind]}' "
                          f"stroke='{STROKE}' stroke-width='1.2'/>")
        lines = label.split("\n")
        total = len(lines) + (len(sub.split("\n")) if sub else 0)
        cy = y + h / 2 - (total - 1) * 8
        for line in lines:
            weight = "600" if bold else "400"
            self.parts.append(f"<text x='{x + w / 2}' y='{cy + 4}' text-anchor='middle' font-weight='{weight}'>"
                              f"{escape(line)}</text>")
            cy += 16
        for line in (sub.split("\n") if sub else []):
            self.parts.append(f"<text x='{x + w / 2}' y='{cy + 4}' text-anchor='middle' font-size='11' "
                              f"fill='#495057'>{escape(line)}</text>")
            cy += 16
        return (x, y, w, h)

    def arrow(self, x1, y1, x2, y2, label=None, dashed=False, both=False):
        dash = " stroke-dasharray='5,4'" if dashed else ""
        start = " marker-start='url(#arrow)'" if both else ""
        self.parts.append(f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}' stroke='{STROKE}' stroke-width='1.3'"
                          f"{dash} marker-end='url(#arrow)'{start}/>")
        if label:
            if abs(y2 - y1) < 1:  # horizontal: label above the line, just after the source end
                lx, ly = min(x1, x2) + 6, y1 - 6
            else:  # vertical or diagonal: label right of the midpoint
                lx, ly = (x1 + x2) / 2 + 6, (y1 + y2) / 2
            self.parts.append(f"<text x='{lx}' y='{ly}' font-size='11' fill='#343a40'>{escape(label)}</text>")

    def text(self, x, y, s, size=13, anchor="start", weight="400", fill="#212529"):
        self.parts.append(f"<text x='{x}' y='{y}' font-size='{size}' text-anchor='{anchor}' font-weight='{weight}' "
                          f"fill='{fill}'>{escape(s)}</text>")

    def save(self, name: str) -> Path:
        OUT.mkdir(parents=True, exist_ok=True)
        path = OUT / name
        path.write_text("\n".join([*self.parts, "</svg>"]), encoding="utf-8")
        return path


def edge_between(a, b):
    """Arrow from the boundary of box a to the boundary of box b (centre-to-centre line, clipped)."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    acx, acy, bcx, bcy = ax + aw / 2, ay + ah / 2, bx + bw / 2, by + bh / 2

    def clip(cx, cy, w, h, dx, dy):
        tx = (w / 2) / abs(dx) if dx else float("inf")
        ty = (h / 2) / abs(dy) if dy else float("inf")
        t = min(tx, ty)
        return cx + dx * t, cy + dy * t

    dx, dy = bcx - acx, bcy - acy
    x1, y1 = clip(acx, acy, aw, ah, dx, dy)
    x2, y2 = clip(bcx, bcy, bw, bh, -dx, -dy)
    return x1, y1, x2, y2


def architecture():
    s = Svg(1000, 560, "Layered architecture")
    s.text(20, 28, "Figure: layers and their responsibilities (arrows: 'uses')", 15, weight="600")
    s.box(40, 50, 440, 62, "Streamlit UI", "ui", "streamlit_app.py · ui/views/*.py · ui/components.py · ui/state.py")
    s.box(520, 50, 440, 62, "Command line", "ui", "cli.py (ragwb) · __main__.py")
    s.box(40, 140, 920, 50, "Application wiring", "core", "services.py: settings + store + runner, safe uploads")
    s.box(40, 218, 730, 58, "Orchestration", "core", "runner.py: prepare → execute · retries · cancellation · thread pool · cost")
    cols = [("Inputs", "data", "datasets.py\ndocuments.py · text.py"),
            ("Answering", "core", "pipeline.py · retrieval.py\nproviders.py · prompts.py"),
            ("Scoring", "core", "metrics/lexical.py\nmetrics/judge.py · aggregate.py"),
            ("Persistence", "store", "storage.py\nSQLite runs + cases"),
            ("Outputs", "data", "reporting.py (CSV/JSON/MD)\narchive.py (bundles)")]
    w, gap = 168, 20
    for i, (label, kind, sub) in enumerate(cols):
        x = 40 + i * (w + gap)
        s.box(x, 310, w, 78, label, kind, sub)
        if label != "Outputs":
            s.arrow(x + w / 2, 276, x + w / 2, 310)
    s.arrow(260, 112, 260, 140)
    s.arrow(740, 112, 740, 140)
    s.arrow(405, 190, 405, 218)
    s.arrow(866, 190, 866, 310)  # wiring/UI/CLI read and write exports and bundles directly
    s.box(40, 418, 920, 50, "Foundation (used by every layer)", "core",
          "config.py (Settings, .env) · models.py (pydantic contracts) · errors.py · logging_setup.py")
    s.box(40, 495, 450, 40, "OpenAI API (optional): chat, embeddings, judge", "ext", bold=False)
    s.box(510, 495, 450, 40, "Local files: examples/, data/runs.db, data/uploads, data/logs", "ext", bold=False)
    return s.save("architecture.svg")


def data_flow():
    s = Svg(980, 360, "Data flow of one evaluation run")
    s.text(20, 28, "Figure: data flow of one run", 15, weight="600")
    ds = s.box(20, 60, 170, 60, "Dataset", "data", ".jsonl / .csv")
    doc = s.box(20, 200, 170, 60, "Document", "data", ".pdf / .txt / .md")
    cases = s.box(240, 60, 160, 60, "EvalCase[]", "core", "validated, hashed")
    chunks = s.box(240, 200, 160, 60, "Chunk[]", "core", "p{page}-b{n}")
    ret = s.box(450, 200, 160, 60, "Retriever", "core", "BM25 / embeddings")
    gen = s.box(450, 60, 160, 60, "Generator", "core", "extractive / GPT / agent")
    g = s.box(660, 60, 150, 60, "Generation", "core", "answer + contexts")
    m = s.box(660, 200, 150, 60, "MetricResult[]", "core", "ok / skipped / error")
    st = s.box(850, 60, 110, 60, "SQLite", "store", "case rows")
    agg = s.box(850, 200, 110, 60, "RunSummary", "store", "means, CIs")
    out = s.box(660, 290, 300, 50, "UI tables & charts · CSV · Markdown · JSON bundle", "ext", bold=False)
    for a, b, lab in ((ds, cases, "parse"), (doc, chunks, "extract"), (chunks, ret, "index"), (cases, gen, "question"),
                      (ret, gen, "top-k chunks"), (gen, g, ""), (g, m, "score"), (g, st, "commit"),
                      (m, agg, "aggregate"), (agg, out, ""), (st, agg, "")):
        s.arrow(*edge_between(a, b), label=lab or None)
    return s.save("data-flow.svg")


def lifecycle():
    s = Svg(900, 330, "Run status lifecycle")
    s.text(20, 28, "Figure: run status lifecycle (storage.runs.status)", 15, weight="600")
    prep = s.box(30, 130, 150, 55, "prepare()", "ext", "validation only\nno row written")
    running = s.box(240, 130, 140, 55, "running", "core")
    completed = s.box(470, 40, 140, 45, "completed", "core", "no case errors", bold=True)
    partial = s.box(470, 100, 140, 45, "partial", "core", "some case errors")
    failed = s.box(470, 160, 140, 45, "failed", "core", "every case errored")
    cancelled = s.box(470, 220, 140, 45, "cancelled", "core", "cancel / Stop / Ctrl-C")
    s.box(700, 200, 170, 55, "interrupted", "core", "process died; set on\nnext start-up")
    s.box(700, 40, 170, 50, "imported", "store", "loaded from a bundle\n(no run executed)")
    s.arrow(*edge_between(prep, running), label="create row")
    for target in (completed, partial, failed, cancelled):
        s.arrow(*edge_between(running, target))
    s.parts.append(f"<path d='M310,185 V292 H785 V255' fill='none' stroke='{STROKE}' stroke-width='1.3' "
                   "stroke-dasharray='5,4' marker-end='url(#arrow)'/>")
    s.text(470, 286, "still 'running' at start-up → recover_interrupted()", 11)
    s.text(30, 318, "Errors in prepare() (bad dataset, document, metric or key) raise before any row exists.", 12,
           fill="#495057")
    return s.save("run-lifecycle.svg")


def sequence(name, title, actors, messages, height=None):
    width = 140 + 150 * len(actors)
    height = height or 110 + 34 * len(messages)
    s = Svg(width, height, title)
    s.text(20, 28, f"Figure: {title}", 15, weight="600")
    xs = {}
    for i, actor in enumerate(actors):
        x = 90 + i * 150
        xs[actor] = x
        s.box(x - 62, 45, 124, 36, actor, "ui" if i == 0 else "core")
        s.parts.append(f"<line x1='{x}' y1='81' x2='{x}' y2='{height - 15}' stroke='#adb5bd' stroke-dasharray='4,4'/>")
    y = 110
    for frm, to, label, *kind in messages:
        dashed = bool(kind and kind[0] == "reply")
        if frm == to:
            x = xs[frm]
            s.parts.append(f"<path d='M{x},{y} h40 v14 h-36' fill='none' stroke='{STROKE}' marker-end='url(#arrow)'/>")
            s.text(x + 46, y + 10, label, 11)
        else:
            s.arrow(xs[frm], y, xs[to], y, dashed=dashed)
            mid = (xs[frm] + xs[to]) / 2
            s.text(mid, y - 5, label, 11, anchor="middle")
        y += 34
    return s.save(name)


def module_graph():
    """Internal import graph of rag_workbench (excluding the ui package), laid out by dependency depth."""
    modules = {}
    for path in sorted(PKG.rglob("*.py")):
        rel = path.relative_to(PKG).with_suffix("")
        parts = list(rel.parts)
        if parts[0] == "ui" or parts[-1] == "__main__":
            continue
        if parts[-1] == "__init__":
            parts = parts[:-1]
        name = ".".join(parts) or "__init__"
        if name == "__init__":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        package = parts[:-1] if path.name != "__init__.py" else parts
        deps = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level:
                base = package[: len(package) - (node.level - 1)] if node.level > 1 else package
                target = ".".join(base + ([node.module] if node.module else []))
                if not node.module:
                    target = ".".join([*base, node.names[0].name])
                deps.add(target)
            elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("rag_workbench."):
                deps.add(node.module.removeprefix("rag_workbench."))
        modules[name] = deps
    known = set(modules)
    graph = {m: {d for d in deps if d in known and d != m} for m, deps in modules.items()}
    depth = {}

    def level(m, seen=()):
        if m in depth:
            return depth[m]
        if m in seen:
            return 0
        depth[m] = 1 + max((level(d, (*seen, m)) for d in graph[m]), default=-1)
        return depth[m]

    for m in graph:
        level(m)
    layers = {}
    for m, d in depth.items():
        layers.setdefault(d, []).append(m)
    max_width = max(len(v) for v in layers.values())
    bw, bh, gx, gy = 128, 34, 20, 70
    width = 40 + max_width * (bw + gx)
    height = 70 + len(layers) * (bh + gy)
    s = Svg(width, height, "Module import graph")
    s.text(20, 28, "Figure: internal imports of rag_workbench (generated from source; ui/ omitted)", 15,
           weight="600")
    pos = {}
    for d in sorted(layers):
        row = sorted(layers[d])
        offset = (width - len(row) * (bw + gx)) / 2
        for i, m in enumerate(row):
            y = height - 40 - (d + 1) * (bh + gy) + gy
            pos[m] = s.box(offset + i * (bw + gx), y, bw, bh, m, "data" if d == 0 else "core", bold=False)
    for m, deps in graph.items():
        for d in deps:
            x1, y1, x2, y2 = edge_between(pos[m], pos[d])
            s.parts.append(f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}' stroke='#868e96' stroke-width='0.8' "
                           "marker-end='url(#arrow)' opacity='0.75'/>")
    s.save("module-graph.svg")
    return graph


def main():
    paths = [architecture(), data_flow(), lifecycle()]
    paths.append(sequence(
        "sequence-run.svg", "sequence of an offline run started from the UI",
        ["New evaluation page", "EvaluationRunner", "RAGPipeline", "BM25Retriever", "Metric", "RunStore"],
        [("New evaluation page", "EvaluationRunner", "prepare(config)"),
         ("EvaluationRunner", "EvaluationRunner", "load dataset, chunks; build pipeline, metrics"),
         ("New evaluation page", "EvaluationRunner", "execute(prepared, progress)"),
         ("EvaluationRunner", "RunStore", "create_run(status=running)"),
         ("EvaluationRunner", "RAGPipeline", "answer(question)   [per case]"),
         ("RAGPipeline", "BM25Retriever", "retrieve(question, k)"),
         ("BM25Retriever", "RAGPipeline", "RetrievedChunk[k]", "reply"),
         ("RAGPipeline", "RAGPipeline", "generator.generate(question, passages)"),
         ("RAGPipeline", "EvaluationRunner", "Generation", "reply"),
         ("EvaluationRunner", "Metric", "evaluate(MetricInput, threshold)"),
         ("Metric", "EvaluationRunner", "MetricResult", "reply"),
         ("EvaluationRunner", "RunStore", "add_case_result(case)"),
         ("EvaluationRunner", "New evaluation page", "progress(done, total)", "reply"),
         ("EvaluationRunner", "RunStore", "finish_run(status, summary)"),
         ("EvaluationRunner", "New evaluation page", "RunRecord", "reply")]))
    paths.append(sequence(
        "sequence-agent.svg", "agent pipeline: real context capture",
        ["AgentRAGPipeline", "LangChain agent", "collecting_info tool", "Retriever"],
        [("AgentRAGPipeline", "LangChain agent", "invoke(question)"),
         ("LangChain agent", "collecting_info tool", "tool call (model-chosen query)"),
         ("collecting_info tool", "Retriever", "retrieve(query, k)"),
         ("Retriever", "collecting_info tool", "chunks", "reply"),
         ("collecting_info tool", "collecting_info tool", "append to per-call `captured` list"),
         ("collecting_info tool", "LangChain agent", "chunk text", "reply"),
         ("LangChain agent", "AgentRAGPipeline", "structured Answer(answer, context)", "reply"),
         ("AgentRAGPipeline", "AgentRAGPipeline", "contexts = captured; context claim kept only for audit")]))
    graph = module_graph()
    for p in [*paths, OUT / "module-graph.svg"]:
        print(p.relative_to(ROOT))
    print("edges:", sum(len(v) for v in graph.values()))


if __name__ == "__main__":
    main()
