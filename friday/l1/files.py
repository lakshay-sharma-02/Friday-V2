"""L1 primitive: files (deterministic filesystem lookup).

A read-only primitive that resolves a *described* file to an absolute path
by name - the missing link for goals like "send the receipt pdf from my
downloads" when the exact filename is not known in advance. It never
reads file contents and never modifies anything; the plan verifies the
result via checks.file_exists on the returned path.

Deterministic by contract: matches are sorted and the first is returned,
so repeated calls agree; a search that finds nothing fails loudly with a
PreconditionError instead of guessing a path. Idempotent, so the executor
may retry it freely (the filesystem is a moving target - a file may
appear between plan and execution).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from friday.contracts import Idempotency, contract
from friday.errors import PreconditionError

# NOTE: this duplicates planner._resolve_path on purpose - the planner
# imports every L1 module, so importing from friday.l4.planner here would
# be a circular import. Keep the anchoring rule identical in both places.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _anchor(raw: str) -> Path:
    """Resolve a directory argument: ~ expands, relative paths anchor at
    the project root (the same rule config/planner_facts.json file_paths
    use), so the search is deterministic regardless of the process cwd."""
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return p


def _scan(base: Path, needle: str, recursive: bool) -> list[Path]:
    """All files under base whose filename contains needle, sorted for
    determinism. Robust by design: os.walk with followlinks=False never
    recurses into symlinked directories (no cycle risk), and directories
    that cannot be read are skipped rather than crashing the walk - if
    nothing readable matches, the caller fails loudly with Precondition
    Error instead of guessing. A scan error on the top-level directory
    itself surfaces as OSError for the caller to convert."""
    if recursive:
        matches = sorted(
            (Path(dirpath) / fn for dirpath, _dirs, files in os.walk(base, followlinks=False)
             for fn in files if needle in fn.lower()),
            key=str,
        )
    else:
        try:
            matches = sorted(
                (p for p in base.iterdir() if p.is_file() and needle in p.name.lower()),
                key=str,
            )
        except OSError as exc:
            raise PreconditionError(f"find_file: cannot scan {base}: {exc}") from exc
    return matches


@contract(
    precondition="name is a non-empty string; directory (if given) exists.",
    postcondition="Returns the absolute path of the first file (sorted) whose "
    "filename contains 'name' as a case-insensitive substring; directories "
    "are never matched. Read-only - nothing is created, read or modified.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PreconditionError naming the directory and search term when "
    "nothing matches or the directory does not exist.",
    returns="dict: {path, name, matches} - path is the chosen file, matches "
    "lists every matching file.",
)
def find_file(name: str, directory: str | None = None, recursive: bool = False) -> dict[str, Any]:
    """Find a file by a case-insensitive substring of its filename.

    `directory` defaults to the user's home; pass a configured folder
    (e.g. \"$facts.downloads\") or an absolute path. `recursive` extends
    the search into subdirectories (off by default - a downloads folder
    is searched one level deep). Returns the lexicographically first
    match so repeated calls are identical; a plan step references its
    result as \"$steps.N.result.path\".
    """
    if not name or not name.strip():
        raise PreconditionError("find_file requires a non-empty 'name'")
    needle = name.strip().lower()
    base = _anchor(directory) if directory else Path.home()
    if not base.is_dir():
        raise PreconditionError(f"find_file: search directory does not exist: {base}")
    matches = _scan(base, needle, recursive)
    if not matches:
        where = f"{base} (recursive)" if recursive else str(base)
        raise PreconditionError(f"find_file: no file in {where} matches {name!r}")
    chosen = matches[0]
    return {
        "path": str(chosen),
        "name": chosen.name,
        "matches": [str(m) for m in matches],
    }
