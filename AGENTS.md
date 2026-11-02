# AGENTS.md: operating manual

Applies to every human or AI contributor.

## Workflow (spec-driven)
For each roadmap phase (master doc §14):
1. **Spec**: write `specs/<NNN>-<name>/spec.md` (what and why, acceptance criteria). Status: Draft → Approved.
2. **Plan**: write `plan.md` (how: modules, data flow, risks, test strategy).
3. **Tasks**: write `tasks.md` (ordered checklist; each task is small and testable).
4. **Implement** on `feature/<NNN>-<slug>` using TDD (test first, then code, then refactor; ≥80% coverage on `src/railguard`).
5. **Review**: run the code-reviewer agent, plus python-reviewer and security-reviewer where relevant.
6. **PR → dev**. CI must be green. Update `docs/logs/DEVLOG.md` and `CHANGELOG.md`.
7. **Milestone**: PR from dev → main, tagged `vX.Y.0`.

Architectural choices get an ADR in `docs/decisions/`. Use [ADR-0000-template.md](docs/decisions/ADR-0000-template.md) as the starting point.

## Branches
| Branch | Purpose |
|---|---|
| `main` | Stable milestones only. PR from `dev`, protected. |
| `dev` | Integration. PRs from feature branches, protected (CI required). |
| `feature/<NNN>-<slug>` | One spec or task group, branched from `dev`. |
| `fix/<slug>` | Bug fixes, branched from `dev`. |

## Commits
Conventional commits: `feat|fix|refactor|docs|test|chore|perf|ci: <summary>`. **No AI or Claude attribution of any kind.**

## Tracking files
| File | Purpose |
|---|---|
| `specs/` | Specs, plans and tasks per phase |
| `docs/logs/DEVLOG.md` | Dated session log: what was done, decisions, next steps |
| `CHANGELOG.md` | User-visible changes per version |
| `docs/decisions/` | ADRs |
| `docs/risk-register.md` | Project risks and mitigations |
| `datasets/metadata/dataset-register.md` | Dataset provenance and checksums |
| `docs/experiments/` | Experiment cards |
| `.claude/skills/` | Project skills (SDD workflow, Graphify) |

## Environment
```powershell
uv venv .venv --python 3.12
uv pip install --python .venv\Scripts\python.exe -e ".[dev]"      # add ,analysis for EDA
.venv\Scripts\python -m pytest --cov
.venv\Scripts\python -m ruff check . ; .venv\Scripts\python -m mypy
```

## Token efficiency
Use Graphify (`graphify query "..."`, `graphify-out/GRAPH_REPORT.md`) before reading files. `graphify hook install` keeps the graph current on commit and checkout.
