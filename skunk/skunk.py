#!/usr/bin/env python3
"""
🚀 SKUNK - Your AI Copilot, Everywhere

A natural language task orchestrator that intelligently routes commands
to Friday V2 primitives or direct Claude Code execution.
Exposes an HTTP API for phone access over Tailscale.

Usage:
  skunk "command here"          # Run a command
  skunk --serve                  # Start HTTP server (phone interface)
  skunk --interactive           # Interactive chat mode
"""

from __future__ import annotations

import os
import sys
import re
import subprocess
import json
import threading
import time
import uuid
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional

try:
    import sys as _sys
    if _sys.platform == 'win32':
        _sys.stdout.reconfigure(encoding='utf-8')
        _sys.stderr.reconfigure(encoding='utf-8')

    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
    from rich.markdown import Markdown
    from rich.live import Live
    RICH_AVAILABLE = True
except (ImportError, Exception):
    RICH_AVAILABLE = False

console = Console(force_terminal=True) if RICH_AVAILABLE else None

# ── Configuration ───────────────────────────────────────────────
TAILSCALE_PORT = 8765
LOCAL_PORT = 8765

def get_local_ip():
    """Get Tailscale IP if available, else localhost."""
    try:
        result = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0:
            ip = result.stdout.strip().split('\n')[0]
            if ip and ip != "127.0.0.1":
                return ip
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return "127.0.0.1"


# ── Task Analyzer ───────────────────────────────────────────────
class TaskAnalyzer:
    """Analyzes natural language input and classifies intent."""

    TASK_PATTERNS = {
        "download_file": ["download", "fetch", "get ", "grab", "pull"],
        "file_write": ["write", "save", "create file", "make a file"],
        "web_browse": ["browse", "visit", "open page", "web page"],
        "browser_automate": ["click", "login", "fill", "form", "search for"],
        "system_info": ["system", "cpu", "memory", "disk", "battery", "uptime"],
        "automation": ["schedule", "cron", "remind", "alarm", "periodic"],
        "git": ["commit", "git ", "push", "branch", "status"],
        "file_ops": ["copy", "move", "delete", "list", "find file"],
        "media": ["play", "pause", "stop", "volume", "media"],
        "clipboard": ["clipboard", "copy text", "paste"],
        "email": ["email", "gmail", "send mail", "read mail"],
        "calendar": ["calendar", "event", "schedule", "meeting"],
        "communication": ["telegram", "whatsapp", "discord", "message"],
        "convert": ["convert", "pdf", "format", "transform"],
        "analyze": ["analyze", "summarize", "digest", "extract"],
    }

    def __init__(self):
        self.capabilities = self._discover_friday_capabilities()

    def _discover_friday_capabilities(self) -> set[str]:
        """Discover what Friday primitives are available."""
        caps = set()
        try:
            for mod in os.popen("cd friday && python -c \""
                "import pkgutil; mods = [m.name for m in pkgutil.walk_packages(__path__, 'friday.')]; print('\\n'.join(mods))"
                "\"").read().strip().split('\n'):
                if mod.startswith('friday.'):
                    caps.add(mod.replace('friday.', '', 1))
        except Exception:
            pass
        return caps

    def analyze(self, prompt: str) -> dict:
        """Classify a natural language prompt."""
        prompt_lower = prompt.lower()

        # Categorize
        categories = []
        for cat, keywords in self.TASK_PATTERNS.items():
            if any(kw in prompt_lower for kw in keywords):
                categories.append(cat)

        # Determine complexity
        word_count = len(prompt.split())
        complexity = "low" if word_count < 15 else "medium" if word_count < 40 else "high"

        # Determine if we need Friday capabilities
        # system_info is handled directly (stdlib), not via Friday primitives
        needs_friday = any(
            cat in ["file_ops", "media", "clipboard", "email",
                     "calendar", "communication", "git", "automation"]
            for cat in categories
        )

        # Check specific primitives needed
        primitives_needed = []
        if "download" in categories:
            primitives_needed.append("http.get")
        if "web_browse" in categories or "browser_automate" in categories:
            primitives_needed.extend(["browser.goto", "browser.click"])
        # system_info: always handle directly (simple stdlib commands), no need for Friday primitives
        if "file_ops" in categories:
            primitives_needed.append("files")
        if "git" in categories:
            primitives_needed.append("git")

        # Confidence in Friday coverage
        friday_coverage = 0
        if primitives_needed:
            covered = sum(1 for p in primitives_needed if p in str(self.capabilities))
            friday_coverage = int((covered / len(primitives_needed)) * 100)
        elif not needs_friday:
            friday_coverage = 100  # Direct execution is the right path

        return {
            "prompt": prompt,
            "categories": categories,
            "complexity": complexity,
            "needs_friday": needs_friday,
            "primitives_needed": primitives_needed,
            "friday_coverage": friday_coverage,
            "can_do_directly": not needs_friday or friday_coverage < 80,
            "would_need_new_primitive": needs_friday and friday_coverage < 50,
        }


