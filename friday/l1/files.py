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

import fnmatch
import os
import shutil
from pathlib import Path
from typing import Any

from friday.contracts import Idempotency, contract
from friday.errors import PreconditionError, PrimitiveError

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
            (
                Path(dirpath) / fn
                for dirpath, _dirs, files in os.walk(base, followlinks=False)
                for fn in files
                if needle in fn.lower()
            ),
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


# ---- gate-registered files.find_file_exact (2026-08-10) ----


@contract(
    precondition="name is a non-empty string; directory (if given) exists.",
    postcondition="Returns the absolute path of the first file (sorted) in "
    "directory whose filename EXACTLY equals name (case-insensitive), or '' "
    "when no file matches exactly. Read-only - nothing is created or modified.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="Returns '' when no exact match exists (an absent file is a "
    "result, never an exception); PreconditionError for an empty name or a "
    "missing directory.",
    returns="str: absolute path of the exact match, or '' when none.",
)
def find_file_exact(name: str, directory: str | None = None) -> str:
    """Find the file in `directory` whose filename EXACTLY equals `name`
    (case-insensitive) and return its absolute path, or '' when no exact
    match exists. Contrast find_file, which matches a substring and raises
    when nothing matches - this is the exact-match probe."""
    if not name or not name.strip():
        raise PreconditionError("find_file_exact requires a non-empty 'name'")
    base = _anchor(directory) if directory else PROJECT_ROOT
    if not base.is_dir():
        raise PreconditionError(f"find_file_exact: directory does not exist: {base}")
    needle = name.strip().lower()
    matches = sorted(
        (p for p in base.iterdir() if p.is_file() and p.name.lower() == needle),
        key=str,
    )
    return str(matches[0]) if matches else ""


# ---- Phase C v1: bounded text reader (2026-08-11) ----
@contract(
    precondition="path is a non-empty string resolving to an existing file; "
    "max_chars is a positive integer.",
    postcondition="Returns the file's text content (UTF-8, invalid bytes "
    "replaced) truncated to the first max_chars characters, plus the total "
    "character count and whether it was truncated. Read-only - nothing is "
    "created or modified.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PreconditionError when the path does not exist, is not a "
    "file, or max_chars is not positive; a read error (permission) raises "
    "PreconditionError naming the path.",
    returns="dict: {path, chars, truncated, text}.",
)
def read_text(path: str, max_chars: int = 8000) -> dict[str, Any]:
    """Read the first `max_chars` characters of a file's text content.

    The bounded reader for cross-project digests: a planning-doc or
    changelog can be huge, and the digest prompt must stay small - this
    returns a truncated preview with a `truncated` flag so a plan can
    verify (checks.text_nonempty on the result) without ever loading the
    whole file into an LLM prompt. ~ expands; relative paths anchor at
    the project root (same rule as find_file)."""
    if not path or not path.strip():
        raise PreconditionError("read_text requires a non-empty 'path'")
    if max_chars < 1:
        raise PreconditionError("read_text requires max_chars >= 1")
    p = _anchor(path)  # same ~/relative anchoring rule as find_file
    if not p.is_file():
        raise PreconditionError(f"read_text: no such file: {p}")
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise PreconditionError(f"read_text: cannot read {p}: {exc}") from exc
    truncated = len(text) > max_chars
    return {
        "path": str(p),
        "chars": len(text),
        "truncated": truncated,
        "text": text[:max_chars],
    }


# ---- Phase C v2.2: recency-based status-doc discovery (2026-08-11) ----
# Status/planning-shaped filenames, matched case-insensitively. "*plan*"
# is deliberately EXCLUDED (it matches e.g. TASK7_LOGIN_PLAN.md - a
# recipe, not a status doc); PLAN_STATUS.md is caught by "*status*".
STATUS_DOC_PATTERNS = ("*status*", "*roadmap*", "*devlog*", "*changelog*", "*future*", "*todo*")

_EXCLUDE_DIRS = {
    ".git",
    "node_modules",
    "target",
    ".venv",
    "__pycache__",
    "dist",
    "build",
    ".next",
    "var",
}


@contract(
    precondition="repo_path is a non-empty string resolving to an existing "
    "directory; patterns (if given) is a non-empty sequence of filename "
    "glob patterns.",
    postcondition="Returns the absolute path of the most recently modified "
    "*.md file in repo_path (recursive, excluding build/vendored dirs) "
    "whose filename matches one of the status/planning patterns - or, when "
    "no status-shaped doc exists, the repo root README.md if present - or '' "
    "when neither exists. Read-only - nothing is created or modified.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PreconditionError when repo_path does not exist or is not "
    "a directory. An absent doc is a RESULT (''), never an exception - the "
    "caller decides whether no status doc is acceptable.",
    returns="str: absolute path of the chosen doc, or '' when none exists.",
)
def find_recent_doc(repo_path: str, patterns: list[str] | tuple[str, ...] | None = None) -> str:
    """Find the most recently modified status/planning doc in a repo.

    The digest's recency-based context gatherer (Phase C v2.2): instead of
    always reading README.md (which can be create-next-app boilerplate),
    find the status-shaped doc the user already maintains as a byproduct
    of real work - PLAN_STATUS.md / ROADMAP.md / DEVLOG.md / docs/*roadmap*
    and similar - and read THAT. Falls back to the repo-root README.md
    only when nothing status-shaped exists ("an absent doc is a result" -
    the fallback keeps the digest trigger from failing on a doc-less repo)."""
    if not repo_path or not repo_path.strip():
        raise PreconditionError("find_recent_doc requires a non-empty 'repo_path'")
    base = _anchor(repo_path)
    if not base.is_dir():
        raise PreconditionError(f"find_recent_doc: repo directory does not exist: {base}")
    pats = tuple(patterns) if patterns else STATUS_DOC_PATTERNS
    if not pats:
        raise PreconditionError("find_recent_doc requires at least one pattern")

    best: Path | None = None
    best_key: tuple[float, str] = (-1.0, "")
    for dirpath, dirnames, files in os.walk(base, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in _EXCLUDE_DIRS]
        for fn in files:
            if not fn.lower().endswith(".md"):
                continue
            # case-insensitive: PLAN_STATUS.md / DEVLOG.md / ROADMAP.md are
            # conventionally uppercase, the patterns are lowercase
            if not any(fnmatch.fnmatch(fn.lower(), pat.lower()) for pat in pats):
                continue
            p = Path(dirpath) / fn
            try:
                mtime = p.stat().st_mtime
            except OSError:
                continue
            key = (mtime, str(p))  # deterministic tie-break on path
            if key > best_key:
                best, best_key = p, key
    if best is not None:
        return str(best)

    # Fallback: repo-root README (any case).
    for name in ("README.md", "readme.md", "Readme.md", "README.MD"):
        r = base / name
        if r.is_file():
            return str(r)
    return ""


# ---- gate-registered files.write_text (2026-08-13) ----
@contract(
    precondition="path is a non-empty string; text is a str; the parent directory exists; append is a bool.",
    postcondition="Creates or overwrites (or appends to) the file at path with "
    "the given text encoded as UTF-8. Parent directories are NOT created. "
    "Side-effect: writes to the filesystem.",
    idempotency=Idempotency.COMMUTATIVE_SAFE,
    failure_mode="PreconditionError when path is empty, parent directory does "
    "not exist, or path is not a string; OSError propagated on disk-space "
    "failure or read-only filesystem.",
    returns="str: the absolute path of the written file.",
)
def write_text(path: str, text: str, *, append: bool = False) -> str:
    """Write text content to the file at path, creating or replacing it.

    The bounded writer counterpart to read_text: needed by the digest
    trigger's "write the latest digest summary to a notes file" path,
    which was previously refused because no write primitive was
    registered. append=True opens in append mode (idempotency class
    becomes commutative-safe: repeated appends are harmless if the
    content already exists). ~ expands; relative paths anchor at the
    project root (same rule as find_file/read_text). Returns the
    absolute path so a plan step can reference it downstream."""
    if not path or not path.strip():
        raise PreconditionError("write_text requires a non-empty 'path'")
    p = _anchor(path)
    parent = p.parent
    if not parent.is_dir():
        raise PreconditionError(f"write_text: parent directory does not exist: {parent}")
    mode = "a" if append else "w"
    with p.open(mode, encoding="utf-8") as f:
        f.write(text)
    return str(p)


# ---- gate-registered files.find_newest (2026-08-14) ----
# Hand-corrected after human review (2026-08-14): the LLM draft returned a
# dict {path, name, mtime, matches}, but the two gate-registered files.*
# READ primitives (find_file_exact, find_recent_doc) return a str path -
# the convention the read-family build-verify probe enforces, and the
# shape the download-alert trigger plan can feed straight into
# whatsapp.send_document ($steps.N.result).


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


# ---- files.copy, files.move, files.delete, files.list_dir, files.file_size ----


@contract(
    precondition="source is an existing file; dest_dir is an existing directory.",
    postcondition="Copies the file to dest_dir with the same filename. Side-effecting.",
    idempotency=Idempotency.COMMUTATIVE_SAFE,
    failure_mode="PreconditionError for missing source/dest; PrimitiveError on copy failure.",
    returns="str: absolute path of the copied file.",
)
def copy(source: str, dest_dir: str) -> str:
    """Copy a file to a destination directory.

    Copies the file at `source` into `dest_dir` keeping the same filename.
    Returns the absolute path of the new copy.
    """
    if not source or not source.strip():
        raise PreconditionError("copy requires a non-empty 'source'")
    if not dest_dir or not dest_dir.strip():
        raise PreconditionError("copy requires a non-empty 'dest_dir'")
    src = _anchor(source)
    dst = _anchor(dest_dir)
    if not src.is_file():
        raise PreconditionError(f"copy: source file does not exist: {src}")
    if not dst.is_dir():
        raise PreconditionError(f"copy: dest_dir does not exist: {dst}")
    dest_file = dst / src.name
    shutil.copy2(str(src), str(dest_file))
    return str(dest_file)


@contract(
    precondition="source is an existing file; dest_dir is an existing directory.",
    postcondition="Moves the file to dest_dir with the same filename. Side-effecting.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PreconditionError for missing source/dest; PrimitiveError on move failure.",
    returns="str: absolute path of the moved file.",
)
def move(source: str, dest_dir: str) -> str:
    """Move a file to a destination directory.

    Moves the file at `source` into `dest_dir` keeping the same filename.
    Returns the absolute path of the new location.
    """
    if not source or not source.strip():
        raise PreconditionError("move requires a non-empty 'source'")
    if not dest_dir or not dest_dir.strip():
        raise PreconditionError("move requires a non-empty 'dest_dir'")
    src = _anchor(source)
    dst = _anchor(dest_dir)
    if not src.is_file():
        raise PreconditionError(f"move: source file does not exist: {src}")
    if not dst.is_dir():
        raise PreconditionError(f"move: dest_dir does not exist: {dst}")
    dest_file = dst / src.name
    shutil.move(str(src), str(dest_file))
    return str(dest_file)


@contract(
    precondition="path is an existing file.",
    postcondition="Deletes the file. Side-effecting.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PreconditionError for missing file; PrimitiveError on delete failure.",
    returns="str: the path that was deleted.",
)
def delete(path: str) -> str:
    """Delete a file.

    Deletes the file at `path`. Returns the path that was deleted.
    """
    if not path or not path.strip():
        raise PreconditionError("delete requires a non-empty 'path'")
    p = _anchor(path)
    if not p.is_file():
        raise PreconditionError(f"delete: file does not exist: {p}")
    p.unlink()
    return str(p)


@contract(
    precondition="path is an existing directory.",
    postcondition="Returns the directory listing. Read-only.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PreconditionError for missing directory.",
    returns="dict: {path, files: list[str], dirs: list[str], count: int}.",
)
def list_dir(path: str = ".") -> dict[str, Any]:
    """List the contents of a directory.

    Returns files and subdirectories (non-recursive) with a total count.
    Useful for goals like 'what files are in my downloads'.
    """
    if not path or not path.strip():
        path = "."
    p = _anchor(path)
    if not p.is_dir():
        raise PreconditionError(f"list_dir: directory does not exist: {p}")
    files = []
    dirs = []
    try:
        for item in sorted(p.iterdir()):
            if item.is_file():
                files.append(item.name)
            elif item.is_dir():
                dirs.append(item.name)
    except OSError as exc:
        raise PreconditionError(f"list_dir: cannot scan {p}: {exc}") from exc
    return {
        "path": str(p),
        "files": files,
        "dirs": dirs,
        "count": len(files) + len(dirs),
    }


@contract(
    precondition="path is an existing file.",
    postcondition="Returns the file size in bytes. Read-only.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PreconditionError for missing file.",
    returns="dict: {path, size_bytes, size_human}.",
)
def file_size(path: str) -> dict[str, Any]:
    """Get the size of a file in bytes and human-readable format.

    Returns size in bytes and a human-readable string (KB/MB/GB).
    Useful for goals like 'is this file too large to email'.
    """
    if not path or not path.strip():
        raise PreconditionError("file_size requires a non-empty 'path'")
    p = _anchor(path)
    if not p.is_file():
        raise PreconditionError(f"file_size: file does not exist: {p}")
    size = p.stat().st_size
    if size < 1024:
        human = f"{size} B"
    elif size < 1024 * 1024:
        human = f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        human = f"{size / (1024 * 1024):.1f} MB"
    else:
        human = f"{size / (1024 * 1024 * 1024):.1f} GB"
    return {
        "path": str(p),
        "size_bytes": size,
        "size_human": human,
    }
