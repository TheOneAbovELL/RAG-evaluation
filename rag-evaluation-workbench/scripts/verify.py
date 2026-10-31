"""Local verification sequence for RAG Evaluation Workbench.

    uv run python scripts/verify.py            # everything
    uv run python scripts/verify.py --quick    # skip coverage and the UI tests

Steps (each prints PASS/FAIL; the exit code is non-zero if any step fails):

1. environment     Python version and required packages importable
2. lockfile        ``uv lock --check --offline`` (skipped when uv is not on PATH)
3. secrets         no API-key-shaped strings or .env files in the project tree
4. static          ruff (lint) and mypy (types); skipped with a note if the dev tools are not installed
5. tests           pytest (with coverage unless --quick)
6. end-to-end      CLI run → show → export (csv/json/md) → import → compare → slices → labels → tag → regress →
                   tune-abstention → user list → doctor → backup,
                   in a temporary data dir

Optional: ``--audit`` also runs pip-audit on the locked runtime dependencies (it sends package names and versions, never
code or data, to a vulnerability database), and ``--wheel`` runs ``scripts/wheel_check.py`` (builds the wheel and installs it
with all its dependencies into a throwaway environment: it downloads from PyPI). These are the only steps that use the network.

Nothing here contacts a remote service, pushes, publishes, or writes outside the temporary directory
(plus pytest's own temporary directories and the coverage data file).
"""

from __future__ import annotations

import argparse
import importlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".venv", "__pycache__", ".pytest_cache", "data", "build", ".git"}
KEY_PATTERN = re.compile(rb"sk-(?:[A-Za-z0-9]+-)?[A-Za-z0-9_\-]{20,}")  # sk-..., sk-proj-..., sk-svcacct-...
FAKE_MARKER = b"not-a-real"  # deliberately fake keys in tests carry this marker and are ignored
results: list[tuple[str, bool, str]] = []


def step(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""), flush=True)


def run(cmd: list[str], env: dict | None = None, cwd: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", check=False)


def check_environment() -> None:
    ok = sys.version_info >= (3, 12)
    missing = []
    for module in ("rag_workbench", "streamlit", "pandas", "pydantic", "pymupdf", "langchain", "langchain_openai",
                   "deepeval", "pytest"):
        try:
            importlib.import_module(module)
        except ImportError:
            missing.append(module)
    step("environment", ok and not missing,
         f"Python {sys.version.split()[0]}" + (f"; missing: {', '.join(missing)}" if missing else ""))


def check_lockfile() -> None:
    if shutil.which("uv") is None:
        step("lockfile", True, "skipped (uv not on PATH)")
        return
    proc = run(["uv", "lock", "--check", "--offline"])
    step("lockfile", proc.returncode == 0, (proc.stderr or proc.stdout).strip().splitlines()[-1:][0]
         if (proc.stderr or proc.stdout).strip() else "")


def check_secrets() -> None:
    hits = []
    env_files = []
    for path in ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts) or not path.is_file():
            continue
        if path.name == ".env":
            env_files.append(path.relative_to(ROOT))  # the documented home of the key: allowed, but never shared
            continue
        if path.stat().st_size < 5_000_000:
            found = [m for m in KEY_PATTERN.findall(path.read_bytes()) if FAKE_MARKER not in m]
            if found:
                hits.append(str(path.relative_to(ROOT)))
    ignored = all(".env" in (ROOT / name).read_text(encoding="utf-8", errors="ignore").split()
                  for name in (".gitignore", ".dockerignore") if (ROOT / name).is_file())
    if env_files and not ignored:
        hits.append(".env is present but not listed in .gitignore and .dockerignore")
    note = "; a .env file is present (git/docker-ignored): never share, zip or sync this folder publicly" if env_files else ""
    step("secrets", not hits, "; ".join(hits) if hits else "no key-shaped strings outside .env" + note)


def check_static() -> None:
    problems, ran = [], []
    for name, cmd in (("ruff", [sys.executable, "-m", "ruff", "check", "."]),
                      ("mypy", [sys.executable, "-m", "mypy"])):
        proc = run(cmd)
        if "No module named" in proc.stderr:
            ran.append(f"{name} not installed")
            continue
        ran.append(name)
        if proc.returncode != 0:
            problems.append(f"{name}: {(proc.stdout or proc.stderr).strip().splitlines()[-1:][0]}")
    step("static", not problems, "; ".join(problems) if problems else "clean (" + ", ".join(ran) + ")")


