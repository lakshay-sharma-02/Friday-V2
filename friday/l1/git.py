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


# ---- gate-registered git.status (2026-08-18) ----
# created by the capability-gap approval gate; reviewed by a human
# before signing.


def _parse_status(output: str) -> dict:
    """Parse git status --porcelain -b output into structured dict."""
    result = {
        "branch": "HEAD",
        "staged": [],
        "conflicts": [],
        "uncommitted": [],
        "is_clean": True,
    }

    lines = output.strip().splitlines()

    # First line is branch info (## branch-name or ## HEAD detached at ...)
    for line in lines:
        if line.startswith("## ") and not line.startswith("##  "):
            branch_line = line[3:]
            # Handle detached HEAD
            if branch_line.startswith("HEAD detached at"):
                result["branch"] = "HEAD"
            elif branch_line.startswith("branch"):
                # "branch main (x commits ahead...)" -> extract "main"
                parts = branch_line.split()
                if parts:
                    result["branch"] = parts[-1].split("(")[0].strip()
            else:
                result["branch"] = branch_line.strip()
            break

    # Remaining lines are file status (2-char prefix + path)
    for line in lines[1:]:
        if len(line) < 3:
            continue
        status = line[:2]
        path_part = line[3:]

        # First char: staged status (untracked files have "??")
        # Second char: unstaged status
        if status == "??":
            result["uncommitted"].append(path_part)
            result["is_clean"] = False
        elif "M" in status or "A" in status or "D" in status:
            # There are staged changes
            result["staged"].append(path_part)
            result["is_clean"] = False
        elif "U" in status:
            # Merge conflict
            result["conflicts"].append(path_part)
            result["is_clean"] = False
        elif "M" in status[1:]:
            # Unstaged modifications
            result["uncommitted"].append(path_part)
            result["is_clean"] = False

    return result


