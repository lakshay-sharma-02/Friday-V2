# Hand-corrected after human review (2026-08-14): the LLM draft returned a
# dict {path, name, mtime, matches}, but the two gate-registered files.*
# READ primitives (find_file_exact, find_recent_doc) return a str path -
# the convention the read-family build-verify probe enforces, and the
# shape the download-alert trigger plan can feed straight into
# whatsapp.send_document ($steps.N.result).
from friday.contracts import Idempotency, contract
from friday.errors import PreconditionError
import os
from pathlib import Path


@contract(
    precondition="name is a non-empty string (the file pattern to match, e.g. 'pdf' or 'receipt'); directory is a non-empty string (the directory to search).",
    postcondition="Returns the absolute path of the most recently modified file whose name contains the pattern (case-insensitive); directories are never matched. Read-only - nothing is created, read or modified.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PreconditionError when name or directory is empty or the directory does not exist; returns '' when no matching file exists (an absent file is a result, never an exception - same convention as find_file_exact).",
    returns="str: absolute path of the newest matching file, or '' when none exists.",
)
def find_newest(name: str, directory: str) -> str:
    """Find the newest file matching a pattern in a directory.

    Searches for files in `directory` whose names contain `name`
    (case-insensitive) and returns the most recently modified one
    (by mtime). Useful for "send the newest pdf to whatsapp" goals where
    the exact filename is unknown. Returns '' when no match exists -
    an absent file is a result, never an exception.
    """
    if not name or not name.strip():
        raise PreconditionError("find_newest requires a non-empty 'name'")
    if not directory or not directory.strip():
        raise PreconditionError("find_newest requires a non-empty 'directory'")
    base = Path(directory).expanduser()
    if not base.is_dir():
        raise PreconditionError(f"find_newest: directory does not exist: {base}")
    needle = name.strip().lower()
    best: tuple[float, Path] | None = None
    try:
        entries = list(base.iterdir())
    except OSError as exc:
        raise PreconditionError(f"find_newest: cannot scan {base}: {exc}") from exc
    for p in entries:
        if not p.is_file() or needle not in p.name.lower():
            continue
        try:
            mtime = p.stat().st_mtime
        except OSError:
            continue  # unreadable entry: skip, never crash the scan
        if best is None or mtime > best[0]:
            best = (mtime, p)
    return str(best[1]) if best is not None else ""
