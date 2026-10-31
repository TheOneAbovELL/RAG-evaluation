"""Command-line interface: ``uv run ragwb <command>`` (equivalently ``python -m rag_workbench <command>``)."""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path
from types import SimpleNamespace

from . import __version__
from .abstention import format_report, tune
from .aggregate import metadata_keys, slice_results
from .archive import BundleError, import_bundle
from .calibration import (
    LabelsError,
    best_threshold,
    calibrate,
    interpret_kappa,
    labelling_sheet,
    load_labels,
    sweep_thresholds,
)
from .config import EXAMPLES_DIR, ConfigError, Settings, load_settings
from .datasets import DatasetError, validate_file
from .documents import DocumentError
from .history import TagError, normalise_tags, parse_tag_list, search_runs, validate_notes
from .judge_noise import estimate_operations, format_noise, measure_noise
from .maintenance import backup_store, rerun_config, restore_store, run_doctor, select_prunable
from .metrics import DEFAULT_JUDGE_METRICS, DEFAULT_OFFLINE_METRICS, METRIC_SPECS, MetricInput, build_metrics
from .models import RunConfig
from .regression import check_regression, format_regression
from .reporting import EXPORT_FORMATS, comparison_dataframe, metric_label, run_metrics, summary_dataframe, write_export
from .runner import Progress
from .services import open_context
from .storage import StorageError
from .users import DEFAULT_ROLE, ROLES, UserError, UserStore


def build_config(args: argparse.Namespace, settings: Settings) -> RunConfig:
    metrics = args.metrics.split(",") if args.metrics else (
        DEFAULT_OFFLINE_METRICS if args.provider == "offline" else DEFAULT_OFFLINE_METRICS + DEFAULT_JUDGE_METRICS)
    thresholds = {}
    for item in args.threshold or []:
        name, _, value = item.partition("=")
        try:
            thresholds[name.strip()] = float(value)
        except ValueError:
            raise ConfigError(f"Bad --threshold {item!r}; expected metric=value") from None
    metrics = [m.strip() for m in metrics if m.strip()]
    uses_judge = any(METRIC_SPECS[m].requires_openai for m in metrics if m in METRIC_SPECS)
    return RunConfig(
        name=args.name, dataset_path=str(Path(args.dataset or settings.default_dataset).resolve()),
        document_path=str(Path(args.document or settings.default_document).resolve()), provider=args.provider,
        pipeline=args.pipeline, retriever=args.retriever, k=args.k, metrics=metrics, thresholds=thresholds,
        generator_model=args.model,
        # Record a judge model only when a judge metric actually runs, so the config never claims one that wasn't used.
        judge_model=(args.judge_model or settings.judge_model) if uses_judge else None,
        embedding_model=(settings.local_embedding_model if args.retriever in ("local", "hybrid-local")
                         else settings.embedding_model if args.retriever != "bm25" else None),
        max_workers=args.workers or (1 if args.provider == "offline" else settings.max_workers),
        max_retries=settings.max_retries, request_timeout_s=settings.request_timeout_s,
        case_timeout_s=settings.case_timeout_s,
        max_answer_sentences=args.answer_sentences, limit=args.limit, notes=args.notes,
        offline_failure_rate=args.inject_failures, seed=args.seed,
        min_evidence=args.min_evidence, skip_headings=args.skip_headings)


def cmd_run(args, ctx) -> int:
    config = build_config(args, ctx.settings)

    def report(p: Progress) -> None:
        mark = "ok " if p.status == "ok" else "ERR"
        print(f"[{p.done:>3}/{p.total}] {mark} {p.case_id}" + ("" if p.status == "ok" else f"  {p.message}"))

    run = ctx.runner().run(config, progress=None if args.quiet else report)
    print(f"\nRun {run.id}: {run.status}")
    _print_summary(run)
    return 0 if run.status == "completed" else 2


def _print_summary(run) -> None:
    if not run.summary:
        print("(no summary)")
        return
    s = run.summary
    latency = f"{s.mean_latency_ms:.1f} ms" if s.mean_latency_ms is not None else "n/a"
    print(f"cases {s.n_cases}  ok {s.n_ok}  errors {s.n_error}  mean latency {latency}")
    print(f"{'metric':<28}{'mean':>8}{'95% CI':>17}{'pass':>8}{'scored':>8}{'skip':>6}{'err':>5}")
    for name, m in s.metrics.items():
        mean = f"{m.mean:.3f}" if m.mean is not None else "-"
        ci = f"{m.ci_low:.3f}-{m.ci_high:.3f}" if m.ci_low is not None else "-"
        rate = f"{m.pass_rate:.0%}" if m.pass_rate is not None else "-"
        print(f"{metric_label(name):<28}{mean:>8}{ci:>17}{rate:>8}{m.n_scored:>8}{m.n_skipped:>6}{m.n_error:>5}")
    for warning in run.config.get("provenance_warnings") or []:
        print(f"! {warning}")


