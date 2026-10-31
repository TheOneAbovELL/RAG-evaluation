# Part XVI — Release 1.4: recovery, account management, calibration sweeps, an indexed BM25 and a clean install

Release 1.3 ended with a list of what no further work could close without something the project did not have (Part XV §167).
Release 1.4 (version `1.4.0`, `src/rag_workbench/__init__.py:13`) starts from that list and asks a narrower question: what on
it, and what around it, can be built and *verified* without a human labeller, an OpenAI key or Docker? The answer is a
release of unglamorous but consequential work: a way to restore the run store, an admin page for accounts, a safe way to
choose a metric's pass threshold, an inverted index for BM25, a wheel that installs into an empty environment, an accessibility
audit with a real tool, a live run of the one pipeline that had only ever run against a fake, and two documents (an operations
runbook and a security overview) for whoever runs the workbench for other people. This Part is organised around what each
piece does, how it was checked, what that check found, and, as plainly as possible, what remains unchecked. Every number in it
comes from `docs/LIVE_VERIFICATION.md`, `docs/TESTING.md`, `CHANGELOG.md`, a file that is cited, or a command run for this
Part whose output is shown or summarised here; nothing is projected or estimated.

**What did not change.** Default behaviour is the same. The five example runs (86 cases) score identically under 1.0.0 and
1.4.0 (§175.4), the default retriever is still BM25, the default provider is still `offline`, no variable is required, no
scoring formula or pass threshold changed, and the storage schema is still 3 (`src/rag_workbench/storage.py:26`). Everything
below is additive, with three exceptions that a user can notice: a new `restore` command and a longer `user` command
(the CLI now has **24 commands**, §179.1); a seventh page, *Accounts*, in the sidebar of an admin; and wheel installs
(not checkouts) now find the bundled example data (§176.2).

## 170. Motivation: what "complete" means when three things are missing

### 170.1 The inventory

Part XV §167 listed ten open items. Release 1.4 went through them one by one, and the honest summary is that it closed one, closed half of a
second, narrowed two more and left six exactly where they were.

| # | Open item after 1.3 | State after 1.4 | Where |
|---|---|---|---|
| 1 | OpenAI itself | **Open.** No key; nothing was sent to OpenAI. | §178.2 |
| 2 | The tool-calling agent pipeline, live | **Closed for the path:** 3 of 3 cases, context captured from the agent's tool calls. Not a quality measurement. | §176.3 |
| 3 | API embeddings and hybrid with API embeddings | **Open.** The provider used has no embedding models. | §178.2 |
| 4 | Judge-versus-human agreement | **Open.** The sheet still waits for a person. New: the tooling to choose a threshold from labels (`--sweep`), exercised on AI-written labels. | §174 |
| 5 | The semantic metrics' thresholds | **Narrowed.** Swept against the AI-written labels: 0.55-0.65 fits better than the 0.70 default. Default **not** changed. | §174.4 |
| 6 | Judge noise beyond one measurement | **Open.** A full four-judge run (run 17) was attempted and was cut short by a token cap. | §176.4, §178.2 |
| 7 | Docker image; a true wheel install | **Wheel closed** (CLI only, 10 of 10 checks); **Docker open**. | §176.1 |
| 8 | Accessibility beyond one keyboard walk | **Narrowed.** axe-core on seven page views, two more pages walked by keyboard; no screen reader. | §177 |
| 9 | Judge cost never compared with an invoice | **Open.** | §178.2 |
| 10 | TLS under a real certificate | **Open.** | §178.2 |

Around that list, release 1.3 had also left four statements of the form "this does not exist": there was no way to restore a
backup (Part XIII §143.2 had made it deliberately manual), no screen for accounts (Part XV §165.5), no way for a user to change
their own password, and every signed-in user saw every run. All four are now features (§171, §173); the limits that remain on
each are stated where the feature is described.

### 170.2 The rule for incomplete work

A project can be "finished" in two ways. One is to stop when the list runs out of items. The other is to stop when the list
runs out of items *that can be done with what is at hand*, and to write down, by name, the ones that cannot. This release takes
the second view, and the reason is concrete: three resources were unavailable (a person to label cases, a key for OpenAI itself,
a Docker engine), and each one blocks a specific, nameable claim. So the work was arranged to avoid pretending in either
direction: build and verify everything that does not need them, and keep the blocked claims out of every document, including
this one. Where a check *substitutes* for a blocked one (labels written by an AI rater standing in for a human's; Groq standing
in for OpenAI), the substitution is named every time it is used, and its result is never described in the blocked check's
words.

One fact deserves repeating because it is easy to lose across a long book. `calibration/volcanoes-labels-by-claude.csv` holds
pass/fail labels written by Claude, an AI model, for the 30 answers of one run (`docs/LIVE_VERIFICATION.md`, run 11). They are
**not human labels**. The word "human" appears in the tool's output (`human_pass`, "human pass") only because the tool's column
is called that; the sweeps in §174 are sweeps against an AI rater and say nothing about what a person would decide.

## 171. Restoring the run store

### 171.1 Why it was manual, and why that stopped being enough

Release 1.1 added `ragwb backup` and chose not to add its inverse: an automated restore that silently overwrites the live
store is a more dangerous feature than the one it protects against (Part XIII §143.2). That reasoning was sound and it left
a real gap. The backup was verified and consistent, and the way back was "stop the app, replace `data/runs.db` by hand". A
person recovering from a bad day is the worst person to improvise an operation on the only copy of their data. Release 1.4
adds `ragwb restore BACKUP --yes [--force]` (`src/rag_workbench/cli.py:424-433`, parser `:554-558`) and keeps the old
caution by making the operation refuse early, refuse often and undo itself.

### 171.2 The order of operations

`restore_store` (`src/rag_workbench/maintenance.py:228-290`) does its work in a fixed order, and the order is the design.

1. **Validate the backup before touching anything** (`maintenance.py:239-256`). The file must exist; it is opened read-only
   (`mode=ro`) and must pass `PRAGMA integrity_check`; it must contain both the `runs` and `case_results` tables; and its
   `user_version` must not be newer than this version's `SCHEMA_VERSION`. Each failure raises a `StorageError` with a message
   that names the backup. A test feeds it, in turn, a missing file, a file of garbage bytes, a valid SQLite file with the wrong
   tables and a copy of a real backup stamped with a future schema, and asserts that after all four refusals the live store is
   byte-for-byte what it was (`tests/test_restore_concurrency.py:42`, assertion `:63`).
2. **Refuse if a run looks active** (`maintenance.py:259-267`, skipped by `--force`). The live store is opened and any run with
   `status == "running"` whose last heartbeat is less than `STALE_AFTER_S` (15 minutes, `storage.py:29`) old makes the restore
   fail with "Run ... is still active; stop it first or pass --force". §171.3 explains the heartbeat.
3. **Write a safety copy** of the live store (`maintenance.py:268-269`): `backup_store` into `<data dir>/backups`, renamed with a
   `pre-restore-` prefix. A restore is therefore reversible: restoring the `pre-restore-*` file puts back what was there, and
   a test does exactly that, restoring a run made *after* the backup back from the safety copy
   (`tests/test_restore_concurrency.py:26`, `:38-39`). If the live store is so damaged that it cannot even be opened or snapshotted
   (which is exactly when a restore is needed), the same step falls back to a **raw byte copy** of the file, named
   `pre-restore-damaged-<timestamp>.db` (`maintenance.py:270-277`), so nothing is lost before the replacement. The only failure that
   still stops the restore here is the "still active" refusal of step 2 (§171.6).
4. **Stage, then replace** (`maintenance.py:278-284`). The backup is copied to `runs.restoring` beside the store, any `-wal`,
   `-shm` and `-journal` sidecar of the old store is deleted, and `os.replace` swaps the staged file in. `os.replace` is atomic
   where the platform provides it, so there is no moment at which `runs.db` is a half-copied file. The sidecars are deleted
   because a sidecar that belongs to the *old* database, applied to the *new* one, is corruption. (The store does not use WAL
   mode, so `-wal` and `-shm` are normally absent; a `-journal` can be left by a crashed writer, and is exactly what must not
   survive.)
5. **Open the result** (`maintenance.py:289`): constructing `RunStore` runs the same migration code as a normal start, so a
   backup from an older schema is upgraded in place. A test builds a schema-1 database by hand and checks that the restored run
   comes out with `tags == []` (`tests/test_restore_concurrency.py:85-100`).