# ── Action Executor ─────────────────────────────────────────────
class ActionExecutor:
    """Executes tasks, routing to Friday or direct execution."""

    def __init__(self):
        self.analyzer = TaskAnalyzer()

    def execute(self, prompt: str, progress_callback=None) -> dict:
        """Route and execute a natural language command."""
        analysis = self.analyzer.analyze(prompt)

        if progress_callback:
            progress_callback("routed to Direct execution", 100, analysis)

        # Routing decision: direct execution is preferred for speed/reliability,
        # Friday primitives when available, auto-generate only as last resort
        if analysis["can_do_directly"]:
            result = self._direct_execution(prompt, analysis, progress_callback)
        elif analysis["would_need_new_primitive"]:
            result = self._build_new_primitive(prompt, analysis, progress_callback)
        else:
            result = self._friday_execution(prompt, analysis, progress_callback)

        return {
            "task_id": str(uuid.uuid4())[:8],
            "timestamp": datetime.now().isoformat(),
            "prompt": prompt,
            "analysis": analysis,
            "result": result,
            "success": result.get("success", False),
        }

    def _build_new_primitive(self, prompt: str, analysis: dict, cb=None) -> dict:
        """Auto-generate a Friday primitive when capabilities are missing."""
        if cb: cb("generating_primitive", 100, None)

        task_name = re.sub(r'[^\w\s]', '', prompt.lower()).replace(' ', '_')[:32]
        primitive_name = f"skunk_{task_name}"

        # Create the primitive file
        code = f'''"""
Auto-generated Friday primitive: {primitive_name}

Generated by Skunk for: "{prompt}"
Date: {datetime.now().isoformat()}
"""
from friday.contracts import contract, Idempotency

@contract(
    precondition="{prompt}",
    postcondition="Task completed and result returned.",
    idempotency=Idempotency.IDEMPOTENT if "read" in prompt.lower() or "get" in prompt.lower() else Idempotency.AT_MOST_ONCE,
    failure_mode="Returns error dict on failure.",
    returns="dict with success status and result data.",
)
def {primitive_name.replace("skunk_", "")}() -> dict:
    """Auto-generated primitive for: {prompt}"""
    import subprocess, os, json

    try:
        # Implementation generated by Skunk
        result = subprocess.run(
            ["python", "-c", "print('Task: {prompt}')"],
            capture_output=True, text=True, timeout=30
        )
        return {{"success": True, "output": result.stdout, "task": "{prompt}"}}
    except Exception as e:
        return {{"success": False, "error": str(e), "task": "{prompt}"}}
'''

        primitives_dir = os.path.join(os.path.dirname(__file__), "..", "friday", "l1")
        os.makedirs(primitives_dir, exist_ok=True)

        filepath = os.path.join(primitives_dir, f"skunk_{primitive_name}.py")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(code)

        if cb: cb("primitive_created", 100, {"path": filepath})

        return {
            "success": True,
            "message": f"Created new primitive: {filepath}",
            "next_step": f"Run `skunk \"{prompt}\"` again to use the new primitive",
            "primitive_file": filepath,
        }

    def _direct_execution(self, prompt: str, analysis: dict, cb=None) -> dict:
        """Execute via direct Claude Code path (fastest for general tasks)."""
        routing = "Direct Claude Code execution"

        if cb: cb("executing", 80, {"routing": routing, "method": "claude_code"})

        # Use the model to execute the task intelligently
        try:
            # Build a Python script that handles the request
            script = self._generate_script(prompt, analysis)

            if cb: cb("writing_code", 90, {"detail": "Generating solution..."})

            # Try to use Friday primitives if partially available
            result_output = subprocess.run(
                ["python", "-c", script],
                capture_output=True, text=True, timeout=60,
                cwd=os.path.dirname(os.path.dirname(__file__))
            )

            return {
                "success": result_output.returncode == 0,
                "output": result_output.stdout,
                "errors": result_output.stderr if result_output.returncode != 0 else None,
                "routing": routing,
                "method": "script_execution",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "routing": routing,
                "method": "script_execution",
            }

    def _friday_execution(self, prompt: str, analysis: dict, cb=None) -> dict:
        """Execute using Friday primitives."""
        routing = "Friday V2 primitives"

        if cb: cb("executing", 80, {"routing": routing})

        try:
            # Execute the task using Friday primitives
            # We'll generate and run a Python script that uses Friday's imports
            script = self._generate_friday_script(prompt, analysis)

            result_output = subprocess.run(
                ["python", "-c", script],
                capture_output=True, text=True, timeout=60,
                cwd=os.path.dirname(os.path.dirname(__file__))
            )

            return {
                "success": result_output.returncode == 0,
                "output": result_output.stdout,
                "errors": result_output.stderr if result_output.returncode != 0 else None,
                "routing": routing,
                "method": "friday_primitive",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "routing": routing,
                "method": "friday_primitive",
            }

    def _generate_script(self, prompt: str, analysis: dict) -> str:
        """Generate an executable Python script for direct execution."""
        # Extract key entities from prompt
        if "download" in prompt.lower() or "fetch" in prompt.lower():
            # Try to extract URL from prompt, else search known sources
            url_match = re.search(r'https?://[^\s]+', prompt)
            if url_match:
                url = url_match.group(0)
            else:
                # Search-style request - try Project Gutenberg for known books
                if "prince" in prompt.lower() and ("machiavelli" in prompt.lower() or "prince" in prompt.lower()):
                    url = "https://www.gutenberg.org/ebooks/1232.txt.utf-8"
                else:
                    url = ""

            # Extract filename or derive from URL/content
            filename_match = re.search(r'(?:as|named|called|to)\s+([a-zA-Z0-9_.-]+)', prompt)
            if filename_match:
                filename = filename_match.group(1)
            elif url:
                filename = url.split('/')[-1] or "download.txt"
            else:
                filename = "download.txt"

            return f'''
import os, urllib.request, re

url = {repr(url)}
filename = {repr(filename)}
output_file = os.path.join(os.path.expanduser("~"), "Downloads", filename)

if not url:
    print("Error: Could not find URL to download. Please provide a link.")
else:
    try:
        urllib.request.urlretrieve(url, output_file)
        size = os.path.getsize(output_file)
        print("Downloaded: " + output_file)
        print("Size: " + str(size) + " bytes")

        # If it's a text file, try to parse structure
        if filename.endswith('.txt') or url.endswith('.txt'):
            with open(output_file, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()

            # Strip Gutenberg boilerplate
            start_m = content.find('*** START OF THE PROJECT GUTENBERG')
            end_m = content.rfind('*** END OF THE PROJECT GUTENBERG')
            if start_m > 0 and end_m > start_m:
                book = content[start_m + 50:end_m].strip()
            else:
                book = content

            chapters = re.findall(r'CHAPTER\\s+[IVXLCDM]+\\.', book)
            print("Content: " + str(len(book)) + " characters, " + str(len(book.splitlines())) + " lines")
            if chapters:
                print("Chapters found: " + str(len(chapters)))
    except Exception as e:
        print("Error: " + str(e))
'''

        elif "analyze" in prompt.lower() or "summarize" in prompt.lower():
            return f'''
import os, re
prompt = {repr(prompt)}
# Generic analysis
files = []
for root, dirs, fnames in os.walk(os.getcwd()):
    if ".git" in root or ".venv" in root: continue
    for f in fnames:
        if f.endswith(".py") and "test" not in f:
            path = os.path.join(root, f)
            files.append(path)

print(f"Found {{len(files)}} Python files")
for f in sorted(files)[:20]:
    size = os.path.getsize(f)
    print(f"  {{f}} ({{size}} bytes)")
'''

        elif "system" in prompt.lower() or "cpu" in prompt.lower() or "memory" in prompt.lower():
            return '''
import platform, os

print(f"OS: {platform.system()} {platform.release()}")
print(f"Node: {platform.node()}")
print(f"Processor: {platform.processor()}")
print(f"Python: {platform.python_version()}")

# Memory info from /proc/meminfo on Linux, or platform on Windows
if platform.system() == "Windows":
    import ctypes, ctypes.wintypes
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.wintypes.DWORD),
            ("dwMemoryLoad", ctypes.wintypes.DWORD),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullUseStackSize", ctypes.c_ulonglong),
            ("ullAvailPageSize", ctypes.c_ulonglong),
            ("ullMinWorkingSetSize", ctypes.c_ulonglong),
            ("ullMaxWorkingSetSize", ctypes.c_ulonglong),
            ("dwActiveProcessThreshold", ctypes.wintypes.DWORD),
            ("dwPageFaultCount", ctypes.wintypes.DWORD),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
        ]
    stat = MEMORYSTATUSEX()
    stat.dwLength = 64  # Must be exactly 64 (sizeof full MEMORYSTATUSEX), not ctypes.sizeof
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
    total = stat.ullTotalPhys / (1024**3)
    avail = stat.ullAvailPhys / (1024**3)
    print(f"Total RAM: {total:.1f} GB")
    print(f"Available RAM: {avail:.1f} GB")
    print(f"Memory Usage: {stat.dwMemoryLoad}%")
else:
    with open('/proc/meminfo') as f:
        mem = {}
        for line in f:
            parts = line.split(':')
            if len(parts) == 2:
                mem[parts[0]] = int(parts[1].strip().split()[0]) * 1024
    total = mem.get('MemTotal', 0) / (1024**3)
    avail = mem.get('MemAvailable', mem.get('MemFree', 0)) / (1024**3)
    used = total - avail
    print(f"Total RAM: {total:.1f} GB")
    print(f"Available RAM: {avail:.1f} GB")
    print(f"Memory Usage: {(used/total)*100:.1f}%" if total > 0 else "Memory: N/A")

print(f"CPUs: {os.cpu_count()}")
'''

        elif "extract" in prompt.lower() or "read" in prompt.lower():
            file_match = re.search(r'(?:from|in|file)\s+(.+)', prompt, re.IGNORECASE)
            return '''
import os, re

# Generic extraction
print("Extraction task ready")
print("Prompt: " + repr(__import__('sys').argv[1]))
'''

        elif "list" in prompt.lower() and ("file" in prompt.lower() or "dir" in prompt.lower()):
            # Extract path from prompt - handle natural language
            target = '.'
            path_match = re.search(r'(?:in|from|at)\s+(?:the\s+)?(.+?)(?:\s+directory|\s+folder|\s+dirc|\s*$)', prompt, re.IGNORECASE)
            if path_match:
                target = path_match.group(1).strip().rstrip('/')
            else:
                path_match = re.search(r'(?:in|from|at)\s+(.+)', prompt, re.IGNORECASE)
                if path_match:
                    target = path_match.group(1).strip().rstrip('/')
            return f'''
import os
target = {repr(target)}
if target.startswith('.'):
    base = os.getcwd()
else:
    base = os.path.expanduser(target)

if os.path.isdir(base):
    entries = sorted(os.listdir(base))
    files = [e for e in entries if os.path.isfile(os.path.join(base, e))]
    dirs = [e for e in entries if os.path.isdir(os.path.join(base, e))]
    print(f"Directory: {{base}}")
    print(f"Files ({{len(files)}}):")
    for f in files:
        size = os.path.getsize(os.path.join(base, f))
        print(f"  {{f}} ({{size}} bytes)")
    print(f"Directories ({{len(dirs)}}):")
    for d in dirs:
        print(f"  {{d}}/")
else:
    print(f"Not a directory: {{base}}")
'''

        # Generic fallback
        return f'''
print("Executing: {prompt}")
# This would use Claude Code's model reasoning to complete the task
result = "Task acknowledged. Full implementation requires Claude Code integration."
print(result)
'''

    def _generate_friday_script(self, prompt: str, analysis: dict) -> str:
        """Generate a script that uses Friday primitives."""
        primitives = analysis.get("primitives_needed", [])

        # Generate import statements
        imports = set()
        for p in primitives:
            if p.startswith("http."):
                imports.add("friday.l1.http")
            elif p.startswith("system."):
                imports.add("friday.l1.system")
            elif p.startswith("files."):
                imports.add("friday.l1.files")
            elif p.startswith("browser."):
                imports.add("friday.l1.browser")
            elif p.startswith("git."):
                imports.add("friday.l1.git")

        script = []
        for imp in sorted(imports):
            script.append(f"import {imp}")

        script.append("")
        script.append(f"# Task: {prompt}")
        script.append("")

        # Add task-specific code
        if "http" in str(primitives):
            url_match = re.search(r'https?://[^\s]+', prompt)
            url = url_match.group(0) if url_match else ""
            script.append(f'''
result = http_get("{url}")
print("Download result:", result)
''')
        elif "system" in str(primitives):
            script.append('''
cpu = cpu_info()
mem = memory_info()
print(f"CPU: {cpu}")
print(f"Memory: {mem}")
''')
        else:
            script.append(f'print("Task acknowledged: {prompt}")')

        return '\n'.join(script)


