"""L5 - MCP server: Friday's primitives as Model Context Protocol tools.

Exposes every contract-registered, executor-accessible primitive as an
MCP tool over stdio (newline-delimited JSON-RPC 2.0), so any MCP client
(Claude Desktop, other agents, editors) can drive the desktop through
the SAME verified boundary the executor uses: a tool call resolves the
primitive through `friday.l3.executor._resolve_primitive` (registered
contract + not in EXECUTOR_BLOCKED + __contract__ present), so an
unproven or blocked primitive is refused exactly as a plan step would
be. L0 observability is automatic: every primitive is already wrapped
by @contract -> @observe, so each tool call lands in the standard
structured log with zero extra instrumentation.

Zero new dependencies, deliberately: the project ships on
requests/playwright/Pillow only, and the MCP stdio transport is plain
JSON-RPC 2.0 - the official `mcp` SDK (pydantic/httpx/anyio) would be
the first heavy dependency for one file. The tool surface here is the
same `build_catalog()` the planner advertises; tool schemas are derived
from the primitives' real signatures at list time, so they can never
drift from what the executor will actually accept.

Protocol implemented (MCP 2024-11-05 subset):
  initialize                -> serverInfo + capabilities.tools
  notifications/initialized -> (no response)
  ping                      -> {}
  tools/list                -> [{name, description, inputSchema}]
  tools/call                -> {content: [{type: "text", text}]} | isError

Tool names: MCP restricts names to [a-zA-Z0-9_-]; Friday's qualified
names are `module.function`, so the dot is mapped to a double
underscore (`window.list_clients` -> `window__list_clients`), reversible
because no l1 module or primitive name contains `__`. The qualified name
is kept in each tool's description.

Run:  python -m friday.mcp_server          (stdio; add to any MCP client
                                             config as a stdio server)
      friday-mcp                           (console script, same thing)
"""

from __future__ import annotations

import importlib
import inspect
import json
import sys
from enum import Enum
from pathlib import Path
from typing import Any, get_args, get_origin, get_type_hints

from friday.contracts import EXECUTOR_BLOCKED, REGISTRY
from friday.errors import FridayError

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "friday"
SERVER_VERSION = "0.8.0"

# JSON-RPC error codes (the MCP spec reuses these).
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


# ------------------------------------------------------------- registry


def _ensure_registry() -> None:
    """Import every L1 module so REGISTRY is complete (same as the
    planner's discovery - importing registers contracts, no side effects).
    Honors FRIDAY_L1_DIR so the gate tests can point at a temp dir."""
    from friday.l4.planner import _discover_l1_modules

    for name in _discover_l1_modules():
        importlib.import_module(f"friday.l1.{name}")


# ------------------------------------------------------------ schemas


def _json_type(annotation: Any) -> str | None:
    """Map a Python annotation to a JSON Schema type. None means 'any' -
    the property is declared without a type so the client passes anything
    and the primitive's own validation decides."""
    origin = get_origin(annotation)
    if origin is not None:
        if origin is list:
            return "array"
        if origin is dict:
            return "object"
        # Union/Optional: use the first non-None member's type
        for arg in get_args(annotation):
            if arg is not type(None):
                return _json_type(arg)
        return None
    if annotation is str or annotation is Path:
        return "string"
    if annotation is int:
        return "integer"
    if annotation is float:
        return "number"
    if annotation is bool:
        return "boolean"
    if annotation is dict:
        return "object"
    if annotation is list:
        return "array"
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return "string"
    return None


def _tool_name(qualified: str) -> str:
    """`module.function` -> `module__function` (MCP-safe, reversible)."""
    return qualified.replace(".", "__")


def _tool_schema(fn: Any) -> dict[str, Any]:
    """JSON Schema inputSchema derived from the primitive's real signature:
    parameters without defaults are required; types map from annotations.
    additionalProperties is false unless the primitive accepts **kwargs."""
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return {"type": "object", "additionalProperties": True}
    # Resolve string annotations (PEP 563 `from __future__ import
    # annotations` keeps them as strings on the function object) into real
    # types so Optional/Union/str/int are recognized. Fall back to the raw
    # annotation on failure so a weird annotation never crashes listing.
    try:
        hints = get_type_hints(fn)
    except Exception:
        hints = {}
    properties: dict[str, Any] = {}
    required: list[str] = []
    accepts_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
    for name, p in sig.parameters.items():
        if p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        prop: dict[str, Any] = {"title": name}
        annotation = hints.get(name, p.annotation)
        t = _json_type(annotation)
        if t is not None:
            prop["type"] = t
        if p.default is not inspect.Parameter.empty:
            prop["default"] = p.default
        properties[name] = prop
        if p.default is inspect.Parameter.empty:
            required.append(name)
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": accepts_kwargs,
    }
    if required:
        schema["required"] = required
    return schema


