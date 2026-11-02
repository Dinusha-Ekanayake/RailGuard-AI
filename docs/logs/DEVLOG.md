# Development log

Newest entry at the top. Each entry records what was done, the decisions made and what comes next.

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
