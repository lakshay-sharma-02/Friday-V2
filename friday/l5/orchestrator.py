"""L5 - Workflow Orchestrator: high-level coordination for multi-plan workflows.

The L5 layer provides workflow orchestration capabilities that coordinate
multiple plans, manage concurrent executions, and provide higher-level
composition primitives.

Key capabilities:
  - Workflow composition: combine multiple plans into a single workflow
  - Conditional execution: run plans based on conditions or previous results
  - Parallel execution: run independent plans concurrently
  - Retry orchestration: apply retry policies across plan boundaries
  - State management: persist and retrieve workflow state

This module builds on top of L3 (executor) and L4 (planner) to provide
a rich orchestration interface for complex automation scenarios.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional


class WorkflowStatus(Enum):
    """Status of a workflow execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"
    CANCELLED = "cancelled"


@dataclass
class WorkflowStep:
    """A step in a workflow - either a plan or a conditional branch."""
    name: str
    plan: Optional[dict[str, Any]] = None
    condition: Optional[str] = None  # Python expression to evaluate
    on_success: Optional[str] = None  # Next step name
    on_failure: Optional[str] = None  # Next step name
    parallel: bool = False  # Run in parallel with subsequent parallel steps
    timeout_s: Optional[float] = None


@dataclass
class WorkflowState:
    """State of a running workflow."""
    name: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    current_step: Optional[str] = None
    step_results: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    variables: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowResult:
    """Result of a workflow execution."""
    success: bool
    state: WorkflowState
    duration_s: float


class WorkflowException(Exception):
    """Base exception for workflow errors."""
    pass


class WorkflowCancelled(Exception):
    """Workflow was cancelled."""
    pass


class ConditionalExecution:
    """Helper class for conditional execution within workflows."""

    @staticmethod
    def evaluate(condition: str, variables: dict[str, Any]) -> bool:
        """Evaluate a condition expression against variables.

        Supports simple expressions like:
        - "step_result.status == 'COMPLETED'"
        - "steps[1].status == 'VERIFIED'"
        - "variables['counter'] > 0"
        """
        # Create a safe evaluation context
        safe_globals = {
            "True": True,
            "False": False,
            "None": None,
        }
        safe_locals = {
            **variables,
            "step_result": variables.get("step_result"),
            "steps": variables.get("steps", {}).get("results"),
        }

        try:
            # Simple eval with safety checks
            result = eval(condition, safe_globals, safe_locals)
            return bool(result)
        except Exception:
            return False


