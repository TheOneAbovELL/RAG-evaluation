# Test catalogue

359 test functions (parametrised tests expand to more test cases at run time).
Every test function, with its docstring or, failing that, its first assertion.

## `tests/test_abstention.py` (6)

| Test | Line | What it checks |
|---|---:|---|
| `test_confusion_arithmetic_and_balanced_accuracy` | 25 | `assert c.n_unanswerable == 4 and c.n_answerable == 8` |
| `test_should_abstain_follows_the_reference_answer` | 35 | `assert should_abstain(case("a", ABSTAIN_ANSWER))` |
| `test_split_is_deterministic_disjoint_and_roughly_even` | 41 | `assert (dev, test) == split_cases(cases, salt="doc")` |
| `test_tuning_reports_a_held_out_half_and_is_reproducible` | 50 | `assert first.chosen == again.chosen and first.test_chosen == again.test_chosen` |
| `test_default_grid_covers_zero_to_point_nine` | 63 | `assert THRESHOLDS[0] == 0.0 and THRESHOLDS[-1] == 0.9 and len(THRESHOLDS) == 10` |
| `test_cli_tune_abstention` | 67 | `assert main(["tune-abstention", "--dataset", str(UNANSWERABLE), "--document", str(REAL_PDF)]) == 0` |

## `tests/test_accounts_admin.py` (12)

| Test | Line | What it checks |
|---|---:|---|
| `test_the_last_admin_cannot_be_removed_or_demoted_while_others_exist` | 31 | `assert team.role_of("ada") == "admin" and "ada" in team.names()` |
| `test_force_overrides_the_last_admin_guard_and_a_single_account_is_always_removable` | 41 | `assert users.remove("a", force=True)` |
| `test_set_password_keeps_role_and_checks_the_current_password` | 51 | `assert team.set_password("ada", NEW_PW, current_password=PW)` |
| `test_entries_never_contain_secret_material` | 63 | `assert [e["user"] for e in entries] == ["ada", "eddie", "vera"]` |
| `test_cli_set_password_and_force` | 69 | `assert main(["user", "set-password", "vera", "--password-stdin"]) == 0` |
| `test_a_non_admin_cannot_even_route_to_the_accounts_page` | 79 | — |
| `test_an_admin_can_add_change_reset_and_remove_accounts` | 90 | `assert not at.exception, [e.value for e in at.exception]` |
| `test_the_page_shows_validation_errors_instead_of_crashing` | 124 | `assert not at.exception and any("Usernames" in e.value for e in at.error)` |
| `test_a_user_can_change_their_own_password` | 139 | `assert team.verify("vera", NEW_PW) == "vera" and team.verify("vera", PW) is None` |
| `test_own_mode_hides_other_users_runs_but_not_shared_ones` | 163 | `assert names == {"shared-example", "mine"}` |
| `test_own_mode_shows_everything_to_admins_and_is_off_by_default` | 178 | `assert len(at.dataframe[0].value) == 2` |
| `test_own_mode_does_not_leak_other_users_runs_through_the_settings_run_count` | 192 | `assert not at.exception, [e.value for e in at.exception]` |

## `tests/test_aggregate.py` (6)

| Test | Line | What it checks |
|---|---:|---|
| `test_missing_values_are_excluded_not_zeroed` | 23 | `assert (m.n_scored, m.n_skipped, m.n_error) == (2, 1, 2)` |
| `test_empty_summary` | 35 | `assert s.metrics["m"].mean is None and s.metrics["m"].pass_rate is None` |
| `test_bootstrap_is_deterministic_and_brackets_mean` | 41 | `assert bootstrap_ci(values) == bootstrap_ci(values)` |
| `test_percentile` | 50 | `assert percentile([], 95) is None` |
| `test_paired_comparison_matches_by_question_text` | 56 | `assert c.n_pairs == 2` |
| `test_paired_comparison_significance_flag` | 67 | `assert paired_comparison(a, b, "m").significant` |

## `tests/test_archive_reporting.py` (10)

| Test | Line | What it checks |
|---|---:|---|
| `test_export_import_round_trip` | 44 | `assert import_bundle(other, bundle) == run_id` |
| `test_invalid_bundles_are_rejected` | 62 | — *(parametrised)* |
| `test_duplicate_case_ids_rejected` | 73 | — |
| `test_bundle_summary_is_recomputed_not_trusted` | 82 | `assert other.get_run(two_runs[1].id).summary.metrics["token_f1"].mean == pytest.approx(` |
| `test_exported_bundles_contain_no_absolute_paths` | 93 | `assert payload["run"]["config"]["dataset_path"] == "small.jsonl"` |
| `test_example_paths_become_project_relative` | 102 | `assert config["dataset_path"] == "examples/datasets/honeybees.jsonl"` |
| `test_csv_export_neutralises_formulas` | 119 | `assert rows[0]["question"].startswith("'=") and rows[0]["answer"].startswith("'+")` |
| `test_json_and_markdown_exports` | 126 | `assert payload["format"] == "rag-workbench-run" and payload["run"]["id"] == run.id` |
| `test_write_export_and_safe_filenames` | 143 | `assert path.parent == tmp_path / "out" and path.name == f"{run.id}.md" and path.stat().st_size > 0` |
| `test_summary_and_comparison_frames` | 152 | `assert set(df["run_id"]) == {a.id, b.id}` |

## `tests/test_auth.py` (8)

| Test | Line | What it checks |
|---|---:|---|
| `test_password_comparison` | 13 | `assert password_matches(PASSWORD, PASSWORD)` |
| `test_throttle_locks_after_the_limit_and_recovers` | 28 | `assert throttle.retry_after() == pytest.approx(60)` |
| `test_throttle_reset_clears_failures` | 44 | `assert throttle.retry_after() > 0` |
| `test_settings_never_expose_the_password` | 52 | `assert settings.has_app_password` |
| `test_without_a_password_the_app_opens_directly` | 90 | `assert "password protected" not in shown(at)` |
| `test_protected_app_blocks_every_page_until_sign_in` | 97 | `assert "password protected" in shown(at)` |
| `test_wrong_then_right_password` | 105 | `assert "Incorrect password." in shown(at) and not at.metric` |
| `test_repeated_failures_lock_out_even_the_right_password` | 115 | `assert "Too many failed attempts" in shown(at) and not at.metric` |

## `tests/test_bm25_equivalence.py` (5)

