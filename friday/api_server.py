"""Friday API Server — remote control via HTTP.

Exposes Friday's capabilities over a simple REST API so you can control
it from your phone (via Tailscale), a web dashboard, or any HTTP client.

Endpoints:
  POST /goal          Execute a natural-language goal (L4→L3→L2→L1)
  GET  /status        System health (primitives, triggers, tasks, memory)
  GET  /triggers      List configured triggers
  GET  /memory        Query memory store
  GET  /logs          Recent log entries
  GET  /primitives    List registered primitives
  GET  /health        Health check (always returns 200)

Run:
  python -m friday.api_server              (default port 8080)
  python -m friday.api_server --port 9000  (custom port)
  friday-api                              (console script)

Security:
  - By default, binds to 0.0.0.0 (all interfaces) for Tailscale access
  - Set FRIDAY_API_KEY env var to require Bearer token auth
  - Use Tailscale to keep it off the public internet
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import threading
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Any
from urllib.parse import urlparse, parse_qs

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Ensure project root is on sys.path
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Rate limiting
_rate_calls: list[float] = []
_rate_lock = threading.Lock()
RATE_LIMIT = 30  # max requests per minute


def _check_rate_limit() -> bool:
    """Check if we're within the rate limit."""
    now = time.time()
    with _rate_lock:
        # Remove entries older than 60 seconds
        _rate_calls[:] = [t for t in _rate_calls if now - t < 60]
        if len(_rate_calls) >= RATE_LIMIT:
            return False
        _rate_calls.append(now)
        return True


def _check_auth(handler: BaseHTTPRequestHandler) -> bool:
    """Check API key authentication if configured."""
    api_key = os.environ.get("FRIDAY_API_KEY")
    if not api_key:
        return True  # no auth required
    auth = handler.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:] == api_key
    return False


class FridayAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Friday's API."""

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/health":
            self._json_response(200, {
                "status": "ok",
                "server": "friday-api",
                "version": "0.8.0",
                "uptime_s": int(time.time() - _start_time),
            })
            return

        if not _check_auth(self):
            self._json_response(401, {"error": "unauthorized", "message": "Set FRIDAY_API_KEY and pass Authorization: Bearer <key>"})
            return

        if not _check_rate_limit():
            self._json_response(429, {"error": "rate_limited", "message": f"Max {RATE_LIMIT} requests per minute"})
            return

        if path == "/status":
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
            self._json_response(404, {"error": "not_found", "message": f"Unknown endpoint: {path}"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if not _check_auth(self):
            self._json_response(401, {"error": "unauthorized", "message": "Set FRIDAY_API_KEY and pass Authorization: Bearer <key>"})
            return

        if not _check_rate_limit():
            self._json_response(429, {"error": "rate_limited", "message": f"Max {RATE_LIMIT} requests per minute"})
            return

        if path == "/goal":
            self._handle_goal()
        else:
            self._json_response(404, {"error": "not_found", "message": f"Unknown endpoint: {path}"})

    # ---- handlers ----

    def _handle_status(self):
        """System health check."""
        try:
            from friday.contracts import REGISTRY, EXECUTOR_BLOCKED
            from friday.l4.planner import _ensure_registry
            _ensure_registry()
            total = len(REGISTRY)
            blocked = len(EXECUTOR_BLOCKED)
        except Exception as e:
            total, blocked = 0, 0

        # Triggers
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

        # Tasks
        tasks_passing, tasks_total = 0, 0
        tasks_file = PROJECT_ROOT / "var" / "logs" / "tasks.jsonl"
        if tasks_file.exists():
            try:
                lines = tasks_file.read_text().strip().splitlines()
                tasks_total = len(lines)
                tasks_passing = sum(1 for l in lines if "gate6_passed\": true" in l.lower())
            except Exception:
                pass

        # Memory
        memory_total = 0
        try:
            from friday.l1.memory import summary as mem_summary
            s = mem_summary()
            memory_total = s.get("total", 0)
        except Exception:
            pass

        self._json_response(200, {
            "status": "ok",
            "version": "0.8.0",
            "primitives": {"total": total, "blocked": blocked},
            "triggers": {"enabled": triggers_enabled, "total": triggers_total},
            "tasks": {"passing": tasks_passing, "total": tasks_total},
            "memory": {"entries": memory_total},
        })

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
                    "goal": t.get("goal", "")[:80],
                    "notify": t.get("notify", True),
                })
            self._json_response(200, {"triggers": result})
        except Exception as e:
            self._json_response(500, {"error": "internal_error", "message": str(e)})

    def _handle_memory(self, query: str | None):
        """Query memory store."""
        try:
            from friday.l1.memory import retrieve, summary as mem_summary
            if query:
                results = retrieve(query, limit=5)
                self._json_response(200, {
                    "query": query,
                    "results": [{
                        "key": r.get("key", ""),
                        "value": r.get("value", "")[:200],
                        "category": r.get("category", ""),
                        "relevance": r.get("relevance", 0),
                    } for r in results],
                })
            else:
                s = mem_summary()
                self._json_response(200, s)
        except Exception as e:
            self._json_response(500, {"error": "internal_error", "message": str(e)})

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
                        "result": str(rec.get("result", ""))[:100],
                        "error": rec.get("exception", ""),
                        "duration_ms": rec.get("duration_ms", 0),
                    })
                except (json.JSONDecodeError, ValueError):
                    pass
            self._json_response(200, {"logs": logs, "count": len(logs)})
        except Exception as e:
            self._json_response(500, {"error": "internal_error", "message": str(e)})

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
            self._json_response(400, {"error": "bad_request", "message": "Missing 'goal' field"})
            return

        run_id = f"api-{int(time.time())}"

        # Execute in background thread, return run_id immediately
        thread = threading.Thread(
            target=_execute_goal,
            args=(goal, run_id),
            daemon=True,
        )
        thread.start()

        self._json_response(202, {
            "status": "accepted",
            "run_id": run_id,
            "goal": goal,
            "message": f"Goal accepted. Poll GET /goal/{run_id} for result.",
        })

    def _json_response(self, status: int, data: dict):
        """Send a JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, default=str).encode())

    def log_message(self, format, *args):
        """Suppress default logging (we use L0 structured logs)."""
        pass


def _execute_goal(goal: str, run_id: str):
    """Execute a goal in background and store the result."""
    result_file = PROJECT_ROOT / "var" / "state" / f"api_result_{run_id}.json"
    result_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        from friday.observability import set_run_id
        set_run_id(run_id)

        t0 = time.monotonic()
        from friday.l4.planner import plan
        from friday.l3.executor import run_plan

        p = plan(goal, run_id=run_id)
        exec_result = run_plan(p, run_id=run_id)
        exec_time = time.monotonic() - t0

        result = {
            "status": exec_result.status,
            "run_id": run_id,
            "goal": goal,
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
            "run_id": run_id,
            "goal": goal,
            "error": str(exc),
        }

    try:
        result_file.write_text(json.dumps(result, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass

    # Auto-cleanup after 5 minutes
    def _cleanup():
        time.sleep(300)
        try:
            result_file.unlink(missing_ok=True)
        except OSError:
            pass
    threading.Thread(target=_cleanup, daemon=True).start()


# Store start time
_start_time = time.time()


class ThreadedHTTPServer(ThreadingMixIn):
    """Threaded HTTP server for handling concurrent requests."""
    daemon_threads = True


def main(argv: list[str] | None = None):
    """Entry point for the API server."""
    parser = argparse.ArgumentParser(description="Friday API Server")
    parser.add_argument("--port", type=int, default=8080, help="Port (default: 8080)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host (default: 0.0.0.0)")
    args = parser.parse_args(argv)

    # Ensure project root is on sys.path
    root = str(PROJECT_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)

    server = ThreadedHTTPServer((args.host, args.port), FridayAPIHandler)

    api_key = os.environ.get("FRIDAY_API_KEY")
    auth_status = "enabled (set FRIDAY_API_KEY)" if api_key else "disabled (open access)"

    print(f"\n🤖 Friday API Server v0.8.0")
    print(f"   Listening on http://{args.host}:{args.port}")
    print(f"   Auth: {auth_status}")
    print(f"\n   Endpoints:")
    print(f"     GET  /health       - Health check")
    print(f"     GET  /status       - System status")
    print(f"     GET  /triggers     - List triggers")
    print(f"     GET  /memory?q=... - Query memory")
    print(f"     GET  /logs?n=20    - Recent logs")
    print(f"     GET  /primitives   - List primitives")
    print(f"     POST /goal         - Execute a goal")
    print(f"\n   From your phone (via Tailscale):")
    print(f"     curl http://<tailscale-ip>:{args.port}/status")
    print(f"     curl -X POST http://<tailscale-ip>:{args.port}/goal \\")
    print(f"       -H 'Content-Type: application/json' \\")
    print(f"       -d '{{\"goal\": \"take a screenshot\"}}'")
    print(f"\n   Press Ctrl+C to stop\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
    finally:
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
