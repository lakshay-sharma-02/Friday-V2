# TESTS_PROOF — automated test suite for Friday

Status date: 2026-08-10T03:53:24+00:00.

The full unittest suite over every layer and feature: registry,
observability (redaction / rotation / log_transform), the executor
(ref resolver, retry policy, blocked primitives), the planner
(validate_plan / catalog / facts), L2 checks, window protected-
classes, the dev dangerous-gate, gmail/notify/secrets, and the
watch loop. All side-effect boundaries are mocked - the suite
never sends, launches, clicks or touches the compositor.

## Verdict: PASS

Ran 214 tests: 214 passed, 0 failed, 0 errors.

## Raw output

```
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
test_message_sent_discord (test_checks.TestPureChecks.test_message_sent_discord) ... ok
test_message_sent_telegram (test_checks.TestPureChecks.test_message_sent_telegram) ... ok
test_message_sent_unknown_platform (test_checks.TestPureChecks.test_message_sent_unknown_platform) ... ok
test_message_sent_whatsapp (test_checks.TestPureChecks.test_message_sent_whatsapp) ... ok
test_window_client_count (test_checks.TestWindowChecks.test_window_client_count) ... ok
test_window_has_class_substring (test_checks.TestWindowChecks.test_window_has_class_substring) ... ok
test_window_on_workspace (test_checks.TestWindowChecks.test_window_on_workspace) ... ok
test_window_only_classes (test_checks.TestWindowChecks.test_window_only_classes) ... ok
test_window_only_classes_vacuous_on_empty (test_checks.TestWindowChecks.test_window_only_classes_vacuous_on_empty) ... ok
test_plain_run_ungated (test_dev.TestDevGate.test_plain_run_ungated) ... ok
test_run_bypass_refuses_without_flag (test_dev.TestDevGate.test_run_bypass_refuses_without_flag) ... ok
test_run_shell_allowed_with_flag (test_dev.TestDevGate.test_run_shell_allowed_with_flag) ... ok
test_run_shell_bad_envelope_raises (test_dev.TestDevGate.test_run_shell_bad_envelope_raises) ... ok
test_run_shell_bypass_flag_reaches_claude (test_dev.TestDevGate.test_run_shell_bypass_flag_reaches_claude) ... ok
test_run_shell_refuses_without_flag (test_dev.TestDevGate.test_run_shell_refuses_without_flag) ... ok
test_run_shell_rejects_empty_command (test_dev.TestDevGate.test_run_shell_rejects_empty_command) ... ok
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
test_verify_failure_exhausts_attempts (test_executor.TestRunPlan.test_verify_failure_exhausts_attempts) ... ok
test_zero_verify_wait_rejected_before_execution (test_executor.TestRunPlan.test_zero_verify_wait_rejected_before_execution) ... ok
test_garbage_base64_returns_empty (test_gmail.TestBodyText.test_garbage_base64_returns_empty) ... ok
test_multipart_prefers_text_plain (test_gmail.TestBodyText.test_multipart_prefers_text_plain) ... ok
test_no_body_returns_empty (test_gmail.TestBodyText.test_no_body_returns_empty) ... ok
test_single_part_body_decoded (test_gmail.TestBodyText.test_single_part_body_decoded) ... ok
test_case_insensitive (test_gmail.TestHeader.test_case_insensitive) ... ok
test_missing_returns_empty (test_gmail.TestHeader.test_missing_returns_empty) ... ok
test_non_list_passthrough (test_gmail.TestLogRedactMailMeta.test_non_list_passthrough) ... ok
test_original_not_mutated (test_gmail.TestLogRedactMailMeta.test_original_not_mutated) ... ok
test_redacts_sender_and_subject_keeps_ids (test_gmail.TestLogRedactMailMeta.test_redacts_sender_and_subject_keeps_ids) ... ok
test_empty_llm_summary_raises (test_gmail.TestSummarizeFlow.test_empty_llm_summary_raises) ... ok
test_message_without_body_or_snippet_raises (test_gmail.TestSummarizeFlow.test_message_without_body_or_snippet_raises) ... ok
test_summary_body_never_reaches_l0_log (test_gmail.TestSummarizeFlow.test_summary_body_never_reaches_l0_log)
Regression: the mail body is passed to the LLM subprocess, but ... ok
test_summary_from_dict_result (test_gmail.TestSummarizeFlow.test_summary_from_dict_result) ... ok
test_summary_from_string_result (test_gmail.TestSummarizeFlow.test_summary_from_string_result) ... ok
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
test_bad_at (test_watcher.TestConfigValidation.test_bad_at) ... ok
test_bad_json (test_watcher.TestConfigValidation.test_bad_json) ... ok
test_bad_schedule_type (test_watcher.TestConfigValidation.test_bad_schedule_type) ... ok
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
test_failed_goal_is_replanned_next_firing (test_watcher.TestPlanCaching.test_failed_goal_is_replanned_next_firing) ... ok
test_inline_plan_never_calls_llm (test_watcher.TestPlanCaching.test_inline_plan_never_calls_llm) ... ok
test_make_plan_caches_goal_across_firings (test_watcher.TestPlanCaching.test_make_plan_caches_goal_across_firings) ... ok
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
Ran 214 tests in 2.679s

OK
```