def cmd_list(args, ctx) -> int:
    all_runs = ctx.store.list_runs()
    if not all_runs:
        print("No runs yet. Try: uv run ragwb run --name first-offline-run")
        return 0
    runs = search_runs(all_runs, " ".join(args.search or []), tag=args.tag, status=args.status)
    if not runs:
        print(f"No run matches (of {len(all_runs)} stored).")
        return 0
    df = summary_dataframe(runs)
    df["tags"] = [",".join(r.tags) for r in runs]
    cols = ["run_id", "name", "status", "provider", "pipeline", "retriever", "k", "n_cases", "n_errors", "tags"]
    print(df[cols].to_string(index=False))
    return 0


def cmd_tag(args, ctx) -> int:
    run = _get_run(ctx, args.run_id)
    tags = [t for t in run.tags if t not in parse_tag_list(args.remove or "")]
    tags = normalise_tags([*tags, *parse_tag_list(args.add or "")])
    ctx.store.set_tags(run.id, tags)
    print(f"{run.id}: tags = {', '.join(tags) if tags else '(none)'}")
    return 0


def cmd_tune_abstention(args, ctx) -> int:
    root = EXAMPLES_DIR  # the project's examples, or the copy bundled in an installed wheel
    if args.dataset or args.document:
        if len(args.dataset or []) != len(args.document or []) or not args.dataset:
            raise ConfigError("Give the same number of --dataset and --document files, in matching order")
        pairs = [(Path(d), Path(p)) for d, p in zip(args.dataset, args.document, strict=True)]
    else:
        pairs = [(root / "datasets" / f"{name}.jsonl", root / "documents" / f"{doc}.pdf")
                 for name, doc in (("honeybees_unanswerable", "honeybees"), ("volcanoes", "volcanoes"),
                                   ("coffee", "coffee"), ("lighthouses", "lighthouses"))]
    print(format_report(tune(ctx.settings, pairs)))
    return 0


def cmd_regress(args, ctx) -> int:
    base, cand = _get_run(ctx, args.baseline), _get_run(ctx, args.candidate)
    metrics = [m.strip() for m in args.metrics.split(",") if m.strip()] if args.metrics else None
    shared = sorted(set(run_metrics(base)) & set(run_metrics(cand)))
    unknown = [m for m in metrics or [] if m not in shared]
    if unknown:
        raise LookupError(f"Metric(s) not present in both runs: {', '.join(unknown)}. "
                          f"Shared metrics: {', '.join(shared) or '(none)'}")
    report = check_regression(base, ctx.store.get_case_results(base.id), cand, ctx.store.get_case_results(cand.id),
                              max_drop=args.max_drop, min_pairs=args.min_pairs,
                              max_error_increase=args.max_error_increase, metrics=metrics)
    print(f"baseline  = {base.name} [{base.id}]")
    print(f"candidate = {cand.name} [{cand.id}]\n")
    print(format_regression(report))
    return report.exit_code


def _read_password(args) -> str:
    if args.password_stdin:
        return sys.stdin.readline().rstrip(chr(13) + chr(10))
    password = getpass.getpass("Password: ")
    if password != getpass.getpass("Repeat password: "):
        raise UserError("The passwords do not match")
    return password