def check_audit() -> None:
    if shutil.which("uv") is None:
        step("audit", True, "skipped (uv not on PATH)")
        return
    exported = run(["uv", "export", "--frozen", "--no-dev", "--all-extras", "--no-hashes", "--no-emit-project"])
    if exported.returncode != 0:
        step("audit", False, "could not export the locked requirements")
        return
    with tempfile.TemporaryDirectory(prefix="ragwb-audit-") as tmp:
        req = Path(tmp) / "requirements.txt"
        req.write_text(exported.stdout, encoding="utf-8")
        proc = run([sys.executable, "-m", "pip_audit", "--no-deps", "--disable-pip", "-r", str(req)])
    if "No module named" in proc.stderr:
        step("audit", True, "skipped (pip-audit not installed)")
        return
    step("audit", proc.returncode == 0, (proc.stdout or proc.stderr).strip().splitlines()[-1:][0])


def check_wheel() -> None:
    proc = run([sys.executable, str(ROOT / "scripts" / "wheel_check.py")])
    lines = [line for line in proc.stdout.strip().splitlines() if line.strip()]
    step("wheel", proc.returncode == 0, lines[-1] if lines else (proc.stderr.strip()[-200:] or "no output"))
    if proc.returncode != 0:
        print(proc.stdout[-3000:])


def check_tests(quick: bool) -> None:
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    if quick:
        cmd += ["-m", "not ui"]
    else:
        cmd += ["--cov", "--cov-report=term"]
    proc = run(cmd)
    tail = [line for line in proc.stdout.strip().splitlines() if line.strip()]
    summary = next((line for line in reversed(tail) if " passed" in line or " failed" in line), "no summary")
    total = next((line for line in tail if line.startswith("TOTAL")), "")
    step("tests", proc.returncode == 0, summary.strip("= ") + (f"; coverage {total.split()[-1]}" if total else ""))
    if proc.returncode != 0:
        print(proc.stdout[-4000:])


def check_end_to_end() -> None:
    with tempfile.TemporaryDirectory(prefix="ragwb-verify-") as tmp:
        env = {**os.environ, "RAGWB_DATA_DIR": tmp, "OPENAI_API_KEY": "", "DEEPEVAL_TELEMETRY_OPT_OUT": "1"}
        cli = [sys.executable, "-m", "rag_workbench"]
        problems = []

        def ok(args: list[str], expect: int = 0) -> str:
            proc = run(cli + args, env=env)
            if proc.returncode != expect:
                problems.append(f"{' '.join(args)} -> exit {proc.returncode}: {proc.stderr.strip()[:200]}")
            return proc.stdout

        for dataset in sorted((ROOT / "examples" / "datasets").iterdir()):
            ok(["validate", str(dataset)])
        out = ok(["run", "--name", "verify-k3", "-k", "3", "--quiet"])
        match = re.search(r"Run (\S+): completed", out)
        if not match:
            problems.append("offline run did not complete")
        else:
            run_id = match.group(1)
            ok(["show", run_id])
            for fmt in ("csv", "json", "md"):
                ok(["export", run_id, "--format", fmt, "--out-dir", tmp])
            ok(["import", str(Path(tmp) / f"{run_id}.json")])  # bundle round trip (already present: skipped)
            other = re.search(r"Run (\S+): completed", ok(["run", "--name", "verify-k1", "-k", "1", "--quiet"]))
            if other:
                ok(["compare", other.group(1), run_id])
            ok(["run", "--name", "verify-failures", "--inject-failures", "1.0", "--limit", "2", "--quiet"], expect=2)
            ok(["run", "--provider", "openai"], expect=1)  # must refuse cleanly without a key
            typed = re.search(r"Run (\S+): completed", ok(["run", "--name", "verify-typed", "--quiet", "--dataset",
                                                         str(ROOT / "examples" / "datasets" / "honeybees_unanswerable.jsonl")]))
            if typed:
                ok(["slices", typed.group(1), "--by", "type"])
            ok(["labels-template", run_id, "--out", str(Path(tmp) / "labels.csv")])
            ok(["tag", run_id, "--add", "verify"])
            ok(["list", "--tag", "verify"])
            ok(["regress", run_id, run_id])  # a run never regresses against itself
            ok(["tune-abstention", "--dataset", str(ROOT / "examples" / "datasets" / "honeybees_unanswerable.jsonl"),
                "--document", str(ROOT / "examples" / "documents" / "honeybees.pdf")])
            ok(["user", "list"])
            ok(["backup", "--out-dir", tmp])
            ok(["doctor"])
        step("end-to-end", not problems, "; ".join(problems) if problems else "CLI workflow completed offline")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--audit", action="store_true", help="also run pip-audit (contacts a vulnerability database)")
    parser.add_argument("--wheel", action="store_true", help="also check a clean wheel install (downloads from PyPI)")
    args = parser.parse_args()
    os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "1")
    check_environment()
    check_lockfile()
    check_secrets()
    check_static()
    check_tests(args.quick)
    check_end_to_end()
    if args.audit:
        check_audit()
    if args.wheel:
        check_wheel()
    failed = [name for name, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed" + (f"; failed: {', '.join(failed)}"
                                                                         if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
