"""Named user accounts for the web app (optional).

A step up from the single shared password: each person has a username and their own password, so access can be
granted and revoked per person and a sign-in is attributable in the log and on the runs they start. It is still a
small local mechanism, not an identity platform: there is no e-mail password reset (an admin sets a new one), roles are
coarse (viewer, editor, admin), and run visibility is shared unless ``RAGWB_RUN_VISIBILITY=own`` hides other users'
runs from non-admins (at application level only).

Each account has a role: ``viewer`` (read-only), ``editor`` (also start runs and edit tags and notes) or ``admin``
(also delete runs). Accounts created before roles existed have no stored role and count as ``editor``.

Storage is one JSON file (``<data dir>/users.json``). Passwords are never stored: each entry holds a random salt and a
scrypt hash (``n=2**14, r=8, p=1``). Verification is constant-time, and an unknown username costs the same hashing work
as a known one, so response time does not reveal which usernames exist. The file is written atomically and, where the
platform supports it, readable by its owner only.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import hmac
import json
import os
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path

SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1
ROLES = ("viewer", "editor", "admin")
DEFAULT_ROLE = "editor"
MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 200
USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,31}$")
_DUMMY_SALT = b"\x00" * 16


class UserError(ValueError):
    """The username, password or users file is not acceptable."""


def normalise_username(name: str) -> str:
    candidate = (name or "").strip().lower()
    if not USERNAME_RE.match(candidate):
        raise UserError("Usernames are 1-32 characters: lowercase letters, digits, '.', '_' or '-', starting with a "
                        "letter or digit")
    return candidate


def _hash(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)


class UserStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    # ------------------------------------------------------------------ reading
    def _load(self) -> dict[str, dict]:
        if not self.path.is_file():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            users = data["users"]
            if not isinstance(users, dict):
                raise TypeError("'users' must be an object")
            return users
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise UserError(f"The users file {self.path.name} is unreadable or malformed ({exc}); "
                            "fix or delete it to continue") from exc

    def names(self) -> list[str]:
        return sorted(self._load())

    def has_users(self) -> bool:
        try:
            return bool(self._load())
        except UserError:
            return True  # a damaged file must lock the app, not silently open it

    # ------------------------------------------------------------------ writing
    def _save(self, users: dict[str, dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": 1, "users": users}, indent=2), encoding="utf-8")
        with contextlib.suppress(OSError):
            os.chmod(tmp, 0o600)  # best effort; Windows ignores most of the mode bits
        os.replace(tmp, self.path)

    def add(self, name: str, password: str, *, replace: bool = False, role: str = DEFAULT_ROLE) -> str:
        username = normalise_username(name)
        if role not in ROLES:
            raise UserError(f"Unknown role {role!r}; choose one of: {', '.join(ROLES)}")
        if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
            raise UserError(f"Passwords must be {MIN_PASSWORD_LENGTH}-{MAX_PASSWORD_LENGTH} characters")
        users = self._load()
        if username in users and not replace:
            raise UserError(f"User {username!r} already exists (use --replace to change the password)")
        salt = secrets.token_bytes(16)
        users[username] = {"salt": base64.b64encode(salt).decode(),
                           "hash": base64.b64encode(_hash(password, salt)).decode(),
                           "role": role, "created": datetime.now(UTC).isoformat(timespec="seconds")}
        self._save(users)
        return username

    def role_of(self, name: str) -> str | None:
        """The user's role, or ``None`` if there is no such user (a removed user must lose access at once)."""
        try:
            entry = self._load().get(normalise_username(name))
        except UserError:
            return None
        if entry is None:
            return None
        role = entry.get("role", DEFAULT_ROLE)
        return role if role in ROLES else "viewer"  # an unrecognised role gets the least access, not the most

    def entries(self) -> list[dict[str, str]]:
        """``[{"user", "role", "created"}]`` sorted by name, without any secret material."""
        users = self._load()
        return [{"user": n, "role": users[n].get("role", DEFAULT_ROLE), "created": str(users[n].get("created", ""))}
                for n in sorted(users)]

    def admins(self) -> list[str]:
        users = self._load()
        return sorted(n for n, e in users.items() if e.get("role", DEFAULT_ROLE) == "admin")

    def _guard_last_admin(self, users: dict[str, dict], username: str, action: str, force: bool) -> None:
        """Refuse to remove or demote the only admin while other accounts remain: nobody could manage accounts then."""
        if force or len(users) < 2:
            return
        is_admin = users[username].get("role", DEFAULT_ROLE) == "admin"
        other_admins = [n for n, e in users.items() if n != username and e.get("role", DEFAULT_ROLE) == "admin"]
        if is_admin and not other_admins:
            raise UserError(f"{username!r} is the last admin; {action} would leave nobody able to manage accounts "
                            "(make another user an admin first, or use --force)")

    def set_password(self, name: str, new_password: str, *, current_password: str | None = None) -> bool:
        """Change a user's password, keeping role and creation date. ``current_password`` (when given) must be right."""
        username = normalise_username(name)
        if not MIN_PASSWORD_LENGTH <= len(new_password) <= MAX_PASSWORD_LENGTH:
            raise UserError(f"Passwords must be {MIN_PASSWORD_LENGTH}-{MAX_PASSWORD_LENGTH} characters")
        if current_password is not None and self.verify(username, current_password) is None:
            raise UserError("The current password is not correct")
        users = self._load()
        if username not in users:
            return False
        salt = secrets.token_bytes(16)
        users[username]["salt"] = base64.b64encode(salt).decode()
        users[username]["hash"] = base64.b64encode(_hash(new_password, salt)).decode()
        self._save(users)
        return True

    def set_role(self, name: str, role: str, *, force: bool = False) -> bool:
        if role not in ROLES:
            raise UserError(f"Unknown role {role!r}; choose one of: {', '.join(ROLES)}")
        username = normalise_username(name)
        users = self._load()
        if username not in users:
            return False
        if role != "admin":
            self._guard_last_admin(users, username, "demoting them", force)
        users[username]["role"] = role
        self._save(users)
        return True

    def remove(self, name: str, *, force: bool = False) -> bool:
        username = normalise_username(name)
        users = self._load()
        if username not in users:
            return False
        self._guard_last_admin(users, username, "removing them", force)
        del users[username]
        if users:
            self._save(users)
        else:
            self.path.unlink(missing_ok=True)  # no accounts left: no file, so nothing looks half-configured
        return True

    # ------------------------------------------------------------------ checking
    def verify(self, name: str, password: str) -> str | None:
        """The normalised username if the credentials are right, else ``None``. Same cost either way."""
        try:
            username = normalise_username(name)
        except UserError:
            username = ""
        try:
            entry = self._load().get(username)
        except UserError:
            return None
        try:
            salt = base64.b64decode(entry["salt"]) if entry else _DUMMY_SALT
            expected = base64.b64decode(entry["hash"]) if entry else b"\x00" * 32
        except (KeyError, ValueError):
            return None
        if len(password) > MAX_PASSWORD_LENGTH:
            return None
        ok = hmac.compare_digest(_hash(password, salt), expected)
        return username if ok and entry else None
