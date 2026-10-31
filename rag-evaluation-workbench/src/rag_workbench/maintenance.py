"""Operations tooling: health checks (``ragwb doctor``), store backup, retention pruning and re-running a stored run.

Everything here is local: no network calls are made (``doctor`` reports whether an API key is *configured*, it never
calls the API). Destructive operations default to a dry run and refuse to touch runs that may still be executing.
"""

from __future__ import annotations

import importlib.metadata
import os
import shutil
import sqlite3
import sys
import tempfile
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Literal

from .config import Settings
from .datasets import validate_file
from .documents import DocumentError, load_chunks
from .models import RunConfig, RunRecord, utcnow
from .storage import SCHEMA_VERSION, STALE_AFTER_S, RunStore, StorageError

CheckStatus = Literal["ok", "warn", "fail"]
MIN_FREE_DISK_BYTES = 500 * 1024 * 1024
REQUIRED_PACKAGES = ("pydantic", "pandas", "pymupdf", "streamlit", "langchain", "langchain-openai", "deepeval",
                     "openai", "python-dotenv")
LOCAL_ADDRESSES = {"localhost", "127.0.0.1", "::1"}


@dataclass(frozen=True)
class Check:
    name: str
    status: CheckStatus
    detail: str


# ------------------------------------------------------------------------------------------------- doctor
def run_doctor(settings: Settings, *, config_file: Path | None = None) -> list[Check]:
    """Run every health check and return the results (never raises)."""
    checks: list[Check] = []
    probes: list[Callable[[], Check]] = [
        _check_python, _check_packages, lambda: _check_data_dir(settings), lambda: _check_disk(settings),
        lambda: _check_store(settings), lambda: _check_examples(settings), lambda: _check_key(settings),
        _check_telemetry, lambda: _check_exposure(settings, config_file),
    ]
    for probe in probes:
        try:
            checks.append(probe())
        except Exception as exc:  # a probe must never take the diagnostics down
            checks.append(Check("diagnostics", "fail", f"a check crashed: {type(exc).__name__}: {exc}"))
    return checks


def _check_python() -> Check:
    version = ".".join(map(str, sys.version_info[:3]))
    ok = sys.version_info >= (3, 12)
    return Check("python", "ok" if ok else "fail", f"{version}" + ("" if ok else " (3.12 or newer is required)"))


def _check_packages() -> Check:
    missing, versions = [], []
    for name in REQUIRED_PACKAGES:
        try:
            versions.append(f"{name} {importlib.metadata.version(name)}")
        except importlib.metadata.PackageNotFoundError:
            missing.append(name)
    if missing:
        return Check("packages", "fail", "missing: " + ", ".join(missing) + " (run `python start.py` or `uv sync`)")
    return Check("packages", "ok", f"{len(versions)} required packages installed")


def _check_data_dir(settings: Settings) -> Check:
    try:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=settings.data_dir, prefix=".doctor-", delete=True):
            pass
    except OSError as exc:
        return Check("data directory", "fail", f"{settings.data_dir} is not writable: {exc}")
    return Check("data directory", "ok", f"{settings.data_dir} is writable")


def _check_disk(settings: Settings) -> Check:
    anchor = settings.data_dir if settings.data_dir.exists() else settings.project_root
    free = shutil.disk_usage(anchor).free
    text = f"{free / 1e9:.1f} GB free"
    return Check("disk space", "ok" if free >= MIN_FREE_DISK_BYTES else "warn",
                 text + ("" if free >= MIN_FREE_DISK_BYTES else " (less than 500 MB)"))


def _check_store(settings: Settings) -> Check:
    path = settings.db_path
    if not path.exists():
        return Check("run store", "ok", "not created yet (created on first use)")
    try:
        store = RunStore(path)
        runs = store.list_runs()
        with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True) as conn:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            version = conn.execute("PRAGMA user_version").fetchone()[0]
    except (StorageError, sqlite3.Error) as exc:
        return Check("run store", "fail", f"{path} cannot be read: {exc}")
    if integrity != "ok":
        return Check("run store", "fail", f"integrity check failed: {integrity}")
    stale = [r for r in runs if r.status == "running" and _is_stale(r)]
    detail = f"schema v{version}, {len(runs)} runs, integrity ok"
    if stale:
        return Check("run store", "warn", detail + f"; {len(stale)} run(s) look abandoned "
                     "(they are marked interrupted at the next start)")
    return Check("run store", "ok", detail)


def _is_stale(run: RunRecord) -> bool:
    return (utcnow() - run.created_at).total_seconds() > STALE_AFTER_S


