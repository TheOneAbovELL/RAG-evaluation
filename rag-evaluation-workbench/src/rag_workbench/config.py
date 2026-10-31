"""Centralised configuration.

Settings are read from environment variables (optionally loaded from a ``.env`` file in the
project root). Every variable uses the ``RAGWB_`` prefix except ``OPENAI_API_KEY``, which keeps
the name the OpenAI SDK and DeepEval already expect.

The API key is held as a :class:`pydantic.SecretStr`; its value is never included in ``repr``,
logs, persisted run configurations or the UI.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field, SecretStr, ValidationError, field_validator


def _find_project_root() -> Path:
    """The folder that holds ``data/``, ``.env`` and ``examples/``.

    1. ``RAGWB_HOME`` when set;
    2. the project checkout this file lives in (``src/rag_workbench/config.py`` -> two levels up, recognised by
       its ``pyproject.toml``; this is the case after ``uv sync`` and ``python start.py``);
    3. otherwise the package was installed as a wheel, and the current directory is used, so data is never
       written into ``site-packages``.
    """
    home = os.environ.get("RAGWB_HOME", "").strip()
    if home:
        return Path(home).expanduser().resolve()
    checkout = Path(__file__).resolve().parents[2]
    return checkout if (checkout / "pyproject.toml").is_file() else Path.cwd().resolve()


PROJECT_ROOT = _find_project_root()
_PACKAGED_EXAMPLES = Path(__file__).resolve().parent / "_examples"  # bundled into the wheel at build time
EXAMPLES_DIR = (PROJECT_ROOT / "examples" if (PROJECT_ROOT / "examples").is_dir() or not _PACKAGED_EXAMPLES.is_dir()
                else _PACKAGED_EXAMPLES)

ProviderName = Literal["offline", "openai"]
PipelineMode = Literal["rag", "agent"]
# embedding/hybrid use an OpenAI-compatible embeddings API; local/hybrid-local use a local model (no key, no network
# after the one-time model download; needs the optional fastembed package).
RetrieverName = Literal["bm25", "embedding", "hybrid", "local", "hybrid-local"]
LogFormat = Literal["text", "json"]


class ConfigError(ValueError):
    """Raised when configuration values are missing or invalid."""


class Settings(BaseModel):
    """Runtime settings. Construct with :func:`load_settings` rather than directly."""

    model_config = {"frozen": True}

    project_root: Path = PROJECT_ROOT
    data_dir: Path = PROJECT_ROOT / "data"
    default_dataset: Path = EXAMPLES_DIR / "datasets" / "honeybees.jsonl"
    default_document: Path = EXAMPLES_DIR / "documents" / "honeybees.pdf"

    openai_api_key: SecretStr | None = None
    # Optional access password for the web app (see ui.auth). Required when the app is exposed beyond localhost.
    app_password: SecretStr | None = None
    openai_base_url: str | None = None
    generator_model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-large"
    judge_model: str = "gpt-4o"
    # Local sentence-embedding model for the optional semantic metrics (needs the fastembed package).
    local_embedding_model: str = "BAAI/bge-small-en-v1.5"

    request_timeout_s: float = Field(default=60.0, gt=0, le=600)
    case_timeout_s: float = Field(default=600.0, gt=0, le=3600)
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_base_delay_s: float = Field(default=1.0, ge=0, le=60)
    # Evenly space model operations (answers, judge measurements) to stay under a provider's request quota.
    max_requests_per_minute: float | None = Field(default=None, gt=0, le=6000)
    max_workers: int = Field(default=4, ge=1, le=32)

    # Optional pricing, in USD per one million tokens. Left unset by default because prices
    # change; when unset, cost is reported as unknown instead of guessed.
    price_input_per_mtok: float | None = Field(default=None, ge=0)
    price_output_per_mtok: float | None = Field(default=None, ge=0)

    max_dataset_bytes: int = Field(default=5_000_000, gt=0)
    max_document_bytes: int = Field(default=25_000_000, gt=0)
    max_cases: int = Field(default=5_000, gt=0)
    max_field_chars: int = Field(default=20_000, gt=0)

    log_level: str = "INFO"
    # shared: every signed-in user sees every run. own: non-admins see only runs they started plus runs with no owner.
    run_visibility: Literal["shared", "own"] = "shared"
    log_format: LogFormat = "text"

    @field_validator("log_level")
    @classmethod
    def _valid_level(cls, value: str) -> str:
        value = value.upper()
        if value not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(f"unknown log level {value!r}")
        return value

    @property
    def db_path(self) -> Path:
        return self.data_dir / "runs.db"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def local_model_dir(self) -> Path:
        return self.data_dir / "models"

    @property
    def users_path(self) -> Path:
        return self.data_dir / "users.json"

    @property
    def has_users(self) -> bool:
        """True when named accounts exist (a damaged users file counts: it must lock the app, not open it)."""
        from .users import UserStore

        return UserStore(self.users_path).has_users()

    @property
    def login_required(self) -> bool:
        return self.has_users or self.has_app_password

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def exports_dir(self) -> Path:
        return self.data_dir / "exports"

    @property
    def log_path(self) -> Path:
        return self.data_dir / "logs" / "rag_workbench.log"

    @property
    def has_openai_key(self) -> bool:
        return bool(self.openai_api_key and self.openai_api_key.get_secret_value().strip())

    @property
    def has_app_password(self) -> bool:
        return bool(self.app_password and self.app_password.get_secret_value())

    def secret_values(self) -> list[str]:
        """Every configured secret value, for log redaction."""
        values = [self.openai_api_key, self.app_password]
        return [v.get_secret_value() for v in values if v is not None and v.get_secret_value()]

    def require_openai_key(self) -> str:
        """The API key's value, for handing to a client. Raises :class:`ConfigError` if none is configured."""
        if not self.has_openai_key or self.openai_api_key is None:
            raise ConfigError("OPENAI_API_KEY is not set. Add it to .env (see .env.example).")
        return self.openai_api_key.get_secret_value()

    def public_dict(self) -> dict:
        """Settings safe to display or persist: secrets replaced by a presence flag."""
        data = self.model_dump(mode="json", exclude={"openai_api_key", "app_password"})
        data["openai_api_key_configured"] = self.has_openai_key
        data["app_password_configured"] = self.has_app_password
        data["user_accounts_configured"] = self.has_users
        return data