| Test | Line | What it checks |
|---|---:|---|
| `test_scores_are_bit_for_bit_identical_to_the_reference_definition` | 49 | `assert retriever.score(query) == reference_scores(chunks, query)  # exact float equality, not approx` *(parametrised)* |
| `test_repeated_query_terms_count_each_time_as_in_the_reference` | 58 | `assert retriever.score("queen queen queen") == reference_scores(chunks, "queen queen queen")` |
| `test_custom_parameters_are_respected` | 65 | `assert retriever.score("queen honey wax") == reference_scores(chunks, "queen honey wax", k1=2.2, b=0.4)` |
| `test_query_with_no_known_terms_scores_zero_everywhere` | 72 | `assert retriever.score("zzzz qqqq") == [0.0] * 10 and retriever.score("") == [0.0] * 10` |
| `test_ranking_and_ties_are_unchanged` | 77 | `assert [h.chunk_id for h in hits] == ["c0", "c1", "c2"]  # ties break by document order` |

## `tests/test_calibration.py` (13)

| Test | Line | What it checks |
|---|---:|---|
| `test_kappa_hand_computed` | 30 | `assert cohen_kappa(20, 5, 10, 15) == pytest.approx(0.4)` |
| `test_kappa_is_undefined_when_a_rater_never_varies` | 39 | `assert cohen_kappa(0, 0, 0, 0) is None` |
| `test_kappa_bands` | 48 | `assert interpret_kappa(value) == label` *(parametrised)* |
| `test_agreement_properties` | 52 | `assert a.accuracy == pytest.approx(0.7) and a.precision == pytest.approx(0.8) and a.recall == pytest.approx(2 ` |
| `test_calibrate_counts_each_cell_and_reports_what_could_not_be_compared` | 62 | `assert (a.tp, a.fp, a.fn, a.tn) == (1, 1, 1, 1)` |
| `test_parse_label` | 79 | `assert parse_label(raw) is expected` *(parametrised)* |
| `test_parse_label_rejects_unknown_values` | 83 | — |
| `test_load_labels_csv_jsonl_and_blanks` | 88 | `assert load_labels(tmp_path / "l.csv") == {"q1": True, "q2": False}  # blank = unlabelled` |
| `test_load_labels_errors_name_the_line` | 105 | — *(parametrised)* |
| `test_load_labels_file_level_errors` | 112 | — |
| `test_labelling_sheet_round_trips_through_calibration` | 121 | `assert [r["case_id"] for r in rows] == [c.case_id for c in cases]` |
| `test_labelling_sheet_neutralises_spreadsheet_formulas` | 139 | `assert "'=SUM(A1)" in text and "'+1" in text and "'@x" in text` |
| `test_cli_labels_template_and_calibrate` | 148 | `assert main(["run", "--name", "cal", "--metrics", "token_f1,context_recall", "--quiet"]) == 0` |

## `tests/test_calibration_sweep.py` (8)

| Test | Line | What it checks |
|---|---:|---|
| `test_sweep_has_one_row_per_threshold_and_is_perfect_between_the_classes` | 22 | `assert [t for t, _ in rows] == list(DEFAULT_SWEEP) and DEFAULT_SWEEP[0] == 0.1 and DEFAULT_SWEEP[-1] == 0.95` |
| `test_the_row_at_the_stored_threshold_matches_calibrate` | 32 | `assert (row.tp, row.fp, row.fn, row.tn) == (plain.tp, plain.fp, plain.fn, plain.tn)` |
| `test_best_threshold_prefers_the_highest_kappa_then_the_lowest_threshold` | 38 | `assert best is not None and dict(rows)[best].kappa == pytest.approx(1.0)` |
| `test_best_threshold_is_none_when_there_is_nothing_to_compare` | 46 | `assert best_threshold([]) is None` |
| `test_unscored_and_unknown_cases_are_excluded_not_zeroed` | 52 | `assert a.n_compared == 2 and a.n_unscored == 1 and a.n_unknown == 1` |
| `test_cli_sweep_prints_the_table_and_the_warning` | 71 | `assert main(["calibrate", run.id, "--labels", str(labels), "--metric", "token_f1", "--sweep"]) == 0` |
| `test_cli_rescore_computes_an_offline_metric_from_stored_answers` | 78 | `assert main(["calibrate", run.id, "--labels", str(labels), "--metric", "rouge_l"]) == 1  # not in the run` |
| `test_cli_rescore_refuses_judge_metrics_and_unknown_metrics` | 86 | `assert main(["calibrate", run.id, "--labels", str(labels), "--metric", "faithfulness", "--rescore"]) == 1` |

## `tests/test_cli_polish.py` (14)

| Test | Line | What it checks |
|---|---:|---|
| `test_markdown_heading_markup_is_dropped_but_the_words_are_kept` | 11 | `assert texts[0] == "Title Here" and texts[1] == "A subsection"` |
| `test_plain_text_files_keep_a_leading_hash` | 21 | `assert load_chunks(doc)[0].text.startswith("# not markup")` |
| `test_the_bundled_markdown_source_no_longer_leaks_markup_into_the_title_chunk` | 27 | `assert first == "Honeybees: Life Inside the Colony"` |
| `test_runs_can_be_referenced_by_full_id_prefix_short_suffix_or_exact_name` | 45 | `assert main(["show", ref]) == 0, ref` |
| `test_ambiguous_and_unknown_references_are_refused_with_a_useful_message` | 52 | `assert main(["show", common]) == 1` |
| `test_show_prints_tags_and_notes` | 63 | `assert main(["tag", alpha.id, "--add", "baseline,v1"]) == 0` |
| `test_calibrate_wording_does_not_claim_the_labels_are_human` | 74 | `assert main(["calibrate", alpha.id, "--labels", str(labels), "--metric", "token_f1"]) == 0` |
| `test_rescoring_a_metric_that_cannot_be_computed_says_why_instead_of_printing_zeros` | 83 | `assert main(["calibrate", alpha.id, "--labels", str(labels), "--metric", "semantic_similarity", "--rescore"]) ` |
| `test_prune_never_deletes_a_run_tagged_keep` | 103 | `assert main(["tag", alpha.id, "--add", "keep"]) == 0` |
| `test_regress_with_a_metric_neither_run_has_is_an_error_not_a_silent_not_judged` | 119 | `assert main(["regress", alpha.id, beta.id, "--metrics", "nope"]) == 1` |
| `test_workers_and_limit_must_be_positive_whole_numbers` | 128 | `assert exc.value.code == 2 and flag in capsys.readouterr().err` *(parametrised)* |
| `test_start_py_honours_the_no_dotenv_switch` | 134 | `assert start.password_configured(env={}, env_file=env_file)` |
| `test_a_local_model_that_cannot_load_stops_the_run_before_any_case` | 149 | — |
| `test_a_semantic_metric_whose_model_cannot_load_fails_at_build_time` | 165 | — |

## `tests/test_cli_services.py` (9)

