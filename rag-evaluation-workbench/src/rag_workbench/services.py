"""Application wiring shared by the CLI and the Streamlit app."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

from .config import EXAMPLES_DIR, Settings, load_settings
from .logging_setup import configure_logging
from .reporting import safe_filename
from .runner import EvaluationRunner
from .storage import RunStore

log = logging.getLogger(__name__)

@dataclass
class AppContext:
    settings: Settings
    store: RunStore

    def runner(self) -> EvaluationRunner:
        return EvaluationRunner(self.settings, self.store)


def open_context(settings: Settings | None = None, *, console_logging: bool = True) -> AppContext:
    """Load settings, configure logging, open the store and mark runs left ``running`` as interrupted."""
    settings = settings or load_settings()
    configure_logging(settings, console=console_logging)
    store = RunStore(settings.db_path)
    recovered = store.recover_interrupted()
    if recovered:
        log.warning("Marked %d run(s) interrupted by a previous shutdown", recovered)
    return AppContext(settings=settings, store=store)


def save_upload(settings: Settings, filename: str, data: bytes, *, allowed_suffixes: set[str],
                max_bytes: int) -> Path:
    """Store an uploaded file under ``uploads/`` with a sanitised, content-addressed name.

    The client-supplied name is reduced to safe characters (no separators, no ``..``) and prefixed
    with a hash of the content, so uploads can never escape the uploads directory or overwrite a
    different file.
    """
    suffix = Path(filename).suffix.lower()
    if suffix not in allowed_suffixes:
        raise ValueError(f"File type {suffix or '(none)'} not allowed; use {', '.join(sorted(allowed_suffixes))}")
    if len(data) > max_bytes:
        raise ValueError(f"File is {len(data):,} bytes; the limit is {max_bytes:,} bytes")
    digest = hashlib.sha256(data).hexdigest()[:12]
    stem = safe_filename(Path(filename).stem)[:60]
    target_dir = settings.uploads_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    target = (target_dir / f"{digest}-{stem}{suffix}").resolve()
    if target.parent != target_dir.resolve():  # defence in depth against traversal
        raise ValueError("Invalid upload filename")
    if not target.exists():
        target.write_bytes(data)
    return target


def bundled_datasets(settings: Settings) -> list[Path]:
    """The default dataset followed by the example datasets shipped in ``examples/datasets/``."""
    samples = EXAMPLES_DIR / "datasets"
    found = sorted(p for p in samples.iterdir() if p.suffix.lower() in {".jsonl", ".csv"}) if samples.is_dir() else []
    return [settings.default_dataset, *found]


def list_files(settings: Settings, suffixes: set[str], extra: list[Path]) -> list[Path]:
    """Known files of the given types: bundled defaults first, then uploads (newest first)."""
    files = [p for p in extra if p.is_file()]
    if settings.uploads_dir.is_dir():
        uploads = sorted((p for p in settings.uploads_dir.iterdir() if p.suffix.lower() in suffixes),
                         key=lambda p: p.stat().st_mtime, reverse=True)
        files += uploads
    seen, unique = set(), []
    for p in files:
        if p.resolve() not in seen:
            seen.add(p.resolve())
            unique.append(p)
    return unique
