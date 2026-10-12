---
name: update-patches
description: Patch-set update cycle for new app versions across F1 audit, F2 implement, F3 Morphe/device acceptance, and F4 regression.
argument-hint: "<target> [--apk <path>] [--phase 1|2|3|4] [--all-options]"
disable-model-invocation: true
---

# `/update-patches` — Patch-Set Update Cycle

## Purpose

Standard cycle for updating the Morphe patch set to a new APK version.
Four sequential phases with hard gates. A phase never starts unless the
previous phase ended in PASS. Never skip a gate, never manufacture a PASS.

| Phase | Name | Gate |
| ----- | ---- | ---- |
| F1 | Audit | `AUDIT PASS` / `NOT READY` |
| F2 | Implement | `IMPLEMENTATION PASS` / `NOT READY` |
| F3 | Morphe + device acceptance | `ACCEPTANCE PASS` / `NOT READY` |
| F4 | Regression + audit + close | `READY` / `NOT READY` |

## Invocation

```text
/update-patches <target> [--apk <path>] [--phase 1|2|3|4] [--all-options]
```

- `<target>`: `brave | gboard | tiktok | hevy | nokoprint | xiaomi_earbuds` (required).
- `--apk`: explicit original input binary. Default: resolve `candidate_apks/<app>_*_orig.(apk|apkm|xapk)`. Brave requires both ABIs (`BraveMonoarm64_*_orig.apk` and `BraveMonoarm_*_orig.apk`).
- `--phase`: run a single phase and stop with its STATUS. Default (no `--phase`): run F1..F4 back-to-back, advancing automatically on every PASS until `READY` or the first non-PASS phase.
- `--all-options`: also force all boolean patch options on in F3 when the change sits behind an option.
- A physical ADB device is always connected when this command runs. Never ask for confirmation between phases. Missing device output is a hard environment blocker, not a skip.

# Why this cycle exists

A patcher exiting without error proves nothing: a fingerprint can match the
wrong method, a `try-catch` can swallow the failure, and an APK that builds
can crash at runtime. So the cycle separates evidence (F1), change (F2),
real proof (F3), and audited close (F4). Non-negotiable acceptance: `runPatchTest`
from the original binary with 0 failed patches, 0 `Failed to match the
fingerprint` / `fingerprint mismatch`, 0 smali errors (`Detected Smali Compile
Errors`), plus physical-device install, clean boot without `FATAL EXCEPTION`,
and every patch verified on screen.

## Remediation loops (automatic, no confirmation)

- F1 incomplete (missing classification or unactionable plan) → repeat F1.
- F2 gate red (build, suite, or per-patch contract) → root-cause, minimal fix, repeat F2 validation. No accumulation of unvalidated changes.
- F3 failure (Morphe, decompilation, or runtime) → root-cause (re-obfuscated target, injection, dependency, order), minimal code fix, contract plus `buildAndroid`, repeat F3 from the original binary. Never fix the APK by hand.
- F4 confirmed defect touching patches or the bundle → fix, then repeat F3 in full before closing again.
- Identical-repeat guard (stuck detection): never re-run the same validation command on the same input without an intervening source change. A second identical failure (same phase, same patch, same blocking reason or fingerprint mismatch) stops the loop: change the diagnosis angle (different anchor string, caller, ABI, or decompiled cross-check) or escalate to the user. The count resets only on a changed hunk or genuinely new evidence, never on a bare re-run.
- F2/F3 diagnosis builds or refreshes a fast, deterministic reproduction command before theorizing, confined to git-ignored outputs (`build/`) or scratch; never create tracked test files.

## Step 0 — Scope bootstrap (before any phase)

0. Toolchain preflight (read-only): `./venv/bin/python harness/update.py --doctor`. Any `[FAIL]` is an environment blocker: fix the environment, never the code, and restart Step 0. `[WARN]` lines never block.
1. Identify repo root, branch, `HEAD`, working tree (`git status --short`, `git log`, `git diff --stat`).
2. Record input SHA-256 of every original binary. Never use an already-patched APK as input. F3 and F4 must prove input F1 == input F3 by SHA-256.
3. Record baseline: supported version from `Constants.kt` (`<APP>_TARGET_VERSION`). If an APK of that version exists in `candidate_apks/`, use it for comparison; otherwise reconstruct from fingerprints, contracts, and docs. Never invent.
4. Read repo `AGENTS.md` and `docs/out-of-scope.md`. They override this contract on gates, commits, and prohibitions.
5. `--phase N` runs only phase N and stops with its STATUS. Full runs chain automatically: every PASS advances to the next phase; the run ends at the first non-PASS phase or at F4 `READY`.

---

# F1 — Audit (read-only)

Strictly read-only. No modification of code, patches, fingerprints, contracts, tests, scripts, docs, or config.