def _check_examples(settings: Settings) -> Check:
    problems = []
    report = validate_file(settings.default_dataset)
    if not report.ok:
        problems.append(f"dataset {settings.default_dataset.name}: " + "; ".join(str(e) for e in report.errors[:2]))
    try:
        load_chunks(settings.default_document, max_bytes=settings.max_document_bytes)
    except DocumentError as exc:
        problems.append(f"document {settings.default_document.name}: {exc}")
    if problems:
        return Check("default data", "warn", " | ".join(problems))
    return Check("default data", "ok", f"{settings.default_dataset.name} and {settings.default_document.name} load")


def _check_key(settings: Settings) -> Check:
    if settings.has_openai_key:
        return Check("OpenAI key", "ok", "configured (not verified: doctor makes no network calls)")
    return Check("OpenAI key", "ok", "not set: offline mode only (BM25, extractive baseline, lexical metrics)")


def _check_telemetry() -> Check:
    value = os.environ.get("DEEPEVAL_TELEMETRY_OPT_OUT", "")
    if value.lower() in {"1", "true", "yes"}:
        return Check("telemetry", "ok", "DeepEval telemetry is disabled")
    return Check("telemetry", "warn", "DEEPEVAL_TELEMETRY_OPT_OUT is not set; importing rag_workbench sets it to 1")


def _check_exposure(settings: Settings, config_file: Path | None) -> Check:
    config_file = config_file or settings.project_root / ".streamlit" / "config.toml"
    address = "localhost"
    if config_file.is_file():
        try:
            address = tomllib.loads(config_file.read_text(encoding="utf-8")).get("server", {}).get("address", "")
        except (tomllib.TOMLDecodeError, OSError) as exc:
            return Check("network exposure", "warn", f"{config_file.name} unreadable: {exc}")
    if address in LOCAL_ADDRESSES:
        return Check("network exposure", "ok", f"the app listens on {address} only")
    if not address:
        return Check("network exposure", "fail" if not settings.has_app_password else "warn",
                     "server.address is unset, so Streamlit listens on all interfaces"
                     + ("" if settings.has_app_password else " and no RAGWB_APP_PASSWORD is configured"))
    if settings.has_app_password:
        return Check("network exposure", "warn", f"the app listens on {address}; access requires the password")
    return Check("network exposure", "fail", f"the app listens on {address} with no RAGWB_APP_PASSWORD configured")