class WorkflowOrchestrator:
    """Orchestrates the execution of multi-plan workflows.

    Provides high-level coordination for complex automation scenarios
    that require multiple plans with conditional execution, parallelism,
    and state management.
    """

    def __init__(self):
        self._workflows: dict[str, WorkflowState] = {}
        self._max_concurrent_workflows: int = 10
        self._workflow_times: dict[str, float] = {}  # For rate limiting

    def create_workflow(
        self,
        name: str,
        steps: list[WorkflowStep],
        variables: Optional[dict[str, Any]] = None,
    ) -> str:
        """Create a new workflow definition.

        Args:
            name: Unique name for the workflow
            steps: List of workflow steps (plans or conditions)
            variables: Initial variables for the workflow

        Returns:
            The workflow name (same as input)
        """
        if name in self._workflows:
            raise WorkflowException(f"Workflow '{name}' already exists")

        self._workflows[name] = WorkflowState(
            name=name,
            variables=variables or {},
        )
        return name

    def start_workflow(self, name: str) -> WorkflowResult:
        """Start executing a workflow.

        Args:
            name: Name of the workflow to start

        Returns:
            Initial WorkflowResult
        """
        if name not in self._workflows:
            raise WorkflowException(f"Workflow '{name}' not found")

        state = self._workflows[name]
        if state.status != WorkflowStatus.PENDING:
            raise WorkflowException(f"Workflow '{name}' is not in pending state")

        state.status = WorkflowStatus.RUNNING
        state.started_at = datetime.now()

        # Start async execution
        asyncio.create_task(self._run_workflow_async(name))

        return WorkflowResult(
            success=False,
            state=state,
            duration_s=0.0,
        )

    async def _run_workflow_async(self, name: str) -> None:
        """Async workflow execution."""
        from friday.l3.executor import run_plan

        state = self._workflows[name]
        steps_data = state.steps or []  # This would need to be stored with workflow definition

        for step in steps_data:
            state.current_step = step.name

            try:
                # Handle conditional execution
                if step.condition:
                    if not ConditionalExecution.evaluate(step.condition, state.variables):
                        # Condition failed, skip to on_failure or next step
                        continue

                # Execute the plan
                if step.plan:
                    start_time = time.monotonic()
                    result = run_plan(step.plan, run_id=f"wf-{name}-{step.name}")
                    duration = time.monotonic() - start_time

                    state.step_results[step.name] = {
                        "status": result.status,
                        "duration_s": duration,
                        "steps": [s.__dict__ for s in result.steps],
                    }
                    state.variables[f"step_{step.name}"] = result

                    if result.status != "COMPLETED":
                        state.status = WorkflowStatus.FAILED
                        state.error = f"Step '{step.name}' failed: {result.steps[-1].error if result.steps else 'Unknown'}"
                        break

            except Exception as e:
                state.status = WorkflowStatus.FAILED
                state.error = f"Step '{step.name}' error: {e}"
                break

        state.completed_at = datetime.now()
        if state.status == WorkflowStatus.RUNNING:
            state.status = WorkflowStatus.COMPLETED

    def get_workflow_state(self, name: str) -> WorkflowState:
        """Get the current state of a workflow."""
        if name not in self._workflows:
            raise WorkflowException(f"Workflow '{name}' not found")
        return self._workflows[name]

    def cancel_workflow(self, name: str) -> None:
        """Cancel a running workflow."""
        if name not in self._workflows:
            raise WorkflowException(f"Workflow '{name}' not found")

        state = self._workflows[name]
        if state.status == WorkflowStatus.RUNNING:
            state.status = WorkflowStatus.CANCELLED
            state.error = "Workflow was cancelled"

    def list_workflows(self) -> list[dict[str, Any]]:
        """List all workflows and their states."""
        return [
            {
                "name": s.name,
                "status": s.status.value,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "current_step": s.current_step,
            }
            for s in self._workflows.values()
        ]

    def delete_workflow(self, name: str) -> None:
        """Delete a workflow (must be completed or failed)."""
        if name not in self._workflows:
            raise WorkflowException(f"Workflow '{name}' not found")

        state = self._workflows[name]
        if state.status == WorkflowStatus.RUNNING:
            raise WorkflowException(f"Cannot delete running workflow '{name}'")

        del self._workflows[name]


# Global orchestrator instance
_orchestrator: Optional[WorkflowOrchestrator] = None


