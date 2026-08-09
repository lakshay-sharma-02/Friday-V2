========================================================================
GATE 1 / PRIMITIVE 1: window (hyprctl IPC)
========================================================================
-- contracts --
  click                  idempotency=at-most-once
      pre : A page is loaded and 'what' resolves through the fallback chain.
      post: The resolved element is clicked; the page may navigate.
      fail: PrimitiveError if nothing resolves or the click times out; a timed-out click may have landed, so verify effects with L2.
  close                  idempotency=commutative-safe
      pre : None.
      post: Browser context closed and playwright stopped; the persistent profile is preserved for the next run.
      fail: Swallows closure errors; nothing left running.
  close_all              idempotency=commutative-safe
      pre : None - an empty desktop is a valid target.
      post: Every client whose class is not in exclude_classes is closed; returns how many were closed.
      fail: PrimitiveError from any individual close; earlier closes are not rolled back (verify with list_clients()).
  close_window           idempotency=commutative-safe
      pre : selector is a client address (0x...) or a hyprctl class/name.
      post: If a client matched the selector it is gone from list_clients() within 5s; closing an already-closed window is a no-op.
      fail: PrimitiveError if hyprctl rejects the selector or the client survives 5s.
  credentials            idempotency=idempotent
      pre : pass is installed and a friday/<service> entry exists (e.g. `pass insert -m friday/gmail` storing JSON {"username", "password"}).
      post: Makes no state changes.
      fail: PrimitiveError if pass is missing, the entry is missing, or the entry is not JSON or two-line user/pass. Never logs the contents.
  find_locator           idempotency=idempotent
      pre : A page is loaded and 'what' is a non-empty query string.
      post: Makes no state changes.
      fail: PrimitiveError if nothing resolves through the whole chain (exact selector -> attribute relaxation -> accessible-name -> visible text).
  focus_window           idempotency=commutative-safe
      pre : selector targets a live client.
      post: The matching client becomes the active (focused) window within 5s.
      fail: PrimitiveError if the selector never becomes active.
  get_active_window      idempotency=idempotent
      pre : Hyprland session is live.
      post: Returns the focused client; makes no state changes.
      fail: PrimitiveError if hyprctl fails.
  goto                   idempotency=idempotent
      pre : url is an http(s):// URL.
      post: The persistent-context page navigates to url (domcontentloaded).
      fail: PrimitiveError on navigation failure (bad URL, offline, timeout); a failed navigation leaves the page on its previous or partial URL.
  is_playing             idempotency=idempotent
      pre : None.
      post: Makes no state changes; reports whether audio is currently playing.
      fail: Never raises: no player -> False.
  list_clients           idempotency=idempotent
      pre : Hyprland session is live.
      post: Returns the current client list; makes no state changes.
      fail: PrimitiveError if hyprctl fails or returns invalid JSON; PrimitiveTimeout if hyprctl hangs.
  login                  idempotency=at-most-once
      pre : Credentials for the service exist in pass and the page is at its login form.
      post: Credentials are filled and the submit control is clicked.
      fail: PrimitiveError from any sub-step; partial fill is possible, so verify the resulting state with L2.
  move_to_workspace      idempotency=commutative-safe
      pre : workspace_id >= 1 and selector targets a live client.
      post: The client's workspace.id becomes workspace_id within 5s.
      fail: PrimitiveError if hyprctl rejects the arguments or the move never lands.
  open_app               idempotency=at-most-once
      pre : command is a non-empty string naming an executable (e.g. 'firefox').
      post: hyprctl dispatch exec ran; within 12s a client matching the command's first token is present (newly appeared, or already running before the call).
      fail: PrimitiveError if no matching client appears within 12s - the app may still have been dispatched, so verify with list_clients(). PreconditionError on empty command.
  pause                  idempotency=commutative-safe
      pre : None.
      post: If a player is running it pauses.
      fail: No-op when no player is running.
  play                   idempotency=at-most-once
      pre : source is a non-empty local path or URL.
      post: Audio from source plays at the given volume until stop() is called.
      fail: PrimitiveError if mpv cannot start or its IPC socket never appears; any pre-existing player is stopped first.
  play_for               idempotency=at-most-once
      pre : minutes > 0 and source is a non-empty local path or URL.
      post: Audio from source plays at the given volume and stops after 'minutes' minutes (mpv --length plus a one-shot safety timer).
      fail: PrimitiveError if mpv cannot start or its IPC socket never appears; any pre-existing player is stopped first (replaced, not stacked).
  press_key              idempotency=at-most-once
      pre : A page is loaded.
      post: The key is pressed on the resolved element, or globally if 'what' is None.
      fail: PrimitiveError if 'what' is given but does not resolve.
  read_page_text         idempotency=idempotent
      pre : A page is loaded.
      post: Makes no state changes.
      fail: PrimitiveError if no page exists (call goto() first) or the context died.
  resume                 idempotency=commutative-safe
      pre : None.
      post: If a paused player is running it resumes.
      fail: No-op when no player is running.
  run                    idempotency=at-most-once
      pre : cwd exists (if given) and task is a non-empty instruction.
      post: Claude Code executes the task and returns its structured response.
      fail: PrimitiveError/PrimitiveTimeout from the subprocess; the task may have had side effects even on failure - verification is the caller's job.
  run_shell              idempotency=at-most-once
      pre : cwd exists and command is a non-empty shell command string.
      post: Claude Code runs the command and reports {exit_code, stdout, stderr}.
      fail: PrimitiveError if claude fails or the result is not the required JSON; the command may have run regardless - verify effects with L2 before retrying.
  set_volume             idempotency=commutative-safe
      pre : 0 <= percent <= 100.
      post: If a player is running, its volume is set to percent.
      fail: PreconditionError on out-of-range volume; no-op (not an error) when no player is running.
  shutdown               idempotency=at-most-once
      pre : You actually want the compositor session to end.
      post: Hyprland exits; the session ends. This is destructive.
      fail: PrimitiveError if hyprctl rejects the exit command.
  stop                   idempotency=commutative-safe
      pre : None - stopping with nothing playing is a harmless no-op.
      post: No mpv process is left bound to SOCKET_PATH and the socket file is gone.
      fail: None expected; stubborn processes are SIGTERM'd by the orphan sweep.
  type_text              idempotency=at-most-once
      pre : A page is loaded, 'what' resolves, and text is a string.
      post: The resolved field contains text (fill preferred; keystrokes as fallback).
      fail: PrimitiveError if the element can neither be filled nor typed into; the field may be partially filled.

