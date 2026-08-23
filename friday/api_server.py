"""Friday API Server — remote control via HTTP + WebSocket.

Full-featured API server that exposes Friday's capabilities over HTTP
with real-time WebSocket updates for goal execution.

Endpoints:
  POST /goal              Execute a natural-language goal (L4→L3→L2→L1)
  GET  /goal/:id          Get goal status and result
  GET  /goals             List recent goals (persistent)
  GET  /status            System health
  GET  /triggers          List configured triggers
  GET  /memory?q=...      Query memory store
  GET  /logs?n=20         Recent log entries
  GET  /primitives        List registered primitives
  GET  /health            Health check
  WS   /ws                WebSocket for real-time updates

Run:
  python -m friday.api_server              (default port 8080)
  friday-api                              (console script)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Any
from urllib.parse import urlparse, parse_qs

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Ensure project root is on sys.path
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Persistent state
GOALS_FILE = PROJECT_ROOT / "var" / "state" / "api_goals.json"
GOALS_FILE.parent.mkdir(parents=True, exist_ok=True)

# Rate limiting
_rate_calls: list[float] = []
_rate_lock = threading.Lock()
RATE_LIMIT = 60  # max requests per minute

# WebSocket connections
_ws_clients: list[Any] = []
_ws_lock = threading.Lock()

# In-memory goal results (for quick access)
_goal_results: dict[str, dict] = {}
_goal_lock = threading.Lock()


def _check_rate_limit() -> bool:
    """Check if we're within the rate limit."""
    now = time.time()
    with _rate_lock:
        _rate_calls[:] = [t for t in _rate_calls if now - t < 60]
        if len(_rate_calls) >= RATE_LIMIT:
            return False
        _rate_calls.append(now)
        return True


def _check_auth(handler: BaseHTTPRequestHandler) -> bool:
    """Check API key authentication if configured."""
    api_key = os.environ.get("FRIDAY_API_KEY")
    if not api_key:
        return True
    auth = handler.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:] == api_key
    return False


