"""Run state for ``/sdd-run`` in ``.sdd/state.json``: progress, caps and halts."""

import json
import subprocess
from pathlib import Path
from typing import Any

from scripts.sdd.tasks import (
    DONE,
    HUMAN,
    REVIEWER_MODEL,
    is_approved,
    next_group,
    parse_tasks,
    set_status,
    spec_dir,
)

STATE_FILE = Path(".sdd") / "state.json"
DEFAULT_LIMITS = {
    "max_review_rounds": 2,
    "max_fix_attempts": 3,
    "max_agent_runs": 60,
    "restart_after_tasks": 4,
}

State = dict[str, Any]


def load(root: Path) -> State | None:
    path = root / STATE_FILE
    if not path.exists():
        return None
    state: State = json.loads(path.read_text(encoding="utf-8"))
    return state


def save(root: Path, state: State) -> None:
    path = root / STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def require(root: Path) -> State:
    state = load(root)
    if state is None or not state["active"]:
        raise ValueError("no active SDD run; start one with `start <NNN>`")
    return state


def tasks_path(root: Path, state: State) -> Path:
    return root / str(state["spec_dir"]) / "tasks.md"


def current_branch(root: Path) -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise ValueError("not a git repository")
    return proc.stdout.strip()


def start(root: Path, spec: str, check_branch: bool = True) -> State:
    directory = spec_dir(root, spec)
    if not is_approved(directory):
        raise ValueError(f"{directory.name}/spec.md is not Approved; get user approval first")
    if check_branch and not current_branch(root).startswith(f"feature/{spec}-"):
        raise ValueError(f"switch to a feature/{spec}-* branch before starting the run")
    parse_tasks(directory / "tasks.md")  # fail early on a malformed table
    state: State = {
        "spec": spec,
        "spec_dir": directory.relative_to(root).as_posix(),
        "active": True,
        "halted": None,
        "limits": dict(DEFAULT_LIMITS),
        "agent_runs": 0,
        "implementer_tasks": 0,
        "last_block_done": -1,
        "tasks": {},
    }
    save(root, state)
    return state


def _task(state: State, task_id: str) -> dict[str, Any]:
    entry: dict[str, Any] = state["tasks"].setdefault(
        task_id, {"failures": [], "fix_attempts": 0, "review_rounds": 0, "assumptions": []}
    )
    return entry


def halt(root: Path, state: State, reason: str) -> State:
    state["halted"] = reason
    save(root, state)
    return state


def next_step(root: Path) -> dict[str, Any]:
    state = require(root)
    if state["halted"]:
        return {"status": "halted", "reason": state["halted"]}
    group = next_group(parse_tasks(tasks_path(root, state)))
    if not group:
        return {"status": "done", "spec": state["spec"]}
    risk = group[0].risk
    return {
        "status": "run",
        "tasks": [t.id for t in group],
        "risk": risk,
        "reviewer_model": REVIEWER_MODEL[risk],
        "human_signoff": risk == "human",
        "restart_implementer": state["implementer_tasks"] >= state["limits"]["restart_after_tasks"],
    }


def record_agent(root: Path, role: str, fresh: bool) -> State:
    state = require(root)
    state["agent_runs"] += 1
    if role == "implementer" and fresh:
        state["implementer_tasks"] = 0
    if state["agent_runs"] > state["limits"]["max_agent_runs"]:
        return halt(root, state, f"agent run cap reached ({state['limits']['max_agent_runs']})")
    save(root, state)
    return state


def record_failure(root: Path, task_id: str, signature: str) -> State:
    state = require(root)
    entry = _task(state, task_id)
    if signature in entry["failures"]:
        return halt(root, state, f"{task_id}: same check failure twice (signature {signature})")
    entry["failures"].append(signature)
    entry["fix_attempts"] += 1
    if entry["fix_attempts"] > state["limits"]["max_fix_attempts"]:
        return halt(root, state, f"{task_id}: fix attempt cap reached")
    save(root, state)
    return state


def record_review(root: Path, task_id: str, verdict: str) -> State:
    if verdict not in ("clean", "changes"):
        raise ValueError("verdict must be 'clean' or 'changes'")
    state = require(root)
    entry = _task(state, task_id)
    entry["review_rounds"] += 1
    if verdict == "changes" and entry["review_rounds"] >= state["limits"]["max_review_rounds"]:
        return halt(root, state, f"{task_id}: review round cap reached with open findings")
    save(root, state)
    return state


def record_assumption(root: Path, task_id: str, text: str) -> State:
    state = require(root)
    _task(state, task_id)["assumptions"].append(text)
    save(root, state)
    return state


def complete(root: Path, task_id: str, human: bool) -> State:
    state = require(root)
    set_status(tasks_path(root, state), task_id, HUMAN if human else DONE)
    state["implementer_tasks"] += 1
    save(root, state)
    return state


def resume(root: Path) -> State:
    """Clear a halt after the user has dealt with it; open tasks get fresh counters."""
    state = require(root)
    state["halted"] = None
    state["last_block_done"] = -1
    open_ids = {t.id for t in parse_tasks(tasks_path(root, state)) if t.pending}
    for task_id in open_ids & set(state["tasks"]):
        state["tasks"][task_id].update(failures=[], fix_attempts=0, review_rounds=0)
    save(root, state)
    return state


def stop(root: Path) -> State:
    state = require(root)
    state["active"] = False
    save(root, state)
    return state