[1a] baseline: window.list_clients()
  client count before: 2

[1b] window.open_app('firefox')
  open_app returned client: {"address": "0x561050b7c9d0", "mapped": true, "hidden": false, "visible": true, "acceptsInput": true, "at": [1, 39], "size": [681, 728], "workspace": {"id": 2, "name": "2"}, "floating": false, "monitor": 0, "class": "firefox", "title": "Mozilla Firefox", "initialClass": "firefox", "initialTitle": "Mozilla Firefox", "pid": 200201, "xwayland": false, "pinned": false, "pinFullscreened": false, "fullscreen": 0, "fullscreenClient": 0, "fullscreenHandler": "default", "allowedOverFullscreen": true, "grouped": [], "tags": [], "swallowing": "0x0", "focusHistoryID": 0, "inhibitingIdle": false, "xdgTag": "", "xdgDescription": "", "contentType": "none", "tearingHint": false, "stableId": "1800003f"}

[1c] raw proof: hyprctl clients -j (firefox entry)
[
  {
    "address": "0x561050b7c9d0",
    "mapped": true,
    "hidden": false,
    "visible": true,
    "acceptsInput": true,
    "at": [
      1,
      39
    ],
    "size": [
      681,
      728
    ],
    "workspace": {
      "id": 2,
      "name": "2"
    },
    "floating": false,
    "monitor": 0,
    "class": "firefox",
    "title": "Mozilla Firefox",
    "initialClass": "firefox",
    "initialTitle": "Mozilla Firefox",
    "pid": 200201,
    "xwayland": false,
    "pinned": false,
    "pinFullscreened": false,
    "fullscreen": 0,
    "fullscreenClient": 0,
    "fullscreenHandler": "default",
    "allowedOverFullscreen": true,
    "grouped": [],
    "tags": [],
    "swallowing": "0x0",
    "focusHistoryID": 0,
    "inhibitingIdle": false,
    "xdgTag": "",
    "xdgDescription": "",
    "contentType": "none",
    "tearingHint": false,
    "stableId": "1800003f"
  }
]
  client count after: 3 (delta +1)

