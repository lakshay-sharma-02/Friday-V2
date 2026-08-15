# Human approval

APPROVED

Reviewed 2026-08-15 after the automated gate passed (AST clean,
registration PASS, sandbox 14/14, build-verify honestly NOT-APPLICABLE
for the screenshot class - human review is the semantic gate here, same
as gmail.send_document). Signed per the user's explicit request
("it should be able to send me screenshots on whatsapp/telegram/discord").

## Review notes

- **Requested feature**: capture the screen (full / active window / a
  window selector) to a PNG path so a send primitive
  (whatsapp/telegram/discord.send_*) can attach it.
- **Hand-built** (not LLM-drafted): the impl reuses the shipped
  window.list_clients / get_active_window for geometry (mirroring
  window.py's class/title matching) and shells out to grim through the
  gate's new CAPTURE subprocess shape (literal allowlisted tool binary +
  runtime args) - the same class of extension as the WRITE shape.
- **Live-verified 2026-08-15**: full (353 KB), active (338 KB) and
  window-selector captures all produced valid PNGs against the real
  Hyprland session.
- **Safety**: read-only (writes one PNG, changes nothing else); only
  grim/slurp/import reachable through the CAPTURE shape; screenshot
  CONTENT never rides an L0 line (only the returned path does); no
  protected-window interaction (capture never modifies).
- **Honest limit**: build-verify is NOT-APPLICABLE for this class (no
  safe real target under the sandbox) - the live verification above is
  the semantic proof, and the hermetic 14-test suite mocks every
  external boundary.
