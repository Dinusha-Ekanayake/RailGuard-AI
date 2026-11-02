---
name: railguard-sdd
description: Spec-driven workflow for RailGuard AI. Use when starting a new roadmap phase or feature, writing spec/plan/tasks, or closing out a feature (devlog, changelog, PR to dev).
---

# RailGuard SDD workflow

## Start a feature
1. Query Graphify for context: `graphify query "<topic>"`.
2. Find the next number in `specs/`. Create `specs/<NNN>-<slug>/` from `specs/_template/`.
3. Fill in `spec.md`: problem, scope and non-goals, requirements (`REQ-<NNN>-xx`), acceptance criteria, data caveats, safety boundary. **Stop and get user approval.**
4. Write `plan.md`, then `tasks.md` (`T-<NNN>-xx`, each with its test).
5. `git switch dev && git pull && git switch -c feature/<NNN>-<slug>`.

## Implement
- TDD per task: failing test → code → refactor. Tick the task in `tasks.md`.
- Tests needing real datasets get `@pytest.mark.slow`. CI uses fixtures in `tests/fixtures/`.

## Close out
1. `pytest --cov` (≥80%), `ruff check .`, `mypy`. All must pass.
2. Code-reviewer agent; fix CRITICAL and HIGH findings.
3. Append to `docs/logs/DEVLOG.md`; update `CHANGELOG.md` under Unreleased.
4. Commit with a conventional message and **no AI attribution**. Open a PR into `dev`.
5. `graphify update .`