[1d] close it again (leave the desktop tidy)
  count after close: 2
  WINDOW: DONE

========================================================================
GATE 1 / PRIMITIVE 2: media (mpv IPC socket)
========================================================================
  test asset: /home/lakshay/Projects/Friday V2/assets/test_tone.mp3 (279547 bytes)

[2a] media.play_for(1, test_tone.mp3)  -> 1 minute
  play_for -> {"pid": 200476, "socket": "/tmp/friday_mpv.sock", "length_s": 60, "source": "/home/lakshay/Projects/Friday V2/assets/test_tone.mp3"}
  raw: socket exists -> True
  raw: pgrep mpv -> 69719 mpv --no-video --volume=50 --force-window=no --keep-open=yes --input-ipc-server=/tmp/friday-mpv.sock /tmp/tmpl_vllln5/tone.wav
200476 mpv --no-terminal --input-ipc-server=/tmp/friday_mpv.sock --volume=70 --length=60 /home/lakshay/Projects/Friday V2/assets/test_tone.mp3

[2b] media.is_playing() right after start (expect True)
  is_playing -> True

  ... sampling playback for 70s (mpv --length=60 must stop it) ...
    t+  5s is_playing -> True
    t+ 10s is_playing -> True
    t+ 15s is_playing -> True
    t+ 20s is_playing -> True
    t+ 25s is_playing -> True
    t+ 30s is_playing -> True
    t+ 35s is_playing -> True
    t+ 40s is_playing -> True
    t+ 45s is_playing -> True
    t+ 50s is_playing -> True
    t+ 55s is_playing -> True
    t+ 60s is_playing -> False
    t+ 65s is_playing -> False
    t+ 70s is_playing -> False

[2c] final: media.is_playing() (expect False)
  is_playing -> False
  raw: pgrep mpv after -> 69719 mpv --no-video --volume=50 --force-window=no --keep-open=yes --input-ipc-server=/tmp/friday-mpv.sock /tmp/tmpl_vllln5/tone.wav
200476 [mpv] <defunct>
  MEDIA: DONE

========================================================================
GATE 1 / PRIMITIVE 3: browser (Playwright persistent context)
========================================================================
  profile: /home/lakshay/Projects/Friday V2/var/browser_profile

[3a] browser.goto('https://example.com')
  goto -> {"url": "https://example.com/", "title": "Example Domain"}

[3b] browser.read_page_text()  (raw, first 400 chars)
  Example Domain |  | This domain is for use in documentation examples without needing permission. Avoid use in operations. |  | Learn more
  BROWSER: DONE

========================================================================
GATE 1 / PRIMITIVE 4: dev (claude -p subprocess)
========================================================================

[4a] dev.run_shell(<project root>, 'echo ok', allow_bypass_permissions=True)
  run_shell -> {
  "exit_code": 0,
  "stdout": "ok",
  "stderr": "",
  "model": "opus",
  "duration_ms": 4103
}
  DEV: DONE