def _tool_description(qualified: str) -> str:
    """Contract precondition/postcondition + docstring summary - the same
    contract surface the planner advertises, so an MCP client sees the
    same guarantees an LLM plan author does."""
    c = REGISTRY[qualified]
    mod_name, _, fn_name = qualified.partition(".")
    fn = getattr(importlib.import_module(f"friday.l1.{mod_name}"), fn_name)
    doc = inspect.getdoc(fn) or ""
    lines: list[str] = [f"Friday primitive {qualified} (idempotency={c.idempotency.value})."]
    if doc:
        lines.append(doc.split("\n")[0].strip() or doc.strip())
    if c.precondition:
        lines.append(f"Precondition: {c.precondition}")
    if c.postcondition:
        lines.append(f"Postcondition: {c.postcondition}")
    if c.returns:
        lines.append(f"Returns: {c.returns}")
    return "\n".join(lines)


def list_tools() -> list[dict[str, Any]]:
    """Every executor-accessible primitive as an MCP tool. Blocked
    primitives (EXECUTOR_BLOCKED, e.g. the destructive window.shutdown)
    are never advertised - exactly as the planner's catalog hides them."""
    _ensure_registry()
    tools: list[dict[str, Any]] = []
    for qualified in sorted(REGISTRY):
        if qualified in EXECUTOR_BLOCKED:
            continue
        mod_name, _, fn_name = qualified.partition(".")
        fn = getattr(importlib.import_module(f"friday.l1.{mod_name}"), fn_name)
        tools.append(
            {
                "name": _tool_name(qualified),
                "description": _tool_description(qualified),
                "inputSchema": _tool_schema(fn),
            }
        )
    return tools


# -------------------------------------------------------------- calls


def _invoke(qualified: str, arguments: dict[str, Any]) -> Any:
    """Run one primitive through the executor's resolve boundary.

    `_resolve_primitive` refuses anything without a registered contract,
    anything in EXECUTOR_BLOCKED, and anything lacking __contract__ - the
    identical gate a plan step passes. The primitive itself is wrapped by
    @observe, so the call is L0-logged with no extra code here."""
    from friday.l3.executor import _resolve_primitive

    fn = _resolve_primitive(qualified)
    return fn(**arguments)


def _call_tool(name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    """Handle a tools/call for one tool. Returns an MCP result dict; a
    refused or failed call is an isError result (the client sees the
    message), never a protocol-level crash."""
    _ensure_registry()
    qualified = name.replace("__", ".", 1)
    try:
        result = _invoke(qualified, arguments or {})
    except (FridayError, TypeError, ValueError, KeyError) as exc:
        return {
            "content": [{"type": "text", "text": f"ERROR: {type(exc).__name__}: {exc}"}],
            "isError": True,
        }
    try:
        text = json.dumps(result, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        text = str(result)
    return {"content": [{"type": "text", "text": text}], "isError": False}


# ----------------------------------------------------------- protocol


def _error(id_: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def _result(id_: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def handle_message(line: str) -> str | None:
    """Process one inbound JSON-RPC line; return the response line, or
    None for notifications (no response) and for parse failures that
    cannot carry an id."""
    try:
        msg = json.loads(line)
    except (json.JSONDecodeError, TypeError):
        return json.dumps(_error(None, PARSE_ERROR, "parse error"))
    if not isinstance(msg, dict):
        return json.dumps(_error(None, INVALID_REQUEST, "invalid request"))
    method = msg.get("method")
    id_ = msg.get("id")
    params = msg.get("params") or {}
    # A notification has no id -> no response (spec).
    if id_ is None:
        return None
    if method == "initialize":
        return json.dumps(
            _result(
                id_,
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                },
            )
        )
    if method == "ping":
        return json.dumps(_result(id_, {}))
    if method == "tools/list":
        return json.dumps(_result(id_, {"tools": list_tools()}))
    if method == "tools/call":
        name = params.get("name")
        if not isinstance(name, str):
            return json.dumps(_error(id_, INVALID_PARAMS, "tools/call needs a 'name'"))
        args = params.get("arguments")
        if args is not None and not isinstance(args, dict):
            return json.dumps(_error(id_, INVALID_PARAMS, "'arguments' must be an object"))
        try:
            return json.dumps(_result(id_, _call_tool(name, args)))
        except Exception as exc:
            return json.dumps(
                _error(id_, INTERNAL_ERROR, f"tool call failed: {type(exc).__name__}: {exc}")
            )
    return json.dumps(_error(id_, METHOD_NOT_FOUND, f"method not found: {method}"))


def main() -> int:
    """stdio loop: read newline-delimited JSON-RPC, write responses.
    Flushes after every line so clients see responses immediately."""
    for line in sys.stdin:
        if not line.strip():
            continue
        response = handle_message(line)
        if response is not None:
            sys.stdout.write(response + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
