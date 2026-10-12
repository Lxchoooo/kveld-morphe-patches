# `/update-patches` — standing authorizations & lessons (2026-10-07, brave 1.97.56 run)

Applies to every future run unless the user restricts it. Does not override
repo `AGENTS.md` / `docs/out-of-scope.md`; on conflict those win.

1. **ADB signature conflict**: authorized to uninstall the installed app and
   continue via `validation/smoke_install.py --uninstall-on-conflict` (F3 step 3;
   a manual `adb uninstall` is denied in Claude Code settings). Never treat it
   as a blocker.
2. **Worktree-first**: open a dedicated `git worktree` on its own branch
   before F1, always. Never run phases on a checkout shared with another
   worker. Merge back only via AGY with workers stopped. READY means merged
   (or explicitly deferred with cause), never just committed-on-branch.
3. **Split orchestrator/AGY**: orchestrator (more capable) does all analysis
   and dictates exact hunks; AGY executes mechanical edits only
   (`gemini-3.8-flash-low --effort low` for fully-dictated text, high tier
   for hook logic/diagnosis). One AGY call per cohesive tranche.
4. **Single-completion prompts**: workers must await their own background
   tasks and answer once with table + STATUS. No status resumes; the
   orchestrator never polls, it backgrounds and waits for notification.
5. **Gate evidence**: every gate claim ships tree-state proof
   (`git status --short`, file hashes) with the verdict.
6. **F3 always `-Pout`** to a git-ignored path so the artifact is hashable
   and installable from the first attempt.
7. **Retry is automatic**: on environment-caused NOT READY, redo in the
   isolated worktree without asking. Ask only when scope or fidelity is
   at stake.
8. **Anchor-existence pre-check before porting**: verify every upstream
   fingerprint anchor (strings, classes, methods) exists in the TARGET
   version binary (DEX strings + xref) before writing a port. If the
   upstream mechanism is gone (e.g. share-URL sessionToken flow present
   in 12.19.1 but absent in 12.33.0), classify OBSOLETE and do not port:
   a hook without a target is a zombie by construction, not a
   fingerprint to fix.
