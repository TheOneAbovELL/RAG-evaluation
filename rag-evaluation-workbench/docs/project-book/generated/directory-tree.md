# Directory tree

Runtime folders (`.venv/`, `data/`, caches) are omitted.

```
rag-evaluation-workbench/
├── .mypy_cache/
│   ├── 3.12/
│   │   ├── cache.0.db
│   │   ├── cache.1.db
│   │   ├── cache.10.db
│   │   ├── cache.11.db
│   │   ├── cache.12.db
│   │   ├── cache.13.db
│   │   ├── cache.14.db
│   │   ├── cache.15.db
│   │   ├── cache.2.db
│   │   ├── cache.3.db
│   │   ├── cache.4.db
│   │   ├── cache.5.db
│   │   ├── cache.6.db
│   │   ├── cache.7.db
│   │   ├── cache.8.db
│   │   └── cache.9.db
│   ├── .gitignore
│   └── CACHEDIR.TAG
├── .ruff_cache/
│   ├── 0.17.3/
│   │   ├── 12350172689393983174
│   │   ├── 12533282978854471601
│   │   ├── 13795396297412139559
│   │   ├── 14018751826410839746
│   │   ├── 14381248014947943083
│   │   ├── 15282512453272718803
│   │   ├── 3578763274885469515
│   │   ├── 4892629194590192896
│   │   ├── 536245276354066127
│   │   ├── 5434682907550506004
│   │   ├── 5723898431750845727
│   │   └── 6719932726367954467
│   ├── .gitignore
│   └── CACHEDIR.TAG
├── .streamlit/
│   └── config.toml
├── calibration/
│   ├── 20261028-035657-qwen-volcanoes-30-b-7d604e.json
│   ├── README.md
│   ├── volcanoes-labelling-sheet.csv
│   └── volcanoes-labels-by-claude.csv
├── docs/
│   ├── project-book/
│   │   ├── chapters/
│   │   │   ├── 00-front-matter.md
│   │   │   ├── 01-foundation.md
│   │   │   ├── 02-design-analysis.md
│   │   │   ├── 03-architecture.md
│   │   │   ├── 04-core-implementation.md
│   │   │   ├── 05-file-reference.md
│   │   │   ├── 06-evaluation-methodology.md
│   │   │   ├── 07-user-interface.md
│   │   │   ├── 08-setup-and-operation.md
│   │   │   ├── 09-testing-and-qa.md
│   │   │   ├── 10-development-history.md
│   │   │   ├── 11-security-reliability-limitations.md
│   │   │   ├── 12-reference-material.md
│   │   │   ├── 13-release-1-1.md
│   │   │   ├── 14-release-1-2.md
│   │   │   ├── 15-release-1-3.md
│   │   │   └── 16-release-1-4.md
│   │   ├── figures/
│   │   │   ├── architecture.svg
│   │   │   ├── data-flow.svg
│   │   │   ├── module-graph.svg
│   │   │   ├── run-lifecycle.svg
│   │   │   ├── sequence-agent.svg
│   │   │   └── sequence-run.svg
│   │   ├── tools/
│   │   │   ├── build_book.py
│   │   │   ├── capture_screenshots.py
│   │   │   ├── diagrams.py
│   │   │   ├── generate_reference.py
│   │   │   └── screenshot_pages.json
│   │   ├── PROJECT_BOOK.md
│   │   ├── RAG_Evaluation_Workbench_Project_Book.pdf
│   │   └── README.md
│   ├── user-guide/
│   │   ├── chapters/
│   │   │   ├── 00-front-matter.md
│   │   │   ├── 01-orientation.md
│   │   │   ├── 02-inputs.md
│   │   │   ├── 03-choosing-configuration.md
│   │   │   ├── 04-running-evaluations.md
│   │   │   ├── 05-reading-results.md
│   │   │   ├── 06-playbooks-quality.md
│   │   │   ├── 07-playbooks-operations.md
│   │   │   ├── 08-troubleshooting-faq.md
│   │   │   └── 09-reference-cards.md
│   │   ├── tools/
│   │   │   └── build_guide.py
│   │   ├── RAG_Evaluation_Workbench_Practitioners_Guide.pdf
│   │   └── USER_GUIDE.md
│   ├── API_REFERENCE.md
│   ├── ARCHITECTURE.md
│   ├── BUILD_AND_RUN.md
│   ├── KNOWN_LIMITATIONS.md
│   ├── LIVE_VERIFICATION.md
│   ├── OPERATIONS.md
│   ├── REQUIREMENTS_TRACEABILITY.md
│   ├── SECURITY.md
│   └── TESTING.md
├── examples/
│   ├── datasets/
│   │   ├── coffee.jsonl
│   │   ├── honeybees.jsonl
│   │   ├── honeybees_paraphrased.csv
│   │   ├── honeybees_unanswerable.jsonl
│   │   ├── lighthouses.jsonl
│   │   └── volcanoes.jsonl
│   └── documents/
│       ├── coffee.md
│       ├── coffee.pdf
│       ├── honeybees.md
│       ├── honeybees.pdf
│       ├── lighthouses.md
│       ├── lighthouses.pdf
│       ├── volcanoes.md
│       └── volcanoes.pdf
├── scripts/
│   ├── benchmark.py
│   ├── benchmark_documents.py
│   ├── live_smoke.py
│   ├── make_example_pdf.py
│   ├── seed_demo_runs.py
│   ├── set_api_key.py
│   ├── verify.py
│   └── wheel_check.py
├── src/
│   └── rag_workbench/
│       ├── metrics/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── judge.py
│       │   ├── lexical.py
│       │   └── semantic.py
│       ├── ui/
│       │   ├── views/
│       │   │   ├── __init__.py
│       │   │   ├── compare.py
│       │   │   ├── data.py
│       │   │   ├── new_run.py
│       │   │   ├── overview.py
│       │   │   ├── results.py
│       │   │   ├── settings.py
│       │   │   └── users.py
│       │   ├── __init__.py
│       │   ├── auth.py
│       │   ├── components.py
│       │   └── state.py
│       ├── __init__.py
│       ├── __main__.py
│       ├── abstention.py
│       ├── aggregate.py
│       ├── archive.py
│       ├── calibration.py
│       ├── cli.py
│       ├── config.py
│       ├── datasets.py
│       ├── demo.py
│       ├── documents.py
│       ├── errors.py
│       ├── history.py
│       ├── judge_noise.py
│       ├── logging_setup.py
│       ├── maintenance.py
│       ├── models.py
│       ├── pipeline.py
│       ├── prompts.py
│       ├── providers.py
│       ├── ratelimit.py
│       ├── regression.py
│       ├── reporting.py
│       ├── retrieval.py
│       ├── runner.py
│       ├── services.py
│       ├── storage.py
│       ├── text.py
│       └── users.py
├── tests/
│   ├── conftest.py
│   ├── test_abstention.py
│   ├── test_accounts_admin.py
│   ├── test_aggregate.py
│   ├── test_archive_reporting.py
│   ├── test_auth.py
│   ├── test_bm25_equivalence.py
│   ├── test_calibration.py
│   ├── test_calibration_sweep.py
│   ├── test_cli_polish.py
│   ├── test_cli_services.py
│   ├── test_config.py
│   ├── test_datasets.py
│   ├── test_documents.py
│   ├── test_dotenv_switch.py
│   ├── test_evaluation_options.py
│   ├── test_example_corpus.py
│   ├── test_history.py
│   ├── test_judge_noise.py
│   ├── test_live.py
│   ├── test_local_retrieval.py
│   ├── test_maintenance.py
│   ├── test_metrics.py
│   ├── test_packaging.py
│   ├── test_providers_pipeline.py
│   ├── test_ratelimit.py
│   ├── test_regression.py
│   ├── test_restore_concurrency.py
│   ├── test_retrieval.py
│   ├── test_retry_hints.py
│   ├── test_roles.py
│   ├── test_runner.py
│   ├── test_semantic.py
│   ├── test_set_api_key.py
│   ├── test_start.py
│   ├── test_storage.py
│   ├── test_text.py
│   ├── test_ui.py
│   └── test_users.py
├── .coverage
├── .dockerignore
├── .env
├── .env.example
├── .gitignore
├── .python-version
├── CHANGELOG.md
├── Dockerfile
├── pyproject.toml
├── README.md
├── start.py
├── streamlit_app.py
└── uv.lock
```
