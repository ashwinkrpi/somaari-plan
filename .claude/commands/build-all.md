---
description: Orchestrate docs/BUILD_PLAN.md stages via the stage-builder subagent, one at a time (default up to Stage 8)
argument-hint: "[stage | from-to]  e.g. 3 or 2-5; default: next stage in docs/STATUS.md through 8"
---

Act as orchestrator for docs/BUILD_PLAN.md. Don't write app code yourself.

Stage range: `$ARGUMENTS`. If empty, start at the "Next" stage in docs/STATUS.md and stop after Stage 8.
Never run Stage 9 (Pi deploy: systemd, sudo) or Stage 10 (go public) from this command, even if asked in the range — tell me instead.

For each stage in the range, in order, one at a time (never in parallel):

1. Read docs/DECISIONS.md. If an Open entry is tagged with this stage (e.g. D-01 and D-04 for Stage 5), stop and ask me about it. Don't decide it. Entries tagged "After Stage N" don't block Stage N.
2. Delegate to the stage-builder subagent with the stage number. Each stage runs in its own fresh subagent context (this replaces the "/clear between stages" rule).
3. When it returns, run the full suite yourself: `.venv/bin/python -m pytest -q`.
4. Check `git log -1 --stat`: the "Stage N" commit exists, and `.env`, `config.toml`, `data/`, `.venv/` and `*.zip` are not in it.
5. Decide:
   - STAGE_COMPLETE and tests pass → next stage.
   - STAGE_PENDING_MANUAL and tests pass → list the manual checks for me, then continue.
   - STAGE_BLOCKED, failing tests, or a bad commit → stop and tell me.

At the end, give me one short summary: stages done, manual checks still owed, open decisions.
