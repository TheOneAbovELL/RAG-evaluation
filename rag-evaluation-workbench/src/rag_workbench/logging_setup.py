"""Logging configuration with secret redaction.

Logs go to the console and to a rotating file under ``<data_dir>/logs``. A filter masks the
configured API key and anything shaped like an OpenAI key (``sk-...``) in every record, as a second
line of defence; the code itself never logs credentials.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler

from .config import Settings

_KEY_PATTERN = re.compile(r"sk-[A-Za-z0-9_\-]{8,}")
_LOGGER_NAME = "rag_workbench"


class RedactingFormatter(logging.Formatter):
    """Redacts the fully formatted record, including exception tracebacks and stack info."""

    def __init__(self, fmt: str, redactor: RedactSecretsFilter):
        super().__init__(fmt)
        self.redactor = redactor

    def format(self, record: logging.LogRecord) -> str:
        return self.redactor.redact(super().format(record))


class RedactingJsonFormatter(logging.Formatter):
    """One JSON object per line (``ts``, ``level``, ``logger``, ``message``, optional ``exc``), redacted.

    Suited to log shippers and ``jq``. Redaction runs on the serialised text as well, so no field can leak a secret.
    """

    def __init__(self, redactor: RedactSecretsFilter):
        super().__init__()
        self.redactor = redactor

    def format(self, record: logging.LogRecord) -> str:
        payload = {"ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
                   "level": record.levelname, "logger": record.name, "message": record.getMessage()}
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return self.redactor.redact(json.dumps(payload, ensure_ascii=False))


class RedactSecretsFilter(logging.Filter):
    def __init__(self, secrets: list[str]):
        super().__init__()
        self.secrets = [s for s in secrets if s and len(s) >= 8]

    def redact(self, text: str) -> str:
        for secret in self.secrets:
            text = text.replace(secret, "***")
        return _KEY_PATTERN.sub("sk-***", text)

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = self.redact(message)
        if redacted != message:
            record.msg, record.args = redacted, None
        return True


def close_logging() -> None:
    """Close and detach the package's log handlers (releases the log file; needed before deleting a data directory
    on Windows, and lets :func:`configure_logging` reconfigure with new settings)."""
    logger = logging.getLogger(_LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    logger._rag_workbench_configured = False  # type: ignore[attr-defined]


def configure_logging(settings: Settings, *, console: bool = True) -> logging.Logger:
    """Idempotently configure the ``rag_workbench`` logger."""
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(settings.log_level)
    if getattr(logger, "_rag_workbench_configured", False):
        return logger
    redactor = RedactSecretsFilter(settings.secret_values())
    formatter: logging.Formatter
    if settings.log_format == "json":
        formatter = RedactingJsonFormatter(redactor)
    else:
        formatter = RedactingFormatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", redactor)
    handlers: list[logging.Handler] = []
    try:
        settings.log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(RotatingFileHandler(settings.log_path, maxBytes=2_000_000, backupCount=3, encoding="utf-8"))
    except OSError as exc:  # read-only location: keep console logging only
        logging.getLogger(__name__).warning("File logging disabled: %s", exc)
    if console:
        handlers.append(logging.StreamHandler())
    for handler in handlers:
        handler.setFormatter(formatter)
        handler.addFilter(redactor)
        logger.addHandler(handler)
    logger.propagate = False
    logger._rag_workbench_configured = True  # type: ignore[attr-defined]
    return logger
