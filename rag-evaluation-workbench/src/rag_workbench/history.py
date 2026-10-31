"""Organising run history: tags, notes and search.

Tags are short lowercase labels (``baseline``, ``prompt-v2``) that let a growing history be filtered; they are stored
with the run and travel with exported bundles. Search is a plain case-insensitive match over the fields a person
remembers a run by, with every word of the query required (AND).
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from .models import RunRecord

MAX_TAGS = 10
MAX_TAG_LENGTH = 30
MAX_NOTES_CHARS = 2000
_TAG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


class TagError(ValueError):
    """A tag or note is not acceptable."""


def normalise_tags(tags: Iterable[str]) -> list[str]:
    """Lowercase, strip, de-duplicate (keeping first-seen order) and validate. Raises :class:`TagError`."""
    out: list[str] = []
    for raw in tags:
        tag = str(raw).strip().lower().replace(" ", "-")
        if not tag:
            continue
        if len(tag) > MAX_TAG_LENGTH or not _TAG_RE.match(tag):
            raise TagError(f"Invalid tag {raw!r}: use up to {MAX_TAG_LENGTH} letters, digits, '.', '_' or '-'")
        if tag not in out:
            out.append(tag)
    if len(out) > MAX_TAGS:
        raise TagError(f"A run can have at most {MAX_TAGS} tags")
    return out


def parse_tag_list(text: str) -> list[str]:
    """``"a, b"`` -> ``["a", "b"]`` (commas or whitespace separate tags)."""
    return normalise_tags(part for part in re.split(r"[,\s]+", text or "") if part)


def validate_notes(notes: str | None) -> str | None:
    if notes is None or not notes.strip():
        return None
    if len(notes) > MAX_NOTES_CHARS:
        raise TagError(f"Notes are limited to {MAX_NOTES_CHARS} characters")
    return notes.strip()


def _haystack(run: RunRecord) -> str:
    config = run.config
    parts = [run.id, run.name, run.notes or "", " ".join(run.tags), run.status, str(config.get("provider", "")),
             str(config.get("pipeline", "")), str(config.get("retriever", "")),
             str(config.get("dataset_path", "")).replace("\\", "/").rsplit("/", 1)[-1],
             str(config.get("document_path", "")).replace("\\", "/").rsplit("/", 1)[-1]]
    return " ".join(parts).lower()


def search_runs(runs: Iterable[RunRecord], query: str = "", *, tag: str | None = None,
                status: str | None = None) -> list[RunRecord]:
    """Filter ``runs`` (order preserved). ``query`` words must all appear in the run's id, name, notes, tags, status,
    provider, pipeline, retriever or dataset/document file names."""
    words = query.lower().split()
    wanted = normalise_tags([tag])[0] if tag and tag.strip() else None
    found = []
    for run in runs:
        if wanted and wanted not in run.tags:
            continue
        if status and run.status != status:
            continue
        if words:
            text = _haystack(run)
            if not all(word in text for word in words):
                continue
        found.append(run)
    return found