| Test | Line | What it checks |
|---|---:|---|
| `test_cli_run_list_show_compare_export` | 14 | `assert main(["run", "--name", "cli-a", "-k", "2", "--limit", "5", "--quiet"]) == 0` |
| `test_cli_errors_are_reported_not_raised` | 30 | `assert main(["run", "--provider", "openai"]) == 1` |
| `test_injected_failures_give_partial_run_exit_code` | 50 | `assert main(["run", "--inject-failures", "1.0", "--limit", "2", "--quiet"]) == 2` |
| `test_module_entry_point_runs_in_a_subprocess` | 55 | `assert proc.returncode == 0, proc.stderr` |
| `test_save_upload_sanitises_names` | 64 | `assert path.parent == settings.uploads_dir.resolve()` |
| `test_redacting_formatter_covers_tracebacks` | 79 | `assert "my-secret-value-123" not in text and "boom with ***" in text` |
| `test_secret_redaction_filter` | 91 | `assert record.getMessage() == "key=*** other=sk-***"` |
| `test_import_command` | 99 | `assert main(["run", "--name", "bundle-me", "--limit", "2", "--quiet"]) == 0` |
| `test_score_command` | 112 | `assert main(["score", "--question", "What do forager bees collect?", "--answer", "Bees collect nectar and poll` |

## `tests/test_config.py` (6)

| Test | Line | What it checks |
|---|---:|---|
| `test_defaults_resolve_inside_project` | 8 | `assert s.default_dataset == PROJECT_ROOT / "examples" / "datasets" / "honeybees.jsonl"` |
| `test_relative_paths_are_resolved_against_project_root` | 17 | `assert s.data_dir == PROJECT_ROOT / "tmpdata"` |
| `test_absolute_path_kept` | 23 | `assert s.data_dir == Path(tmp_path)` |
| `test_numeric_parsing_and_blank_values_ignored` | 28 | `assert s.max_retries == 5` |
| `test_invalid_values_raise_config_error_naming_the_variable` | 42 | `assert next(iter(env)) in str(info.value)` *(parametrised)* |
| `test_secret_never_exposed` | 48 | `assert s.has_openai_key` |

## `tests/test_datasets.py` (12)

| Test | Line | What it checks |
|---|---:|---|
| `test_real_dataset_is_valid` | 13 | `assert report.ok` |
| `test_ids_metadata_and_optional_reference` | 22 | `assert report.ok` |
| `test_blank_lines_ignored_and_bom_accepted` | 32 | `assert report.ok and len(report.cases) == 1` |
| `test_errors_are_reported_with_line_numbers` | 48 | `assert not report.ok` *(parametrised)* |
| `test_duplicate_questions_are_warnings_not_errors` | 55 | `assert report.ok` |
| `test_empty_dataset_is_an_error` | 61 | `assert not report.ok` |
| `test_limits` | 67 | `assert "limit" in str(parse_dataset(b"x" * 101, "d.jsonl", max_bytes=100).errors[0])` |
| `test_non_utf8_and_unsupported_type` | 75 | `assert "not valid UTF-8" in str(parse_dataset(b"\xff\xfe\x00", "d.jsonl").errors[0])` |
| `test_non_ascii_round_trip` | 80 | `assert report.cases[0].question == "Où vivent les abeilles ?"` |
| `test_csv_format_with_extra_columns_as_metadata` | 86 | `assert report.ok` |
| `test_csv_requires_question_column` | 94 | `assert "must include a 'question' column" in str(report.errors[0])` |
| `test_load_dataset_raises_with_summary` | 99 | — |

## `tests/test_documents.py` (5)

| Test | Line | What it checks |
|---|---:|---|
| `test_real_pdf_chunks` | 7 | `assert len(chunks) == 11  # title + one block per paragraph` |
| `test_text_document_split_on_blank_lines` | 17 | `assert [c.text for c in chunks] == ["First para wraps.", "Second para.", "Third."]` |
| `test_long_blocks_are_split_on_sentences` | 25 | `assert len(chunks) > 1` |
| `test_errors` | 34 | — |
| `test_sha256_is_stable` | 54 | `assert file_sha256(path) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"` |

## `tests/test_dotenv_switch.py` (5)

| Test | Line | What it checks |
|---|---:|---|
| `test_the_project_dotenv_is_loaded_by_default` | 14 | `assert config.load_settings().generator_model == "from-dotenv"` |
| `test_ragwb_no_dotenv_skips_it` | 19 | `assert config.load_settings().generator_model == "gpt-4o"  # the default, not the .env value` |
| `test_the_suite_itself_runs_with_the_switch_on` | 24 | `assert os.environ.get("RAGWB_NO_DOTENV") == "1"` |
| `test_importing_the_package_tells_deepeval_not_to_load_dotenv_files_itself` | 30 | Found when a real .env slowed the whole suite: DeepEval auto-loads a .env from the working directory on import. |
| `test_the_test_process_environment_is_not_polluted_by_the_real_project_dotenv` | 50 | A real .env must never leak into the suite (it once paced every test at 10 operations a minute). |

## `tests/test_evaluation_options.py` (14)

| Test | Line | What it checks |
|---|---:|---|
| `test_apostrophes_inside_words_do_not_leave_stray_tokens` | 24 | `assert tokenize("The queen's cells can't wait") == ["the", "queens", "cells", "cant", "wait"]` |
| `test_heading_heuristic` | 38 | `assert is_heading(text) is expected` *(parametrised)* |
| `test_drop_headings_keeps_everything_if_all_blocks_look_like_headings` | 42 | `assert [c.id for c in drop_headings(chunks)] == ["c2"]` |
| `test_example_document_title_is_dropped_but_content_is_kept` | 50 | `assert chunks[0].text.startswith("Honeybees: Life") and len(kept) == len(chunks) - 1` |
| `test_min_evidence_zero_always_answers_when_a_term_matches` | 64 | `assert not is_abstention(generator.generate("Why do bees sing in winter?", passages).answer)` |
| `test_min_evidence_abstains_when_too_little_of_the_question_is_covered` | 69 | `assert any(p.search(answer) for p in ABSTENTION_PATTERNS)` |
| `test_min_evidence_is_validated` | 77 | — *(parametrised)* |
| `test_the_options_reach_the_pipeline_and_change_the_run` | 84 | `assert abstentions(run()) == set()` |
| `test_rrf_fusion_matches_the_formula_and_prefers_agreement` | 115 | `assert scores["b"] == pytest.approx(1 / 62 + 1 / 62, abs=1e-6)` |
| `test_hybrid_validation` | 127 | — |
| `test_hybrid_pipeline_needs_a_key_and_works_with_a_fake_embedding_model` | 134 | `assert len(generation.contexts) == 2 and generation.context_source == "retriever"` |
| `test_slices_group_by_metadata_and_keep_missing_last` | 156 | `assert metadata_keys(results) == ["n", "type"]` |
| `test_metadata_flows_from_the_dataset_to_results_exports_and_the_cli` | 170 | `assert {c.metadata["type"] for c in results} == {"answerable", "unanswerable"}` |
| `test_cli_options_are_passed_through` | 192 | `assert main(["run", "--name", "opt", "--dataset", UNANSWERABLE, "--min-evidence", "0.7", "--skip-headings",` |

