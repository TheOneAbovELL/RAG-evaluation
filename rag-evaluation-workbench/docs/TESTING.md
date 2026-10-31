# Testing

```bash
uv run pytest                      # all 455 tests, offline, ~2 min
uv run pytest -m "not ui"          # skip the Streamlit journeys
uv run pytest --cov                # with statement coverage
uv run python scripts/verify.py    # the full local check sequence (static analysis, tests, end-to-end)
```

## What the suite guarantees

Every test runs with **no API key and an isolated temporary data directory** (`tests/conftest.py::isolated_env`),
so the suite never touches `data/` and never contacts a network service.

| File | Tests | Covers |
|---|---:|---|
| `test_config.py` | 9 | defaults, path resolution, invalid values naming the variable, secret never exposed |
| `test_text.py` | 19 | tokenisation (Unicode), stemming, SQuAD normalisation, sentence split, abstention detection |
| `test_datasets.py` | 19 | JSONL/CSV parsing, every validation error with line numbers, limits, non-UTF-8, non-ASCII |
| `test_documents.py` | 5 | PDF blocks of the example document (11 chunks), text splitting, long-block splitting, error cases |
| `test_retrieval.py` | 7 | BM25 score vs hand computation, ranking, deterministic ties, lazy embedding index, error classification |
| `test_providers_pipeline.py` | 10 | extractive generator, failure injection, OpenAI error mapping, agent context capture |
| `test_metrics.py` | 15 | lexical metrics vs hand-computed values, skip rules, out-of-range scores, judge adapter with fakes |
| `test_aggregate.py` | 6 | missing-value handling, bootstrap determinism, percentile, paired comparison |
| `test_storage.py` | 9 | round trip, duplicates, cascade delete, heartbeat-based interrupted recovery, v1→v2 migration, error translation, schema guard |
| `test_runner.py` | 16 | end-to-end offline run, reproducibility, retries/back-off, cancellation, threads, cost, example runs |
| `test_archive_reporting.py` | 13 | bundle export/import round trip from real runs, invalid bundles, summaries recomputed on import, no absolute paths in exports, CSV injection guard |
| `test_cli_services.py` | 9 | every CLI command (incl. bundle import), error exits, upload sanitisation, log and traceback redaction |
| `test_ui.py` | 9 | Streamlit AppTest journeys: empty state, stored runs, run → results → compare, invalid input, failures, provenance notes, HTML escaping of imported values, settings health checks |
| `test_maintenance.py` | 21 | doctor checks, consistent backup, prune selection, rerun configuration |
| `test_auth.py` | 8 | constant-time password match, lockout window, login gate |
| `test_start.py` | 14 | launcher host/password rules, readiness polling |
| `test_evaluation_options.py` | 21 | hybrid fusion, min-evidence abstention, heading skipping, slice breakdowns, settings |
| `test_calibration.py` | 39 | kappa by hand, label parsing and errors, labelling sheet round trip, CLI flow |
| `test_history.py` | 14 | tag/note validation, search semantics, storage round trip, bundles carry tags, CLI, Overview filter, Results editing |
| `test_regression.py` | 10 | significant drop, noise, improvement, too few pairs, no shared metrics, error-rate gate, CLI exit codes |
| `test_abstention.py` | 6 | confusion arithmetic, deterministic split, held-out reporting, CLI |
| `test_semantic.py` | 10 | cosine, similarity and context recall with a stand-in embedder, lazy single load, refusal without the package, full run |
| `test_users.py` | 22 | scrypt store, no stored passwords, normalisation, fail-closed damaged file, throttling, CLI, login/lockout/sign-out/started_by journeys |
| `test_packaging.py` | 5 | project-root resolution, wheel bundles examples |
| `test_example_corpus.py` | 9 | the three added documents and datasets are well-formed |
| `test_local_retrieval.py` | 9 | local retriever ranking and laziness, pipeline wiring without a key, install hint, full hybrid-local run, optional real-model check |
| `test_ratelimit.py` | 8 | even spacing, no burst after idling, shared by threads, setting validation, judge waits for its slot |
| `test_retry_hints.py` | 8 | Retry-After carried, tenacity unwrapping, transport-caused connection errors stay transient, back-off cap |
| `test_judge_noise.py` | 8 | within/between SD, flips, excluded failures, CLI confirmation gate |
| `test_roles.py` | 10 | role storage and defaults, tampered roles get least access, viewer/editor/admin journeys, removal and role change apply at once |
| `test_restore_concurrency.py` | 11 | restore round trip and reversibility, restore of an unreadable store keeps a raw copy, same-second backups do not collide, refusals leave the store untouched, active-run guard, older-schema migration, held-open store, four processes plus a reader on one store |
| `test_accounts_admin.py` | 12 | last-admin guard, password change, entries without secrets, admin Accounts journeys, non-admins cannot route to it, run visibility |
| `test_calibration_sweep.py` | 8 | threshold sweep table, best threshold and its tie rule, excluded cases, CLI sweep and rescore |
| `test_bm25_equivalence.py` | 12 | bit-for-bit equality with the textbook BM25 definition on random corpora, repeated terms, custom parameters, ties |
| `test_live.py` | 7 | opt-in paid live tests (skipped by default); guards and failure path of the smoke script |
| `test_cli_polish.py` | 19 | release 1.4.1 CLI fixes: run references by prefix, suffix or name, `show` tags and notes, `prune` and the `keep` tag, `--workers`/`--limit` below 1, `regress --metrics`, `calibrate` header and `--rescore` |
| `test_dotenv_switch.py` | 5 | `RAGWB_NO_DOTENV`, the project `.env` loaded by default, no leak into the suite, DeepEval's own dotenv loading switched off |
| `test_set_api_key.py` | 13 | `scripts/set_api_key.py`: only the key line changes, implausible keys refused, the key never printed, `--check` reports a status only |

The full catalogue (every test and what it asserts) is generated into
`docs/project-book/generated/test-catalogue.md`.

## Latest recorded results

From `uv run pytest --cov`: **453 passed, 0 failed, 2 skipped** (455 collected) (the opt-in live and real-model tests); statement coverage **97 %** (3,624 statements,
125 missed). `ui/views/*` is excluded from coverage measurement
(`[tool.coverage.run]` in `pyproject.toml`) because the page scripts run inside AppTest's script runner, which
coverage does not attribute reliably; those pages are exercised by `test_ui.py` instead.

## Not covered by automated tests

* Real OpenAI and DeepEval calls (adapters are tested with fakes only; `scripts/live_smoke.py` exists for a paid check).
* Browser-level rendering beyond AppTest (checked manually in a browser and via screenshots).
* Runs longer than a few minutes (multi-process use of one store is covered by `test_restore_concurrency.py`). Offline scale is measured by `scripts/benchmark.py`, not asserted by tests.