1. Primary signal, every target: a differential full-suite run on the new input (writes only git-ignored `build/` outputs, so it stays read-only for the repo):
   ```bash
   ./gradlew runPatchTest -Papk=<input> -PallowVersionMismatch=true --console=plain > build/patchtest-<app>-f1.log 2>&1; echo "exit=$?"
   ```
   The runner rejects inputs whose version is not the `Constants.kt` target unless `-PallowVersionMismatch=true` is passed. The `FINAL PATCHING RESULT` block lists every failed patch and fingerprint mismatch: this is the authoritative list of what F2 must touch. Measured precision (TikTok 47.0.3 vs 47.1.4 contracts): the patcher failed 21 patches, the harness flagged 1 of the 12 failing patches that have contracts and 9 failing patches had no contract at all. Never classify a patch VERIFIED from the harness alone when this run failed it.
   Secondary, only when the target has a harness pipeline (brave, gboard, tiktok, xiaomi_earbuds; hevy and nokoprint exit `rc=2`):
   ```bash
   mkdir -p build
   ./venv/bin/python harness/update.py <input> --audit --output build/<app>_HARNESS_REPORT.md --json
   ```
   Parse `build/<app>_HARNESS_REPORT.json` (same content, machine-readable) for per-patch statuses and blocking reasons; the `.md` is the human companion. Reports under `build/` stay git-ignored so F4 diff stays clean.
   The report is initial evidence, not a verdict. A BLOCKED line can come from a stale contract (`harness/<app>/contracts.py`; Brave: `harness/migration/validator.py`), not from the patch. Confirm every BLOCKED against the real fingerprint in the `.kt`.
2. Report input: SHA-256, package, version, versionCode, ABIs, DEX/splits, native libraries. For bundles identify `base.apk` and splits. Never mutate the input.
3. Per patch: current target, equivalent target in the new version, fingerprint, context and control flow, injection strategy, resulting behavior. Natives (`rawResourcePatch`): offsets in `.so` (strings/`.rodata`), Hermes `index.android.bundle`, presence of libs to trim. Never rely on names, offsets, or "the patcher did not fail".
4. One classification per patch:
   `VERIFIED` (works unchanged) | `FINGERPRINT_UPDATE_REQUIRED` (logic holds, only identification changes) | `PATCH_UPDATE_REQUIRED` (code/structure/flow changed) | `OBSOLETE` (target or behavior gone) | `UNKNOWN` (missing evidence). Never VERIFIED by inference.
5. Plan only for `FINGERPRINT_UPDATE_REQUIRED` and `PATCH_UPDATE_REQUIRED`: old/new target, difference and cause, current/proposed fingerprint, injection point, transformation, risks, harness contract to update, acceptance criterion. No implementation.

Output: `| Patch | Target | State | Evidence | Required change | Risk | Contract |` plus sections per state, so another agent can implement without repeating analysis.

Gate: `AUDIT PASS` only with every patch classified and every non-VERIFIED plan actionable. Else `NOT READY`.

---

# F2 — Implement (no commits)

No reclassification. Modify only `FINGERPRINT_UPDATE_REQUIRED` and `PATCH_UPDATE_REQUIRED`. `OBSOLETE` and `UNKNOWN` are never marked functional.

Invariants: single target version, zero zombie fingerprints, per-patch telemetry with bracketed prefix and consolidated summary, zero emojis in code/scripts/logs, minimal change, `docs/out-of-scope.md` prohibitions respected.

Scope: patch code, `Constants.kt`, harness contracts and their suite. No user APK builds, no ADB, no `README.md` or `docs/apps/`, no `generatePatchesList`, nothing that mutates `patches-list.json` or `CHANGELOG.md`. No commits.

Rules:

- Version: bump `<APP>_TARGET_VERSION` in `Constants.kt` by hand, or inspect the plan with `harness/update.py <input> --dry-run`. `--update` applies it and checks with `./gradlew check buildAndroid` (no release artifacts), but for Brave it only covers the constant plus symbols/offsets.
- Multi-ABI: native offsets for every supported ABI in the same change, never one ABI alone.
- Contracts: every target change (class, method, anchor string) is mirrored in its harness contract (`harness/<app>/contracts.py`; Brave: `harness/migration/validator.py`).
- Minimal change; no unrelated refactors.

Per-patch validation (no Kotlin unit tests; validation is contract plus isolated application):

1. Per iteration: `./gradlew runPatchTest -Papk=<input> -Ppatch="<Patch name>"` (TikTok ~6 s versus ~152 s full suite and ~125 s harness audit). Add `-PallowVersionMismatch=true` only while `Constants.kt` still holds the old version.
2. Once at phase close, only when the target has a harness pipeline: `harness/update.py <input> --audit --output build/<app>_HARNESS_REPORT.md --json` (`mkdir -p build` first on standalone `--phase 2` runs): every modified patch's contract VERIFIED in the JSON sidecar. Targets without a pipeline (hevy, nokoprint) skip this step; their contract evidence is the per-patch run.
3. Single deterministic target, no false positives, nothing outside the modified patch.