# ------------------------------------------------------------------------------------------------- backup
def backup_store(store_path: Path, dest_dir: Path) -> Path:
    """Copy the run store with SQLite's online backup API (consistent even while the app is writing).

    The copy is verified with ``PRAGMA integrity_check`` and removed if it fails. Returns the backup path.
    """
    if not store_path.is_file():
        raise StorageError(f"No run store at {store_path}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    # The clock can tick coarsely (about 15 ms on some Windows systems), so a timestamp alone is not unique:
    # add a counter.
    stem = f"runs-{utcnow():%Y%m%d-%H%M%S-%f}"
    target, attempt = dest_dir / f"{stem}.db", 1
    while target.exists():
        attempt += 1
        target = dest_dir / f"{stem}-{attempt}.db"
    source = sqlite3.connect(f"file:{store_path.as_posix()}?mode=ro", uri=True)
    try:
        destination = sqlite3.connect(target)
        try:
            source.backup(destination)
            verdict = destination.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            destination.close()
    except sqlite3.Error as exc:
        target.unlink(missing_ok=True)
        raise StorageError(f"Backup failed: {exc}") from exc
    finally:
        source.close()
    if verdict != "ok":
        target.unlink(missing_ok=True)
        raise StorageError(f"Backup failed its integrity check: {verdict}")
    return target


# ------------------------------------------------------------------------------------------------- prune
def select_prunable(runs: list[RunRecord], *, keep_last: int | None = None,
                    older_than_days: float | None = None) -> list[RunRecord]:
    """Runs eligible for deletion under a retention policy. Runs that may still be executing are never selected.

    ``keep_last`` keeps the newest N runs; ``older_than_days`` selects runs created before the cutoff. With both,
    a run must satisfy both conditions (older than the cutoff *and* outside the newest N). A run tagged ``keep``
    is never selected, whatever its age or position: that is how a baseline is protected.
    """
    if keep_last is None and older_than_days is None:
        raise ValueError("Give keep_last and/or older_than_days; refusing to select every run")
    ordered = sorted(runs, key=lambda r: r.created_at, reverse=True)
    protected = {r.id for r in ordered[:keep_last]} if keep_last is not None else set()
    cutoff = utcnow() - timedelta(days=older_than_days) if older_than_days is not None else None
    chosen = []
    for run in ordered:
        if run.id in protected or "keep" in run.tags:
            continue
        if run.status == "running" and not _is_stale(run):
            continue
        if cutoff is not None and run.created_at >= cutoff:
            continue
        chosen.append(run)
    return chosen


# ------------------------------------------------------------------------------------------------- rerun
def restore_store(backup_path: Path, store_path: Path, safety_dir: Path, *,
                  force: bool = False) -> tuple[Path, Path | None]:
    """Replace the run store with a backup made by :func:`backup_store`.

    The backup is checked first (opens read-only, ``integrity_check`` is ``ok``, has the runs table, and is not from a
    newer schema than this version understands). A safety copy of the current store is written to ``safety_dir`` before
    anything is replaced, so a restore can itself be undone. A store that has a run recently active (``running`` with a
    fresh heartbeat) is refused unless ``force``: the app or a CLI run may still be writing to it.

    Returns ``(store_path, safety_copy_or_None)``.
    """
    if not backup_path.is_file():
        raise StorageError(f"Backup not found: {backup_path}")
    try:
        probe = sqlite3.connect(f"file:{backup_path.as_posix()}?mode=ro", uri=True)
        try:
            verdict = probe.execute("PRAGMA integrity_check").fetchone()[0]
            version = probe.execute("PRAGMA user_version").fetchone()[0]
            tables = {r[0] for r in probe.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        finally:
            probe.close()
    except sqlite3.Error as exc:
        raise StorageError(f"{backup_path.name} is not a readable run store: {exc}") from exc
    if verdict != "ok":
        raise StorageError(f"{backup_path.name} failed its integrity check: {verdict}")
    if not {"runs", "case_results"} <= tables:
        raise StorageError(f"{backup_path.name} is not a run store (no runs/case_results tables)")
    if version > SCHEMA_VERSION:
        raise StorageError(f"{backup_path.name} was made by a newer version (schema {version}); upgrade first")

    safety: Path | None = None
    if store_path.is_file():
        try:
            if not force:
                current = RunStore(store_path)
                now = utcnow()
                active = [r for r in current.list_runs() if r.status == "running"
                          and (now - (current.heartbeat(r.id) or r.created_at)).total_seconds() < STALE_AFTER_S]
                if active:
                    raise StorageError(f"Run {active[0].id} is still active; stop it first or pass --force")
            safety = backup_store(store_path, safety_dir)
            safety = safety.rename(safety.with_name("pre-restore-" + safety.name))
        except StorageError as exc:
            if "still active" in str(exc):
                raise
            # The current store is unreadable (this is exactly when a restore is needed): keep a raw copy of the damaged
            # file instead of a consistent snapshot, so nothing is lost, then carry on.
            safety_dir.mkdir(parents=True, exist_ok=True)
            safety = safety_dir / f"pre-restore-damaged-{utcnow():%Y%m%d-%H%M%S-%f}.db"
            shutil.copyfile(store_path, safety)
    staged = store_path.with_suffix(".restoring")
    store_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(backup_path, staged)
    try:
        for sidecar in ("-wal", "-shm", "-journal"):
            Path(str(store_path) + sidecar).unlink(missing_ok=True)
        os.replace(staged, store_path)
    except PermissionError as exc:  # Windows: another process (the web app) still has the file open
        staged.unlink(missing_ok=True)
        raise StorageError(f"The run store is in use by another process ({exc.strerror}); stop the web app and any "
                           "running evaluation, then try again. Nothing was changed.") from exc
    RunStore(store_path)  # opens it, which migrates an older schema to the current one
    return store_path, safety


def rerun_config(run: RunRecord, *, name: str | None = None, project_root: Path | None = None) -> RunConfig:
    """Rebuild a :class:`RunConfig` from a stored run so the same experiment can be repeated.

    Relative dataset/document paths (as written into exported bundles) are resolved against ``project_root``.
    Raises ``ValueError`` if the stored configuration is no longer valid.
    """
    stored = dict(run.config)
    for key in ("dataset_path", "document_path"):
        value = stored.get(key)
        if value and project_root is not None and not Path(value).is_absolute():
            stored[key] = str(project_root / value)
    stored["name"] = name or f"{run.name}-rerun"
    stored["started_by"] = None  # a re-run is a new run; it must not inherit the original starter
    stored["notes"] = f"Re-run of {run.id}" + (f". {run.notes}" if run.notes else "")
    return RunConfig.model_validate(stored)
