---
name: patch-app
description: Manual end-to-end workflow that builds every applicable patch for one target app - recon, registration, dedicated variants of the universal patches, and parallel family workers (telemetry-blocking, app-debloat, compat-bypass, privacy-controls, ux-declutter) - then gates, device and traffic validation, and atomic commits. Invoke with /patch-app <apk>.
disable-model-invocation: true
---

<!-- Shared skill: canonical source is kveld-morphe-patches; scripts/sync_shared_skills.sh mirrors it byte-identically into kveld-extra-morphe-patches (.claude/skills is a symlink to .agents/skills in each repo). Edit only in kveld-morphe-patches; the sibling pre-commit hook rejects direct edits. Repo-specific deltas live in section 0 below. -->

# Patch App: Full Per-App Patch Build

## 0. Repository Adaptation Notes (Shared Canonical Copy)

- **Sync invariant**: the canonical copy lives in kveld-morphe-patches; edit this file only there. After each commit or merge on `dev` in the kveld-morphe-patches main checkout (linked worktrees and other branches are skipped), `scripts/hooks/post-commit` and `scripts/hooks/post-merge` copy the committed version into kveld-extra-morphe-patches and commit it there when that checkout is safe to write; the sibling `pre-commit` hook rejects direct edits. `scripts/sync_shared_skills.sh --check` verifies. Repo-specific deltas belong in this section.
- **README**: update only the hand-maintained Supported Targets table above `PATCHES_START`/`PATCHES_END`. Never edit the generated Patch Catalog block, `patches-list.json`, `patches-bundle.json`, or `CHANGELOG.md`; the release pipeline regenerates them. Verify catalog registration from a temporary directory outside the checkout; never run `generatePatchesList` in the checkout.
- **Registry**: register the app in `util/PatchExecutionTest.kt` (`id`, `packageName` from `Constants.kt`, `candidateFilenames`, `filePattern`, `patchDirectoryPart`). Known divergence: id `xiaomi_earbuds` uses `patchDirectoryPart` `xiaomi` and guide `docs/apps/xiaomi-earbuds.md`.
- **Extension wiring**: both repos expose `sharedExtensionPatch` (`app.morphe.patches.shared.SharedExtensionPatch.kt`). Link companion runtime filters (e.g. preference-gate filters) with `dependsOn(sharedExtensionPatch)`; a direct `extendWith("extensions/extension.mpe")` per patch triggers a redundant `ClassMerger` pass.
- **Universal boundary**: dedicated telemetry suites are a precision superset; never stack a generic telemetry neutralizer on maintained apps. Generic debloat universals (locale/dpi) are unaffected.
- **Universal patches**: they live only in kveld-morphe-patches (patches/src/main/kotlin/app/morphe/patches/universal, catalog in docs/universal-patches.md). The runner (patches/src/main/kotlin/util/PatchExecutionTest.kt) runs a universal patch only when it is named with -Ppatch="<Patch Name>", one per run; it requires a registered -Papp (or a filename it can infer). In kveld-extra-morphe-patches, probe universals from the sibling kveld-morphe-patches checkout with -Papk=<absolute APK path> -Papp=<any registered id> -PallowVersionMismatch=true (unverified path, inferred from the runner source: confirm on first use; if it fails, fall back to the static review in the Universal Coverage step).
- **Skill availability**: app-debloat, compat-bypass, privacy-controls and ux-declutter are now shared skills present in both repos.
- **Commits**: one atomic Conventional Commit per unit (`feat(<app>):` / `fix(<app>):`), direct commit, never push without explicit request. kveld-morphe-patches develops on `dev` (`main` is the release line); kveld-extra-morphe-patches follows its own `AGENTS.md`.

## 1. Invocation & Workflow

Target: APK path argument in `candidate_apks/` (e.g. `candidate_apks/com.example_1.0.apkm`).