def cmd_user(args, ctx) -> int:
    store = UserStore(ctx.settings.users_path)
    if args.action == "list":
        names = store.names()
        for name in names:
            print(f"{name}  ({store.role_of(name)})")
        if not names:
            print("No user accounts (the app uses RAGWB_APP_PASSWORD, or no login).")
        return 0
    if not args.name:
        raise UserError(f"'user {args.action}' needs a username")
    if args.action == "set-role":
        if not args.role:
            raise UserError("'user set-role' needs --role viewer|editor|admin")
        if not store.set_role(args.name, args.role, force=args.force):
            print(f"No such user: {args.name}", file=sys.stderr)
            return 1
        print(f"{args.name} is now {args.role}. The change applies on the next page load.")
        return 0
    if args.action == "set-password":
        password = _read_password(args)
        if not store.set_password(args.name, password):
            print(f"No such user: {args.name}", file=sys.stderr)
            return 1
        print(f"Password changed for {args.name}. Open sessions stay signed in until they end.")
        return 0
    if args.action == "remove":
        if not store.remove(args.name, force=args.force):
            print(f"No such user: {args.name}", file=sys.stderr)
            return 1
        print(f"Removed {args.name}. Any open session for this user ends on its next page load.")
        return 0
    password = _read_password(args)
    username = store.add(args.name, password, replace=args.replace, role=args.role or DEFAULT_ROLE)
    print(f"Saved user {username} ({args.role or DEFAULT_ROLE}). Sign in on the web app with this username.")
    return 0


def cmd_judge_noise(args, ctx) -> int:
    run = _get_run(ctx, args.run_id)
    wanted = [m.strip() for m in args.metrics.split(",") if m.strip()] if args.metrics else [
        m for m in run.config.get("metrics", []) if m in METRIC_SPECS and METRIC_SPECS[m].requires_openai]
    if not wanted:
        raise ConfigError("This run has no judge metrics; name some with --metrics (for example faithfulness)")
    cases = ctx.store.get_case_results(run.id)[: args.limit or None]
    operations = estimate_operations(cases, len(wanted), args.repeats)
    print(f"{operations} judge measurements ({args.repeats} repeats x {len(wanted)} metrics x cases), each of which "
          "can make several API calls.")
    if operations > MAX_UNCONFIRMED_OPERATIONS and not args.yes:
        print(f"error: more than {MAX_UNCONFIRMED_OPERATIONS} measurements; re-run with --yes to confirm the spend "
              "(or lower --repeats / --limit)", file=sys.stderr)
        return 1
    metrics = build_metrics(wanted, ctx.settings, judge_model=run.config.get("judge_model"))
    thresholds = {m.name: run.config.get("thresholds", {}).get(m.name, m.spec.default_threshold) for m in metrics}
    rows = measure_noise(cases, metrics, thresholds, args.repeats)
    print(format_noise(rows))
    return 0


MAX_UNCONFIRMED_OPERATIONS = 30


def cmd_note(args, ctx) -> int:
    run = _get_run(ctx, args.run_id)
    if args.clear == (args.text is not None):
        raise TagError("Give the note text, or --clear to remove the note (not both)")
    notes = None if args.clear else validate_notes(args.text)
    ctx.store.set_notes(run.id, notes)
    print(f"{run.id}: note {'cleared' if notes is None else 'saved'}")
    return 0


def cmd_show(args, ctx) -> int:
    run = _get_run(ctx, args.run_id)
    print(f"{run.name} [{run.id}] status={run.status} created={run.created_at:%Y-%m-%d %H:%M:%S}")
    for key in ("provider", "pipeline", "retriever", "k", "generator_model", "judge_model", "dataset_path",
                "document_path"):
        print(f"  {key}: {run.config.get(key)}")
    if run.tags:
        print(f"  tags: {', '.join(run.tags)}")
    if run.notes:
        print(f"  notes: {run.notes}")
    _print_summary(run)
    return 0


