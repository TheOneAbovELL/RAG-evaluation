# Contributing

Thank you for looking at the RAG Evaluation Workbench. This page is the short path from a fresh clone to a passing check.

## Set up

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run python start.py
```

`start.py` is the single launcher (web app, CLI help, offline demo). Optional local embeddings: `uv sync --extra semantic`.
Copy `.env.example` to `.env` only if you want a provider; the tool works fully offline without one. Never commit `.env`.

## Check your change

```bash
uv run python scripts/verify.py
```

This runs the environment, lockfile, secret scan, ruff and mypy, the test suite with coverage, an end-to-end offline workflow and,
with `--audit` and `--wheel`, a dependency vulnerability audit and a clean wheel-install check.
The tests never call a network or provider; keep it that way (see `docs/TESTING.md`).

## Layout

| Path | What it holds |
|---|---|
| `src/rag_workbench/` | the package (`cli.py` is the `ragwb` command; `metrics/` and `ui/views/` are subpackages) |
| `tests/` | the test suite |
| `scripts/` | verification, benchmarks, key helper |
| `examples/` | sample documents and datasets |
| `calibration/` | a re-importable live run and labelling sheets for the judge check |
| `docs/` | reference documents, the Project Book and the Practitioner's Guide |

## Ground rules

- Match the surrounding style; `ruff` and `mypy` must be clean.
- Add a test for every behaviour change; update `CHANGELOG.md` and the affected document in `docs/`.
- Never put a key, token or personal data in a file, a test, a log or a commit.
- Report security problems as described in `docs/SECURITY.md`.

Licensed under the MIT License (see `LICENSE`).