## `tests/test_example_corpus.py` (3)

| Test | Line | What it checks |
|---|---:|---|
| `test_dataset_validates` | 19 | `assert report.ok, report.errors` *(parametrised)* |
| `test_document_yields_one_chunk_per_paragraph` | 25 | `assert expected - 1 >= 10` *(parametrised)* |
| `test_dataset_rows` | 34 | `assert len(cases) == 30` *(parametrised)* |

## `tests/test_history.py` (11)

| Test | Line | What it checks |
|---|---:|---|
| `test_normalise_tags_lowercases_dedupes_and_hyphenates_spaces` | 34 | `assert normalise_tags(["Baseline", " baseline ", "Prompt V2", "", "v1.0_rc"]) == ["baseline", "prompt-v2", "v1` |
| `test_invalid_tags_are_rejected` | 39 | — *(parametrised)* |
| `test_too_many_tags_are_rejected` | 44 | — |
| `test_parse_tag_list_accepts_commas_and_spaces` | 49 | `assert parse_tag_list("a, b  c,,d") == ["a", "b", "c", "d"]` |
| `test_notes_are_trimmed_cleared_and_limited` | 54 | `assert validate_notes("  hi  ") == "hi"` |
| `test_search_requires_every_word_and_ignores_case` | 62 | `assert ids(search_runs(runs, "honeybee BASELINE")) == ["r1"]` |
| `test_store_round_trips_tags_and_notes` | 77 | `assert store.get_run("r1").tags == ["a", "b"]` |
| `test_tags_travel_with_an_exported_bundle` | 94 | `assert payload["run"]["tags"] == ["keep-me"]` |
| `test_cli_tag_note_and_filtered_list` | 108 | `assert main(["run", "--name", "alpha-run", "--limit", "2", "--quiet"]) == 0` |
| `test_overview_search_and_tag_filter` | 143 | `assert len(at.dataframe[0].value) == 2` |
| `test_results_page_saves_tags_and_notes_and_rejects_bad_tags` | 162 | `assert not at.exception, [e.value for e in at.exception]` |

## `tests/test_judge_noise.py` (8)

| Test | Line | What it checks |
|---|---:|---|
| `test_steady_judge_has_zero_within_sd_and_flips` | 42 | `assert row.within_sd == pytest.approx(0.0) and row.verdict_flips == 0 and row.n_cases == 12` |
| `test_noisy_judge_is_measured_and_flips_are_counted` | 50 | `assert row.verdict_flips == 1  # only case a crosses the 0.5 threshold between repeats` |
| `test_failed_measurements_are_excluded_not_zeroed` | 59 | `assert row.n_errors == 4 and row.n_cases == 1  # a: 2 usable repeats; b: none` |
| `test_skipped_and_failed_cases_are_not_judged` | 67 | `assert estimate_operations(cases, n_metrics=2, repeats=3) == 6  # only case a counts` |
| `test_repeats_must_be_at_least_two` | 74 | — |
| `test_report_explains_what_the_numbers_mean` | 79 | `assert "within SD" in text and "noise/signal" in text` |
| `test_cli_requires_confirmation_for_many_calls_and_runs_with_a_stand_in_judge` | 95 | `assert main(["judge-noise", judged_run.id, "--metrics", "faithfulness,correctness", "--repeats", "3"]) == 1` |
| `test_cli_without_judge_metrics_explains_what_to_do` | 105 | `assert main(["judge-noise", judged_run.id]) == 1` |

## `tests/test_live.py` (5)

| Test | Line | What it checks |
|---|---:|---|
| `test_live_smoke_script_passes` | 28 | `assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]` |
| `test_smoke_script_refuses_to_spend_without_the_flag` | 43 | `assert result.returncode == 2 and "--yes-spend" in result.stderr` |
| `test_smoke_script_refuses_without_a_key` | 48 | `assert result.returncode == 2 and "OPENAI_API_KEY is not set" in result.stderr` |
| `test_smoke_script_caps_the_number_of_cases` | 54 | `assert result.returncode == 2 and "between 1 and 5" in result.stderr` *(parametrised)* |
| `test_smoke_script_reports_failure_and_exits_nonzero_when_the_api_is_unreachable` | 59 | Whole flow with a fake key and a closed local port (no external traffic): it must fail loudly, not vacuously. |

## `tests/test_local_retrieval.py` (9)

| Test | Line | What it checks |
|---|---:|---|
| `test_local_retriever_ranks_by_similarity_and_is_deterministic` | 41 | `assert [r.rank for r in first] == [1, 2, 3]` |
| `test_the_index_is_built_once_and_lazily` | 50 | `assert built == [] and embedder.batches == 0  # constructing loads nothing` |
| `test_local_retriever_validates_its_inputs` | 61 | — |
| `test_pipeline_builds_local_and_hybrid_local_without_any_key` | 68 | `assert not settings.has_openai_key` |
| `test_local_retrievers_are_refused_with_an_install_hint_when_the_package_is_missing` | 82 | — |
| `test_full_offline_run_with_hybrid_local_retrieval` | 90 | `assert run.status == "completed" and run.summary.n_error == 0` |
| `test_model_cache_lives_under_the_data_dir` | 100 | `assert settings.local_model_dir == settings.data_dir / "models"` |
| `test_real_model_ranks_a_paraphrase_above_an_unrelated_sentence` | 107 | `assert sem.cosine(a, b) > sem.cosine(a, c) + 0.2 and len(a) == 384` |
| `test_metrics_package_exports_still_resolve` | 113 | `assert callable(metrics_pkg.build_metrics)` |

## `tests/test_maintenance.py` (18)