The command line adds one more layer. Without `--yes`, `cmd_restore` prints what it would replace and that a safety copy is
written first, then exits 1 with "re-run with --yes to proceed (stop the web app first)" (`cli.py:418-423`;
`tests/test_restore_concurrency.py:103`). A real run of the command, in a scratch data directory for this Part:

```text
$ ragwb restore <data dir>\backups\runs-20261029-102039.db --yes
This replaces the run store <data dir>\runs.db with <data dir>\backups\runs-20261029-102039.db.
A safety copy of the current store is written first, so the restore can be undone.
Restored <data dir>\runs.db. Previous store saved as <data dir>\backups\pre-restore-runs-20261029-102057.db.
```

### 171.3 The heartbeat, and what the guard can and cannot know

The refusal in step 2 needs an answer to "is a run executing right now?" that does not require asking the process. The run
store already held one. Since release 1.0 every committed case refreshes the run's `heartbeat_at` column (`storage.py:123`, in
`add_case_result`), and `create_run` seeds it at creation; start-up marks runs whose heartbeat is older than 15 minutes as
`interrupted` (`RunStore.recover_interrupted`, `storage.py:154-166`, called from `open_context`, `services.py:32`). What was
missing was a way to read it: release 1.4 adds `RunStore.heartbeat(run_id)` (`storage.py:169-173`), which returns the time a case
was last committed, or `None` if unknown, and `restore_store` falls back to the run's `created_at` when it is `None`
(`maintenance.py:265`).

The guard is a statement about *evidence of life*, not about processes, and it has the usual limits of such a statement.

* **It errs towards refusing.** A process that died four minutes ago still has a fresh heartbeat, so a restore is refused for
  up to fifteen minutes after a crash unless `--force` is given. That is the safe direction.
* **It cannot see a run that has not committed a case for fifteen minutes** (a single case can take several timeouts plus
  back-off, `storage.py:27-28`); the opposite test, that a run which stopped heartbeating three hours ago does not block, is
  `tests/test_restore_concurrency.py:76`.
* **It cannot see the web app itself.** Nothing about an idle Streamlit server marks the store as in use, and §171.4 explains
  why no operating system would either. "Stop the app first" is therefore not advice; it is the actual safeguard, and the
  command line says it twice.
* **It is a check followed by an action**, with a gap between them. A run started in that gap is not seen. The window is
  milliseconds on a laptop; it is stated here because "refuses while a run is active" would otherwise read as a guarantee.

### 171.4 The Windows file lock, and what a held-open store does elsewhere

The last branch of `restore_store` handles `PermissionError` from `os.replace` (`maintenance.py:281-288`): the staged file is
removed and a `StorageError` is raised that says the store is in use by another process, to stop the web app and any running
evaluation, and that "Nothing was changed". The behaviour is a Windows property. A file that a process holds open cannot be
replaced; the call fails with "Access is denied". The test that covers the branch cannot rely on a second process holding a
lock at the right moment, so it patches `os.replace` to raise the error and checks that the live store is unchanged and no
`.restoring` file is left behind (`tests/test_restore_concurrency.py:162-173`).

For this Part the real condition was reproduced as well, in the Windows development environment: a connection was opened to
the run store, one query was run on it, the connection was *kept open*, and `restore_store` was called with `force=True`.

```text
StorageError: The run store is in use by another process (Access is denied); stop the web app and any running evaluation,
then try again. Nothing was changed.
store unchanged: True | leftover .restoring: False
```

Two corollaries are worth stating, because the first is a limit on the feature and the second is a limit on what was tested.

1. **The lock protects less than it seems to.** The run store opens a short-lived connection for each operation and closes it
   (`storage.py:85-98`); between operations the web app holds no handle on the database file. The Windows error therefore appears only
   if a query happens to be in flight, and an idle app does not prevent the replacement. After such a restore the app keeps
   running and its next operation opens the new file, which is usually what was wanted, but it also means the operating system
   gave no warning. Note too that the failed attempt above had already written its safety copy, which is harmless.
2. **On a platform where replacing an open file succeeds, a process holding a connection keeps writing to the old, now
   unnamed, file.** That is how POSIX file replacement works and it is reasoning, not a test: the development machine is
   Windows and no other platform was exercised. The runbook's instruction to stop the app first is what covers it.

### 171.5 What a backup does and does not cover

`ragwb backup` (`maintenance.py:168-199`; names carry microseconds and, if needed, a `-N` counter, `runs-%Y%m%d-%H%M%S-%f.db`, so two backups or safety copies in one second do not collide, `tests/test_restore_concurrency.py:156`) copies `runs.db` with SQLite's online backup API, so it is consistent while the app is
running, and verifies the copy. That is all it covers. It does **not** include `users.json` (account hashes and roles),
`uploads/` (files a user uploaded), `exports/`, `logs/` or `models/`, and the runbook says so and tells the operator to copy
`users.json` separately and never to put `.env` in a backup location they do not control (`docs/OPERATIONS.md` §4). The
restored store is also only as portable as the run records it holds: runs keep the absolute paths of the files they were made
from (`docs/KNOWN_LIMITATIONS.md`), so a restore onto another machine brings the results but not necessarily the inputs.

### 171.6 The unreadable store: a defect found, then fixed

While writing this Part, the incident table of the runbook was tried against its own commands. Its row for "Cannot open run store /
integrity failure" says to `ragwb restore` the latest backup (`docs/OPERATIONS.md` §8). In the first version of release 1.4 that
failed: `main` opened the store for every command except `doctor`, and opening a damaged file raises, so `restore` could not run on the
one store it was meant to repair. Reproduced at the time with a `runs.db` replaced by random bytes:

```text
$ ragwb list
error: Run store error (runs.db): file is not a database
$ ragwb restore <backup> --yes        # first version of 1.4
error: Run store error (runs.db): file is not a database
$ ragwb doctor        # worked by design: "8 ok, 0 warning(s), 1 failure(s)"
```

A manual workaround was found (move the unreadable file aside, then restore into the empty store that the command opens) and the
defect was then fixed in two places. `main` now dispatches `restore` before opening the store, next to `doctor`, passing only the
settings (`cli.py:674-685`, the `restore` branch at `:679-680`), and `restore_store` keeps a raw copy of a damaged store instead of
failing (`maintenance.py:270-277`, §171.2 step 3). The regression test builds a real backup, overwrites the live store file with
junk, confirms that `ragwb list` exits 1, then restores, and asserts that the output names a `pre-restore-damaged-*` file whose bytes
equal the junk and that the restored store lists the original run
(`tests/test_restore_concurrency.py:140-153`, `test_restore_repairs_an_unreadable_store_and_keeps_a_raw_copy`). The manual
workaround is obsolete. The episode is kept here because it is the argument for trying a runbook's commands against its own incident
table.

## 172. Several processes on one store

Part III §35.7 and Part IV §40.6 describe the run store as safe for a CLI run and a Streamlit session to share, on the strength of
a design argument: every operation opens its own connection with a 15-second busy timeout (`storage.py:86-87`), commits on
success and closes (`storage.py:88-98`), so no process holds a lock across the time a case spends waiting on a model. What was
missing was a test. `tests/test_restore_concurrency.py:117` is that test.

It starts **four CLI processes** (`python -m rag_workbench run --name p0..p3 --limit 8 --quiet`) against one data directory
and, while any of them is still running, repeatedly runs `ragwb list` as a **fifth, reading process**. The assertions are that
every process exits 0; that no reader call failed; that the store holds exactly the four runs, each `completed` with 8 case
results; and that `PRAGMA integrity_check` returns `ok` (`tests/test_restore_concurrency.py:130-137`). It passed.

What that does and does not show:

* It shows that short connections with a busy timeout suffice for *this* workload: four writers inserting a case at a time and a
  reader scanning the run list. SQLite's default rollback journal serialises writers; with a timeout of 15 s a writer waits for
  its turn instead of failing, and a reader sees a committed state, never a half-written one.
* It does not show behaviour under heavy contention, with long transactions, on a network file system or in a folder that a
  synchronisation tool rewrites. The runbook's incident table says not to keep `data/` in such a folder while the app runs
  (`docs/OPERATIONS.md` §8), and that advice is a hypothesis from how such tools behave, not a measurement from this project.
* It is one machine. Requirement R49 is marked "Done" with the limit "single machine"
  (`docs/REQUIREMENTS_TRACEABILITY.md`).

