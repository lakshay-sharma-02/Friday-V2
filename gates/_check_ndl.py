#!/usr/bin/env python
"""Check whether new-download-alert would generate a gap or actually execute."""
import sys
from pathlib import Path

sys.path.insert(0, ".")
from friday.l4.planner import _ensure_registry  # noqa: E402

_ensure_registry()
from friday.contracts import REGISTRY  # noqa: E402

# The goal's likely plan: find newest pdf (files.*) + send via whatsapp.
# Both must exist for zero-gap. What's registered in those modules?
print("=== files.* registered ===")
for n in sorted(x for x in REGISTRY if x.startswith("files.")):
    print("  ", n)
print("=== whatsapp.* registered ===")
for n in sorted(x for x in REGISTRY if x.startswith("whatsapp.")):
    print("  ", n)

# Would firing actually send? Check Downloads for pdfs.
d = Path.home() / "Downloads"
pdfs = sorted(d.glob("*.pdf")) if d.is_dir() else []
print(f"\n=== ~/Downloads pdfs: {len(pdfs)} ===")
for p in pdfs[-5:]:
    print("  ", p.name, p.stat().st_mtime)

# Watcher fired-state / file-schedule semantics: does new-download-alert
# have fired state today (would it fire if enabled)?
import json  # noqa: E402

fs = Path("var/state/watcher_fired.json")
if fs.is_file():
    fired = json.loads(fs.read_text())
    print("\n=== fired-state key for new-download-alert ===")
    print("  ", fired.get("new-download-alert", "<absent - has never fired>"))