| Test | Line | What it checks |
|---|---:|---|
| `test_doctor_passes_on_a_healthy_installation` | 26 | `assert {c.status for c in checks.values()} == {"ok"}` |
| `test_doctor_reports_an_unwritable_data_directory` | 33 | `assert checks["data directory"].status == "fail"` |
| `test_doctor_detects_a_corrupt_store` | 40 | `assert by_name(run_doctor(settings))["run store"].status == "fail"` |
| `test_doctor_warns_about_abandoned_runs` | 45 | `assert check.status == "warn" and "abandoned" in check.detail` |
| `test_doctor_checks_network_exposure` | 55 | `assert check.status == expected` *(parametrised)* |
| `test_doctor_fails_when_no_address_is_set_and_there_is_no_password` | 63 | `assert check.status == "fail" and "all interfaces" in check.detail` |
| `test_the_projects_own_streamlit_config_is_localhost_only` | 71 | `assert by_name(run_doctor(settings))["network exposure"].status == "ok"` |
| `test_doctor_never_prints_secrets` | 75 | `assert "sk-not-a-real" not in text and "pw-secret-value" not in text and "configured" in text` |
| `test_backup_is_a_consistent_verified_copy` | 83 | `assert target.parent == tmp_path / "backups" and target.name.startswith("runs-")` |
| `test_backup_without_a_store_and_with_a_corrupt_store_fails_cleanly` | 92 | `assert not list((tmp_path / "b").glob("*.db"))  # no half-written backup left behind` |
| `test_prune_policies` | 103 | `assert [r.id for r in select_prunable(runs, keep_last=2)] == ["old", "older"]` |
| `test_prune_never_selects_a_run_that_may_still_be_executing` | 114 | `assert {r.id for r in select_prunable(runs, older_than_days=0)} == {"dead", "done"}` |
| `test_rerun_reproduces_an_offline_run_exactly` | 121 | `assert config.name == "orig-rerun" and config.k == 2 and config.notes == f"Re-run of {original.id}. first try"` |
| `test_rerun_resolves_relative_paths_from_bundles` | 135 | `assert payload["run"]["config"]["dataset_path"] == "examples/datasets/honeybees.jsonl"` |
| `test_cli_doctor_exit_codes` | 149 | `assert main(["doctor"]) == 0` |
| `test_cli_doctor_survives_invalid_configuration` | 159 | `assert main(["doctor"]) == 1  # reported as an error, not a traceback` |
| `test_cli_backup_prune_rerun_and_version` | 165 | `assert exit_info.value.code == 0 and capsys.readouterr().out.startswith("ragwb ")` |
| `test_json_log_format_redacts_secrets` | 190 | `assert payload["level"] == "ERROR" and payload["logger"] == "rag_workbench.x"` |

## `tests/test_metrics.py` (15)

| Test | Line | What it checks |
|---|---:|---|
| `test_exact_match` | 21 | `assert score("exact_match", answer="The Nectar!", expected="nectar").score == 1.0` |
| `test_token_f1_hand_computed` | 27 | `assert r.score == pytest.approx(0.75)` |
| `test_token_f1_counts_multiset_overlap` | 36 | `assert r.score == pytest.approx(0.4)` |
| `test_rouge_l_hand_computed` | 42 | `assert r.score == pytest.approx(2 * p * rec / (p + rec))` |
| `test_context_recall_and_groundedness` | 50 | `assert r.score == pytest.approx(3 / 4)  # bee, collect, nectar found; pollen missing` |
| `test_skips_are_not_zero` | 59 | `assert score("token_f1", answer="x", expected=None).status == "skipped"` |
| `test_custom_threshold_and_errors_are_captured` | 71 | `assert r.threshold == 0.9 and r.passed is False` |
| `test_registry_and_validation` | 83 | `assert set(METRIC_SPECS) == set(LEXICAL_METRICS) \| set(SEMANTIC_SPECS) \| set(JUDGE_SPECS)` |
| `test_judge_metric_uses_fresh_metric_and_threshold` | 112 | `assert (result.status, result.score, result.passed, result.reason) == ("ok", 0.82, False, "supported")` |
| `test_judge_metric_requirements_and_failures` | 127 | `assert metric.evaluate(inp(answer="a", expected=None)).status == "skipped"` |
| `test_build_judge_metric_constructs_deepeval_objects_without_network` | 138 | `assert deepeval_metric.threshold == 0.6` |
| `test_out_of_range_scores_are_errors_but_float_noise_is_absorbed` | 149 | `assert result.status == "error" and result.score is None and "outside [0, 1]" in result.reason` |
| `test_judge_retries_transient_errors_with_backoff` | 178 | `assert result.status == "ok" and result.score == 0.9 and result.cost_usd == 0.002` |
| `test_judge_gives_up_after_the_retry_budget_and_does_not_retry_permanent_errors` | 189 | `assert failed.status == "error" and "RateLimitError" in failed.reason and always.calls == 3` |
| `test_judge_cost_is_aggregated_per_run` | 205 | `assert summarize_run([case(1, 0.01), case(2, 0.02)], ["faithfulness"], {}).total_judge_cost_usd == pytest.appr` |

## `tests/test_packaging.py` (5)

| Test | Line | What it checks |
|---|---:|---|
| `test_checkout_is_recognised_by_its_pyproject` | 7 | `assert (root / "pyproject.toml").is_file() and (root / "src" / "rag_workbench").is_dir()` |
| `test_ragwb_home_overrides_everything` | 13 | `assert config._find_project_root() == (tmp_path / "home").resolve()` |
| `test_without_a_checkout_the_current_directory_is_used` | 18 | Simulates a wheel install: config.py lives somewhere with no pyproject.toml two levels up. |
| `test_wheel_bundles_the_examples_and_they_exist` | 28 | `assert include == {"examples": "rag_workbench/_examples"}` |
| `test_default_example_paths_resolve_to_real_files` | 36 | `assert Path(s.default_dataset).is_file() and Path(s.default_document).is_file()` |

## `tests/test_providers_pipeline.py` (10)

| Test | Line | What it checks |
|---|---:|---|
| `test_extractive_generator_selects_matching_sentences_in_order` | 17 | `assert out.answer.startswith("Forager bees collect nectar, pollen and water.")` |
| `test_extractive_generator_abstains_without_overlap` | 24 | `assert gen.generate("Quantum chromodynamics?", [chunks[0].text]).answer == ABSTAIN_ANSWER` |
| `test_failure_injection_is_deterministic` | 30 | `assert type(info.value) is ProviderError  # permanent: retrying a deterministic failure only adds delay` |
| `test_classify_openai_errors` | 50 | `assert isinstance(classify_openai_error(rate), TransientProviderError)` |
| `test_openai_generator_records_tokens_and_prompt` | 73 | `assert (out.answer, out.prompt_tokens, out.completion_tokens) == ("Nectar.", 50, 3)` |
| `test_openai_generator_errors` | 82 | — |
| `test_rag_pipeline_evaluates_exactly_the_retrieved_chunks` | 92 | `assert [c.chunk_id for c in gen.contexts] == [c.chunk_id for c in retriever.retrieve("What do forager bees col` |
| `test_build_pipeline_validation` | 101 | `assert isinstance(build_pipeline(offline_config(), settings, chunks), RAGPipeline)` |
| `test_build_openai_pipelines_with_key` | 111 | `assert isinstance(rag, RAGPipeline) and rag.model == "gpt-x"` |
| `test_agent_pipeline_captures_real_tool_output_not_self_report` | 126 | `assert gen.answer == "Nectar, pollen and water."` |

## `tests/test_ratelimit.py` (8)