The test is slow, because it starts five Python interpreters and keeps starting the reader (the four new test files, 39 tests
together, ran in 59 s in this session). That is the price of a test that exercises real processes rather than threads in one
interpreter, which would have shared one set of Python-level locks and proved nothing.

## 173. Accounts, passwords and who can see which run

### 173.1 The Accounts page

Release 1.3 made roles real and left them administrable only from the command line (Part XV §165.5). Release 1.4 adds an
admin-only page, `src/rag_workbench/ui/views/users.py` (72 lines), reachable as *Accounts* in a new *Admin* group of the sidebar.

Two independent mechanisms keep it away from everyone else, and the redundancy is deliberate.

1. **It is not registered.** `streamlit_app.py` adds the page to the navigation only when named accounts exist and the current
   role is `admin` (`streamlit_app.py:39-40`). For a viewer or editor the page is simply not in the sidebar, and an attempt to
   route to it by name fails (`tests/test_accounts_admin.py:79`).
2. **It checks itself.** If it is reached anyway, the page shows "Managing accounts needs an admin account." and stops before
   rendering any control (`ui/views/users.py:13-15`).

On the page (`ui/views/users.py`): a table of accounts with columns `user`, `role` and `created` (`:22-23`), produced by
`UserStore.entries()` (`rag_workbench/users.py:119-123`), which returns exactly those three keys and nothing derived from the salt or hash
(`tests/test_accounts_admin.py:63`); a form to add an account with a role (`:39-47`); a form to change an account's role and a
form to reset its password (`:49-62`); and a *Remove this account* expander that requires typing the username before the button
is enabled, and that explains instead of offering the button when the target is the signed-in admin themself (`:64-72`). One
helper, `flash` (`:26-36`), runs each store action and turns a `UserError` into an on-page message, so a bad password length
or a duplicate name shows an error instead of a traceback (`tests/test_accounts_admin.py:124`).

### 173.2 The last-admin guard

A system where accounts are managed by admins has an obvious way to lock itself: remove or demote the only admin. The CLI and
the page both go through `UserStore`, so the rule lives there. `_guard_last_admin` (`rag_workbench/users.py:129-137`) refuses `remove` and a
`set_role` to anything but `admin` (`rag_workbench/users.py:162-163`, `:173`) when the target is an admin, no *other* admin exists, and
other accounts would remain. The message names the way out: make another user an admin first, or use `--force`.

Three details of the rule, each with a test (`tests/test_accounts_admin.py:31`, `:41`):

* **The rule only protects against locking out other people.** When the store has a single account (`len(users) < 2`,
  `rag_workbench/users.py:131`), nobody else can be locked out, and removing the sole account is allowed. When the last account is removed
  the file itself is deleted (`rag_workbench/users.py:175-178`), so nothing looks half-configured, and the app falls back to the shared
  password or to no login.
* **`--force` overrides** (`cli.py:588`), and is the documented route when the guard is in the way on purpose.
* **A second admin makes the first replaceable.** The test promotes `eddie` and then demotes and removes `ada`.

The guard is a convenience for a careless click, not a security control: anyone with a shell can edit `users.json`, and the
runbook records how to recover from a lock-out (`docs/OPERATIONS.md` §8: add an admin from the command line, or delete the
file to fall back to no accounts and set `RAGWB_APP_PASSWORD` before exposing the host).

### 173.3 Changing a password

There are now three ways, with different authority.

| Who | How | Check on the old password |
|---|---|---|
| The signed-in user | sidebar expander *Change password* (`ui/auth.py:239-256`) | yes: `set_password(..., current_password=current)` raises "The current password is not correct" when wrong |
| An admin, for anyone | *Reset password* on the Accounts page (`ui/views/users.py:59-62`) | no |
| An operator | `ragwb user set-password NAME [--password-stdin]` (`cli.py:178-184`) | no |

All three go through one method, `UserStore.set_password` (`rag_workbench/users.py:139-153`), which validates the length (10 to 200
characters), optionally verifies the current password with the same constant-time `verify` used at sign-in, and then replaces
**only** the salt and the hash: the role and the creation date are kept (`tests/test_accounts_admin.py:51`). A fresh 16-byte
salt is drawn every time, so changing a password to itself still changes the stored bytes. The self-service path logs
`password changed user=...` and never the password (`ui/auth.py:255`); passwords are not logged anywhere (`docs/SECURITY.md`).
The command line reads the password from a no-echo prompt asked twice, or from standard input with `--password-stdin`
(`cli.py:150-156`), so it need not appear in a shell history or process list.

Two things the feature does not do, and the CLI says one of them out loud. **It does not end other sessions**: the message of
`set-password` reads "Open sessions stay signed in until they end" (`cli.py:183-184`), because a session is a flag in server
memory and the password is not consulted again after sign-in. **It is not a reset flow.** There is no e-mail, no token and no
question; a forgotten password is replaced by an admin. `docs/SECURITY.md` lists "no password reset flow, no MFA, no SSO" among
its known gaps.

### 173.4 Run visibility, and its honest limit

Until now every signed-in user saw every run; `started_by` on a run was attribution, not access control (Part XIV §156.4).
`RAGWB_RUN_VISIBILITY` (`config.py:94`, mapped at `:198`) takes `shared` (the default, unchanged) or `own`. In `own` mode,
`visible_runs` (`ui/auth.py:219-228`) returns, for a non-admin with named accounts, the runs whose `started_by` is that user's
name **plus runs with no owner**; admins see everything; and with `shared`, or with no named accounts, nothing is filtered.

The "no owner" half is a decision, not an oversight. Runs created by the first-launch example seeding, by the command line and
by `ragwb import` have no `started_by`, and filtering them away would empty a new user's Overview page. They stay visible to
everyone. The consequence is that `own` is a statement about runs started *in the web app*; anything created elsewhere is
shared. `started_by` is set in one place (`ui/views/new_run.py:209`).

The filter is applied in the three pages that list runs, at the point where the list is read: Overview (`ui/views/overview.py:13`),
Run results (`results.py:24`) and Compare (`compare.py:13`). Because Run results builds its selector from the filtered list, a
`?run=<id>` deep link to someone else's run falls back to the first visible one (`results.py:32-35`) instead of opening it.
`tests/test_accounts_admin.py:163` signs in as an editor in `own` mode and checks that the Overview table and the Run results
selector contain the shared example and the editor's own run but not another user's; `:178` checks that admins see all and that
`shared` is the default.

**The limit is the point.** Visibility is enforced in the page scripts, and nowhere else.

* The command line lists, shows, exports and deletes any run (`ragwb list`, `export`, `delete`); it has no notion of a user.
* Anyone who can read `data/runs.db` can read every run, and `users.json` as well; the permission tightening on `users.json`
  is best effort (Windows ignores most mode bits, `rag_workbench/users.py:88-89`).
* One page leaked a count: the Settings page printed the number of runs in the store from an unfiltered list, so a non-admin in
  `own` mode could learn how many runs exist in total, though not what they were. It was found while writing this Part and fixed: the
  count now goes through `visible_runs` (`ui/views/settings.py:54`, imported at `:10`), with a test
  (`tests/test_accounts_admin.py:192`, `test_own_mode_does_not_leak_other_users_runs_through_the_settings_run_count`). It is the kind
  of thing a UI-level filter produces: every page that touches the run list has to remember to use it.
* Nothing is encrypted.

