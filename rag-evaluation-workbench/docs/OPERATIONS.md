# Operations runbook

For whoever runs the workbench for others: install, configure, back up, restore, upgrade, watch, and recover. Everything here
uses commands that exist in this release; where a step has a limit, it says so.

## 1. Installing and starting

| Goal | Command |
|---|---|
| Everything (environment, first-launch examples, app) | `python start.py` |
| Shared on a network, with a login and TLS | `python start.py --host 0.0.0.0 --ssl-cert cert.pem --ssl-key key.pem` (refuses to start without a login) |
| Command-line tool only, from a wheel | `uv build --wheel`, then `uv pip install dist/*.whl`; `scripts/wheel_check.py` proves a clean install works |
| Container (web app) | `docker build -t rag-workbench .` (never built in the development environment: verify it first) |

Data lives in `<data dir>` (`data/` beside the project, or `RAGWB_DATA_DIR`, or `RAGWB_HOME`/`data` for a wheel install):
`runs.db` (the run store), `users.json` (accounts), `uploads/`, `exports/`, `logs/`, `backups/`, `models/` (downloaded embedding model).
On Windows keep the path short: the model cache nests folders and can exceed the 260-character limit.

## 2. Configuration that matters in production

| Setting | Why |
|---|---|
| `RAGWB_APP_PASSWORD` or `ragwb user add` | any non-local listener needs a login; accounts take precedence |
| `RAGWB_RUN_VISIBILITY=own` | with accounts, non-admins see only their own runs (plus runs with no owner) |
| `RAGWB_MAX_REQUESTS_PER_MINUTE` | stay under a provider's quota; one operation is one answer or one judge measurement |
| `RAGWB_MAX_RETRIES`, `RAGWB_RETRY_BASE_DELAY_S`, `RAGWB_REQUEST_TIMEOUT_S`, `RAGWB_CASE_TIMEOUT_S` | retry budget and time limits (defaults 3, 1 s, 60 s, 600 s) |
| `RAGWB_LOG_FORMAT=json` | one JSON object per line for a log collector; secrets are redacted in both formats |
| `RAGWB_MAX_CASES`, `RAGWB_MAX_DATASET_BYTES`, `RAGWB_MAX_DOCUMENT_BYTES` | input ceilings (defaults 5,000 cases, 5 MB, 25 MB) |

Keep API keys in the environment or an untracked `.env` (git- and Docker-ignored; see `docs/SECURITY.md` on cloud-sync folders). The secret scan in
`scripts/verify.py` fails on key-shaped strings anywhere except `.env`, and on a `.env` that is not ignored. `RAGWB_NO_DOTENV=1` makes the
loader skip `.env` (the test suite uses it).

## 3. Health and monitoring

* `ragwb doctor` (also Settings → Health checks): Python, packages, data directory and free disk, run-store integrity and stale runs,
  default data, key presence, telemetry, network exposure. Exit code 1 when a check fails: suitable for a scheduler.
* `ragwb list --status running` and the heartbeat: a `running` run with no case committed for 15 minutes is marked `interrupted` at the
  next start.
* Logs: `<data dir>/logs/rag_workbench.log` (rotating). Sign-ins, failures, throttling, password changes, retries and run
  lifecycle are logged; passwords and keys are not.
* The web server's own health endpoint: `/_stcore/health` returns `ok`.

## 4. Backup and restore

```bash
ragwb backup                              # consistent snapshot into <data dir>/backups, verified with integrity_check
ragwb restore <backup.db> --yes           # replaces the run store; writes pre-restore-<name>.db first
```

* A backup uses SQLite's online backup API, so it is safe while the app is running. It covers `runs.db` only: copy `users.json`
  separately (it is small), and never copy `.env` into a backup location you do not control.
* Restore refuses a corrupt backup, one from a newer schema, or while a run is recently active (override with `--force`), and
  reports a store held open by another process instead of corrupting it: **stop the web app first**. The safety copy makes a
  restore reversible: restoring the `pre-restore-*` file undoes it.
* Test a restore on a copy of the data directory before you need it.

## 5. Upgrades and rollback

1. `ragwb backup`, and keep the file.
2. Stop the app, replace the code, run `uv sync` (or `python start.py --setup-only`).
3. Start; the store migrates in place (schema 1 to 3 so far; migrations only add columns). `ragwb doctor` should report schema v3.
4. Rollback: stop, put the old code back, `ragwb restore` the backup from step 1 (an older version refuses a newer schema by
   design, so a restore is required, not optional).

## 6. Access management

`ragwb user add|remove|set-role|set-password|list`, or Accounts in the web app (admins). Roles: viewer, editor, admin. The last admin
cannot be removed or demoted without `--force`. A removed user's open session ends on their next page load; a role change applies on
the next page load. There is no self-service password reset: an admin sets a new password.

## 7. Capacity (measured, offline path, one laptop; see `scripts/benchmark.py`, `scripts/benchmark_documents.py`)

* 5,000 cases: about 47 s (about 100 cases/s, flat from 200 to 5,000 cases), 54 MB peak Python memory, 21 MB database; reading all
  results back takes 0.3 s and the CSV export 0.15 s.
* Documents: 5,000 chunks index in about 0.3 s and answer a query in about 3 ms (p95 under 4 ms); a 200-page PDF (1,600 chunks) loads in
  0.2 s and answers in under 1 ms.
* More workers help only a little offline (4 workers: about 115 versus 100 cases/s at 1,000 cases); they matter when cases wait on a provider.
* These were re-measured in release 1.4 after finding that the first benchmarks ran under `tracemalloc`, which inflated times about
  2x (cases) to 10x (queries); the scripts now time without a tracer and measure memory in a separate pass.
* With a provider, throughput is set by its quotas, not by this tool: free tiers cap tokens per minute and per day (see
  `docs/LIVE_VERIFICATION.md`).

## 8. Incident playbook

| Symptom | Likely cause | Action |
|---|---|---|
| Run stays `running` after a crash | process died | wait 15 minutes or restart: it becomes `interrupted`; `ragwb rerun <id>` repeats it |
| Many cases fail with rate-limit errors | provider quota | set `RAGWB_MAX_REQUESTS_PER_MINUTE`; lower `--workers`; check the provider's daily/minute token budgets |
| Case errors "Connection error" | network drop | retries handle short drops; re-run the failed run with `ragwb rerun` |
| "Cannot open run store" / integrity failure | disk or sync-tool corruption | `ragwb restore` the latest backup; do not keep `data/` in a folder a sync tool rewrites while the app runs |
| Locked out (no admin) | last admin removed with `--force`, or users.json damaged | stop the app; `ragwb user add NAME --role admin`, or delete `users.json` to fall back to no accounts (then set `RAGWB_APP_PASSWORD` before exposing the host) |
| An API key was exposed | pasted in chat, logs, a commit | rotate it at the provider immediately (their console), then `uv run python scripts/set_api_key.py` to install the new one; check `.env`, shell history, sync clients and backups |
| Disk filling | many runs, backups, exports | `ragwb prune --keep-last 20 --yes`; delete old `backups/` and `exports/` |

## 9. Release checklist

`uv run python scripts/verify.py --audit` (environment, lockfile, secrets, ruff, mypy, tests with coverage, end-to-end CLI, dependency
audit), `uv run python scripts/wheel_check.py` (clean install), `scripts/benchmark.py` if performance-relevant code changed, book rebuild
(`docs/project-book/tools/build_book.py`), and a read of `docs/KNOWN_LIMITATIONS.md` so the limits you ship are the limits you state.
