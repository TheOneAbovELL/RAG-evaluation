# Environment variables

From `rag_workbench.config.ENV_VARS` and the `Settings` model.

| Variable | Setting | Default | Constraint |
|---|---|---|---|
| `OPENAI_API_KEY` | `openai_api_key` | `None` | — |
| `OPENAI_BASE_URL` | `openai_base_url` | `None` | — |
| `RAGWB_DATA_DIR` | `data_dir` | `data` | — |
| `RAGWB_DATASET` | `default_dataset` | `examples/datasets/honeybees.jsonl` | — |
| `RAGWB_DOCUMENT` | `default_document` | `examples/documents/honeybees.pdf` | — |
| `RAGWB_GENERATOR_MODEL` | `generator_model` | `gpt-4o` | — |
| `RAGWB_EMBEDDING_MODEL` | `embedding_model` | `text-embedding-3-large` | — |
| `RAGWB_JUDGE_MODEL` | `judge_model` | `gpt-4o` | — |
| `RAGWB_LOCAL_EMBEDDING_MODEL` | `local_embedding_model` | `BAAI/bge-small-en-v1.5` | — |
| `RAGWB_REQUEST_TIMEOUT_S` | `request_timeout_s` | `60.0` | Gt(gt=0), Le(le=600) |
| `RAGWB_CASE_TIMEOUT_S` | `case_timeout_s` | `600.0` | Gt(gt=0), Le(le=3600) |
| `RAGWB_MAX_RETRIES` | `max_retries` | `3` | Ge(ge=0), Le(le=10) |
| `RAGWB_RETRY_BASE_DELAY_S` | `retry_base_delay_s` | `1.0` | Ge(ge=0), Le(le=60) |
| `RAGWB_MAX_REQUESTS_PER_MINUTE` | `max_requests_per_minute` | `None` | Gt(gt=0), Le(le=6000) |
| `RAGWB_MAX_WORKERS` | `max_workers` | `4` | Ge(ge=1), Le(le=32) |
| `RAGWB_PRICE_INPUT_PER_MTOK` | `price_input_per_mtok` | `None` | Ge(ge=0) |
| `RAGWB_PRICE_OUTPUT_PER_MTOK` | `price_output_per_mtok` | `None` | Ge(ge=0) |
| `RAGWB_MAX_DATASET_BYTES` | `max_dataset_bytes` | `5000000` | Gt(gt=0) |
| `RAGWB_MAX_DOCUMENT_BYTES` | `max_document_bytes` | `25000000` | Gt(gt=0) |
| `RAGWB_MAX_CASES` | `max_cases` | `5000` | Gt(gt=0) |
| `RAGWB_MAX_FIELD_CHARS` | `max_field_chars` | `20000` | Gt(gt=0) |
| `RAGWB_LOG_LEVEL` | `log_level` | `INFO` | — |
| `RAGWB_LOG_FORMAT` | `log_format` | `text` | — |
| `RAGWB_APP_PASSWORD` | `app_password` | `None` | — |
| `RAGWB_RUN_VISIBILITY` | `run_visibility` | `shared` | — |