`docs/SECURITY.md` says the same in a sentence ("UI level"), the requirements table records R47 as "UI-level only; file access
bypasses it", and the hardening checklist makes disk encryption and operating-system permissions the operator's job. The
argument of Part XV §165.4 (a server-driven framework gives the client no way to call a page's code it was not shown) is why
UI-level enforcement is *adequate for the stated model*, a trusted team on one machine; it has not been attacked, and no
penetration test was done.

## 174. Choosing a pass threshold from labels: `--sweep` and `--rescore`

### 174.1 The problem

`ragwb calibrate` (added in release 1.1, Part XIII §142.4) measures how well a metric's pass/fail verdict
agrees with labels, at the metric's *stored* threshold. That answers "how good is this threshold?" but not the question a
person actually has: "what threshold should I use?". Doing it by hand means re-running the evaluation with `--threshold
metric=value` once per candidate, which for a judge metric costs API calls for a question whose answer is already in the stored
scores. Release 1.4 adds two options that remove that cost.

### 174.2 `--sweep`

`sweep_thresholds` (`src/rag_workbench/calibration.py:206-235`) takes the stored scores of one metric, the labels and a tuple of
candidate thresholds (`DEFAULT_SWEEP`, 0.10 to 0.95 in steps of 0.05, `calibration.py:203`), and returns one `Agreement` per
threshold. A case passes at threshold `t` when its score is at least `t` (with a 1e-9 tolerance so that 0.7 is not lost to
float representation, `:226-229`); cases the metric did not score, and labels for unknown case ids, are *excluded*, never
counted as failures, exactly as the single-threshold comparison does (`tests/test_calibration_sweep.py:52-56`, `n_unscored` and `n_unknown`). The row at the metric's own threshold
matches what `calibrate` prints (`:32`).

`best_threshold` (`calibration.py:238-245`) picks the row with the highest kappa, breaking ties by higher accuracy and then by
the *lower* threshold (`:243`; `tests/test_calibration_sweep.py:38`). The docstring and the command's closing line both state
the caveat that governs the whole feature: the row is chosen on the same labels it is measured on, so its agreement is
optimistic, and with a few dozen labels several thresholds tie. The table is the output; "best" is a mark on it, printed as
`<- best`, not a recommendation (`cli.py:365-374`).

### 174.3 `--rescore`

A run only has the metrics it was run with. To calibrate `semantic_similarity` against a run that was scored with the judge,
the old route was to re-run. `--rescore` (`cli.py:313-330`, used at `:336-340`) computes the missing metric from the run's
**stored answers and stored contexts**, for any offline or local-model metric, with no API call: it builds the metric, and for
each case with `status == "ok"` and an answer constructs the `MetricInput` and adds the result. A judge metric is refused with
an explanatory `ConfigError` ("it makes API calls, so it cannot be recomputed here", `cli.py:326-328`) and an unknown metric
with an "Unknown metric" error (`tests/test_calibration_sweep.py:86-91`). The option only matters when the run lacks the metric; if the run
has it, the stored scores are used.

### 174.4 The two sweeps that were run

Both use the 30 answers of run 7 (volcanoes, `qwen/qwen3.8-27b` as generator and judge) and the 30 labels written by an AI
rater (§170.2). The numbers are `docs/LIVE_VERIFICATION.md`, run 13.

| Metric | At the default 0.70 (agreement / kappa) | Best plateau |
|---|---|---|
| `correctness` (judge) | 0.967 / 0.870 | agreement is flat at 0.967 for every threshold from 0.25 to 0.70; 1.000 only at 0.10-0.20, which is one borderline case (v05 scored 0.20) |
| `semantic_similarity` (local model, via `--rescore`) | 0.867 / 0.595 | 0.967 / 0.839 for thresholds 0.55-0.65; 0.933 at 0.40-0.50; falls to 0.767 at 0.75 and 0.433 at 0.90 |

The `correctness` sweep needs no model and was re-run offline for this Part from the committed run bundle
(`calibration/20261028-035657-qwen-volcanoes-30-b-7d604e.json`, imported into a scratch data directory) and the committed
labels. It reproduced the record, including the plateau; the middle of the table reads:

```text
 threshold  agreement   kappa  metric pass rate
      0.10      1.000   1.000             0.867   <- best
      0.20      1.000   1.000             0.867
      0.25      0.967   0.870             0.833
      0.70      0.967   0.870             0.833
      0.75      0.900   0.672             0.767
      0.95      0.767   0.420             0.633
```

Reading these:

* **The judge's default sits in the middle of a wide plateau.** Anything from 0.25 to 0.70 gives the same verdicts on these 30
  answers, so nothing needs changing, and the plateau is also the reason not to trust the single "best" row: 0.10 is marked best
  only because one borderline case (v05, scored 0.20 and failed by the judge at the default) flips, and a rule that picks that
  row picks the threshold fitted to one case.
* **The semantic metric's default is stricter than this data supports.** At 0.70 it fails four answers the labeller passed.
  The sweep puts its best agreement at 0.55-0.65. That sharpens the Part XV §162.6 finding (cosines from this model have a high
  floor): in run 9 the extractive baseline's answers were so similar to their references that no threshold separated them, whereas
  these LLM answers *do* separate from wrong ones by embedding similarity, in the range 0.55-0.65.
* **A caution from the same tool.** Running the identical sweep for lexical `token_f1` on these labels marks 0.10 as best, with
  agreement 1.000 and a pass rate of 0.867, the labels' own (an offline re-run for this Part, not in the live record). On these 30
  answers the four the labeller failed all score below 0.10 and the rest at or above it. It would be easy to read that as "F1 at
  0.10 is a perfect judge". It is not: the same metric at its default 0.5 agrees on only 18 of 30 (0.600, kappa 0.237), 0.10 is a
  threshold so low that it asks for almost no overlap with the reference, and this is the "optimistic best row" the closing
  line warns about, fitted to 30 cases and 4 failures. It is the clearest demonstration in the project of why a sweep is a
  table to read, not a value to adopt.

### 174.5 Why the defaults were not changed

The defaults are 0.70 for `semantic_similarity` and for the judge metrics, and 0.5 for token F1 (Part VI §67). The sweep found a better value
for exactly one metric, and the decision is to leave it. One document, 30 cases, 4 failures and one AI rater are not enough to
move a threshold that other users' data will meet; the best row is optimistic by construction; and changing a default
silently changes the pass/fail of every future run, which would break the project's property that earlier runs stay
comparable. The tooling to redo this with real labels exists, `docs/KNOWN_LIMITATIONS.md` lists it first among future work, and
until a person fills `calibration/volcanoes-labelling-sheet.csv` the entry in §178.1 stays open. A user who wants a different
threshold for their own data can pass it per run (`--threshold semantic_similarity=0.60`, `cli.py:44-50`).

## 175. BM25 with an inverted index

### 175.1 The old algorithm and its cost

Through release 1.3 `BM25Retriever.score` walked every chunk for every query term, looking each term up in that chunk's term
counts: O(chunks x query terms) dictionary lookups per query, with no index (Part IV §58.2 recorded it in its table of hot paths:
"Scores every chunk for every query; no inverted index"). On the 11-chunk example document that costs nothing. It stops being free as documents
grow, and an upload of up to 25 MB is allowed (`RAGWB_MAX_DOCUMENT_BYTES`, `docs/OPERATIONS.md` §2).

### 175.2 The new structure

The constructor now builds an **inverted index** (`src/rag_workbench/retrieval.py:51-63`).

```python
self._postings: dict[str, list[tuple[int, int]]] = {}      # term -> [(chunk index, term frequency)]
for index, tokens in enumerate(doc_tokens):
    for term, tf in tokens.items():
        self._postings.setdefault(term, []).append((index, tf))
self._len_norm = [k1 * (1 - b + b * length / self._avg_len) for length in self._doc_len]
self.idf = {term: math.log(1 + (n - len(postings) + 0.5) / (len(postings) + 0.5)) for term, postings in self._postings.items()}
```

(`retrieval.py:56-63`, abridged). Three things follow. A term's document frequency is the length of its postings list, so the IDF
is computed from the index with no extra pass. The part of the BM25 denominator that depends only on the chunk (`k1 * (1 - b +
b * len / avg_len)`) is computed once per chunk, not once per chunk per term. And `score` (`retrieval.py:65-79`) now touches
only the chunks that contain a query term:

```python
scores = [0.0] * len(self.chunks)
for term in content_tokens(query):
    postings = self._postings.get(term)
    if not postings:
        continue
    idf = self.idf[term]
    for index, tf in postings:
        scores[index] += idf * (tf * (self.k1 + 1) / (tf + self._len_norm[index]))
return scores
```

### 175.3 Why the scores are *bit-for-bit* identical

It is easy to make a retriever faster and subtly different. A search engine does not care about the last bit of a score. This
project does, for a stricter reason than purity: scores break ties (`retrieval.py:86`), ties decide which chunk is rank 1, rank
1 decides what the extractive generator quotes, and what it quotes decides every lexical metric. A change in the 16th decimal
of a score could in principle reorder two near-equal chunks and change an answer, which would break the rule that earlier runs
stay comparable.

Floating-point addition is not associative, so `(a + b) + c` and `a + (b + c)` can differ in the last bit. The old code,
for each chunk, added the contributions of the query terms **in query order**, starting from `0.0`. The new code loops over the
query terms in the same order on the outside and over each term's postings on the inside, so each chunk's accumulator receives
the same contributions in the same order, starting from the same `0.0`. The arithmetic for one contribution is the same
expression with `k1 * (1 - b + b * length / avg_len)` hoisted out as a value that evaluates identically. A term repeated in the
query is looked up once per occurrence and contributes once per occurrence, as before. The loop order is what preserves
equality, and the docstring says so (`retrieval.py:66-70`).

An argument like that is worth exactly as much as the test that can falsify it.
`tests/test_bm25_equivalence.py` contains a literal transcription of the textbook definition, written the obvious way and with
no index (`reference_scores`, `:20-38`), and compares it with the retriever using exact equality, `==` on lists of floats, never
`approx`:

* eight random corpora (seeds 0-7), 1 to 60 chunks, some with empty chunks, each queried 25 times with queries of 1 to 9
  terms drawn from the corpus vocabulary plus two words that never occur (`:48-55`);
* a query with a repeated term, and a check that repeating it changes the score (`:58-62`);
* non-default `k1` and `b` (`:65-69`);
* a query with no known term, which must score exactly `0.0` everywhere, and an empty query (`:72-74`);
* five identical chunks, whose retrieval order must follow document order (`:77-80`).

That is 12 tests; they passed when the four new files were run for this Part. The same equality was also observed in a larger,
independent way: over the five example runs, 86 cases, 1.0.0 and 1.4.0 produce **0 differences** in any case's metrics
(`CHANGELOG.md`, 1.4.0).

### 175.4 Measured speed, an erratum, and an honest reading

`scripts/benchmark_documents.py` generates synthetic documents (random words drawn from the bundled example text, so term
statistics are realistic), and reports load time, chunks, index time, the median and 95th-percentile latency of a top-3 query over 50
queries, and Python-level peak memory. **Erratum.** The first measurements recorded for this release (for example a 5,000-chunk query
p50 of 40.14 ms, and 64.79 ms before the index) were timed while `tracemalloc` was running, because the script started the tracer
before the queries; tracing every allocation slows Python code that allocates a lot by several times. The same fault affected
`scripts/benchmark.py`. Both scripts now time with no tracer and measure memory in a separate pass. The corrected measurements, offline,
on the same laptop:

| Document | Chunks | Load | Index build | Query p50 | Query p95 | Peak memory |
|---|---:|---:|---:|---:|---:|---:|
| 100 paragraphs | 101 | 0.01 s | 0.006 s | 0.05 ms | 0.06 ms | 0.5 MB |
| 1,000 paragraphs | 1,001 | 0.01 s | 0.071 s | 0.39 ms | 0.45 ms | 4.7 MB |
| 5,000 paragraphs | 5,001 | 0.03 s | 0.298 s | 2.79 ms | 3.80 ms | 23.7 MB |
| 200-page PDF | 1,600 | 0.21 s | 0.108 s | 0.67 ms | 0.80 ms | 7.9 MB |

What the erratum withdraws: the earlier latencies (40.14 ms, 47.44 ms, 10.43 ms), the earlier load and index times, and the changelog
sentence that queries are "about 1.6x faster at 5,000 chunks" *as measured by that harness*. The 1.6x came from comparing 64.79 ms
with 40.14 ms, both under the tracer; it was not a measurement of the index. A query now costs milliseconds even at 5,000 chunks,
loading takes hundredths of a second to a fifth of a second, and indexing 5,000 chunks takes about 0.3 s.

**What was and was not re-measured about the index itself.** The corrected harness was *not* run against the old per-chunk scan, and
no copy of the old code is kept, so there is **no corrected before-and-after figure** for the speed-up. The only direct comparison
available is a spot check made for this Part (a single run, same laptop, 5,001 synthetic chunks, 50 queries; these are the author's
own numbers, not output of the benchmark script). A re-creation of the pre-1.4 scan, written from its description and verified to
return identical scores on those 50 queries, measured a median `retrieve` of 14.58 ms against 6.45 ms for the index with no tracer
(2.3x), and 51.01 ms against 35.00 ms with the tracer on (1.5x). A separate run of the new retriever alone gave 4.91 ms with no tracer
and 26.92 ms with it on. These timings vary from run to run (the index alone read 6.45 ms in one run and 4.91 ms in another), so the
reading is "the index is faster by a factor of about two on this synthetic corpus, not a precise ratio".

**Why the speed-up is modest.** The synthetic vocabulary is the honeybee text's, a few hundred distinct words (288 in the vocabulary
of the generator, 228 of them in the 5,000-chunk index); each indexed term appears in about 600 of the 5,001 chunks on average. A query
of six such words therefore touches a large fraction of the corpus anyway, and an inverted index pays off when terms are rare, as
real vocabularies make them and this one does not. Latency also includes the part of `retrieve` that is *not* indexed: it sorts all N
scores for the top 3 (`retrieval.py:86`), an O(N log N) step the index does not touch.

