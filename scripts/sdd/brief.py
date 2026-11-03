"""Build a short task brief so a subagent reads one small file instead of the whole spec."""

import ast
import re
import subprocess
from pathlib import Path

from scripts.sdd.tasks import REVIEWER_MODEL, Task, parse_tasks

BRIEF_DIR = Path(".sdd") / "briefs"
GRAPHIFY_BUDGET = 400
HELPER_FILES = ("tests/conftest.py", "tests/synthetic.py")
SPEC_FILES = "brief-files.txt"  # extra files for every brief of a spec, one path per line
_BACKTICKED = re.compile(r"`([^`]+)`")
_PATH = re.compile(r"(?:src|scripts|tests|configs|docs)/[\w/.-]+\.\w+")
_REQ_OR_AC = re.compile(r"^- (?:\[[ x]\] )?(?:REQ|AC)-")

RULES = """\
## Rules
- TDD: write the failing test, run it (RED), implement (GREEN), refactor. Synthetic fixtures only.
- HARD RULE (Graphify): before opening any file not named here, run `graphify explain
  "<symbol>"` or `graphify query "..."` and open only the lines it points to. Do this even
  for files you wrote earlier. If you still had to look further, say so under BRIEF GAPS.
- Gate: `.venv/Scripts/python.exe -m scripts.sdd check` must print `SDD CHECK: PASS`.
- Never commit, push, delete data or install packages. Never touch `datasets/`.
- Wording: "anomaly detected" / "alert"; never "failure predicted", "defect confirmed", "healthy".
- If the spec is ambiguous and the choice changes behaviour, stop and report it under
  QUESTIONS instead of guessing. Record smaller choices under ASSUMPTIONS.

## Report (return exactly this, nothing else)
STATUS: done | blocked
TASKS: <ids>
FILES: <changed files>
TESTS: <new test names, one line>
CHECK: <the SDD CHECK line and coverage line>
ASSUMPTIONS: <bullets or none>
QUESTIONS: <bullets or none>
BRIEF GAPS: <what was missing from this brief, or none>
"""


def _is_specific(part: str) -> bool:
    """Module paths, snake_case and CamelCase names; plain words match too many lines."""
    return "/" in part or "_" in part or re.search(r"[a-z][A-Z]", part) is not None


def _tokens(text: str) -> set[str]:
    """Identifiers and module paths named in backticks, plus their specific dotted parts."""
    tokens: set[str] = set()
    for item in _BACKTICKED.findall(text):
        tokens.add(item)
        tokens.update(part for part in re.split(r"[.:\s]", item) if _is_specific(part))
    return tokens


def _matching_lines(path: Path, tokens: set[str]) -> list[str]:
    if not path.exists() or not tokens:
        return []
    return [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if any(token in line for token in tokens)
    ]


def signatures(path: Path) -> list[str]:
    """Public top-level functions and classes with their first docstring line."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef | ast.ClassDef) or node.name.startswith("_"):
            continue
        if isinstance(node, ast.FunctionDef):
            ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
            head = f"def {node.name}({ast.unparse(node.args)}){ret}"
        else:
            head = f"class {node.name}"
        doc = (ast.get_docstring(node) or "").split("\n")[0]
        out.append(f"{head}  # {doc}" if doc else head)
    return out


def _graphify(query: str) -> str:
    try:
        proc = subprocess.run(
            ["graphify", "query", query, "--budget", str(GRAPHIFY_BUDGET)],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "(graphify unavailable)"
    lines = [line for line in proc.stdout.splitlines() if line.startswith("NODE")]
    return "\n".join(lines) or "(no graph matches)"


def _spec_files(spec_dir: Path) -> set[str]:
    """Paths a spec lists in ``brief-files.txt`` (types its plan uses but does not name)."""
    path = spec_dir / SPEC_FILES
    if not path.exists():
        return set()
    lines = (line.strip() for line in path.read_text(encoding="utf-8").splitlines())
    return {line for line in lines if line and not line.startswith("#")}


def build_brief(root: Path, spec_dir: Path, task_ids: list[str], use_graph: bool = True) -> str:
    tasks = {t.id: t for t in parse_tasks(spec_dir / "tasks.md")}
    missing = [i for i in task_ids if i not in tasks]
    if missing:
        raise ValueError(f"unknown tasks: {missing}")
    chosen: list[Task] = [tasks[i] for i in task_ids]
    tokens = set().union(*(_tokens(f"{t.text} {t.test}") for t in chosen))
    plan_lines = _matching_lines(spec_dir / "plan.md", tokens)
    spec_text = (spec_dir / "spec.md").read_text(encoding="utf-8").splitlines()
    requirements = [line for line in spec_text if _REQ_OR_AC.match(line)]

    named = set(_PATH.findall("\n".join(plan_lines)))
    # A new module should reuse what its package already has, so show its siblings too.
    siblings = {
        sibling.relative_to(root).as_posix()
        for rel in named
        if not (root / rel).exists() and (root / rel).parent.is_dir()
        for sibling in (root / rel).parent.glob("*.py")
        if sibling.name != "__init__.py"
    }
    referenced = sorted(named | siblings | set(HELPER_FILES) | _spec_files(spec_dir))
    apis = []
    for rel in referenced:
        path = root / rel
        if path.suffix == ".py" and path.exists():
            apis.append(f"### {rel}\n" + "\n".join(signatures(path) or ["(no public names)"]))
        elif not path.exists():
            apis.append(f"### {rel}\n(new file)")

    risk = chosen[0].risk
    rows = "\n".join(f"| {t.id} | {t.text} | {t.test} | {t.risk} |" for t in chosen)
    parts = [
        f"# Brief: {', '.join(task_ids)} ({spec_dir.name})",
        f"Risk: {risk}. Reviewer model: {REVIEWER_MODEL[risk]}.",
        "## Tasks\n| ID | Task | Test | Risk |\n|---|---|---|---|\n" + rows,
        "## Plan lines\n" + ("\n".join(plan_lines) or "(none matched)"),
        "## Requirements and acceptance criteria\n" + "\n".join(requirements),
        "## Existing APIs (signatures only)\n" + "\n\n".join(apis),
    ]
    if use_graph:
        query = " ".join(sorted(t for t in tokens if "/" not in t and " " not in t)[:8])
        parts.append("## Related graph nodes\n" + _graphify(query))
    parts.append(RULES)
    return "\n\n".join(parts) + "\n"


def write_brief(root: Path, spec_dir: Path, task_ids: list[str], use_graph: bool = True) -> Path:
    path = root / BRIEF_DIR / f"{task_ids[0]}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_brief(root, spec_dir, task_ids, use_graph), encoding="utf-8")
    return path
