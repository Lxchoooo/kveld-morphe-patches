---
name: morphe-patcher
description: Morphe patch architecture and DSL reference (bytecodePatch, resourcePatch, rawResourcePatch, universal patches, booleanOption and stringOption, fingerprints, Constants.kt compatibility, diagnostic telemetry). Use when creating or modifying any patch, fingerprint, patch option or compatibility target.
---

<!-- Shared skill: canonical source is kveld-morphe-patches; scripts/sync_shared_skills.sh mirrors it byte-identically into kveld-extra-morphe-patches (.claude/skills is a symlink to .agents/skills in each repo). Edit only in kveld-morphe-patches; the sibling pre-commit hook rejects direct edits. -->

# Morphe Patcher Architectural Guidelines

## 1. Patch DSL & Typology

Morphe patches are declared using functional Kotlin builder DSLs provided by `app.morphe.patcher.patch`:

### A. `bytecodePatch`
Primary tool for Dalvik/Smali AST bytecode transformations via dexlib2 fingerprints and instructions.
```kotlin
val myPatch = bytecodePatch(
    name = "Unique Patch Name",
    description = "Concise technical description of the modification.",
    default = true // Whether enabled by default in Morphe Manager
) {
    compatibleWith(Constants.COMPATIBILITY_BRAVE)
    dependsOn(companionResourcePatch) // Optional dependency execution

    execute {
        // Fingerprinting and instruction insertion
    }
}
```

### B. `resourcePatch`
Used for parsing and transforming decompiled Android resource XML files prior to DEX assembly.
```kotlin
val myResourcePatch = resourcePatch(
    name = "Resource Defaults Patch",
    description = "Overwrites default XML attributes.",
    default = false
) {
    compatibleWith(Constants.COMPATIBILITY_BRAVE)

    execute {
        val targetFile = get("res/xml").listFiles()
            ?.firstOrNull { it.extension == "xml" && it.readText().contains("target_key") }
            ?: return@execute

        document(targetFile.absolutePath).use { doc ->
            val nodes = doc.getElementsByTagName("SwitchPreference")
            for (i in 0 until nodes.length) {
                val elem = nodes.item(i) as? Element ?: continue
                if (elem.getAttribute("android:key") == "target_key") {
                    elem.setAttribute("android:defaultValue", "true")
                }
            }
        }
    }
}
```

### C. `rawResourcePatch`
Direct byte-level modification of bundled binary shared libraries (`.so`) or uncompressed assets (`assets/index.android.bundle`).
```kotlin
val myNativePatch = rawResourcePatch(
    name = "Native Hardening Patch",
    description = "Direct binary patching of libchrome.so",
    default = false
) {
    compatibleWith(Constants.COMPATIBILITY_BRAVE)

    execute {
        val soFile = get("lib/arm64-v8a/libchrome.so")
        if (!soFile.exists()) return@execute
        // Validate offsets and mutate bytes via RandomAccessFile
    }
}
```

---

## 2. Compatibility Scope & Universal Patches

Compatibility is configured via `compatibleWith(...)`:

- **Single Target**:
  ```kotlin
  compatibleWith(Constants.COMPATIBILITY_BRAVE)
  ```
- **Multi-Compatibility Varargs**:
  Accepts multiple `Compatibility` contracts for cross-target or dual-package applications:
  ```kotlin
  compatibleWith(targetA, targetB)
  ```
- **Universal Patches**:
  **Omitting `compatibleWith(...)`** entirely produces a universal patch (e.g. `LocaleResourceSlimmerPatch`, `DpiResourceSlimmerPatch`). Universal patches are offered across all target applications in Morphe Manager and the CLI patcher. In kveld-morphe-patches, universal patch sources live in `app.morphe.patches.universal`; `app.morphe.patches.shared` holds only contracts and helpers in both repositories.

---

## 3. User Configurable Options (`booleanOption` / `stringOption` DSL)

Patches expose patch-time settings in Morphe Manager or CLI through option property delegates. Use `booleanOption` for toggles and `stringOption` for free-form values:

```kotlin
import app.morphe.patcher.patch.booleanOption

val blockOffersHost by booleanOption(
    key = "blockOffersHost",
    default = true,
    title = "Block offers server",
    description = "Also blocks the shopping offers server. Turn off to keep it.",
    required = false,
)
```

```kotlin
import app.morphe.patcher.patch.stringOption

val targetLocales by stringOption(
    key = "locales",
    title = "Locales to keep",
    description = "Comma-separated language codes to preserve (e.g. 'en, es, pt, fr, de'). English fallback is always retained.",
    default = "en",
    required = false,
)
```

Code behind a disabled-by-default option is only exercised by `runPatchTest -PallOptions=true`; run it whenever such code changes.

### Metadata Synchronization Rule
When patch options, descriptions, titles, or defaults are added or modified in Kotlin code, verify catalog registration by running the patch list generator against the built `.mpp` from a temporary working directory outside the repository, and confirm the expected entries appear. Do NOT run `./gradlew generatePatchesList` in the repository checkout: it rewrites the tracked `patches-list.json`, which the release pipeline regenerates (see `AGENTS.md`, rule 11).

