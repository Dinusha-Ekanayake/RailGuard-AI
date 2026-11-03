"""CLI: ``.venv/Scripts/python.exe -m scripts.sdd <command>`` (run from the repo root)."""

import argparse
import io
import json
import os
import sys
from pathlib import Path

from scripts.sdd import state as run_state
from scripts.sdd.brief import write_brief
from scripts.sdd.check import format_report, run_all, signature
from scripts.sdd.hooks import format_python, stop_decision


def _root() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scripts.sdd")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="run the quality gate")
    check.add_argument("--task", help="record a failure for this task (orchestrator gate only)")
    brief = sub.add_parser("brief", help="write .sdd/briefs/<first-id>.md")
    brief.add_argument("tasks", nargs="+")
    brief.add_argument("--no-graph", action="store_true")
    start = sub.add_parser("start")
    start.add_argument("spec")
    start.add_argument("--no-branch-check", action="store_true")
    agent = sub.add_parser("agent", help="count a subagent run")
    agent.add_argument("role", choices=("planner", "implementer", "reviewer", "clerk"))
    agent.add_argument("--fresh", action="store_true")
    review = sub.add_parser("review")
    review.add_argument("task")
    review.add_argument("verdict", choices=("clean", "changes"))
    done = sub.add_parser("done")
    done.add_argument("task")
    done.add_argument("--human", action="store_true", help="mark [?]: needs human sign-off")
    assume = sub.add_parser("assume")
    assume.add_argument("task")
    assume.add_argument("text")
    sub.add_parser("halt").add_argument("reason")
    for name in ("next", "status", "resume", "stop", "hook-stop", "hook-format"):
        sub.add_parser(name)
    return parser


def _check(root: Path, task: str | None) -> int:
    results = run_all(root)
    print(format_report(results))
    if all(r.ok for r in results):
        return 0
    if task:
        state = run_state.record_failure(root, task, signature(results))
        if state["halted"]:
            print(f"HALTED: {state['halted']}")
    return 1


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):  # Windows consoles default to cp1252
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = _parser().parse_args(argv)
    root = _root()
    try:
        return _dispatch(args, root)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


def _dispatch(args: argparse.Namespace, root: Path) -> int:
    command = args.command
    if command == "check":
        return _check(root, args.task)
    if command == "hook-stop":
        decision = stop_decision(root)
        if decision:
            print(json.dumps(decision))
        return 0
    if command == "hook-format":
        format_python(json.load(sys.stdin))
        return 0
    if command == "start":
        state = run_state.start(root, args.spec, not args.no_branch_check)
    elif command == "next":
        print(json.dumps(run_state.next_step(root)))
        return 0
    elif command == "brief":
        state = run_state.require(root)
        path = write_brief(root, root / state["spec_dir"], args.tasks, not args.no_graph)
        print(path.relative_to(root).as_posix())
        return 0
    elif command == "agent":
        state = run_state.record_agent(root, args.role, args.fresh)
    elif command == "review":
        state = run_state.record_review(root, args.task, args.verdict)
    elif command == "done":
        state = run_state.complete(root, args.task, args.human)
    elif command == "assume":
        state = run_state.record_assumption(root, args.task, args.text)
    elif command == "halt":
        state = run_state.halt(root, run_state.require(root), args.reason)
    elif command == "resume":
        state = run_state.resume(root)
    elif command == "stop":
        state = run_state.stop(root)
    else:
        state = run_state.require(root)
    print(json.dumps({k: state[k] for k in ("spec", "active", "halted", "agent_runs")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
