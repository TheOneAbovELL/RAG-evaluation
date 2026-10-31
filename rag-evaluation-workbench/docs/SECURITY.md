# Security overview

A summary for someone deciding whether and how to expose the workbench. The full threat model and review notes are in the project
book (Part XI and Part XIV to XV); what each control is and how it was tested is listed here.

## Assets and who can reach them

* **Secrets:** an API key (`OPENAI_API_KEY`, normally in the git-ignored, Docker-ignored `.env`), the optional shared password, and
  account password hashes (`users.json`).
* **Data:** datasets, documents, answers and scores in `runs.db`, exports and logs. Treat them as confidential if your documents are.
* **Reach:** by default the app listens on `localhost` only. Anything else needs a login (`python start.py --host ...` refuses without one).

## Controls (implemented and tested)

| Area | Control | Test |
|---|---|---|
| Secrets in memory/logs | keys and passwords held as `SecretStr`; log and traceback redaction (text and JSON formats); never rendered in the UI | `test_config.py`, `test_cli_services.py` |
| Secrets in the tree | `scripts/verify.py` scans for key-shaped strings and `.env` files | verify step 3 |
| Passwords | scrypt (n=2^14, r=8, p=1) with per-user salt; constant-time comparison; unknown users cost the same hashing work | `test_users.py` |
| Brute force | per-username lockout (5 failures per 60 s) plus a global limit; throttle state bounded in memory | `test_users.py`, `test_auth.py` |
| Access | optional shared password or named accounts; roles viewer/editor/admin; roles read on every page load; a removed user's session ends; the last admin is protected | `test_roles.py`, `test_accounts_admin.py` |
| Data separation | `RAGWB_RUN_VISIBILITY=own` hides other users' runs from non-admins (UI level) | `test_accounts_admin.py` |
| Transport | `--ssl-cert/--ssl-key` serve HTTPS | probed with a self-signed certificate (HTTPS answered, HTTP refused) |
| Input | dataset/document size and case limits, line-numbered validation errors, upload name sanitising, CSV formula neutralisation in exports and labelling sheets, HTML-escaped display of stored values | `test_datasets.py`, `test_archive_reporting.py`, `test_ui.py` |
| Telemetry | DeepEval and Streamlit usage statistics disabled | `doctor` check |
| Dependencies | locked (`uv.lock`); `pip-audit` over locked runtime requirements including the optional extra | `verify.py --audit` (no known vulnerabilities at the time) |
| Supply chain of data | run bundles are validated on import and summaries recomputed, never trusted | `test_archive_reporting.py` |

## Known gaps and honest limits

* **No TLS by default.** Without `--ssl-cert/--ssl-key` or a TLS proxy, credentials cross the network in clear text.
* **Roles and visibility are enforced in the application only.** Anyone with file access to the data directory can read `runs.db`
  and `users.json`; the file permission tightening on `users.json` is best effort (Windows ignores most mode bits). Disk encryption and OS
  permissions are the operator's job.
* **No password reset flow, no MFA, no SSO, no audit trail beyond the log file.** Sign-in events are logged; changes to runs are not.
* **Streamlit's session model.** Sessions live in server memory; they end on restart; a shared deployment is a single process.
* **Provider data flow.** With a provider, questions, retrieved text and answers are sent to that provider; offline mode sends nothing.
  Judge metrics send more (every answer and context) than generation alone.
* **Dependency audit is point-in-time**, against public advisory data on the day it ran.
* **Not verified:** the Docker image; behaviour behind a TLS proxy; penetration testing by a third party (none was done).

## A `.env` in the project folder

`.env` is the documented home of the provider key and settings; `load_settings` reads it automatically and the settings page, logs and
exports never show the value. Consequences to manage:

* It is **excluded from git, Docker builds and wheels**, but not from a zip, a file copy or a **cloud-sync client**. If the project
  folder is inside OneDrive, Dropbox or similar (this one is under OneDrive's Desktop), the file is uploaded to that service. Either
  move the folder out of the synced area, exclude `.env` from sync, or keep the key in a user environment variable instead and delete `.env`.
* `scripts/verify.py` allows a `.env` that is listed in `.gitignore` and `.dockerignore` and says so in its output; it still fails on any
  key-shaped string in any other file, and on a `.env` that is not ignored.
* The test suite sets `RAGWB_NO_DOTENV=1`, so a real key or setting in `.env` can never reach a test or its child processes.
* A key that has been pasted into a chat, a ticket or a log should be treated as exposed: rotate it at the provider (their console, with
  your account), then install the replacement with `uv run python scripts/set_api_key.py` (hidden prompt; `--check` tests it).

## Hardening checklist for a shared deployment

1. Use named accounts (`ragwb user add`), not the shared password; make one or two admins, the rest editors/viewers.
2. Serve over TLS (`--ssl-cert/--ssl-key` or a proxy) and keep the port off the public internet.
3. Set `RAGWB_RUN_VISIBILITY=own` if users should not see each other's runs.
4. Keep `data/` on an encrypted disk with owner-only permissions; back up with `ragwb backup`; test `ragwb restore`.
5. Put the API key in the service environment (or a `.env` that no sync or backup tool uploads), not in other files; rotate it if it was
   ever pasted anywhere.
6. Run `scripts/verify.py --audit` before every release and read `docs/KNOWN_LIMITATIONS.md`.
7. Review the log for repeated `sign-in failed` lines.
