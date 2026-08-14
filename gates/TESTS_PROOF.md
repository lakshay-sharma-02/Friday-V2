# TESTS_PROOF — automated test suite for Friday

Status date: 2026-08-14T03:41:49+00:00.

The full unittest suite over every layer and feature: registry,
observability (redaction / rotation / log_transform), the executor
(ref resolver, retry policy, blocked primitives), the planner
(validate_plan / catalog / facts), L2 checks, window protected-
classes, the dev dangerous-gate, gmail/notify/secrets, and the
watch loop. All side-effect boundaries are mocked - the suite
never sends, launches, clicks or touches the compositor.

## Verdict: PASS

Ran 463 tests: 463 passed, 0 failed, 0 errors.

## Raw output

```
test_catches_test_passes_but_impl_wrong (test_automated_gate.TestBuildVerify.test_catches_test_passes_but_impl_wrong)
The draft's own test passes (isinstance str) yet its impl returns ... ok
test_correct_draft_passes_both_stages (test_automated_gate.TestBuildVerify.test_correct_draft_passes_both_stages) ... ok
test_correct_write_draft_passes_build_verify (test_automated_gate.TestBuildVerify.test_correct_write_draft_passes_build_verify)
A genuinely correct write_text draft passes the write probes: ... ok
test_not_applicable_class_is_honestly_flagged (test_automated_gate.TestBuildVerify.test_not_applicable_class_is_honestly_flagged)
demo.adder has no safe real target - the gate does NOT pretend it ... ok
test_probe_family_detection (test_automated_gate.TestBuildVerify.test_probe_family_detection)
Fix 2: the probe family is derived from the DRAFT's declared ... ok
test_write_draft_that_appends_when_it_should_overwrite_is_caught (test_automated_gate.TestBuildVerify.test_write_draft_that_appends_when_it_should_overwrite_is_caught)
The draft's own test passes (writes once, checks content) but the ... ok
test_write_draft_without_append_param_still_passes (test_automated_gate.TestBuildVerify.test_write_draft_without_append_param_still_passes)
The append probe is conditional on the DRAFT declaring append - ... ok
test_wrong_return_shape_rejected (test_automated_gate.TestBuildVerify.test_wrong_return_shape_rejected)
Returns a Path object (not str) - the present-name probe's exact ... ok
test_clean_impl_passes_all (test_automated_gate.TestCombinedAst.test_clean_impl_passes_all) ... ok
test_dead_arg_surfaces (test_automated_gate.TestCombinedAst.test_dead_arg_surfaces) ... ok
test_subprocess_call_surfaces_even_with_allowed_import (test_automated_gate.TestCombinedAst.test_subprocess_call_surfaces_even_with_allowed_import) ... ok
test_missing_function_flagged (test_automated_gate.TestContractFunction.test_missing_function_flagged) ... ok
test_present_function_clean (test_automated_gate.TestContractFunction.test_present_function_clean) ... ok
test_clean_impl_no_danger (test_automated_gate.TestDangerChecks.test_clean_impl_no_danger) ... ok
test_dangerous_calls_rejected (test_automated_gate.TestDangerChecks.test_dangerous_calls_rejected) ... ok
test_ignored_argument_flagged (test_automated_gate.TestDeadArgs.test_ignored_argument_flagged) ... ok
test_used_arguments_clean (test_automated_gate.TestDeadArgs.test_used_arguments_clean) ... ok
test_credentials_and_overrides_stripped (test_automated_gate.TestEnvSanitization.test_credentials_and_overrides_stripped) ... ok
test_absolute_open_write_rejected (test_automated_gate.TestFsScope.test_absolute_open_write_rejected) ... ok
test_dotdot_traversal_rejected (test_automated_gate.TestFsScope.test_dotdot_traversal_rejected) ... ok
test_dynamic_path_not_statically_flagged (test_automated_gate.TestFsScope.test_dynamic_path_not_statically_flagged) ... ok
test_home_expansion_rejected (test_automated_gate.TestFsScope.test_home_expansion_rejected) ... ok
test_os_open_absolute_rejected (test_automated_gate.TestFsScope.test_os_open_absolute_rejected)
os.open(path, flags) with a WRITE flag - the path must stay in the sandbox. ... ok
test_os_open_readonly_absolute_allowed (test_automated_gate.TestFsScope.test_os_open_readonly_absolute_allowed)
os.open(path, os.O_RDONLY) is a READ - reads are a documented ... ok
test_os_remove_absolute_rejected (test_automated_gate.TestFsScope.test_os_remove_absolute_rejected) ... ok
test_path_join_traversal_rejected (test_automated_gate.TestFsScope.test_path_join_traversal_rejected) ... ok
test_path_method_absolute_write_rejected (test_automated_gate.TestFsScope.test_path_method_absolute_write_rejected) ... ok
test_path_method_relative_write_allowed (test_automated_gate.TestFsScope.test_path_method_relative_write_allowed) ... ok
test_path_open_keyword_mode_absolute_rejected (test_automated_gate.TestFsScope.test_path_open_keyword_mode_absolute_rejected)
Path.open(mode=...) with the mode as a KEYWORD is a write too. ... ok
test_read_absolute_not_flagged (test_automated_gate.TestFsScope.test_read_absolute_not_flagged)
The sandbox FS check targets WRITES; reads of local files remain ... ok
test_relative_write_allowed (test_automated_gate.TestFsScope.test_relative_write_allowed) ... ok
test_allowed_imports_pass (test_automated_gate.TestImportAllowlist.test_allowed_imports_pass) ... ok
test_derived_from_real_primitives (test_automated_gate.TestImportAllowlist.test_derived_from_real_primitives)
The allowlist must cover every import the shipped L1 primitives ... ok
test_unseen_import_rejected (test_automated_gate.TestImportAllowlist.test_unseen_import_rejected) ... ok
test_bad_import_fails_before_any_signature_consideration (test_automated_gate.TestRunAutomatedGate.test_bad_import_fails_before_any_signature_consideration) ... ok
test_clean_proposal_passes_and_reports_to_rationale (test_automated_gate.TestRunAutomatedGate.test_clean_proposal_passes_and_reports_to_rationale) ... ok
test_dangerous_test_file_rejected_before_execution (test_automated_gate.TestRunAutomatedGate.test_dangerous_test_file_rejected_before_execution)
The file the sandbox EXECUTES is itself AST-checked - a clean ... ok
test_dead_argument_fails (test_automated_gate.TestRunAutomatedGate.test_dead_argument_fails) ... ok
test_gate_allows_relative_write_inside_sandbox (test_automated_gate.TestRunAutomatedGate.test_gate_allows_relative_write_inside_sandbox)
A relative write lands in the sandbox cwd and is both allowed by ... ok
test_gate_rejects_absolute_write_in_test_file (test_automated_gate.TestRunAutomatedGate.test_gate_rejects_absolute_write_in_test_file)
A test.py that writes an absolute path is rejected before the ... ok
test_draft_is_what_gets_tested_not_the_registered_function (test_automated_gate.TestSandbox.test_draft_is_what_gets_tested_not_the_registered_function)
The sandbox injects the DRAFT over the real module - a draft that ... ok
test_failing_test_rejected (test_automated_gate.TestSandbox.test_failing_test_rejected) ... ok
test_missing_test_file_is_documented_skip (test_automated_gate.TestSandbox.test_missing_test_file_is_documented_skip) ... ok
test_package_level_import_style_sees_the_draft (test_automated_gate.TestSandbox.test_package_level_import_style_sees_the_draft)
Regression (2026-08-13 live): a draft whose test uses the ... ok
test_passing_test_runs_in_sandbox (test_automated_gate.TestSandbox.test_passing_test_runs_in_sandbox) ... ok
test_click_context_destroyed_counts_as_navigated (test_browser.TestClickNavigationSettle.test_click_context_destroyed_counts_as_navigated) ... ok
test_timed_out_click_that_navigated_is_reported_navigated (test_browser.TestClickNavigationSettle.test_timed_out_click_that_navigated_is_reported_navigated) ... ok
test_timed_out_click_without_navigation_raises (test_browser.TestClickNavigationSettle.test_timed_out_click_without_navigation_raises) ... ok
test_empty_query_precondition (test_browser.TestFindLocator.test_empty_query_precondition) ... ok
test_falls_through_chain_to_text (test_browser.TestFindLocator.test_falls_through_chain_to_text) ... ok
test_malformed_selector_falls_through_chain (test_browser.TestFindLocator.test_malformed_selector_falls_through_chain)
A locator() that raises (malformed selector) must fall through to ... ok
test_malformed_selector_then_nothing_matches (test_browser.TestFindLocator.test_malformed_selector_then_nothing_matches) ... ok
test_no_page_raises (test_browser.TestFindLocator.test_no_page_raises) ... ok
test_nothing_matches_raises_with_tried_list (test_browser.TestFindLocator.test_nothing_matches_raises_with_tried_list) ... ok
test_selector_wins_when_visible (test_browser.TestFindLocator.test_selector_wins_when_visible) ... ok
test_goto_rejects_non_http (test_browser.TestGotoAndUpload.test_goto_rejects_non_http) ... ok
test_upload_file_missing_path (test_browser.TestGotoAndUpload.test_upload_file_missing_path) ... ok
test_no_page_raises (test_browser.TestReadPageText.test_no_page_raises) ... ok
test_returns_inner_text (test_browser.TestReadPageText.test_returns_inner_text) ... ok
test_fill_failure_falls_back_to_click_and_keystrokes (test_browser.TestTypeTextFallback.test_fill_failure_falls_back_to_click_and_keystrokes)
When loc.fill raises (not a fillable input), type_text clicks the ... ok
test_fill_field_actually_fills (test_browser.TestTypingAndSecretDiscipline.test_fill_field_actually_fills) ... ok
test_fill_field_is_silent (test_browser.TestTypingAndSecretDiscipline.test_fill_field_is_silent)
The credential fill path emits NO line carrying the secret - the ... ok
test_type_text_logs_its_text_argument (test_browser.TestTypingAndSecretDiscipline.test_type_text_logs_its_text_argument) ... ok
test_args_shape_never_leaks_values (test_capability_gaps.TestExecutorGaps.test_args_shape_never_leaks_values)
The recorded shape is type tags only - secrets never ride a gap. ... ok
test_blocked_by_design_primitive_records_gap (test_capability_gaps.TestExecutorGaps.test_blocked_by_design_primitive_records_gap)
EXECUTOR_BLOCKED (window.shutdown) is also recorded - honestly ... ok
test_successful_step_produces_no_gap (test_capability_gaps.TestExecutorGaps.test_successful_step_produces_no_gap)
(c) A normal successful run records nothing. ... ok
test_unknown_module_primitive_also_records (test_capability_gaps.TestExecutorGaps.test_unknown_module_primitive_also_records)
A primitive whose MODULE does not exist is the same class of gap. ... ok
test_unknown_primitive_produces_one_gap_record (test_capability_gaps.TestExecutorGaps.test_unknown_primitive_produces_one_gap_record)
(a) An unknown/unregistered primitive -> exactly ONE gap record ... ok
test_group_by_primitive_dedupes_preserving_order (test_capability_gaps.TestProcessing.test_group_by_primitive_dedupes_preserving_order) ... ok
test_mark_processed_is_idempotent (test_capability_gaps.TestProcessing.test_mark_processed_is_idempotent) ... ok
test_record_never_raises_on_unwritable_file (test_capability_gaps.TestProcessing.test_record_never_raises_on_unwritable_file) ... ok
test_allowlist_refusal_produces_gap_record (test_capability_gaps.TestWatcherGaps.test_allowlist_refusal_produces_gap_record)
(b) A watcher allowlist refusal records a gap per forbidden ... ok
test_allowlist_refusal_records_per_forbidden_primitive (test_capability_gaps.TestWatcherGaps.test_allowlist_refusal_records_per_forbidden_primitive) ... ok
test_passing_trigger_produces_no_gap (test_capability_gaps.TestWatcherGaps.test_passing_trigger_produces_no_gap) ... ok
test_browser_has_text (test_checks.TestBrowserChecks.test_browser_has_text) ... ok
test_browser_has_text_no_page_is_false (test_checks.TestBrowserChecks.test_browser_has_text_no_page_is_false) ... ok
test_browser_has_text_real_error_propagates (test_checks.TestBrowserChecks.test_browser_has_text_real_error_propagates) ... ok
test_browser_input_has_value_direct (test_checks.TestBrowserChecks.test_browser_input_has_value_direct) ... ok
test_browser_input_has_value_wrapper_path (test_checks.TestBrowserChecks.test_browser_input_has_value_wrapper_path) ... ok
test_gmail_message_matches (test_checks.TestGmailChecks.test_gmail_message_matches) ... ok
test_gmail_unread_exists (test_checks.TestGmailChecks.test_gmail_unread_exists) ... ok
test_gmail_unread_exists_emits_exactly_one_l2_line (test_checks.TestGmailChecks.test_gmail_unread_exists_emits_exactly_one_l2_line)
Regression for the duplicate @observe decorator bug: exactly one ... ok
test_checks_emit_l2_lines (test_checks.TestL2Observed.test_checks_emit_l2_lines) ... ok
test_whatsapp_identity_ok (test_checks.TestMessagingChecks.test_whatsapp_identity_ok) ... ok
test_file_exists (test_checks.TestPureChecks.test_file_exists) ... ok
test_list_nonempty (test_checks.TestPureChecks.test_list_nonempty) ... ok
test_message_sent_discord (test_checks.TestPureChecks.test_message_sent_discord) ... ok
test_message_sent_telegram (test_checks.TestPureChecks.test_message_sent_telegram) ... ok
test_message_sent_unknown_platform (test_checks.TestPureChecks.test_message_sent_unknown_platform) ... ok
test_message_sent_whatsapp (test_checks.TestPureChecks.test_message_sent_whatsapp) ... ok
test_text_nonempty (test_checks.TestPureChecks.test_text_nonempty) ... ok
test_window_client_count (test_checks.TestWindowChecks.test_window_client_count) ... ok
test_window_has_class_substring (test_checks.TestWindowChecks.test_window_has_class_substring) ... ok
test_window_on_workspace (test_checks.TestWindowChecks.test_window_on_workspace) ... ok
test_window_only_classes (test_checks.TestWindowChecks.test_window_only_classes) ... ok
test_window_only_classes_vacuous_on_empty (test_checks.TestWindowChecks.test_window_only_classes_vacuous_on_empty) ... ok
test_claude_timeout_raises_primitive_timeout_with_state (test_dev.TestClaudeTimeout.test_claude_timeout_raises_primitive_timeout_with_state)
REGRESSION (2026-08-13, found LIVE by the triage repair loop): ... ok
test_plain_run_ungated (test_dev.TestDevGate.test_plain_run_ungated) ... ok
test_run_bypass_refuses_without_flag (test_dev.TestDevGate.test_run_bypass_refuses_without_flag) ... ok
test_run_shell_allowed_with_flag (test_dev.TestDevGate.test_run_shell_allowed_with_flag) ... ok
test_run_shell_bad_envelope_raises (test_dev.TestDevGate.test_run_shell_bad_envelope_raises) ... ok
test_run_shell_bypass_flag_reaches_claude (test_dev.TestDevGate.test_run_shell_bypass_flag_reaches_claude) ... ok
test_run_shell_refuses_without_flag (test_dev.TestDevGate.test_run_shell_refuses_without_flag) ... ok
test_run_shell_rejects_empty_command (test_dev.TestDevGate.test_run_shell_rejects_empty_command) ... ok
test_digest_accepts_custom_instruction (test_dev.TestDigest.test_digest_accepts_custom_instruction) ... ok
test_digest_builds_labeled_context_prompt (test_dev.TestDigest.test_digest_builds_labeled_context_prompt) ... ok
test_digest_empty_context_raises (test_dev.TestDigest.test_digest_empty_context_raises) ... ok
test_digest_empty_instruction_raises (test_dev.TestDigest.test_digest_empty_instruction_raises) ... ok
test_digest_llm_empty_result_raises (test_dev.TestDigest.test_digest_llm_empty_result_raises) ... ok
test_digest_returns_llm_text (test_dev.TestDigest.test_digest_returns_llm_text) ... ok
test_default_model_used_without_override (test_dev.TestFridayModelOverride.test_default_model_used_without_override) ... ok
test_override_replaces_the_model_flag (test_dev.TestFridayModelOverride.test_override_replaces_the_model_flag) ... ok
test_context_values_may_be_lists (test_digestcheck.TestVerifyAttribution.test_context_values_may_be_lists) ... ok
test_correct_attribution_passes (test_digestcheck.TestVerifyAttribution.test_correct_attribution_passes) ... ok
test_cross_repo_misattribution_flagged (test_digestcheck.TestVerifyAttribution.test_cross_repo_misattribution_flagged)
The exact v2.1 failure shape: Vivaha's Cloudflare-Worker pattern ... ok
test_dotted_mechanism_in_no_repo_flagged (test_digestcheck.TestVerifyAttribution.test_dotted_mechanism_in_no_repo_flagged) ... ok
test_empty_context_raises (test_digestcheck.TestVerifyAttribution.test_empty_context_raises) ... ok
test_empty_digest_raises (test_digestcheck.TestVerifyAttribution.test_empty_digest_raises) ... ok
test_idempotent (test_digestcheck.TestVerifyAttribution.test_idempotent) ... ok
test_legit_roadmap_claim_passes (test_digestcheck.TestVerifyAttribution.test_legit_roadmap_claim_passes) ... ok
test_no_claims_is_honest_not_silent (test_digestcheck.TestVerifyAttribution.test_no_claims_is_honest_not_silent) ... ok
test_registered (test_digestcheck.TestVerifyAttribution.test_registered) ... ok
test_typographic_apostrophes_are_matched (test_digestcheck.TestVerifyAttribution.test_typographic_apostrophes_are_matched)
Regression (2026-08-11): a real LLM digest used U+2019 ... ok
test_typographic_quote_misattribution_still_flagged (test_digestcheck.TestVerifyAttribution.test_typographic_quote_misattribution_still_flagged) ... ok
test_unconnected_suggestion_flagged (test_digestcheck.TestVerifyAttribution.test_unconnected_suggestion_flagged)
v2's S1 shape: 'daily email summaries' attributed to Vivaha when ... ok
test_bracket_path (test_executor.TestRefResolver.test_bracket_path) ... ok
test_dot_path (test_executor.TestRefResolver.test_dot_path) ... ok
test_future_ref_rejected (test_executor.TestRefResolver.test_future_ref_rejected) ... ok
test_index_on_non_list_raises (test_executor.TestRefResolver.test_index_on_non_list_raises) ... ok
test_list_index_dot_and_bracket (test_executor.TestRefResolver.test_list_index_dot_and_bracket) ... ok
test_literal_text_not_a_ref (test_executor.TestRefResolver.test_literal_text_not_a_ref) ... ok
test_missing_step_raises (test_executor.TestRefResolver.test_missing_step_raises) ... ok
test_negative_index_rejected (test_executor.TestRefResolver.test_negative_index_rejected) ... ok
test_out_of_range_index_raises (test_executor.TestRefResolver.test_out_of_range_index_raises) ... ok
test_recursive_application (test_executor.TestRefResolver.test_recursive_application) ... ok
test_split_ref_path_mixed (test_executor.TestRefResolver.test_split_ref_path_mixed) ... ok
test_unknown_key_raises (test_executor.TestRefResolver.test_unknown_key_raises) ... ok
test_whole_result (test_executor.TestRefResolver.test_whole_result) ... ok
test_derived_from_idempotency (test_executor.TestRetryPolicy.test_derived_from_idempotency) ... ok
test_blocked_primitive_aborts (test_executor.TestRunPlan.test_blocked_primitive_aborts) ... ok
test_empty_steps_rejected (test_executor.TestRunPlan.test_empty_steps_rejected) ... ok
test_future_ref_rejected_before_primitive_runs (test_executor.TestRunPlan.test_future_ref_rejected_before_primitive_runs) ... ok
test_malformed_step_aborts (test_executor.TestRunPlan.test_malformed_step_aborts) ... ok
test_retry_exhaustion_aborts (test_executor.TestRunPlan.test_retry_exhaustion_aborts) ... ok
test_successful_plan_completes (test_executor.TestRunPlan.test_successful_plan_completes) ... ok
test_unknown_primitive_aborts (test_executor.TestRunPlan.test_unknown_primitive_aborts) ... ok
test_verified_by_world_with_raised_primitive_has_none_result (test_executor.TestRunPlan.test_verified_by_world_with_raised_primitive_has_none_result)
Regression: a step whose primitive raises on every attempt but ... ok
test_verify_failure_exhausts_attempts (test_executor.TestRunPlan.test_verify_failure_exhausts_attempts) ... ok
test_zero_verify_wait_rejected_before_execution (test_executor.TestRunPlan.test_zero_verify_wait_rejected_before_execution) ... ok
test_empty_or_blank_name_raises (test_files.TestFindFileExact.test_empty_or_blank_name_raises) ... ok
test_exact_name_match_case_insensitive (test_files.TestFindFileExact.test_exact_name_match_case_insensitive) ... ok
test_missing_directory_raises (test_files.TestFindFileExact.test_missing_directory_raises) ... ok
test_no_exact_match_returns_empty_not_exception (test_files.TestFindFileExact.test_no_exact_match_returns_empty_not_exception) ... ok
test_substring_is_not_a_match (test_files.TestFindFileExact.test_substring_is_not_a_match) ... ok
test_registered_in_contract_registry (test_files.TestFindFileExactRegistration.test_registered_in_contract_registry)
The approval gate's registration is real: REGISTRY holds the ... ok
test_custom_patterns_respected (test_files.TestFindRecentDoc.test_custom_patterns_respected) ... ok
test_devlog_and_nested_docs_matched (test_files.TestFindRecentDoc.test_devlog_and_nested_docs_matched) ... ok
test_empty_repo_path_raises (test_files.TestFindRecentDoc.test_empty_repo_path_raises) ... ok
test_falls_back_to_readme (test_files.TestFindRecentDoc.test_falls_back_to_readme) ... ok
test_missing_repo_raises (test_files.TestFindRecentDoc.test_missing_repo_raises) ... ok
test_most_recent_status_doc_wins (test_files.TestFindRecentDoc.test_most_recent_status_doc_wins) ... ok
test_no_docs_at_all_returns_empty (test_files.TestFindRecentDoc.test_no_docs_at_all_returns_empty) ... ok
test_plan_word_alone_is_not_a_status_match (test_files.TestFindRecentDoc.test_plan_word_alone_is_not_a_status_match)
Regression: '*plan*' would match TASK7_LOGIN_PLAN.md (a recipe, ... ok
test_registered_idempotent (test_files.TestFindRecentDoc.test_registered_idempotent) ... ok
test_status_doc_wins_over_newer_readme (test_files.TestFindRecentDoc.test_status_doc_wins_over_newer_readme) ... ok
test_contract_registered_idempotent (test_files.TestReadText.test_contract_registered_idempotent) ... ok
test_directory_is_not_a_file_raises (test_files.TestReadText.test_directory_is_not_a_file_raises) ... ok
test_empty_path_or_bad_max_chars_raises (test_files.TestReadText.test_empty_path_or_bad_max_chars_raises) ... ok
test_missing_file_raises (test_files.TestReadText.test_missing_file_raises) ... ok
test_no_truncation_when_within_limit (test_files.TestReadText.test_no_truncation_when_within_limit) ... ok
test_reads_text_and_reports_chars (test_files.TestReadText.test_reads_text_and_reports_chars) ... ok
test_truncates_at_max_chars (test_files.TestReadText.test_truncates_at_max_chars) ... ok
test_chain_exhausted_reuses_last_model (test_gap_triage.TestDraftOne.test_chain_exhausted_reuses_last_model)
Primary AND fallback both fail: the last model is reused for the ... ok
test_chain_single_model_without_fallbacks (test_gap_triage.TestDraftOne.test_chain_single_model_without_fallbacks) ... ok
test_fallback_chain_parses_order_and_whitespace (test_gap_triage.TestDraftOne.test_fallback_chain_parses_order_and_whitespace) ... ok
test_hard_failure_advances_to_fallback_model (test_gap_triage.TestDraftOne.test_hard_failure_advances_to_fallback_model)
The DEGRADED-provider case (claude rc=1, empty stderr): a ... ok
test_llm_call_exception_leaves_group_unprocessed (test_gap_triage.TestDraftOne.test_llm_call_exception_leaves_group_unprocessed)
A dead claude CLI must not kill the whole triage run - the group ... ok
test_model_defaults_to_alias_without_env (test_gap_triage.TestDraftOne.test_model_defaults_to_alias_without_env) ... ok
test_model_override_env_flows_through (test_gap_triage.TestDraftOne.test_model_override_env_flows_through)
FRIDAY_TRIAGE_MODEL (a full model id) overrides the opus alias - ... ok
test_no_fallback_reuses_same_model (test_gap_triage.TestDraftOne.test_no_fallback_reuses_same_model)
Default (no FRIDAY_TRIAGE_FALLBACK_MODELS) preserves the ... ok
test_parses_llm_result (test_gap_triage.TestDraftOne.test_parses_llm_result) ... ok
test_persistent_failure_returns_none (test_gap_triage.TestDraftOne.test_persistent_failure_returns_none) ... ok
test_retries_once_then_succeeds (test_gap_triage.TestDraftOne.test_retries_once_then_succeeds) ... ok
test_structural_rejection_does_not_advance_chain (test_gap_triage.TestDraftOne.test_structural_rejection_does_not_advance_chain)
A structurally-broken reply is a WORKING model's defect - the ... ok
test_timeout_advances_to_fallback_model (test_gap_triage.TestDraftOne.test_timeout_advances_to_fallback_model)
A PrimitiveTimeout on the primary model advances to the ... ok
test_garbage_returns_none (test_gap_triage.TestExtractJson.test_garbage_returns_none) ... ok
test_markdown_fenced_json (test_gap_triage.TestExtractJson.test_markdown_fenced_json) ... ok
test_plain_json (test_gap_triage.TestExtractJson.test_plain_json) ... ok
test_prose_then_object (test_gap_triage.TestExtractJson.test_prose_then_object) ... ok
test_compiles_does_not_execute (test_gap_triage.TestHelpers.test_compiles_does_not_execute) ... ok
test_proposal_dir_sanitizes (test_gap_triage.TestHelpers.test_proposal_dir_sanitizes) ... ok
test_leaves_plain_module_fn_untouched (test_gap_triage.TestNormalizeName.test_leaves_plain_module_fn_untouched) ... ok
test_normalize_does_not_mask_a_rename (test_gap_triage.TestNormalizeName.test_normalize_does_not_mask_a_rename)
A fully-qualified RENAME ('friday.l1.files.write_notes') normalizes ... ok
test_normalized_draft_passes_self_check (test_gap_triage.TestNormalizeName.test_normalized_draft_passes_self_check)
The exact observed failure: a draft whose contract name is the ... ok
test_strips_friday_package_prefix (test_gap_triage.TestNormalizeName.test_strips_friday_package_prefix) ... ok
test_two_part_name_untouched (test_gap_triage.TestNormalizeName.test_two_part_name_untouched) ... ok
test_broken_draft_repaired_on_retry (test_gap_triage.TestSelfCheck.test_broken_draft_repaired_on_retry)
The centerpiece: a structurally-broken first draft gets the EXACT ... ok
test_clean_draft_passes (test_gap_triage.TestSelfCheck.test_clean_draft_passes) ... ok
test_dead_arg_and_ast_defects_rejected (test_gap_triage.TestSelfCheck.test_dead_arg_and_ast_defects_rejected) ... ok
test_persistently_broken_returns_none (test_gap_triage.TestSelfCheck.test_persistently_broken_returns_none)
A draft that never passes the self-check is left unprocessed - ... ok
test_renamed_primitive_rejected (test_gap_triage.TestSelfCheck.test_renamed_primitive_rejected)
A draft that renames the gapped primitive (write_text -> ... ok
test_test_py_compile_defect_rejected (test_gap_triage.TestSelfCheck.test_test_py_compile_defect_rejected)
The self-check must not write a draft whose own test.py does not ... ok
test_three_dot_contract_name_rejected (test_gap_triage.TestSelfCheck.test_three_dot_contract_name_rejected)
The observed defect: a 4-segment qualified name instead of ... ok
test_uncompilable_impl_rejected (test_gap_triage.TestSelfCheck.test_uncompilable_impl_rejected) ... ok
test_compile_failure_reported_honestly (test_gap_triage.TestTriage.test_compile_failure_reported_honestly) ... ok
test_llm_failure_leaves_group_unprocessed (test_gap_triage.TestTriage.test_llm_failure_leaves_group_unprocessed) ... ok
test_registered_primitive_gaps_consumed_without_drafting (test_gap_triage.TestTriage.test_registered_primitive_gaps_consumed_without_drafting)
The post-approval lifecycle: the ambient-gap probes keep refusing ... ok
test_writes_artifacts_marks_processed_and_is_idempotent (test_gap_triage.TestTriage.test_writes_artifacts_marks_processed_and_is_idempotent) ... ok
test_written_proposal_records_self_check_status (test_gap_triage.TestTriage.test_written_proposal_records_self_check_status)
rationale.md must state whether the draft passed the triage ... ok
test_contract_registered_idempotent (test_git.TestGitLog.test_contract_registered_idempotent) ... ok
test_log_bad_count_days_raise_precondition (test_git.TestGitLog.test_log_bad_count_days_raise_precondition) ... ok
test_log_count_limits_entries (test_git.TestGitLog.test_log_count_limits_entries) ... ok
test_log_days_filters (test_git.TestGitLog.test_log_days_filters) ... ok
test_log_empty_repo_returns_empty_list (test_git.TestGitLog.test_log_empty_repo_returns_empty_list) ... ok
test_log_missing_dir_raises_precondition (test_git.TestGitLog.test_log_missing_dir_raises_precondition) ... ok
test_log_not_a_repo_raises_primitive (test_git.TestGitLog.test_log_not_a_repo_raises_primitive) ... ok
test_log_returns_entries_newest_first (test_git.TestGitLog.test_log_returns_entries_newest_first) ... ok
test_garbage_base64_returns_empty (test_gmail.TestBodyText.test_garbage_base64_returns_empty) ... ok
test_multipart_prefers_text_plain (test_gmail.TestBodyText.test_multipart_prefers_text_plain) ... ok
test_no_body_returns_empty (test_gmail.TestBodyText.test_no_body_returns_empty) ... ok
test_single_part_body_decoded (test_gmail.TestBodyText.test_single_part_body_decoded) ... ok
test_case_insensitive (test_gmail.TestHeader.test_case_insensitive) ... ok
test_missing_returns_empty (test_gmail.TestHeader.test_missing_returns_empty) ... ok
test_non_list_passthrough (test_gmail.TestLogRedactMailMeta.test_non_list_passthrough) ... ok
test_original_not_mutated (test_gmail.TestLogRedactMailMeta.test_original_not_mutated) ... ok
test_redacts_sender_and_subject_keeps_ids (test_gmail.TestLogRedactMailMeta.test_redacts_sender_and_subject_keeps_ids) ... ok
test_api_error_surfaces_primitive_error (test_gmail.TestSendDocument.test_api_error_surfaces_primitive_error) ... ok
test_default_recipient_env (test_gmail.TestSendDocument.test_default_recipient_env) ... ok
test_empty_to_raises (test_gmail.TestSendDocument.test_empty_to_raises)
An empty `to` must raise BEFORE any network call. `_default_to` ... ok
test_missing_file_raises_precondition (test_gmail.TestSendDocument.test_missing_file_raises_precondition) ... ok
test_recipient_redacted_from_l0_result_line (test_gmail.TestSendDocument.test_recipient_redacted_from_l0_result_line)
The RECIPIENT is mail metadata - the result line in ... ok
test_registered_in_registry_as_at_most_once (test_gmail.TestSendDocument.test_registered_in_registry_as_at_most_once) ... ok
test_sends_attachment_and_returns_meta (test_gmail.TestSendDocument.test_sends_attachment_and_returns_meta) ... ok
test_empty_llm_summary_raises (test_gmail.TestSummarizeFlow.test_empty_llm_summary_raises) ... ok
test_message_without_body_or_snippet_raises (test_gmail.TestSummarizeFlow.test_message_without_body_or_snippet_raises) ... ok
test_summary_body_never_reaches_l0_log (test_gmail.TestSummarizeFlow.test_summary_body_never_reaches_l0_log)
Regression: the mail body is passed to the LLM subprocess, but ... ok
test_summary_from_dict_result (test_gmail.TestSummarizeFlow.test_summary_from_dict_result) ... ok
test_summary_from_string_result (test_gmail.TestSummarizeFlow.test_summary_from_string_result) ... ok
test_deterministic_draft_is_inert_and_valid (test_goal_proposals.TestDraft.test_deterministic_draft_is_inert_and_valid) ... ok
test_llm_garbage_falls_back_deterministic (test_goal_proposals.TestDraft.test_llm_garbage_falls_back_deterministic) ... ok
test_llm_non_time_schedule_falls_back (test_goal_proposals.TestDraft.test_llm_non_time_schedule_falls_back) ... ok
test_unique_id_avoids_existing_trigger_ids (test_goal_proposals.TestDraft.test_unique_id_avoids_existing_trigger_ids) ... ok
test_verbatim_goal_survives_llm_path (test_goal_proposals.TestDraft.test_verbatim_goal_survives_llm_path) ... ok
test_goal_covered_substring_and_token_overlap (test_goal_proposals.TestHelpers.test_goal_covered_substring_and_token_overlap) ... ok
test_normalize_goal (test_goal_proposals.TestHelpers.test_normalize_goal) ... ok
test_clusters_recurring_failed_goals (test_goal_proposals.TestMine.test_clusters_recurring_failed_goals) ... ok
test_covered_by_existing_trigger_skipped (test_goal_proposals.TestMine.test_covered_by_existing_trigger_skipped)
The real dedupe shape: the gmail-summary failures are covered by ... ok
test_not_covered_by_unrelated_trigger (test_goal_proposals.TestMine.test_not_covered_by_unrelated_trigger) ... ok
test_refused_and_probe_records_excluded (test_goal_proposals.TestMine.test_refused_and_probe_records_excluded) ... ok
test_sorted_by_occurrences (test_goal_proposals.TestMine.test_sorted_by_occurrences) ... ok
test_watch_l0_evidence_attached (test_goal_proposals.TestMine.test_watch_l0_evidence_attached) ... ok
test_window_filters_old_failures (test_goal_proposals.TestMine.test_window_filters_old_failures) ... ok
test_dry_run_writes_nothing (test_goal_proposals.TestPropose.test_dry_run_writes_nothing) ... ok
test_existing_proposal_dir_covered (test_goal_proposals.TestPropose.test_existing_proposal_dir_covered) ... ok
test_idempotent_never_reproposes (test_goal_proposals.TestPropose.test_idempotent_never_reproposes) ... ok
test_llm_draft_note_stays_out_of_trigger_json (test_goal_proposals.TestPropose.test_llm_draft_note_stays_out_of_trigger_json)
Regression (review 2026-08-11): the artifact a human copies into ... ok
test_never_touches_watcher_config (test_goal_proposals.TestPropose.test_never_touches_watcher_config) ... ok
test_proposal_validates_through_watcher_loader (test_goal_proposals.TestPropose.test_proposal_validates_through_watcher_loader) ... ok
test_writes_inert_proposal_and_rationale (test_goal_proposals.TestPropose.test_writes_inert_proposal_and_rationale) ... ok
test_l0_only_failures (test_goal_proposals.TestRead.test_l0_only_failures) ... ok
test_malformed_lines_skipped (test_goal_proposals.TestRead.test_malformed_lines_skipped) ... ok
test_top_signatures (test_goal_proposals.TestSummary.test_top_signatures) ... ok
test_injection_is_bounded (test_lessons.TestApprovedStore.test_injection_is_bounded) ... ok
test_invalid_entries_excluded_fail_open (test_lessons.TestApprovedStore.test_invalid_entries_excluded_fail_open) ... ok
test_invalid_utf8_store_is_fail_open (test_lessons.TestApprovedStore.test_invalid_utf8_store_is_fail_open)
Regression (review 2026-08-11): read_text raises ... ok
test_malformed_store_is_fail_open (test_lessons.TestApprovedStore.test_malformed_store_is_fail_open) ... ok
test_no_file_means_no_lessons (test_lessons.TestApprovedStore.test_no_file_means_no_lessons) ... ok
test_valid_entries_load_and_render (test_lessons.TestApprovedStore.test_valid_entries_load_and_render) ... ok
test_below_min_examples_no_candidate (test_lessons.TestGeneralize.test_below_min_examples_no_candidate) ... ok
test_cluster_writes_candidate_with_evidence (test_lessons.TestGeneralize.test_cluster_writes_candidate_with_evidence) ... ok
test_event_without_id_never_forces_rewrite (test_lessons.TestGeneralize.test_event_without_id_never_forces_rewrite)
Regression (review 2026-08-11): a parseable event missing ... ok
test_idempotent_no_rewrite_for_covered_events (test_lessons.TestGeneralize.test_idempotent_no_rewrite_for_covered_events) ... ok
test_new_evidence_extends_candidate (test_lessons.TestGeneralize.test_new_evidence_extends_candidate) ... ok
test_unregistered_category_never_candidates (test_lessons.TestGeneralize.test_unregistered_category_never_candidates) ... ok
test_digest_task_includes_lessons (test_lessons.TestInjection.test_digest_task_includes_lessons) ... ok
test_planner_prompt_includes_lessons (test_lessons.TestInjection.test_planner_prompt_includes_lessons) ... ok
test_triage_prompt_empty_without_lessons (test_lessons.TestInjection.test_triage_prompt_empty_without_lessons) ... ok
test_triage_prompt_includes_lessons (test_lessons.TestInjection.test_triage_prompt_includes_lessons) ... ok
test_detail_truncated (test_lessons.TestRecord.test_detail_truncated) ... ok
test_events_append_in_order (test_lessons.TestRecord.test_events_append_in_order) ... ok
test_malformed_lines_skipped_never_raised (test_lessons.TestRecord.test_malformed_lines_skipped_never_raised) ... ok
test_record_writes_well_formed_event (test_lessons.TestRecord.test_record_writes_well_formed_event) ... ok
test_clean_proposal_records_nothing (test_lessons.TestRecordSites.test_clean_proposal_records_nothing) ... ok
test_digest_misattribution_records_event (test_lessons.TestRecordSites.test_digest_misattribution_records_event) ... ok
test_gate_rejection_records_draft_ast (test_lessons.TestRecordSites.test_gate_rejection_records_draft_ast) ... ok
test_planner_schema_failure_records_lesson (test_lessons.TestRecordSites.test_planner_schema_failure_records_lesson) ... ok
test_schema_rejection_records_draft_schema (test_lessons.TestRecordSites.test_schema_rejection_records_draft_schema) ... ok
test_idle_means_stopped (test_media.TestIsPlaying.test_idle_means_stopped) ... ok
test_no_player_returns_false (test_media.TestIsPlaying.test_no_player_returns_false) ... ok
test_paused_means_not_playing (test_media.TestIsPlaying.test_paused_means_not_playing) ... ok
test_playing_when_not_idle_and_not_paused (test_media.TestIsPlaying.test_playing_when_not_idle_and_not_paused) ... ok
test_launch_mpv_missing_raises_and_leaves_proc (test_media.TestLaunchAndWaitSocket.test_launch_mpv_missing_raises_and_leaves_proc) ... ok
test_launch_socket_never_ready_stops_and_sweeps (test_media.TestLaunchAndWaitSocket.test_launch_socket_never_ready_stops_and_sweeps) ... ok
test_launch_success (test_media.TestLaunchAndWaitSocket.test_launch_success) ... ok
test_wait_socket_false_when_silent (test_media.TestLaunchAndWaitSocket.test_wait_socket_false_when_silent) ... ok
test_wait_socket_true_when_probe_replies (test_media.TestLaunchAndWaitSocket.test_wait_socket_true_when_probe_replies) ... ok
test_pgrep_missing_binary_returns_empty (test_media.TestOrphanSweep.test_pgrep_missing_binary_returns_empty) ... ok
test_pgrep_parses_pids (test_media.TestOrphanSweep.test_pgrep_parses_pids) ... ok
test_pgrep_timeout_returns_empty (test_media.TestOrphanSweep.test_pgrep_timeout_returns_empty) ... ok
test_sweep_with_no_orphans_is_noop (test_media.TestOrphanSweep.test_sweep_with_no_orphans_is_noop) ... ok
test_play_for_minutes_must_be_positive (test_media.TestPreconditions.test_play_for_minutes_must_be_positive) ... ok
test_play_for_requires_source (test_media.TestPreconditions.test_play_for_requires_source) ... ok
test_play_requires_source (test_media.TestPreconditions.test_play_requires_source) ... ok
test_set_volume_range (test_media.TestPreconditions.test_set_volume_range) ... ok
test_failure_or_none (test_media.TestReplyOk.test_failure_or_none) ... ok
test_success (test_media.TestReplyOk.test_success) ... ok
test_send_file_missing (test_messaging.TestDiscord.test_send_file_missing) ... ok
test_send_text_empty (test_messaging.TestDiscord.test_send_text_empty) ... ok
test_send_document_missing_file (test_messaging.TestTelegram.test_send_document_missing_file) ... ok
test_send_text_empty (test_messaging.TestTelegram.test_send_text_empty) ... ok
test_mime_map (test_messaging.TestWhatsapp.test_mime_map) ... ok
test_mime_unknown_raises (test_messaging.TestWhatsapp.test_mime_unknown_raises) ... ok
test_send_document_missing_file (test_messaging.TestWhatsapp.test_send_document_missing_file) ... ok
test_send_text_bad_recipient (test_messaging.TestWhatsapp.test_send_text_bad_recipient) ... ok
test_send_text_empty (test_messaging.TestWhatsapp.test_send_text_empty) ... ok
test_upload_document_missing_file (test_messaging.TestWhatsapp.test_upload_document_missing_file) ... ok
test_empty_title_precondition (test_notify.TestNotifySend.test_empty_title_precondition) ... ok
test_missing_binary (test_notify.TestNotifySend.test_missing_binary) ... ok
test_no_body_omits_body_arg (test_notify.TestNotifySend.test_no_body_omits_body_arg) ... ok
test_nonzero_exit (test_notify.TestNotifySend.test_nonzero_exit) ... ok
test_success (test_notify.TestNotifySend.test_success) ... ok
test_timeout (test_notify.TestNotifySend.test_timeout) ... ok
test_timeout_flag_respects_custom_value (test_notify.TestNotifySend.test_timeout_flag_respects_custom_value) ... ok
test_broken_log_transform_cannot_break_primitive (test_observability.TestObserveWrapper.test_broken_log_transform_cannot_break_primitive) ... ok
test_exception_line_and_reraises (test_observability.TestObserveWrapper.test_exception_line_and_reraises) ... ok
test_log_transform_applied_to_log_only (test_observability.TestObserveWrapper.test_log_transform_applied_to_log_only) ... ok
test_observability_disabled_writes_nothing (test_observability.TestObserveWrapper.test_observability_disabled_writes_nothing) ... ok
test_redact_result (test_observability.TestObserveWrapper.test_redact_result) ... ok
test_success_line_shape (test_observability.TestObserveWrapper.test_success_line_shape) ... ok
test_bind_args_redacts_argument_named_password (test_observability.TestRedaction.test_bind_args_redacts_argument_named_password) ... ok
test_clip_redacts_nested_and_bounds (test_observability.TestRedaction.test_clip_redacts_nested_and_bounds) ... ok
test_clip_truncates_long_strings_and_deep (test_observability.TestRedaction.test_clip_truncates_long_strings_and_deep) ... ok
test_sensitive_keys_redacted (test_observability.TestRedaction.test_sensitive_keys_redacted) ... ok
test_backups_zero_disables_rotation (test_observability.TestRotation.test_backups_zero_disables_rotation) ... ok
test_rotation_config_clamps (test_observability.TestRotation.test_rotation_config_clamps) ... ok
test_rotation_output_valid_jsonl (test_observability.TestRotation.test_rotation_output_valid_jsonl) ... ok
test_rotation_preserves_order_and_drops_oldest (test_observability.TestRotation.test_rotation_preserves_order_and_drops_oldest) ... ok
test_discovery_finds_new_module_files (test_planner.TestCatalog.test_discovery_finds_new_module_files)
REGRESSION (2026-08-13, found live by cycle 2): the default base ... ok
test_discovery_honors_friday_l1_dir_override (test_planner.TestCatalog.test_discovery_honors_friday_l1_dir_override) ... ok
test_hides_blocked_primitives (test_planner.TestCatalog.test_hides_blocked_primitives) ... ok
test_lists_primitives_and_checks (test_planner.TestCatalog.test_lists_primitives_and_checks) ... ok
test_bare (test_planner.TestExtractJson.test_bare) ... ok
test_embedded (test_planner.TestExtractJson.test_embedded) ... ok
test_fenced (test_planner.TestExtractJson.test_fenced) ... ok
test_garbage (test_planner.TestExtractJson.test_garbage) ... ok
test_bad_json_raises (test_planner.TestFacts.test_bad_json_raises) ... ok
test_collision_raises (test_planner.TestFacts.test_collision_raises) ... ok
test_defaults_when_no_file (test_planner.TestFacts.test_defaults_when_no_file) ... ok
test_load_and_resolve_paths (test_planner.TestFacts.test_load_and_resolve_paths) ... ok
test_substitute_facts_refs (test_planner.TestFacts.test_substitute_facts_refs) ... ok
test_substitute_unknown_raises (test_planner.TestFacts.test_substitute_unknown_raises) ... ok
test_prompt_carries_rejection_reason (test_planner.TestPrompt.test_prompt_carries_rejection_reason) ... ok
test_prompt_contains_goal_and_catalog (test_planner.TestPrompt.test_prompt_contains_goal_and_catalog) ... ok
test_bad_kwarg_to_check (test_planner.TestValidatePlan.test_bad_kwarg_to_check) ... ok
test_bad_kwarg_to_primitive (test_planner.TestValidatePlan.test_bad_kwarg_to_primitive) ... ok
test_blocked_primitive (test_planner.TestValidatePlan.test_blocked_primitive) ... ok
test_bool_timing_rejected (test_planner.TestValidatePlan.test_bool_timing_rejected) ... ok
test_empty_steps (test_planner.TestValidatePlan.test_empty_steps) ... ok
test_good_plan (test_planner.TestValidatePlan.test_good_plan) ... ok
test_missing_goal (test_planner.TestValidatePlan.test_missing_goal) ... ok
test_missing_verify (test_planner.TestValidatePlan.test_missing_verify) ... ok
test_non_positive_timing_rejected (test_planner.TestValidatePlan.test_non_positive_timing_rejected) ... ok
test_not_a_dict (test_planner.TestValidatePlan.test_not_a_dict) ... ok
test_retries_non_int (test_planner.TestValidatePlan.test_retries_non_int) ... ok
test_unknown_check (test_planner.TestValidatePlan.test_unknown_check) ... ok
test_unknown_primitive (test_planner.TestValidatePlan.test_unknown_primitive) ... ok
test_unresolved_facts_rejected (test_planner.TestValidatePlan.test_unresolved_facts_rejected) ... ok
test_contract_must_be_json_object_not_source (test_register_proposal.TestApprovalGate.test_contract_must_be_json_object_not_source) ... ok
test_contract_schema_validated (test_register_proposal.TestApprovalGate.test_contract_schema_validated) ... ok
test_impl_must_compile_and_define_function (test_register_proposal.TestApprovalGate.test_impl_must_compile_and_define_function) ... ok
test_marker_without_token_rejected (test_register_proposal.TestApprovalGate.test_marker_without_token_rejected) ... ok
test_requires_approval_marker (test_register_proposal.TestApprovalGate.test_requires_approval_marker) ... ok
test_signed_proposal_accepted (test_register_proposal.TestApprovalGate.test_signed_proposal_accepted) ... ok
test_automated_gate_blocks_signed_dangerous_impl (test_register_proposal.TestApproveAndRegister.test_automated_gate_blocks_signed_dangerous_impl)
Even a SIGNED proposal is blocked: an impl calling subprocess is ... ok
test_automated_gate_blocks_signed_dead_arg_impl (test_register_proposal.TestApproveAndRegister.test_automated_gate_blocks_signed_dead_arg_impl)
The exact defect the human caught by hand last round (an impl ... ok
test_full_gate_refuses_without_signature (test_register_proposal.TestApproveAndRegister.test_full_gate_refuses_without_signature) ... ok
test_full_gate_registers_signed_valid_proposal (test_register_proposal.TestApproveAndRegister.test_full_gate_registers_signed_valid_proposal) ... ok
test_gate_rejects_bad_contract_even_when_signed (test_register_proposal.TestApproveAndRegister.test_gate_rejects_bad_contract_even_when_signed) ... ok
test_schema_rejection_is_annotated_in_rationale (test_register_proposal.TestApproveAndRegister.test_schema_rejection_is_annotated_in_rationale)
A contract-schema rejection must leave a rejection record in the ... ok
test_signed_valid_proposal_sandbox_runs_and_registers (test_register_proposal.TestApproveAndRegister.test_signed_valid_proposal_sandbox_runs_and_registers)
The full gate with a real test.py: AST passes, the sandbox runs ... ok
test_falls_back_to_known_modules (test_register_proposal.TestL1Discovery.test_falls_back_to_known_modules) ... ok
test_planner_discovers_modules_from_dir (test_register_proposal.TestL1Discovery.test_planner_discovers_modules_from_dir) ... ok
test_appends_to_existing_module (test_register_proposal.TestRegister.test_appends_to_existing_module) ... ok
test_future_import_stripped_when_appending (test_register_proposal.TestRegister.test_future_import_stripped_when_appending)
Regression (gmail.send_document): an impl beginning with ... ok
test_future_import_with_semicolon_keeps_remainder (test_register_proposal.TestRegister.test_future_import_with_semicolon_keeps_remainder)
A single-line `from __future__ import x; y = 1` shares its line ... ok
test_new_module_written_and_idempotent (test_register_proposal.TestRegister.test_new_module_written_and_idempotent) ... ok
test_blocked_primitive_still_registered (test_registry.TestRegistry.test_blocked_primitive_still_registered) ... ok
test_contract_carries_idempotency_and_docs (test_registry.TestRegistry.test_contract_carries_idempotency_and_docs) ... ok
test_contract_wraps_and_attaches_contract (test_registry.TestRegistry.test_contract_wraps_and_attaches_contract) ... ok
test_decorator_rejects_private_function_names (test_registry.TestRegistry.test_decorator_rejects_private_function_names) ... ok
test_known_primitives_registered (test_registry.TestRegistry.test_known_primitives_registered) ... ok
test_read_only_primitives_are_idempotent (test_registry.TestRegistry.test_read_only_primitives_are_idempotent) ... ok
test_registry_keys_are_module_qualified (test_registry.TestRegistry.test_registry_keys_are_module_qualified) ... ok
test_json_entry (test_secrets.TestSecrets.test_json_entry) ... ok
test_missing_binary (test_secrets.TestSecrets.test_missing_binary) ... ok
test_nonzero_exit (test_secrets.TestSecrets.test_nonzero_exit) ... ok
test_two_line_entry (test_secrets.TestSecrets.test_two_line_entry) ... ok
test_unsupported_entry_shape (test_secrets.TestSecrets.test_unsupported_entry_shape) ... ok
test_allow_must_be_a_list_of_strings (test_watcher.TestAllowList.test_allow_must_be_a_list_of_strings) ... ok
test_allowed_exact_and_prefix_plan_executes (test_watcher.TestAllowList.test_allowed_exact_and_prefix_plan_executes) ... ok
test_plan_with_disallowed_prim_is_refused_not_executed (test_watcher.TestAllowList.test_plan_with_disallowed_prim_is_refused_not_executed) ... ok
test_bad_at (test_watcher.TestConfigValidation.test_bad_at) ... ok
test_bad_json (test_watcher.TestConfigValidation.test_bad_json) ... ok
test_bad_schedule_type (test_watcher.TestConfigValidation.test_bad_schedule_type) ... ok
test_committed_digest_trigger_plan_validates (test_watcher.TestConfigValidation.test_committed_digest_trigger_plan_validates)
The enabled weekly-cross-project-digest trigger (Phase C v2) is ... ok
test_committed_file_write_probe_retired_after_registration (test_watcher.TestConfigValidation.test_committed_file_write_probe_retired_after_registration)
ambient-gap-probe-file-write (added 2026-08-13) targeted ... ok
test_committed_gap_probes_retired_after_registration (test_watcher.TestConfigValidation.test_committed_gap_probes_retired_after_registration)
The ambient-gap-probe triggers were the deliberate ambient ... ok
test_committed_morning_allowlist_stays_read_only (test_watcher.TestConfigValidation.test_committed_morning_allowlist_stays_read_only)
The enabled morning-gmail-summary trigger's allowlist must stay ... ok
test_committed_reminder_trigger_plan_validates (test_watcher.TestConfigValidation.test_committed_reminder_trigger_plan_validates)
The enabled sunday-digest-reminder trigger (the DIGEST_TRACKING.md ... ok
test_days_must_be_list (test_watcher.TestConfigValidation.test_days_must_be_list) ... ok
test_duplicate_id (test_watcher.TestConfigValidation.test_duplicate_id) ... ok
test_file_schedule_needs_directory (test_watcher.TestConfigValidation.test_file_schedule_needs_directory) ... ok
test_invalid_days_rejected_at_load (test_watcher.TestConfigValidation.test_invalid_days_rejected_at_load)
Regression: an unknown day name must fail at load, not crash the ... ok
test_missing_goal_and_plan (test_watcher.TestConfigValidation.test_missing_goal_and_plan) ... ok
test_missing_id (test_watcher.TestConfigValidation.test_missing_id) ... ok
test_valid_config (test_watcher.TestConfigValidation.test_valid_config) ... ok
test_detects_new_files_once (test_watcher.TestFileDue.test_detects_new_files_once) ... ok
test_missing_directory_is_not_due (test_watcher.TestFileDue.test_missing_directory_is_not_due) ... ok
test_corrupt_state_fails_safe (test_watcher.TestFiredState.test_corrupt_state_fails_safe) ... ok
test_daemon_mode_persists_and_survives_restart (test_watcher.TestFiredState.test_daemon_mode_persists_and_survives_restart)
Daemon mode: first run fires + persists; a restarted daemon on ... ok
test_missing_state_fails_safe (test_watcher.TestFiredState.test_missing_state_fails_safe) ... ok
test_restart_new_day_fires (test_watcher.TestFiredState.test_restart_new_day_fires) ... ok
test_restart_same_day_does_not_refire (test_watcher.TestFiredState.test_restart_same_day_does_not_refire)
The regression: a restart after today's firing must not produce ... ok
test_emit_heartbeat_never_fires_without_trigger (test_watcher.TestHeartbeat.test_emit_heartbeat_never_fires_without_trigger) ... ok
test_emit_heartbeat_reports_liveness (test_watcher.TestHeartbeat.test_emit_heartbeat_reports_liveness) ... ok
test_heartbeat_fires_inside_daemon_loop (test_watcher.TestHeartbeat.test_heartbeat_fires_inside_daemon_loop)
In daemon mode the loop emits daemon.alive on the interval; a ... ok
test_heartbeat_fires_once_interval_elapses (test_watcher.TestHeartbeat.test_heartbeat_fires_once_interval_elapses) ... ok
test_heartbeat_respects_interval (test_watcher.TestHeartbeat.test_heartbeat_respects_interval)
Regression: the first heartbeat must NOT fire immediately. The ... ok
test_heartbeat_s_must_be_positive (test_watcher.TestHeartbeat.test_heartbeat_s_must_be_positive) ... ok
test_failed_goal_is_replanned_next_firing (test_watcher.TestPlanCaching.test_failed_goal_is_replanned_next_firing) ... ok
test_inline_plan_never_calls_llm (test_watcher.TestPlanCaching.test_inline_plan_never_calls_llm) ... ok
test_make_plan_caches_goal_across_firings (test_watcher.TestPlanCaching.test_make_plan_caches_goal_across_firings) ... ok
test_backoff_gates_retry_cadence (test_watcher.TestRetryOnFailure.test_backoff_gates_retry_cadence)
A persistently-FAILED trigger retries, but attempts are spaced ... ok
test_completed_run_marks_fired_not_retried (test_watcher.TestRetryOnFailure.test_completed_run_marks_fired_not_retried) ... ok
test_failed_run_not_marked_fired_and_retried (test_watcher.TestRetryOnFailure.test_failed_run_not_marked_fired_and_retried) ... ok
test_refused_run_marks_fired_not_retried (test_watcher.TestRetryOnFailure.test_refused_run_marks_fired_not_retried)
An allowlist REFUSAL is the safe terminal outcome for the day: ... ok
test_failed_trigger_recorded_honestly (test_watcher.TestRunWatcher.test_failed_trigger_recorded_honestly) ... ok
test_notify_failure_does_not_break_run (test_watcher.TestRunWatcher.test_notify_failure_does_not_break_run) ... ok
test_once_runs_due_triggers_and_records (test_watcher.TestRunWatcher.test_once_runs_due_triggers_and_records) ... ok
test_poll_s_must_be_positive (test_watcher.TestRunWatcher.test_poll_s_must_be_positive) ... ok
test_unknown_config_raises (test_watcher.TestRunWatcher.test_unknown_config_raises) ... ok
test_before_time (test_watcher.TestTimeDue.test_before_time) ... ok
test_due_on_enabled_day_after_time (test_watcher.TestTimeDue.test_due_on_enabled_day_after_time) ... ok
test_fires_once_per_day (test_watcher.TestTimeDue.test_fires_once_per_day) ... ok
test_no_days_means_every_day (test_watcher.TestTimeDue.test_no_days_means_every_day) ... ok
test_not_enabled_day (test_watcher.TestTimeDue.test_not_enabled_day) ... ok
test_hyprctl_failure_raises_primitive_error (test_window.TestListClientsErrors.test_hyprctl_failure_raises_primitive_error) ... ok
test_compact_client (test_window.TestLogProjection.test_compact_client) ... ok
test_log_clients_result_list_and_single (test_window.TestLogProjection.test_log_clients_result_list_and_single) ... ok
test_close_window_empty_selector (test_window.TestPreconditions.test_close_window_empty_selector) ... ok
test_move_to_workspace_invalid (test_window.TestPreconditions.test_move_to_workspace_invalid) ... ok
test_open_app_empty_command (test_window.TestPreconditions.test_open_app_empty_command) ... ok
test_close_all_excluding_protected_closes_rest (test_window.TestProtectedClasses.test_close_all_excluding_protected_closes_rest) ... ok
test_close_all_refuses_before_any_dispatch (test_window.TestProtectedClasses.test_close_all_refuses_before_any_dispatch) ... ok
test_close_window_allows_non_protected (test_window.TestProtectedClasses.test_close_window_allows_non_protected) ... ok
test_close_window_refuses_protected_address (test_window.TestProtectedClasses.test_close_window_refuses_protected_address) ... ok
test_close_window_refuses_protected_via_class_selector (test_window.TestProtectedClasses.test_close_window_refuses_protected_via_class_selector) ... ok
test_default_protected_is_kitty (test_window.TestProtectedClasses.test_default_protected_is_kitty) ... ok
test_env_override (test_window.TestProtectedClasses.test_env_override) ... ok
test_env_override_relaxes_protection (test_window.TestProtectedClasses.test_env_override_relaxes_protection) ... ok
test_address_prefix (test_window.TestSelectorNormalization.test_address_prefix) ... ok
test_bare_name_becomes_class (test_window.TestSelectorNormalization.test_bare_name_becomes_class) ... ok
test_explicit_prefix_passthrough (test_window.TestSelectorNormalization.test_explicit_prefix_passthrough) ... ok

----------------------------------------------------------------------
Ran 463 tests in 21.931s

OK
```

