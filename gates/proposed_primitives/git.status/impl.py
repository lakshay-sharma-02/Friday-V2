# ---- gate-registered git.status (2026-08-18) ----
# created by the capability-gap approval gate; reviewed by a human
# before signing.
"""L1 primitive: git (status query).

A read-only primitive that returns the current status of a git repository -
which branch is checked out, what files have staged changes, what files
have uncommitted changes, and whether the repo is clean. This enables
goals like "check if Friday repo has uncommitted changes" or "list all
modified files in the vivaha repo".
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from friday.contracts import Idempotency, contract
from friday.errors import PreconditionError, PrimitiveError

PROJECT_ROOT = Path(__file__).resolve().parents[3]
GIT_TIMEOUT_S = 10


def _anchor(raw: str) -> str:
    """Resolve a directory path: ~ expands, relative paths anchor at PROJECT_ROOT.

    Returns the string path, not a Path object, so it can be used in
    literal subprocess commands.
    """
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return str(p)


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
    if not Path(repo).is_dir():
        raise PreconditionError(f"git.status: directory does not exist: {repo}")

    # Check if it's a git repository first - using all-literal command
    try:
        proc = subprocess.run(
            ["git", "-C", repo, "rev-parse", "--git-dir"],
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
            ["git", "-C", repo, "status", "--porcelain", "-b"],
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