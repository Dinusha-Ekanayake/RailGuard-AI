import json
from pathlib import Path

import pytest

from scripts.sdd import state as run_state
from scripts.sdd.__main__ import main
from scripts.sdd.brief import build_brief, signatures
from scripts.sdd.check import StepResult, format_report, scan_wording, signature
from scripts.sdd.hooks import format_python, stop_decision
from scripts.sdd.tasks import DONE, HUMAN, TODO, next_group, parse_tasks, set_status

TASKS = """\
# Tasks 009: demo

| ID | Task | Test | Risk | Status |
|---|---|---|---|---|
| T-009-01 | `configs/x.yaml` loader | loads | low | [x] |
| T-009-02 | `features/demo.make_demo` | values | high | [ ] |
| T-009-03 | `features/demo` leakage | future rows | high | [ ] |
| T-009-04 | `models/demo.Scorer` | scores | high | [ ] |
| T-009-05 | helper | shape | low | [ ] |
| T-009-06 | real data run | files | human | [ ] |
"""
SPEC = """\
# Spec 009: demo
- **Status:** Approved (2026-11-02)
- REQ-009-01: Features use only past rows.
- [ ] AC-01: tests pass.
"""
PLAN = "| `src/demo/demo.py` | `make_demo(df)` builds features |\nunrelated line\n"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    spec = tmp_path / "specs" / "009-demo"
    spec.mkdir(parents=True)
    (spec / "tasks.md").write_text(TASKS, encoding="utf-8")
    (spec / "spec.md").write_text(SPEC, encoding="utf-8")
    (spec / "plan.md").write_text(PLAN, encoding="utf-8")
    return tmp_path


def _tasks_file(repo: Path) -> Path:
    return repo / "specs" / "009-demo" / "tasks.md"


# --- tasks.md ---------------------------------------------------------------


def test_parse_tasks_reads_risk_and_status(repo: Path) -> None:
    tasks = parse_tasks(_tasks_file(repo))
    assert [t.risk for t in tasks] == ["low", "high", "high", "high", "low", "human"]
    assert tasks[0].status == DONE and tasks[1].pending


def test_parse_tasks_defaults_risk_without_column(tmp_path: Path) -> None:
    path = tmp_path / "tasks.md"
    path.write_text(
        "| ID | Task | Test | Status |\n|---|---|---|---|\n| T-001-01 | a | b | [ ] |\n"
    )
    assert parse_tasks(path)[0].risk == "low"


def test_parse_tasks_rejects_unknown_risk(tmp_path: Path) -> None:
    path = tmp_path / "tasks.md"
    path.write_text("| ID | Task | Test | Risk | Status |\n| T-001-01 | a | b | huge | [ ] |\n")
    with pytest.raises(ValueError, match="risk"):
        parse_tasks(path)


def test_set_status_changes_only_that_row(repo: Path) -> None:
    path = _tasks_file(repo)
    set_status(path, "T-009-02", HUMAN)
    statuses = [t.status for t in parse_tasks(path)]
    assert statuses == [DONE, HUMAN, TODO, TODO, TODO, TODO]
    with pytest.raises(ValueError, match="not found"):
        set_status(path, "T-009-99", DONE)


def test_next_group_caps_high_risk_and_isolates_human(repo: Path) -> None:
    tasks = parse_tasks(_tasks_file(repo))
    assert [t.id for t in next_group(tasks)] == ["T-009-02", "T-009-03"]
    rest = [t for t in tasks if t.id not in ("T-009-02", "T-009-03", "T-009-04", "T-009-05")]
    assert [t.id for t in next_group(rest)] == ["T-009-06"]


# --- run state --------------------------------------------------------------


def test_start_refuses_unapproved_spec(repo: Path) -> None:
    spec = repo / "specs" / "009-demo" / "spec.md"
    spec.write_text(SPEC.replace("Approved", "Draft"), encoding="utf-8")
    with pytest.raises(ValueError, match="not Approved"):
        run_state.start(repo, "009", check_branch=False)


def test_next_step_reports_group_and_reviewer(repo: Path) -> None:
    run_state.start(repo, "009", check_branch=False)
    step = run_state.next_step(repo)
    assert step["tasks"] == ["T-009-02", "T-009-03"]
    assert step["reviewer_model"] == "opus"
    assert step["restart_implementer"] is False


def test_same_failure_twice_halts(repo: Path) -> None:
    run_state.start(repo, "009", check_branch=False)
    assert run_state.record_failure(repo, "T-009-02", "abc")["halted"] is None
    state = run_state.record_failure(repo, "T-009-02", "abc")
    assert "same check failure twice" in state["halted"]
    assert run_state.next_step(repo)["status"] == "halted"


