"""One compact quality gate: lint, format, types, fast tests with coverage, safety wording.

Prints a short summary instead of full tool output and a failure signature, so the
orchestrator can spot the same failure coming back.
"""

import hashlib
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

MAX_DETAIL_LINES = 25
SCAN_DIRS = ("src", "scripts", "configs", "docs/experiments")
SCAN_SUFFIXES = (".py", ".md", ".yaml", ".yml", ".json", ".ipynb")
ALLOW_MARKER = "sdd: allow-wording"
# Wording that overstates what the system knows (CLAUDE.md safety boundary, REQ-002-07).
BANNED = re.compile(
    r"failure[s]? predicted|predict(?:s|ed)? (?:a )?failure|defect[s]? confirmed|"
    r"confirm(?:s|ed)? (?:a )?defect|collision[s]? prevented|prevent(?:s|ed)? (?:a )?collision|"
    r"\bhealthy\b",
    re.IGNORECASE,
)
_NEGATED_HEALTHY = re.compile(r"\b(?:not|never)\s+\W*healthy", re.IGNORECASE)

STEPS: tuple[tuple[str, tuple[str, ...], re.Pattern[str]], ...] = (
    ("ruff", ("-m", "ruff", "check", ".", "--output-format", "concise"), re.compile(r":\d+:")),
    ("format", ("-m", "ruff", "format", "--check", "."), re.compile(r"^Would reformat")),
    ("mypy", ("-m", "mypy"), re.compile(r"error:")),
    (
        "pytest",
        ("-m", "pytest", "-m", "not slow", "-q", "--tb=line", "--cov", "--cov-report=term"),
        re.compile(r"^(FAILED|ERROR)|Required test coverage|^E |\.py:\d+: "),
    ),
)


@dataclass(frozen=True)
class StepResult:
    name: str
    ok: bool
    detail: tuple[str, ...]


def run_step(root: Path, name: str, args: tuple[str, ...], keep: re.Pattern[str]) -> StepResult:
    proc = subprocess.run(
        [sys.executable, *args], cwd=root, capture_output=True, text=True, check=False
    )
    lines = (proc.stdout + proc.stderr).splitlines()
    detail = [line for line in lines if keep.search(line)][:MAX_DETAIL_LINES]
    if proc.returncode != 0 and not detail:
        detail = lines[-MAX_DETAIL_LINES:]
    if name == "pytest":
        detail += [line for line in lines if line.startswith("TOTAL")]
    return StepResult(name, proc.returncode == 0, tuple(detail))


def scan_wording(root: Path) -> StepResult:
    hits = []
    for top in SCAN_DIRS:
        for path in sorted((root / top).rglob("*")):
            if path.suffix not in SCAN_SUFFIXES or "sdd" in path.relative_to(root).parts[:2]:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for number, line in enumerate(text.splitlines(), start=1):
                if ALLOW_MARKER in line or not BANNED.search(line):
                    continue
                if _NEGATED_HEALTHY.search(line) and not BANNED.search(
                    _NEGATED_HEALTHY.sub("", line)
                ):
                    continue
                rel = path.relative_to(root).as_posix()
                hits.append(f"{rel}:{number}: {line.strip()[:120]}")
    return StepResult("wording", not hits, tuple(hits[:MAX_DETAIL_LINES]))


def signature(results: list[StepResult]) -> str:
    """Hash of the failing lines with line numbers and timings removed."""
    parts = []
    for result in results:
        if result.ok:
            continue
        for line in result.detail:
            if line.startswith("TOTAL"):
                continue
            line = re.sub(r":\d+(?::\d+)?", ":", line)
            parts.append(f"{result.name}|{re.sub(r'in [\d.]+s', '', line)}")
    return hashlib.sha1("\n".join(parts).encode()).hexdigest()[:12] if parts else ""


def format_report(results: list[StepResult]) -> str:
    ok = all(r.ok for r in results)
    summary = ", ".join(f"{r.name} {'ok' if r.ok else 'FAIL'}" for r in results)
    out = [f"SDD CHECK: {'PASS' if ok else 'FAIL'} ({summary})"]
    for result in results:
        coverage = [line for line in result.detail if line.startswith("TOTAL")]
        out += [f"coverage: {' '.join(line.split())}" for line in coverage]
        if not result.ok:
            out.append(f"--- {result.name}")
            out += [line for line in result.detail if not line.startswith("TOTAL")]
    if not ok:
        out.append(f"SIGNATURE: {signature(results)}")
    return "\n".join(out)


def run_all(root: Path) -> list[StepResult]:
    results = [run_step(root, name, args, keep) for name, args, keep in STEPS]
    return [*results, scan_wording(root)]
