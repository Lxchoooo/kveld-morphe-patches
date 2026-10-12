---
description: Build every applicable patch for one target app (telemetry, debloat, compatibility, privacy, UX declutter, and dedicated variants of the universal patches) via AGY.
---

Run `/patch-app` with arguments: $ARGUMENTS

Read the orchestrator contract in full and follow it exactly: `.agents/skills/patch-app/SKILL.md` (repo-relative).
It is shared with Antigravity and Claude Code (`.claude/skills` symlinks to `.agents/skills`) and is the single source of truth for steps, family workers, universal coverage, gates, device validation, and closing.

OpenCode mapping (this command runs inside OpenCode, not Claude Code):
- You are the AGY orchestrator: load the `agy-orchestrator` skill and delegate every project edit to the AGY CLI; never edit project code directly.
- The orchestrator runs checks whose writes are git-ignored (`build/`); AGY validates anything writing versioned files.
- Do not push or open a PR autonomously.