def test_fix_attempt_cap_halts(repo: Path) -> None:
    run_state.start(repo, "009", check_branch=False)
    for sig in ("a", "b", "c"):
        assert run_state.record_failure(repo, "T-009-02", sig)["halted"] is None
    assert "fix attempt cap" in run_state.record_failure(repo, "T-009-02", "d")["halted"]


def test_review_round_cap_halts_only_with_open_findings(repo: Path) -> None:
    run_state.start(repo, "009", check_branch=False)
    assert run_state.record_review(repo, "T-009-02", "changes")["halted"] is None
    assert "review round cap" in run_state.record_review(repo, "T-009-02", "changes")["halted"]
    run_state.resume(repo)
    assert run_state.record_review(repo, "T-009-02", "clean")["halted"] is None


def test_agent_run_cap_and_restart_flag(repo: Path) -> None:
    state = run_state.start(repo, "009", check_branch=False)
    state["limits"]["max_agent_runs"] = 1
    state["limits"]["restart_after_tasks"] = 1
    run_state.save(repo, state)
    run_state.complete(repo, "T-009-02", human=False)
    assert run_state.next_step(repo)["restart_implementer"] is True
    assert run_state.record_agent(repo, "implementer", fresh=True)["halted"] is None
    assert run_state.next_step(repo)["restart_implementer"] is False
    assert "agent run cap" in run_state.record_agent(repo, "reviewer", fresh=False)["halted"]


def test_resume_clears_halt_and_counters(repo: Path) -> None:
    run_state.start(repo, "009", check_branch=False)
    run_state.record_failure(repo, "T-009-02", "abc")
    run_state.record_failure(repo, "T-009-02", "abc")
    state = run_state.resume(repo)
    assert state["halted"] is None
    assert state["tasks"]["T-009-02"]["failures"] == []


def test_complete_human_marks_question(repo: Path) -> None:
    run_state.start(repo, "009", check_branch=False)
    run_state.complete(repo, "T-009-06", human=True)
    assert parse_tasks(_tasks_file(repo))[-1].status == HUMAN


def test_assumptions_and_stop(repo: Path) -> None:
    run_state.start(repo, "009", check_branch=False)
    run_state.record_assumption(repo, "T-009-02", "used right-closed windows")
    assert run_state.load(repo)["tasks"]["T-009-02"]["assumptions"] == [  # type: ignore[index]
        "used right-closed windows"
    ]
    run_state.stop(repo)
    with pytest.raises(ValueError, match="no active"):
        run_state.next_step(repo)


# --- stop hook --------------------------------------------------------------


def test_stop_hook_inactive_without_run(repo: Path) -> None:
    assert stop_decision(repo) is None


def test_stop_hook_blocks_then_halts_without_progress(repo: Path) -> None:
    run_state.start(repo, "009", check_branch=False)
    first = stop_decision(repo)
    assert first is not None and first["decision"] == "block"
    assert stop_decision(repo) is None
    assert "no task completed" in run_state.load(repo)["halted"]  # type: ignore[index]


def test_stop_hook_keeps_blocking_while_progress_is_made(repo: Path) -> None:
    run_state.start(repo, "009", check_branch=False)
    assert stop_decision(repo) is not None
    run_state.complete(repo, "T-009-02", human=False)
    assert stop_decision(repo) is not None


def test_stop_hook_allows_stop_when_all_done(repo: Path) -> None:
    run_state.start(repo, "009", check_branch=False)
    for task in parse_tasks(_tasks_file(repo)):
        if task.pending:
            run_state.complete(repo, task.id, human=False)
    assert stop_decision(repo) is None


def test_format_hook_ignores_non_python(tmp_path: Path) -> None:
    target = tmp_path / "notes.md"
    target.write_text("x  =  1\n")
    format_python({"tool_input": {"file_path": str(target)}})
    assert target.read_text() == "x  =  1\n"


def test_format_hook_formats_python(tmp_path: Path) -> None:
    target = tmp_path / "mod.py"
    target.write_text("x  =  1\n")
    format_python({"tool_input": {"file_path": str(target)}})
    assert target.read_text() == "x = 1\n"


# --- brief ------------------------------------------------------------------


