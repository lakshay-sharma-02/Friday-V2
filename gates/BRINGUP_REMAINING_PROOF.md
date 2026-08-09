# Bring-up: remaining L1 primitives (media pause/resume, browser upload, window focus/move/close_all)

Proves the last unproven L1 primitives standalone (hand-invoked, no executor, no LLM),
per the V8 plan's rule that a primitive which cannot be proven standalone is never
called by the executor. Unattended run: the user's open windows were the protected
control group - every pre-existing client had to survive, and focus was restored.

Sections:
  A. media.pause / media.resume  - audio only, zero window interaction
  B. browser.upload_file         - throwaway local page + test file
  C. window.focus_window, window.move_to_workspace, window.close_all
                                   - ONLY against a firefox test window opened by the
                                     script; close_all ran with every pre-existing
                                     class excluded (brave-browser, chromium-browser,
                                     kitty) so the only closable client was the test
                                     window. window.shutdown is never called.
                                     Safety: a TOCTOU guard re-checks that no new
                                     client appeared since the snapshot before
                                     close_all runs; focus is restored in a finally.

Run:  ./.venv/bin/python -u gates/bringup_remaining.py

Raw output (shipped script, run 'bringup-remaining-b'):

========================================================================
BRING-UP (remaining L1 primitives): media pause/resume, browser upload,
window focus/move/close_all - unattended, user windows protected
========================================================================

========================================================================
SECTION A - media.pause / media.resume (audio only)
========================================================================

[a1] media.play_for(0.1, test_tone) -> {'pid': 83772, 'socket': '/tmp/friday_mpv.sock', 'length_s': 6, 'source': '/home/lakshay/Projects/Friday V2/assets/test_tone.mp3'}
[a2] media.is_playing() -> True  (expect True)
[a3] media.pause() -> None
[a4] media.is_playing() -> False  (expect False - paused)
[a5] media.resume() -> None
[a6] media.is_playing() -> True  (expect True - resumed)
[a7] media.stop() -> None
[a8] media.is_playing() -> False  (expect False - stopped)

--- SECTION A DoD ---
  OK: play -> True; pause -> False; resume -> True; stop -> False

========================================================================
SECTION B - browser.upload_file (throwaway local page)
========================================================================

