"""Claude Code hooks: keep an SDD run going on Stop, auto-format Python after edits."""

import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.sdd import state as run_state
from scripts.sdd.tasks import parse_tasks

CONTINUE_REASON = (
    "SDD run for spec {spec}: {open} task(s) still open. Run "
    "`.venv/Scripts/python.exe -m scripts.sdd next` and continue the /sdd-run loop. "
    'If you need the user, run `.venv/Scripts/python.exe -m scripts.sdd halt "<reason>"` '
    "first, then ask."
)


def stop_decision(root: Path) -> dict[str, str] | None:
    """Block the stop while tasks remain, but only if a task was completed since the last block.

    No progress since the last automatic continue halts the run, so it can never loop forever.
    """
    state = run_state.load(root)
    if state is None or not state["active"] or state["halted"]:
        return None
    tasks = parse_tasks(run_state.tasks_path(root, state))
    open_count = sum(t.pending for t in tasks)
    if open_count == 0:
        return None
    done = len(tasks) - open_count
    if done <= state["last_block_done"]:
        run_state.halt(root, state, "no task completed since the last automatic continue")
        return None
    state["last_block_done"] = done
    run_state.save(root, state)
    return {
        "decision": "block",
        "reason": CONTINUE_REASON.format(spec=state["spec"], open=open_count),
    }


def format_python(payload: dict[str, Any]) -> None:
    """Format an edited ``.py`` file and sort its imports. Never fails the edit."""
    file_path = str(payload.get("tool_input", {}).get("file_path", ""))
    if not file_path.endswith(".py") or not Path(file_path).exists():
        return
    for args in (("format", file_path), ("check", "--fix", "--select", "I", file_path)):
        subprocess.run(
            [sys.executable, "-m", "ruff", *args], capture_output=True, check=False, timeout=60
        )
