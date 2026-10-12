---
description: Patch-set update cycle for a new app version. Sequential gates F1 audit, F2 implement, F3 Morphe plus device acceptance, F4 regression plus audit-stack plus atomic commits.
---

Run `/update-patches` with arguments: $ARGUMENTS

Read the orchestrator contract in full and follow it exactly: `.agents/skills/update-patches/SKILL.md` (repo-relative).
It is shared with Antigravity and Claude Code (`.claude/skills` symlinks to `.agents/skills`) and is the single source of truth for phases, gates, stop conditions, verification, and reports.

OpenCode mapping (this command runs inside OpenCode, not Claude Code):
- This is a sequential gated pipeline (F1→F2→F3→F4), not a concurrent audit. Execute one phase per turn with the `subagent` tool; pass the full Step 0 scope (target, input SHA-256, baseline version, branch/HEAD/status) in the prompt so workers start without redundant bootstrap.
- Where project implementation is required (F2, F2/F3 remediations, F4 fixes), delegate to the AGY CLI per the `agy-orchestrator` skill; the orchestrator never edits project code directly. Direct edits are only for files outside the project or on explicit user request.
- F1 is read-only: no writes, no commits. F2 writes patch code plus `Constants.kt` plus harness contracts only; no commits, no README/docs, no `generatePatchesList`.
- Default run chains F1→F2→F3→F4 automatically with no confirmation prompts; an ADB device is always connected. `--phase N` runs only that phase.
- F3 needs ADB hardware; a missing device is a hard blocker, never a skip. The orchestrator runs checks whose writes are git-ignored (`build/` logs); AGY validates anything writing versioned files. Demand the `FINAL PATCHING RESULT` block (0 failed, 0 mismatches, 0 smali errors); exit code 0 alone is insufficient. Never hand-edit APKs; diagnostics filtered by package, loopback only.
- F4 runs `/audit-stack` (stages 1-2 sequential, 3-5 concurrent) over a frozen snapshot, then docs plus one atomic commit per patch. Do not push or open a PR autonomously.
- Present each phase STATUS as it completes; stop only at the first non-PASS phase or at F4 `READY`.