You are the AGY orchestrator (skill `agy-orchestrator`; never edit project code directly, never use another harness's subagents for implementation). Execute:

### Step 0 — Scope bootstrap
0. Environment bootstrap: `python3 -m venv venv && ./venv/bin/pip install -r requirements.txt`.
1. Record `git status --short`. Isolate any pre-existing dirty files or untracked changes as `FOREIGN_IN_PROGRESS_WORK` (do not require working tree to be clean; never stage or commit foreign files). APK must exist under `candidate_apks/` (gitignored, runner resolves only this directory name without explicit `-Papk`; never commit).
2. Recon (orchestrator shell, read-only): run `mkdir -p scratch` for raw recon dumps, `unzip -l`, badging dump via `${AAPT2:-aapt2}`, manifest xmltree to `$AGY_TMP` (path per `agy-orchestrator`), multi-family component inventory across all five patch families and universal selectors. Save evidence paths for workers.

### Step 0b — Already-onboarded app (automatic differential mode, never ask)
If Step 0 recon shows the target package is already registered (`Constants.COMPATIBILITY_*` + `TargetApp` entry + existing `patches/.../<app>/` suite for the same version), DO NOT ask the user what to do and DO NOT re-run Step 1. Proceed automatically in differential-audit mode across every family and universal coverage:
1. Run Step 4 gates against the existing suite to establish the green baseline.
2. Differential recon: inventory of DEX classes/methods, manifest components, native `.so` strings, behavioral checklist (Section 4.J), and universal coverage gaps vs existing patches across all five families. Every gap needs file:line evidence before delegating. Discard funnel (report `no gaps found (rule X)` instead of launching): MANIFEST_INACTIVE (component already disabled) -> TRANSITIVELY_DEAD (no XREFs outside the package) -> CALLER_NEUTRALIZED (single caller already stubbed) -> PRESERVATION_PROTECTED (MLKit/FCM/billing/deeplinks/user-initiated flows) -> INERT_PROCESSING (no network I/O, ID persistence, or UI friction reachable). Callback-accepting or async-returning dispatchers are never gaps-by-stub (see Step 3 rules); only transport-cut or neutral-callback patterns qualify.
3. Launch Step 3 workers ONLY for confirmed gaps (exclusive paths, same rules); skip workers entirely when no gap survives evidence.
4. Continue with Step 5 (device + traffic) and Step 6 (atomic `fix(<app>)` commits only for applied gaps, `audit-stack` over the pending range).
Report `no gaps found` with gate evidence when the suite already covers the surface.

### Step 1 — Registration (one AGY worker, `accept-edits`, low tier)
New `agy` conversation (`gemini-3.8-flash-low --effort low`: benchmarked sufficient — 71 s vs 168 s high at equal schema quality): add `Constants` entry inside `object Constants` + `TargetApp` entry + README row (matching repository column schema) + `docs/apps/<app_id>.md` skeleton (with mandatory Behavioral Hazards Warning) per `AGENTS.md` section 2, and NOTHING else (no companion-mapping edits unless explicitly requested). Folding documentation skeleton here avoids worker collision on docs. Uncommitted; orchestrator commits with the first patch.

### Step 2 — Family plan and universal coverage
Before implementation:
1. **Per-Family Applicability Decision**: Decide per family (`telemetry-blocking`, `app-debloat`, `compat-bypass`, `privacy-controls`, `ux-declutter`) whether it applies, with recon evidence (file:line, class, manifest entry); a family with no evidence gets no worker.
2. **Universal Coverage Matrix**: Map each universal patch from `docs/universal-patches.md` and universal source files to its owning family skill:

| Universal Patch | Source / Typology | Owning Family Skill | Notes & Coverage Scope |
| :--- | :--- | :--- | :--- |
| **Remove Trackers** | `UniversalTelemetryNeutralizerPatch.kt` (`resourcePatch`) | `telemetry-blocking` | Manifest-level ad permissions, analytics providers/services, discovery registrars, declarative opt-out flags. |
| **Block Tracking SDKs** | `UniversalSdkBlockerPatch.kt` (`bytecodePatch`) | `telemetry-blocking` | Dalvik bytecode early `return-void` stubs for third-party APM, crash, analytics, attribution, session replay SDKs. |
| **Block Tracking Servers** | `UniversalHostsBlockerPatch.kt` (`bytecodePatch`) | `telemetry-blocking` | Dalvik URL/host `const-string` rewriting to sink IP (`0.0.0.0`). Requires curated host list. |
| **Remove Tracking Code** | `UniversalNativeBinaryTrimmerPatch.kt` (`rawResourcePatch`) | `app-debloat` (`native-binary-patching` for `.so`) | Byte-level in-situ zeroing (`writeBytes(byteArrayOf())`) of non-essential crash reporter & debug `.so` files. |
| **Remove Extra Languages** | `LocaleResourceSlimmerPatch.kt` (`resourcePatch`) | `app-debloat` | Prunes unselected translation directories from `res/values-*`. |
| **Remove Unused Screen Sizes** | `DpiResourceSlimmerPatch.kt` (`resourcePatch`) | `app-debloat` | Retains target device screen density, prunes non-phone UI modes, safe orphan asset preservation. |
| **Stop Background Wakeups** | `BackgroundSyncPurgePatch.kt` (`resourcePatch`) | `app-debloat` | Strips boot permissions, disables boot receivers and periodic WorkManager schedulers. |
| **Clean App Packaging** | `ApkJunkCleanerPatch.kt` (`rawResourcePatch`) | `app-debloat` | Prunes compiler properties, Kotlin debug tables, and duplicate license files from APK root and `META-INF/`. |
| **Shrink PNG Images** | `PngOptimizerPatch.kt` (`rawResourcePatch`) | `app-debloat` | Lossless RGBA-verified level 9 zlib recompression and chunk stripping for PNG assets in `res/**`, `assets/**`. |
| **Shrink WebP Images** | `UniversalWebpOptimizerPatch.kt` (`rawResourcePatch`) | `app-debloat` | Lossless chunk stripping (`EXIF`, `XMP`, `ICCP`) and VP8X header recalculation for WebP assets in `res/**`, `assets/**`. |
| **Allow Screen Capture (Setup)** & **Allow Screenshots** | `UniversalScreenshotProtectionBypassPatch.kt` (`resourcePatch` + `bytecodePatch`) | `privacy-controls` | Manifest `allowAudioPlaybackCapture="true"`, bitwise `FLAG_SECURE` (`-0x2001`) masking, `setSecure(false)`, screenshot callback stubs. |
| **Remove Permissions** | `UniversalPrivacyPermissionsPatch.kt` (`resourcePatch`) | `privacy-controls` | Selectively revokes sensitive hardware, location, contact, and sensor permissions from `AndroidManifest.xml`. |
| **Go Fully Offline** | `UniversalOfflinePatch.kt` (`resourcePatch`) | `privacy-controls` | Revokes `INTERNET` and network permissions, enforces `usesCleartextTraffic="false"`. Subject to Offline Applicability Gate. |
| **Lock Screen Brightness** | `UniversalScreenBrightnessGovernorPatch.kt` (`bytecodePatch`) | Universal only (no dedicated variant) | Neutralizes direct writes to `WindowManager.LayoutParams.screenBrightness` (`iput`). Operates purely on public Android framework fields. |
| **Force Screen Timeout** | `UniversalScreenTimeoutEnforcerPatch.kt` (`bytecodePatch`) | Universal only (no dedicated variant) | Neutralizes `View.setKeepScreenOn` calls and strips `FLAG_KEEP_SCREEN_ON` (`0x80`). Operates purely on public Android framework APIs. |

*(Exact Name Note: In codebase sources and `docs/universal-patches.md`, the manifest telemetry patch is named `Remove Trackers` [`UniversalTelemetryNeutralizerPatch.kt`] and the native `.so` trimmer is named `Remove Tracking Code` [`UniversalNativeBinaryTrimmerPatch.kt`]).*

3. **Target Probing & Classification**: For each mapped universal, probe it on the target application:
   - *Runtime probe*: `./gradlew runPatchTest -Papp=<app_id> -Papk=<apk> -Ppatch="<Patch Name>" -PallOptions=true -Pout=build/test-<app_id>-probe.apk`, then device smoke test.
   - *Static fallback*: Check the universal's selectors and fingerprints against the APK recon.
   - *Classification*: Classify each universal as:
     - `NOT_APPLICABLE`: The target APK does not contain matching components, assets, or permissions.
     - `UNIVERSAL_OK`: The universal patch applies cleanly and operates as intended without breaking or degrading functionality.
     - `DEDICATED_NEEDED`: The universal patch breaks or degrades the app, misses app-specific paths, or a targeted hook is clearly more precise and performant. Items classified as `DEDICATED_NEEDED` go to the owning family worker as a dedicated patch.
   - *Offline Applicability Gate*: Author a dedicated offline patch only when the app's core function works without network (offline utilities, local file readers/editors, hardware controllers). Never create an offline patch for apps whose primary function requires network (streaming, social feeds, messaging, browsers).

### Step 3 — Implementation (parallel AGY workers, exclusive paths)
Launch one fresh AGY worker per applicable family with exclusive paths, each loading its family skill (`telemetry-blocking`, `app-debloat`, `compat-bypass`, `privacy-controls`, `ux-declutter`):
- Launch at most three concurrent workers (`agy-orchestrator` limit); queue remaining families until an active worker completes.
- Both/all workers: fresh conversation per worker, `--add-dir` for project + origin reference repo, launch flags and permissions per `agy-orchestrator`, native read/edit only (headless denies RunCommand). Same-scope corrections always resume the same conversation; a failed worker is discarded, never integrated by hand.
- Exclusive paths: workers never touch the same files (e.g. `patches/.../<app>/<App><Family>Patch.kt`).
- Hook selection rules:
  - Never stub methods returning Task/Future/Completable/Observable/Deferred or accepting Callback/Listener/Continuation params (stubbing hangs callers — cut the network transport underneath or invoke the success callback with neutral args instead).
  - Perimeter severing: no hooks on helpers/serializers/queues when the root dispatcher or manifest component is already neutralized — every hook needs extra-package XREFs.
  - Indexed fingerprints only: exact definingClass with `match()`, `classDefBy` scoping, `strings` anchors — never unindexed whole-APK `custom` + `matchAll`.
  - Hosts-rewrite only on isolated host literals or scheme-valid sinks (never bare `0.0.0.0` over full URLs parsed by `Uri` / `HttpUrl`).
  - Coverage matrix per SDK/feature (`MANIFEST_DISABLED` / `STUBBED_VOID` / `HOST_REDIRECTED` / `TRANSITIVELY_DEAD` with file:line) in the worker handoff.
- On `RESOURCE_EXHAUSTED`: checkpoint, rotate via `~/.gemini/config/skills/agy-orchestrator/scripts/switch_account.py auto` (preauthorized), resume same conversation.

### Step 4 — Gates (orchestrator, writes only to gitignored `build/`)
Run in-situ gates sending output to `build/` (gitignored):
1. Patcher execution requires two passes with `-Pout=build/test-<app_id>.apk` (without this flag the runner will not write the output APK):
   - First pass (defaults): `./gradlew runPatchTest -Papp=<app_id> -Papk=<apk> -Pout=build/test-<app_id>.apk`
   - Second pass (all options forced on): `./gradlew runPatchTest -Papp=<app_id> -Papk=<apk> -PallOptions=true -Pout=build/test-<app_id>.apk`
   (100% success, 0 failed patches, 0 fingerprint mismatches, 0 smali compile errors).
   Benchmarked cost (defaults pass): xiaomi_earbuds 32 s / nokoprint 8 s / hevy 8 s; harness 1 s; check 8 s. Both passes stay mandatory — no exemption for small apps (second pass costs ~as much as the first and covers opt-in toggles).
2. RE harness unit tests: `./venv/bin/python -m unittest discover harness/tests`.
3. Project checks: `./gradlew check`.
Injection proof via output-APK manifest dump (`build/test-<app_id>.apk`), never counters alone.

### Step 5 — Device (standing authorization confirmed)
`validation/smoke_install.py` on ABI-matched device points to base plus generated splits for APKM/XAPK targets (glob `build/test-<app_id>*.apk` via `install-multiple`, never base alone when splits exist; `.apk` extension on every split); uninstall after.
Traffic audit (mandatory analysis, never a strings-only pass):
1. Capture with on-device tcpdump on the Wi-Fi interface (`-i wlan0`, EN10MB — never `-i any`/SLL2), detached (`nohup ... >/dev/null 2>&1 &`, stop by PID file, never `pkill -f` pattern which self-matches), time-boxed (not `-c`-truncated), SLL/linktype-aware parsing. Two windows: baseline (app force-stopped, 60 s) and exercise (launch + monkey/clicks through first-run screens, 3+ min, fresh install so TLS hellos fall inside the window). Private DNS forced `off` during capture with mandatory restore (`settings put global private_dns_mode off` / restore `hostname`); per-UID `iptables owner` isolation (ACCEPT app UID, DROP 10000-19999) with counter readout and full rule removal after. UDP/443 DROP to force TCP/TLS is optional (effect unmeasured); lifecycle/job forcing (`jobscheduler run -f`, background/foreground cycles) is pending validation. Analyze with scapy-in-venv or tshark, never a hand-rolled parser as sole evidence.
2. Per-UID attribution via `/proc/net/xt_qtaguid/stats` (root) before/after exercise; report the target UID byte delta.
3. Flow table with IN/OUT packet+byte counts per remote peer:port (direction from SLL ptype, never guessed). TLS SNI per flow via ClientHello extension 0x0000 parsing of reassembled client streams; QUIC (UDP/443) Initial count when present.
4. DNS blind-spot check: state whether port 53 or DoT/DoH (853/443) carried resolution; names resolved under Private DNS are unobservable and must be reported as such.
5. Closed verdicts only (no free-text verdicts): `PASS_VERIFIED` (active 180 s+ exercise, UID/owner-counter delta > 0 proving app connectivity, >=1 functional flow to legit servers, zero flows to known telemetry endpoints, no blind spots); `FAIL_TELEMETRY_DETECTED` (dst ip:port + proto, hostname via SNI/DNS-53/MITM URL, owner-counter attribution, emitter framework named); `AMBIGUOUS_SHARED_HOST` (functional+tracking share host/CDN — PASS forbidden without MITM payload proof or DEX XREF proof that no tracking path builds requests to it; MITM becomes mandatory evidence here); `INCONCLUSIVE_BLIND_SPOT` (empty capture, zero UID delta, Private DNS on, ECH without MITM, or guest-only exercise where login/pairing gates tracking). Abort (never a silent-telemetry claim) if the capture is empty or the hellos predate the window.
A `strings` hostname grep alone is NOT an audit and never closes this step.
Optimal capture stack (use when available, in this order): (a) isolate the app (dedicated profile/device, force-stop everything else, or per-UID VPN capture) since pcap alone cannot attribute flows on a noisy device; (b) `settings put global private_dns_mode off` during the audit to force plaintext port-53 DNS logging; (c) MITM via mitmproxy with user CA (the Network Security patch already trusts user CAs) + block outbound UDP/443 to force TLS over TCP, yielding full URLs/payloads instead of SNI-only; (d) analyze with tshark instead of hand-rolled parsers; (e) exercise authenticated/paired states, not just guest, since backend hosts only appear there.

### Step 6 — Close
One atomic commit per patch/toggle (`feat(<app>)`/`fix(<app>)`, plain ASCII English, no emojis, no attribution), registration and doc guide folded into the first patch commit. Before closing the task, run `audit-stack` over the pending range (e.g. `origin/<base>..HEAD`, never per-commit auto-audit), verifying `git status` clean of task scope while preserving foreign files. NEVER push or open PRs without explicit user instruction.

---

## 2. Scope & Non-Goals

### A. In-Scope Objectives
- Comprehensive onboarding and patching across all five patch families for strictly ONE new target application version:
  1. **Telemetry Blocking**: surgical neutralization of tracking, analytics, attribution, crash-reporting, and advertising SDKs via manifest entrypoint purging, declarative opt-out flags, Dalvik bytecode dispatchers, and native binary host redirection (`libchrome.so`, companion `.so` endpoints).
  2. **Application Debloating**: asset, native binary, locale (`res/values-*/`, `.pak`), density (`drawable-*dpi`), tutorial video/sticker stubbing, background sync elimination, and lossless PNG/WebP image optimization.
  3. **Compatibility & Functioning Bypass**: client-side signature and integrity checks, involuntary store update redirects, sharedUserId conflicts, forced login requirements blocking local utilities, and client-side feature/paywall gates passing the Three-Question Test.
  4. **Privacy Controls**: screen and audio capture protection bypass (`FLAG_SECURE`, `allowAudioPlaybackCapture`), granular permission stripping, opt-in offline mode, network security hardening (user CA trust, certificate pinner neutralization), share-link tracking parameter cleaning, and runtime device-data access neutralization (contacts, location, sensors).
  5. **UX Declutter**: first-party splash/in-feed ads, promotional dialogs, store rating prompts, onboarding and first-run wizard skipping, nag dialogs/popups, and non-essential navigation tabs and buttons.
- Dedicated per-app variants of universal patches where universal implementations break or degrade the app, miss app-specific paths, or where a targeted hook is clearly more precise and performant.

### B. Explicit Non-Goals & Architectural Boundaries
- **Preserve Core Networking**: Never remove `android.permission.INTERNET` or sever primary application network channels outside explicit opt-in offline patches.
- **Preserve Essential App Features**: Never break push notifications (FCM/GCM registration and receivers), deep links, account authentication, session renewal, media playback, billing (`ProxyBillingActivity`), or primary user interactions unless explicitly requested by the user.
- **Strict Prohibition of In-App Settings Screens**:
  - Never inject preference screens, settings activities, floating overlays, or dynamic runtime toggles into target applications.
  - *Rationale*: Dynamic UI panels introduce extreme fragility across weekly upstream obfuscation shifts and add disk I/O on performance-critical paths (authoritative boundary: `docs/out-of-scope.md`).
  - *Controlled Exception (Gboard Lite)*: Gboard Lite is the sole exception where in-app settings are permitted because it exposes standard AndroidX `PreferenceScreen` XML resources and standard IME settings activities.
  - *Standard for All Other Targets*: All configurable parameters must be compile-time / patch-time options via Morphe Manager / CLI (`stringOption`, `booleanOption`).
- **Strict Prohibition of Server-Side Bypasses & DRM**:
  - Never attempt to bypass server-side subscription paywalls, unlock cloud-restricted content, access private accounts, or defeat DRM protections (authoritative boundary: `docs/out-of-scope.md`). Patches operate strictly on client-side bytecode and local assets.
- **Controlled Scope & Client-Side Verification Test**:
  - Any client-side compatibility or entitlement patch must pass the three-question verification test before implementation:
    1. Is the final decision executed locally by the APK's own bytecode or assets?
    2. Does the complete user flow execute entirely on-device?
    3. Does the patch operate without forging network credentials, session tokens, purchase receipts, or remote attestations?
  - **Three-Yes Invariant**: All three questions MUST answer YES. If any question is NO, the patch is strictly out of scope and must not be written.
  - **Truthful Documentation Invariant**: If backend servers continue to reject, restrict, or deny the feature or cloud data, NEVER document or describe the patch as an "unlock" or "subscription bypass". Document it strictly as a client-side UI suppression or local feature gate bypass.
  - **Social & Messaging Guest-Mode Prohibition**: Guest-mode or login-bypass patches are strictly prohibited on social networks and messaging platforms (e.g. Discord, Twitter/X) where client-side sessions are intrinsically tied to server state. When implementing guest mode in permitted local utilities, implement mandatory null-identity guards to prevent crashes.
  - **Default Setting Policy**: Set `default = true` ONLY when the complete user flow is verified on a physical device. Any doubt or lack of hardware validation requires `default = false` (opt-in).
- **Strict Prohibition of Feature Bloat & Download Managers**:
  - Never embed third-party media download engines, torrent clients, or custom UI skins inside host applications.
- **Single Target Version Invariant**:
  - Every target application must target strictly ONE active upstream version.
  - When upstream ships distinct 32-bit and 64-bit builds (e.g. `armeabi-v7a` and `arm64-v8a`), configure a SINGLE `AppTarget` entry for that upstream version with `versionCodes = mapOf(...)` keyed by ABI variant when applicable in `targets = listOf(...)`.
  - Never retain legacy fallback code or multi-version compatibility matrices for older versions. When upstream updates, bump the target version and retire the old version immediately.

---

## 3. Architecture & Compatibility Policy

### A. CPU Architecture Support Matrix
- **`arm64-v8a` (Primary / First-Class)**: Standard 64-bit target for all modern Android devices. All patches, native transforms, and validation runs must target `arm64-v8a` first.
- **`armeabi-v7a` (Legacy 32-bit)**: Supported only when the application provides official 32-bit builds and patches operate strictly on Dalvik bytecode/resources without 64-bit-exclusive native dependencies.
- **`x86` / `x86_64` (Out of Scope)**: Desktop emulator architectures are not supported.

### B. APK Variant Selection
- **Standalone nodpi APK**: Preferred target format whenever available upstream.
- **Split APK Bundles (`.apkm` / `.xapk`)**: Used when upstream distributes only split bundles. Morphe Patcher and the test runner fuse split DEXes and assets into a unified base APK during patching.
- Target compatibility must declare the exact format: `apkFileType = ApkFileType.APK`, `ApkFileType.APKM`, or `ApkFileType.XAPK`.

### C. Universal vs Dedicated Patch Boundary
- **Precision Superset Rule**: Dedicated application patches are a precision superset for their respective targets.
- **Prohibition on Stacking Universals**: Never stack `Universal Telemetry Neutralizer` or `Universal SDK Blocker` on maintained apps. Stacking adds execution time, runs expensive full-DEX scans, and risks breaking features like push notifications or login if generic toggles collide.
- If a newly discovered generic SDK appears in an onboarded app, author the rule directly inside that app's dedicated patch suite.

### D. Core Patch Typologies
- **`bytecodePatch`**: High-level Dalvik AST transforms via dexlib2 fingerprints and instruction injection (`addInstructions(0, "return-void")`).
- **`resourcePatch`**: XML DOM manipulation (`AndroidManifest.xml`, `res/xml/*.xml`) executed prior to DEX assembly.
- **`rawResourcePatch`**: Deterministic byte-level ELF string redirection, companion `.so` zeroing, or asset binary patching.
- Universal patches are ordinary patches that omit `compatibleWith(...)`, making them applicable across any target APK without app-specific obfuscation dependencies. There is no special `universalPatch` typology in the patcher engine.

---

## 4. Recon Procedure

### A. Artifact Placement
Place candidate APK, APKM, or XAPK files into `candidate_apks/` (the Morphe patch runner specifically resolves `candidate_apks/` when running without an explicit `-Papk` parameter). Never commit raw binary APKs to version control.

### B. Badging & Version Metadata Extraction
Extract target package name, version name, version code, and SDK requirements:

```bash
# Resolve aapt2: PATH first, then the newest build-tools under ANDROID_HOME or local.properties sdk.dir.
SDK_DIR="${ANDROID_HOME:-$(sed -n 's/^sdk.dir=//p' local.properties 2>/dev/null | tr -d '\r')}"
AAPT2="$(command -v aapt2 || ls -d "$SDK_DIR"/build-tools/*/aapt2 2>/dev/null | sort -V | tail -n 1)"
[ -x "$AAPT2" ] || { echo "aapt2 not found (set ANDROID_HOME or install build-tools)" >&2; }
"$AAPT2" dump badging candidate_apks/<app>.apk | grep -E "(package: name=|versionCode=|versionName=|sdkVersion:)"
```

Record the following metadata:
- Package name (e.g. `com.example.android`)
- Version name (e.g. `1.2.3.4`)
- Version code (e.g. `12345678`)
- Minimum SDK (e.g. `26`)
- Supported ABIs (e.g. `arm64-v8a`)

### C. Manifest XML Tree Dump
Dump the decoded manifest tree to a scratch path outside git tracking:

```bash
mkdir -p scratch
"$AAPT2" dump xmltree --file AndroidManifest.xml candidate_apks/<app>.apk > scratch/manifest_tree.txt
```

### D. Telemetry Component Inventory
Grep `scratch/manifest_tree.txt` for the six entrypoint categories catalogued in `telemetry-blocking` Section 1.A (permissions, providers, services, receivers/activities, component discovery registrars, startup initializers) and record every match with its exact component name. Apply the preservation rules in `telemetry-blocking` Section 1.C before marking any match for removal.

### E. ML Kit Analysis & Scanner False-Positive Rule
Scanners flag `MlKitInitProvider` and `MlKitComponentDiscoveryService` as trackers, but ML Kit runs on-device and default telemetry patches must keep it. Follow `telemetry-blocking` Section 2.B (an ML Kit slimmer is only allowed as a separate opt-in patch with a breakage warning).

### F. Native Binary Reconnaissance (`lib/<abi>/*.so`)
When the target application bundles native libraries:
1. Inspect bundled native libraries:
   ```bash
   unzip -l candidate_apks/<app>.apk "lib/*"
   ```
2. Scan for embedded telemetry endpoints in native binaries:
   ```bash
   strings -a lib/arm64-v8a/libnative.so | grep -E "(telemetry|analytics|crash|stats|log|metrics)"
   ```
3. Check for standalone crash reporter or profiler `.so` files suitable for companion bloat zeroing (e.g. `libcrashlytics.so`, `libsentry.so`, `libgwp-asan.so`).

When maintaining native binary host redirections across application updates, enforce a structured native ELF audit contract generalized from single-app scanners. Maintain a catalog of known telemetry endpoints with expected occurrence counts per target ABI (e.g. `arm64-v8a`, `armeabi-v7a`). During an update audit, classify findings into offset-change (the domain string persists but shifted position in `.rodata`), vanished (the string was removed or refactored upstream, requiring hook pruning to avoid false assertion failures), and new-candidate discovery (strings matching domain heuristics such as `*telemetry*`, `*collector*`, `*crash*`, `*metrics*` that emerged in the new build). All ELF audit reports and candidate offset tables must be written to `scratch/` (e.g. `scratch/elf_audit_<app>.txt`) and never committed to version control.

### G. Bytecode Scan for Stable SDK Signatures
Scan DEX files with `androguard` to locate stable SDK entrypoints and verify exact Smali descriptors:

```python
# Command run via python virtual environment
./venv/bin/python -c '
from androguard.core.apk import APK
from androguard.core.dex import DEX
apk = APK("candidate_apks/<app>.apk")
for dex_bytes in apk.get_all_dex():
    dex = DEX(dex_bytes)
    for cls in dex.get_classes():
        name = cls.get_name()
        if "analytics" in name.lower() or "measurement" in name.lower():
            for m in cls.get_methods():
                print(f"{name}->{m.get_name()}{m.get_descriptor()}")
' > scratch/sdk_methods.txt
```

Identify stable SDK dispatch points:
- `FirebaseAnalytics.logEvent`: `(Ljava/lang/String; Landroid/os/Bundle;)V` or obfuscated equivalent
- `AppMeasurement.logEventInternal`: `(Ljava/lang/String; Ljava/lang/String; Landroid/os/Bundle;)V`
- App-specific uploader dispatchers: e.g. `IgAnalytics2TaskBasedUploader.HZG` in Instagram

Record exact Smali descriptors:
- Defining class: `Lcom/target/Uploader;`
- Method name: `dispatch`
- Parameter types: `listOf("Ljava/lang/String;", "Landroid/os/Bundle;")`
- Return type: `V` (void) or `Z` (boolean)

### H. Triage Tooling
When signatures shift or cannot be identified via simple grep:
- **`jadx-gui` (Static Triage)**: Open APK in jadx, follow Xrefs from string constants or log messages, and identify the shifted method signature.
- **`frida` / `jnitrace` (Dynamic Lab Triage)**: Attach to the target process on the lab device to confirm whether candidate methods execute during user interactions before writing hooks.

Always store intermediate recon dumps in `scratch/` (ensuring `mkdir -p scratch` first). Never commit raw scan outputs.

### I. Compatibility Blocker Reconnaissance
After analyzing telemetry, investigate client-side post-patch compatibility blockers and functioning gates that prevent the modified application from installing, launching, or operating properly:

1. **Manifest-Level Blocker Scan (`aapt2 dump xmltree`)**:
   - Dump the manifest as shown in Section 4.C and inspect for:
     - Shared User ID conflicts: `android:sharedUserId` (triggers `INSTALL_FAILED_SHARED_USER_INCOMPATIBLE` on modern Android distributions).
     - Store redirect and update activities: activities launching store intents or orphan update services (e.g. `AppUpdateActivity`, `MarketRedirectActivity`).
     - Orphan billing activities: vendor store billing components that fail without host OEM stores. *Rule*: Never disable `com.android.billingclient.api.ProxyBillingActivity` or `ProxyBillingActivityV2`.
     - Intent filter handlers: confirm `android.intent.action.VIEW` filters for web schemes and OAuth redirects remain intact.

2. **Bytecode-Level Gate & Integrity Scan (DEX Scan & jadx)**:
   - Scan DEX bytecodes (using the method scanner in Section 4.G or jadx) for:
     - **Signature & Anti-Tamper Verification**: APK signature hash checks, package manager signature comparisons, emulator/root/Xposed detection classes, and code transparency callback interfaces (`CodeTransparencyCheckCallback`).
     - **Involuntary Store & Market Redirects**: String constants `market://details?id=`, `play.google.com/store/apps/details`, or store intent builders executed on launch or repackage detection.
     - **Mandatory Login & FTUX Gates**: First-Time User Experience (FTUX) wizards or compulsory login listeners that block offline or standalone utility functions.
     - **Client-Side Paywalls & Local Feature Gates**: Boolean getters (`isPro`, `isPaying`, `isSubscribed`, `hasFamilyPlan`), licensing state enums (`LicensingState`), or local paywall activities (`BlockPaywallActivity`).

### J. Behavioral Privacy Recon Checklist (Non-SDK Hardening)
Standard telemetry reconnaissance (Exodus signatures, manifest components, and uploader dispatchers) does not discover first-party behavioral tracking or invasive client features that operate outside commercial SDKs. During application onboarding, audit the decompiled application for the following non-SDK privacy hardening candidates:
- **Sensors & Content-Capture Indicators**: Camera, microphone, and ambient sensor background listeners, motion sensors, screen capture callbacks, or visual content analysis hooks.
- **In-App Browser Guards**: WebViews that inject custom JavaScript bridges, track external link browsing history, or override third-party cookie/storage isolation.
- **Share-URL Tracking Parameters**: Outgoing share intent builders that append tracking identifiers (e.g. `utm_*`, `igshid`, `si`, `fbclid`, or custom attribution query parameters) to shared URLs.
- **Clipboard Access**: Background or unexpected foreground reads from `ClipboardManager` on launch or input focus.
- **GMS / Phenotype Decoupling Candidates**: Hard couplings to Google Play Services Experiment/Phenotype configuration flags that force remote feature rollouts or telemetry overrides.
- **Local History Recording**: Internal SQLite/Room databases or SharedPreferences storing local watch, search, browse, or query histories without user consent.
- **Personalized Search & Feed Algorithms**: Client-side ranking models, behavioral interaction counters, and recommendation logging.
- **P2P Relay & Mesh Networking**: Background peer-to-peer data sharing, local network discovery (mDNS, SSDP), or distributed caching services.
- **On-Device AI Governors**: On-device machine learning models indexing local user data, photos, audio, or text for client-side profiling.
- **Incognito & Private Input Modes**: Keyboard/IME flags, voice typing transmission, or lack of `IME_FLAG_NO_PERSONALIZED_LEARNING` when handling sensitive text fields.

*Scope Invariant*: These behavioral privacy vectors are NOT discovered by the automated Exodus-plus-dispatchers model. Each identified vector represents a separate, dedicated privacy hardening item (often requiring its own independent opt-in patch) and must NEVER be bundled into the primary telemetry suppression patch.

---

## 5. Registration & Documentation Deliverables

Onboarding a new target app requires synchronized deliverables, all committed in the SAME atomic commit as the app's first patch:
1. `Constants.kt` entry inside `object Constants { ... }`
2. `PatchExecutionTest.kt` entry in `TargetApp`
3. `README.md` Supported Apps table update (adhering strictly to repository-specific column schema)
4. `docs/apps/<app_id>.md` comprehensive application guide (including mandatory Behavioral Hazards Warning)
5. `docs/compatibility.md` synchronization when that file exists in the repository

### A. Centralized Constants (`Constants.kt`)
File: `patches/src/main/kotlin/app/morphe/patches/shared/Constants.kt`

Add package name, target version, and `Compatibility` contract inside `object Constants`:

```kotlin
object Constants {
    // ... existing constants ...

    const val <APP>_PACKAGE_NAME = "com.example.android"
    const val <APP>_TARGET_VERSION = "1.2.3.4"

    val COMPATIBILITY_<APP> = Compatibility(
        name = "<App Name>",
        packageName = <APP>_PACKAGE_NAME,
        apkFileType = ApkFileType.APK, // Use ApkFileType.APKM or ApkFileType.XAPK for bundles
        appIconColor = 0x123456,
        targets = listOf(
            AppTarget(
                version = <APP>_TARGET_VERSION,
                description = "Download com.example.android v$<APP>_TARGET_VERSION (APK) from APKMirror",
            )
        )
    )
}
```

**Single Version / ABI Variant Rule**: Maintain strictly ONE upstream version. If upstream ships separate 32-bit and 64-bit APKs, declare a single `AppTarget` entry with `versionCodes = mapOf(...)` keyed by ABI variant under that upstream version.

### B. Runner Registry (`PatchExecutionTest.kt`) & Mapping Invariant
File: `patches/src/main/kotlin/util/PatchExecutionTest.kt`

Every target app establishes a 1:1:1:1 mapping:
- `TargetApp.id`: CLI/runner identifier (e.g. `instagram`, `xiaomi_earbuds`)
- `TargetApp.patchDirectoryPart`: Subdirectory under `patches/src/main/kotlin/app/morphe/patches/` (usually matches `id`, but can diverge, e.g. `xiaomi_earbuds` id pointing to `xiaomi` directory)
- Guide filename: `docs/apps/<id>.md`, with underscores in the id written as hyphens (e.g. `xiaomi_earbuds` -> `docs/apps/xiaomi-earbuds.md`)
- README table row: Target entry matching the target repo's table columns

Add the target to `enum class TargetApp`:

```kotlin
<APP>(
    id = "<app_id>",
    appName = "<App Name>",
    packageName = Constants.<APP>_PACKAGE_NAME,
    candidateFilenames = listOf(
        "<app>_${Constants.<APP>_TARGET_VERSION}.apk",
        "com.example.android_${Constants.<APP>_TARGET_VERSION}.apkm",
    ),
    filePattern = Regex("(?i).*<app_id>.*\\.(?:apk|apkm|xapk)$"),
    patchDirectoryPart = "<app_id>", // e.g. "xiaomi" when id is "xiaomi_earbuds"
),
```

### C. Supported Apps Table (`README.md`)
File: `README.md`

Follow the repository's existing Supported Apps table schema (6 columns):
`| App | Package | Target Version | Variant | Download Source | Guide |`

Example for this repository:
```markdown
| <App Name> | `<package_name>` | <target_version> | APKM bundle (`arm64-v8a`) | [APKMirror](url) | [<App Name> Guide](docs/apps/<app_id>.md) |
```

### D. Application Guide Deliverable (`docs/apps/<app_id>.md`)
File: `docs/apps/<app_id>.md`

Every new application onboarding MUST produce a dedicated guide with this exact structure, including a mandatory **Behavioral Hazards & Warnings** section:

```markdown
# <App Name>: Complete Patch & Architecture Guide

Comprehensive technical, architecture, and patch guide for **<App Name>** (`<package_name>`), covering target requirements, telemetry neutralization, and architectural invariants.

---

## Target & Compatibility

| Property | Value |
| :--- | :--- |
| **Target Application** | <App Name> |
| **Package Name** | `<package_name>` |
| **Supported Target Version** | **`<target_version>`** |
| **Target File Format** | Standalone APK (`APK`) or Bundle (`APKM`/`XAPK`) |
| **Recommended Architecture** | `arm64-v8a` |
| **Official Download Source** | [APKMirror / APKPure](url) |

---

## Applied Patches Catalog

| Patch Name | Type | Category | Default | Primary Mechanism |
| :--- | :--- | :--- | :---: | :--- |
| **Block Telemetry & Trackers** | `bytecodePatch` + `resourcePatch` | Privacy & Telemetry | Yes | Strips advertising permissions, disables analytics services/providers in AndroidManifest.xml, and stubs Dalvik telemetry dispatchers. |

---

## Behavioral Hazards & Warnings

> [!WARNING]
> Document critical user-facing trade-offs, potential upstream breaking points, preserved services (e.g. push tokens, billing), or components that must NOT be removed (e.g. MLKit breakage for QR/barcodes).
> - **Client-Side vs Server-Side Entitlements**: Client-side gates, local license checks, or login requirement screens are neutralized locally on-device. No server-side subscriptions or cloud entitlements are granted or claimed; cloud-synced features and server-backed assets remain subject to backend authorization.

---

## Deep Technical Patch Breakdown

### 1. Block Telemetry & Trackers (`<appId>BlockTelemetryPatch`)
- **Objective**: Neutralize tracking SDKs, analytics dispatchers, and advertising permissions.
- **Manifest Purge**: Strips `AD_ID` and advertising permissions, disables measurement and analytics components, and removes discovery registrars.
- **Bytecode Hooks**: Stubs telemetry dispatch methods with early `return-void`.
```

### E. Package Directory & Extension Payloads
Create the target package directory:
`patches/src/main/kotlin/app/morphe/patches/<patchDirectoryPart>/`

**Extension Payload Invariant**: When bytecode hooks require companion Java/Kotlin runtime logic, always link via `dependsOn(sharedExtensionPatch)` rather than calling `extendWith("extensions/extension.mpe")` directly. Direct calls invoke redundant `ClassMerger` passes and heavily degrade build performance.

**Release Catalog Protection**: Never execute `./gradlew generatePatchesList` in the repository checkout: it rewrites the tracked `patches-list.json`, which is managed strictly by the CI release pipeline.

---

## 6. Implementation Skill Delegation

Implementation across the five patch families is partitioned into dedicated specialized skills. Do not duplicate implementation logic or code snippets across skill definitions.

### A. Telemetry Blocking Implementation (`telemetry-blocking`)
- **When to Invoke**: Invoke when implementing the primary telemetry suppression suite for a target application, including manifest-level permission stripping, component disabling, opt-out metadata injection, and Dalvik bytecode dispatcher stubs.
- **What It Delivers**: manifest purge with the `ManifestXml.kt` helpers, bytecode stubs with the `BytecodeUtils.kt` helpers, direction-inversion and return-type traps, registrar pruning and the ML Kit caveat, multi-return reverse traversal, the DEX hosts-rewrite pattern, the mandatory SDK method exclusion list, the zero-zombie and diagnostic telemetry contracts, and `aapt2` manifest assertions. Reference: `.agents/skills/telemetry-blocking/SKILL.md` (Sections 1, 2, 3, 4).

### B. Application Debloating & Asset Slimming (`app-debloat`)
- **When to Invoke**: Invoke when analyzing or stripping companion native libraries, non-essential asset bundles, multi-language string tables, high-density screen graphics, onboarding videos, editor assets, or background sync schedulers.
- **What It Delivers**:
  - Native binary in-situ zeroing (`file.writeBytes(byteArrayOf())`) for companion AI, VPN, XR, and crash-reporting shared libraries (with `native-binary-patching` for ELF offset rewriting and Hermes HBC patching).
  - Localization slimming for Android `res/values-*/` and Chromium DataPack v5 `assets/locales/*.pak` with safe fallback preservation.
  - Screen density (`drawable-*dpi`, `mipmap-*dpi`) and non-phone UI mode trimming with launcher icon protection and orphan asset preservation.
  - Replacement of heavy onboarding media and editor stickers with minimal container headers and transparent PNG stubs.
  - Background wakeup and periodic sync elimination via `BackgroundSyncPurgePatch` patterns.
  - Lossless PNG recompression and WebP metadata stripping.
  - Guidelines for structuring one independent opt-in patch per debloat axis (`default = false`).
  - Reference: `.agents/skills/app-debloat/SKILL.md` (Sections 1, 2, 3).

### C. Compatibility and Functioning Bypass (`compat-bypass`)
- **When to Invoke**: Invoke when the patched application fails to install, launch, or function properly due to client-side integrity/signature checks, mandatory login requirements blocking local utility, involuntary store redirects, sharedUserId conflicts, or client-side feature/paywall gates.
- **What It Delivers**:
  - Local signature and integrity check neutralization patterns (anti-tamper bypass, code transparency callback stubs, signature spoofing to Google Play Services).
  - Involuntary store-redirect killer patterns without affecting standard `VIEW` deep links or OAuth browser flows.
  - Client-side paywall and local feature gate neutralization patterns (boolean flags, licensing state enums, FTUX dismissals).
  - Conditional guest-mode and login bypass patterns for standalone utilities, with strict exclusion of social and messaging applications (e.g. Discord, Twitter/X) and mandatory null-identity crash guards.
  - Manifest compatibility fixes (stripping `android:sharedUserId`).
  - Strict preservation invariants: never disable `ProxyBillingActivity`, push notifications, or `android.permission.INTERNET`.
  - Default policy guidance: `default = true` strictly requires physical device verification of the full user flow; any doubt or unverified state defaults to `false` (opt-in).
  - Reference: `.agents/skills/compat-bypass/SKILL.md` (Sections 1, 2, 3, 4).

### D. Privacy Controls Implementation (`privacy-controls`)
- **When to Invoke**: Invoke when implementing user-controlled privacy axes for a target application, including screen and audio capture protection bypass, granular permission removal, opt-in offline mode, network security hardening, share-link tracking parameter stripping, and runtime device-data access neutralization.
- **What It Delivers**:
  - Screen and audio capture protection bypass patterns (`FLAG_SECURE` bitmasking `-0x2001`, `allowAudioPlaybackCapture="true"`, `ALLOW_CAPTURE_BY_ALL`, screenshot/recording detection callback stubs) (`privacy-controls` Sections 1, 2.A, 3.A).
  - Granular manifest permission removal across 9 opt-in groups (`stripNotifications`, `stripCamera`, `stripMicrophone`, etc.) with runtime catch safety (`privacy-controls` Sections 1, 2.B, 3.B).
  - Opt-in offline mode via `INTERNET` and network permissions revocation, cleartext blocking, and companion state mocking, governed by the Offline Applicability Gate (`privacy-controls` Sections 1, 2.C, 3.C).
  - Network security hardening (user CA certificate trust anchors in `network_security_config.xml`, cleartext transport policies, and OkHttp `CertificatePinner.check` stubbing) (`privacy-controls` Sections 2.D, 3.D).
  - Share-link tracking parameter stripping and in-app browser WebView neutralization with system browser redirection (`privacy-controls` Sections 2.E, 3.E).
  - Runtime device-data access neutralization (permission framework/denial interception, `ContentResolver.query` contacts filtering with `MatrixCursor`, `PackageManager.queryIntentActivities` package filtering, `LocationManager` and BLE location decoupling, advertising ID and hardware identifier zeroing, motion sensors, battery broadcasts, content capture) (`privacy-controls` Sections 2.F, 3.F).
  - Dedicated variant justification criteria and device verification procedures (`privacy-controls` Sections 4, 5).
  - Reference: `.agents/skills/privacy-controls/SKILL.md`.

### E. UX Declutter Implementation (`ux-declutter`)
- **When to Invoke**: Invoke when neutralizing client-side visual, promotional, onboarding, and navigational friction to create a lean user experience.
- **What It Delivers**:
  - First-party ads neutralization: splash ad preload task stubs and immediate `finish()`, global ad-free state getters (`m4.g(Z)Z`), ad loader completion short-circuiting, in-feed model filtering via runtime extension, and manifest ad component disabling (`ux-declutter` Sections 1, 2.A).
  - Promos, rating/review prompts, and marketing notifications: review dialog eligibility gate suppression, dialog `.show()` stubbing, tag filtering, and retention notification scheduler/alarm cancellation (`ux-declutter` Section 2.B).
  - Onboarding and first-run skipping: first-run flow engine flag overrides (`FirstRunStatus`, `FirstRunFlowSequencer`), SharedPreferences consent auto-accept hooks, non-zero consent timestamps, and onboarding funnel bypass (`ux-declutter` Section 2.C).
  - Nag dialogs and popups: targeted method stubbing (`replaceWithReturnVoid`, `replaceWithReturnBoolean`), semantic PopLayer reflection filter hooks, floating live teaser bubbles, direct system permission request nag bypass, and inline streak reminder filtering (`ux-declutter` Section 2.D).
  - UI element hiding: resource default flipping, PrefService interception, tab protocol disabling, `View.GONE` (`0x8`) visibility overrides, unread badge parameter guarding, and feed search/trending bar stubbing (`ux-declutter` Section 2.E).
  - Engineering contracts (zero-zombie fingerprints, one-axis-per-toggle option standards, surgical diagnostic telemetry, runtime extension payloads with reflection bridges) and verification protocols (`ux-declutter` Sections 3, 4).
  - Reference: `.agents/skills/ux-declutter/SKILL.md`.

---

## 7. Verification Gates

### A. Full-Suite In-Situ Patching Gate
Execute Morphe Patcher against the target APK with all patches active:

```bash
# Execute patch test by registered target app id and candidate APK
./gradlew runPatchTest -Papp=<app_id> -Papk=candidate_apks/<app>.apk

# Force all boolean patch options on (covers opt-in toggles)
./gradlew runPatchTest -Papp=<app_id> -Papk=candidate_apks/<app>.apk -PallOptions=true

# Byte-identical DEX proof for performance or refactor changes
./gradlew runPatchTest -Papp=<app_id> -Papk=candidate_apks/<app>.apk -PdexDigest=build/digest-before.txt
```

#### Quiet Gate Invocation (Agent Standard)
Always redirect full output to a git-ignored file in `build/` and inspect the verdict:
```bash
./gradlew runPatchTest -Papp=<app_id> -Papk=candidate_apks/<app>.apk -PallOptions=true --console=plain > build/patchtest-<app_id>.log 2>&1; rc=$?; sed -n '/FINAL PATCHING RESULT/,$p' build/patchtest-<app_id>.log | grep -v '^\s*at ' || tail -40 build/patchtest-<app_id>.log; echo "exit=$rc"
```

#### Gate Pass Criteria
- Patcher exit code: `0`
- Failed patches: `0`
- Detected Fingerprint Failures: `0`
- Detected Smali Compile Errors: `0`
- Exceptions: `0`

### B. Lint, Unit Tests and Compiler Checks
Run standard project checks and harness unit tests:

```bash
# Unit tests for RE update harness
./venv/bin/python -m unittest discover harness/tests

# Static lint and compilation check (quiet to build/)
./gradlew check --console=plain > build/check.log 2>&1; rc=$?; tail -25 build/check.log; echo "exit=$rc"
```

### C. Injection Proof via Output APK Inspection
Verify modifications on the actual output APK artifacts rather than trusting stdout counters alone:

```bash
# Generate signed and aligned output APK
./gradlew runPatchTest -Papp=<app_id> -Papk=candidate_apks/<app>.apk -Pout=build/test-<app_id>.apk
```

*Note*: `-Pout` specifies the output APK path. Without `-Pout`, the test runner will not write the output APK to disk. For APKM/XAPK split targets, the runner writes the base APK to `build/test-<app_id>.apk` and separate signed splits to `build/test-<app_id>.<split>.apk`.

#### Verification Commands
```bash
SDK_DIR="${ANDROID_HOME:-$(sed -n 's/^sdk.dir=//p' local.properties 2>/dev/null | tr -d '\r')}"
AAPT2="$(command -v aapt2 || ls -d "$SDK_DIR"/build-tools/*/aapt2 2>/dev/null | sort -V | tail -n 1)"
[ -x "$AAPT2" ] || { echo "aapt2 not found (set ANDROID_HOME or install build-tools)" >&2; }

# 1. Verify stripped permissions in output APK
"$AAPT2" dump xmltree --file AndroidManifest.xml build/test-<app_id>.apk | grep -E "E: uses-permission.*android:name.*(AD_ID|ACCESS_ADSERVICES)"

# 2. Verify disabled components have android:enabled="false" (0x0)
"$AAPT2" dump xmltree --file AndroidManifest.xml build/test-<app_id>.apk | grep -B 2 -A 5 "AppMeasurementService"

# 3. Verify injected opt-out metadata
"$AAPT2" dump xmltree --file AndroidManifest.xml build/test-<app_id>.apk | grep -B 2 -A 5 "firebase_analytics_collection_enabled"
```

Assert that:
- Blocked permissions are completely absent from the dump.
- Blocked components contain `A: android:enabled(0x0101000e)=0x0`.
- Injected metadata flags are present.

### D. Reverse Engineering Harness Usage (Version Bumps)
For target applications integrated with the automated update harness (`harness/update.py`):
```bash
# Run preflight environment check
./venv/bin/python harness/update.py --doctor

# Non-destructive audit of a new target APK version
./venv/bin/python harness/update.py candidate_apks/<new-apk> --audit
```
*Note*: Applications without a dedicated harness pipeline are audited manually and validated via `./gradlew runPatchTest -Papp=<app_id>`.

---

## 8. Device Validation & Traffic Audit

### A. Automated ADB Smoke Install Gate
Use `validation/smoke_install.py` against a connected Android device matching the target ABI (`arm64-v8a`) and minimum SDK. Install the generated APK(s) in `build/`: for standalone APKs, pass the single `build/test-<app_id>.apk`; for APKM/XAPK targets where split APKs were produced (`build/test-<app_id>.<split>.apk`), pass both base and all generated splits (`build/test-<app_id>*.apk`) so `smoke_install.py` performs an `install-multiple`:

```bash
# Single standalone APK or base plus splits
./venv/bin/python validation/smoke_install.py build/test-<app_id>.apk --uninstall-on-conflict

# Multiple APKs (base + splits for bundle targets)
./venv/bin/python validation/smoke_install.py build/test-<app_id>*.apk --uninstall-on-conflict

# Explicit device serial if multiple devices are attached
./venv/bin/python validation/smoke_install.py build/test-<app_id>*.apk --serial <serial> --uninstall-on-conflict
```

#### Post-Test Cleanup
Keep the test install on the device; reinstall with `-r` on the next run to preserve data. The standing device authorization in `AGENTS.md` permits `adb uninstall` of the package under validation only when a signature or split conflict blocks installation, which `--uninstall-on-conflict` already handles.

### B. Physical Device Comparative Validation
For non-trivial telemetry, background sync, and compatibility bypass modifications, perform a comparative run (Vanilla vs Patched) on the physical lab device:
1. Run vanilla APK: exercise user flows, measure background jobs and telemetry dispatch, and record default gate/login/license behavior.
2. Run patched APK: confirm telemetry endpoints remain silent, bypassed gates function as intended, and the application functions with zero crashes.
3. **State Persistence & Cold Restart Verification**: For compatibility and bypass modifications, verify that bypassed gates, local entitlements, or guest session states persist across:
   - Cold app restarts (`am force-stop` followed by launcher restart).
   - Task eviction (swiping away from recents).
   - Cache clearance and device reboot.
   Assert that the app does not regress to a locked state, show unhandled `NullPointerException`, or attempt invalid background synchronizations upon reopening.

### C. Runtime Traffic Audit (Optional Tooling)
Runtime packet capture audits require `tcpdump` on the device and optional analysis tools (`tshark`). Note that `tcpdump` and `tshark` are optional tools that may not be available in standard PATH environments.

```bash
# 1. Verify tcpdump exists on the device; skip the audit (do not exit the shell) when it is missing
if ! adb -s <serial> shell "command -v tcpdump || ls /data/local/tmp/tcpdump" >/dev/null 2>&1; then
    echo "tcpdump not found on device; skipping traffic capture"
else
    # 2. Start a bounded capture on the device in the background
    adb -s <serial> shell su -c "tcpdump -i any -s 0 -c 1000 -w /data/local/tmp/traffic.pcap" &

    # 3. Launch the patched app and exercise standard user flows
    adb -s <serial> shell monkey -p <package_name> -c android.intent.category.LAUNCHER 1
    sleep 30

    # 4. Stop the capture, pull the pcap, and remove it from the device
    adb -s <serial> shell su -c "pkill -f 'tcpdump -i any'"
    wait
    adb -s <serial> pull /data/local/tmp/traffic.pcap scratch/traffic.pcap
    adb -s <serial> shell su -c "rm -f /data/local/tmp/traffic.pcap"

    # 5. An empty or missing capture is a failed audit, never evidence of silent telemetry
    if [ ! -s scratch/traffic.pcap ]; then
        echo "ERROR: packet capture empty or missing; traffic audit FAILED" >&2
    fi
fi
```

**Never Commit PCAPs**: `.pcap` capture files must stay in `scratch/` or git-ignored paths and must never be committed.

#### Protocol & Host Inventory Extraction (when tshark is available)
```bash
if command -v tshark >/dev/null 2>&1; then
    # Extract TLS Server Name Indication (SNI) hostnames
    tshark -r scratch/traffic.pcap -Y "tls.handshake.type == 1" -T fields -e tls.handshake.extensions_server_name | sort -u

    # Extract QUIC Initial packet server names (HTTP/3 traffic)
    tshark -r scratch/traffic.pcap -Y "quic" -T fields -e quic.tls.handshake.extensions_server_name | sort -u
fi
```

#### Traffic Audit Caveats & Blind Spots
When reporting network audit results, always document technical blind spots:
1. **Empty Capture Hazard**: Never interpret an empty pcap file or failed capture run as proof that telemetry is silent. Abort report if capture failed.
2. **QUIC / HTTP/3 Traffic**: UDP port 443 traffic bypasses standard HTTP/HTTPS forward proxies unless UDP 443 is blocked or intercepted at the firewall. Inspect QUIC Initial frames directly.
3. **Encrypted Client Hello (ECH)**: TLS 1.3 connections negotiating ECH encrypt the inner SNI, exposing only outer provider hostnames.
4. **DNS-over-TLS (DoT) / DNS-over-HTTPS (DoH)**: Android Private DNS encrypts DNS resolution over port 853 or port 443. Queries do not appear in standard plaintext UDP 53 captures.
5. **Evidence Standard**: Report observed hostnames and explicit caveats. Never claim "100% telemetry blocked" beyond the empirical evidence collected from traffic dumps.

---

## 9. Closing Protocol

### A. Mandatory Atomic Commits & Vertical Slices
Every completed unit of work must be committed immediately as an isolated, independent commit.

1. **Initial App Onboarding Commit (Vertical Slice)**:
   - Scope: Target app registration (`Constants.kt`, `PatchExecutionTest.kt`, `README.md`) + dedicated app guide (`docs/apps/<app_id>.md`) + initial telemetry patch implementation (`patches/.../<app_id>/...`).
   - Format: `feat(<app_id>): add block telemetry patch`
2. **Subsequent Feature / Opt-In Patch Commits**:
   - Scope: Standalone opt-in patch (e.g. MLKit slimmer) + accompanying documentation updates in `docs/apps/<app_id>.md`.
   - Format: `feat(<app_id>): add mlkit vision slimmer patch`
3. **Bugfix Commits**:
   - Scope: Standalone fix for a shifted fingerprint or broken component.
   - Format: `fix(<app_id>): update uploader fingerprint for <version>`

### B. Commit Message & Push Rules
Commit format, language, attribution, direct-commit and push/PR rules are defined in `AGENTS.md` (rules 14 and 15) and the `release-conventions` skill; follow them exactly.

### C. Mandatory Post-Close Adversarial Audit (audit-stack)
After all commits in A are landed, automatically run the `audit-stack` skill against the onboarding changeset before closing the task (auditing the pending range, e.g. `origin/<base>..HEAD`). Never run per-commit auto-audits.
1. **Scope**: Strictly the onboarding scope -- `patches/.../<app_id>/`, `docs/apps/<app_id>.md`, and the app's hunks in `Constants.kt` / `PatchExecutionTest.kt` / `README.md`. Explicitly exclude `FOREIGN_IN_PROGRESS_WORK` (uncommitted files and directories outside the app scope); never stage, modify, or report foreign work as part of this audit.
2. **Remediation precedence**: `audit-stack` applies fixes through whatever implementation workflow is configured for the local harness (for example a delegated worker); this skill does not define who edits files.
3. **Fix commits**: Each confirmed fix lands as its own `fix(<app_id>): ...` commit after re-running the Section 7 gates. Loop until the audit reports zero blocking findings.
4. No push / no PR (per B).
