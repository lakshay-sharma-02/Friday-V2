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
import base64
import hashlib
import json
import os
import struct
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

# ── WebSocket helpers ──
WS_MAGIC = b"258EAFA5-E914-47DA-95CA-5AB9FFB319F5"


def _ws_accept_key(key: str) -> str:
    """Compute Sec-WebSocket-Accept from the client's Sec-WebSocket-Key."""
    return base64.b64encode(
        hashlib.sha1((key.strip() + WS_MAGIC).encode()).digest()
    ).decode()


def _ws_send_frame(sock: Any, data: str, opcode: int = 0x1) -> None:
    """Send a single WebSocket frame (server → client, unmasked)."""
    payload = data.encode("utf-8")
    length = len(payload)
    header = bytes([0x80 | opcode])
    if length < 126:
        header += bytes([length])
    elif length < 65536:
        header += bytes([126]) + struct.pack("!H", length)
    else:
        header += bytes([127]) + struct.pack("!Q", length)
    sock.sendall(header + payload)


def _ws_read_frame(sock: Any) -> tuple[int, str] | None:
    """Read one WebSocket frame. Returns (opcode, payload_text) or None
    on close/error."""
    try:
        header = sock.recv(2)
        if len(header) < 2:
            return None
        opcode = header[0] & 0x0F
        masked = bool(header[1] & 0x80)
        length = header[1] & 0x7F
        if length == 126:
            raw = sock.recv(2)
            if len(raw) < 2:
                return None
            length = struct.unpack("!H", raw)[0]
        elif length == 127:
            raw = sock.recv(8)
            if len(raw) < 8:
                return None
            length = struct.unpack("!Q", raw)[0]
        mask_key = None
        if masked:
            mask_key = sock.recv(4)
            if len(mask_key) < 4:
                return None
        payload = b""
        while len(payload) < length:
            chunk = sock.recv(length - len(payload))
            if not chunk:
                return None
            payload += chunk
        if mask_key and mask_key:
            payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
        return opcode, payload.decode("utf-8", errors="replace")
    except Exception:
        return None


