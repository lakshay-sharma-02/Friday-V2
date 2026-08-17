"""L1 primitive: git (deterministic read-only repository history).

The cross-project layer's eyes: a read-only primitive that returns recent
commit entries (hash, author, date, subject) for a local repository via
the `git` CLI. No diffs, no file contents, no writes - just the history
surface the weekly cross-project digest summarizes. Verification of the
result (non-empty, correct shape) is the caller's (L2's) job, never its
own.

Deterministic by contract: entries are newest-first, bounded by `count`
(and optionally `days`), parsed from a unit-separator format so subjects
containing any character parse safely. Idempotent, so the executor may
retry it freely.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from friday.contracts import Idempotency, contract
from friday.errors import PreconditionError, PrimitiveError

# Anchoring rule identical to files._anchor / planner._resolve_path: ~
# expands, relative paths anchor at the project root, so a repo path in a
# trigger config is deterministic regardless of the process cwd.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

GIT_TIMEOUT_S = 30


def _anchor(raw: str) -> Path:
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return p


def _git_log(repo: Path, count: int, days: int | None) -> list[str]:
    """Run `git log` and return raw formatted lines. Unit-separator
    (%x1f) fields so a subject containing '|' or any printable character
    parses safely. Never raises for an empty history (empty output is the
    legitimate no-commits-in-range result)."""
    fmt = "%h%x1f%an%x1f%ad%x1f%s"
    cmd = [
        "git",
        "--no-pager",
        "-C",
        str(repo),
        "log",
        f"--format={fmt}",
        "--date=short",
        "-n",
        str(count),
    ]
    if days is not None:
        cmd += ["--since", f"{int(days)} days ago"]
    env = dict(os.environ, LC_ALL="C")
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_S,
            env=env,
            # decode in the parent locale-robustly: a non-UTF-8 commit
            # subject must be REPLACED, never raise UnicodeDecodeError
            # (which the executor would misread as a caller bug)
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise PrimitiveError(
            "git is not installed or not on PATH",
            state="git binary missing",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise PrimitiveError(
            f"git log did not finish within {GIT_TIMEOUT_S}s",
            state="git log timed out",
        ) from exc
    if proc.returncode != 0:
        # An initialized repo with NO commits exits 128 with this specific
        # message - that is the legitimate empty-history result (an empty
        # list), not a failure. Any other error (not a repository, git
        # missing) raises PrimitiveError.
        if "does not have any commits yet" in proc.stderr:
            return []
        raise PrimitiveError(
            f"git log failed (rc={proc.returncode}): {proc.stderr.strip()[:300]}",
            state="git log failed - is the path a git repository?",
        )
    return [l for l in proc.stdout.splitlines() if l.strip()]


@contract(
    precondition="repo_path is an existing directory containing a git "
    "repository; count >= 1; days (if given) is >= 1.",
    postcondition="Returns the most recent commit entries as a list of "
    "{commit, author, date, subject} dicts, newest first, with NO diff or "
    "file content. Read-only - nothing is created, read beyond the "
    "history, or modified.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PreconditionError for a missing/non-directory repo_path or "
    "an invalid count/days; PrimitiveError if git itself fails (not a "
    "repository, git missing). An empty history (no commits in range) is "
    "an empty list, never an exception.",
    returns="list[dict]: [{commit, author, date, subject}] newest first.",
)
def log(repo_path: str, count: int = 10, days: int | None = None) -> list[dict[str, str]]:
    """Recent commit entries for a local git repository, newest first.

    `repo_path` is the repository directory (~ expands, relative paths
    anchor at the project root). `count` bounds the number of entries;
    `days` (optional) restricts to commits within that many days.
    Returns [{commit, author, date, subject}] - a compact history surface
    with no diff content, sized for an LLM digest prompt.
    """
    if not repo_path or not repo_path.strip():
        raise PreconditionError("git.log requires a non-empty repo_path")
    base = _anchor(repo_path)
    if not base.is_dir():
        raise PreconditionError(f"git.log: directory does not exist: {base}")
    if count < 1:
        raise PreconditionError("git.log: count must be >= 1")
    if days is not None and days < 1:
        raise PreconditionError("git.log: days must be >= 1")
    out: list[dict[str, str]] = []
    for line in _git_log(base, count, days):
        parts = line.split("\x1f")
        if len(parts) < 4:
            continue  # defensive: a malformed line is skipped, never fatal
        out.append(
            {
                "commit": parts[0],
                "author": parts[1],
                "date": parts[2],
                "subject": "\x1f".join(parts[3:]),
            }
        )
    return out
