#!/usr/bin/env python
"""Task 10 (Gate-6-grade proof) - composite browser upload.

GOAL: "open the upload test page served by the harness, upload the file
      named 'friday_upload_test.txt' to it, and report whether the upload
      succeeded by reading the page text"
      (LLM-planned by L4, executed by L3, verified by L2, logged through L0)

First full-stack composite over browser.upload_file - proven standalone in
the remaining primitives bring-up, now driven by the executor from an LLM
plan. The harness serves a throwaway local page with a file input (a JS
change handler reports the selected filename in the page text) - the
upload's real-world effect is readable state, exactly what L2 checks read.
No external service is involved, so the run is fully unattended-safe.

The task's DoD asserts, from the raw L0 trace:
  1. every step VERIFIED and the plan used browser.goto + browser.upload_file,
  2. the upload_file result in the trace reports input_count >= 1,
  3. the final page read reports the uploaded filename ('selected:
     friday_upload_test.txt') - the upload really landed.

Side effects: opens the Playwright chromium window on a throwaway local
page and uploads a scratch test file to it.

Run:  ./.venv/bin/python -u gates/task10_browser_upload.py [run_label]
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from friday.errors import FridayError  # noqa: E402
from friday.l1 import browser  # noqa: E402
from friday.l3 import executor  # noqa: E402
from friday.l4 import planner  # noqa: E402

GOAL = (
    "open the upload test page served by the harness, upload the file named "
    "'friday_upload_test.txt' to it, and report whether the upload succeeded "
    "by reading the page text"
)

REQUIRED_PRIMITIVES = ("browser.goto", "browser.upload_file")

RUN_LABEL = sys.argv[1] if len(sys.argv) > 1 else "task10-upload"
TASK_ID = "task10"

SCRATCH = ROOT / "var" / "logs" / "upload_tmp"
TEST_FILE = SCRATCH / "friday_upload_test.txt"
UPLOAD_PAGE = """<!doctype html><html><head><meta charset="utf-8"></head><body>
<h1>friday upload test</h1>
<input type="file" id="f" />
<div id="status">no file</div>
<script>
document.getElementById('f').addEventListener('change', function(e){
  var f = e.target.files[0];
  document.getElementById('status').textContent = f ? 'selected: ' + f.name : 'no file';
});
</script>
</body></html>"""


def dump(run_id: str, label: str) -> None:
    log = ROOT / "var" / "logs" / "friday.jsonl"
    lines = [
        json.loads(l) for l in log.read_text().splitlines()
        if json.loads(l).get("run_id") == run_id
    ]
    print(f"\n=== L0 trace: {label} ({len(lines)} lines, run_id={run_id}) ===")
    for rec in lines:
        outcome = rec["result"] if rec["result"] is not None else "None"
        if rec["exception"] is not None:
            outcome = f"{outcome} EXC: {rec['exception']}"
        extra = f" extra={rec['extra']}" if rec.get("extra") else ""
        print(
            f"[{rec['timestamp']}] {rec['layer']} step={rec['step_id']} {rec['primitive']:30s} "
            f"-> {outcome}{extra}"
        )


def register_task(ok: bool) -> None:
    reg = ROOT / "var" / "logs" / "tasks.jsonl"
    reg.parent.mkdir(parents=True, exist_ok=True)
    line = {
        "task_id": TASK_ID,
        "goal": GOAL,
        "gate6_passed": bool(ok),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "proof": "gates/TASK10_UPLOAD_PROOF.md",
    }
    with reg.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line) + "\n")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _upload_input_count(records: list[dict[str, Any]]) -> int | None:
    for rec in records:
        if rec["layer"] == "L1" and rec["primitive"] == "browser.upload_file":
            res = rec.get("result")
            if isinstance(res, dict) and isinstance(res.get("input_count"), int):
                return res["input_count"]
    return None


def _last_read_page_text(records: list[dict[str, Any]]) -> str | None:
    last: str | None = None
    for rec in records:
        if rec["layer"] == "L1" and rec["primitive"] == "browser.read_page_text":
            if isinstance(rec.get("result"), str) and rec["result"]:
                last = rec["result"]
    return last


def check_dod(
    plan: dict[str, Any],
    result: executor.PlanResult | None,
    records: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    problems: list[str] = []

    # 1. the executor verified every step
    if result is None:
        problems.append("executor ABORTed before completing (see trace above)")
    elif result.status != "COMPLETED" or not all(
        s.status == "VERIFIED" for s in result.steps
    ):
        problems.append(f"not every step VERIFIED (status={result.status})")

    # 2. the plan used the upload chain
    prims = [s["primitive"] for s in plan["steps"]]
    for required in REQUIRED_PRIMITIVES:
        if required not in prims:
            problems.append(f"plan never called {required}")

    # 3. the upload really attached a file (input_count >= 1 in the trace)
    count = _upload_input_count(records)
    if count is None:
        problems.append("no browser.upload_file result with input_count in the L0 trace")
    elif count < 1:
        problems.append(f"upload_file reported input_count={count}, expected >= 1")

    # 4. the final page read reports the uploaded filename
    final = _last_read_page_text(records)
    marker = f"selected: {TEST_FILE.name}"
    if final is None:
        problems.append("no browser.read_page_text in the L0 trace")
    elif marker not in final:
        problems.append(f"final page text missing {marker!r}")

    return not problems, problems


def main() -> None:
    print("=" * 72)
    print("TASK 10 - composite browser upload (goto -> upload_file -> report)")
    print("=" * 72)
    print(f"GOAL: {GOAL!r}")

    SCRATCH.mkdir(parents=True, exist_ok=True)
    (SCRATCH / "index.html").write_text(UPLOAD_PAGE)
    TEST_FILE.write_text("friday task10 upload payload\n")

    port = _free_port()
    server = subprocess.Popen(
        ["python3", "-m", "http.server", str(port), "--bind", "127.0.0.1",
         "--directory", str(SCRATCH)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}/index.html"
    try:
        time.sleep(1.0)  # let the server come up

        loaded = planner.load_project_facts()
        file_paths = dict(loaded.file_paths)
        file_paths["upload_test"] = str(TEST_FILE)
        recipe = (
            f"The upload test page is served by the task harness at {url} "
            "(only during this task). The upload test file is at "
            "$facts.upload_test (filename friday_upload_test.txt). Recipe: "
            f"step 1 browser.goto('{url}') verified with "
            "checks.browser_has_text on {'substring': 'friday upload test'} "
            "expect true; step 2 browser.upload_file with args {'what': None, "
            "'path': '$facts.upload_test'} verified with checks.browser_has_text "
            "on {'substring': 'selected: friday_upload_test.txt'} expect true; "
            "step 3 browser.read_page_text verified with checks.browser_has_text "
            "on {'substring': 'selected: friday_upload_test.txt'} expect true - "
            "its output IS the report."
        )
        facts_override = list(loaded.facts) + [recipe]

        print("\n--- L4: LLM planning ---")
        llm_plan = planner.plan(
            GOAL,
            run_id=f"{RUN_LABEL}-plan",
            facts=facts_override,
            recipients=dict(loaded.recipients),
            file_paths=file_paths,
        )
        print("LLM-produced plan JSON:")
        print(json.dumps(llm_plan, indent=2))

        print("\n--- L3: executor runs the LLM plan (real browser upload) ---")
        result: executor.PlanResult | None = None
        try:
            result = executor.run_plan(llm_plan, run_id=f"{RUN_LABEL}-exec")
            print(f"plan status: {result.status}")
            for sr in result.steps:
                print(
                    f"  step {sr.step_id}: {sr.primitive:26s} {sr.status:12s} "
                    f"attempts={sr.attempts} verify_actual={sr.verify_actual!r}"
                )
        except FridayError as exc:
            print(f"plan status: ABORTED -> {exc}")
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
        browser.close()  # hygiene: never hold the profile

    dump(f"{RUN_LABEL}-plan", "L4 planning")
    dump(f"{RUN_LABEL}-exec", "execution (real browser upload)")

    log = ROOT / "var" / "logs" / "friday.jsonl"
    records = [
        json.loads(l) for l in log.read_text().splitlines()
        if json.loads(l).get("run_id") == f"{RUN_LABEL}-exec"
    ]
    ok, problems = check_dod(llm_plan, result, records)
    print("\n=== TASK 10 DoD (from raw L0 trace) ===")
    for p in problems:
        print(f"  FAIL: {p}")
    if ok:
        count = _upload_input_count(records)
        final = _last_read_page_text(records)
        preview = (final or "").splitlines()[-1].strip() if final else ""
        print("  OK: every step VERIFIED; plan used goto -> upload_file -> read_page_text")
        print(f"  OK: upload_file attached to {count} file input(s)")
        print(f"  OK: final page read reports the uploaded file: {preview!r}")

    register_task(ok)

    print(f"\nTASK 10: {'DONE' if ok else 'FAILED'} "
          f"(goal -> LLM plan -> upload -> verified page state)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