# Environment variable → Settings field. Kept explicit so the documentation can list them.
ENV_VARS: dict[str, str] = {
    "OPENAI_API_KEY": "openai_api_key",
    "OPENAI_BASE_URL": "openai_base_url",
    "RAGWB_DATA_DIR": "data_dir",
    "RAGWB_DATASET": "default_dataset",
    "RAGWB_DOCUMENT": "default_document",
    "RAGWB_GENERATOR_MODEL": "generator_model",
    "RAGWB_EMBEDDING_MODEL": "embedding_model",
    "RAGWB_JUDGE_MODEL": "judge_model",
    "RAGWB_LOCAL_EMBEDDING_MODEL": "local_embedding_model",
    "RAGWB_REQUEST_TIMEOUT_S": "request_timeout_s",
    "RAGWB_CASE_TIMEOUT_S": "case_timeout_s",
    "RAGWB_MAX_RETRIES": "max_retries",
    "RAGWB_RETRY_BASE_DELAY_S": "retry_base_delay_s",
    "RAGWB_MAX_REQUESTS_PER_MINUTE": "max_requests_per_minute",
    "RAGWB_MAX_WORKERS": "max_workers",
    "RAGWB_PRICE_INPUT_PER_MTOK": "price_input_per_mtok",
    "RAGWB_PRICE_OUTPUT_PER_MTOK": "price_output_per_mtok",
    "RAGWB_MAX_DATASET_BYTES": "max_dataset_bytes",
    "RAGWB_MAX_DOCUMENT_BYTES": "max_document_bytes",
    "RAGWB_MAX_CASES": "max_cases",
    "RAGWB_MAX_FIELD_CHARS": "max_field_chars",
    "RAGWB_LOG_LEVEL": "log_level",
    "RAGWB_LOG_FORMAT": "log_format",
    "RAGWB_APP_PASSWORD": "app_password",
    "RAGWB_RUN_VISIBILITY": "run_visibility",
}

_PATH_FIELDS = {"data_dir", "default_dataset", "default_document"}


def load_settings(env: dict[str, str] | None = None, *, dotenv: bool = True) -> Settings:
    """Build :class:`Settings` from ``env`` (defaults to ``os.environ``).

    Relative paths are resolved against the project root, so behaviour does not depend on the
    current working directory. Blank values are treated as unset.
    """
    if env is None:
        # RAGWB_NO_DOTENV=1 skips the project's .env (used by the test suite so a real key or setting in .env can never
        # reach a test, including child processes that inherit the environment).
        if dotenv and os.environ.get("RAGWB_NO_DOTENV") != "1":
            load_dotenv(PROJECT_ROOT / ".env", override=False)
        env = dict(os.environ)

    values: dict[str, Any] = {}
    for var, field in ENV_VARS.items():
        raw = env.get(var)
        if raw is None or not str(raw).strip():
            continue
        raw = str(raw).strip()
        if field in _PATH_FIELDS:
            path = Path(raw).expanduser()
            values[field] = path if path.is_absolute() else PROJECT_ROOT / path
        else:
            values[field] = raw
    try:
        return Settings.model_validate(values)
    except ValidationError as exc:
        problems = "; ".join(
            f"{_env_name(err['loc'][0])}: {err['msg']}" for err in exc.errors()
        )
        raise ConfigError(f"Invalid configuration: {problems}") from None


def _env_name(field: object) -> str:
    for var, name in ENV_VARS.items():
        if name == field:
            return var
    return str(field)