| Test | Line | What it checks |
|---|---:|---|
| `test_no_limit_never_waits` | 31 | `assert [lim.acquire() for _ in range(5)] == [0.0] * 5 and clock.sleeps == []` |
| `test_calls_are_spaced_evenly` | 36 | `assert waits == [0.0, 2.0, 2.0, 2.0] and clock.sleeps == [2.0, 2.0, 2.0]` |
| `test_idle_time_does_not_bank_a_burst` | 42 | `assert lim.acquire() == 0.0  # the first call after idling is free...` |
| `test_invalid_limits_are_rejected` | 50 | — |
| `test_threads_share_one_budget` | 57 | `assert len(stamps) == 40 and elapsed >= 0.035  # 40 operations cannot finish faster than ~39 intervals` |
| `test_limiter_for_returns_one_shared_instance_per_setting` | 78 | `assert limiter_for(12.5) is limiter_for(12.5)` |
| `test_setting_is_read_from_the_environment_and_validated` | 84 | `assert load_settings({"RAGWB_MAX_REQUESTS_PER_MINUTE": "20"}, dotenv=False).max_requests_per_minute == 20` |
| `test_judge_metric_waits_for_its_slot_before_each_measurement` | 93 | `assert [round(b - a, 1) for a, b in itertools.pairwise(calls)] == [2.0, 2.0]` |

## `tests/test_regression.py` (10)

| Test | Line | What it checks |
|---|---:|---|
| `test_clear_drop_is_a_regression` | 36 | `assert v == "regression" and report.exit_code == EXIT_REGRESSION` |
| `test_identical_runs_pass` | 42 | `assert v == "ok" and report.exit_code == EXIT_OK and "PASS" in format_regression(report)` |
| `test_clear_gain_is_reported_as_improved_and_passes` | 47 | `assert v == "improved" and report.exit_code == EXIT_OK` |
| `test_noisy_drop_is_possible_not_a_failure` | 52 | `assert v == "possible" and report.exit_code == EXIT_OK` |
| `test_drop_inside_the_tolerance_is_ok` | 60 | `assert v == "ok"` |
| `test_too_few_pairs_means_not_judged_and_does_not_pass` | 65 | `assert v == "insufficient" and report.exit_code == EXIT_UNJUDGED` |
| `test_no_shared_metrics_is_not_judged` | 71 | `assert report.findings == [] and report.exit_code == EXIT_UNJUDGED` |
| `test_more_failures_is_a_regression_even_if_scores_match` | 76 | `assert report.error_regression and report.exit_code == EXIT_REGRESSION` |
| `test_metric_filter_limits_what_is_gated` | 85 | `assert [f.metric for f in report.findings] == ["n"]` |
| `test_cli_regress_exit_codes` | 93 | `assert main(["run", "--name", "wide", "-k", "3", "--quiet"]) == 0` |

## `tests/test_restore_concurrency.py` (11)

| Test | Line | What it checks |
|---|---:|---|
| `test_restore_round_trip_with_a_safety_copy` | 26 | `assert {r.id for r in store.list_runs()} == {first.id, second.id}` |
| `test_restore_refuses_bad_backups_and_changes_nothing` | 42 | `assert settings.db_path.read_bytes() == before  # every refusal left the live store untouched` |
| `test_restore_refuses_while_a_run_is_active_unless_forced` | 66 | `assert [r.name for r in RunStore(settings.db_path).list_runs()] == ["done"]` |
| `test_a_run_that_stopped_heartbeating_does_not_block_a_restore` | 76 | — |
| `test_restore_migrates_an_older_schema` | 85 | `assert run is not None and run.tags == []` |
| `test_cli_restore_requires_confirmation` | 103 | `assert main(["backup", "--out-dir", str(tmp_path / "bk")]) == 0` |
| `test_several_processes_can_use_one_store_at_the_same_time` | 117 | Four CLI processes run evaluations against the same data directory while a fifth keeps reading it. |
| `test_restore_repairs_an_unreadable_store_and_keeps_a_raw_copy` | 140 | The case the runbook sends operators to: the live runs.db is damaged, so no command that opens it can work. |
| `test_two_backups_in_the_same_second_do_not_collide` | 156 | `assert len(paths) == 5` |
| `test_restore_reports_a_store_held_open_by_another_process` | 162 | `assert settings.db_path.read_bytes() == before and not settings.db_path.with_suffix(".restoring").exists()` |
| `test_backup_names_stay_unique_even_when_the_clock_does_not_move` | 176 | Found by the final verification run: a coarse clock gave two quick backups the same timestamp. |

## `tests/test_retrieval.py` (7)

| Test | Line | What it checks |
|---|---:|---|
| `test_bm25_score_matches_hand_computation` | 13 | `assert scores[0] == pytest.approx(expected)` |
| `test_bm25_ranks_relevant_chunk_first` | 27 | `assert hits[0].chunk_id == "p1-b2"` |
| `test_bm25_is_deterministic_with_ties` | 35 | `assert [h.chunk_id for h in hits] == ["c1", "c2", "c3"]  # all zero: document order` |
| `test_k_larger_than_corpus_and_invalid_k` | 41 | `assert len(r.retrieve("bees", 50)) == len(chunks)` |
| `test_embedding_retriever_is_lazy_and_maps_ids` | 50 | `assert created == []  # nothing built at construction time` |
| `test_embedding_errors_are_classified_for_retry` | 70 | — |
| `test_real_client_classes_accept_the_parameters_we_pass` | 89 | Construct the real LangChain OpenAI clients (no request is made) to catch parameter-name drift. |

## `tests/test_retry_hints.py` (8)

| Test | Line | What it checks |
|---|---:|---|
| `test_retry_after_header_is_carried_on_the_classified_error` | 29 | `assert isinstance(mapped, TransientProviderError) and mapped.retry_after_s == 12.0` |
| `test_a_rate_limit_hidden_inside_a_tenacity_retry_error_is_recognised_as_transient` | 37 | `assert isinstance(mapped, TransientProviderError)` |
| `test_a_raise_from_chain_is_unwrapped_too` | 43 | `assert isinstance(classify_openai_error(outer), TransientProviderError)` |
| `test_a_connection_error_caused_by_a_transport_error_is_still_transient` | 53 | Found in a live run: the SDK error's own __cause__ (an httpx error) must not be unwrapped past the SDK error. |
| `test_unrelated_wrapped_errors_are_not_classified` | 67 | `assert classify_openai_error(wrapped_in_retry_error(ValueError("bad json"))) is None` |
| `test_permanent_errors_stay_permanent_when_wrapped` | 72 | `assert isinstance(mapped, ProviderError) and not isinstance(mapped, TransientProviderError)` |
| `test_backoff_follows_the_hint_but_is_capped` | 79 | `assert backoff_delay(1.0, 1, None, jitter=no_jitter) == 1.0` |
| `test_judge_waits_for_the_providers_retry_after_before_retrying` | 88 | `assert result.status == "ok" and len(calls) == 2` |