def _load_goals() -> list[dict]:
    """Load goals from persistent storage."""
    try:
        if GOALS_FILE.exists():
            data = json.loads(GOALS_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
    except (OSError, ValueError):
        pass
    return []


def _save_goals(goals: list[dict]) -> None:
    """Save goals to persistent storage (atomic)."""
    try:
        tmp = GOALS_FILE.with_name(GOALS_FILE.name + ".tmp")
        tmp.write_text(json.dumps(goals, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
        os.replace(tmp, GOALS_FILE)
    except OSError:
        pass


def _add_goal(goal_data: dict) -> None:
    """Add a goal to persistent storage."""
    goals = _load_goals()
    # Remove old completed goals if too many
    if len(goals) > 100:
        goals = [g for g in goals if g.get("status") in ("running", "pending")][-50:]
    goals.insert(0, goal_data)
    _save_goals(goals)


def _update_goal(run_id: str, updates: dict) -> None:
    """Update a goal in persistent storage."""
    goals = _load_goals()
    for g in goals:
        if g.get("run_id") == run_id:
            g.update(updates)
            break
    _save_goals(goals)
    # Also update in-memory cache
    with _goal_lock:
        if run_id in _goal_results:
            _goal_results[run_id].update(updates)


def _broadcast_ws(data: dict) -> None:
    """Broadcast a message to all WebSocket clients."""
    msg = json.dumps(data, ensure_ascii=False, default=str)
    with _ws_lock:
        dead = []
        for ws in _ws_clients:
            try:
                ws.send_message(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            _ws_clients.remove(ws)


def _execute_goal_thread(goal: str, run_id: str):
    """Execute a goal in background thread."""
    _update_goal(run_id, {"status": "running", "started_at": datetime.now(UTC).isoformat()})
    _broadcast_ws({"type": "goal_update", "run_id": run_id, "status": "running"})

    try:
        from friday.observability import set_run_id
        set_run_id(run_id)

        t0 = time.monotonic()
        from friday.l4.planner import plan
        from friday.l3.executor import run_plan

        # Plan
        _broadcast_ws({"type": "goal_update", "run_id": run_id, "status": "planning"})
        p = plan(goal, run_id=run_id)

        # Execute
        _broadcast_ws({"type": "goal_update", "run_id": run_id, "status": "executing", "steps": len(p.get("steps", []))})
        exec_result = run_plan(p, run_id=run_id)
        exec_time = time.monotonic() - t0

        result = {
            "status": exec_result.status,
            "duration_s": round(exec_time, 2),
            "steps": [{
                "step_id": sr.step_id,
                "primitive": sr.primitive,
                "status": sr.status,
                "attempts": sr.attempts,
                "retries": len(sr.retry_history) if sr.retry_history else 0,
                "error": sr.error,
            } for sr in exec_result.steps],
        }
    except Exception as exc:
        result = {
            "status": "ERROR",
            "error": str(exc),
        }

    _update_goal(run_id, {
        **result,
        "completed_at": datetime.now(UTC).isoformat(),
    })
    _broadcast_ws({
        "type": "goal_update",
        "run_id": run_id,
        **result,
    })


class FridayAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Friday's API."""

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # Serve dashboard at root
        if path == "" or path == "/":
            self._serve_dashboard()
            return

        if path == "/health":
            self._json_response(200, {
                "status": "ok",
                "server": "friday-api",
                "version": "0.8.0",
                "uptime_s": int(time.time() - _start_time),
            })
            return

        # WebSocket upgrade check
        if path == "/ws":
            self._handle_websocket()
            return

        if not _check_auth(self):
            self._json_response(401, {"error": "unauthorized"})
            return

        if not _check_rate_limit():
            self._json_response(429, {"error": "rate_limited"})
            return

        # Goal by ID
        if path.startswith("/goal/"):
            goal_id = path[6:]  # Remove "/goal/"
            self._handle_goal_by_id(goal_id)
            return

        if path == "/goals":
            self._handle_goals_list()
        elif path == "/status":
            self._handle_status()
        elif path == "/triggers":
            self._handle_triggers()
        elif path == "/memory":
            params = parse_qs(parsed.query)
            query = params.get("q", [None])[0]
            self._handle_memory(query)
        elif path == "/logs":
            params = parse_qs(parsed.query)
            count = int(params.get("n", ["20"])[0])
            self._handle_logs(count)
        elif path == "/primitives":
            self._handle_primitives()
        else:
            self._json_response(404, {"error": "not_found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if not _check_auth(self):
            self._json_response(401, {"error": "unauthorized"})
            return

        if not _check_rate_limit():
            self._json_response(429, {"error": "rate_limited"})
            return

        if path == "/goal":
            self._handle_goal()
        else:
            self._json_response(404, {"error": "not_found"})

    # ---- Dashboard ----

    def _serve_dashboard(self):
        """Serve the web dashboard HTML."""
        dashboard_path = PROJECT_ROOT / "friday" / "dashboard.html"
        try:
            html = dashboard_path.read_text(encoding="utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(html.encode())
        except OSError:
            self._json_response(404, {"error": "dashboard_not_found"})

    # ---- WebSocket ----

    def _handle_websocket(self):
        """Handle WebSocket upgrade (simplified - returns error for now)."""
        self._json_response(400, {"error": "websocket_not_implemented", "message": "Use polling with GET /goal/:id"})

    # ---- Goals ----

    def _handle_goal(self):
        """Execute a natural-language goal."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, ValueError):
            self._json_response(400, {"error": "bad_request", "message": "Invalid JSON"})
            return

        goal = data.get("goal", "").strip()
        if not goal:
            self._json_response(400, {"error": "bad_request", "message": "Missing 'goal'"})
            return

        run_id = f"api-{int(time.time())}-{hashlib.md5(goal.encode()).hexdigest()[:6]}"

        goal_data = {
            "run_id": run_id,
            "goal": goal,
            "status": "pending",
            "created_at": datetime.now(UTC).isoformat(),
            "steps": [],
        }
        _add_goal(goal_data)

        thread = threading.Thread(target=_execute_goal_thread, args=(goal, run_id), daemon=True)
        thread.start()

        self._json_response(202, {
            "status": "accepted",
            "run_id": run_id,
            "goal": goal,
        })

    def _handle_goal_by_id(self, goal_id: str):
        """Get goal status and result."""
        # Check in-memory first
        with _goal_lock:
            if goal_id in _goal_results:
                self._json_response(200, _goal_results[goal_id])
                return

        # Check persistent storage
        goals = _load_goals()
        for g in goals:
            if g.get("run_id") == goal_id:
                self._json_response(200, g)
                return

        self._json_response(404, {"error": "not_found", "message": f"Goal {goal_id} not found"})

    def _handle_goals_list(self):
        """List recent goals."""
        goals = _load_goals()
        self._json_response(200, {"goals": goals[:50], "count": len(goals)})

    # ---- Status ----

    def _handle_status(self):
        """System health check."""
        try:
            from friday.contracts import REGISTRY, EXECUTOR_BLOCKED
            from friday.l4.planner import _ensure_registry
            _ensure_registry()
            total = len(REGISTRY)
            blocked = len(EXECUTOR_BLOCKED)
        except Exception:
            total, blocked = 0, 0

        triggers_total, triggers_enabled = 0, 0
        config_path = PROJECT_ROOT / "config" / "watcher.json"
        if config_path.exists():
            try:
                data = json.loads(config_path.read_text())
                triggers = data.get("triggers", [])
                triggers_total = len(triggers)
                triggers_enabled = sum(1 for t in triggers if t.get("enabled", False))
            except Exception:
                pass

        tasks_passing, tasks_total = 0, 0
        tasks_file = PROJECT_ROOT / "var" / "logs" / "tasks.jsonl"
        if tasks_file.exists():
            try:
                lines = tasks_file.read_text().strip().splitlines()
                tasks_total = len(lines)
                tasks_passing = sum(1 for l in lines if "gate6_passed\": true" in l.lower())
            except Exception:
                pass

        memory_total = 0
        try:
            from friday.l1.memory import summary as mem_summary
            s = mem_summary()
            memory_total = s.get("total", 0)
        except Exception:
            pass

        goals = _load_goals()
        running = sum(1 for g in goals if g.get("status") in ("running", "pending", "planning", "executing"))

        self._json_response(200, {
            "status": "ok",
            "version": "0.8.0",
            "primitives": {"total": total, "blocked": blocked},
            "triggers": {"enabled": triggers_enabled, "total": triggers_total},
            "tasks": {"passing": tasks_passing, "total": tasks_total},
            "memory": {"entries": memory_total},
            "goals": {"total": len(goals), "running": running},
        })

    # ---- Triggers ----

    def _handle_triggers(self):
        """List configured triggers."""
        config_path = PROJECT_ROOT / "config" / "watcher.json"
        if not config_path.exists():
            self._json_response(200, {"triggers": []})
            return

        try:
            data = json.loads(config_path.read_text())
            triggers = data.get("triggers", [])
            result = []
            for t in triggers:
                schedule = t.get("schedule", {})
                sched_type = schedule.get("type", "?")
                if sched_type == "time":
                    sched_str = f"{schedule.get('at', '?')} ({', '.join(schedule.get('days', ['daily']))})"
                elif sched_type == "file":
                    sched_str = f"file: {schedule.get('directory', '?')}/{schedule.get('name', '?')}"
                else:
                    sched_str = str(schedule)
                result.append({
                    "id": t.get("id", "unknown"),
                    "enabled": t.get("enabled", False),
                    "schedule": sched_str,
                    "goal": t.get("goal", "")[:100],
                    "notify": t.get("notify", True),
                })
            self._json_response(200, {"triggers": result})
        except Exception as e:
            self._json_response(500, {"error": "internal_error", "message": str(e)})

    # ---- Memory ----

    def _handle_memory(self, query: str | None):
        """Query memory store."""
        try:
            from friday.l1.memory import retrieve, summary as mem_summary
            if query:
                results = retrieve(query, limit=10)
                self._json_response(200, {
                    "query": query,
                    "results": [{
                        "key": r.get("key", ""),
                        "value": r.get("value", "")[:500],
                        "category": r.get("category", ""),
                        "relevance": r.get("relevance", 0),
                    } for r in results],
                })
            else:
                s = mem_summary()
                self._json_response(200, s)
        except Exception as e:
            self._json_response(500, {"error": "internal_error", "message": str(e)})

    # ---- Logs ----

    def _handle_logs(self, count: int):
        """Recent log entries."""
        log_file = Path(os.environ.get("FRIDAY_LOG_FILE", str(PROJECT_ROOT / "var" / "logs" / "friday.jsonl")))
        if not log_file.exists():
            self._json_response(200, {"logs": []})
            return

        try:
            lines = log_file.read_text(encoding="utf-8").strip().splitlines()
            recent = lines[-count:]
            logs = []
            for line in recent:
                try:
                    rec = json.loads(line)
                    logs.append({
                        "timestamp": rec.get("timestamp", "")[:19],
                        "layer": rec.get("layer", ""),
                        "primitive": rec.get("primitive", ""),
                        "result": str(rec.get("result", ""))[:200],
                        "error": rec.get("exception", ""),
                        "duration_ms": rec.get("duration_ms", 0),
                        "run_id": rec.get("run_id", ""),
                    })
                except (json.JSONDecodeError, ValueError):
                    pass
            self._json_response(200, {"logs": logs, "count": len(logs)})
        except Exception as e:
            self._json_response(500, {"error": "internal_error", "message": str(e)})

    # ---- Primitives ----

    def _handle_primitives(self):
        """List registered primitives."""
        try:
            from friday.contracts import REGISTRY, EXECUTOR_BLOCKED
            from friday.l4.planner import _ensure_registry
            _ensure_registry()
            primitives = []
            for q in sorted(REGISTRY):
                c = REGISTRY[q]
                primitives.append({
                    "name": q,
                    "idempotency": c.idempotency.value,
                    "blocked": q in EXECUTOR_BLOCKED,
                })
            self._json_response(200, {"primitives": primitives, "count": len(primitives)})
        except Exception as e:
            self._json_response(500, {"error": "internal_error", "message": str(e)})

    # ---- Helpers ----

    def _json_response(self, status: int, data: dict):
        """Send a JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, default=str).encode())

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


# Store start time
_start_time = time.time()


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Threaded HTTP server."""
    daemon_threads = True
    allow_reuse_address = True


def main(argv: list[str] | None = None):
    """Entry point for the API server."""
    parser = argparse.ArgumentParser(description="Friday API Server")
    parser.add_argument("--port", type=int, default=8080, help="Port (default: 8080)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host (default: 0.0.0.0)")
    args = parser.parse_args(argv)

    root = str(PROJECT_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)

    server = ThreadedHTTPServer((args.host, args.port), FridayAPIHandler)

    api_key = os.environ.get("FRIDAY_API_KEY")
    auth_status = "enabled" if api_key else "open"

    print(f"\n🤖 Friday API Server v0.8.0")
    print(f"   http://{args.host}:{args.port}")
    print(f"   Auth: {auth_status}")
    print(f"\n   Dashboard:  http://localhost:{args.port}/")
    print(f"   API:        http://localhost:{args.port}/status")
    print(f"   Goal:       POST http://localhost:{args.port}/goal")
    print(f"\n   Press Ctrl+C to stop\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
    finally:
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
