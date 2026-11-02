# Development log

Newest entry at the top. Each entry records what was done, the decisions made and what comes next.

## 2026-11-02: Spec 001 implemented (MetroPT-3 EDA)
**Done**
- T-001-01 to T-001-14: loader, validation, segments, labels, quality report, CLI, tests (25 passing, 98% coverage, ruff and mypy strict clean), notebook executed top to bottom, ADR-0002, dataset card.
- Ran the CLI on the real file: 1,516,948 rows, 0 nulls, 331 gaps over 60 s, 332 segments. Labels: 29,954 failure-window rows, 28,668 pre-event (24 h), 1,458,326 unknown.
- Added `pyyaml`, `types-PyYAML`, `pandas-stubs` (dev) dependencies.

**Next:** code review, PR into dev (T-001-15).
## 2026-11-02: Spec 001 approved (MetroPT-3 EDA)
**Done**
- Profiled the real CSV: 1,516,948 rows at **10 s sampling** (UCI confirms 0.1 Hz), Feb to Sep 2020, 160 gaps longer than 1 h, no nulls or duplicates.
- Verified online: MetroPT-3 is CC BY 4.0 with DOI 10.24432/C5VW3R. The paper DOI is `…9564181`; the master doc's `…9564201` is a typo. Zenodo is CC BY 4.0. FRA Form 54 is US Government Works.
- Event 2's "Maintenance 30Apr" is unverifiable as published. Labels use only the window timestamps.
- Wrote spec, plan and tasks for 001 on branch `feature/001-metropt-eda`. Installed the `analysis` extra.

**Next:** T-001-01 to T-001-15 (implementation, on Sonnet).

## 2026-11-02: Phase 0 bootstrap
**Done**
- Read master doc v1.0 and confirmed local datasets A, B and C, with checksums recorded in the dataset register.
- Created `.venv` (Python 3.12.2, uv), `pyproject.toml`, and the skeleton matching master doc §13.
- Installed Graphify 0.9.100 (`uv tool install graphifyy`), registered the Claude skill and hooks, and added the hard rule to the global CLAUDE.md.
- Added AGENTS.md, CLAUDE.md, the SDD skill, spec templates, ADRs, risk register and CI.

**Decisions** (ADR-0001): lightweight in-repo SDD; main/dev plus feature/*; raw data gitignored with checksums; MIT licence; graph gitignored.

- Pushed `main` and `dev`; CI green on both. Branch protection requires a PR and both CI checks; merged branches are auto-deleted.
- Installed the Graphify git hooks; first graph has 121 nodes and 24 communities.

**Next**
- User to provide further project details.
- Draft `specs/001-metropt-eda`.