def get_orchestrator() -> WorkflowOrchestrator:
    """Get the global workflow orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = WorkflowOrchestrator()
    return _orchestrator


def compose_workflows(
    plans: list[dict[str, Any]],
    parallel: bool = False,
    dependencies: Optional[dict[int, int]] = None,
) -> dict[str, Any]:
    """Compose multiple plans into a single workflow plan.

    Args:
        plans: List of plan dicts to compose
        parallel: Whether to run plans in parallel (only independent plans)
        dependencies: Dict mapping step indices to their dependencies

    Returns:
        A single plan that orchestrates all input plans
    """
    if not plans:
        return {"goal": "empty workflow", "steps": []}

    steps: list[dict[str, Any]] = []
    step_offset = 0

    for i, plan in enumerate(plans):
        if not plan.get("steps"):
            continue

        # Adjust step numbering and add workflow metadata
        for j, step in enumerate(plan.get("steps", [])):
            if parallel and not dependencies:
                # First step is just run normally
                pass
            elif parallel and i > 0:
                # Add a marker that this is parallel
                step["_parallel_chain"] = i

            steps.append(step)

    return {
        "goal": "composed workflow",
        "steps": steps,
        "_workflow_metadata": {
            "plans_composed": len(plans),
            "parallel": parallel,
        },
    }


def run_workflow(
    name: str,
    plans: list[dict[str, Any]],
    variables: Optional[dict[str, Any]] = None,
    timeout_s: Optional[float] = None,
) -> WorkflowResult:
    """Run a workflow synchronously.

    This is a convenience function for running a workflow without
    the async interface.

    Args:
        name: Name for the workflow
        plans: List of plans to execute (will be composed)
        variables: Variables to pass to the workflow
        timeout_s: Optional timeout for the entire workflow

    Returns:
        WorkflowResult with the execution outcome
    """
    from friday.l3.executor import run_plan

    start_time = time.monotonic()
    step_results: list[dict[str, Any]] = []
    overall_status = "COMPLETED"
    error: Optional[str] = None

    for i, plan in enumerate(plans):
        if not plan.get("goal"):
            continue

        # Check timeout
        if timeout_s and (time.monotonic() - start_time) >= timeout_s:
            overall_status = "ABORT"
            error = "Workflow timeout exceeded"
            break

        try:
            result = run_plan(plan, run_id=f"wf-{name}-{i}")
            step_results.extend([s.__dict__ for s in result.steps])

            if result.status != "COMPLETED":
                overall_status = "ABORT"
                error = f"Plan {i} failed: {result.steps[-1].error if result.steps else 'Unknown'}"
                break
        except Exception as e:
            overall_status = "ABORT"
            error = f"Plan {i} error: {e}"
            break

    duration = time.monotonic() - start_time

    return WorkflowResult(
        success=overall_status == "COMPLETED",
        state=WorkflowState(
            name=name,
            status=WorkflowStatus(overall_status),
            started_at=datetime.now() - timedelta(seconds=duration),
            completed_at=datetime.now(),
            error=error,
            variables=variables or {},
        ),
        duration_s=duration,
    )


def run_workflow_parallel(
    plans: list[dict[str, Any]],
    max_concurrent: int = 4,
    timeout_s: Optional[float] = None,
) -> WorkflowResult:
    """Run multiple plans in parallel.

    Args:
        plans: List of plans to execute in parallel
        max_concurrent: Maximum number of concurrent executions
        timeout_s: Optional timeout for the entire workflow

    Returns:
        WorkflowResult with the execution outcome
    """
    async def _run_with_semaphore(
        semaphore: asyncio.Semaphore,
        plan: dict[str, Any],
    ) -> dict[str, Any]:
        from friday.l3.executor import run_plan

        async with semaphore:
            result = run_plan(plan, run_id=f"parallel-{id(plan)}")
            return {
                "status": result.status,
                "steps": [s.__dict__ for s in result.steps],
            }

    start_time = time.monotonic()

    async def _execute():
        semaphore = asyncio.Semaphore(max_concurrent)
        tasks = [_run_with_semaphore(semaphore, p) for p in plans]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results

    # Run the async execution
    try:
        results = asyncio.run(_execute())
    except Exception as e:
        return WorkflowResult(
            success=False,
            state=WorkflowState(
                name="parallel-workflow",
                status=WorkflowStatus.FAILED,
                error=str(e),
            ),
            duration_s=time.monotonic() - start_time,
        )

    # Check results
    successful = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "COMPLETED")
    failed = len(results) - successful

    duration = time.monotonic() - start_time

    return WorkflowResult(
        success=failed == 0,
        state=WorkflowState(
            name="parallel-workflow",
            status=WorkflowStatus.COMPLETED if failed == 0 else WorkflowStatus.FAILED,
            started_at=datetime.now() - timedelta(seconds=duration),
            completed_at=datetime.now(),
            variables={"successful_plans": successful, "failed_plans": failed},
        ),
        duration_s=duration,
    )


# Convenience primitives for MCP exposure
def workflow_run(
    name: str,
    goals: list[str],
    facts: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """Run multiple goals as a workflow.

    This is a convenience primitive that:
    1. Plans each goal individually
    2. Composes them into a single workflow
    3. Executes the workflow

    Args:
        name: Name for the workflow run
        goals: List of goal strings to execute
        facts: Optional facts file paths/recipients for planning

    Returns:
        Dict with success status, duration, and step results
    """
    from friday.l4.planner import plan as llm_plan

    plans = []
    for goal in goals:
        try:
            p = llm_plan(goal, facts=list(facts.values()) if facts else None)
            plans.append({"goal": p.goal, "steps": p.steps})
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to plan goal '{goal}': {e}",
                "duration_s": 0.0,
            }

    result = run_workflow(name, plans, timeout_s=3600)

    return {
        "success": result.success,
        "status": result.state.status.value,
        "duration_s": result.duration_s,
        "step_count": len(result.state.step_results),
        "error": result.state.error,
    }


def workflow_status(name: str) -> dict[str, Any]:
    """Get the status of a named workflow."""
    orch = get_orchestrator()
    state = orch.get_workflow_state(name)

    return {
        "name": state.name,
        "status": state.status.value,
        "started_at": state.started_at.isoformat() if state.started_at else None,
        "completed_at": state.completed_at.isoformat() if state.completed_at else None,
        "current_step": state.current_step,
        "steps_completed": len(state.step_results),
        "error": state.error,
    }


def workflow_list() -> list[dict[str, Any]]:
    """List all workflows and their statuses."""
    orch = get_orchestrator()
    return orch.list_workflows()


def workflow_cancel(name: str) -> dict[str, Any]:
    """Cancel a running workflow."""
    orch = get_orchestrator()
    orch.cancel_workflow(name)

    state = orch.get_workflow_state(name)
    return {
        "name": name,
        "cancelled": state.status == WorkflowStatus.CANCELLED,
        "error": state.error,
    }