@contract(
    precondition="repo_path is an existing directory containing a git repository.",
    postcondition="Returns the git status of the repository as a dict. Makes NO state changes - this is a read-only query.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PreconditionError for a missing/non-directory repo_path; PrimitiveError if git itself fails or the path is not a git repository.",
    returns="dict: {branch: str, staged: list[str], conflicts: list[str], uncommitted: list[str], is_clean: bool} - branch name is 'HEAD' when detached; staged lists paths with staged changes; conflicts lists merge conflicts; uncommitted lists modified/untracked files; is_clean is true when staged, conflicts, and uncommitted are all empty."
)
def status(repo_path: str) -> dict:
    """Get the status of a git repository.

    Returns a dict with branch name and lists of staged, conflicted, and
    uncommitted files. is_clean is True when there are no changes.

    This is useful for checking if a repo has pending changes before
    making decisions about commits or pushes.
    """
    if not repo_path or not repo_path.strip():
        raise PreconditionError("git.status requires a non-empty repo_path")

    repo = _anchor(repo_path)
    if not repo.is_dir():
        raise PreconditionError(f"git.status: directory does not exist: {repo}")

    # Check if it's a git repository first - using all-literal command
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--git-dir"],
            capture_output=True,
            timeout=GIT_TIMEOUT_S,
            text=True,
        )
    except FileNotFoundError as exc:
        raise PrimitiveError("git is not installed or not on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise PrimitiveError(f"git status check timed out after {GIT_TIMEOUT_S}s") from exc

    if proc.returncode != 0:
        raise PreconditionError(
            f"git.status: not a git repository: {repo}"
        )

    # Get porcelain status - using all-literal command
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain", "-b"],
            capture_output=True,
            timeout=GIT_TIMEOUT_S,
            text=True,
        )
    except FileNotFoundError as exc:
        raise PrimitiveError("git is not installed or not on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise PrimitiveError(f"git status timed out after {GIT_TIMEOUT_S}s") from exc

    if proc.returncode != 0:
        raise PrimitiveError(
            f"git status failed: {proc.stderr.strip()[:200] if proc.stderr else 'unknown error'}"
        )

    return _parse_status(proc.stdout)


# ---- git.diff: staged + unstaged changes ----


def _run_git(repo: Path, *args: str) -> str:
    """Run a git command and return stdout. Raises PrimitiveError on failure."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo)] + list(args),
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_S,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise PrimitiveError("git is not installed or not on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise PrimitiveError(
            f"git command timed out after {GIT_TIMEOUT_S}s"
        ) from exc
    if proc.returncode != 0:
        raise PrimitiveError(
            f"git {' '.join(args)} failed (rc={proc.returncode}): {proc.stderr.strip()[:300]}"
        )
    return proc.stdout


@contract(
    precondition="repo_path is an existing directory containing a git repository.",
    postcondition="Returns the diff of staged and unstaged changes. Read-only.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PreconditionError for missing repo; PrimitiveError if git fails.",
    returns="dict: {staged: str, unstaged: str, is_clean: bool}.",
)
def diff(repo_path: str) -> dict[str, Any]:
    """Get staged and unstaged diffs for a repository.

    Returns a dict with 'staged' (git diff --cached), 'unstaged'
    (git diff), and 'is_clean' (both empty). Useful for goals like
    'what changed since my last commit' or 'show me pending changes'.
    """
    if not repo_path or not repo_path.strip():
        raise PreconditionError("git.diff requires a non-empty repo_path")
    repo = _anchor(repo_path)
    if not repo.is_dir():
        raise PreconditionError(f"git.diff: directory does not exist: {repo}")
    staged = _run_git(repo, "diff", "--cached")
    unstaged = _run_git(repo, "diff")
    return {
        "staged": staged,
        "unstaged": unstaged,
        "is_clean": not staged.strip() and not unstaged.strip(),
    }


# ---- git.branch: list and current branch ----


@contract(
    precondition="repo_path is an existing directory containing a git repository.",
    postcondition="Returns branch info: current branch name and list of all local branches.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PreconditionError for missing repo; PrimitiveError if git fails.",
    returns="dict: {current: str, branches: list[str]}.",
)
def branch(repo_path: str) -> dict[str, Any]:
    """Get branch information for a repository.

    Returns the current branch name and a list of all local branches.
    Useful for goals like 'which branch am I on' or 'list all branches'.
    """
    if not repo_path or not repo_path.strip():
        raise PreconditionError("git.branch requires a non-empty repo_path")
    repo = _anchor(repo_path)
    if not repo.is_dir():
        raise PreconditionError(f"git.branch: directory does not exist: {repo}")
    current = _run_git(repo, "branch", "--show-current").strip()
    raw = _run_git(repo, "branch")
    branches = [
        line.lstrip("* ").strip()
        for line in raw.splitlines()
        if line.strip()
    ]
    return {
        "current": current or "HEAD",
        "branches": branches,
    }


# ---- git.commit: create a commit ----


@contract(
    precondition="repo_path is an existing git repository; message is a non-empty string; files (if given) is a list of paths to stage.",
    postcondition="Creates a git commit with the given message. Side-effecting.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PreconditionError for empty message or missing repo; PrimitiveError if git commit fails.",
    returns="dict: {commit_hash: str, message: str}.",
)
def commit(repo_path: str, message: str, files: list[str] | None = None) -> dict[str, Any]:
    """Stage files and create a git commit.

    If files is None, commits all staged changes (--all). If files is
    a list, stages those specific files first. Returns the new commit
    hash and message.
    """
    if not repo_path or not repo_path.strip():
        raise PreconditionError("git.commit requires a non-empty repo_path")
    if not message or not message.strip():
        raise PreconditionError("git.commit requires a non-empty message")
    repo = _anchor(repo_path)
    if not repo.is_dir():
        raise PreconditionError(f"git.commit: directory does not exist: {repo}")
    if files:
        _run_git(repo, "add", *files)
    else:
        _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-m", message.strip())
    commit_hash = _run_git(repo, "rev-parse", "HEAD").strip()
    return {
        "commit_hash": commit_hash,
        "message": message.strip(),
    }