def _ws_upgrade(handler: BaseHTTPRequestHandler) -> Any | None:
    """Perform WebSocket handshake and return the raw socket.
    Returns None if the handshake fails."""
    key = handler.headers.get("Sec-WebSocket-Key", "")
    if not key:
        return None
    accept = _ws_accept_key(key)
    response = (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept}\r\n"
        "\r\n"
    )
    handler.wfile.write(response.encode())
    handler.wfile.flush()
    return handler.request


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
    """Add a goal to persistent storage AND seed the in-memory cache."""
    goals = _load_goals()
    # Remove old completed goals if too many
    if len(goals) > 100:
        goals = [g for g in goals if g.get("status") in ("running", "pending")][-50:]
    goals.insert(0, goal_data)
    _save_goals(goals)
    # Seed in-memory cache so /goal/:id polling hits it immediately
    with _goal_lock:
        _goal_results[goal_data["run_id"]] = dict(goal_data)


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
                _ws_send_frame(ws, msg)
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

        # Extract the most useful result text from the last verified step
        result_text = ""
        for sr in reversed(exec_result.steps):
            if sr.status == "VERIFIED" and sr.result is not None:
                r = sr.result
                if isinstance(r, str):
                    result_text = r
                elif isinstance(r, dict):
                    # Try common result keys
                    for k in ("text", "body", "description", "summary", "content"):
                        if k in r and isinstance(r[k], str):
                            result_text = r[k]
                            break
                    if not result_text:
                        import json as _json
                        result_text = _json.dumps(r, default=str)[:2000]
                else:
                    import json as _json
                    result_text = _json.dumps(r, default=str)[:2000]
                break

        result = {
            "status": exec_result.status,
            "duration_s": round(exec_time, 2),
            "_result": result_text[:2000],
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
            "_result": str(exc)[:500],
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

    # Auto-store goal outcomes in memory for future reference.
    # Best-effort: a memory failure must never break goal execution.
    if result.get("status") == "COMPLETED":
        try:
            from friday.l1.memory import record_success
            record_success(
                goal=goal,
                outcome=result.get("_result", "completed successfully")[:500],
                tags=["source:api"],
            )
        except Exception:
            pass
    elif result.get("status") in ("ABORT", "ERROR"):
        try:
            from friday.l1.memory import store as mem_store
            mem_store(
                key=f"failure:{goal.strip()[:80]}",
                value=f"Status: {result.get('status')}. Error: {result.get('error', 'unknown')[:300]}",
                category="context",
                tags=["type:failure", "source:api"],
            )
        except Exception:
            pass


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

        # Favicon
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
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
            category = params.get("category", [None])[0]
            tags_raw = params.get("tags", [None])[0]
            tags = [t.strip() for t in tags_raw.split(",")] if tags_raw else None
            offset = int(params.get("offset", ["0"])[0])
            limit = int(params.get("limit", ["20"])[0])
            self._handle_memory(query, category=category, tags=tags, offset=offset, limit=limit)
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
        elif path == "/memory":
            self._handle_memory_store()
        elif path == "/memory/forget":
            self._handle_memory_forget()
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
        """Handle WebSocket upgrade and push real-time goal updates."""
        sock = _ws_upgrade(self)
        if sock is None:
            self._json_response(400, {"error": "bad_websocket_handshake"})
            return
        # Register this client
        with _ws_lock:
            _ws_clients.append(sock)
        # Send current status immediately
        try:
            status_msg = {"type": "connected", "version": "0.8.0"}
            _ws_send_frame(sock, json.dumps(status_msg))
        except Exception:
            pass
        # Listen for close frames (keep connection alive)
        try:
            while True:
                frame = _ws_read_frame(sock)
                if frame is None:
                    break
                opcode, _ = frame
                if opcode == 0x8:  # close
                    break
                if opcode == 0x9:  # ping
                    _ws_send_frame(sock, "", opcode=0xA)  # pong
        except Exception:
            pass
        finally:
            with _ws_lock:
                if sock in _ws_clients:
                    _ws_clients.remove(sock)

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

    def _handle_memory(self, query: str | None, category: str | None = None, tags: list[str] | None = None, offset: int = 0, limit: int = 20):
        """Query, list, or search memory store.

        GET /memory                    — summary
        GET /memory?q=...              — search by relevance
        GET /memory?category=facts     — list by category
        GET /memory?tags=proj:friday   — list by tags (comma-separated)
        GET /memory?q=...&tags=...     — search with tag filter
        """
        try:
            from friday.l1.memory import retrieve, list_memories, summary as mem_summary
            if query:
                results = retrieve(query, category=category, tags=tags, limit=min(limit, 20))
                self._json_response(200, {
                    "query": query,
                    "category": category,
                    "tags": tags,
                    "results": [{
                        "id": r.get("id", ""),
                        "key": r.get("key", ""),
                        "value": r.get("value", "")[:500],
                        "category": r.get("category", ""),
                        "tags": r.get("tags", []),
                        "relevance": r.get("relevance", 0),
                        "access_count": r.get("access_count", 0),
                    } for r in results],
                })
            elif category or tags:
                result = list_memories(category=category, tags=tags, offset=offset, limit=limit)
                self._json_response(200, result)
            else:
                s = mem_summary()
                # Also include category list for the UI
                from friday.l1.memory import list_categories
                cats = list_categories()
                s["category_counts"] = cats.get("categories", {})
                self._json_response(200, s)
        except Exception as e:
            self._json_response(500, {"error": "internal_error", "message": str(e)})

    def _handle_memory_store(self):
        """Store a memory entry."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, ValueError):
            self._json_response(400, {"error": "bad_request", "message": "Invalid JSON"})
            return

        key = data.get("key", "").strip()
        value = data.get("value", "").strip()
        category = data.get("category", "facts")
        tags = data.get("tags")

        if not key or not value:
            self._json_response(400, {"error": "bad_request", "message": "key and value are required"})
            return

        try:
            from friday.l1.memory import store
            result = store(key=key, value=value, category=category, tags=tags)
            self._json_response(200, result)
        except Exception as e:
            self._json_response(500, {"error": "internal_error", "message": str(e)})

    def _handle_memory_forget(self):
        """Delete a memory entry."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, ValueError):
            self._json_response(400, {"error": "bad_request", "message": "Invalid JSON"})
            return

        key = data.get("key", "").strip()
        category = data.get("category")

        if not key:
            self._json_response(400, {"error": "bad_request", "message": "key is required"})
            return

        try:
            from friday.l1.memory import forget
            result = forget(key=key, category=category)
            self._json_response(200, result)
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


def _seed_goal_cache() -> None:
    """Seed the in-memory goal cache from persistent storage on startup,
    so GET /goal/:id works immediately after a restart without waiting
    for the polling loop to reload."""
    goals = _load_goals()
    with _goal_lock:
        for g in goals:
            rid = g.get("run_id")
            if rid and rid not in _goal_results:
                _goal_results[rid] = dict(g)


def main(argv: list[str] | None = None):
    """Entry point for the API server."""
    parser = argparse.ArgumentParser(description="Friday API Server")
    parser.add_argument("--port", type=int, default=8080, help="Port (default: 8080)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host (default: 0.0.0.0)")
    args = parser.parse_args(argv)

    root = str(PROJECT_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)

    # Seed in-memory goal cache from disk
    _seed_goal_cache()

    server = ThreadedHTTPServer((args.host, args.port), FridayAPIHandler)

    api_key = os.environ.get("FRIDAY_API_KEY")
    auth_status = "enabled" if api_key else "open"

    print(f"\n🤖 Friday API Server v0.8.0")
    print(f"   http://{args.host}:{args.port}")
    print(f"   Auth: {auth_status}")
    print(f"   WebSocket: ws://{args.host}:{args.port}/ws")
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
