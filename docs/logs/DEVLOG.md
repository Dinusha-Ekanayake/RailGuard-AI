# Development log

Newest entry at the top. Each entry records what was done, the decisions made and what comes next.

## 2026-11-03: Spec 002 implemented and EXP-002 run (MetroPT-3 baselines)
**Done**
- T-002-01 to T-002-12: experiment config loader, synthetic test frame, trailing window features (60 s, 5 min, 15 min, 60 min on a 60 s grid), chronological split and fit mask, E0 robust z-score, E1 Isolation Forest, alert episodes, event metrics, threshold selection, experiment runner and `scripts/run_exp002.py`.
- Ran EXP-002 on the real CSV at commit `a16c5de`, then re-ran it at `f731072` (`git_dirty: false`, 18 s) after that commit added the segmentation gap, windows file hash and row counts to the provenance. The committed outputs are from the `f731072` run. Outputs in `docs/experiments/exp002/`, card in `docs/experiments/EXP-002-metropt-baselines.md` (status: draft for sign-off).
- Results as event counts (2 validation events, 2 test events): E0 (`all`) detected 1 of 2 on validation and 2 of 2 on test, but its test rate of alerts outside documented windows (0.0743 per operating hour) is above the 0.0417 budget. E1 (`all`) detected 2 of 2 on both splits, within budget (0.0118 validation, 0.0058 test). E1 alerts were at or after window onset for three events. Dropping `Oil_level` left E0 unchanged and moved E1 only slightly.
- Added SDD automation tooling: `scripts/sdd/`, `.claude/agents/`, `.claude/skills/sdd-run/`.

**Decisions**
- E1 (`all`) is the primary comparator because it stayed within budget on both splits; E0 stays as the interpretable reference.
- Threshold chosen on validation only; test metrics reported once with the frozen threshold.
- Results are descriptive counts from 4 events on one compressor. No precursor or prediction claim is made.
- `Oil_level` kept as a feature, with a `no_oil_level` variant so no result depends on it.

**Next**
- User sign-off on T-002-13 (slow end-to-end test), T-002-14 (commit `docs/experiments/exp002/`) and T-002-15 (experiment card review).
- Record pytest, ruff and mypy results for the PR (not yet recorded in this entry).
- Code review, `graphify update .`, PR into dev (T-002-16).

## 2026-11-02: Spec 002 approved (MetroPT-3 baselines)
**Done**
- PR #2 (spec 001) merged into dev; spec 001 marked Implemented.
- Wrote and approved spec, plan and tasks for 002: E0 robust z-score and E1 Isolation Forest, event-level evaluation.
- Added `docs/master-doc-errata.md` (sampling, windows, DOI, date span) and risks R10 to R12.

**Decisions**: MLflow deferred to the Docker Compose phase; chronological split (fit Feb to 10 Apr, validation events 1 and 2, test events 3 and 4); alert budget of 1 per 24 operating hours; `Oil_level` checked by running with and without it.

**Next:** T-002-01 to T-002-16 (implementation, on Sonnet). Ask the dataset authors about event 2's maintenance date and `Oil_level`.

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