On failure: root cause, minimal fix, repeat. No accumulation of unvalidated changes.

Phase close: `./gradlew check buildAndroid` clean, `./venv/bin/python -m unittest discover harness/tests` PASS, only planned patches modified, single version, zero zombies, contracts synced and VERIFIED, no temp artifacts, README/docs untouched.

Output: `| Patch | Change type | Contract | Build | State |` plus `STATUS = IMPLEMENTATION PASS | NOT READY`. On PASS advance to F3 automatically.

---

# F3 — Morphe + device acceptance (blocking gate)

Preconditions (if any is unproven, stop): F2 `IMPLEMENTATION PASS`; input is the F1 original binary with identical SHA-256. Never a patched APK or leftovers from prior attempts.

1. Morphe:
   ```bash
   ./gradlew runPatchTest -Papp=<target> -Pout=candidate_apks/<app>_<version>_patched.apk
   ```
   (`-Papk=candidate_apks/<input>` variant allowed; relative `-Pout` resolves against the repo root only when the directory exists.) Brave: one run per ABI (`-Papk=...Monoarm64...` and `-Papk=...Monoarm...`); both must pass. Bundles: the runner merges split DEX into `base.apk`, patches, signs base plus splits; splits land as `<app>_<version>_patched.<split>.apk`. When the change sits behind a patch option, repeat with `-PallOptions=true`. Demand: every expected patch applied, 0 failed, 0 fingerprint mismatches, 0 smali errors. Exit code 0 alone is insufficient. On failure: full log, patch, root cause (re-obfuscated target, injection, dependency, order), minimal fix, contract plus `buildAndroid`, repeat from the original binary.
