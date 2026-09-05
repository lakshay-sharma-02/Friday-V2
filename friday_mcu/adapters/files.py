"""Files adapter — deterministic file discovery and bounded reader.

Ported from V8 l1/files.py with the same contract-registered primitives.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from friday_mcu.adapters import Adapter, register_adapter
from friday_mcu.core.contracts import Idempotency, contract
from friday_mcu.core.errors import PreconditionError, PrimitiveError


@contract(
    precondition="name is a non-empty substring, directory exists.",
    postcondition="Returns {path, name, directory} for the first match, or raises.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PreconditionError if no match found or directory missing.",
    returns="dict: {path: str, name: str, directory: str}.",
)
def find_file(name: str, directory: str, recursive: bool = False) -> dict[str, str]:
    """Find a file by name substring in a directory."""
    if not name or not name.strip():
        raise PreconditionError("find_file requires a non-empty name")
    d = Path(directory).expanduser()
    if not d.is_dir():
        raise PreconditionError(f"directory does not exist: {directory}")
    needle = name.lower()
    try:
        if recursive:
            matches = [
                p for p in d.rglob("*")
                if p.is_file() and needle in p.name.lower()
            ]
        else:
            matches = [
                p for p in d.iterdir()
                if p.is_file() and needle in p.name.lower()
            ]
    except OSError as exc:
        raise PrimitiveError(f"failed to search {directory}: {exc}") from exc
    if not matches:
        raise PreconditionError(f"no file matching '{name}' in {directory}")
    matches.sort(key=lambda p: p.name.lower())
    chosen = matches[0]
    return {"path": str(chosen.resolve()), "name": chosen.name, "directory": str(d)}


@contract(
    precondition="name is a non-empty substring, directory exists.",
    postcondition="Returns {path, name} for exact match, or empty path if absent.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="Never raises for missing file — returns empty path.",
    returns="dict: {path: str, name: str}.",
)
def find_file_exact(name: str, directory: str) -> dict[str, str]:
    """Find a file by exact name match. Returns empty path if not found."""
    d = Path(directory).expanduser()
    if not d.is_dir():
        return {"path": "", "name": name}
    target = d / name
    if target.is_file():
        return {"path": str(target.resolve()), "name": name}
    return {"path": "", "name": name}


@contract(
    precondition="name is a non-empty substring, directory exists.",
    postcondition="Returns {path, name} for the newest match by mtime, or empty path.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="Never raises for missing file — returns empty path.",
    returns="dict: {path: str, name: str}.",
)
def find_newest(name: str, directory: str) -> dict[str, str]:
    """Find the most recently modified file matching a name substring."""
    d = Path(directory).expanduser()
    if not d.is_dir():
        return {"path": "", "name": name}
    needle = name.lower()
    try:
        matches = [p for p in d.iterdir() if p.is_file() and needle in p.name.lower()]
    except OSError:
        return {"path": "", "name": name}
    if not matches:
        return {"path": "", "name": name}
    newest = max(matches, key=lambda p: p.stat().st_mtime)
    return {"path": str(newest.resolve()), "name": newest.name}


@contract(
    precondition="path points to a readable file.",
    postcondition="Returns {path, text, size} with bounded text content.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PreconditionError if file missing or unreadable.",
    returns="dict: {path: str, text: str, size: int}.",
)
def read_text(path: str, max_chars: int = 100_000) -> dict[str, Any]:
    """Read bounded text content from a file."""
    p = Path(path).expanduser()
    if not p.is_file():
        raise PreconditionError(f"file not found: {path}")
    try:
        text = p.read_text(encoding="utf-8", errors="replace")[:max_chars]
        return {"path": str(p.resolve()), "text": text, "size": p.stat().st_size}
    except OSError as exc:
        raise PrimitiveError(f"failed to read {path}: {exc}") from exc


@contract(
    precondition="path is a writable location.",
    postcondition="File exists with the written content.",
    idempotency=Idempotency.COMMUTATIVE_SAFE,
    failure_mode="PrimitiveError if write fails.",
    returns="dict: {path: str, bytes_written: int, appended: bool}.",
)
def write_text(path: str, text: str, append: bool = False) -> dict[str, Any]:
    """Write text to a file (create or append)."""
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        mode = "a" if append else "w"
        with open(p, mode, encoding="utf-8") as fh:
            fh.write(text)
        return {"path": str(p.resolve()), "bytes_written": len(text.encode("utf-8")), "appended": append}
    except OSError as exc:
        raise PrimitiveError(f"failed to write {path}: {exc}") from exc


@contract(
    precondition="directory exists.",
    postcondition="Returns list of file entries in the directory.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PreconditionError if directory missing.",
    returns="dict: {path: str, entries: list[str], total: int}.",
)
def list_dir(path: str) -> dict[str, Any]:
    """List files in a directory."""
    p = Path(path).expanduser()
    if not p.is_dir():
        raise PreconditionError(f"directory not found: {path}")
    try:
        entries = sorted([e.name for e in p.iterdir()])
        return {"path": str(p.resolve()), "entries": entries, "total": len(entries)}
    except OSError as exc:
        raise PrimitiveError(f"failed to list {path}: {exc}") from exc


class FilesAdapter(Adapter):
    """File operations adapter."""

    @property
    def name(self) -> str:
        return "files"

    @property
    def capabilities(self) -> list[str]:
        return ["find_file", "find_file_exact", "find_newest", "read_text", "write_text", "list_dir"]

    async def initialize(self) -> None:
        pass

    async def execute(self, action: str, **kwargs: Any) -> Any:
        actions = {
            "find_file": find_file,
            "find_file_exact": find_file_exact,
            "find_newest": find_newest,
            "read_text": read_text,
            "write_text": write_text,
            "list_dir": list_dir,
        }
        fn = actions.get(action)
        if fn is None:
            raise PrimitiveError(f"Unknown files action: {action}")
        return fn(**kwargs)

    async def observe(self) -> list:
        return []

    def health_check(self) -> bool:
        return True


try:
    register_adapter(FilesAdapter())
except Exception:
    pass