---

## 4. Fingerprint Resolution Strategies

Fingerprints locate target methods across obfuscated versions without hardcoding method names:

> **Scan cost:** a fingerprint without `strings` or an exact `definingClass` walks every method of the APK. Follow the measured rules in `AGENTS.md` Section 2, item 5 (one candidate scan per target family, cheap checks first, iterate only the member kind needed, scope `matchAll()` with `classDefBy(TYPE)`, prefer indexed filters, prove performance-only changes with `-PdexDigest`).

1. **String Literals**: Most resilient anchor. Locate methods referencing unique log strings or preference keys.
   ```kotlin
   Fingerprint(
       returnType = "V",
       strings = listOf("brave.origin.package_name_android", "brave.origin.product_id_android")
   )
   ```

2. **Signature & Parameter Filtering**: Match methods by strict parameter and return type signatures.
   ```kotlin
   Fingerprint(
       returnType = "Z",
       parameters = listOf("Lorg/chromium/chrome/browser/profiles/Profile;"),
       strings = listOf("getIsSubscriptionActive profile is null")
   )
   ```

3. **Instruction Filters & Register Sniffing**:
   ```kotlin
   val fp = Fingerprint(
       definingClass = "Lorg/chromium/chrome/browser/settings/BraveOriginPreferences;",
       returnType = "V",
       parameters = listOf("Ljava/lang/String;", "Landroid/os/Bundle;"),
       filters = listOf(
           methodCall(definingClass = "Lcom/target/Class;", name = "predicate", returnType = "Z")
       )
   )
   val matchIndex = fp.instructionMatches.first().index
   val targetReg = fp.method.getInstruction<OneRegisterInstruction>(matchIndex + 1).registerA
   ```

   > **Runtime safety (device-proven):** hook insert-only after `move-result`, reusing existing registers. Removing and re-adding a lone invoke, or growing the register frame while original instructions remain, passes `runPatchTest` and crashes on device with `VerifyError`; whole-body replacement through the `replaceWith*` helpers is safe. Details: `smali-bytecode-hooks` skill, Section 6.

---

## 5. Metadata Contracts (`Constants.kt`)

Every patch must reference the shared compatibility object defined centrally in `Constants.kt`. Never inline `Compatibility(...)` objects.

Active targets are defined in each repository's `Constants.kt` as `COMPATIBILITY_<APP>`; add new ones there. Code examples in this skill come from kveld-morphe-patches and use its Brave target for illustration.

**Single Target Version Invariant**: Every target app maintains strictly ONE active version (the latest supported release) in `targets = listOf(AppTarget(...))`. Never retain older versions or multi-version entries in `targets`.

---

## 6. Diagnostic Telemetry Invariants & Harness Compliance

Every patch execution must emit concise, high-signal diagnostic telemetry captured by Morphe Manager / CLI logs (`[WARN] [STDIO]: [...]`). Patches must satisfy the following invariants tested by RE and audit harnesses:

1. **Standardized Prefix**: Every log line must start with the bracketed patch name prefix: `println("[Patch Name] ...")`.
2. **Dynamic Mutation Counter**: Track injected modifications with a local counter:
   ```kotlin
   var patched = 0
   ```
3. **Development Triage vs Final Zero-Mismatch Gate**: Wrap risky hook/fingerprint blocks in `try/catch` during development to allow partial degradation and pinpoint shifting targets without halting the suite prematurely:
   ```kotlin
   try {
       // fingerprint resolution and hook injection
       patched++
   } catch (e: Exception) {
       println("[Patch Name] Component note: ${e.message}")
   }
   ```
   **CRITICAL GATE**: Prior to final verification, committing, or release, every single fingerprint failure (`Failed to match the fingerprint`) MUST be resolved to the new shifted target or pruned if the feature was deleted upstream. Retaining failing fingerprints in production/committed code is strictly forbidden.
4. **Consolidated Summary Log**: Emit a quantifiable summary upon completing operations:
   ```kotlin
   println("[Patch Name] Successfully applied $patched hooks across target components.")
   ```
5. **Anti-Spam & Bounded Output**: Never dump thousands of lines or unbounded file trees. Repetitive items must be summarized or bounded to short representative samples (e.g. `.take(6)`).
6. **Failure & Guard Transparency**: If an operation is skipped or safely aborted (e.g. missing targets or preconditions), log an explicit descriptive reason so issues can be immediately diagnosed from user-submitted logs.
7. **Zero Emojis Policy**: Never use emojis in telemetry logs, exceptions, or console output. All logging must use clean, standard ASCII / plain-text formatting (e.g. `[INFO]`, `[WARN]`, `[PASS]`, `[FAIL]`).

---

## 7. Mandatory Verification Gate

Static checks are never enough. Run the in-situ patching gate defined in `AGENTS.md` (Section 3, Step 4): `./gradlew runPatchTest -Papp=<targetApp>` (`<targetApp>` is a `TargetApp` id registered in `PatchExecutionTest.kt`), adding `-PallOptions=true` when the change sits behind an option.