Correctness did not depend on any of this: the equality of scores (§175.3) and the 86-case comparison between 1.0.0 and 1.4.0 (0 differences)
are unaffected by the benchmark error. Operationally, the corrected figures say that retrieval is not a bottleneck at the document
sizes the limits allow; the cost of a run is dominated by generation and judging, and for the offline path by per-case work.

The same correction changed the offline case benchmark of Part XIII §146 (see its erratum): 5,000 cases take about 47 s, not 109 s, and
four workers are slightly faster than one, not slower.

## 176. Verification by running

### 176.1 A clean wheel install

Part XIV §157.3 ran an *unpacked* wheel from a neutral folder and said plainly that this was not an installation. Release 1.4 does
the installation. `scripts/wheel_check.py` (86 lines; `verify.py --wheel`, `scripts/verify.py:123-126`, runs it) builds the wheel
with `uv build --wheel`, creates a throwaway virtual environment, installs the wheel into it **with all its dependencies from
PyPI**, and uses it from an empty working folder. It makes ten checks:

| # | Check |
|---|---|
| 1 | the wheel builds (`wheel_check.py:46`) |
| 2 | it installs into a fresh venv (`:52`) |
| 3 | the package imports from `site-packages`, not from the checkout (`:61`) |
| 4 | `--version` prints `ragwb 1.4.0` (`:64`) |
| 5 | an offline evaluation completes (`:66`) |
| 6 | data is written to the current directory (`:68`) |
| 7 | nothing was written into `site-packages` (`:70`) |
| 8 | `doctor` reports no failure: 9 ok, 0 failures (`:73`) |
| 9 | the bundled examples are found by `tune-abstention` (`:76`) |
| 10 | the run store reads back (`:79`) |

It ran 10 of 10 (`docs/LIVE_VERIFICATION.md`, run 14; the install took 25 s on a warm cache). The script needs the network (the
dependencies come from PyPI, several hundred MB on a cold cache) and says so in its docstring; nothing of the project is uploaded.
It was **not** re-run for this Part, because it downloads packages; the record is run 14's.

What the check does not prove: that the *web app* works from a wheel. The Streamlit entry script and the page files are in the
project folder, not the wheel, so the wheel is the command-line tool only (`docs/REQUIREMENTS_TRACEABILITY.md`, R50). The
Dockerfile, which does copy the project, is still unbuilt (§178.2).

### 176.2 The defect the install found

The first attempt did not pass: the install worked, and a command that needed the example data did not. The cause was ordinary
and instructive. Release 1.2 had made the package usable outside a checkout by choosing the data folder from the current directory
when no `pyproject.toml` is found (`config.py:21-34`, Part XIV §157.2), by bundling the examples into the wheel
(`pyproject.toml:47-48`, a `force-include` of `examples` as `rag_workbench/_examples`), and by defining one rule for where the
examples are: `EXAMPLES_DIR` (`config.py:37-40`), the project's `examples/` when it exists or when no packaged copy exists, and
otherwise the copy bundled in the wheel. The default dataset and document already followed that rule (`config.py:61-62`). But
three places still built the path from `PROJECT_ROOT / "examples"` directly: `tune-abstention`, the first-launch demo runs and
the dataset picker. In a wheel install `PROJECT_ROOT` is the current directory, which has no `examples/`, so those three failed.

Release 1.2's own wheel test could not see this. It unpacked the wheel and ran `ragwb run` from a neutral folder (Part XIV
§157.3), and `run` uses the default dataset, which followed the rule. The three call sites that did not were never run from a
wheel. The fix is to make them use the rule (`cli.py:24` and `:125`, `demo.py:12` and `:25`, `services.py:10` and `:65`), and the
new benchmark script uses it too (`scripts/benchmark_documents.py:25`, `:33`). `scripts/wheel_check.py` now runs
`tune-abstention` as one of its ten checks to guard the case. One edge of the rule is worth knowing: a wheel install run from a
folder that happens to contain its own `examples/` directory uses *that* one, because the test is whether the folder exists, not
what is in it.

