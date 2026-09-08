"""L1 primitive: Workflow orchestration.

Provides high-level coordination for executing multiple plans,
composing workflows, and managing complex automation scenarios.

These primitives enable:
- Running multiple goals as a coordinated workflow
- Querying workflow status and history
- Cancelling long-running workflows
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from friday.contracts import Idempotency, contract
from friday.errors import PrimitiveError


# Global workflow registry
_workflow_states: dict[str, dict[str, Any]] = {}


def _generate_workflow_id() -> str:
    """Generate a unique workflow ID."""
    return f"wf-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%f')}"


@contract(
    precondition="goals is a non-empty list of goal strings.",
    postcondition="Returns a dict with workflow execution results: success (bool), duration_s (float), and step_results (list).",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PrimitiveError when planning or execution fails entirely.",
    returns="dict: {success, duration_s, step_results, error}",
)
def run_workflow(
    goals: list[str],
    *,
    name: str | None = None,
    timeout_s: float = 3600.0,
) -> dict[str, Any]:
    """Run multiple goals as a coordinated workflow.

    Each goal is planned individually via the LLM, then executed
    sequentially. Results are tracked per-step for debugging.

    Args:
        goals: List of goal strings to execute in sequence
        name: Optional name for the workflow (auto-generated if not provided)
        timeout_s: Maximum time for the entire workflow in seconds

    Returns:
        Dict with success status, duration, step results, and any errors
    """
    if not goals:
        raise PrimitiveError("run_workflow requires a non-empty list of goals")

    from friday.l3.executor import run_plan
    from friday.l4.planner import plan as llm_plan

    workflow_id = name or _generate_workflow_id()
    start_time = datetime.now(UTC)

    workflow_state = {
        "id": workflow_id,
        "status": "running",
        "started_at": start_time,
        "goals": goals,
        "step_results": [],
        "error": None,
    }
    _workflow_states[workflow_id] = workflow_state

    all_step_results = []
    success = True
    error = None

    try:
        for i, goal in enumerate(goals):
            try:
                plan_result = llm_plan(goal, run_id=f"{workflow_id}-{i}")
            except Exception as e:
                workflow_state["status"] = "aborted"
                error = f"Failed to plan goal {i}: {e}"
                success = False
                break

            try:
                result = run_plan(
                    {"goal": plan_result.goal, "steps": plan_result.steps},
                    run_id=f"{workflow_id}-{i}",
                )
            except Exception as e:
                workflow_state["status"] = "aborted"
                error = f"Failed to execute goal {i}: {e}"
                success = False
                break

            step_result = {
                "goal": goal,
                "status": result.status,
                "steps": [s.__dict__ for s in result.steps],
            }
            all_step_results.append(step_result)

            if result.status != "COMPLETED":
                workflow_state["status"] = "failed"
                error = f"Goal {i} failed: {result.steps[-1].error if result.steps else 'Unknown'}"
                success = False
                break

    except Exception as e:
        workflow_state["status"] = "failed"
        error = str(e)
        success = False

    finally:
        end_time = datetime.now(UTC)
        duration_s = (end_time - start_time).total_seconds()

        if success and workflow_state.get("status") != "aborted":
            workflow_state["status"] = "completed"

        workflow_state["completed_at"] = end_time
        workflow_state["duration_s"] = duration_s
        workflow_state["step_results"] = all_step_results
        workflow_state["error"] = error

    return {
        "success": success,
        "duration_s": duration_s,
        "step_results": all_step_results,
        "error": error,
    }


@contract(
    precondition="name is the workflow identifier to query.",
    postcondition="Returns workflow state or None if not found.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if the workflow doesn't exist.",
    returns="dict: workflow state including status, duration, and results.",
)
def get_workflow_status(name: str) -> dict[str, Any]:
    """Get the current status of a workflow by name.

    Args:
        name: The workflow identifier

    Returns:
        Dict with workflow state: id, status, started_at, completed_at,
        duration_s, step_results, error
    """
    if name not in _workflow_states:
        raise PrimitiveError(f"Workflow '{name}' not found")

    state = _workflow_states[name]

    duration_s = 0.0
    if state.get("started_at") and state.get("completed_at"):
        duration_s = (state["completed_at"] - state["started_at"]).total_seconds()
    elif state.get("started_at"):
        duration_s = (datetime.now(UTC) - state["started_at"]).total_seconds()

    return {
        "id": state.get("id", name),
        "status": state.get("status", "unknown"),
        "started_at": state.get("started_at").isoformat() if state.get("started_at") else None,
        "completed_at": state.get("completed_at").isoformat() if state.get("completed_at") else None,
        "duration_s": duration_s,
        "step_results": state.get("step_results", []),
        "error": state.get("error"),
    }


@contract(
    precondition="name is the workflow identifier to cancel.",
    postcondition="Returns dict with cancelled status.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if the workflow doesn't exist.",
    returns="dict: {cancelled, workflow_id, status, error}",
)
def cancel_workflow(name: str) -> dict[str, Any]:
    """Cancel a running workflow.

    Note: This marks the workflow as cancelled but doesn't actually
    interrupt running execution - subsequent steps will see the
    cancellation status.

    Args:
        name: The workflow identifier to cancel

    Returns:
        Dict with cancellation status
    """
    if name not in _workflow_states:
        raise PrimitiveError(f"Workflow '{name}' not found")

    state = _workflow_states[name]
    if state.get("status") != "running":
        return {
            "cancelled": False,
            "workflow_id": name,
            "status": state.get("status"),
            "error": "Workflow is not running",
        }

    state["status"] = "cancelled"
    state["error"] = "Workflow was cancelled"

    return {
        "cancelled": True,
        "workflow_id": name,
        "status": "cancelled",
        "error": None,
    }


@contract(
    precondition="None.",
    postcondition="Returns list of all known workflow states.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="None (returns empty list on error).",
    returns="list[dict]: List of workflow states.",
)
def list_workflows() -> list[dict[str, Any]]:
    """List all known workflow states.

    Returns:
        List of workflow state dicts with id, status, duration, etc.
    """
    result = []
    for name, state in _workflow_states.items():
        duration_s = 0.0
        if state.get("started_at") and state.get("completed_at"):
            duration_s = (state["completed_at"] - state["started_at"]).total_seconds()
        elif state.get("started_at"):
            duration_s = (datetime.now(UTC) - state["started_at"]).total_seconds()

        result.append({
            "id": state.get("id", name),
            "name": name,
            "status": state.get("status", "unknown"),
            "duration_s": duration_s,
            "started_at": state.get("started_at").isoformat() if state.get("started_at") else None,
            "step_count": len(state.get("step_results", [])),
        })
    return result


@contract(
    precondition="plan1 and plan2 are valid plan dicts with 'goal' and 'steps' keys.",
    postcondition="Returns a composed plan that executes both plans sequentially.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if plans are invalid.",
    returns="dict: A valid plan dict representing the composition.",
)
def compose_plans(plan1: dict[str, Any], plan2: dict[str, Any]) -> dict[str, Any]:
    """Compose two plans into a single sequential plan.

    The resulting plan will execute plan1's steps first, then plan2's steps.
    Step numbering continues sequentially, so reference resolution works
    correctly.

    Args:
        plan1: First plan (dict with 'goal' and 'steps')
        plan2: Second plan (dict with 'goal' and 'steps')

    Returns:
        A new plan dict combining both plans
    """
    if not isinstance(plan1, dict) or not isinstance(plan2, dict):
        raise PrimitiveError("Both plans must be dictionaries")

    if "steps" not in plan1 or "steps" not in plan2:
        raise PrimitiveError("Both plans must have a 'steps' key")

    # Get the number of steps from plan1
    offset = len(plan1.get("steps", []))

    # Adjust step references in plan2
    new_steps = []

    for step in plan1.get("steps", []):
        new_steps.append(step)

    for step in plan2.get("steps", []):
        new_step = dict(step)
        # Adjust any $steps.N.result references
        if "args" in new_step:
            new_step["args"] = _adjust_step_references(new_step["args"], offset)
        if "verify" in new_step:
            new_step["verify"] = _adjust_step_references(new_step["verify"], offset)
        new_steps.append(new_step)

    return {
        "goal": f"{plan1.get('goal', 'unknown')} then {plan2.get('goal', 'unknown')}",
        "steps": new_steps,
    }


def _adjust_step_references(obj: Any, offset: int) -> Any:
    """Adjust $steps.N.result references by an offset.

    Used when composing plans to maintain correct step references.
    """
    import re

    if isinstance(obj, dict):
        return {k: _adjust_step_references(v, offset) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_adjust_step_references(item, offset) for item in obj]
    elif isinstance(obj, str):
        def repl(match):
            step_num = int(match.group(1))
            return f"$steps.{step_num + offset}.result"
        pattern = r'\$steps\.(\d+)\.result'
        return re.sub(pattern, repl, obj)
    else:
        return obj


@contract(
    precondition="plans is a list of valid plan dicts.",
    postcondition="Returns a plan that executes all input plans in parallel where possible.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if any plan is invalid.",
    returns="dict: A plan dict that orchestrates parallel execution.",
)
def parallel_run(plans: list[dict[str, Any]]) -> dict[str, Any]:
    """Create a plan that executes multiple plans in parallel.

    Each plan is executed independently. The combined plan includes
    a metadata field indicating parallelism for executor awareness.

    Args:
        plans: List of plan dicts to execute in parallel

    Returns:
        A plan dict that orchestrates parallel execution
    """
    if not plans:
        raise PrimitiveError("parallel_run requires a non-empty list of plans")

    all_steps = []
    for i, plan in enumerate(plans):
        if not isinstance(plan, dict) or "steps" not in plan:
            raise PrimitiveError(f"Plan {i} must be a dict with 'steps' key")

        for j, step in enumerate(plan.get("steps", [])):
            new_step = dict(step)
            new_step["_parallel_group"] = i
            all_steps.append(new_step)

    return {
        "goal": "parallel execution of " + str(len(plans)) + " plans",
        "steps": all_steps,
        "_parallel": True,
    }