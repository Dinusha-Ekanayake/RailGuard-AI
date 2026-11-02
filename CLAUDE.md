# RailGuard AI: project instructions for Claude Code

Read `AGENTS.md` first. It is the operating manual (workflow, branches, specs, logs). This file only adds Claude-specific rules.

## Hard rules
1. **No AI attribution in git or GitHub.** No `Co-Authored-By` Claude/AI trailers, no "Generated with Claude Code" or similar lines in commits, PRs, issues, tags or releases. Commits use the user's identity. Check every message before committing.
2. **Graphify first (token efficiency).** Query `graphify-out/` (`graphify query`, `graphify explain`, `GRAPH_REPORT.md`) before sweeping files with Read/Glob/Grep. Rebuild with `graphify update .` after big changes. Never index `datasets/`.
3. **Use the project venv only:** `.venv\Scripts\python.exe` (Python 3.12). Never install into the global interpreter.
4. **Never commit raw/processed data.** Record provenance in `datasets/metadata/dataset-register.md` instead.
5. **Safety boundary.** ML never overrides the deterministic rule engine. Keep the wording neutral ("anomaly detected", "simulated rule conflict") and never "defect confirmed" or "collision prevented".
6. **Spec before code.** No implementation without an approved `specs/<NNN>-<name>/spec.md`.

## Source of truth
`docs/RailGuard_AI_Project_Master_Document.docx` (v1.0, 2026-11-01). The specs in `specs/` refine it phase by phase.

## graphify
- **graphify** (`.claude/skills/graphify/SKILL.md`): turns any input into a knowledge graph. Trigger: `/graphify`. PreToolUse hooks in `.claude/settings.json` check the graph before searches and reads.
