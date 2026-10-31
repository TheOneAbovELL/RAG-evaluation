# CLI and Python API Reference

The workbench has **no HTTP API**: both front ends call the `rag_workbench` package in-process. This page covers
the CLI and the Python entry points intended for scripting. Full argument listings are generated from argparse
into `docs/project-book/generated/cli-reference.md`; every public function with its line number is in
`docs/project-book/generated/source-inventory.md`.

## CLI (`uv run ragwb …`, or `python -m rag_workbench …`)

| Command | Purpose | Exit codes |
|---|---|---|
| `run [--name] [--dataset] [--document] [--provider offline\|openai] [--pipeline rag\|agent] [--retriever bm25\|embedding\|hybrid\|local\|hybrid-local] [-k N] [--metrics a,b] [--threshold m=v] [--model] [--judge-model] [--workers] [--limit] [--answer-sentences] [--inject-failures F] [--min-evidence X] [--skip-headings] [--seed] [--notes] [--quiet]` | run and store an evaluation | 0 completed · 2 partial or failed · 1 configuration error; Ctrl+C stops it (stored as `cancelled`, Python's interrupt exit) |
| `list` | stored runs | 0 |
| `show RUN_ID` | configuration and summary of one run | 0 · 1 unknown id |
| `compare RUN_A RUN_B` | paired comparison of B against A | 0 · 1 no shared metric / unknown id |
| `export RUN_ID [--format csv\|json\|md] [--out-dir]` | write an export (JSON = re-importable bundle) | 0 |
| `import BUNDLE [BUNDLE ...]` | import bundles written by `export --format json` | 0 · 1 invalid bundle |
| `validate DATASET` | validate a dataset file | 0 valid · 1 invalid |
| `score --question --answer [--expected] [--context ...] [--metrics]` | score one answer, store nothing | 0 · 1 |
| `metrics` | metric catalogue | 0 |
| `delete RUN_ID --yes` | delete a stored run | 0 · 1 without `--yes` |
| `rerun RUN_ID [--name]` | repeat a stored run with the same configuration | as `run` |
| `slices RUN_ID --by FIELD` | scores per value of a dataset metadata field | 0 · 1 unknown field |
| `labels-template RUN_ID --out F.csv [--force]` | CSV with a blank `human_pass` column for labelling | 0 · 1 file exists |
| `calibrate RUN_ID --labels F --metric M [--sweep] [--rescore]` | agreement of a metric with human labels (accuracy, kappa) | 0 · 1 nothing comparable |
| `doctor` | health checks (also in Settings) | 0 all ok · 1 a check failed |
| `backup [--out-dir]` | consistent copy of the run store | 0 |
| `restore BACKUP [--yes] [--force]` | replace the run store with a backup (safety copy first; refuses corrupt, newer-schema or active-run cases) | 0 · 1 |
| `prune [--keep-last N] [--older-than-days D] [--yes]` | delete old runs; lists them without `--yes` | 0 |
| `--version` | print the version | 0 |
| `tag RUN_ID [--add a,b] [--remove c]` | add or remove run tags | 0 · 1 invalid tag |
| `note RUN_ID TEXT` / `note RUN_ID --clear` | set or clear a run note | 0 · 1 |
| `list [--search WORD ...] [--tag T] [--status S]` | stored runs, filtered (every word must match) | 0 |
| `regress BASELINE CANDIDATE [--max-drop 0.02] [--min-pairs 10] [--max-error-increase 0.05] [--metrics a,b]` | regression gate | 0 ok · 3 regression · 4 not judged · 1 error |
| `tune-abstention [--dataset F ...] [--document F ...]` | choose `--min-evidence` on a dev half, report on a held-out half | 0 |
| `user add NAME [--role viewer\|editor\|admin] [--replace] [--password-stdin]` / `user set-role NAME --role R` / `user set-password NAME` / `user remove NAME [--force]` / `user list` | named web-app accounts and roles | 0 · 1 |
| `judge-noise RUN_ID [--repeats 3] [--metrics a,b] [--limit N] [--yes]` | re-score stored answers to measure judge jitter (makes API calls; `--yes` above 30 measurements) | 0 · 1 |

Errors are printed as `error: …` on stderr; tracebacks are not shown for expected failures.

## Python API

```python
from rag_workbench.config import load_settings
from rag_workbench.models import RunConfig
from rag_workbench.services import open_context
from rag_workbench.reporting import export_markdown

ctx = open_context(load_settings(), console_logging=False)   # settings + SQLite store
config = RunConfig(
    name="scripted-k3",
    dataset_path=str(ctx.settings.default_dataset),
    document_path=str(ctx.settings.default_document),
    k=3,
    metrics=["token_f1", "context_recall"],
)
run = ctx.runner().run(config, progress=lambda p: print(p.done, "/", p.total))
print(run.status, run.summary.metrics["context_recall"].mean)
print(export_markdown(run, ctx.store.get_case_results(run.id)))
```

| Object | Module | Use |
|---|---|---|
| `load_settings(env=None)` → `Settings` | `config` | read env/.env; raises `ConfigError` naming the bad variable |
| `RunConfig` | `models` | everything a run needs; validated (k 1–50, unique metrics, …) |
| `EvaluationRunner.prepare(config)` / `.execute(prepared, progress, cancel)` / `.run(...)` | `runner` | validate then execute; `cancel` is a `threading.Event` |
| `RunStore(path)` | `storage` | `list_runs`, `get_run`, `get_case_results`, `delete_run`, … |
| `build_metrics(names, settings)`, `METRIC_SPECS` | `metrics` | metric objects; `Metric.evaluate(MetricInput, threshold)` |
| `summarize_run`, `paired_comparison`, `bootstrap_ci` | `aggregate` | statistics over `CaseResult` lists |
| `export_run(run, results, fmt)`, `comparison_dataframe` | `reporting` | exports and tables |
| `load_bundle`, `import_bundle` | `archive` | run bundles |
| `validate_file`, `parse_dataset` | `datasets` | dataset validation report |
| `load_chunks` | `documents` | document → `Chunk` list |

### Data contracts (`models.py`)

`EvalCase`, `Chunk`, `RetrievedChunk`, `Generation`, `MetricResult` (`status` ok/skipped/error, `score` in [0, 1]
or None), `CaseResult`, `RunConfig`, `MetricSummary`, `RunSummary`, `RunRecord` (`status` running / completed /
partial / failed / cancelled / interrupted / imported). JSON exports and bundles serialise these models directly.

### Run bundle format

```json
{"format": "rag-workbench-run", "version": 1, "run": { RunRecord }, "cases": [ CaseResult, ... ]}
```

Validated against the models on import; duplicate case ids, wrong format or version, invalid JSON and files over
50 MB are rejected with `BundleError`.
