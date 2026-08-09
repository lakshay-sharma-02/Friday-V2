========================================================================
GATE 3 / L2 VERIFICATION
========================================================================

[1] import discipline (L2 imports read-only accessors only)
  violations: 0
  DISCIPLINE: OK

[2] window: open_app -> count goes UP -> close -> count returns DOWN
  count before: 3
  window_has_class('firefox') before: False
  opened: 0x561050b74d40 (class=firefox)
  count after open: 4  (delta +1)
  window_has_class('firefox') after open: True
  count after close: 3  (delta 0)
  window_has_class('firefox') after close: False
  WINDOW CHECK: PASS

[3] media: play_for(1) -> media_playing True -> stop -> False
  media_playing() after start: True
  media_playing() after stop: False
  MEDIA CHECK: PASS

[4] browser: goto -> browser_has_text True -> close -> False
  browser_has_text('Example Domain') after goto: True
  browser_has_text('Example Domain') after close: False
  BROWSER CHECK: PASS

[5] file check (pure, no side effects)
  file_exists(README): True
  file_exists(/nonexistent): False

[6] whatsapp identity (read-only API check)
  whatsapp_identity_ok: True

=== raw L2 log lines (layer=L2) from this run ===
{"run_id": "23124ba9fa44", "step_id": null, "layer": "L2", "primitive": "checks.window_client_count", "args": {}, "result": 3, "exception": null, "duration_ms": 9.785, "timestamp": "2026-08-07T14:10:00.794+00:00"}
{"run_id": "23124ba9fa44", "step_id": null, "layer": "L2", "primitive": "checks.window_has_class", "args": {"cls": "firefox"}, "result": false, "exception": null, "duration_ms": 11.359, "timestamp": "2026-08-07T14:10:00.805+00:00"}
{"run_id": "23124ba9fa44", "step_id": null, "layer": "L2", "primitive": "checks.window_client_count", "args": {}, "result": 4, "exception": null, "duration_ms": 32.215, "timestamp": "2026-08-07T14:10:06.225+00:00"}
{"run_id": "23124ba9fa44", "step_id": null, "layer": "L2", "primitive": "checks.window_has_class", "args": {"cls": "firefox"}, "result": true, "exception": null, "duration_ms": 57.395, "timestamp": "2026-08-07T14:10:06.284+00:00"}
{"run_id": "23124ba9fa44", "step_id": null, "layer": "L2", "primitive": "checks.window_client_count", "args": {}, "result": 3, "exception": null, "duration_ms": 66.636, "timestamp": "2026-08-07T14:10:06.774+00:00"}
{"run_id": "23124ba9fa44", "step_id": null, "layer": "L2", "primitive": "checks.window_has_class", "args": {"cls": "firefox"}, "result": false, "exception": null, "duration_ms": 208.299, "timestamp": "2026-08-07T14:10:06.988+00:00"}
{"run_id": "23124ba9fa44", "step_id": null, "layer": "L2", "primitive": "checks.window_has_class", "args": {"cls": "firefox"}, "result": false, "exception": null, "duration_ms": 61.85, "timestamp": "2026-08-07T14:10:07.054+00:00"}
{"run_id": "23124ba9fa44", "step_id": null, "layer": "L2", "primitive": "checks.media_playing", "args": {}, "result": false, "exception": null, "duration_ms": 62.318, "timestamp": "2026-08-07T14:10:09.101+00:00"}
{"run_id": "23124ba9fa44", "step_id": null, "layer": "L2", "primitive": "checks.media_playing", "args": {}, "result": true, "exception": null, "duration_ms": 6.311, "timestamp": "2026-08-07T14:10:09.611+00:00"}
{"run_id": "23124ba9fa44", "step_id": null, "layer": "L2", "primitive": "checks.media_playing", "args": {}, "result": false, "exception": null, "duration_ms": 1.95, "timestamp": "2026-08-07T14:10:10.904+00:00"}
{"run_id": "23124ba9fa44", "step_id": null, "layer": "L2", "primitive": "checks.browser_has_text", "args": {"substring": "Example Domain"}, "result": true, "exception": null, "duration_ms": 153.297, "timestamp": "2026-08-07T14:10:17.791+00:00"}
{"run_id": "23124ba9fa44", "step_id": null, "layer": "L2", "primitive": "checks.browser_has_text", "args": {"substring": "Example Domain"}, "result": false, "exception": null, "duration_ms": 0.851, "timestamp": "2026-08-07T14:10:18.476+00:00"}
{"run_id": "23124ba9fa44", "step_id": null, "layer": "L2", "primitive": "checks.file_exists", "args": {"path": "/home/lakshay/Projects/Friday V2/README.md"}, "result": true, "exception": null, "duration_ms": 0.777, "timestamp": "2026-08-07T14:10:18.477+00:00"}
{"run_id": "23124ba9fa44", "step_id": null, "layer": "L2", "primitive": "checks.file_exists", "args": {"path": "/nonexistent/nope"}, "result": false, "exception": null, "duration_ms": 0.308, "timestamp": "2026-08-07T14:10:18.478+00:00"}
{"run_id": "23124ba9fa44", "step_id": null, "layer": "L2", "primitive": "checks.whatsapp_identity_ok", "args": {}, "result": true, "exception": null, "duration_ms": 714.226, "timestamp": "2026-08-07T14:10:19.192+00:00"}
{"run_id": "19ef8d7050c7", "step_id": null, "layer": "L2", "primitive": "checks.window_client_count", "args": {}, "result": 3, "exception": null, "duration_ms": 10.809, "timestamp": "2026-08-07T14:13:16.904+00:00"}
{"run_id": "19ef8d7050c7", "step_id": null, "layer": "L2", "primitive": "checks.window_has_class", "args": {"cls": "firefox"}, "result": false, "exception": null, "duration_ms": 11.935, "timestamp": "2026-08-07T14:13:16.916+00:00"}
{"run_id": "19ef8d7050c7", "step_id": null, "layer": "L2", "primitive": "checks.window_client_count", "args": {}, "result": 4, "exception": null, "duration_ms": 36.944, "timestamp": "2026-08-07T14:13:22.073+00:00"}
{"run_id": "19ef8d7050c7", "step_id": null, "layer": "L2", "primitive": "checks.window_has_class", "args": {"cls": "firefox"}, "result": true, "exception": null, "duration_ms": 32.617, "timestamp": "2026-08-07T14:13:22.106+00:00"}
{"run_id": "19ef8d7050c7", "step_id": null, "layer": "L2", "primitive": "checks.window_client_count", "args": {}, "result": 3, "exception": null, "duration_ms": 29.598, "timestamp": "2026-08-07T14:13:22.488+00:00"}
{"run_id": "19ef8d7050c7", "step_id": null, "layer": "L2", "primitive": "checks.window_has_class", "args": {"cls": "firefox"}, "result": false, "exception": null, "duration_ms": 50.049, "timestamp": "2026-08-07T14:13:22.539+00:00"}
{"run_id": "19ef8d7050c7", "step_id": null, "layer": "L2", "primitive": "checks.media_playing", "args": {}, "result": true, "exception": null, "duration_ms": 22.54, "timestamp": "2026-08-07T14:13:24.856+00:00"}
{"run_id": "19ef8d7050c7", "step_id": null, "layer": "L2", "primitive": "checks.media_playing", "args": {}, "result": false, "exception": null, "duration_ms": 0.615, "timestamp": "2026-08-07T14:13:26.155+00:00"}
{"run_id": "19ef8d7050c7", "step_id": null, "layer": "L2", "primitive": "checks.browser_has_text", "args": {"substring": "Example Domain"}, "result": true, "exception": null, "duration_ms": 446.939, "timestamp": "2026-08-07T14:13:31.732+00:00"}
{"run_id": "19ef8d7050c7", "step_id": null, "layer": "L2", "primitive": "checks.browser_has_text", "args": {"substring": "Example Domain"}, "result": false, "exception": null, "duration_ms": 0.535, "timestamp": "2026-08-07T14:13:32.721+00:00"}
{"run_id": "19ef8d7050c7", "step_id": null, "layer": "L2", "primitive": "checks.file_exists", "args": {"path": "/home/lakshay/Projects/Friday V2/README.md"}, "result": true, "exception": null, "duration_ms": 0.425, "timestamp": "2026-08-07T14:13:32.722+00:00"}
{"run_id": "19ef8d7050c7", "step_id": null, "layer": "L2", "primitive": "checks.file_exists", "args": {"path": "/nonexistent/nope"}, "result": false, "exception": null, "duration_ms": 0.202, "timestamp": "2026-08-07T14:13:32.723+00:00"}
{"run_id": "19ef8d7050c7", "step_id": null, "layer": "L2", "primitive": "checks.whatsapp_identity_ok", "args": {}, "result": true, "exception": null, "duration_ms": 612.487, "timestamp": "2026-08-07T14:13:33.335+00:00"}
{"run_id": "efe5ffd4797e", "step_id": null, "layer": "L2", "primitive": "checks.window_client_count", "args": {}, "result": 3, "exception": null, "duration_ms": 14.509, "timestamp": "2026-08-07T14:20:05.226+00:00"}
{"run_id": "efe5ffd4797e", "step_id": null, "layer": "L2", "primitive": "checks.window_has_class", "args": {"cls": "firefox"}, "result": false, "exception": null, "duration_ms": 13.318, "timestamp": "2026-08-07T14:20:05.240+00:00"}
{"run_id": "efe5ffd4797e", "step_id": null, "layer": "L2", "primitive": "checks.window_client_count", "args": {}, "result": 4, "exception": null, "duration_ms": 40.285, "timestamp": "2026-08-07T14:20:10.330+00:00"}
{"run_id": "efe5ffd4797e", "step_id": null, "layer": "L2", "primitive": "checks.window_has_class", "args": {"cls": "firefox"}, "result": true, "exception": null, "duration_ms": 16.083, "timestamp": "2026-08-07T14:20:10.347+00:00"}
{"run_id": "efe5ffd4797e", "step_id": null, "layer": "L2", "primitive": "checks.window_client_count", "args": {}, "result": 3, "exception": null, "duration_ms": 16.75, "timestamp": "2026-08-07T14:20:10.698+00:00"}
{"run_id": "efe5ffd4797e", "step_id": null, "layer": "L2", "primitive": "checks.window_has_class", "args": {"cls": "firefox"}, "result": false, "exception": null, "duration_ms": 39.794, "timestamp": "2026-08-07T14:20:10.739+00:00"}
{"run_id": "efe5ffd4797e", "step_id": null, "layer": "L2", "primitive": "checks.media_playing", "args": {}, "result": true, "exception": null, "duration_ms": 44.323, "timestamp": "2026-08-07T14:20:12.466+00:00"}
{"run_id": "efe5ffd4797e", "step_id": null, "layer": "L2", "primitive": "checks.media_playing", "args": {}, "result": false, "exception": null, "duration_ms": 2.098, "timestamp": "2026-08-07T14:20:13.423+00:00"}
{"run_id": "efe5ffd4797e", "step_id": null, "layer": "L2", "primitive": "checks.browser_has_text", "args": {"substring": "Example Domain"}, "result": true, "exception": null, "duration_ms": 45.502, "timestamp": "2026-08-07T14:20:18.527+00:00"}
{"run_id": "efe5ffd4797e", "step_id": null, "layer": "L2", "primitive": "checks.browser_has_text", "args": {"substring": "Example Domain"}, "result": false, "exception": null, "duration_ms": 1.031, "timestamp": "2026-08-07T14:20:19.826+00:00"}
{"run_id": "efe5ffd4797e", "step_id": null, "layer": "L2", "primitive": "checks.file_exists", "args": {"path": "/home/lakshay/Projects/Friday V2/README.md"}, "result": true, "exception": null, "duration_ms": 0.188, "timestamp": "2026-08-07T14:20:19.827+00:00"}
{"run_id": "efe5ffd4797e", "step_id": null, "layer": "L2", "primitive": "checks.file_exists", "args": {"path": "/nonexistent/nope"}, "result": false, "exception": null, "duration_ms": 0.311, "timestamp": "2026-08-07T14:20:19.827+00:00"}
{"run_id": "efe5ffd4797e", "step_id": null, "layer": "L2", "primitive": "checks.whatsapp_identity_ok", "args": {}, "result": true, "exception": null, "duration_ms": 611.831, "timestamp": "2026-08-07T14:20:20.440+00:00"}

GATE 3: DONE