The general lesson is the same as Part XV §160.4's, one level down. A test is exact about the paths its author exercised, and a
rule defined in one place and bypassed in three others is invisible to a test of the one that follows it. A real
installation into an empty environment, with the whole command set run from an empty folder, found in 25 seconds what a
release of reasoning had not.

### 176.3 The agent pipeline, live

`--pipeline agent` has existed since release 1.0: a LangChain tool-calling agent decides when and with what query to call a
retrieval tool, and every chunk the tool returns is captured per call, so the context scored by the metrics is what the tool
actually returned and not what the model says it read (`src/rag_workbench/pipeline.py:61-120`; the capture sets
`context_source="agent_tool"`, `:120`). Until release 1.4 it had run only against a scripted fake model
(`tests/test_providers_pipeline.py:126`).

Run 12 (`docs/LIVE_VERIFICATION.md`) ran it on Groq with `qwen/qwen3.8-27b` as the tool-calling model, BM25 as the tool, and 3
honeybee questions. All three were answered (the first, "A typical honeybee colony has one queen.", and similar), each with 3
chunks captured from the agent's own tool calls, 1 attempt each, 1,104-1,166 prompt tokens and 153-283 completion tokens per
case. Lexical means over the three cases: token F1 0.811, context recall 0.917, groundedness 0.933.

What those numbers are for: they prove the *path*. The model called the search tool, the retrieved text was recorded and scored,
and tokens were counted. Three cases are far too few for the means to say anything about agent quality (compare the interval
widths in Part XV §160.3 at ten cases), the run used one provider and one model, and it makes no statement about OpenAI. What it
removes is a specific risk: that a real model would not use the tool in the shape the code expects. It did.

### 176.4 A full four-judge run that did not complete

Run 17 (`docs/LIVE_VERIFICATION.md`) was the attempt to finish what run 5 of release 1.3 could not: all 20 honeybee questions with
all four judge metrics, `qwen/qwen3.8-27b` as generator and judge, paced at 10 operations per minute. All 20 answers were produced
(5,688 prompt and 613 completion tokens). The evaluation is only partly complete, and the record says so.

| Metric | Mean | Scored | Failed (rate limit) |
|---|---:|---:|---:|
| Token F1 | 0.629 | 20 | 0 |
| Context recall (lexical) | 0.885 | 20 | 0 |
| Groundedness (lexical) | 0.920 | 20 | 0 |
| Answer relevancy (judge) | 0.925 | 20 | 0 |
| Faithfulness (judge) | 1.000 | 6 | 14 |
| Context relevancy (judge) | 0.429 | 1 | 19 |
| Correctness (judge) | 0.958 | 19 | 1 |

The model's free tier allows 1,000 output tokens per minute; the faithfulness and context-relevancy judges write long outputs, and
34 of the 80 judge measurements kept hitting the limit until the retry budget (4 retries, at most 60 s each) ran out. They were
recorded as errors and left out of the means, never counted as zero, exactly as designed. The faithfulness mean therefore rests on
6 cases and the context-relevancy mean on 1 case: both are **missing, not results**. Pacing cannot create a token quota (Part XV
§161). The run took hours. A paid tier, a provider without this cap or a longer retry budget would complete it; none was available.

## 177. Accessibility: an audit tool, and two corrections to earlier text

### 177.1 What was done

Release 1.3's accessibility evidence was a script over five pages and one keyboard walk. Release 1.4 adds two things
(`docs/LIVE_VERIFICATION.md`, runs 15 and 16).

* **axe-core 4.10.2**, run with WCAG 2.0, 2.1 and 2.2 level A and AA rules plus best practices. The library was downloaded from the
  jsDelivr CDN, served to the browser from a local port, and run against this application's own local pages only. Result: **no
  violations** on the views listed in the record (Overview, Run results with its summary, cases and case-detail parts, Compare,
  Datasets and Settings), with 38-43 rules passing per view and one "needs review" item on two of them; and **one minor
  violation** on New evaluation, `presentation-role-conflict` on Streamlit's own file-uploader dropzone (2 nodes), inside a
  component this project cannot change. axe-core cannot see inside a canvas, which is why tables were handled separately.
* **Keyboard walks** of Run results and Settings. Run results: 104 focus events over 40 Tab presses, returning to its first stop
  after 59, with no trap. Settings: 63 events over 40 presses, still inside its tables when stopped. With the New evaluation
  walk of release 1.3, three pages (New evaluation, Run results and Settings) have now been walked by keyboard. Overview, Compare,
  Datasets and the new Accounts page have not, and the Accounts page was not audited by axe-core.

### 177.2 Two corrections

**The early false positive.** Release 1.2's script reported white-on-blue slider values at a contrast of 1.0:1, and Part XIV
§158.3 recorded that as a probable false positive that had not been confirmed. axe-core did not flag the sliders at all on the
page that has them, which supports the reading that the script mis-measured. It is evidence, not proof: it shows that a second,
independent tool does not reproduce the finding.

**What the tables really are.** Parts VII, XIV and XV said that Streamlit draws data tables on a canvas that a screen reader cannot
read, with a CSV download as the alternative. The keyboard walk showed that is not the whole picture. The tables are exposed to
assistive technology through a **parallel grid structure** of `gridcell` elements, so they are not unreadable canvases. But
**each cell is its own Tab stop**, and on Run results 23 of the 59 stops before the focus returned to the start were on
zero-size elements. A table is therefore reachable and readable in principle, and tedious by keyboard in practice. That moves the
problem from "inaccessible" to "inconvenient", which is a different problem with a different remedy (a table with fewer Tab
stops, for example paged HTML tables, if keyboard use is a requirement; `docs/KNOWN_LIMITATIONS.md`, future work item 4). The CSV
download stays. The wording in the chapters that described tables as unreadable has been corrected.

Streamlit's built-in JSON viewer uses syntax colours below 4.5:1; like the uploader, that is not fixable inside this project.

### 177.3 What is still not known

No screen reader was used. Announcement order, the text a reader says for a labelled control, and whether the grid structure is
read in a sensible order are all untested. Zoom and reflow were not tested. Of the 16 focus stops that release 1.3's script
flagged as lacking an outline or shadow, two were checked visually and 14 are still unchecked (Part XV §166); axe-core's focus
rules found nothing on the pages it covered, which is consistent with those being false flags but does not check them one by one.
The requirement table therefore records R44 as "Partly" with a note: axe-core (six views clean), three pages walked, no screen
reader.

## 178. Operations, security, and what is still unverified

### 178.1 The two new documents

`docs/OPERATIONS.md` (94 lines) is a runbook for whoever runs the workbench for others. It uses only commands that exist in this
release and says where each step has a limit.

| Section | Content |
|---|---|
| 1. Installing and starting | the commands for the four ways to run it, the data folder layout, the Windows short-path warning |
| 2. Configuration that matters in production | login, `RAGWB_RUN_VISIBILITY`, pacing, retry and time limits, JSON logs, input ceilings |
| 3. Health and monitoring | `doctor` exit code for a scheduler, the heartbeat, log location, the `/_stcore/health` endpoint |
| 4. Backup and restore | `backup`, `restore`, what a backup covers, "stop the web app first" |
| 5. Upgrades and rollback | back up, replace the code, `uv sync`, migrate in place; rollback needs a restore because an older version refuses a newer schema |
| 6. Access management | the `user` subcommands, roles, the last-admin rule, no self-service reset by e-mail |
| 7. Capacity | measured offline figures (corrected, §175.4 and Part XIII §146): 5,000 cases in about 47 s, 54 MB peak, 21 MB database; documents as in §175.4 |
| 8. Incident playbook | symptom, likely cause, action, for crashes, rate limits, connection drops, store corruption, lock-out, exposed keys, full disks |
| 9. Release checklist | `verify.py --audit`, `wheel_check.py`, the benchmark, the book rebuild, a read of the limitations |

`docs/SECURITY.md` (49 lines) is the summary a person deciding whether to expose the workbench needs: the assets (an API key, the
optional shared password, password hashes, the data), a table of controls with the test that covers each (secrets handling and
log redaction, scrypt hashing, lockout, roles, run visibility, TLS, input limits, telemetry off, locked dependencies, validated
bundles), a list of known gaps, and a seven-step hardening checklist. Its gaps section is the part to read twice: no TLS by
default, roles and visibility enforced in the application only, no password reset, MFA or SSO, no audit trail beyond a log file
and none for changes to runs, sessions in server memory, provider data flow, a point-in-time dependency audit, and "not
verified: the Docker image, behaviour behind a TLS proxy, penetration testing by a third party". The full threat model remains
in Part XI.

