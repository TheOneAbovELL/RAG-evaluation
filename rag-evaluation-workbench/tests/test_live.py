"""Opt-in live tests. They are skipped unless BOTH ``RAGWB_LIVE_TESTS=1`` and ``OPENAI_API_KEY`` are set, because they
make paid API calls. Run with:  RAGWB_LIVE_TESTS=1 uv run pytest -m live

The guard tests at the bottom run always: they prove the smoke script cannot spend money by accident."""

import os
import subprocess
import sys

import pytest

from rag_workbench.config import PROJECT_ROOT

SCRIPT = PROJECT_ROOT / "scripts" / "live_smoke.py"


def live_enabled() -> bool:
    return os.environ.get("RAGWB_LIVE_TESTS") == "1" and bool(os.environ.get("OPENAI_API_KEY", "").strip())


# The suite's autouse fixture blanks OPENAI_API_KEY for isolation, so live tests read the real key from the
# process environment captured at import time.
REAL_KEY = os.environ.get("OPENAI_API_KEY", "")


@pytest.mark.live
@pytest.mark.skipif(not live_enabled(), reason="set RAGWB_LIVE_TESTS=1 and OPENAI_API_KEY to run paid live tests")
def test_live_smoke_script_passes(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", REAL_KEY)
    result = subprocess.run([sys.executable, str(SCRIPT), "--yes-spend", "--cases", "2"], capture_output=True,
                            text=True, timeout=900, check=False)
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]
    assert "checks passed" in result.stdout


def run_script(*args, env=None):
    base = {"SYSTEMROOT": os.environ.get("SYSTEMROOT", ""), "PATH": os.environ.get("PATH", ""),
            "OPENAI_API_KEY": "", "RAGWB_DATA_DIR": "", "RAGWB_NO_DOTENV": "1"}
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=120,
                          env=base | (env or {}), check=False)


def test_smoke_script_refuses_to_spend_without_the_flag():
    result = run_script(env={"OPENAI_API_KEY": "sk-not-a-real-key-for-tests-123"})
    assert result.returncode == 2 and "--yes-spend" in result.stderr


def test_smoke_script_refuses_without_a_key():
    result = run_script("--yes-spend")
    assert result.returncode == 2 and "OPENAI_API_KEY is not set" in result.stderr


@pytest.mark.parametrize("cases", ["0", "6", "-1"])
def test_smoke_script_caps_the_number_of_cases(cases):
    result = run_script("--yes-spend", "--cases", cases, env={"OPENAI_API_KEY": "sk-not-a-real-key-for-tests-123"})
    assert result.returncode == 2 and "between 1 and 5" in result.stderr


def test_smoke_script_reports_failure_and_exits_nonzero_when_the_api_is_unreachable():
    """Whole flow with a fake key and a closed local port (no external traffic): it must fail loudly, not vacuously."""
    result = run_script("--yes-spend", "--cases", "1", "--skip-judge", env={
        "OPENAI_API_KEY": "sk-not-a-real-key-for-tests-123", "OPENAI_BASE_URL": "http://127.0.0.1:9/v1",
        "RAGWB_MAX_RETRIES": "0", "RAGWB_REQUEST_TIMEOUT_S": "3"})
    assert result.returncode == 1, result.stdout + result.stderr
    assert "[FAIL] at least one case succeeded" in result.stdout and "0/8 checks passed" in result.stdout
    assert "[PASS]" not in result.stdout  # nothing passes vacuously on an empty run
    assert "sk-not-a-real" not in result.stdout + result.stderr  # the key is never printed