## `tests/test_roles.py` (10)

| Test | Line | What it checks |
|---|---:|---|
| `test_roles_are_stored_and_default_to_editor` | 29 | `assert users.role_of("a") == DEFAULT_ROLE == "editor" and users.role_of("b") == "admin"` |
| `test_unknown_roles_are_rejected_and_unrecognised_stored_roles_get_least_access` | 38 | `assert users.role_of("a") == "viewer"  # a tampered or future role never grants more access` |
| `test_set_role` | 54 | `assert users.set_role("A", "admin") and users.role_of("a") == "admin"` |
| `test_cli_roles` | 63 | `assert main(["user", "add", "carol", "--role", "viewer", "--password-stdin"]) == 0` |
| `test_a_viewer_can_browse_but_not_start_runs_edit_or_delete` | 78 | `assert "Signed in as **vera** (viewer)" in shown(at)` |
| `test_an_editor_can_run_and_tag_but_not_delete` | 95 | `assert store.get_run(run.id).tags == ["reviewed"]` |
| `test_an_admin_can_delete` | 111 | `assert store.get_run(run.id) is None` |
| `test_removing_a_user_ends_their_open_session_on_the_next_page_load` | 124 | `assert at.metric  # signed in` |
| `test_a_role_change_applies_to_an_open_session_without_signing_in_again` | 133 | `assert not at.text_input(key=f"tags_{run.id}").disabled` |
| `test_without_accounts_everyone_keeps_full_access` | 145 | `assert not at.text_input(key=f"tags_{run.id}").disabled` |

## `tests/test_runner.py` (16)

| Test | Line | What it checks |
|---|---:|---|
| `test_offline_end_to_end_on_the_real_dataset` | 20 | `assert run.status == "completed" and run.n_cases == 20` |
| `test_offline_runs_are_reproducible` | 35 | `assert a.id != b.id` |
| `test_missing_reference_skips_reference_metrics` | 46 | `assert q4.metrics["token_f1"].status == "skipped"` |
| `test_partial_and_failed_statuses` | 54 | `assert run.status == "partial" and run.summary.n_error == 1` |
| `test_transient_errors_are_retried_with_backoff` | 67 | `assert case.status == "ok" and case.attempts == 3` |
| `test_retries_give_up` | 82 | `assert case.status == "error" and case.attempts == 3 and "gave up after 3 attempts" in case.error` |
| `test_unexpected_exceptions_do_not_abort_the_run` | 90 | `assert run.status == "partial"` |
| `test_cancellation_event_stops_and_records_progress` | 97 | `assert run.status == "cancelled"` |
| `test_exception_in_progress_callback_marks_run_cancelled` | 111 | `assert run.status == "cancelled" and store.count_case_results(run.id) == 1` |
| `test_parallel_execution_keeps_every_case` | 124 | `assert run.status == "completed" and len(results) == 20` |
| `test_validation_happens_before_a_run_is_created` | 135 | `assert store.list_runs() == []` |
| `test_limit_and_cost` | 148 | `assert run.n_cases == 2` |
| `test_run_ids_are_safe_and_unique` | 159 | `assert len(ids) == 20` |
| `test_demo_runs_are_genuine_and_reproducible` | 165 | `assert set(runs) == {"k1", "k3", "k5", "unanswerable", "failures"}` |
| `test_a_hung_case_is_abandoned_after_the_time_limit` | 178 | `assert case.status == "error" and "time limit" in case.error` |
| `test_prices_are_stored_with_the_run` | 203 | `assert run.config["prices_usd_per_mtok"] == {"input": 2.0, "output": 10.0}` |

## `tests/test_semantic.py` (10)

| Test | Line | What it checks |
|---|---:|---|
| `test_cosine_basics` | 38 | `assert sem.cosine([1, 0], [1, 0]) == pytest.approx(1.0)` |
| `test_similarity_is_high_for_shared_words_and_low_for_unrelated` | 48 | `assert same.status == "ok" and same.score == pytest.approx(1.0) and same.passed is True` |
| `test_context_recall_uses_the_best_chunk` | 57 | `assert result.status == "ok" and result.score > 0.8 and "chunk 2 of 2" in result.reason` |
| `test_requirements_are_enforced_by_the_shared_wrapper` | 64 | `assert sim.evaluate(MetricInput("q", "a", None, [])).status == "skipped"  # no reference` |
| `test_embedder_failure_is_an_error_result_not_a_crash` | 71 | `assert result.status == "error" and "model file corrupt" in (result.reason or "")` |
| `test_the_embedder_is_created_once_and_lazily` | 81 | `assert created == []  # nothing loaded at construction` |
| `test_selecting_a_semantic_metric_without_fastembed_is_refused` | 92 | — |
| `test_full_run_with_semantic_metrics_through_the_runner` | 98 | `assert run.status == "completed"` |
| `test_real_loader_refuses_without_the_package` | 112 | — |
| `test_build_metrics_wires_the_configured_model` | 118 | `assert seen == ["my/model"]` |

## `tests/test_set_api_key.py` (9)

| Test | Line | What it checks |
|---|---:|---|
| `test_only_the_key_line_changes` | 28 | `assert env_file.read_text(encoding="utf-8") == (` |
| `test_a_missing_key_line_is_added_and_a_missing_file_is_created_from_the_example` | 34 | `assert target.read_text(encoding="utf-8") == f"# template\nOPENAI_API_KEY={NEW}\n# RAGWB_MAX_RETRIES=3\n"` |
| `test_implausible_keys_are_refused_without_echoing_them` | 47 | `assert bad.strip() == "" or bad not in str(exc.value)` *(parametrised)* |
| `test_main_reads_stdin_updates_the_file_and_never_prints_the_key` | 53 | `assert tool.main(["--stdin"], env_file=env_file) == 0` |
| `test_main_refuses_a_bad_key_and_leaves_the_file_alone` | 62 | `assert tool.main(["--stdin"], env_file=env_file) == 1` |
| `test_remove_blanks_the_key_and_keeps_everything_else` | 69 | `assert tool.main(["--remove"], env_file=env_file) == 0` |
| `test_read_setting_ignores_comments_and_quotes` | 75 | `assert tool.read_setting(path, "OPENAI_API_KEY") is None` |
| `test_check_reports_a_refused_key_without_leaking_it` | 82 | `assert (status, message) == (401, "rejected") and OLD not in message  # ...but never reports it` |
| `test_check_without_a_key_makes_no_request` | 94 | `assert tool.check_key(path) == (None, "no key is set in .env")` |

## `tests/test_start.py` (10)