def cmd_compare(args, ctx) -> int:
    run_a, run_b = _get_run(ctx, args.run_a), _get_run(ctx, args.run_b)
    df = comparison_dataframe(run_a, ctx.store.get_case_results(run_a.id), run_b,
                              ctx.store.get_case_results(run_b.id))
    if df.empty:
        print("The two runs share no metrics.")
        return 1
    print(f"A = {run_a.name} [{run_a.id}]\nB = {run_b.name} [{run_b.id}]\n")
    print(df.drop(columns=["metric"]).to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    return 0


def cmd_export(args, ctx) -> int:
    run = _get_run(ctx, args.run_id)
    out_dir = Path(args.out_dir) if args.out_dir else ctx.settings.exports_dir
    path = write_export(run, ctx.store.get_case_results(run.id), args.format, out_dir)
    print(f"Wrote {path}")
    return 0


def cmd_validate(args, ctx) -> int:
    s = ctx.settings
    report = validate_file(args.dataset, max_bytes=s.max_dataset_bytes, max_cases=s.max_cases,
                           max_field_chars=s.max_field_chars)
    print(f"{report.name}: {len(report.cases)} cases, {report.n_with_reference} with reference answers")
    for issue in report.errors:
        print(f"  ERROR   {issue}")
    for issue in report.warnings:
        print(f"  warning {issue}")
    print("valid" if report.ok else "INVALID")
    return 0 if report.ok else 1


def cmd_delete(args, ctx) -> int:
    if not args.yes:
        print("Refusing to delete without --yes")
        return 1
    if ctx.store.delete_run(args.run_id):
        print("deleted")
        return 0
    print(f"No run with id {args.run_id!r}.", file=sys.stderr)
    return 1


def cmd_metrics(args, ctx) -> int:
    for name, spec in METRIC_SPECS.items():
        needs = [w for w, flag in (("reference", spec.requires_reference), ("context", spec.requires_context),
                                   ("OpenAI", spec.requires_openai),
                                   ("fastembed", spec.requires_local_model)) if flag]
        print(f"{name:<18} {spec.family:<10} threshold {spec.default_threshold:<4} needs: {', '.join(needs) or '-'}")
        print(f"{'':<18} {spec.description}")
    return 0


def cmd_import(args, ctx) -> int:
    for path in (Path(p) for p in args.bundles):
        run_id = import_bundle(ctx.store, path)
        print(f"{path.name}: " + (f"imported as {run_id}" if run_id else "already present, skipped"))
    return 0


def cmd_labels_template(args, ctx) -> int:
    run = _get_run(ctx, args.run_id)
    out = Path(args.out)
    if out.exists() and not args.force:
        raise ValueError(f"{out} already exists; pass --force to overwrite")
    out.write_bytes(labelling_sheet(run, ctx.store.get_case_results(run.id)))
    print(f"Wrote {out}. Fill the human_pass column (pass/fail) for each case, then run: "
          f"ragwb calibrate {run.id} --labels {out} --metric <metric>")
    return 0


def _rescored(ctx, metric: str, cases):
    """Copies of ``cases`` with ``metric`` computed from the stored answers and contexts (no API calls)."""
    spec = METRIC_SPECS.get(metric)
    if spec is None:
        raise LookupError(f"Unknown metric {metric!r}")
    if spec.requires_openai:
        raise ConfigError(f"{metric} is a judge metric: it makes API calls, so it cannot be recomputed here; "
                          "re-run the evaluation with it instead")
    [scorer] = build_metrics([metric], ctx.settings)
    out = []
    attempted = []
    for case in cases:
        if case.status != "ok" or not case.answer:
            out.append(case)
            continue
        inp = MetricInput(question=case.question, answer=case.answer, expected_answer=case.expected_answer,
                          contexts=[c.text for c in case.contexts])
        result = scorer.evaluate(inp)
        attempted.append(result)
        out.append(case.model_copy(update={"metrics": {**case.metrics, metric: result}}))
    if attempted and all(r.status == "error" for r in attempted):
        reason = (attempted[0].reason or "unknown error")[:300]
        raise ConfigError(f"{metric} could not be computed for any case: {reason}")
    return out


def cmd_calibrate(args, ctx) -> int:
    run = _get_run(ctx, args.run_id)
    cases = ctx.store.get_case_results(run.id)
    if args.metric not in run_metrics(run):
        if not args.rescore:
            raise LookupError(f"Run {run.id} has no metric {args.metric!r}. Available: {', '.join(run_metrics(run))}"
                              " (offline and local-model metrics can be computed from stored answers with --rescore)")
        cases = _rescored(ctx, args.metric, cases)
    labels = load_labels(args.labels)
    result = calibrate(cases, labels, args.metric)

    def fmt(v):
        return "n/a" if v is None else f"{v:.3f}"
    print(f"{metric_label(args.metric)} vs labels from {Path(args.labels).name}, run {run.name} [{run.id}]")
    print(f"labelled cases matched: {result.n_labelled}   compared: {result.n_compared}   "
          f"metric did not score: {result.n_unscored}   labels for unknown cases: {result.n_unknown}")
    print("                    human pass   human fail")
    print(f"metric pass        {result.tp:>10}   {result.fp:>10}")
    print(f"metric fail        {result.fn:>10}   {result.tn:>10}")
    print(f"agreement {fmt(result.accuracy)}   kappa {fmt(result.kappa)} ({interpret_kappa(result.kappa)})   "
          f"precision {fmt(result.precision)}   recall {fmt(result.recall)}")
    print(f"pass rate: metric {fmt(result.metric_pass_rate)}, human {fmt(result.human_pass_rate)}")
    if result.small_sample:
        print("note: fewer than 30 compared cases; treat kappa as indicative only")
    if args.sweep:
        rows = sweep_thresholds(cases, labels, args.metric)
        best = best_threshold(rows)
        print("\nthreshold sweep (a case passes when its score >= threshold):")
        print(f"{'threshold':>10}{'agreement':>11}{'kappa':>8}{'metric pass rate':>18}")
        for t, a in rows:
            mark = "   <- best" if t == best else ""
            print(f"{t:>10.2f}{fmt(a.accuracy):>11}{fmt(a.kappa):>8}{fmt(a.metric_pass_rate):>18}{mark}")
        print("The best row is chosen on these same labels, so it is optimistic; with a few dozen labels several "
              "thresholds tie. Confirm on new labels before changing a default.")
    return 0 if result.n_compared else 1


def cmd_slices(args, ctx) -> int:
    run = _get_run(ctx, args.run_id)
    results = ctx.store.get_case_results(run.id)
    keys = metadata_keys(results)
    if args.by not in keys:
        raise LookupError(f"No case in this run has metadata field {args.by!r}. "
                          f"Available: {', '.join(keys) if keys else '(none; add a metadata object to dataset rows)'}")
    names = list(run.summary.metrics) if run.summary else run_metrics(run)
    thresholds = {n: m.threshold for n, m in run.summary.metrics.items()} if run.summary else {}
    rows = slice_results(results, args.by, names, thresholds)
    print(f"{run.name} [{run.id}] by {args.by}")
    print(f"{'slice':<24}{'cases':>6}{'ok':>5}  " + "  ".join(f"{metric_label(n)[:18]:>18}" for n in names))
    for row in rows:
        cells = []
        for n in names:
            m = row.metrics[n]
            cells.append(f"{(f'{m.mean:.3f}' if m.mean is not None else '-'):>8} {f'({m.n_scored})':>9}")
        print(f"{row.value[:23]:<24}{row.n_cases:>6}{row.n_ok:>5}  " + "  ".join(cells))
    print("(n scored in brackets; small slices have wide uncertainty)")
    return 0


def cmd_rerun(args, ctx) -> int:
    """Repeat a stored run from its recorded configuration (same dataset, document, pipeline and metrics)."""
    original = _get_run(ctx, args.run_id)
    config = rerun_config(original, name=args.name, project_root=ctx.settings.project_root)
    prepared = ctx.runner().prepare(config)
    if original.dataset_sha256 and original.dataset_sha256 != prepared.dataset_sha256:
        print("warning: the dataset has changed since the original run (different SHA-256); "
              "results are not like-for-like", file=sys.stderr)
    if original.document_sha256 and original.document_sha256 != prepared.document_sha256:
        print("warning: the document has changed since the original run (different SHA-256)", file=sys.stderr)

    def report(p: Progress) -> None:
        print(f"[{p.done:>3}/{p.total}] {'ok ' if p.status == 'ok' else 'ERR'} {p.case_id}")

    run = ctx.runner().execute(prepared, progress=None if args.quiet else report)
    print(f"\nRun {run.id}: {run.status} (re-run of {original.id})")
    _print_summary(run)
    return 0 if run.status == "completed" else 2


def cmd_backup(args, ctx) -> int:
    target = backup_store(ctx.settings.db_path, Path(args.out_dir) if args.out_dir else ctx.settings.backups_dir)
    print(f"Backup written and verified: {target} ({target.stat().st_size:,} bytes)")
    return 0


def cmd_restore(args, ctx) -> int:
    backup = Path(args.backup)
    print(f"This replaces the run store {ctx.settings.db_path} with {backup}.")
    print("A safety copy of the current store is written first, so the restore can be undone.")
    if not args.yes:
        print("error: re-run with --yes to proceed (stop the web app first)", file=sys.stderr)
        return 1
    target, safety = restore_store(backup, ctx.settings.db_path, ctx.settings.backups_dir, force=args.force)
    print(f"Restored {target}." + (f" Previous store saved as {safety}." if safety else ""))
    return 0


def cmd_prune(args, ctx) -> int:
    runs = ctx.store.list_runs()
    chosen = select_prunable(runs, keep_last=args.keep_last, older_than_days=args.older_than_days)
    protected = sum(1 for r in runs if "keep" in r.tags)
    if protected:
        print(f"{protected} run(s) tagged 'keep' are never pruned.")
    if not chosen:
        print("Nothing to prune.")
        return 0
    for run in chosen:
        print(f"  {run.id}  {run.status:<11} {run.created_at:%Y-%m-%d}  {run.name}")
    if not args.yes:
        print(f"{len(chosen)} run(s) would be deleted. Re-run with --yes to delete them (consider `ragwb backup`).")
        return 0
    for run in chosen:
        ctx.store.delete_run(run.id)
    print(f"Deleted {len(chosen)} run(s).")
    return 0


def cmd_doctor(settings: Settings) -> int:
    checks = run_doctor(settings)
    marks = {"ok": "ok  ", "warn": "WARN", "fail": "FAIL"}
    for check in checks:
        print(f"[{marks[check.status]}] {check.name:<17} {check.detail}")
    failed = sum(c.status == "fail" for c in checks)
    warned = sum(c.status == "warn" for c in checks)
    print(f"\n{len(checks) - failed - warned} ok, {warned} warning(s), {failed} failure(s)")
    return 1 if failed else 0


def cmd_score(args, ctx) -> int:
    """Score one answer with the chosen metrics, without running a pipeline or storing anything."""
    names = [m.strip() for m in args.metrics.split(",") if m.strip()]
    metrics = build_metrics(names, ctx.settings, judge_model=args.judge_model)
    inp = MetricInput(question=args.question, answer=args.answer, expected_answer=args.expected,
                      contexts=args.context or [])
    for metric in metrics:
        result = metric.evaluate(inp)
        score = f"{result.score:.3f}" if result.score is not None else "-"
        verdict = {True: "pass", False: "fail", None: result.status}[result.passed]
        print(f"{metric_label(metric.name):<28} {score:>6}  {verdict:<7} {result.reason or ''}")
    return 0


MIN_PARTIAL_ID = 4


def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a whole number") from None
    if value < 1:
        raise argparse.ArgumentTypeError("must be 1 or more")
    return value


def _get_run(ctx, run_id: str):
    """The run with this exact id, or the single run matching it as an id prefix, an id suffix (the short id the web app
    shows) or an exact name. Ambiguous or unknown references are errors that say what matched."""
    run = ctx.store.get_run(run_id)
    if run is not None:
        return run
    if len(run_id) >= MIN_PARTIAL_ID:
        runs = ctx.store.list_runs()
        found = [r for r in runs if r.id.startswith(run_id) or r.id.endswith(run_id)] or [
            r for r in runs if r.name == run_id]
        if len(found) == 1:
            return found[0]
        if len(found) > 1:
            shown = ", ".join(r.id for r in found[:5]) + (" ..." if len(found) > 5 else "")
            raise LookupError(f"{run_id!r} matches {len(found)} runs ({shown}); give more of the id.")
    raise LookupError(f"No run with id {run_id!r}. Use 'list' to see run ids.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ragwb",
        description="RAG Evaluation Workbench: evaluate a retrieval-augmented QA pipeline over a dataset.")
    parser.add_argument("--version", action="version", version=f"ragwb {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run an evaluation")
    run.add_argument("--name", default="cli-run", help="human-readable run name")
    run.add_argument("--dataset", help="dataset .jsonl/.csv (default: examples/datasets/honeybees.jsonl)")
    run.add_argument("--document", help="source .pdf/.txt/.md (default: examples/documents/honeybees.pdf)")
    run.add_argument("--provider", choices=["offline", "openai"], default="offline")
    run.add_argument("--pipeline", choices=["rag", "agent"], default="rag")
    run.add_argument("--retriever", choices=["bm25", "embedding", "hybrid", "local", "hybrid-local"], default="bm25",
                     help="embedding/hybrid use an embeddings API (needs OPENAI_API_KEY); local/hybrid-local use a "
                          "local model (needs the optional fastembed package, no key); hybrid = BM25 + dense "
                          "fused by reciprocal rank")
    run.add_argument("-k", type=int, default=3, help="chunks retrieved per query")
    run.add_argument("--metrics", help=f"comma-separated; available: {','.join(METRIC_SPECS)}")
    run.add_argument("--threshold", action="append", metavar="METRIC=VALUE", help="override a pass threshold")
    run.add_argument("--model", help="generator model (openai provider)")
    run.add_argument("--judge-model", help="DeepEval judge model")
    run.add_argument("--workers", type=_positive_int,
                     help="parallel cases (default: 1 offline; RAGWB_MAX_WORKERS with a provider)")
    run.add_argument("--limit", type=_positive_int, help="evaluate only the first N cases (default: all)")
    run.add_argument("--answer-sentences", type=int, default=2, help="offline generator: sentences per answer")
    run.add_argument("--inject-failures", type=float, default=0.0, help="offline: fraction of cases that fail")
    run.add_argument("--min-evidence", type=float, default=0.0,
                     help="offline: abstain unless the answer covers this share (0-1) of the question's terms")
    run.add_argument("--skip-headings", action="store_true", help="drop heading-like blocks from the chunks")
    run.add_argument("--seed", type=int, default=0)
    run.add_argument("--notes")
    run.add_argument("--quiet", action="store_true")
    run.set_defaults(func=cmd_run)

    lst = sub.add_parser("list", help="list stored runs (optionally filtered)")
    lst.add_argument("--search", nargs="+", metavar="WORD", help="words that must all appear in the run's id, name, "
                     "notes, tags, status, provider, retriever or file names")
    lst.add_argument("--tag", help="only runs with this tag")
    lst.add_argument("--status", help="only runs with this status")
    lst.set_defaults(func=cmd_list)
    tag = sub.add_parser("tag", help="add or remove tags on a run")
    tag.add_argument("run_id")
    tag.add_argument("--add", help="comma-separated tags to add")
    tag.add_argument("--remove", help="comma-separated tags to remove")
    tag.set_defaults(func=cmd_tag)
    note = sub.add_parser("note", help="set or clear a run's note")
    note.add_argument("run_id")
    note.add_argument("text", nargs="?")
    note.add_argument("--clear", action="store_true")
    note.set_defaults(func=cmd_note)
    reg = sub.add_parser("regress", help="fail when a candidate run is significantly worse than a baseline run")
    reg.add_argument("baseline")
    reg.add_argument("candidate")
    reg.add_argument("--max-drop", type=float, default=0.02, help="largest tolerated drop in a metric mean (0.02)")
    reg.add_argument("--min-pairs", type=int, default=10, help="paired questions needed to judge a metric (10)")
    reg.add_argument("--max-error-increase", type=float, default=0.05,
                     help="largest tolerated rise in the share of failed cases (0.05)")
    reg.add_argument("--metrics", help="comma-separated metrics to gate (default: all shared)")
    reg.set_defaults(func=cmd_regress)
    user = sub.add_parser("user", help="manage named accounts for the web app (add, remove, set-role, list)")
    user.add_argument("action", choices=["add", "remove", "set-role", "set-password", "list"])
    user.add_argument("--role", choices=list(ROLES), help="with add or set-role: viewer (read-only), editor "
                      "(default: run, tag), admin (also delete runs)")
    user.add_argument("name", nargs="?")
    user.add_argument("--replace", action="store_true", help="with add: change an existing user's password")
    user.add_argument("--password-stdin", action="store_true", help="read the password from standard input")
    user.add_argument("--force", action="store_true", help="remove/demote even the last admin")
    user.set_defaults(func=cmd_user)
    noise = sub.add_parser("judge-noise", help="re-score a run's answers several times to measure judge jitter "
                           "(makes API calls)")
    noise.add_argument("run_id")
    noise.add_argument("--repeats", type=int, default=3, help="scorings per case and metric (2 or more, default 3)")
    noise.add_argument("--metrics", help="comma-separated judge metrics (default: the run's judge metrics)")
    noise.add_argument("--limit", type=_positive_int, help="only the first N cases")
    noise.add_argument("--yes", action="store_true", help="confirm a large number of judge calls")
    noise.set_defaults(func=cmd_judge_noise)
    restore = sub.add_parser("restore", help="replace the run store with a backup (writes a safety copy first)")
    restore.add_argument("backup", help="a file made by `ragwb backup`")
    restore.add_argument("--yes", action="store_true", help="confirm the replacement")
    restore.add_argument("--force", action="store_true", help="replace even if a run looks active")
    restore.set_defaults(func=cmd_restore)
    tuner = sub.add_parser("tune-abstention", help="pick the offline abstention threshold on a development half and "
                           "report it on a held-out half")
    tuner.add_argument("--dataset", nargs="+", help="datasets (default: the bundled examples with unanswerable rows)")
    tuner.add_argument("--document", nargs="+", help="documents, in the same order as --dataset")
    tuner.set_defaults(func=cmd_tune_abstention)
    show = sub.add_parser("show", help="show one run")
    show.add_argument("run_id")
    show.set_defaults(func=cmd_show)
    cmp_ = sub.add_parser("compare", help="paired comparison of run B against run A")
    cmp_.add_argument("run_a")
    cmp_.add_argument("run_b")
    cmp_.set_defaults(func=cmd_compare)
    exp = sub.add_parser("export", help="export a run")
    exp.add_argument("run_id")
    exp.add_argument("--format", choices=EXPORT_FORMATS, default="csv")
    exp.add_argument("--out-dir")
    exp.set_defaults(func=cmd_export)
    val = sub.add_parser("validate", help="validate a dataset file (exit code 1 if it is invalid)")
    val.add_argument("dataset")
    val.set_defaults(func=cmd_validate)
    dele = sub.add_parser("delete", help="delete a stored run")
    dele.add_argument("run_id")
    dele.add_argument("--yes", action="store_true", help="confirm deletion")
    dele.set_defaults(func=cmd_delete)
    sub.add_parser("metrics", help="describe available metrics").set_defaults(func=cmd_metrics)
    imp = sub.add_parser("import", help="import run bundles written by 'export --format json'")
    imp.add_argument("bundles", nargs="+", help="bundle .json files")
    imp.set_defaults(func=cmd_import)
    score = sub.add_parser("score", help="score a single answer with selected metrics (nothing is stored)")
    score.add_argument("--question", required=True)
    score.add_argument("--answer", required=True)
    score.add_argument("--expected", help="reference answer")
    score.add_argument("--context", action="append", help="a context passage (repeatable)")
    score.add_argument("--metrics", default=",".join(DEFAULT_OFFLINE_METRICS))
    score.add_argument("--judge-model")
    score.set_defaults(func=cmd_score)
    tpl = sub.add_parser("labels-template", help="write a CSV for human labelling of a run's cases")
    tpl.add_argument("run_id")
    tpl.add_argument("--out", required=True)
    tpl.add_argument("--force", action="store_true")
    tpl.set_defaults(func=cmd_labels_template)
    cal = sub.add_parser("calibrate",
                         help="compare a metric's pass/fail with labels (agreement, kappa)")
    cal.add_argument("run_id")
    cal.add_argument("--labels", required=True, help=".csv (case_id,human_pass) or .jsonl")
    cal.add_argument("--metric", required=True)
    cal.add_argument("--sweep", action="store_true", help="also show agreement at each pass threshold (0.10-0.95)")
    cal.add_argument("--rescore", action="store_true", help="compute an offline or local-model metric the run does "
                     "not have from its stored answers (no API calls)")
    cal.set_defaults(func=cmd_calibrate)
    sli = sub.add_parser("slices", help="summarise a run per value of a dataset metadata field")
    sli.add_argument("run_id")
    sli.add_argument("--by", required=True, help="metadata field, e.g. type")
    sli.set_defaults(func=cmd_slices)
    rer = sub.add_parser("rerun", help="repeat a stored run from its recorded configuration")
    rer.add_argument("run_id")
    rer.add_argument("--name", help="name for the new run (default: <old name>-rerun)")
    rer.add_argument("--quiet", action="store_true")
    rer.set_defaults(func=cmd_rerun)
    bak = sub.add_parser("backup", help="write a verified copy of the run store")
    bak.add_argument("--out-dir", help="default: <data dir>/backups")
    bak.set_defaults(func=cmd_backup)
    pru = sub.add_parser("prune", help="delete old runs by retention policy (dry run unless --yes)")
    pru.add_argument("--keep-last", type=int, help="always keep the newest N runs")
    pru.add_argument("--older-than-days", type=float, help="select runs created more than D days ago")
    pru.add_argument("--yes", action="store_true", help="actually delete")
    pru.set_defaults(func=cmd_prune)
    sub.add_parser("doctor", help="check the installation, configuration and run store (no network calls)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "doctor":  # must work even when the store or configuration is broken
            return cmd_doctor(load_settings())
        if args.command == "restore":  # the store may be the thing that is broken: do not open it first
            return cmd_restore(args, SimpleNamespace(settings=load_settings()))
        ctx = open_context(load_settings(), console_logging=False)
        return args.func(args, ctx)
    except (BundleError, LabelsError, TagError, UserError, ConfigError, DatasetError, DocumentError, StorageError,
            LookupError,
            ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
