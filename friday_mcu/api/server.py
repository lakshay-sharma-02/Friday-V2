"""Friday API Server — proper HTTP + WebSocket.

Uses FastAPI for production-grade API serving. Not hand-rolled.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from friday_mcu.core.events import EventBus, EventType, Event, get_bus

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


def _auth_token() -> str:
    """Bearer token required for /v1/* and /ws/events when set.

    When FRIDAY_API_TOKEN is empty the server refuses to bind anything
    but loopback, so localhost-only is the secure default.
    """
    return os.environ.get("FRIDAY_API_TOKEN", "")


def _is_loopback(host: str) -> bool:
    return host in ("127.0.0.1", "localhost", "::1")

PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ── Pydantic models (only if FastAPI is available)

if HAS_FASTAPI:
    class GoalRequest(BaseModel):
        goal: str
        context: str = ""
        timeout_s: int = 300

    class MemoryStoreRequest(BaseModel):
        key: str
        content: str
        memory_type: str = "episodic"
        tags: list[str] = []


# ── In-memory goal tracking

_goals: dict[str, dict[str, Any]] = {}
GOALS_FILE = PROJECT_ROOT / "var" / "state" / "api_goals.json"


def _load_goals() -> list[dict[str, Any]]:
    """Load goals from persistent storage."""
    try:
        if GOALS_FILE.exists():
            data = json.loads(GOALS_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
    except (OSError, ValueError):
        pass
    return []


def _save_goals(goals: list[dict[str, Any]]) -> None:
    """Save goals to persistent storage."""
    GOALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp = GOALS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(goals, ensure_ascii=False, default=str), encoding="utf-8")
        os.replace(tmp, GOALS_FILE)
    except OSError:
        pass


def _add_goal(goal_data: dict[str, Any]) -> None:
    """Add a goal to persistent storage and in-memory cache."""
    goals = _load_goals()
    if len(goals) > 100:
        goals = [g for g in goals if g.get("status") in ("running", "pending")][-50:]
    goals.insert(0, goal_data)
    _save_goals(goals)
    _goals[goal_data["run_id"]] = dict(goal_data)


def _update_goal(run_id: str, updates: dict[str, Any]) -> None:
    """Update a goal in persistent storage."""
    goals = _load_goals()
    for g in goals:
        if g.get("run_id") == run_id:
            g.update(updates)
            break
    _save_goals(goals)
    if run_id in _goals:
        _goals[run_id].update(updates)


# ── WebSocket manager

class ConnectionManager:
    """Manages WebSocket connections for real-time event streaming."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections = [ws for ws in self._connections if ws != websocket]

    async def broadcast(self, data: dict[str, Any]) -> None:
        message = json.dumps(data, default=str)
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections = [w for w in self._connections if w != ws]


_manager = ConnectionManager()


# ── App factory

def create_app() -> Any:
    """Create the FastAPI application."""
    if not HAS_FASTAPI:
        raise ImportError("FastAPI is required: pip install fastapi uvicorn")

    app = FastAPI(
        title="MCU Friday",
        description="An AI that observes, infers, acts, learns, and communicates.",
        version="1.0.0",
    )

    # CORS — wildcard origin with allow_credentials is invalid per spec and
    # only ever widens the attack surface; credentials are never used.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=json.loads(os.environ.get("FRIDAY_API_CORS", '["*"]')),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Serve dashboard
    from fastapi.responses import HTMLResponse
    dashboard_path = Path(__file__).parent / "dashboard.html"
    if dashboard_path.exists():
        @app.get("/", response_class=HTMLResponse)
        async def dashboard():
            return dashboard_path.read_text(encoding="utf-8")

    # ── Health

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "1.0.0", "timestamp": datetime.now(UTC).isoformat()}

    # ── Auth gate for every /v1 endpoint when FRIDAY_API_TOKEN is set
    @app.middleware("http")
    async def _require_token(request, call_next):
        token = _auth_token()
        if token and request.url.path.startswith("/v1/"):
            auth = request.headers.get("authorization", "")
            if auth != f"Bearer {token}":
                return JSONResponse(status_code=401, content={"detail": "unauthorized"})
        return await call_next(request)

    @app.get("/v1/status")
    async def status():
        from friday_mcu.core.contracts import REGISTRY
        from friday_mcu.core.registry import ensure_registry
        ensure_registry()
        return {
            "version": "1.0.0",
            "primitives": len(REGISTRY),
            "goals_running": sum(1 for g in _goals.values() if g.get("status") == "running"),
            "goals_total": len(_goals),
            "uptime_s": 0,  # placeholder
        }

    # ── Goals

    @app.post("/v1/goals")
    async def execute_goal(request: GoalRequest):
        import threading
        import uuid

        run_id = f"api-{int(time.time())}-{uuid.uuid4().hex[:6]}"

        goal_data = {
            "run_id": run_id,
            "goal": request.goal,
            "status": "pending",
            "created_at": datetime.now(UTC).isoformat(),
            "context": request.context,
        }
        _add_goal(goal_data)

        # Execute in background thread
        def _execute():
            _update_goal(run_id, {"status": "running", "started_at": datetime.now(UTC).isoformat()})
            try:
                from friday_mcu.brain.planner import plan
                from friday_mcu.brain.executor import run_plan
                from friday_mcu.core.observability import set_run_id

                set_run_id(run_id)
                p = plan(request.goal, run_id=run_id, timeout_s=request.timeout_s)
                result = run_plan(
                    {"goal": p.goal, "steps": p.steps},
                    run_id=run_id,
                    confidence=p.confidence,
                )
                _update_goal(run_id, {
                    "status": result.status.lower(),
                    "completed_at": datetime.now(UTC).isoformat(),
                    "steps": [
                        {"step_id": s.step_id, "primitive": s.primitive, "status": s.status}
                        for s in result.steps
                    ],
                    "confidence": p.confidence,
                })
            except Exception as exc:
                _update_goal(run_id, {
                    "status": "failed",
                    "error": str(exc)[:500],
                    "completed_at": datetime.now(UTC).isoformat(),
                })

        threading.Thread(target=_execute, daemon=True).start()

        return {"run_id": run_id, "status": "pending", "goal": request.goal}

    @app.get("/v1/goals")
    async def list_goals(limit: int = 20):
        goals = _load_goals()
        return {"goals": goals[:limit], "total": len(goals)}

    @app.get("/v1/goals/{run_id}")
    async def get_goal(run_id: str):
        if run_id in _goals:
            return _goals[run_id]
        # Try loading from file
        for g in _load_goals():
            if g.get("run_id") == run_id:
                return g
        raise HTTPException(status_code=404, detail="Goal not found")

    # ── Memory

    @app.get("/v1/memory")
    async def query_memory(q: str = "", memory_type: str = "episodic", limit: int = 10):
        from friday_mcu.memory.store import MemoryManager
        mgr = MemoryManager()
        if q:
            results = mgr.search(q, memory_type=memory_type, limit=limit)
        else:
            results = mgr.episodic.recent(limit=limit)
        return {"results": [r.to_dict() for r in results], "query": q, "type": memory_type}

    @app.post("/v1/memory")
    async def store_memory(request: MemoryStoreRequest):
        from friday_mcu.memory.store import MemoryManager
        mgr = MemoryManager()
        entry = mgr.store(request.key, request.content, memory_type=request.memory_type, tags=request.tags)
        return {"status": "stored", "key": entry.key}

    # ── Patterns

    @app.get("/v1/patterns")
    async def list_patterns(pattern_type: str | None = None):
        from friday_mcu.observer.patterns import PatternDetector
        detector = PatternDetector()
        patterns = detector.get_patterns(pattern_type)
        return {"patterns": [p.to_dict() for p in patterns], "type": pattern_type}

    # ── Phone telemetry (companion app / Tasker / WebSocket bridge)

    @app.get("/v1/phone")
    async def get_phone():
        from friday_mcu.phone import get_phone_state
        state = get_phone_state()
        return {"state": state, "paired": bool(state.get("last_seen"))}

    @app.post("/v1/phone")
    async def update_phone(payload: dict):
        from friday_mcu.phone import update_phone_state
        merged = update_phone_state(payload)
        return {"state": merged, "paired": True}

    # ── Adapters

    @app.get("/v1/adapters")
    async def list_adapters():
        from friday_mcu.adapters import list_adapters
        from friday_mcu.core.registry import ensure_registry
        ensure_registry()
        adapters = list_adapters()
        return {
            "adapters": {
                name: {
                    "name": adapter.name,
                    "capabilities": adapter.capabilities,
                    "healthy": adapter.health_check(),
                }
                for name, adapter in adapters.items()
            }
        }

    # ── WebSocket

    @app.websocket("/ws/events")
    async def websocket_events(websocket: WebSocket):
        # Auth: require ?token= to match FRIDAY_API_TOKEN when it is set
        token = _auth_token()
        if token:
            qs = websocket.query_params.get("token", "")
            if qs != token:
                await websocket.close(code=4401)
                return
        await _manager.connect(websocket)
        bus = get_bus()
        loop = asyncio.get_running_loop()

        def forward_event(event: Event):
            # run_coroutine_threadsafe is the correct cross-thread primitive:
            # loop.create_task from another thread is not thread-safe.
            asyncio.run_coroutine_threadsafe(
                _manager.broadcast(event.to_dict()), loop
            )

        bus.subscribe(None, forward_event)
        try:
            # Keep connection alive; receive loop lets the server notice drops.
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            bus.unsubscribe(None, forward_event)
            _manager.disconnect(websocket)

    return app


# ── CLI entry point

def main(argv: list[str] | None = None) -> None:
    """Run the API server."""
    import uvicorn

    app = create_app()
    port = int(os.environ.get("FRIDAY_API_PORT", "8080"))
    host = os.environ.get("FRIDAY_API_HOST", "0.0.0.0")

    # Security default: binding non-loopback without FRIDAY_API_TOKEN exposes
    # goal execution (sends, file writes, shell) and all memory to the network.
    if not _is_loopback(host) and not _auth_token():
        raise RuntimeError(
            "Refusing to bind non-loopback host without authentication. "
            "Set FRIDAY_API_TOKEN and pass `Authorization: Bearer <token>`, "
            "or bind 127.0.0.1."
        )

    print(f"MCU Friday API starting on {host}:{port}")
    print(f"   Docs: http://{host}:{port}/docs")
    print(f"   Health: http://{host}:{port}/health")
    print(f"   WebSocket: ws://{host}:{port}/ws/events")
    if _auth_token():
        print("   Auth: bearer token required (Authorization: Bearer <FRIDAY_API_TOKEN>)")
    else:
        print("   Auth: none (loopback only — set FRIDAY_API_TOKEN to expose remotely)")

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
