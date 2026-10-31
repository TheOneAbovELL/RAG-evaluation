"""Generate the book's reference appendices from the code itself.

    uv run python docs/project-book/tools/generate_reference.py

Writes Markdown into docs/project-book/generated/:

* source-inventory.md   every module, class, function and method with line numbers and docstring summary
* directory-tree.md     the project tree (excluding generated/runtime folders)
* env-vars.md           environment variables, from rag_workbench.config.ENV_VARS and Settings defaults
* metric-catalogue.md   metrics, from rag_workbench.metrics.METRIC_SPECS
* test-catalogue.md     every test function with its docstring or first assertion line
* cli-reference.md      `ragwb --help` and each subcommand's help, captured from argparse
"""

from __future__ import annotations

import ast
import contextlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "project-book" / "generated"
EXCLUDE = {".venv", "__pycache__", ".pytest_cache", "data", "build", ".git", "generated", "screenshots"}


def summary(node) -> str:
    doc = ast.get_docstring(node) or ""
    return doc.strip().split("\n\n")[0].replace("\n", " ") if doc else ""


def signature(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = [a.arg for a in fn.args.posonlyargs + fn.args.args]
    if fn.args.vararg:
        args.append("*" + fn.args.vararg.arg)
    elif fn.args.kwonlyargs:
        args.append("*")
    args += [a.arg for a in fn.args.kwonlyargs]
    if fn.args.kwarg:
        args.append("**" + fn.args.kwarg.arg)
    return f"{fn.name}({', '.join(args)})"


def source_inventory() -> str:
    lines = ["# Source inventory", "",
             "Generated from the source with `ast` by `docs/project-book/tools/generate_reference.py`. Line numbers "
             "refer to the files as they were when the book was built.", ""]
    files = [*sorted((ROOT / "src").rglob("*.py")), ROOT / "start.py", ROOT / "streamlit_app.py", *sorted((ROOT / "scripts").glob("*.py"))]
    total_funcs = 0
    lines += ["| File | Lines | Classes | Functions/methods |", "|---|---:|---:|---:|"]
    rows, details = [], []
    for path in files:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        rel = path.relative_to(ROOT).as_posix()
        classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
        funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        total_funcs += len(funcs)
        rows.append(f"| `{rel}` | {len(text.splitlines())} | {len(classes)} | {len(funcs)} |")
        details += [f"## `{rel}`", ""]
        if summary(tree):
            details += [summary(tree), ""]
        entries = []
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                entries.append(f"* **class `{node.name}`** (line {node.lineno}) — {summary(node) or '—'}")
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        entries.append(f"    * `{signature(item)}` (line {item.lineno}) — {summary(item) or '—'}")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                entries.append(f"* `{signature(node)}` (line {node.lineno}) — {summary(node) or '—'}")
        details += (entries or ["*(no top-level definitions; page script or package marker)*"]) + [""]
    lines += [*rows, "", f"Total: {len(files)} files, {total_funcs} functions and methods.", "", *details]
    return "\n".join(lines)


def directory_tree() -> str:
    out = ["# Directory tree", "", "Runtime folders (`.venv/`, `data/`, caches) are omitted.", "", "```"]

    def walk(folder: Path, prefix: str = "") -> None:
        entries = sorted((p for p in folder.iterdir() if p.name not in EXCLUDE and p.name != ".claude"),
                         key=lambda p: (p.is_file(), p.name.lower()))
        for i, p in enumerate(entries):
            last = i == len(entries) - 1
            out.append(f"{prefix}{'└── ' if last else '├── '}{p.name}{'/' if p.is_dir() else ''}")
            if p.is_dir():
                walk(p, prefix + ("    " if last else "│   "))

    out.append(f"{ROOT.name}/")
    walk(ROOT)
    out.append("```")
    return "\n".join(out) + "\n"


def env_vars() -> str:
    from rag_workbench.config import ENV_VARS, Settings

    fields = Settings.model_fields
    rows = ["# Environment variables", "", "From `rag_workbench.config.ENV_VARS` and the `Settings` model.", "",
            "| Variable | Setting | Default | Constraint |", "|---|---|---|---|"]
    for var, name in ENV_VARS.items():
        f = fields[name]
        default = f.default
        if hasattr(default, "relative_to"):
            with contextlib.suppress(ValueError):
                default = default.relative_to(Settings().project_root).as_posix()
        constraints = ", ".join(str(m) for m in f.metadata) or "—"
        rows.append(f"| `{var}` | `{name}` | `{default}` | {constraints} |")
    return "\n".join(rows) + "\n"


def metric_catalogue() -> str:
    from rag_workbench.metrics import METRIC_SPECS

    rows = ["# Metric catalogue", "", "From `rag_workbench.metrics.METRIC_SPECS`.", "",
            "| Name | Label | Family | Default threshold | Needs reference | Needs context | Needs OpenAI | Description |",
            "|---|---|---|---:|---|---|---|---|"]
    for name, s in METRIC_SPECS.items():
        def yn(b):
            return "yes" if b else "no"

        rows.append(f"| `{name}` | {s.label} | {s.family} | {s.default_threshold} | {yn(s.requires_reference)} | "
                    f"{yn(s.requires_context)} | {yn(s.requires_openai)} | {s.description} |")
    return "\n".join(rows) + "\n"


def test_catalogue() -> str:
    lines = ["# Test catalogue", "", "Every test function, with its docstring or, failing that, its first assertion.",
             ""]
    total = 0
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        src = text.splitlines()
        tests = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
        lines += [f"## `tests/{path.name}` ({len(tests)})", "", "| Test | Line | What it checks |", "|---|---:|---|"]
        for t in tests:
            total += 1
            params = next((d for d in t.decorator_list if isinstance(d, ast.Call) and getattr(d.func, "attr", "") ==
                           "parametrize"), None)
            note = summary(t)
            if not note:
                first = next((n for n in ast.walk(t) if isinstance(n, ast.Assert)), None)
                note = "`" + src[first.lineno - 1].strip().replace("|", "\\|")[:110] + "`" if first else "—"
            if params is not None:
                note += " *(parametrised)*"
            lines.append(f"| `{t.name}` | {t.lineno} | {note} |")
        lines.append("")
    lines.insert(2, f"{total} test functions (parametrised tests expand to more test cases at run time).")
    return "\n".join(lines)


def cli_reference() -> str:
    from rag_workbench.cli import build_parser

    parser = build_parser()
    out = ["# CLI reference", "", "Captured from the argparse definitions in `src/rag_workbench/cli.py`.", "",
           "```text", parser.format_help().rstrip(), "```", ""]
    sub = next(a for a in parser._actions if a.__class__.__name__ == "_SubParsersAction")
    for name, sp in sub.choices.items():
        out += [f"## `ragwb {name}`", "", "```text", sp.format_help().rstrip(), "```", ""]
    return "\n".join(out)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    outputs = {"source-inventory.md": source_inventory(), "directory-tree.md": directory_tree(),
               "env-vars.md": env_vars(), "metric-catalogue.md": metric_catalogue(),
               "test-catalogue.md": test_catalogue(), "cli-reference.md": cli_reference()}
    for name, content in outputs.items():
        (OUT / name).write_text(content, encoding="utf-8")
        print(f"{name}: {len(content.splitlines())} lines")


if __name__ == "__main__":
    main()