Writing the runbook against the code, rather than from memory of it, found the two problems described in §171.6 and §175.4 (an unrepairable-store restore and a measurement error in the benchmarks), both since fixed or corrected. That
is the argument for writing such a document last, with every command at hand, and for having it say "this was tried" only where
it was.

### 178.2 What is still unverified

These items remain open after release 1.4. They are the union of `CHANGELOG.md` ("Not verified"), `docs/KNOWN_LIMITATIONS.md` and
`docs/LIVE_VERIFICATION.md` ("Not covered"), and they replace the list of Part XV §167.

1. **Judge calibration against human labels.** Needs a person. The 30-case sheet (`calibration/volcanoes-labelling-sheet.csv`)
   is still empty. What exists is a comparison with an AI rater's labels (§170.2, §174), which supports "the judge is not
   obviously unreliable on easy cases" and nothing stronger. Every threshold in the project is still uncalibrated against a
   person.
2. **OpenAI itself.** The live evidence is one OpenAI-compatible service (Groq's free tier). Rate-limit headers, error bodies,
   token accounting and model behaviour on OpenAI may differ. `scripts/live_smoke.py` has passed against Groq and never against
   OpenAI.
3. **API embeddings** and hybrid retrieval with them. The provider used has no embedding models. Local embeddings were verified
   (Part XV §162); the API path is tested with fakes only.
4. **The Docker image** has never been built or run (no Docker was available). The wheel is closed (§176.1), for the command-line
   tool only.
5. **Screen readers**, zoom and reflow, and keyboard walks of Overview, Compare, Datasets and Accounts; axe-core on the Accounts
   page (§177.3).
6. **Complete live runs of the other judge metrics.** Only `correctness` and answer relevancy have a complete live run. Run 17 (§176.4) scored faithfulness on 6 of 20 cases and context relevancy on 1 of 20 before the provider's output-token cap stopped it, so those two metrics still lack a complete live result.
7. **Judge noise** beyond one measurement (one metric, ten cases, one judge); **judge cost**, which has never been compared with
   a real invoice; the agent pipeline beyond three cases and one model.
8. **TLS** beyond a self-signed local certificate, and the app behind a TLS-terminating proxy.
9. **Concurrency** beyond one machine and a four-process workload (§172); behaviour on a network or synchronised folder.
10. **Third-party security review.** None was done. Roles and run visibility have not been attacked.
11. **Behaviour on non-Windows platforms.** Everything was run on Windows with Python 3.12. The POSIX file-replacement
    reasoning in §171.4 is untested.

**A checklist for trusting a 1.4 result.**

1. Everything in the 1.3 checklist (Part XV §167) still applies.
2. A threshold chosen by `--sweep` is a candidate, not a calibration: it was fitted to the labels it is measured on.
3. A claim that a judge "agrees with human labels" requires human labels. The sweeps in this book are against an AI rater's.
4. Run visibility `own` hides runs in the web pages only; treat the data directory as readable by everyone with file access.
5. A restore replaces the whole run store; take a fresh `ragwb backup` first if the current store is worth keeping, even though
   `restore` also writes a safety copy.
6. Benchmark figures are single-machine, single-run timings on synthetic data, and the first ones recorded for this release were wrong (§175.4): quote the corrected figures with that caveat.
7. "Wheel verified" means the command-line tool installs and works on Windows with Python 3.12, not the web app and not Docker.

## 179. Reference: commands, variables, files and verification

### 179.1 New and changed commands, options, variables and files

| Item | Purpose | Where |
|---|---|---|
| `ragwb restore BACKUP --yes [--force]` | replace the run store with a backup; validates it, refuses newer schemas and recently active runs, writes a `pre-restore-*` safety copy (a raw `pre-restore-damaged-*` copy if the store is unreadable; works without opening the store) | `cli.py:424-433`, parser `:554-558`, `maintenance.py:228-290`, §171 |
| `ragwb user set-password NAME [--password-stdin]` | change a password without the old one; keeps role and creation date | `cli.py:178-184`, `:150-156`, §173.3 |
| `ragwb user remove\|set-role ... --force` | override the last-admin guard | `cli.py:170-191`, parser `:537-545`, §173.2 |
| `ragwb calibrate RUN --labels F --metric M --sweep` | agreement and kappa at every pass threshold 0.10-0.95 | `cli.py:357-366`, parser `:600-608`, `calibration.py:203-245`, §174 |
| `ragwb calibrate ... --rescore` | compute an offline or local-model metric from a run's stored answers (no API calls) | `cli.py:313-330`, `:336-340`, §174.3 |
| `RAGWB_RUN_VISIBILITY=shared\|own` | with accounts, hide other users' runs from non-admins (UI level only) | `config.py:94`, `:198`, `ui/auth.py:219-228`, §173.4 |
| Accounts page (admins only) | add, change role, reset password, remove | `ui/views/users.py`, `streamlit_app.py:39-40`, §173.1 |
| *Change password* (sidebar) | self-service password change | `ui/auth.py:239-256`, §173.3 |
| `<data dir>/backups/pre-restore-runs-*.db` | the safety copy a restore writes | `maintenance.py:268-269`, §171.2 |
| `scripts/wheel_check.py`, `verify.py --wheel` | clean-install check, 10 checks | §176.1 |
| `scripts/benchmark_documents.py` | large-document scale benchmark | §175.4 |
| `docs/OPERATIONS.md`, `docs/SECURITY.md` | runbook and security overview | §178.1 |
| `rag_workbench/_examples` (inside the wheel) | the bundled examples; `config.EXAMPLES_DIR` chooses between it and `examples/` | `config.py:37-40`, `pyproject.toml:47-48`, §176.2 |

The CLI now has **24 commands**: the 23 of release 1.3 plus `restore` (parser definitions `cli.py:478-628`, 24 `add_parser` calls);
`user` gained `set-password` and `--force`, and `calibrate` gained `--sweep` and `--rescore`. The Python surface that is new is
`maintenance.restore_store`, `storage.RunStore.heartbeat`, `users.UserStore.set_password`, `entries`, `admins` and
`_guard_last_admin` (with a `force` argument on `remove` and `set_role`), `calibration.sweep_thresholds`, `best_threshold` and
`DEFAULT_SWEEP`, `ui.auth.visible_runs`, and `config.EXAMPLES_DIR`.

### 179.2 New source files and tests

| File | Lines | Role |
|---|---:|---|
| `src/rag_workbench/ui/views/users.py` | 72 | admin Accounts page |
| `scripts/wheel_check.py` | 86 | clean-install check |
| `scripts/benchmark_documents.py` | 107 | large-document benchmark |
| `docs/OPERATIONS.md` | 94 | runbook |
| `docs/SECURITY.md` | 49 | security overview |
| `tests/test_restore_concurrency.py` | - | 10 tests: restore round trip and reversibility, refusals leave the store untouched, active-run guard, a dead run does not block, older-schema migration, CLI confirmation, four processes plus a reader, an unreadable store repaired with a raw copy kept, two backups in one second, held-open store |
| `tests/test_accounts_admin.py` | - | 12 tests: last-admin guard, `--force`, password change, entries without secrets, CLI, routing, admin journey, validation errors, self-service change, run visibility (three, one for the Settings run count) |
| `tests/test_calibration_sweep.py` | - | 8 tests: sweep table, row at the stored threshold, best-threshold tie rule, no-comparison case, excluded cases, CLI sweep, CLI rescore, CLI refusals |
| `tests/test_bm25_equivalence.py` | - | 12 tests: exact equality on eight random corpora, repeated terms, custom parameters, unknown terms, ties |

Changed files: `maintenance.py`, `storage.py`, `cli.py`, `calibration.py`, `users.py`, `ui/auth.py`, `config.py`, `retrieval.py`,
`demo.py`, `services.py`, `streamlit_app.py`, `ui/views/overview.py`, `results.py`, `compare.py`, `scripts/verify.py`,
`pyproject.toml` and `uv.lock` (version 1.4.0).

### 179.3 Verification

`docs/TESTING.md` records **418 tests collected, 416 passed, 0 failed, 2 skipped** (the opt-in live test and the opt-in real-model
test); statement coverage **96 %** (3,567 statements, 125 missed; `ui/views/*` is excluded from the measurement, Part IX §97.3);
`ruff` and `mypy` clean over 47 source files. That is the full suite run after the three tests that accompany the fixes of §171.6,
§171.5 and §173.4 (the unreadable-store test, the same-second backup test and the Settings-count test) were added; the four new test
files hold 43 tests in all (11, 12, 8 and 12). The release adds one verification step beyond the six of
`scripts/verify.py`: `--wheel`, optional because it downloads packages. The commands re-run offline for this Part (a scratch data
directory, no key, no network): the correctness sweep of §174.4, the restore and corrupt-store cases of §171, the held-open store of
§171.4 and the spot-check timings of §175.4.

### 179.4 Defects and text that lags the code

These were found while writing this Part. Those that were fixed afterwards say so; the rest are facts about the release as shipped.

* **Fixed: `restore` could not repair an unreadable store** (§171.6). `main` now dispatches it before opening the store, and a damaged
  store is kept as a raw copy.
* **Corrected: benchmark timings were taken under `tracemalloc`** and were several times too slow; both scripts were fixed and the
  figures re-measured (§175.4, Part XIII §146). The speed-up of the inverted index has no corrected before-and-after measurement.
* **Fixed: the Settings page leaked the total run count** in `own` mode (§173.4).
* **Fixed: two backups or safety copies in the same second collided on their file name**; names now carry microseconds (§171.5).
* **Fixed: stale lines in `docs/KNOWN_LIMITATIONS.md` and the `users.py` module docstring.**
* **The audit record's view count is ambiguous**: `docs/LIVE_VERIFICATION.md` run 15 says seven page views (six clean, one with
  a minor issue) but its list (Overview; Run results as summary, cases and case detail; Compare; Datasets; Settings) names more
  than six clean views if the three parts of Run results are counted separately. §177.1 quotes the list as written.