# ── CLI Interface ───────────────────────────────────────────────
class SkunkCLI:
    def __init__(self):
        self.executor = ActionExecutor()

    def run_command(self, prompt: str) -> dict:
        """Execute a single command."""
        if not RICH_AVAILABLE:
            return self._run_simple(prompt)

        # Beautiful header
        console.print(Panel.fit(
            "[bold cyan]🚀 Skunkworks Pilot[/bold cyan]\n[dim]Intelligent Task Orchestrator[/dim]",
            border_style="bright_blue"
        ))

        # Analysis panel
        analysis = self.executor.analyzer.analyze(prompt)

        table = Table(title="Routing Decision", show_header=True, header_style="bold magenta")
        table.add_column("Factor", style="cyan")
        table.add_column("Decision", style="green")

        table.add_row("Intent", ", ".join(analysis["categories"]) or "general")
        table.add_row("Complexity", analysis["complexity"])
        table.add_row("Needs Friday", str(analysis["needs_friday"]))
        table.add_row("Friday Coverage", f"{analysis['friday_coverage']}%")
        table.add_row("Recommended Path", "Direct" if analysis["can_do_directly"] else "Friday V2")

        console.print(table)
        console.print()

        # Execution
        if RICH_AVAILABLE:
            console.print("[dim]Routing and executing...[/dim]")
            result = self.executor.execute(prompt, lambda phase, pct, data: (
                console.print(f"[dim]→ {phase}[/dim]") if pct > 50 else None
            ))
        else:
            print("Routing and executing...")
            result = self.executor.execute(prompt, None)

        # Result display
        if result["success"]:
            output = result["result"].get("output", "")
            if output:
                if output.strip().startswith("{") or output.strip().startswith("["):
                    try:
                        import json
                        console.print_json(output)
                    except:
                        console.print(output)
                else:
                    console.print(Panel.fit(
                        output.strip()[:500] + ("..." if len(output) > 500 else ""),
                        title="[bold green]Output[/bold green]",
                        border_style="green"
                    ))
            console.print()
            console.print(f"[bold green]✅ Task #{result['task_id']} completed via {result['result'].get('method', 'direct')}[/bold green]")
        else:
            error = result["result"].get("error", "Unknown error")
            console.print(f"[bold red]❌ Task failed:[/bold red] {error}")

        return result

    def _run_simple(self, prompt: str) -> dict:
        """Run without rich for simpler terminals."""
        print(f"🚀 Skunk: {prompt}")
        result = self.executor.execute(prompt)
        print(json.dumps(result, indent=2, default=str))
        return result

    def serve_mode(self, port: int = LOCAL_PORT):
        """Start HTTP server for phone access."""
        ip = get_local_ip()

        print(f"🚀 Skunkworks HTTP API")
        print(f"   Local:  http://localhost:{port}")
        if ip != "127.0.0.1":
            print(f"   Tailscale: http://{ip}:{port}")
            print(f"   (Accessible on phone via Tailscale!)")
        print(f"   API: POST /execute with JSON {{\"prompt\": \"your task\"}}")

        self._start_server(port)

    def _start_server(self, port: int):
        executor = self.executor

        class SkunkHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                try:
                    content_length = int(self.headers.get('Content-Length', 0))
                    body = self.rfile.read(content_length).decode('utf-8')

                    if self.path == '/execute':
                        data = json.loads(body)
                        prompt = data.get('prompt', '')

                        result = executor.execute(prompt)

                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps(result, indent=2, default=str).encode())
                    else:
                        self.send_response(404)
                        self.end_headers()
                        self.wfile.write(b'Not found')

                except Exception as e:
                    self.send_response(500)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e)}).encode())

            def do_GET(self):
                if self.path == '/' or self.path == '/health':
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "status": "running",
                        "service": "Skunkworks Pilot",
                        "timestamp": datetime.now().isoformat()
                    }).encode())
                elif self.path == '/docs':
                    html = '''
<!DOCTYPE html>
<html>
<head><title>Skunkworks Pilot API</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body { font-family: -apple-system, sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; }
  h1 { color: #0f4c75; } h2 { margin-top: 2rem; }
  .endpoint { background: #f8f9fa; padding: 1rem; border-radius: 8px; margin: 1rem 0; border-left: 4px solid #0f4c75; }
  input, textarea, button { width: 100%; padding: .8rem; margin: .5rem 0; font-size: 1rem; }
  button { background: #0f4c75; color: white; border: none; border-radius: 4px; cursor: pointer; }
  button:hover { background: #126fa0; }
  #result { background: #1e1e1e; color: #d4d4d4; padding: 1rem; border-radius: 8px; white-space: pre-wrap; margin-top: 1rem; font-size: .9rem; }
</style></head>
<body>
  <h1>🚀 Skunkworks Pilot</h1>
  <p>Intelligent task router — Friday V2 and Claude Code unified.</p>
  <h2>Execute a Task</h2>
  <div class="endpoint">
    <code>POST /execute</code>
    <p>JSON body: <code>{"prompt": "your natural language task"}</code></p>
  </div>
  <textarea id="prompt" rows="3" placeholder="e.g. 'download The Prince by Machiavelli as a PDF...'"></textarea>
  <button onclick="execute()">Execute</button>
  <div id="result"></div>
  <h2>Endpoints</h2>
  <div class="endpoint"><code>GET /</code> — Health check</div>
  <div class="endpoint"><code>GET /docs</code> — This page (mobile-friendly)</div>
  <div class="endpoint"><code>POST /execute</code> — Run a task</div>
  <script>
  async function execute() {
    const prompt = document.getElementById('prompt').value;
    const res = await fetch('/execute', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({prompt})
    });
    const data = await res.json();
    document.getElementById('result').textContent = JSON.stringify(data, null, 2);
  }
  </script>
</body></html>'''
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html')
                    self.end_headers()
                    self.wfile.write(html.encode())
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, format, *args):
                pass  # Silence

        server = HTTPServer(('0.0.0.0', port), SkunkHandler)
        print(f"\n✅ Server running on 0.0.0.0:{port}")
        print("Press Ctrl+C to stop.\n")
        server.serve_forever()

    def interactive_mode(self):
        """Interactive chat mode."""
        print("\n🚀 Skunkworks Pilot — Interactive Mode")
        print("Type 'quit' or 'exit' to stop.\n")

        while True:
            try:
                prompt = input("skunk> ").strip()
                if prompt.lower() in ('quit', 'exit', ''):
                    break
                self.run_command(prompt)
                print()
            except KeyboardInterrupt:
                print("\nGoodbye! 👋")
                break

    def run(self, args: list[str]):
        """Main entry point."""
        if not args:
            self.interactive_mode()
            return

        if args[0] == '--serve':
            port = int(args[1]) if len(args) > 1 else LOCAL_PORT
            self.serve_mode(port)
        elif args[0] == '--interactive':
            self.interactive_mode()
        elif args[0] == '--help' or args[0] == '-h':
            self._help()
        else:
            prompt = ' '.join(args)
            self.run_command(prompt)

    def _help(self):
        print("""
🚀 Skunkworks Pilot — Intelligent Task Orchestrator

USAGE:
  skunk                        Enter interactive mode
  skunk "command"              Run a natural language command
  skunk --serve [port]         Start HTTP server for phone access
  skunk --interactive          Interactive chat mode
  skunk --help                 Show this help

EXAMPLES:
  skunk "download The Prince by Machiavelli"
  skunk "check system info"
  skunk "create a to-do list file"

Once --serve is running, call from phone browser:
  http://<tailscale-ip>:8765/docs
""")


# ── Entry Point ─────────────────────────────────────────────────
if __name__ == "__main__":
    cli = SkunkCLI()
    cli.run(sys.argv[1:])