[b1] browser.goto(http://127.0.0.1:36541/index.html) -> {'url': 'http://127.0.0.1:36541/index.html', 'title': ''}
[b2] browser.upload_file(what=None, path=friday_upload_test.txt) -> {'path': '/home/lakshay/Projects/Friday V2/var/logs/upload_tmp/friday_upload_test.txt', 'input_count': 1}
[b3] page text after upload:
     | friday upload test
     | selected: friday_upload_test.txt
[b4] checks.browser_has_text('selected: friday_upload_test.txt') -> True  (expect True)

--- SECTION B DoD ---
  OK: upload_file attached the file and the page state shows it (L2-confirmed)

========================================================================
SECTION C - window focus_window / move_to_workspace / close_all (test window only)
========================================================================

[c0] pre-existing clients (4):
     - class='kitty' addr=0x55c72bbec680 ws=3
     - class='kitty' addr=0x55c72c9db420 ws=1
     - class='brave-browser' addr=0x55c72c1d08c0 ws=2
     - class='chromium-browser' addr=0x55c72c9ff280 ws=1
[c0] originally-active address: 0x55c72c9ff280
[c0] classes to exclude from close_all: ['brave-browser', 'chromium-browser', 'kitty']

[c1] window.open_app('firefox') -> {'address': '0x55c72ca1b6c0', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsInput': True, 'at': [684, 404], 'size': [681, 363], 'workspace': {'id': 1, 'name': '1'}, 'floating': False, 'monitor': 0, 'class': 'firefox', 'title': 'Mozilla Firefox', 'initialClass': 'firefox', 'initialTitle': 'Mozilla Firefox', 'pid': 84097, 'xwayland': False, 'pinned': False, 'pinFullscreened': False, 'fullscreen': 0, 'fullscreenClient': 0, 'fullscreenHandler': 'default', 'allowedOverFullscreen': True, 'grouped': [], 'tags': [], 'swallowing': '0x0', 'focusHistoryID': 0, 'inhibitingIdle': False, 'xdgTag': '', 'xdgDescription': '', 'contentType': 'none', 'tearingHint': False, 'stableId': '18000013'}
[c2] test window address: 0x55c72ca1b6c0

[c3] window.focus_window(test window) -> None
[c4] get_active_window().address -> 0x55c72ca1b6c0  (expect 0x55c72ca1b6c0)

[c5] window.move_to_workspace(9, test window) -> None
[c6] test window workspace.id -> 9  (expect 9)

[c7] window.move_to_workspace(1, test window) -> None

[c8] window.close_all(exclude_classes={...}) -> 1 closed
[c9] pre-existing clients still present: 4/4
[c9] test window closed: True
  [cleanup] focus restored to 0x55c72c9ff280

--- SECTION C DoD ---
  OK: focused test window, moved it ws9 and back, close_all closed ONLY it;
      every pre-existing window survived; focus restored

=== L0 trace: bring-up bringup-remaining-b (61 lines, run_id=bringup-remaining-b) ===
[2026-08-08T06:35:54.976+00:00] L1 step=None media.play_for               -> {'pid': 83772, 'socket': '/tmp/friday_mpv.sock', 'length_s': 6, 'source': '/home/lakshay/P
[2026-08-08T06:35:55.481+00:00] L1 step=None media.is_playing             -> True
[2026-08-08T06:35:55.483+00:00] L1 step=None media.is_playing             -> True
[2026-08-08T06:35:55.485+00:00] L1 step=None media.pause                  -> None
[2026-08-08T06:35:55.987+00:00] L1 step=None media.is_playing             -> False
[2026-08-08T06:35:55.989+00:00] L1 step=None media.is_playing             -> False
[2026-08-08T06:35:55.991+00:00] L1 step=None media.resume                 -> None
[2026-08-08T06:35:56.493+00:00] L1 step=None media.is_playing             -> True
[2026-08-08T06:35:56.495+00:00] L1 step=None media.is_playing             -> True
[2026-08-08T06:35:56.611+00:00] L1 step=None media.stop                   -> None
[2026-08-08T06:35:57.112+00:00] L1 step=None media.is_playing             -> False
[2026-08-08T06:35:57.113+00:00] L1 step=None media.is_playing             -> False
[2026-08-08T06:36:02.149+00:00] L1 step=None browser.goto                 -> {'url': 'http://127.0.0.1:36541/index.html', 'title': ''}
[2026-08-08T06:36:03.400+00:00] L1 step=None browser.upload_file          -> {'path': '/home/lakshay/Projects/Friday V2/var/logs/upload_tmp/friday_upload_test.txt', 'i
[2026-08-08T06:36:03.940+00:00] L1 step=None browser.read_page_text       -> friday upload test
selected: friday_upload_test.txt
[2026-08-08T06:36:03.947+00:00] L1 step=None browser.read_page_text       -> friday upload test
selected: friday_upload_test.txt
[2026-08-08T06:36:03.947+00:00] L2 step=None checks.browser_has_text      -> True
[2026-08-08T06:36:03.953+00:00] L1 step=None browser.read_page_text       -> friday upload test
selected: friday_upload_test.txt
[2026-08-08T06:36:03.953+00:00] L2 step=None checks.browser_has_text      -> True
[2026-08-08T06:36:04.015+00:00] L1 step=None window.list_clients          -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsI
[2026-08-08T06:36:04.027+00:00] L1 step=None window.get_active_window     -> {'address': '0x55c72c9ff280', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsIn
[2026-08-08T06:36:04.041+00:00] L1 step=None window.list_clients          -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsI
[2026-08-08T06:36:04.100+00:00] L1 step=None window.list_clients          -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsI
[2026-08-08T06:36:04.423+00:00] L1 step=None window.list_clients          -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsI
[2026-08-08T06:36:04.780+00:00] L1 step=None window.list_clients          -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsI
[2026-08-08T06:36:05.138+00:00] L1 step=None window.list_clients          -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsI
[2026-08-08T06:36:05.562+00:00] L1 step=None window.list_clients          -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsI
[2026-08-08T06:36:05.907+00:00] L1 step=None window.list_clients          -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsI
[2026-08-08T06:36:06.286+00:00] L1 step=None window.list_clients          -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsI
[2026-08-08T06:36:06.648+00:00] L1 step=None window.list_clients          -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsI
[2026-08-08T06:36:07.029+00:00] L1 step=None window.list_clients          -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsI
[2026-08-08T06:36:07.392+00:00] L1 step=None window.list_clients          -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsI
[2026-08-08T06:36:07.757+00:00] L1 step=None window.list_clients          -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsI
[2026-08-08T06:36:08.125+00:00] L1 step=None window.list_clients          -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsI
[2026-08-08T06:36:08.489+00:00] L1 step=None window.list_clients          -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsI
[2026-08-08T06:36:08.859+00:00] L1 step=None window.list_clients          -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsI
[2026-08-08T06:36:09.238+00:00] L1 step=None window.list_clients          -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsI
[2026-08-08T06:36:09.585+00:00] L1 step=None window.list_clients          -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsI
[2026-08-08T06:36:10.075+00:00] L1 step=None window.list_clients          -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsI
[2026-08-08T06:36:10.566+00:00] L1 step=None window.list_clients          -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsI
[2026-08-08T06:36:10.593+00:00] L1 step=None window.open_app              -> {'address': '0x55c72ca1b6c0', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsIn
[2026-08-08T06:36:10.782+00:00] L1 step=None window.get_active_window     -> {'address': '0x55c72ca1b6c0', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsIn
[2026-08-08T06:36:10.787+00:00] L1 step=None window.focus_window          -> None
[2026-08-08T06:36:11.460+00:00] L1 step=None window.get_active_window     -> {'address': '0x55c72ca1b6c0', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsIn
[2026-08-08T06:36:11.634+00:00] L1 step=None window.list_clients          -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsI
[2026-08-08T06:36:11.653+00:00] L1 step=None window.move_to_workspace     -> None
[2026-08-08T06:36:12.358+00:00] L1 step=None window.list_clients          -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsI
[2026-08-08T06:36:12.551+00:00] L1 step=None window.list_clients          -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsI
[2026-08-08T06:36:12.556+00:00] L1 step=None window.move_to_workspace     -> None
[2026-08-08T06:36:13.090+00:00] L1 step=None window.list_clients          -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsI
[2026-08-08T06:36:13.128+00:00] L1 step=None window.list_clients          -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsI
[2026-08-08T06:36:13.220+00:00] L1 step=None window.list_clients          -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsI
[2026-08-08T06:36:13.541+00:00] L1 step=None window.list_clients          -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsI
[2026-08-08T06:36:13.547+00:00] L1 step=None window.close_window          -> None
[2026-08-08T06:36:13.548+00:00] L1 step=None window.close_all             -> 1
[2026-08-08T06:36:13.615+00:00] L1 step=None window.list_clients          -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsI
[2026-08-08T06:36:13.648+00:00] L1 step=None window.list_clients          -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsI
[2026-08-08T06:36:13.680+00:00] L1 step=None window.list_clients          -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsI
[2026-08-08T06:36:13.758+00:00] L1 step=None window.get_active_window     -> {'address': '0x55c72c9ff280', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsIn
[2026-08-08T06:36:13.760+00:00] L1 step=None window.focus_window          -> None
[2026-08-08T06:36:16.848+00:00] L1 step=None browser.close                -> None

=== BRING-UP DoD ===
  OK: pause/resume proved; upload_file proved; focus/move/close_all proved
      with every pre-existing window untouched and focus restored

BRING-UP: DONE (media A / upload B / window C)