* **The Accounts page has no screenshot** in the book. The page was added after the screenshots of Part VII were taken, and this
  release did not recapture them; the page is exercised by AppTest journeys (`tests/test_accounts_admin.py:90`).

### 179.5 How to read a 1.4 result

A 1.4 run is the same record as a 1.3 run: the same fields, the same scores for the same inputs, schema 3, and a recorded
environment version of `1.4.0` (`src/rag_workbench/__init__.py:13`). Nothing about an old run needs to be re-interpreted, and
that was the constraint the whole release was built to keep: restore, accounts, visibility, the sweep and the index all change
how a run is *managed or found*, and none changes what it *says*.


## 180. Release 1.4.1: the provider key in the project, and its helper

Release 1.4.1 changed no evaluation behaviour. It put the owner's provider key where the project already expects it and made that
safe to do. Four facts, each checked by running the code.

**The key lives in `.env`, and only there.** `load_settings` reads `<project>/.env` (`src/rag_workbench/config.py`, the `load_dotenv`
call inside `load_settings`) unless the environment variable `RAGWB_NO_DOTENV` is `1`. The file holds the key, the endpoint (Groq's
OpenAI-compatible URL), the model names and the pacing settings of Part XV §161. It is excluded from git (`.gitignore`), from Docker
builds (`.dockerignore`) and from wheels (the wheel packages only `src/rag_workbench` and the examples). A live smoke test run with no
environment variables set, only the file, passed 8 of 8 checks on 2 cases, which proves the loader path end to end.

**A real `.env` must never reach a test.** Before 1.4.1 the test fixture blanked only `OPENAI_API_KEY` and *deleted* a few other
variables, which does not stop `.env` from supplying them again. The suite now sets `RAGWB_NO_DOTENV=1` at import time in
`tests/conftest.py`, so child processes inherit it, and the two helpers that build an explicit environment for a subprocess
(`tests/test_live.py`, `tests/test_cli_services.py`) pass it too. `tests/test_dotenv_switch.py` proves both directions with a temporary
project root: the file is loaded by default and ignored with the switch.

**The secret scan changed its mind about `.env`.** `scripts/verify.py` used to fail whenever a `.env` existed. That was right while the
file was a hazard and wrong once it is the documented home of the key, so a `.env` that is listed in `.gitignore` and `.dockerignore`
now passes with a note, and the scan still fails on a key-shaped string anywhere else, or on a `.env` that is not ignored.

**Rotating a key is done in the provider's console, and the project makes the swap trivial.** `scripts/set_api_key.py` replaces only the
`OPENAI_API_KEY` line of `.env`, reads the new key without echo (or from standard input), never prints it (it reports only its length),
writes through a temporary file so an interruption cannot corrupt the file, and can blank the key (`--remove`). With `--check` it sends
one `GET <base url>/models` request and prints only the HTTP status. `tests/test_set_api_key.py` (13 tests) checks that only the key
line changes, that implausible keys are refused without being echoed, that the key never appears in output, and that `--check` sends the
stored key but reports nothing but a status.

**One exposure the code cannot fix.** The project folder sat inside a cloud-sync client (OneDrive) when the key was added, so the file
was exposed to that service until sync was stopped; the key had also been pasted into a chat. Both are operational matters: the
documents `docs/SECURITY.md` and `docs/OPERATIONS.md` now say to exclude `.env` from sync, to treat a pasted key as exposed, and to
rotate it. The honest status at the end of this book is therefore: the project is complete; the key in `.env` should be rotated by its
owner, with `scripts/set_api_key.py` to install the replacement.

### 180.1 Polish fixes found by using the tools

Release 1.4.1 also collected a set of small defects found by running the commands as a user would. Each has a test.

* **`.md` headings.** For `.md` documents only, `documents._ATX_MARKER` removes a leading `#` to `######` marker from each paragraph, so
  a title chunk no longer begins with `# `. `.txt` files are unchanged.
* **Run references.** `cli._get_run` accepts the exact id, otherwise a unique id prefix, a unique id suffix (the short id the web app
  shows) or an exact run name, each of at least 4 characters. A reference matching several runs is an error that lists up to five ids.
* **`show`** prints the run's tags and notes. **`calibrate`** prints `vs labels from <file>` in its header, and `calibrate --rescore`
  fails with a `ConfigError` if the metric can be computed for no case, instead of reporting an empty comparison.
* **`prune`** never selects a run tagged `keep`, whichever of `--keep-last` and `--older-than-days` is given.
* **`--workers` and `--limit`** reject values below 1 (a usage error). **`regress --metrics`** with a name that is not shared by both runs
  is an error with exit 1 that lists the shared metrics, rather than a silently empty gate.
* **Local embedding model.** `metrics/semantic.py` loads the local model when the run is prepared, and a model that cannot be loaded
  becomes one `ConfigError` (`local_model_error`) before any case runs, instead of one failure per case.
* **Backups and restore.** Backup names are `runs-%Y%m%d-%H%M%S-%f.db`, and restoring from a backup file that cannot be read as a run
  store reports that plainly (§171.5, §171.6).
* **`start.py`** honours `RAGWB_NO_DOTENV` like the rest of the program. **`scripts/set_api_key.py`** is the helper described above.
* The tests for these fixes are in `tests/test_cli_polish.py` (19 tests).

### 180.2 Finding: DeepEval loaded a real `.env` by itself

While timing the test suite, a run was slower than the offline suite should be. The cause was DeepEval: when it is imported, and again
through the pytest plugin it registers, it loads a `.env` file from the working directory. With a real key in the project `.env`, that
meant the suite could read the key and its settings without going through `load_settings`, and the extra start-up work slowed every run.
`RAGWB_NO_DOTENV` could not help, because it is checked by the workbench's own loader, not by DeepEval. The fix has two parts: the
package sets `DEEPEVAL_DISABLE_DOTENV=1` with `setdefault` on import (`src/rag_workbench/__init__.py`; set it to `0` to restore DeepEval's
own behaviour), and `pyproject.toml` passes `-p no:deepeval` in pytest's `addopts`, so the plugin never starts. `tests/conftest.py`
sets the variable too, and `tests/test_dotenv_switch.py` is the leak guard: it checks that the switch is on in the suite and that a
fresh interpreter importing the package has the variable set.

### 180.3 Final verification of 1.4.1

`pytest --collect-only -q` reports 455 tests; the full run is 453 passed, 2 skipped (the same two opt-in tests), statement coverage 97 % (3,624 statements, 125 missed),
and `scripts/verify.py --audit --wheel` passes 8 of 8 steps. No human-labelled data and no live OpenAI run were added in 1.4.1; the
limits of §178.2 stand.
