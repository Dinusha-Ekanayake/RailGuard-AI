# Spec 000: Project setup

- **Status:** Implemented
- **Master doc refs:** §13, §14 (Phase 0), §15
- **Branch:** main (bootstrap), then dev

## Problem / why
A reproducible foundation is needed before any data or ML work starts.

## Requirements
- REQ-000-01: Python 3.12 venv, isolated per project, with deps declared in `pyproject.toml`.
- REQ-000-02: Repository layout follows master doc §13.
- REQ-000-03: Raw and processed data are never committed. Provenance and checksums are recorded.
- REQ-000-04: CI runs lint, type-check and tests on PRs to `dev` and `main`, and rejects large files and AI attribution.
- REQ-000-05: Tracking files exist: AGENTS.md, CLAUDE.md, DEVLOG, CHANGELOG, ADRs, risk register, SDD skill.
- REQ-000-06: Graphify is configured for token-efficient codebase queries.

## Acceptance criteria
- [x] AC-01: A fresh clone plus the README setup commands give passing `pytest`, `ruff` and `mypy`.
- [x] AC-02: `git ls-files` contains no file from `datasets/raw/`.
- [x] AC-03: `main` and `dev` exist on GitHub, and CI is green on `dev`.
