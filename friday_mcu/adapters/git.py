"""Git adapter — read-only git operations (log, status, diff, branch)."""

from __future__ import annotations

import subprocess
from typing import Any

from friday_mcu.adapters import Adapter, register_adapter
from friday_mcu.core.contracts import Idempotency, contract
from friday_mcu.core.errors import PreconditionError, PrimitiveError


def _git(repo_path: str, *args: str) -> str:
    """Run a git command and return stdout."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            raise PrimitiveError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout
    except FileNotFoundError:
        raise PrimitiveError("git not found")
    except subprocess.TimeoutExpired as exc:
        raise PrimitiveError(f"git {' '.join(args)} timed out") from exc


@contract(
    precondition="repo_path is a git repository.",
    postcondition="Returns recent commit entries.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if git log fails.",
    returns="list[dict]: [{hash, author, date, subject}].",
)
def log(repo_path: str = ".", count: int = 10, days: int = 0) -> list[dict[str, str]]:
    """Get recent git log entries."""
    if not repo_path:
        raise PreconditionError("repo_path is required")
    args = ["log", f"--max-count={count}", "--pretty=format:%H|%an|%ai|%s"]
    if days > 0:
        args.append(f"--since={days} days ago")
    output = _git(repo_path, *args)
    entries: list[dict[str, str]] = []
    for line in output.strip().splitlines():
        parts = line.split("|", 3)
        if len(parts) == 4:
            entries.append({
                "hash": parts[0],
                "author": parts[1],
                "date": parts[2],
                "subject": parts[3],
            })
    return entries


@contract(
    precondition="repo_path is a git repository.",
    postcondition="Returns branch and status info.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if git status fails.",
    returns="dict: {branch, is_clean, staged, unstaged}.",
)
def status(repo_path: str = ".") -> dict[str, Any]:
    """Get git repository status."""
    branch = _git(repo_path, "branch", "--show-current").strip()
    porcelain = _git(repo_path, "status", "--porcelain")
    lines = [l.strip() for l in porcelain.strip().splitlines() if l.strip()]
    staged = [l for l in lines if l[0] != " " and l[0] != "?"]
    unstaged = [l for l in lines if l[0] == " " and len(l) > 1 and l[1] != " "]
    return {
        "branch": branch,
        "is_clean": len(lines) == 0,
        "staged": staged,
        "unstaged": unstaged,
    }


@contract(
    precondition="repo_path is a git repository.",
    postcondition="Returns the diff.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if git diff fails.",
    returns="dict: {diff: str, is_clean: bool}.",
)
def diff(repo_path: str = ".") -> dict[str, Any]:
    """Get git diff (staged + unstaged)."""
    output = _git(repo_path, "diff", "HEAD")
    return {"diff": output[:50000], "is_clean": not output.strip()}


@contract(
    precondition="repo_path is a git repository.",
    postcondition="Returns branch info.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if git branch fails.",
    returns="dict: {current: str, all: list[str]}.",
)
def branch(repo_path: str = ".") -> dict[str, Any]:
    """Get current branch and all local branches."""
    current = _git(repo_path, "branch", "--show-current").strip()
    all_output = _git(repo_path, "branch")
    branches = [l.strip().lstrip("* ") for l in all_output.splitlines() if l.strip()]
    return {"current": current, "all": branches}


class GitAdapter(Adapter):
    @property
    def name(self) -> str:
        return "git"

    @property
    def capabilities(self) -> list[str]:
        return ["log", "status", "diff", "branch"]

    async def initialize(self) -> None:
        pass

    async def execute(self, action: str, **kwargs: Any) -> Any:
        actions = {"log": log, "status": status, "diff": diff, "branch": branch}
        fn = actions.get(action)
        if fn is None:
            raise PrimitiveError(f"Unknown git action: {action}")
        return fn(**kwargs)

    async def observe(self) -> list:
        return []

    def health_check(self) -> bool:
        try:
            result = subprocess.run(["git", "--version"], capture_output=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False


try:
    register_adapter(GitAdapter())
except Exception:
    pass