2. APK verification: integrity (manifest, DEX, signature) and decompilation. Per patch: target, injection point, and modification present, no adjacent-code effects. Output: `| Patch | Target | Verified injection | Result |`.
3. Device (ADB): install and boot-check exactly what the successful run produced with the repo gate:
   ```bash
   ./venv/bin/python validation/smoke_install.py candidate_apks/<app>_<version>_patched*.apk --uninstall-on-conflict
   ```
   It picks the connected device by APK ABI and min SDK (several devices are attached; a bare `adb` fails), uses `install-multiple` for split sets, launches via monkey, scans the crash buffer scoped to the package, and prints a JSON verdict (exit 0 = PASS; `PASS_NO_LAUNCHER` is valid for IMEs). Brave: one run per ABI output, so the arm build lands on the armeabi-v7a device. For every later manual `adb` command export the `serial` from the JSON as `ANDROID_SERIAL`. `SKIPPED_ACTIVE_IME` (patched Gboard is the user's daily keyboard on the arm64 device): rerun with `--serial` of a compatible device where it is not the active IME; when none exists, ask the user before passing `--allow-active-ime`. Per patch: trigger the behavior, verify on screen, check logcat, test persistence/restart where applicable. Privacy: logcat and dumpsys (`jobscheduler`, `alarm`) filtered by `PACKAGE_NAME`, never global dumps. Diagnostic servers on `127.0.0.1` only. On failure: filtered trace, root cause, code fix, rerun Morphe from the original, reinstall. Never hand-edit the APK. Output: `| Patch | Morphe | Install | Runtime | Logcat | Result |`.

Gate: Morphe 100% (all ABIs), decompilation-verified APK, same artifact installed, boot without `FATAL EXCEPTION`, every patch runtime-tested, filtered diagnostics. `STATUS = ACCEPTANCE PASS | NOT READY`. On PASS advance to F4 automatically, no confirmation.

---

# F4 — Regression + audit + close

Runs automatically after F3 `ACCEPTANCE PASS`. Else `STATUS = NOT READY` and the run ends.

1. Regression: with no code changes since F3, `./gradlew check buildAndroid` suffices. After remediations: harness suite, target audit, full `runPatchTest`. When a local task mutated `patches-list.json` or `CHANGELOG.md`, restore only those files (`git checkout -- <file>`).
2. `/audit-stack` (manual-only skill: read and follow `~/.gemini/config/skills/audit-stack/SKILL.md` directly): stages 1 (adversarial-pr-breaker) and 2 (integration-regression-auditor) sequential; stages 3 (maintainability-hardcoding), 4 (security-privacy-integrity), 5 (repo-hygiene) parallel over a frozen snapshot. One confirmed defect stops the close; when the fix touches patches or the bundle, repeat F3.
3. Diff: `git status`, `git diff`, `git diff --check`: no artifacts or temporaries, no weakened tests, no absolute paths or local coupling, no out-of-scope changes, no emojis outside README.
4. Docs and commits: document only what was demonstrated (supported version and per-patch behavior in `docs/apps/<app>.md` and manual `README.md` sections; the `PATCHES_START`/`PATCHES_END` catalog is regenerated by release). One atomic commit per patch (`feat|fix(<target>): ...`) bundling its code, harness contract, and docs.
5. Close: traceability input F1 == input F3 (SHA-256), F2 patch set == Morphe patch set, Morphe artifact == installed artifact. READY only with F1-F3 PASS, single version, Morphe 100%, verified injection, runtime PASS, filtered diagnostics, regression PASS, `/audit-stack` PASS, clean diff, faithful docs, atomic commits, zero pending defects. Else NOT READY.
6. Merge-back (automatic, local only): after READY, merge the update branch into main via AGY with all workers stopped.
   - If main HEAD == branch base: `git merge --ff-only`, then remove the worktree. No confirmation.
   - If main diverged: merge automatically ONLY if conflict-free AND file-disjoint from the foreign commits, then re-run the target gate post-merge; remove the worktree only on green.
   - Otherwise stop at READY-on-branch and report the divergence with the exact merge command. Never auto-resolve conflicts touching foreign files. Never rebase foreign commits.
   - Explicit user stop constraints ("stop at READY") override this step.
   - Push still requires explicit user instruction in all cases.

Report: final state (`READY`/`NOT READY`), Morphe, physical validation, regression, `/audit-stack`, `| Patch | State | Morphe | Runtime | Evidence |`, `| Artifact | SHA-256 | State |`, pending defects (or NONE).

# Gotchas / operational notes

- Input purity: every run starts from the F1 original (SHA-256). The `runPatchTest` autodiscovery fallback ignores any file with `patched` in its name, so it never reuses a previous output or its splits.
- Autodiscovery: without `-Papk`, `runPatchTest` looks for the canonical names of the target version in `candidate_apks/` (and download folders) and infers the app from `git status --porcelain`.
- Bundles (Hevy, NokoPrint, Xiaomi Earbuds): installing only the base crashes on missing resources/code; manual installs need `adb install-multiple` (`smoke_install.py` does it).
- Contracts vs fingerprints: harness validators match method names inside the contract classes and anchor strings across all DEX, same as fingerprints, which usually anchor on obfuscated `LX/...` helpers. A method renamed in the `.kt` but not in the contract yields BLOCKED even when the patch applies.
- Natives: `.so` offsets (e.g. `.rodata` of `libchrome.so` in Brave) and Hermes bytecode (`index.android.bundle` in Hevy) are invisible to the Dalvik AST; audit them on the binary. The harness compares Brave telemetry hosts against the patch offsets per ABI.
- Performance budgets (measured 2026-10-08): harness audit Gboard ~4 s, Brave ~7 s arm64 / ~6 s arm, Xiaomi ~16 s, TikTok ~125 s (56 DEX, ~2M methods, Androguard parse). Full `runPatchTest`: Gboard ~22 s, Brave ~25 s per ABI, Xiaomi ~6 s, NokoPrint ~7 s, Hevy ~7 s, TikTok ~152 s; a single `-Ppatch` run ~6 s. `check buildAndroid` ~17 s cold, ~3 s warm. `smoke_install.py` ~2 s to a verdict on conflict, ~1.5 min for a full install plus launch on the armeabi-v7a device.
- Version guard: `runPatchTest` also fails on an unknown `-Papp`. JSON sidecar encodes enums as values and native bytes as hex.
- Release artifacts: `patches-list.json`, `patches-bundle.json`, `CHANGELOG.md`, and the README catalog are generated by semantic-release in CI. Never commit local `generatePatchesList` output.
- Agent isolation: never two agents writing on the same checkout; parallel work goes in a `git worktree` on its own branch and merges with `git merge --ff-only`.

# Evidence rules

Evidence hierarchy: global `AGENTS.md` §5. A BLOCKED contract line is not a patch verdict until confirmed against the `.kt` fingerprint. Exit code 0 is not Morphe success without the `FINAL PATCHING RESULT` block (0 failed, 0 mismatches, 0 smali errors).

# Precedence and closing

Repo `AGENTS.md`, then global `AGENTS.md`, then `docs/out-of-scope.md`, then this contract. Standing authorizations and run lessons live in `observations.md` next to this file; read it at Step 0. F1 never writes. F2 never commits. F3 never hand-edits APKs and never exposes diagnostics beyond loopback. F4 never pushes or opens a PR without explicit user instruction.

# Core invariant

> A patch set is updated only when every phase sequentially survived its gate on the same original input: audited (F1), implemented (F2), Morphe-accepted on all ABIs plus device-accepted (F3), regression-clean plus audit-clean plus atomically committed (F4). Invoking a gate is not surviving it.
