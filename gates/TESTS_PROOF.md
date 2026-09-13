# TESTS_PROOF — automated test suite for Friday

Status date: 2026-09-12T16:52:56+00:00.

The full unittest suite over every layer and feature: registry,
observability (redaction / rotation / log_transform), the executor
(ref resolver, retry policy, blocked primitives), the planner
(validate_plan / catalog / facts), L2 checks, window protected-
classes, the dev dangerous-gate, gmail/notify/secrets, and the
watch loop. All side-effect boundaries are mocked - the suite
never sends, launches, clicks or touches the compositor.

## Verdict: PASS

Ran 1037 tests: 1037 passed, 0 failed, 0 errors.

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
test_bare_builtin_raise_flagged (test_automated_gate.TestContractAwareChecks.test_bare_builtin_raise_flagged)
The fourth clipboard defect: bare RuntimeError against a ... ok
test_decorated_impl_clean (test_automated_gate.TestContractAwareChecks.test_decorated_impl_clean) ... ok
test_friday_error_raise_clean (test_automated_gate.TestContractAwareChecks.test_friday_error_raise_clean)
Raising the FridayError family is the convention - never flagged. ... ok
test_implicit_oserror_propagation_not_flagged (test_automated_gate.TestContractAwareChecks.test_implicit_oserror_propagation_not_flagged)
files.write_text's documented behavior - letting OSError escape ... ok
test_log_transform_defined_clean (test_automated_gate.TestContractAwareChecks.test_log_transform_defined_clean) ... ok
test_missing_contract_decorator_flagged (test_automated_gate.TestContractAwareChecks.test_missing_contract_decorator_flagged)
The first clipboard draft's exact defect: a self-check-clean impl ... ok
test_raise_class_in_contract_text_allowed (test_automated_gate.TestContractAwareChecks.test_raise_class_in_contract_text_allowed)
A contract that explicitly declares a builtin (e.g. a ValueError ... ok
test_undefined_log_transform_flagged (test_automated_gate.TestContractAwareChecks.test_undefined_log_transform_flagged)
The second clipboard defect: contract declares ... ok
test_missing_function_flagged (test_automated_gate.TestContractFunction.test_missing_function_flagged) ... ok
test_present_function_clean (test_automated_gate.TestContractFunction.test_present_function_clean) ... ok
test_bounded_run_with_text_and_extra_kwargs_allowed (test_automated_gate.TestDangerChecks.test_bounded_run_with_text_and_extra_kwargs_allowed) ... ok
test_capture_shape_literal_path_allowed (test_automated_gate.TestDangerChecks.test_capture_shape_literal_path_allowed) ... ok
test_capture_shape_runtime_args_allowed (test_automated_gate.TestDangerChecks.test_capture_shape_runtime_args_allowed) ... ok
test_capture_shape_unknown_tool_rejected (test_automated_gate.TestDangerChecks.test_capture_shape_unknown_tool_rejected)
The CAPTURE shape's whole point is the TOOL is allowlisted: a ... ok
test_capture_shape_variable_first_element_rejected (test_automated_gate.TestDangerChecks.test_capture_shape_variable_first_element_rejected)
A non-literal first element (a variable tool name) hides what ... ok
test_capture_shape_without_timeout_rejected (test_automated_gate.TestDangerChecks.test_capture_shape_without_timeout_rejected) ... ok
test_check_output_and_popen_still_rejected (test_automated_gate.TestDangerChecks.test_check_output_and_popen_still_rejected) ... ok
test_clean_impl_no_danger (test_automated_gate.TestDangerChecks.test_clean_impl_no_danger) ... ok
test_dangerous_calls_rejected (test_automated_gate.TestDangerChecks.test_dangerous_calls_rejected) ... ok
test_mixed_read_and_write_shapes_rejected (test_automated_gate.TestDangerChecks.test_mixed_read_and_write_shapes_rejected)
capture_output=True AND stdout=DEVNULL is contradictory - even ... ok
test_partial_devnull_rejected (test_automated_gate.TestDangerChecks.test_partial_devnull_rejected)
Only stdout discarded - stderr still inherits a pipe; the ... ok
test_read_only_bounded_subprocess_run_allowed (test_automated_gate.TestDangerChecks.test_read_only_bounded_subprocess_run_allowed) ... ok
test_run_with_shell_true_rejected (test_automated_gate.TestDangerChecks.test_run_with_shell_true_rejected) ... ok
test_run_with_string_command_rejected (test_automated_gate.TestDangerChecks.test_run_with_string_command_rejected) ... ok
test_run_with_variable_command_rejected (test_automated_gate.TestDangerChecks.test_run_with_variable_command_rejected) ... ok
test_run_without_capture_output_rejected (test_automated_gate.TestDangerChecks.test_run_without_capture_output_rejected) ... ok
test_run_without_timeout_rejected (test_automated_gate.TestDangerChecks.test_run_without_timeout_rejected) ... ok
test_write_shape_devnull_allowed (test_automated_gate.TestDangerChecks.test_write_shape_devnull_allowed) ... ok
test_write_shape_without_timeout_rejected (test_automated_gate.TestDangerChecks.test_write_shape_without_timeout_rejected) ... ok
test_write_shape_xclip_allowed (test_automated_gate.TestDangerChecks.test_write_shape_xclip_allowed) ... ok
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
test_decorated_draft_registers (test_automated_gate.TestRegistrationCheck.test_decorated_draft_registers) ... ok
test_missing_test_py_still_gets_registration_check (test_automated_gate.TestRegistrationCheck.test_missing_test_py_still_gets_registration_check)
The registration check runs on the impl alone - a draft whose ... ok
test_undecorated_draft_does_not_register (test_automated_gate.TestRegistrationCheck.test_undecorated_draft_does_not_register)
The exact clipboard failure: an impl that compiles but has no ... ok
test_undefined_log_transform_fails_import (test_automated_gate.TestRegistrationCheck.test_undefined_log_transform_fails_import)
The log_transform defect is caught here too: exec'ing the impl ... ok
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
test_bare_runtime_error_rejected (test_automated_gate.TestSubreadBuildVerify.test_bare_runtime_error_rejected)
The exact defect a human hand-corrected on the clipboard draft: ... ok
test_correct_clipboard_draft_passes (test_automated_gate.TestSubreadBuildVerify.test_correct_clipboard_draft_passes)
A correct clipboard-style draft (modeled on the hand-corrected ... ok
test_non_subprocess_module_still_not_applicable (test_automated_gate.TestSubreadBuildVerify.test_non_subprocess_module_still_not_applicable)
A non-files module that does NOT use the bounded subprocess ... ok
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
test_posix_sweep_uses_pgrep (test_browser.TestOrphanSweep.test_posix_sweep_uses_pgrep) ... ok
test_windows_sweep_missing_powershell_is_noop (test_browser.TestOrphanSweep.test_windows_sweep_missing_powershell_is_noop) ... ok
test_windows_sweep_uses_powershell_stop_process (test_browser.TestOrphanSweep.test_windows_sweep_uses_powershell_stop_process) ... ok
test_no_page_raises (test_browser.TestReadPageText.test_no_page_raises) ... ok
test_returns_inner_text (test_browser.TestReadPageText.test_returns_inner_text) ... ok
test_fill_failure_falls_back_to_click_and_keystrokes (test_browser.TestTypeTextFallback.test_fill_failure_falls_back_to_click_and_keystrokes)
When loc.fill raises (not a fillable input), type_text clicks the ... ok
test_fill_field_actually_fills (test_browser.TestTypingAndSecretDiscipline.test_fill_field_actually_fills) ... ok
test_fill_field_is_silent (test_browser.TestTypingAndSecretDiscipline.test_fill_field_is_silent)
The credential fill path emits NO line carrying the secret - the ... ok
test_type_text_logs_its_text_argument (test_browser.TestTypingAndSecretDiscipline.test_type_text_logs_its_text_argument) ... ok
test_403_readonly_scope_is_actionable (test_calendar.TestAddEvent.test_403_readonly_scope_is_actionable)
The scope guard (2026-08-15): a 403 'Insufficient Permission' ... ok
test_403_unrelated_is_generic (test_calendar.TestAddEvent.test_403_unrelated_is_generic)
A 403 that is NOT a scope problem (e.g. calendar API disabled) ... ok
test_500_api_error_raises (test_calendar.TestAddEvent.test_500_api_error_raises) ... ok
test_creates_event (test_calendar.TestAddEvent.test_creates_event) ... ok
test_empty_summary_rejected (test_calendar.TestAddEvent.test_empty_summary_rejected) ... ok
test_end_before_start_rejected_across_offsets (test_calendar.TestAddEvent.test_end_before_start_rejected_across_offsets)
The 2026-08-14 hand-fix: an END of '14:00+05:30' vs a START of ... ok
test_garbage_datetime_rejected (test_calendar.TestAddEvent.test_garbage_datetime_rejected) ... ok
test_env_credentials_refresh_and_cache (test_calendar.TestAuth.test_env_credentials_refresh_and_cache) ... ok
test_missing_credentials_raise (test_calendar.TestAuth.test_missing_credentials_raise) ... ok
test_refresh_failure_raises (test_calendar.TestAuth.test_refresh_failure_raises) ... ok
test_delete_event_200_also_works (test_calendar.TestDeleteEvent.test_delete_event_200_also_works)
Google API may return 200 or 204 on successful delete. ... ok
test_delete_event_api_failure (test_calendar.TestDeleteEvent.test_delete_event_api_failure) ... ok
test_delete_event_contract_registered (test_calendar.TestDeleteEvent.test_delete_event_contract_registered) ... ok
test_delete_event_empty_id (test_calendar.TestDeleteEvent.test_delete_event_empty_id) ... ok
test_delete_event_success (test_calendar.TestDeleteEvent.test_delete_event_success) ... ok
test_delete_event_whitespace_id (test_calendar.TestDeleteEvent.test_delete_event_whitespace_id) ... ok
test_401_refreshes_once_and_retries (test_calendar.TestListUpcoming.test_401_refreshes_once_and_retries)
A stale cached access token (expired ~1h) must not fail the call: ... ok
test_api_error_raises_not_empty (test_calendar.TestListUpcoming.test_api_error_raises_not_empty) ... ok
test_invalid_days_raises_precondition (test_calendar.TestListUpcoming.test_invalid_days_raises_precondition) ... ok
test_returns_parsed_events (test_calendar.TestListUpcoming.test_returns_parsed_events) ... ok
test_summary_redacted_from_l0_log (test_calendar.TestListUpcoming.test_summary_redacted_from_l0_log)
Event SUMMARY is metadata that could leak - the L0 result line ... ok
test_update_event_api_failure (test_calendar.TestUpdateEvent.test_update_event_api_failure) ... ok
test_update_event_contract_registered (test_calendar.TestUpdateEvent.test_update_event_contract_registered) ... ok
test_update_event_empty_id (test_calendar.TestUpdateEvent.test_update_event_empty_id) ... ok
test_update_event_invalid_end_datetime (test_calendar.TestUpdateEvent.test_update_event_invalid_end_datetime) ... ok
test_update_event_invalid_start_datetime (test_calendar.TestUpdateEvent.test_update_event_invalid_start_datetime) ... ok
test_update_event_success_summary_only (test_calendar.TestUpdateEvent.test_update_event_success_summary_only) ... ok
test_update_event_with_times (test_calendar.TestUpdateEvent.test_update_event_with_times) ... ok
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
test_file_exists_and_contents_false_missing (test_checks.TestFileChecks.test_file_exists_and_contents_false_missing) ... ok
test_file_exists_and_contents_false_wrong_content (test_checks.TestFileChecks.test_file_exists_and_contents_false_wrong_content) ... ok
test_file_exists_and_contents_true (test_checks.TestFileChecks.test_file_exists_and_contents_true) ... ok
test_file_is_copied_to_false_missing (test_checks.TestFileChecks.test_file_is_copied_to_false_missing) ... ok
test_file_is_copied_to_true (test_checks.TestFileChecks.test_file_is_copied_to_true) ... ok
test_file_is_deleted_false_exists (test_checks.TestFileChecks.test_file_is_deleted_false_exists) ... ok
test_file_is_deleted_true (test_checks.TestFileChecks.test_file_is_deleted_true) ... ok
test_file_is_moved_from_true (test_checks.TestFileChecks.test_file_is_moved_from_true) ... ok
test_file_size_equals_false (test_checks.TestFileChecks.test_file_size_equals_false) ... ok
test_file_size_equals_missing_file (test_checks.TestFileChecks.test_file_size_equals_missing_file) ... ok
test_file_size_equals_true (test_checks.TestFileChecks.test_file_size_equals_true) ... ok
test_gmail_message_matches (test_checks.TestGmailChecks.test_gmail_message_matches) ... ok
test_gmail_unread_exists (test_checks.TestGmailChecks.test_gmail_unread_exists) ... ok
test_gmail_unread_exists_emits_exactly_one_l2_line (test_checks.TestGmailChecks.test_gmail_unread_exists_emits_exactly_one_l2_line)
Regression for the duplicate @observe decorator bug: exactly one ... ok
test_checks_emit_l2_lines (test_checks.TestL2Observed.test_checks_emit_l2_lines) ... ok
test_whatsapp_identity_ok (test_checks.TestMessagingChecks.test_whatsapp_identity_ok) ... ok
test_whatsapp_media_downloaded_false_empty (test_checks.TestMessagingChecks.test_whatsapp_media_downloaded_false_empty) ... ok
test_whatsapp_media_downloaded_false_missing (test_checks.TestMessagingChecks.test_whatsapp_media_downloaded_false_missing) ... ok
test_whatsapp_media_downloaded_true (test_checks.TestMessagingChecks.test_whatsapp_media_downloaded_true) ... ok
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
test_contract_registered_commutative_safe (test_files_extended.TestFileCopy.test_contract_registered_commutative_safe) ... ok
test_copy_creates_file_in_dest (test_files_extended.TestFileCopy.test_copy_creates_file_in_dest) ... ok
test_copy_overwrites_existing_file (test_files_extended.TestFileCopy.test_copy_overwrites_existing_file) ... ok
test_copy_preserves_subdirectories (test_files_extended.TestFileCopy.test_copy_preserves_subdirectories) ... ok
test_empty_dest_raises_precondition (test_files_extended.TestFileCopy.test_empty_dest_raises_precondition) ... ok
test_empty_source_raises_precondition (test_files_extended.TestFileCopy.test_empty_source_raises_precondition) ... ok
test_missing_dest_dir_raises_precondition (test_files_extended.TestFileCopy.test_missing_dest_dir_raises_precondition) ... ok
test_missing_source_raises_precondition (test_files_extended.TestFileCopy.test_missing_source_raises_precondition) ... ok
test_contract_registered_at_most_once (test_files_extended.TestFileDelete.test_contract_registered_at_most_once) ... ok
test_delete_removes_file (test_files_extended.TestFileDelete.test_delete_removes_file) ... ok
test_empty_path_raises_precondition (test_files_extended.TestFileDelete.test_empty_path_raises_precondition) ... ok
test_missing_file_raises_precondition (test_files_extended.TestFileDelete.test_missing_file_raises_precondition) ... ok
test_whitespace_path_raises_precondition (test_files_extended.TestFileDelete.test_whitespace_path_raises_precondition) ... ok
test_contract_registered_at_most_once (test_files_extended.TestFileMove.test_contract_registered_at_most_once) ... ok
test_empty_dest_raises_precondition (test_files_extended.TestFileMove.test_empty_dest_raises_precondition) ... ok
test_empty_source_raises_precondition (test_files_extended.TestFileMove.test_empty_source_raises_precondition) ... ok
test_missing_dest_raises_precondition (test_files_extended.TestFileMove.test_missing_dest_raises_precondition) ... ok
test_missing_source_raises_precondition (test_files_extended.TestFileMove.test_missing_source_raises_precondition) ... ok
test_move_creates_file_in_dest (test_files_extended.TestFileMove.test_move_creates_file_in_dest) ... ok
test_move_removes_from_source (test_files_extended.TestFileMove.test_move_removes_from_source) ... ok
test_bytes_to_kb (test_files_extended.TestFileSize.test_bytes_to_kb) ... ok
test_bytes_to_mb (test_files_extended.TestFileSize.test_bytes_to_mb) ... ok
test_contract_registered_idempotent (test_files_extended.TestFileSize.test_contract_registered_idempotent) ... ok
test_empty_path_raises_precondition (test_files_extended.TestFileSize.test_empty_path_raises_precondition) ... ok
test_missing_file_raises_precondition (test_files_extended.TestFileSize.test_missing_file_raises_precondition) ... ok
test_returns_size_in_bytes_and_human (test_files_extended.TestFileSize.test_returns_size_in_bytes_and_human) ... ok
test_contract_registered_idempotent (test_files_extended.TestListDir.test_contract_registered_idempotent) ... ok
test_default_path_is_current_directory (test_files_extended.TestListDir.test_default_path_is_current_directory) ... ok
test_directory_only_lists_immediate_contents (test_files_extended.TestListDir.test_directory_only_lists_immediate_contents) ... ok
test_lists_files_and_dirs (test_files_extended.TestListDir.test_lists_files_and_dirs) ... ok
test_missing_directory_raises_precondition (test_files_extended.TestListDir.test_missing_directory_raises_precondition) ... ok
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
test_bare_builtin_raise_rejected_at_triage (test_gap_triage.TestSelfCheck.test_bare_builtin_raise_rejected_at_triage)
A draft raising bare RuntimeError against a contract declaring ... ok
test_broken_draft_repaired_on_retry (test_gap_triage.TestSelfCheck.test_broken_draft_repaired_on_retry)
The centerpiece: a structurally-broken first draft gets the EXACT ... ok
test_clean_draft_passes (test_gap_triage.TestSelfCheck.test_clean_draft_passes) ... ok
test_dead_arg_and_ast_defects_rejected (test_gap_triage.TestSelfCheck.test_dead_arg_and_ast_defects_rejected) ... ok
test_missing_contract_decorator_rejected_at_triage (test_gap_triage.TestSelfCheck.test_missing_contract_decorator_rejected_at_triage)
The clipboard round's first defect is now repaired at TRIAGE: an ... ok
test_persistently_broken_returns_none (test_gap_triage.TestSelfCheck.test_persistently_broken_returns_none)
A draft that never passes the self-check is left unprocessed - ... ok
test_renamed_primitive_rejected (test_gap_triage.TestSelfCheck.test_renamed_primitive_rejected)
A draft that renames the gapped primitive (write_text -> ... ok
test_test_py_compile_defect_rejected (test_gap_triage.TestSelfCheck.test_test_py_compile_defect_rejected)
The self-check must not write a draft whose own test.py does not ... ok
test_test_py_danger_ast_rejected (test_gap_triage.TestSelfCheck.test_test_py_danger_ast_rejected)
The gate AST-checks test.py before executing it (the sandbox never ... ok
test_test_py_subprocess_mock_constructor_rejected (test_gap_triage.TestSelfCheck.test_test_py_subprocess_mock_constructor_rejected)
The exact clipboard test defect: building a mock via ... ok
test_three_dot_contract_name_rejected (test_gap_triage.TestSelfCheck.test_three_dot_contract_name_rejected)
The observed defect: a 4-segment qualified name instead of ... ok
test_uncompilable_impl_rejected (test_gap_triage.TestSelfCheck.test_uncompilable_impl_rejected) ... ok
test_undefined_log_transform_rejected_at_triage (test_gap_triage.TestSelfCheck.test_undefined_log_transform_rejected_at_triage)
A contract naming a log_transform the impl never defines is a ... ok
test_compile_failure_reported_honestly (test_gap_triage.TestTriage.test_compile_failure_reported_honestly) ... ok
test_llm_failure_leaves_group_unprocessed (test_gap_triage.TestTriage.test_llm_failure_leaves_group_unprocessed) ... ok
test_registered_primitive_gaps_consumed_without_drafting (test_gap_triage.TestTriage.test_registered_primitive_gaps_consumed_without_drafting)
The post-approval lifecycle: the ambient-gap probes keep refusing ... ok
test_writes_artifacts_marks_processed_and_is_idempotent (test_gap_triage.TestTriage.test_writes_artifacts_marks_processed_and_is_idempotent) ... ok
test_written_proposal_records_self_check_status (test_gap_triage.TestTriage.test_written_proposal_records_self_check_status)
rationale.md must state whether the draft passed the triage ... ok
test_branch_contract_registered (test_git.TestGitBranch.test_branch_contract_registered) ... ok
test_branch_detached_head (test_git.TestGitBranch.test_branch_detached_head) ... ok
test_branch_empty_path (test_git.TestGitBranch.test_branch_empty_path) ... ok
test_branch_returns_current (test_git.TestGitBranch.test_branch_returns_current) ... ok
test_commit_all_staged (test_git.TestGitCommit.test_commit_all_staged) ... ok
test_commit_contract_registered (test_git.TestGitCommit.test_commit_contract_registered) ... ok
test_commit_empty_message (test_git.TestGitCommit.test_commit_empty_message) ... ok
test_commit_empty_path (test_git.TestGitCommit.test_commit_empty_path) ... ok
test_commit_with_files (test_git.TestGitCommit.test_commit_with_files) ... ok
test_diff_contract_registered (test_git.TestGitDiff.test_diff_contract_registered) ... ok
test_diff_empty_path (test_git.TestGitDiff.test_diff_empty_path) ... ok
test_diff_empty_repo (test_git.TestGitDiff.test_diff_empty_repo) ... ok
test_diff_missing_repo (test_git.TestGitDiff.test_diff_missing_repo) ... ok
test_diff_with_staged_changes (test_git.TestGitDiff.test_diff_with_staged_changes) ... ok
test_diff_with_unstaged_changes (test_git.TestGitDiff.test_diff_with_unstaged_changes) ... ok
test_contract_registered_idempotent (test_git.TestGitLog.test_contract_registered_idempotent) ... ok
test_log_bad_count_days_raise_precondition (test_git.TestGitLog.test_log_bad_count_days_raise_precondition) ... ok
test_log_count_limits_entries (test_git.TestGitLog.test_log_count_limits_entries) ... ok
test_log_days_filters (test_git.TestGitLog.test_log_days_filters) ... ok
test_log_empty_repo_returns_empty_list (test_git.TestGitLog.test_log_empty_repo_returns_empty_list) ... ok
test_log_missing_dir_raises_precondition (test_git.TestGitLog.test_log_missing_dir_raises_precondition) ... ok
test_log_not_a_repo_raises_primitive (test_git.TestGitLog.test_log_not_a_repo_raises_primitive) ... ok
test_log_returns_entries_newest_first (test_git.TestGitLog.test_log_returns_entries_newest_first) ... ok
test_clean_repo_is_clean (test_git.TestGitStatus.test_clean_repo_is_clean)
A fresh repo should be clean after initial commit. ... ok
test_contract_registered_idempotent (test_git.TestGitStatus.test_contract_registered_idempotent)
git.status should be in REGISTRY with correct contract. ... ok
test_detects_staged_changes (test_git.TestGitStatus.test_detects_staged_changes)
Should detect staged files. ... ok
test_detects_untracked_files (test_git.TestGitStatus.test_detects_untracked_files)
Should detect untracked files. ... ok
test_raises_for_non_git_directory (test_git.TestGitStatus.test_raises_for_non_git_directory)
Should raise PreconditionError for non-git directory. ... ok
test_returns_dict_with_expected_keys (test_git.TestGitStatus.test_returns_dict_with_expected_keys)
git.status should return a dict with expected keys. ... ok
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
test_connection_error_raises_primitive_error (test_http.TestHttpRequestErrors.test_connection_error_raises_primitive_error) ... ok
test_non_json_response_returns_text (test_http.TestHttpRequestErrors.test_non_json_response_returns_text) ... ok
test_timeout_raises_primitive_error (test_http.TestHttpRequestErrors.test_timeout_raises_primitive_error) ... ok
test_custom_headers_passed (test_http.TestHttpRequestMocked.test_custom_headers_passed) ... ok
test_get_non_json_returns_text (test_http.TestHttpRequestMocked.test_get_non_json_returns_text) ... ok
test_get_returns_structured_response (test_http.TestHttpRequestMocked.test_get_returns_structured_response) ... ok
test_post_with_json_body (test_http.TestHttpRequestMocked.test_post_with_json_body) ... ok
test_post_with_string_body (test_http.TestHttpRequestMocked.test_post_with_string_body) ... ok
test_timeout_passed (test_http.TestHttpRequestMocked.test_timeout_passed) ... ok
test_empty_url (test_http.TestHttpRequestPreconditions.test_empty_url) ... ok
test_invalid_method (test_http.TestHttpRequestPreconditions.test_invalid_method) ... ok
test_just_domain (test_http.TestHttpRequestPreconditions.test_just_domain) ... ok
test_method_case_insensitive (test_http.TestHttpRequestPreconditions.test_method_case_insensitive) ... ok
test_no_http_prefix (test_http.TestHttpRequestPreconditions.test_no_http_prefix) ... ok
test_valid_methods (test_http.TestHttpRequestPreconditions.test_valid_methods)
GET, POST, PUT, DELETE, PATCH should all be accepted. ... ok
test_whitespace_url (test_http.TestHttpRequestPreconditions.test_whitespace_url) ... ok
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
test_initialize_handshake (test_mcp_server.TestProtocol.test_initialize_handshake) ... ok
test_non_dict_message (test_mcp_server.TestProtocol.test_non_dict_message) ... ok
test_notification_gets_no_response (test_mcp_server.TestProtocol.test_notification_gets_no_response) ... ok
test_parse_error (test_mcp_server.TestProtocol.test_parse_error) ... ok
test_ping (test_mcp_server.TestProtocol.test_ping) ... ok
test_unknown_method (test_mcp_server.TestProtocol.test_unknown_method) ... ok
test_bad_kwarg_is_error_result (test_mcp_server.TestToolsCall.test_bad_kwarg_is_error_result) ... ok
test_blocked_primitive_refused (test_mcp_server.TestToolsCall.test_blocked_primitive_refused) ... ok
test_hermetic_primitive_call (test_mcp_server.TestToolsCall.test_hermetic_primitive_call) ... ok
test_missing_name_is_invalid_params (test_mcp_server.TestToolsCall.test_missing_name_is_invalid_params) ... ok
test_non_object_arguments_rejected (test_mcp_server.TestToolsCall.test_non_object_arguments_rejected) ... ok
test_unknown_tool_is_error_not_crash (test_mcp_server.TestToolsCall.test_unknown_tool_is_error_not_crash) ... ok
test_description_carries_contract (test_mcp_server.TestToolsList.test_description_carries_contract) ... ok
test_exposes_registered_primitives (test_mcp_server.TestToolsList.test_exposes_registered_primitives) ... ok
test_schema_derived_from_signature (test_mcp_server.TestToolsList.test_schema_derived_from_signature) ... ok
test_record_send (test_mcu_adapters.TestAdaptiveComms.test_record_send)
Recording sends updates channel preferences. ... ok
test_select_channel_prefers_high_score (test_mcu_adapters.TestAdaptiveComms.test_select_channel_prefers_high_score)
Channel selection prefers high-scoring channels. ... ok
test_read_text_returns_string (test_mcu_adapters.TestClipboardAdapter.test_read_text_returns_string)
read_text returns a string (mocked). ... ok
test_write_text_returns_text (test_mcu_adapters.TestClipboardAdapter.test_write_text_returns_text)
write_text returns the text that was written (mocked). ... ok
test_build_full_context (test_mcu_adapters.TestContextManager.test_build_full_context)
Context manager builds a text block for the planner. ... ok
test_goal_history (test_mcu_adapters.TestContextManager.test_goal_history)
Goals are tracked in history. ... ok
test_events_flow_through_bus (test_mcu_adapters.TestEventBus.test_events_flow_through_bus)
Events emitted by adapters are received by subscribers. ... ok
test_find_file (test_mcu_adapters.TestFilesAdapter.test_find_file)
find_file locates a file by name substring. ... ok
test_find_file_exact (test_mcu_adapters.TestFilesAdapter.test_find_file_exact)
find_file_exact returns empty path for missing files. ... ok
test_find_file_not_found (test_mcu_adapters.TestFilesAdapter.test_find_file_not_found)
find_file raises PreconditionError when no match. ... ok
test_find_newest (test_mcu_adapters.TestFilesAdapter.test_find_newest)
find_newest returns the most recently modified file. ... ok
test_list_dir (test_mcu_adapters.TestFilesAdapter.test_list_dir)
list_dir returns directory entries. ... ok
test_read_text (test_mcu_adapters.TestFilesAdapter.test_read_text)
read_text returns file content. ... ok
test_write_text (test_mcu_adapters.TestFilesAdapter.test_write_text)
write_text creates and writes to a file. ... ok
test_write_text_append (test_mcu_adapters.TestFilesAdapter.test_write_text_append)
write_text appends when append=True. ... ok
test_branch (test_mcu_adapters.TestGitAdapter.test_branch)
git branch returns current branch. ... ok
test_log (test_mcu_adapters.TestGitAdapter.test_log)
git log returns commit entries. ... ok
test_status (test_mcu_adapters.TestGitAdapter.test_status)
git status returns branch and clean flag. ... ok
test_get_volume_when_no_mpv (test_mcu_adapters.TestMediaAdapter.test_get_volume_when_no_mpv)
get_volume returns 0 when no mpv is running. ... ok
test_is_playing_when_no_mpv (test_mcu_adapters.TestMediaAdapter.test_is_playing_when_no_mpv)
is_playing returns False when no mpv is running. ... ok
test_procedural_memory (test_mcu_adapters.TestMemoryManager.test_procedural_memory)
Procedural memory tracks success rates. ... ok
test_search_all (test_mcu_adapters.TestMemoryManager.test_search_all)
Search across all memory types. ... ok
test_store_and_recall (test_mcu_adapters.TestMemoryManager.test_store_and_recall)
Store and recall across memory types. ... ok
test_notify_returns_delivered (test_mcu_adapters.TestNotifyAdapter.test_notify_returns_delivered)
notify_send returns delivered flag. ... ok
test_failure_patterns (test_mcu_adapters.TestPatternDetector.test_failure_patterns)
Repeated failures are detected. ... ok
test_goal_patterns (test_mcu_adapters.TestPatternDetector.test_goal_patterns)
Recurring goals are detected. ... ok
test_suggest_and_flush (test_mcu_adapters.TestProactiveEngine.test_suggest_and_flush)
Messages can be suggested and flushed. ... ok
test_analyze_failure_suggests_adaptation (test_mcu_adapters.TestReasoner.test_analyze_failure_suggests_adaptation)
Failure analysis produces adaptation suggestions. ... ok
test_assess_decreases_confidence_for_destructive (test_mcu_adapters.TestReasoner.test_assess_decreases_confidence_for_destructive)
Destructive goals get lower confidence. ... ok
test_assess_goal_with_primitives (test_mcu_adapters.TestReasoner.test_assess_goal_with_primitives)
Goal assessment returns execute when primitives are available. ... ok
test_adapter_registration (test_mcu_adapters.TestRegistry.test_adapter_registration)
Adapters register themselves on import. ... ok
test_build_catalog (test_mcu_adapters.TestRegistry.test_build_catalog)
build_catalog includes registered primitives. ... ok
test_discover_modules (test_mcu_adapters.TestRegistry.test_discover_modules)
discover_modules finds adapter files. ... ok
test_cpu_info (test_mcu_adapters.TestSystemAdapter.test_cpu_info)
cpu_info returns model and cores. ... ok
test_memory_info (test_mcu_adapters.TestSystemAdapter.test_memory_info)
memory_info returns total and available. ... ok
test_contract_registers_primitive (test_mcu_core.TestContracts.test_contract_registers_primitive)
A @contract-decorated function appears in REGISTRY. ... ok
test_contract_rejects_private (test_mcu_core.TestContracts.test_contract_rejects_private)
A @contract decorator on a private function raises TypeError. ... ok
test_idempotency_enum (test_mcu_core.TestContracts.test_idempotency_enum)
Idempotency enum values are correct. ... ok
test_friday_error_is_base (test_mcu_core.TestErrors.test_friday_error_is_base)
All errors inherit from FridayError. ... ok
test_primitive_error_has_state (test_mcu_core.TestErrors.test_primitive_error_has_state)
PrimitiveError carries state information. ... ok
test_emit_and_subscribe (test_mcu_core.TestEventBus.test_emit_and_subscribe)
Events are delivered to subscribers. ... ok
test_event_to_dict (test_mcu_core.TestEventBus.test_event_to_dict)
Event serialization works. ... ok
test_global_subscriber (test_mcu_core.TestEventBus.test_global_subscriber)
Global subscribers receive all events. ... ok
test_history (test_mcu_core.TestEventBus.test_history)
Event history is maintained. ... ok
test_subscriber_error_doesnt_crash (test_mcu_core.TestEventBus.test_subscriber_error_doesnt_crash)
Subscriber errors are caught and ignored. ... ok
test_unsubscribe (test_mcu_core.TestEventBus.test_unsubscribe)
Unsubscribed callbacks stop receiving events. ... ok
test_episodic_memory_store_and_search (test_mcu_core.TestMemoryStore.test_episodic_memory_store_and_search)
Episodic memory stores and searches. ... ok
test_memory_manager_context_building (test_mcu_core.TestMemoryStore.test_memory_manager_context_building)
MemoryManager builds context for the planner. ... ok
test_procedural_memory_pattern (test_mcu_core.TestMemoryStore.test_procedural_memory_pattern)
Procedural memory stores and recalls patterns. ... ok
test_semantic_memory_store_and_recall (test_mcu_core.TestMemoryStore.test_semantic_memory_store_and_recall)
Semantic memory stores and recalls. ... ok
test_working_memory_expiry (test_mcu_core.TestMemoryStore.test_working_memory_expiry)
Working memory entries expire after TTL. ... ok
test_working_memory_store_and_recall (test_mcu_core.TestMemoryStore.test_working_memory_store_and_recall)
Working memory stores and recalls entries. ... ok
test_goal_pattern_detection (test_mcu_core.TestPatternDetector.test_goal_pattern_detection)
Recurring goals are detected as patterns. ... ok
test_low_confidence_suppressed (test_mcu_core.TestProactiveEngine.test_low_confidence_suppressed)
Low-confidence messages are suppressed. ... ok
test_proactive_message_queued (test_mcu_core.TestProactiveEngine.test_proactive_message_queued)
Messages are queued when conditions are met (bypass quiet hours in test). ... ok
test_quiet_hours_suppress (test_mcu_core.TestProactiveEngine.test_quiet_hours_suppress)
Messages are suppressed during quiet hours. ... ok
test_channel_send_delivers_via_adapter (test_mcu_fixes.TestBuiltinChannels.test_channel_send_delivers_via_adapter) ... ok
test_registers_only_credentialed_platforms (test_mcu_fixes.TestBuiltinChannels.test_registers_only_credentialed_platforms) ... ok
test_gmail_check_uses_module_primitive (test_mcu_fixes.TestChecksReadRealState.test_gmail_check_uses_module_primitive) ... ok
test_window_checks_read_live_clients (test_mcu_fixes.TestChecksReadRealState.test_window_checks_read_live_clients) ... ok
test_existing_env_wins (test_mcu_fixes.TestCredentialLoader.test_existing_env_wins) ... ok
test_loads_sections_into_env (test_mcu_fixes.TestCredentialLoader.test_loads_sections_into_env) ... ok
test_missing_file_is_noop (test_mcu_fixes.TestCredentialLoader.test_missing_file_is_noop) ... ok
test_bypass_requires_dangerous_env (test_mcu_fixes.TestDevRunInvocation.test_bypass_requires_dangerous_env) ... ok
test_posix_no_shell_and_flags_preserved (test_mcu_fixes.TestDevRunInvocation.test_posix_no_shell_and_flags_preserved) ... ok
test_windows_uses_shell_with_joined_command (test_mcu_fixes.TestDevRunInvocation.test_windows_uses_shell_with_joined_command) ... ok
test_poll_filters_by_watermark (test_mcu_fixes.TestDiscordWatermark.test_poll_filters_by_watermark) ... ok
test_concurrent_emit (test_mcu_fixes.TestEventBusThreadSafety.test_concurrent_emit) ... ok
test_raising_subscriber_does_not_break_bus (test_mcu_fixes.TestEventBusThreadSafety.test_raising_subscriber_does_not_break_bus) ... ok
test_unsubscribe_stops_delivery (test_mcu_fixes.TestEventBusThreadSafety.test_unsubscribe_stops_delivery) ... ok
test_logs_when_run_id_given (test_mcu_fixes.TestExecutorLogging.test_logs_when_run_id_given) ... ok
test_no_log_without_run_id (test_mcu_fixes.TestExecutorLogging.test_no_log_without_run_id) ... ok
test_failed_verify_aborts_not_completes (test_mcu_fixes.TestExecutorVerifyDiscipline.test_failed_verify_aborts_not_completes) ... ok
test_passing_verify_verifies (test_mcu_fixes.TestExecutorVerifyDiscipline.test_passing_verify_verifies) ... ok
test_unresolvable_ref_aborts (test_mcu_fixes.TestExecutorVerifyDiscipline.test_unresolvable_ref_aborts) ... ok
test_confidence_floor_applies_to_substring_matches (test_mcu_fixes.TestLearnerFixes.test_confidence_floor_applies_to_substring_matches) ... ok
test_duration_lesson_no_duplicate_prefix (test_mcu_fixes.TestLearnerFixes.test_duration_lesson_no_duplicate_prefix) ... ok
test_consolidate_decay_persisted (test_mcu_fixes.TestMemoryPersistence.test_consolidate_decay_persisted) ... ok
test_prune_persisted (test_mcu_fixes.TestMemoryPersistence.test_prune_persisted) ... ok
test_cache_returns_isolated_copies (test_mcu_fixes.TestPlannerValidationAndTemplates.test_cache_returns_isolated_copies) ... ok
test_git_template_uses_correct_arg (test_mcu_fixes.TestPlannerValidationAndTemplates.test_git_template_uses_correct_arg) ... ok
test_send_template_never_fabricates_default (test_mcu_fixes.TestPlannerValidationAndTemplates.test_send_template_never_fabricates_default) ... ok
test_system_template_valid (test_mcu_fixes.TestPlannerValidationAndTemplates.test_system_template_valid) ... ok
test_validate_rejects_missing_required_arg (test_mcu_fixes.TestPlannerValidationAndTemplates.test_validate_rejects_missing_required_arg) ... ok
test_validate_rejects_unknown_arg (test_mcu_fixes.TestPlannerValidationAndTemplates.test_validate_rejects_unknown_arg) ... ok
test_flush_sends_and_records_learning (test_mcu_fixes.TestProactiveChannelDelivery.test_flush_sends_and_records_learning) ... ok
test_mark_read_only_advances (test_mcu_fixes.TestTelegramCommitModel.test_mark_read_only_advances) ... ok
test_poll_media_only_returns_media (test_mcu_fixes.TestTelegramCommitModel.test_poll_media_only_returns_media) ... ok
test_poll_updates_commit_semantics (test_mcu_fixes.TestTelegramCommitModel.test_poll_updates_commit_semantics) ... ok
test_default_config_is_mcu_specific (test_mcu_fixes.TestWatcherMcuConfig.test_default_config_is_mcu_specific) ... ok
test_inline_calendar_plan_validates (test_mcu_fixes.TestWatcherMcuConfig.test_inline_calendar_plan_validates) ... ok
test_sample_triggers_load_and_are_inert (test_mcu_fixes.TestWatcherMcuConfig.test_sample_triggers_load_and_are_inert) ... ok
test_file_seen_state_survives_restart (test_mcu_fixes.TestWatcherSemantics.test_file_seen_state_survives_restart) ... ok
test_inline_plan_runs_without_llm (test_mcu_fixes.TestWatcherSemantics.test_inline_plan_runs_without_llm) ... ok
test_cli_records_learning (test_mcu_learning.TestLearningIntegration.test_cli_records_learning)
CLI cmd_run records learning outcomes. ... ok
test_learning_context_included_in_planner_prompt (test_mcu_learning.TestLearningIntegration.test_learning_context_included_in_planner_prompt)
The planner prompt includes learning context when available. ... ok
test_apply_lesson (test_mcu_learning.TestMemoryLearner.test_apply_lesson)
Lessons can be marked as applied. ... ok
test_build_learning_context (test_mcu_learning.TestMemoryLearner.test_build_learning_context)
Learning context provides useful info for the planner. ... ok
test_consolidation (test_mcu_learning.TestMemoryLearner.test_consolidation)
Consolidation decays unused lessons and prunes weak ones. ... ok
test_duration_tracking (test_mcu_learning.TestMemoryLearner.test_duration_tracking)
Duration lessons track expected duration. ... ok
test_empty_goal_no_context (test_mcu_learning.TestMemoryLearner.test_empty_goal_no_context)
No history means empty learning context. ... ok
test_error_classification (test_mcu_learning.TestMemoryLearner.test_error_classification)
Errors are classified into categories. ... ok
test_persistence (test_mcu_learning.TestMemoryLearner.test_persistence)
Lessons persist across instances. ... ok
test_record_failure_outcome (test_mcu_learning.TestMemoryLearner.test_record_failure_outcome)
Failed outcomes produce failure lessons. ... ok
test_record_success_outcome (test_mcu_learning.TestMemoryLearner.test_record_success_outcome)
Successful outcomes produce success lessons. ... ok
test_repeated_failure_increases_confidence (test_mcu_learning.TestMemoryLearner.test_repeated_failure_increases_confidence)
Repeated failures of same type increase lesson confidence. ... ok
test_repeated_success_increases_confidence (test_mcu_learning.TestMemoryLearner.test_repeated_success_increases_confidence)
Repeated successes increase lesson confidence. ... ok
test_stats (test_mcu_learning.TestMemoryLearner.test_stats)
Stats report learning state. ... ok
test_empty_history_returns_neutral (test_mcu_natural.TestLearning.test_empty_history_returns_neutral)
Empty history returns neutral tone. ... ok
test_record_and_get_preferred_tone (test_mcu_natural.TestLearning.test_record_and_get_preferred_tone)
Recorded tones influence preferred tone. ... ok
test_stats (test_mcu_natural.TestLearning.test_stats)
Stats report communication state. ... ok
test_to_dict (test_mcu_natural.TestMessageToDict.test_to_dict)
NaturalMessage serialization works. ... ok
test_build_confirmation_formal (test_mcu_natural.TestNaturalComms.test_build_confirmation_formal)
Formal confirmation is more formal. ... ok
test_build_confirmation_request (test_mcu_natural.TestNaturalComms.test_build_confirmation_request)
Confirmation requests ask before acting. ... ok
test_build_daily_briefing (test_mcu_natural.TestNaturalComms.test_build_daily_briefing)
Daily briefings are formatted nicely. ... ok
test_build_error_report (test_mcu_natural.TestNaturalComms.test_build_error_report)
Error reports are clear. ... ok
test_build_error_report_with_attempts (test_mcu_natural.TestNaturalComms.test_build_error_report_with_attempts)
Error reports include attempt count. ... ok
test_build_goal_result_failure (test_mcu_natural.TestNaturalComms.test_build_goal_result_failure)
Failure messages include the error. ... ok
test_build_goal_result_progressive_disclosure (test_mcu_natural.TestNaturalComms.test_build_goal_result_progressive_disclosure)
Summary is separate from full content. ... ok
test_build_goal_result_success (test_mcu_natural.TestNaturalComms.test_build_goal_result_success)
Success messages are natural and informative. ... ok
test_build_goal_result_with_details (test_mcu_natural.TestNaturalComms.test_build_goal_result_with_details)
Details are included in full content. ... ok
test_build_proactive_suggestion (test_mcu_natural.TestNaturalComms.test_build_proactive_suggestion)
Proactive suggestions are natural. ... ok
test_daily_briefing_empty (test_mcu_natural.TestNaturalComms.test_daily_briefing_empty)
Empty briefing still produces output. ... ok
test_discord_keeps_markdown (test_mcu_natural.TestPlatformFormatting.test_discord_keeps_markdown)
Discord keeps markdown formatting. ... ok
test_telegram_keeps_markdown (test_mcu_natural.TestPlatformFormatting.test_telegram_keeps_markdown)
Telegram keeps markdown formatting. ... ok
test_whatsapp_strips_markdown (test_mcu_natural.TestPlatformFormatting.test_whatsapp_strips_markdown)
WhatsApp strips markdown formatting. ... ok
test_all_profiles_exist (test_mcu_natural.TestToneProfiles.test_all_profiles_exist)
All predefined tone profiles exist. ... ok
test_casual_tone_has_emoji (test_mcu_natural.TestToneProfiles.test_casual_tone_has_emoji)
Casual tone has emoji. ... ok
test_formal_tone_has_no_emoji (test_mcu_natural.TestToneProfiles.test_formal_tone_has_no_emoji)
Formal tone has no emoji. ... ok
test_profile_to_dict (test_mcu_natural.TestToneProfiles.test_profile_to_dict)
Profile serialization works. ... ok
test_evening_use_personal_tone (test_mcu_natural.TestToneSelection.test_evening_use_personal_tone)
Evening hours default to personal tone. ... ok
test_explicit_tone_overrides (test_mcu_natural.TestToneSelection.test_explicit_tone_overrides)
Explicit tone in context overrides everything. ... ok
test_neutral_default (test_mcu_natural.TestToneSelection.test_neutral_default)
Unknown context defaults to neutral. ... ok
test_platform_tone_override (test_mcu_natural.TestToneSelection.test_platform_tone_override)
Platform-specific tone overrides time heuristic. ... ok
test_work_hours_use_work_tone (test_mcu_natural.TestToneSelection.test_work_hours_use_work_tone)
Work hours default to work tone. ... ok
test_full_message_flow (test_mcu_natural_integration.TestNaturalCommsEndToEnd.test_full_message_flow)
A goal result flows through NaturalComms from execution to notification. ... ok
test_flush_emits_tone_in_event (test_mcu_natural_integration.TestProactiveNaturalWiring.test_flush_emits_tone_in_event)
flush() includes tone in the MESSAGE_SENT event. ... ok
test_flush_formats_with_natural_comms (test_mcu_natural_integration.TestProactiveNaturalWiring.test_flush_formats_with_natural_comms)
flush() formats queued messages through NaturalComms before sending. ... ok
test_flush_records_tone_in_metadata (test_mcu_natural_integration.TestProactiveNaturalWiring.test_flush_records_tone_in_metadata)
flush() records the tone used in message metadata. ... ok
test_notify_outcome_failure_uses_natural_comms (test_mcu_natural_integration.TestWatcherNaturalWiring.test_notify_outcome_failure_uses_natural_comms)
_notify_outcome formats error messages through NaturalComms. ... ok
test_notify_outcome_uses_natural_comms (test_mcu_natural_integration.TestWatcherNaturalWiring.test_notify_outcome_uses_natural_comms)
_notify_outcome formats messages through NaturalComms. ... ok
test_text_trigger_reply_uses_natural_comms (test_mcu_natural_integration.TestWatcherNaturalWiring.test_text_trigger_reply_uses_natural_comms)
Text trigger replies use NaturalComms for formatting. ... ok
test_anomaly_severity_sorting (test_mcu_observer.TestAnomalyDetector.test_anomaly_severity_sorting)
Anomalies are sorted by severity. ... ok
test_anomaly_to_dict (test_mcu_observer.TestAnomalyDetector.test_anomaly_to_dict)
Anomaly serialization works. ... ok
test_empty_tasks_no_anomalies (test_mcu_observer.TestAnomalyDetector.test_empty_tasks_no_anomalies)
Empty task list produces no anomalies. ... ok
test_failure_streak_detected (test_mcu_observer.TestAnomalyDetector.test_failure_streak_detected)
Consecutive failures produce an anomaly. ... ok
test_no_streak_on_successes (test_mcu_observer.TestAnomalyDetector.test_no_streak_on_successes)
Successful goals don't produce failure streaks. ... ok
test_performance_degradation (test_mcu_observer.TestAnomalyDetector.test_performance_degradation)
Goals taking much longer than usual produce anomalies. ... ok
test_resolve_anomaly (test_mcu_observer.TestAnomalyDetector.test_resolve_anomaly)
Anomalies can be marked as resolved. ... ok
test_stats (test_mcu_observer.TestAnomalyDetector.test_stats)
Stats report detector state. ... ok
test_empty_tasks_no_predictions (test_mcu_observer.TestPredictionEngine.test_empty_tasks_no_predictions)
Empty task list produces no predictions. ... ok
test_predict_next_goal (test_mcu_observer.TestPredictionEngine.test_predict_next_goal)
Recurring goals produce predictions. ... ok
test_predict_success_rate (test_mcu_observer.TestPredictionEngine.test_predict_success_rate)
Goals with mixed results produce success rate predictions. ... ok
test_predict_timing (test_mcu_observer.TestPredictionEngine.test_predict_timing)
Repeated goals at the same hour produce timing predictions. ... ok
test_prediction_to_dict (test_mcu_observer.TestPredictionEngine.test_prediction_to_dict)
Prediction serialization works. ... ok
test_prediction_validity (test_mcu_observer.TestPredictionEngine.test_prediction_validity)
Predictions expire after their validity window. ... ok
test_build_context (test_mcu_observer.TestUserModel.test_build_context)
Context builder produces text for the planner. ... ok
test_low_confidence_preference_returns_none (test_mcu_observer.TestUserModel.test_low_confidence_preference_returns_none)
Low confidence preferences are hidden. ... ok
test_observe_goal_detects_habits (test_mcu_observer.TestUserModel.test_observe_goal_detects_habits)
Repeated goals at similar times create habits. ... ok
test_observe_goal_records_history (test_mcu_observer.TestUserModel.test_observe_goal_records_history)
Goal observations are recorded. ... ok
test_persistence (test_mcu_observer.TestUserModel.test_persistence)
Model persists across instances. ... ok
test_preference_confidence_increase (test_mcu_observer.TestUserModel.test_preference_confidence_increase)
Repeated same-value observations increase confidence. ... ok
test_preference_new_value_replaces_if_higher_confidence (test_mcu_observer.TestUserModel.test_preference_new_value_replaces_if_higher_confidence)
Higher confidence new value replaces old. ... ok
test_record_and_get_preference (test_mcu_observer.TestUserModel.test_record_and_get_preference)
Preferences can be recorded and retrieved. ... ok
test_stats (test_mcu_observer.TestUserModel.test_stats)
Stats report model state. ... ok
test_adapters_command (test_mcu_phone.TestChatCommandRouting.test_adapters_command) ... ok
test_chatter_not_consumed_no_reply (test_mcu_phone.TestChatCommandRouting.test_chatter_not_consumed_no_reply) ... ok
test_empty_prefix_makes_plain_text_a_goal (test_mcu_phone.TestChatCommandRouting.test_empty_prefix_makes_plain_text_a_goal) ... ok
test_extract_goal_backcompat (test_mcu_phone.TestChatCommandRouting.test_extract_goal_backcompat) ... ok
test_goal_prefix_env_override (test_mcu_phone.TestChatCommandRouting.test_goal_prefix_env_override) ... ok
test_goal_prefix_falls_through (test_mcu_phone.TestChatCommandRouting.test_goal_prefix_falls_through) ... ok
test_goal_prefix_without_goal_gets_usage (test_mcu_phone.TestChatCommandRouting.test_goal_prefix_without_goal_gets_usage) ... ok
test_help_command (test_mcu_phone.TestChatCommandRouting.test_help_command) ... ok
test_memory_command (test_mcu_phone.TestChatCommandRouting.test_memory_command) ... ok
test_phone_command (test_mcu_phone.TestChatCommandRouting.test_phone_command) ... ok
test_status_command (test_mcu_phone.TestChatCommandRouting.test_status_command) ... ok
test_unknown_slash_gets_help (test_mcu_phone.TestChatCommandRouting.test_unknown_slash_gets_help) ... ok
test_phone_get_post (test_mcu_phone.TestPhoneApiEndpoints.test_phone_get_post) ... ok
test_phone_context_in_full_context (test_mcu_phone.TestPhonePlannerContext.test_phone_context_in_full_context) ... ok
test_allowlist_drops_unknown_keys (test_mcu_phone.TestPhoneState.test_allowlist_drops_unknown_keys) ... ok
test_context_marks_dnd (test_mcu_phone.TestPhoneState.test_context_marks_dnd) ... ok
test_context_render (test_mcu_phone.TestPhoneState.test_context_render) ... ok
test_empty_value_clears_key (test_mcu_phone.TestPhoneState.test_empty_value_clears_key) ... ok
test_no_state_returns_empty (test_mcu_phone.TestPhoneState.test_no_state_returns_empty) ... ok
test_sensors_allowlisted (test_mcu_phone.TestPhoneState.test_sensors_allowlisted)
Only allowlisted sensor keys are persisted. ... ok
test_sms_and_notification_sensors (test_mcu_phone.TestPhoneState.test_sms_and_notification_sensors)
SMS/call/notification telemetry persists and renders. ... ok
test_update_and_get_roundtrip (test_mcu_phone.TestPhoneState.test_update_and_get_roundtrip) ... ok
test_chatter_consumed_no_reply (test_mcu_phone.TestTextTriggerRouting.test_chatter_consumed_no_reply) ... ok
test_discord_reply_uses_channel_id_kwarg (test_mcu_phone.TestTextTriggerRouting.test_discord_reply_uses_channel_id_kwarg)
Regression: discord.send_text takes channel_id=, not to= — the old ... ok
test_friday_command_replies_without_llm (test_mcu_phone.TestTextTriggerRouting.test_friday_command_replies_without_llm) ... ok
test_goal_message_executes_and_replies (test_mcu_phone.TestTextTriggerRouting.test_goal_message_executes_and_replies) ... ok
test_goal_prefix_env_used (test_mcu_phone.TestTextTriggerRouting.test_goal_prefix_env_used) ... ok
test_empty_prefix_returns_all (test_mcu_watcher.TestCommandPrefix.test_empty_prefix_returns_all) ... ok
test_extract_goal_case_insensitive (test_mcu_watcher.TestCommandPrefix.test_extract_goal_case_insensitive) ... ok
test_extract_goal_with_prefix (test_mcu_watcher.TestCommandPrefix.test_extract_goal_with_prefix) ... ok
test_no_prefix_returns_none (test_mcu_watcher.TestCommandPrefix.test_no_prefix_returns_none) ... ok
test_prefix_only_returns_none (test_mcu_watcher.TestCommandPrefix.test_prefix_only_returns_none) ... ok
test_corrupt_file_returns_empty (test_mcu_watcher.TestFiredState.test_corrupt_file_returns_empty) ... ok
test_missing_file_returns_empty (test_mcu_watcher.TestFiredState.test_missing_file_returns_empty) ... ok
test_save_and_load_fired_state (test_mcu_watcher.TestFiredState.test_save_and_load_fired_state) ... ok
test_proactive_tick_dedupes_notified_patterns (test_mcu_watcher.TestProactiveTick.test_proactive_tick_dedupes_notified_patterns)
A pattern already in the notified set is not re-sent. ... ok
test_proactive_tick_does_not_crash_on_empty_memory (test_mcu_watcher.TestProactiveTick.test_proactive_tick_does_not_crash_on_empty_memory)
Proactive tick handles empty memory gracefully. ... ok
test_proactive_tick_filters_scheduled_goals (test_mcu_watcher.TestProactiveTick.test_proactive_tick_filters_scheduled_goals)
Patterns matching scheduled trigger goals are not reported. ... ok
test_proactive_tick_respects_confidence_and_frequency_floors (test_mcu_watcher.TestProactiveTick.test_proactive_tick_respects_confidence_and_frequency_floors)
Patterns below the confidence/frequency floors are not suggested. ... ok
test_proactive_tick_stores_patterns (test_mcu_watcher.TestProactiveTick.test_proactive_tick_stores_patterns)
Detected patterns are stored as semantic memories. ... ok
test_in_backoff_within_window (test_mcu_watcher.TestRetryBackoff.test_in_backoff_within_window) ... ok
test_not_in_backoff_after_window (test_mcu_watcher.TestRetryBackoff.test_not_in_backoff_after_window) ... ok
test_not_in_backoff_unknown_trigger (test_mcu_watcher.TestRetryBackoff.test_not_in_backoff_unknown_trigger) ... ok
test_record_task_writes_jsonl (test_mcu_watcher.TestTaskRecording.test_record_task_writes_jsonl) ... ok
test_empty_allowlist_not_reached (test_mcu_watcher.TestWatcherAllowlist.test_empty_allowlist_not_reached) ... ok
test_exact_match (test_mcu_watcher.TestWatcherAllowlist.test_exact_match) ... ok
test_multiple_patterns (test_mcu_watcher.TestWatcherAllowlist.test_multiple_patterns) ... ok
test_no_match (test_mcu_watcher.TestWatcherAllowlist.test_no_match) ... ok
test_pattern_match (test_mcu_watcher.TestWatcherAllowlist.test_pattern_match) ... ok
test_triggers_command_bad_config (test_mcu_watcher.TestWatcherCLI.test_triggers_command_bad_config)
triggers command handles bad config gracefully. ... ok
test_triggers_command_lists_triggers (test_mcu_watcher.TestWatcherCLI.test_triggers_command_lists_triggers)
triggers command lists configured triggers. ... ok
test_bad_json_raises (test_mcu_watcher.TestWatcherConfig.test_bad_json_raises)
Malformed JSON raises FridayError. ... ok
test_bad_schedule_type_raises (test_mcu_watcher.TestWatcherConfig.test_bad_schedule_type_raises)
Unknown schedule type raises FridayError. ... ok
test_bad_time_format_raises (test_mcu_watcher.TestWatcherConfig.test_bad_time_format_raises)
Invalid HH:MM raises FridayError. ... ok
test_duplicate_id_raises (test_mcu_watcher.TestWatcherConfig.test_duplicate_id_raises)
Duplicate trigger IDs raise FridayError. ... ok
test_file_schedule_needs_directory (test_mcu_watcher.TestWatcherConfig.test_file_schedule_needs_directory)
File schedule without directory raises FridayError. ... ok
test_load_valid_config (test_mcu_watcher.TestWatcherConfig.test_load_valid_config)
Valid config loads successfully. ... ok
test_missing_config_raises (test_mcu_watcher.TestWatcherConfig.test_missing_config_raises)
Missing config file raises FridayError. ... ok
test_missing_goal_and_plan_raises (test_mcu_watcher.TestWatcherConfig.test_missing_goal_and_plan_raises)
Trigger without goal or plan raises FridayError. ... ok
test_unknown_day_raises (test_mcu_watcher.TestWatcherConfig.test_unknown_day_raises)
Unknown day name raises FridayError. ... ok
test_valid_file_schedule (test_mcu_watcher.TestWatcherConfig.test_valid_file_schedule)
Valid file schedule loads. ... ok
test_missing_directory_returns_empty (test_mcu_watcher.TestWatcherNewFiles.test_missing_directory_returns_empty) ... ok
test_new_files_detected (test_mcu_watcher.TestWatcherNewFiles.test_new_files_detected) ... ok
test_non_matching_files_ignored (test_mcu_watcher.TestWatcherNewFiles.test_non_matching_files_ignored) ... ok
test_seen_files_not_repeated (test_mcu_watcher.TestWatcherNewFiles.test_seen_files_not_repeated) ... ok
test_once_fires_due_trigger (test_mcu_watcher.TestWatcherRunOnce.test_once_fires_due_trigger)
--once fires a due trigger and exits. ... ok
test_once_skips_disabled_trigger (test_mcu_watcher.TestWatcherRunOnce.test_once_skips_disabled_trigger)
--once skips disabled triggers. ... ok
test_once_with_inline_plan_skips_llm (test_mcu_watcher.TestWatcherRunOnce.test_once_with_inline_plan_skips_llm)
Inline deterministic plans execute directly without an LLM plan. ... ok
test_day_filter_allows_correct_day (test_mcu_watcher.TestWatcherScheduling.test_day_filter_allows_correct_day)
Trigger fires on included days. ... ok
test_day_filter_blocks_wrong_day (test_mcu_watcher.TestWatcherScheduling.test_day_filter_blocks_wrong_day)
Trigger doesn't fire on excluded days. ... ok
test_time_due_after_at (test_mcu_watcher.TestWatcherScheduling.test_time_due_after_at)
Trigger is due when current time is past the scheduled time. ... ok
test_time_due_on_different_day (test_mcu_watcher.TestWatcherScheduling.test_time_due_on_different_day)
Trigger is due on a new day even if fired yesterday. ... ok
test_time_not_due_before_at (test_mcu_watcher.TestWatcherScheduling.test_time_not_due_before_at)
Trigger is not due before the scheduled time. ... ok
test_time_not_due_if_already_fired (test_mcu_watcher.TestWatcherScheduling.test_time_not_due_if_already_fired)
Trigger is not due if already fired today. ... ok
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
test_build_memory_context_category_filter (test_memory.TestMemoryBuildContext.test_build_memory_context_category_filter) ... ok
test_build_memory_context_empty (test_memory.TestMemoryBuildContext.test_build_memory_context_empty) ... ok
test_build_memory_context_with_memories (test_memory.TestMemoryBuildContext.test_build_memory_context_with_memories) ... ok
test_concurrent_store_retrieve (test_memory.TestMemoryEdgeCases.test_concurrent_store_retrieve) ... ok
test_corrupted_memory_file (test_memory.TestMemoryEdgeCases.test_corrupted_memory_file)
Test that corrupted memory file is handled gracefully. ... ok
test_memory_file_atomicity (test_memory.TestMemoryEdgeCases.test_memory_file_atomicity)
Test that writes are atomic (no partial writes on crash). ... ok
test_retrieve_tag_boost (test_memory.TestMemoryEdgeCases.test_retrieve_tag_boost) ... ok
test_store_special_characters (test_memory.TestMemoryEdgeCases.test_store_special_characters) ... ok
test_forget_empty_key (test_memory.TestMemoryForget.test_forget_empty_key) ... ok
test_forget_existing (test_memory.TestMemoryForget.test_forget_existing) ... ok
test_forget_nonexistent (test_memory.TestMemoryForget.test_forget_nonexistent) ... ok
test_forget_with_category (test_memory.TestMemoryForget.test_forget_with_category) ... ok
test_memory_has_key_found (test_memory.TestMemoryL2Checks.test_memory_has_key_found) ... ok
test_memory_has_key_not_found (test_memory.TestMemoryL2Checks.test_memory_has_key_not_found) ... ok
test_memory_has_key_with_category (test_memory.TestMemoryL2Checks.test_memory_has_key_with_category) ... ok
test_memory_retrieval_ok_found (test_memory.TestMemoryL2Checks.test_memory_retrieval_ok_found) ... ok
test_memory_retrieval_ok_not_found (test_memory.TestMemoryL2Checks.test_memory_retrieval_ok_not_found) ... ok
test_memory_store_status (test_memory.TestMemoryL2Checks.test_memory_store_status) ... ok
test_empty_store (test_memory.TestMemoryListCategories.test_empty_store) ... ok
test_with_entries (test_memory.TestMemoryListCategories.test_with_entries) ... ok
test_maintenance_archives_old_low_access (test_memory.TestMemoryMaintenance.test_maintenance_archives_old_low_access) ... ok
test_maintenance_keeps_frequent (test_memory.TestMemoryMaintenance.test_maintenance_keeps_frequent) ... ok
test_maintenance_keeps_fresh (test_memory.TestMemoryMaintenance.test_maintenance_keeps_fresh) ... ok
test_maintenance_no_entries (test_memory.TestMemoryMaintenance.test_maintenance_no_entries) ... ok
test_build_memory_block_empty (test_memory.TestMemoryPlannerIntegration.test_build_memory_block_empty) ... ok
test_build_memory_block_import_error (test_memory.TestMemoryPlannerIntegration.test_build_memory_block_import_error)
Test that import errors are handled gracefully. ... ok
test_build_memory_block_with_memories (test_memory.TestMemoryPlannerIntegration.test_build_memory_block_with_memories) ... ok
test_record_decision (test_memory.TestMemoryRecordDecision.test_record_decision) ... ok
test_record_decision_empty (test_memory.TestMemoryRecordDecision.test_record_decision_empty) ... ok
test_record_decision_empty_rationale (test_memory.TestMemoryRecordDecision.test_record_decision_empty_rationale) ... ok
test_record_success (test_memory.TestMemoryRecordSuccess.test_record_success) ... ok
test_record_success_empty_goal (test_memory.TestMemoryRecordSuccess.test_record_success_empty_goal) ... ok
test_reinforce_empty_key (test_memory.TestMemoryReinforce.test_reinforce_empty_key) ... ok
test_reinforce_existing (test_memory.TestMemoryReinforce.test_reinforce_existing) ... ok
test_reinforce_nonexistent (test_memory.TestMemoryReinforce.test_reinforce_nonexistent) ... ok
test_retrieve_by_value (test_memory.TestMemoryRetrieve.test_retrieve_by_value) ... ok
test_retrieve_empty_query (test_memory.TestMemoryRetrieve.test_retrieve_empty_query) ... ok
test_retrieve_exact_key (test_memory.TestMemoryRetrieve.test_retrieve_exact_key) ... ok
test_retrieve_invalid_category (test_memory.TestMemoryRetrieve.test_retrieve_invalid_category) ... ok
test_retrieve_no_match (test_memory.TestMemoryRetrieve.test_retrieve_no_match) ... ok
test_retrieve_reinforces_access (test_memory.TestMemoryRetrieve.test_retrieve_reinforces_access) ... ok
test_retrieve_relevance_ranking (test_memory.TestMemoryRetrieve.test_retrieve_relevance_ranking) ... ok
test_retrieve_respects_limit (test_memory.TestMemoryRetrieve.test_retrieve_respects_limit) ... ok
test_retrieve_with_category_filter (test_memory.TestMemoryRetrieve.test_retrieve_with_category_filter) ... ok
test_store_all_categories (test_memory.TestMemoryStore.test_store_all_categories) ... ok
test_store_basic (test_memory.TestMemoryStore.test_store_basic) ... ok
test_store_empty_key (test_memory.TestMemoryStore.test_store_empty_key) ... ok
test_store_empty_value (test_memory.TestMemoryStore.test_store_empty_value) ... ok
test_store_invalid_category (test_memory.TestMemoryStore.test_store_invalid_category) ... ok
test_store_truncates_long_values (test_memory.TestMemoryStore.test_store_truncates_long_values) ... ok
test_store_update_existing (test_memory.TestMemoryStore.test_store_update_existing) ... ok
test_store_with_tags (test_memory.TestMemoryStore.test_store_with_tags) ... ok
test_empty_store (test_memory.TestMemorySummary.test_empty_store) ... ok
test_with_entries (test_memory.TestMemorySummary.test_with_entries) ... ok
test_sync_lessons_empty_approved (test_memory.TestMemorySyncLessons.test_sync_lessons_empty_approved) ... ok
test_sync_lessons_with_approved (test_memory.TestMemorySyncLessons.test_sync_lessons_with_approved) ... ok
test_send_file_missing (test_messaging.TestDiscord.test_send_file_missing) ... ok
test_send_text_empty (test_messaging.TestDiscord.test_send_text_empty) ... ok
test_send_document_missing_file (test_messaging.TestTelegram.test_send_document_missing_file) ... ok
test_send_text_empty (test_messaging.TestTelegram.test_send_text_empty) ... ok
test_download_file_bad_dest (test_messaging.TestTelegramReceive.test_download_file_bad_dest) ... ok
test_download_file_empty_id (test_messaging.TestTelegramReceive.test_download_file_empty_id) ... ok
test_download_file_full_flow (test_messaging.TestTelegramReceive.test_download_file_full_flow)
End-to-end mocked download: getFile -> download binary. ... ok
test_poll_updates_empty (test_messaging.TestTelegramReceive.test_poll_updates_empty)
poll_updates returns empty list when no new messages. ... ok
test_poll_updates_extracts_media (test_messaging.TestTelegramReceive.test_poll_updates_extracts_media)
poll_updates extracts photo messages with file_id. ... ok
test_poll_updates_skips_text_messages (test_messaging.TestTelegramReceive.test_poll_updates_skips_text_messages)
Text-only messages are skipped (nothing to download). ... ok
test_clear_pending_media_all (test_messaging.TestWhatsapp.test_clear_pending_media_all) ... ok
test_clear_pending_media_selective (test_messaging.TestWhatsapp.test_clear_pending_media_selective) ... ok
test_download_media_bad_dest (test_messaging.TestWhatsapp.test_download_media_bad_dest) ... ok
test_download_media_empty_id (test_messaging.TestWhatsapp.test_download_media_empty_id) ... ok
test_download_media_ext_for_mime (test_messaging.TestWhatsapp.test_download_media_ext_for_mime)
The reverse MIME map covers common types. ... ok
test_download_media_fallback_filename (test_messaging.TestWhatsapp.test_download_media_fallback_filename)
When Content-Disposition is absent, fallback uses media_id + ext. ... ok
test_download_media_full_flow (test_messaging.TestWhatsapp.test_download_media_full_flow)
End-to-end mocked download: get_media_url -> download binary. ... ok
test_download_media_missing_dest_file (test_messaging.TestWhatsapp.test_download_media_missing_dest_file)
dest_dir must be an existing directory, not a file. ... ok
test_enqueue_and_load (test_messaging.TestWhatsapp.test_enqueue_and_load) ... ok
test_enqueue_deduplicates (test_messaging.TestWhatsapp.test_enqueue_deduplicates) ... ok
test_enqueue_empty_media_id (test_messaging.TestWhatsapp.test_enqueue_empty_media_id) ... ok
test_enqueue_multiple (test_messaging.TestWhatsapp.test_enqueue_multiple) ... ok
test_get_media_url_api_error (test_messaging.TestWhatsapp.test_get_media_url_api_error)
get_media_url raises PrimitiveError on non-200. ... ok
test_get_media_url_empty (test_messaging.TestWhatsapp.test_get_media_url_empty) ... ok
test_get_media_url_no_url_in_response (test_messaging.TestWhatsapp.test_get_media_url_no_url_in_response)
get_media_url raises PrimitiveError when url is missing. ... ok
test_get_media_url_whitespace (test_messaging.TestWhatsapp.test_get_media_url_whitespace) ... ok
test_load_pending_media_empty_on_missing_file (test_messaging.TestWhatsapp.test_load_pending_media_empty_on_missing_file) ... ok
test_mime_map (test_messaging.TestWhatsapp.test_mime_map) ... ok
test_mime_unknown_raises (test_messaging.TestWhatsapp.test_mime_unknown_raises) ... ok
test_send_document_missing_file (test_messaging.TestWhatsapp.test_send_document_missing_file) ... ok
test_send_text_bad_recipient (test_messaging.TestWhatsapp.test_send_text_bad_recipient) ... ok
test_send_text_empty (test_messaging.TestWhatsapp.test_send_text_empty) ... ok
test_upload_document_missing_file (test_messaging.TestWhatsapp.test_upload_document_missing_file) ... ok
test_delete_event_empty (test_new_primitives.TestCalendarDeleteEvent.test_delete_event_empty) ... ok
test_update_event_empty (test_new_primitives.TestCalendarUpdateEvent.test_update_event_empty) ... ok
test_copy_file (test_new_primitives.TestFilesCopy.test_copy_file) ... ok
test_copy_missing_dest (test_new_primitives.TestFilesCopy.test_copy_missing_dest) ... ok
test_copy_missing_source (test_new_primitives.TestFilesCopy.test_copy_missing_source) ... ok
test_delete_file (test_new_primitives.TestFilesDelete.test_delete_file) ... ok
test_delete_missing_file (test_new_primitives.TestFilesDelete.test_delete_missing_file) ... ok
test_file_size (test_new_primitives.TestFilesFileSize.test_file_size) ... ok
test_file_size_missing (test_new_primitives.TestFilesFileSize.test_file_size_missing) ... ok
test_list_dir (test_new_primitives.TestFilesListDir.test_list_dir) ... ok
test_list_dir_missing (test_new_primitives.TestFilesListDir.test_list_dir_missing) ... ok
test_move_file (test_new_primitives.TestFilesMove.test_move_file) ... ok
test_branch_detached (test_new_primitives.TestGitBranch.test_branch_detached) ... ok
test_branch_returns_current (test_new_primitives.TestGitBranch.test_branch_returns_current) ... ok
test_commit_empty_message (test_new_primitives.TestGitCommit.test_commit_empty_message) ... ok
test_commit_with_files (test_new_primitives.TestGitCommit.test_commit_with_files) ... ok
test_diff_empty_path (test_new_primitives.TestGitDiff.test_diff_empty_path) ... ok
test_diff_empty_repo (test_new_primitives.TestGitDiff.test_diff_empty_repo) ... ok
test_diff_missing_repo (test_new_primitives.TestGitDiff.test_diff_missing_repo) ... ok
test_diff_with_changes (test_new_primitives.TestGitDiff.test_diff_with_changes) ... ok
test_mark_read_empty (test_new_primitives.TestGmailMarkRead.test_mark_read_empty) ... ok
test_search_empty_query (test_new_primitives.TestGmailSearch.test_search_empty_query) ... ok
test_send_text_empty (test_new_primitives.TestGmailSendText.test_send_text_empty) ... ok
test_send_text_no_recipient (test_new_primitives.TestGmailSendText.test_send_text_no_recipient) ... ok
test_battery_no_battery (test_new_primitives.TestSystemInfo.test_battery_no_battery) ... ok
test_cpu_info (test_new_primitives.TestSystemInfo.test_cpu_info) ... ok
test_disk_info (test_new_primitives.TestSystemInfo.test_disk_info) ... ok
test_memory_info (test_new_primitives.TestSystemInfo.test_memory_info) ... ok
test_system_summary (test_new_primitives.TestSystemInfo.test_system_summary) ... ok
test_uptime_info (test_new_primitives.TestSystemInfo.test_uptime_info) ... ok
test_empty_title_precondition (test_notify.TestNotifySend.test_empty_title_precondition) ... ok
test_missing_binary (test_notify.TestNotifySend.test_missing_binary) ... ok
test_no_body_omits_body_arg (test_notify.TestNotifySend.test_no_body_omits_body_arg) ... ok
test_nonzero_exit (test_notify.TestNotifySend.test_nonzero_exit) ... ok
test_success (test_notify.TestNotifySend.test_success) ... ok
test_timeout (test_notify.TestNotifySend.test_timeout) ... ok
test_timeout_flag_respects_custom_value (test_notify.TestNotifySend.test_timeout_flag_respects_custom_value) ... ok
test_windows_branch_uses_powershell (test_notify.TestNotifySend.test_windows_branch_uses_powershell) ... ok
test_windows_cmd_builder_shape (test_notify.TestNotifySend.test_windows_cmd_builder_shape) ... ok
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
test_emitted_lines_use_reset_run_id (test_observability.TestRunIdLifecycle.test_emitted_lines_use_reset_run_id) ... ok
test_reset_restores_process_default (test_observability.TestRunIdLifecycle.test_reset_restores_process_default) ... ok
test_set_run_id_none_generates_fresh (test_observability.TestRunIdLifecycle.test_set_run_id_none_generates_fresh) ... ok
test_all_registered_primitives_in_catalog (test_planner.TestCatalog.test_all_registered_primitives_in_catalog)
REGRESSION guard: every contract-registered primitive must be ... ok
test_calendar_and_screenshot_are_planable (test_planner.TestCatalog.test_calendar_and_screenshot_are_planable)
REGRESSION test for calendar and screenshot modules. ... ok
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
test_registered_in_registry (test_screenshot.TestContract.test_registered_in_registry) ... ok
test_default_path_when_omitted (test_screenshot.TestFullCapture.test_default_path_when_omitted) ... ok
test_full_uses_literal_grim_argv (test_screenshot.TestFullCapture.test_full_uses_literal_grim_argv) ... ok
test_grim_failure_raises (test_screenshot.TestFullCapture.test_grim_failure_raises) ... ok
test_grim_timeout_raises_primitive_timeout (test_screenshot.TestFullCapture.test_grim_timeout_raises_primitive_timeout) ... ok
test_missing_output_dir_rejected (test_screenshot.TestFullCapture.test_missing_output_dir_rejected) ... ok
test_relative_output_path_rejected (test_screenshot.TestFullCapture.test_relative_output_path_rejected) ... ok
test_capture_shape_requires_timeout (test_screenshot.TestGateCaptureShape.test_capture_shape_requires_timeout) ... ok
test_literal_tool_with_runtime_args_allowed (test_screenshot.TestGateCaptureShape.test_literal_tool_with_runtime_args_allowed) ... ok
test_non_allowlisted_tool_rejected (test_screenshot.TestGateCaptureShape.test_non_allowlisted_tool_rejected)
bash/python/rm with runtime args is the shell-escape the gate ... ok
test_variable_first_element_rejected (test_screenshot.TestGateCaptureShape.test_variable_first_element_rejected) ... ok
test_active_window_phrasing_maps_to_active (test_screenshot.TestWindowCapture.test_active_window_phrasing_maps_to_active)
The LLM says 'active window' (the goal phrasing) - the impl must ... ok
test_missing_selector_raises_precondition (test_screenshot.TestWindowCapture.test_missing_selector_raises_precondition) ... ok
test_no_active_window_raises_precondition (test_screenshot.TestWindowCapture.test_no_active_window_raises_precondition) ... ok
test_selector_passes_geometry (test_screenshot.TestWindowCapture.test_selector_passes_geometry) ... ok
test_env_json_override_wins_over_pass (test_secrets.TestSecrets.test_env_json_override_wins_over_pass) ... ok
test_env_malformed_json_falls_back_to_pass (test_secrets.TestSecrets.test_env_malformed_json_falls_back_to_pass) ... ok
test_env_partial_pair_falls_back_to_pass (test_secrets.TestSecrets.test_env_partial_pair_falls_back_to_pass)
Only one of USERNAME/PASSWORD set is a misconfiguration - must ... ok
test_env_username_password_pair (test_secrets.TestSecrets.test_env_username_password_pair) ... ok
test_json_entry (test_secrets.TestSecrets.test_json_entry) ... ok
test_missing_binary (test_secrets.TestSecrets.test_missing_binary) ... ok
test_no_env_no_pass_error_names_the_override (test_secrets.TestSecrets.test_no_env_no_pass_error_names_the_override) ... ok
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
test_heartbeat_reports_pending_separately_from_total (test_watcher.TestHeartbeat.test_heartbeat_reports_pending_separately_from_total)
capability_gaps is the TOTAL ever recorded; gaps_pending_triage ... ok
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
test_download_pending_media_full_flow (test_watcher.TestWhatsAppMediaTrigger.test_download_pending_media_full_flow)
_download_pending_media downloads all pending items and clears ... ok
test_has_pending_media_false_when_empty (test_watcher.TestWhatsAppMediaTrigger.test_has_pending_media_false_when_empty)
_has_pending_media returns False when queue is empty or missing. ... ok
test_has_pending_media_true (test_watcher.TestWhatsAppMediaTrigger.test_has_pending_media_true)
_has_pending_media returns True when there are items in the queue. ... ok
test_run_whatsapp_media_trigger_completes (test_watcher.TestWhatsAppMediaTrigger.test_run_whatsapp_media_trigger_completes)
The whatsapp-media trigger handler runs and records properly. ... ok
test_run_whatsapp_media_trigger_empty_queue (test_watcher.TestWhatsAppMediaTrigger.test_run_whatsapp_media_trigger_empty_queue)
When queue is empty, trigger completes with 0 downloads. ... ok
test_whatsapp_media_trigger_due_check (test_watcher.TestWhatsAppMediaTrigger.test_whatsapp_media_trigger_due_check)
The whatsapp-media trigger is due when there are pending items ... ok
test_whatsapp_media_trigger_end_to_end (test_watcher.TestWhatsAppMediaTrigger.test_whatsapp_media_trigger_end_to_end)
Full watcher run with a whatsapp-media trigger: enqueue -> ... ok
test_whatsapp_media_trigger_loads (test_watcher.TestWhatsAppMediaTrigger.test_whatsapp_media_trigger_loads)
A whatsapp-media trigger must pass config validation. ... ok
test_audio_message (test_webhook_server.TestExtractMediaMessages.test_audio_message) ... ok
test_document_message (test_webhook_server.TestExtractMediaMessages.test_document_message) ... ok
test_empty_payload (test_webhook_server.TestExtractMediaMessages.test_empty_payload) ... ok
test_image_message (test_webhook_server.TestExtractMediaMessages.test_image_message) ... ok
test_media_id_missing_skipped (test_webhook_server.TestExtractMediaMessages.test_media_id_missing_skipped) ... ok
test_multiple_media_messages (test_webhook_server.TestExtractMediaMessages.test_multiple_media_messages) ... ok
test_no_messages_in_payload (test_webhook_server.TestExtractMediaMessages.test_no_messages_in_payload) ... ok
test_sticker_message (test_webhook_server.TestExtractMediaMessages.test_sticker_message) ... ok
test_text_message_skipped (test_webhook_server.TestExtractMediaMessages.test_text_message_skipped) ... ok
test_video_message (test_webhook_server.TestExtractMediaMessages.test_video_message) ... ok
test_empty_payload (test_webhook_server.TestVerifySignature.test_empty_payload) ... ok
test_invalid_signature (test_webhook_server.TestVerifySignature.test_invalid_signature) ... ok
test_no_secret_allows_all (test_webhook_server.TestVerifySignature.test_no_secret_allows_all)
When no app_secret is configured, all signatures pass. ... ok
test_valid_signature (test_webhook_server.TestVerifySignature.test_valid_signature) ... ok
test_valid_signature_without_prefix (test_webhook_server.TestVerifySignature.test_valid_signature_without_prefix) ... ok
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
test_close_window_uses_postmessage_on_windows (test_window.TestWin32Backend.test_close_window_uses_postmessage_on_windows) ... ok
test_focus_window_no_match_raises (test_window.TestWin32Backend.test_focus_window_no_match_raises) ... ok
test_focus_window_uses_setforeground_on_windows (test_window.TestWin32Backend.test_focus_window_uses_setforeground_on_windows) ... ok
test_list_clients_dispatches_to_win32 (test_window.TestWin32Backend.test_list_clients_dispatches_to_win32) ... ok
test_move_to_workspace_stub_on_windows (test_window.TestWin32Backend.test_move_to_workspace_stub_on_windows) ... ok
test_open_app_launches_via_popen_on_windows (test_window.TestWin32Backend.test_open_app_launches_via_popen_on_windows) ... ok
test_shutdown_is_noop_on_windows (test_window.TestWin32Backend.test_shutdown_is_noop_on_windows) ... ok
test_win_clients_shape (test_window.TestWin32Backend.test_win_clients_shape) ... ok
test_win_enum_failure_degrades_to_empty (test_window.TestWin32Backend.test_win_enum_failure_degrades_to_empty) ... ok

----------------------------------------------------------------------
Ran 1037 tests in 89.694s

OK
```