def test_brief_contains_only_relevant_context(repo: Path) -> None:
    brief = build_brief(repo, repo / "specs" / "009-demo", ["T-009-02"], use_graph=False)
    assert "T-009-02" in brief and "T-009-04" not in brief
    assert "make_demo(df)" in brief and "unrelated line" not in brief
    assert "REQ-009-01" in brief and "AC-01" in brief
    assert "### src/demo/demo.py\n(new file)" in brief
    assert "STATUS: done | blocked" in brief


def test_brief_rejects_unknown_task(repo: Path) -> None:
    with pytest.raises(ValueError, match="unknown"):
        build_brief(repo, repo / "specs" / "009-demo", ["T-009-42"], use_graph=False)


def test_signatures_lists_public_names(tmp_path: Path) -> None:
    module = tmp_path / "m.py"
    module.write_text(
        'def f(a: int) -> int:\n    """Add one."""\n    return a + 1\n\n'
        "def _hidden() -> None: ...\n\nclass C: ...\n"
    )
    assert signatures(module) == ["def f(a: int) -> int  # Add one.", "class C"]


# --- check ------------------------------------------------------------------


def test_wording_scan_flags_overclaims_and_allows_negation(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.py").write_text(
        '"""Rows are unknown, never healthy."""\nMSG = "failure predicted"\n'
        'OK = "healthy"  # sdd: allow-wording\n'
    )
    result = scan_wording(tmp_path)
    assert not result.ok
    assert result.detail == ('src/a.py:2: MSG = "failure predicted"',)


def test_wording_scan_passes_on_clean_tree(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text('MSG = "anomaly detected"\n')
    assert scan_wording(tmp_path).ok


def test_signature_ignores_line_numbers_and_timings() -> None:
    a = [StepResult("mypy", False, ("src/x.py:10: error: bad",))]
    b = [StepResult("mypy", False, ("src/x.py:12: error: bad",))]
    c = [StepResult("mypy", False, ("src/x.py:12: error: other",))]
    assert signature(a) == signature(b) != signature(c)
    assert signature([StepResult("ruff", True, ())]) == ""


def test_report_is_compact() -> None:
    results = [
        StepResult("ruff", True, ()),
        StepResult("pytest", False, ("FAILED tests/t.py::test_x", "TOTAL 100 5 95%")),
    ]
    report = format_report(results).splitlines()
    assert report[0] == "SDD CHECK: FAIL (ruff ok, pytest FAIL)"
    assert "coverage: TOTAL 100 5 95%" in report
    assert report[-1].startswith("SIGNATURE: ")


# --- CLI --------------------------------------------------------------------


def test_cli_round_trip(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(repo))
    assert main(["start", "009"]) == 2  # tmp_path is not a git repo
    assert main(["start", "009", "--no-branch-check"]) == 0
    assert main(["next"]) == 0
    step = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert step["tasks"] == ["T-009-02", "T-009-03"]
    assert main(["brief", "T-009-02", "--no-graph"]) == 0
    assert (repo / ".sdd" / "briefs" / "T-009-02.md").exists()
    assert main(["done", "T-009-02"]) == 0
    assert main(["halt", "need user"]) == 0
    capsys.readouterr()
    assert main(["hook-stop"]) == 0
    assert capsys.readouterr().out == ""  # halted runs never block a stop
    assert main(["start", "777"]) == 2


def test_start_requires_feature_branch(repo: Path) -> None:
    with pytest.raises(ValueError, match="git"):
        run_state.start(repo, "009")


def test_brief_shows_sibling_modules_for_new_files(repo: Path) -> None:
    package = repo / "src" / "demo"
    package.mkdir(parents=True)
    (package / "config.py").write_text("class DemoConfig: ...\n")
    brief = build_brief(repo, repo / "specs" / "009-demo", ["T-009-02"], use_graph=False)
    assert "### src/demo/config.py\nclass DemoConfig" in brief


def test_brief_ignores_plain_words(repo: Path) -> None:
    plan = repo / "specs" / "009-demo" / "plan.md"
    plan.write_text(PLAN + "features are great\n", encoding="utf-8")
    brief = build_brief(repo, repo / "specs" / "009-demo", ["T-009-02"], use_graph=False)
    assert "features are great" not in brief


def test_brief_includes_files_listed_by_the_spec(repo: Path) -> None:
    (repo / "src" / "demo").mkdir(parents=True)
    (repo / "src" / "demo" / "types.py").write_text("class FailureWindow: ...\n")
    spec = repo / "specs" / "009-demo"
    (spec / "brief-files.txt").write_text("# comment\nsrc/demo/types.py\n\n")
    brief = build_brief(repo, spec, ["T-009-02"], use_graph=False)
    assert "### src/demo/types.py\nclass FailureWindow" in brief
