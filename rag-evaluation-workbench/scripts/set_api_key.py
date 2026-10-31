"""Replace (or remove) the provider API key in the project's ``.env`` without the key ever appearing on screen or in a log.

    uv run python scripts/set_api_key.py              # prompts for the new key (hidden input)
    uv run python scripts/set_api_key.py --remove     # blanks the key (offline mode again)
    uv run python scripts/set_api_key.py --check      # after saving, send ONE tiny request to the configured endpoint

Use it after rotating a key in the provider's console (rotating is done there, with your account: this script cannot do it).

* Only the ``OPENAI_API_KEY`` line is changed; every other line (and comment) is kept as it is. A missing ``.env`` is created
  from ``.env.example``.
* The key is read with ``getpass`` (no echo), or from standard input with ``--stdin`` (for password managers), and is never printed;
  the script reports only its length. The file is written to a temporary file and moved into place, so an interruption cannot
  leave a half-written ``.env``.
* ``--check`` makes one authenticated ``GET <OPENAI_BASE_URL>/models`` request and prints only the HTTP status. It is the only
  network use of this script, and only with that flag.
"""

from __future__ import annotations

import argparse
import contextlib
import getpass
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
EXAMPLE = ROOT / ".env.example"
KEY_LINE = re.compile(r"^\s*OPENAI_API_KEY\s*=")
MIN_LENGTH = 16


def validate_key(key: str) -> str:
    """The stripped key, or raises ``ValueError`` with a message that does not contain the key."""
    key = key.strip()
    if len(key) < MIN_LENGTH:
        raise ValueError(f"that does not look like an API key (shorter than {MIN_LENGTH} characters)")
    if re.search(r"\s", key) or any(c in key for c in "\"'#"):
        raise ValueError("an API key contains no spaces, quotes or '#': check what was pasted")
    return key


def update_env_text(text: str, key: str) -> str:
    """``text`` with the ``OPENAI_API_KEY`` line set to ``key`` (added if there is none); all other lines untouched."""
    lines = text.splitlines()
    replaced = False
    out = []
    for line in lines:
        if KEY_LINE.match(line) and not replaced:
            out.append(f"OPENAI_API_KEY={key}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"OPENAI_API_KEY={key}")
    return "\n".join(out) + "\n"


def write_env(path: Path, key: str, example: Path = EXAMPLE) -> None:
    if path.is_file():
        text = path.read_text(encoding="utf-8")
    elif example.is_file():
        text = example.read_text(encoding="utf-8")
    else:
        text = ""
    new_text = update_env_text(text, key)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(new_text, encoding="utf-8")
    with contextlib.suppress(OSError):
        os.chmod(tmp, 0o600)  # best effort; Windows ignores most mode bits
    os.replace(tmp, path)


def read_setting(path: Path, name: str) -> str | None:
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(rf"^\s*{re.escape(name)}\s*=\s*(.*?)\s*$", line)
        if match and not line.lstrip().startswith("#"):
            return match.group(1).strip("\"'")
    return None


def check_key(path: Path = ENV_FILE) -> tuple[int | None, str]:
    """One authenticated request to ``<base url>/models``; returns ``(status, message)`` and never the key."""
    key = read_setting(path, "OPENAI_API_KEY")
    base = read_setting(path, "OPENAI_BASE_URL") or "https://api.openai.com/v1"
    if not key:
        return None, "no key is set in .env"
    request = urllib.request.Request(base.rstrip("/") + "/models", headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, "accepted"
    except urllib.error.HTTPError as exc:
        return exc.code, "rejected" if exc.code in (401, 403) else "provider error"
    except (urllib.error.URLError, OSError) as exc:
        return None, f"could not reach the endpoint ({type(exc).__name__})"


def main(argv: list[str] | None = None, env_file: Path = ENV_FILE) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--remove", action="store_true", help="blank the key instead of setting one")
    parser.add_argument("--stdin", action="store_true", help="read the key from standard input (first line)")
    parser.add_argument("--check", action="store_true", help="after saving, send one request to test the key (network)")
    args = parser.parse_args(argv)

    if args.remove:
        write_env(env_file, "")
        print("The API key was removed from .env (offline mode).")
        return 0
    try:
        raw = sys.stdin.readline() if args.stdin else getpass.getpass("New API key (input hidden): ")
        key = validate_key(raw)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    write_env(env_file, key)
    print(f".env updated: OPENAI_API_KEY set ({len(key)} characters; not displayed).")
    if args.check:
        status, message = check_key(env_file)
        print(f"check: {message}" + (f" (HTTP {status})" if status else ""))
        return 0 if status == 200 else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
