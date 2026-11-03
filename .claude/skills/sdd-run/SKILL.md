---
name: sdd-run
description: Run an approved RailGuard spec to completion with subagents - Sonnet implementer, risk-based reviewer (Opus for high risk), Haiku clerk - with briefs, a scripted quality gate, hard caps and human gates. Trigger with /sdd-run <NNN>, or /sdd-run plan <topic> to draft a new spec.
---

# /sdd-run

`SDD` below means `.venv/Scripts/python.exe -m scripts.sdd`. Run it from the repo root with
no `cd` prefix, so the permission allowlist matches.

## Before you start
- Tell the user, once: "Orchestration is cheap work. Switch this session to Sonnet
  (`/model sonnet`). Opus is still used where the agents ask for it." Then continue.
- Read only the JSON that `SDD` prints. Do not read specs, plans or source files yourself;
  the briefs and agents do that.

## `/sdd-run plan <topic>`: new spec
1. Run the `sdd-planner` agent with the topic.
2. Show the user its summary and open questions. **Stop.** The user approves the spec by
   setting `Status: Approved`. Never approve it yourself.

## `/sdd-run <NNN>`: implement an approved spec
1. `SDD start <NNN>` (refuses unless the spec is Approved and the branch is
   `feature/<NNN>-*`; if the branch is wrong, stop and tell the user).
2. Loop:
   1. `SDD next` → JSON.
      - `halted`: run step 4.
      - `done`: run step 3.
      - `run`: continue with its `tasks`, `risk`, `reviewer_model`, `human_signoff`,
        `restart_implementer`.
   2. `SDD brief <ids...>` → brief path.
   3. **Implement.** First group, or `restart_implementer` is true: start a new
      `sdd-implementer` agent with the brief path and run `SDD agent implementer --fresh`.
      Otherwise send the brief path to the existing implementer with SendMessage and run
      `SDD agent implementer`. Keep only its report.
   4. Report says `STATUS: blocked` or has QUESTIONS that change behaviour: run
      `SDD halt "<question>"`, then step 4.
      For each line under ASSUMPTIONS: `SDD assume <task> "<text>"`.
   5. **Gate.** `SDD check --task <first id>`. On FAIL, send the failing lines to the
      implementer and repeat the gate. If it prints `HALTED`, run step 4.
   6. **Review.** Start (or SendMessage to) an `sdd-reviewer` with the brief path, using
      `model: <reviewer_model>` from `next`. Use one reviewer per model and reuse it.
      Run `SDD agent reviewer`, then `SDD review <first id> clean|changes`.
      - `changes`: send the CRITICAL/HIGH findings to the implementer, then repeat 5 and 6.
        A `HALTED` output means step 4.
      - Reviewer QUESTIONS FOR USER: `SDD halt "<question>"`, then step 4.
   7. **Tick.** For each task: `SDD done <id>`, with `--human` when `human_signoff` is true.
   8. If a group ticked anything under `src/`, run `graphify update .` (local, no tokens).
   9. Print one line, e.g. `T-002-03..04 done (review clean, 2 assumptions)`. Next loop.
3. **Done.** Run the `sdd-clerk` agent (Haiku) for DEVLOG, CHANGELOG and a PR draft.
   Then run a final `sdd-reviewer` on the whole branch with `model: opus`
   (`git diff dev...HEAD` plus uncommitted). Present to the user: tasks ticked, tasks marked
   `[?]` for sign-off, all recorded assumptions (`.sdd/state.json`), final review findings,
   and the PR draft path. **Stop.** Commit, push and the PR need the user's go-ahead.
   Then `SDD stop`.
4. **Halted.** Show the user the reason, the task, and what you need from them. Stop. After
   they answer: `SDD resume` and continue the loop.

## `human` tasks
Do the preparation (run the script, produce the outputs, draft the card), but leave the
judgement to the user: real-data results, interpretation, experiment cards, commits and
PRs. Tick them with `--human` so they show as `[?]`.

## Guarantees enforced by `scripts/sdd`
- Same gate failure twice, more than 3 fix attempts, a second review with open findings,
  or more than 60 agent runs: halt.
- Stop hook: the session cannot end while tasks are open, but it only pushes on when a task
  was completed since the last push. No progress halts the run.
- Implementer is restarted fresh every 4 tasks to stop its context growing.
- Banned wording fails the gate.
