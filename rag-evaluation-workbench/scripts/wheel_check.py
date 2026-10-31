"""Clean-install check: build the wheel, install it into a throwaway virtual environment, and use it from a neutral folder.

    uv run python scripts/wheel_check.py

What it proves: the wheel contains everything the command-line tool needs (including the bundled example data), a fresh
environment resolves its dependencies, data and logs go to the current directory (never into ``site-packages``), and the
core commands work with no project checkout on the path. The web app is not part of the wheel (it needs this project folder).

NETWORK: installing the dependencies downloads them from PyPI (several hundred MB; a few minutes on a cold cache). Nothing
from this project is uploaded. Everything is created in a temporary folder and removed afterwards. Needs ``uv`` on PATH.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""), flush=True)


def run(cmd: list[str], cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          check=False)


def main() -> int:
    if shutil.which("uv") is None:
        print("uv is required (https://docs.astral.sh/uv/)", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="ragwb-wheel-", ignore_cleanup_errors=True) as tmp_name:
        tmp = Path(tmp_name)
        dist, venv, work = tmp / "dist", tmp / "venv", tmp / "work"
        work.mkdir()
        built = run(["uv", "build", "--wheel", "--out-dir", str(dist)], ROOT)
        wheels = sorted(dist.glob("*.whl"))
        check("wheel builds", built.returncode == 0 and len(wheels) == 1, wheels[0].name if wheels else built.stderr[-300:])
        if not wheels:
            return 1
        made = run(["uv", "venv", str(venv), "--python", "3.12", "-q"], ROOT)
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        installed = run(["uv", "pip", "install", "--python", str(python), str(wheels[0])], ROOT)
        check("installs into a fresh venv", made.returncode == 0 and installed.returncode == 0,
              (installed.stderr.strip().splitlines() or [""])[-1][:200])
        if installed.returncode != 0:
            return 1
        env = {**os.environ, "OPENAI_API_KEY": "", "DEEPEVAL_TELEMETRY_OPT_OUT": "1"}
        env.pop("RAGWB_DATA_DIR", None)
        env.pop("RAGWB_HOME", None)

        where = run([str(python), "-c", "import rag_workbench as r; print(r.__file__)"], work, env)
        check("imports from site-packages, not the checkout", "site-packages" in where.stdout and str(ROOT) not in where.stdout,
              where.stdout.strip()[-80:])
        version = run([str(python), "-m", "rag_workbench", "--version"], work, env)
        check("--version", version.returncode == 0 and version.stdout.strip().startswith("ragwb "), version.stdout.strip())
        evaluation = run([str(python), "-m", "rag_workbench", "run", "--name", "wheel-check", "--quiet"], work, env)
        check("an offline evaluation completes", evaluation.returncode == 0 and "completed" in evaluation.stdout,
              evaluation.stderr.strip()[-200:])
        check("data is written to the current directory", (work / "data" / "runs.db").is_file(),
              str(work / "data"))
        check("nothing was written into site-packages", not (venv / "Lib" / "site-packages" / "data").exists()
              and not any((venv / "lib").glob("python*/site-packages/data")))
        doctor = run([str(python), "-m", "rag_workbench", "doctor"], work, env)
        check("doctor reports no failure", doctor.returncode == 0 and "0 failure" in doctor.stdout,
              doctor.stdout.strip().splitlines()[-1] if doctor.stdout.strip() else doctor.stderr[-200:])
        tuned = run([str(python), "-m", "rag_workbench", "tune-abstention"], work, env)
        check("bundled examples are found (tune-abstention)", tuned.returncode == 0 and "Held-out test half" in tuned.stdout,
              tuned.stderr.strip()[-200:])
        listing = run([str(python), "-m", "rag_workbench", "list"], work, env)
        check("the run store reads back", listing.returncode == 0 and "wheel-check" in listing.stdout)
    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed" + (f"; failed: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