| Test | Line | What it checks |
|---|---:|---|
| `test_local_hosts_never_need_a_password` | 26 | `assert start.host_problem(host, password_set=False) is None` *(parametrised)* |
| `test_exposed_hosts_are_refused_without_a_password_and_allowed_with_one` | 31 | `assert problem and "RAGWB_APP_PASSWORD" in problem and host in problem` *(parametrised)* |
| `test_password_is_detected_in_the_environment_and_in_dotenv` | 37 | `assert not start.password_configured(env={}, env_file=env_file)` |
| `test_accounts_are_detected_from_the_users_file` | 50 | `assert not start.accounts_configured(env=env)` |
| `test_tls_options_must_come_as_a_valid_pair` | 63 | `assert start.tls_problem(None, None) is None` |
| `test_exposed_host_message_mentions_accounts` | 73 | `assert "ragwb user add" in start.host_problem("0.0.0.0", password_set=False)` |
| `test_free_port_skips_a_port_that_is_in_use` | 77 | `assert start.free_port(taken) != taken` |
| `test_wait_until_ready_sees_a_healthy_server_and_stops_when_the_process_died` | 95 | `assert start.wait_until_ready(1, Dead(), timeout=5) is False` |
| `test_the_launcher_refuses_an_exposed_host_without_a_password_before_touching_anything` | 117 | `assert result.returncode != 0 and "refusing to listen" in result.stderr` |
| `test_help_lists_every_option` | 126 | `assert result.returncode == 0` |

## `tests/test_storage.py` (9)

| Test | Line | What it checks |
|---|---:|---|
| `test_round_trip_preserves_unicode_and_order` | 20 | `assert run.name == "Run ü" and run.config["note"] == "蜂蜜"` |
| `test_duplicates_and_missing_runs_are_errors` | 31 | — |
| `test_finish_list_delete_cascade` | 44 | `assert store.get_run("a").status == "completed" and store.get_run("a").finished_at is not None` |
| `test_recover_interrupted_only_touches_stale_runs` | 57 | `assert store.recover_interrupted() == 1` |
| `test_case_commits_refresh_the_heartbeat` | 69 | `assert store.recover_interrupted() == 0` |
| `test_schema_v1_store_is_migrated` | 77 | `assert store.get_run("old").tags == []` |
| `test_sqlite_errors_become_storage_errors` | 97 | — |
| `test_newer_schema_is_refused` | 104 | — |
| `test_unwritable_location_reports_storage_error` | 113 | — |

## `tests/test_text.py` (8)

| Test | Line | What it checks |
|---|---:|---|
| `test_stem` | 18 | `assert stem(word) == expected` *(parametrised)* |
| `test_tokenize_is_unicode_aware` | 22 | `assert tokenize("Abejas RÉINE 蜜蜂!") == ["abejas", "réine", "蜜蜂"]` |
| `test_content_tokens_drop_stopwords_and_stem` | 26 | `assert content_tokens("What do the workers build?") == ["worker", "build"]` |
| `test_squad_normalize_matches_reference_behaviour` | 30 | `assert squad_normalize("The  Queen's diet: ROYAL, jelly!") == "queens diet royal jelly"` |
| `test_normalize_whitespace_collapses_newlines` | 34 | `assert normalize_whitespace(" a\nb\r\n\tc  ") == "a b c"` |
| `test_split_sentences` | 38 | `assert split_sentences("Bees fly. They make honey! Do they sleep? Yes.") == [` |
| `test_is_abstention` | 51 | `assert is_abstention(answer) is expected` *(parametrised)* |
| `test_squad_normalize_drops_unicode_punctuation` | 55 | `assert squad_normalize("The queen’s diet — “jelly”…") == "queens diet jelly"` |

## `tests/test_ui.py` (9)

| Test | Line | What it checks |
|---|---:|---|
| `test_overview_empty_state_then_runs` | 68 | `assert at.title[0].value == "RAG Evaluation Workbench"` |
| `test_overview_lists_stored_runs` | 77 | `assert {m.label: m.value for m in at.metric}["Runs stored"] == "2"` |
| `test_new_run_journey_offline_then_results_and_compare` | 85 | `assert "20 cases · 20 with reference answers" in texts(at)` |
| `test_new_run_blocks_invalid_inputs` | 118 | `assert "This dataset cannot be used" in texts(at)` |
| `test_openai_option_explains_missing_key` | 129 | `assert not at.exception` |
| `test_failure_injection_shows_partial_run` | 138 | `assert not at.exception, [e.value for e in at.exception]` |
| `test_results_for_imported_run_show_provenance` | 148 | `assert "Imported run" in texts(at)` |
| `test_data_and_settings_pages` | 158 | `assert labels["Cases"] == "20" and labels["Errors"] == "0"` |
| `test_imported_config_values_are_html_escaped` | 169 | `assert "&lt;img src=x onerror=alert(1)&gt;" in html and "<img" not in html` |

## `tests/test_users.py` (17)

| Test | Line | What it checks |
|---|---:|---|
| `test_add_verify_and_normalisation` | 25 | `assert users.add("  Alice ", PW) == "alice"` |
| `test_passwords_are_never_stored` | 34 | `assert PW not in raw` |
| `test_same_password_gets_a_different_salt_and_hash` | 41 | `assert entries["alice"]["salt"] != entries["bob"]["salt"]` |
| `test_bad_usernames_are_rejected` | 50 | — *(parametrised)* |
| `test_password_length_limits_and_duplicates` | 55 | `assert users.verify("alice", PW) is None` |
| `test_remove_and_list` | 68 | `assert users.names() == [] and not users.has_users()` |
| `test_rerun_does_not_inherit_the_original_starter` | 79 | `assert rerun_config(run).started_by is None` |
| `test_a_damaged_users_file_locks_rather_than_opens` | 89 | `assert users.has_users()  # fail closed` |
| `test_oversize_password_is_refused_and_unknown_users_still_pay_for_hashing` | 97 | `assert users.verify("alice", "x" * 10_000) is None` |
| `test_throttle_set_is_per_username_with_a_loose_global_limit` | 110 | `assert throttles.retry_after("alice") > 0` |
| `test_settings_report_accounts_without_exposing_anything` | 128 | `assert not settings.has_users and not settings.login_required` |
| `test_cli_user_commands` | 137 | `assert main(["user", "list"]) == 0` |
| `test_accounts_block_the_app_until_a_valid_sign_in` | 187 | `assert "Sign in with your account" in shown(at) and not at.metric` |
| `test_account_login_wins_over_the_shared_password` | 203 | `assert "Sign in with your account" in shown(new_app())` |
| `test_repeated_failures_lock_that_username` | 209 | `assert "Too many failed attempts" in shown(at) and not at.metric` |
| `test_sign_out_returns_to_the_login_form` | 217 | `assert "Sign in with your account" in shown(at) and not at.metric` |
| `test_runs_started_in_the_app_record_who_started_them` | 225 | `assert not at.exception, [e.value for e in at.exception]` |
