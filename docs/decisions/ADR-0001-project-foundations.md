# ADR-0001: Project foundations (SDD, branching, data, licence)

- **Status:** Accepted
- **Date:** 2026-11-02

## Context
This is a solo academic and portfolio prototype. It needs traceable scope (the master doc phases), reproducibility and no large files in Git.

## Decision
1. **SDD:** lightweight in-repo specs in `specs/<NNN>-<slug>/{spec,plan,tasks}.md`, one per roadmap phase or feature. No external SDD tooling.
2. **Branching:** `main` holds milestones and is tagged. `dev` is the integration branch. Work happens on `feature/*` and `fix/*` branched from `dev`. PRs require green CI.
3. **Data:** `datasets/raw` and `datasets/processed` are gitignored. Provenance and SHA-256 checksums go in `datasets/metadata/dataset-register.md`. CI uses small fixtures.
4. **Licence:** MIT.
5. **Graphify:** `graphify-out/` is gitignored and rebuilt locally through the git hook.
6. **Environment:** uv-managed `.venv` on Python 3.12, configured in `pyproject.toml`.

## Alternatives considered
GitHub Spec Kit, OpenSpec, full git-flow, DVC, committing the graph. All were rejected as too much overhead for a solo prototype at this stage.

## Consequences
A fresh clone needs the datasets downloaded manually or by script (Phase 1 adds the scripts). DVC can be revisited if processed artefacts become important to share.
