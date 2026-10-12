---
name: smali-bytecode-hooks
description: Smali and Dalvik hooking rules (register conventions, whole-body replacement helpers, multi-return reverse traversal, register extraction, branch polarity, reflection bridges, device-only VerifyError traps). Use when writing or reviewing inline smali, addInstructions calls or register-level hooks.
---

<!-- Shared skill: canonical source is kveld-morphe-patches; scripts/sync_shared_skills.sh mirrors it byte-identically into kveld-extra-morphe-patches (.claude/skills is a symlink to .agents/skills in each repo). Edit only in kveld-morphe-patches; the sibling pre-commit hook rejects direct edits. -->

# Smali & Dalvik Bytecode Hooking Guidelines

## 1. Register Architecture & Essential Extension Imports

In Dalvik bytecode, register naming follows strict calling conventions:
- **`p0`**: Represents `this` in instance methods, or the 1st parameter in static methods.
- **`p1, p2, ...`**: Subsequent incoming method arguments.
- **`v0, v1, ...`**: Local registers allocated for computation within the method frame.

### Required Patcher Extension Imports
Always import the core instruction helper extensions from `app.morphe.patcher`:
```kotlin
import app.morphe.patcher.extensions.InstructionExtensions.addInstructions
import app.morphe.patcher.extensions.InstructionExtensions.addInstructionsWithLabels
import app.morphe.patcher.extensions.InstructionExtensions.getInstruction
```

### Safe Return Overrides
When replacing a complete method body, use the shared helpers in `app.morphe.patches.shared` (`BytecodeUtils.kt`): `replaceWithReturnVoid()`, `replaceWithReturnBoolean(value)`, `replaceWithReturnInt(value)`, `replaceWithReturnNull()`, `replaceWithReturnBooleanObject(value)`, `replaceWithReturnIntegerObject(value)`, `replaceWithReturnEmptyList()`. They clear try blocks before wiping the body (dangling try ranges cause ART `VerifyError`) and make sure the frame holds the registers the new body uses:
```kotlin
import app.morphe.patches.shared.replaceWithReturnBoolean

fingerprint.method.replaceWithReturnBoolean(true)
```
For a custom whole-body replacement without a helper, keep the same order: `clearTryBlocks()`, `ensureRegisterCount(n)`, `removeInstructions(0, count)`, then `addInstructions(0, ...)`.

---

## 2. Multi-Return Hooking & Reverse Traversal

When modifying or injecting hooks before return instructions (`return-void`, `return-object`, `return`), inserting instructions shifts the indices of all subsequent instructions within the method.

To maintain valid AST offsets without invalidating subsequent indices, **always collect return indices and iterate in reverse order** using `.asReversed()`:

```kotlin
val method = fingerprint.method
val returnIndices = method.implementation?.instructions?.withIndex()
    ?.filter { it.value.opcode == Opcode.RETURN_OBJECT }
    ?.map { it.index to (it.value as OneRegisterInstruction).registerA }
    ?.toList() ?: emptyList()

// Reverse iteration prevents index shifting
returnIndices.asReversed().forEach { (returnIndex, reg) ->
    method.addInstructions(
        returnIndex,
        """
            invoke-static {v$reg}, Lcom/kveld9/morphe/extension/Payload;->filter(Ljava/lang/Object;)V
        """.trimIndent(),
    )
}
```

---

## 3. Register Extraction & Instruction Sniffing

Never hardcode register numbers when modifying intermediate instructions. Extract dynamically allocated registers directly from the dexlib2 AST instruction nodes:

### `OneRegisterInstruction`
Applies to instructions with a single register reference (e.g. `return-object`, `move-result`, `check-cast`):
```kotlin
import com.android.tools.smali.dexlib2.iface.instruction.OneRegisterInstruction

val matchIndex = fingerprint.instructionMatches[0].index
val resultReg = fingerprint.method
    .getInstruction<OneRegisterInstruction>(matchIndex + 1).registerA

fingerprint.method.addInstructions(matchIndex + 2, "const/4 v$resultReg, 0x0")
```

### `TwoRegisterInstruction`
Applies to instructions with two register references (e.g. `iput`, `iget`, `iput-boolean`, `instance-of`):
- `registerA`: Destination/source data register (`vx`).
- `registerB`: Target instance/object reference register (`vy`).
*(Note: `check-cast` uses format 21c and is a `OneRegisterInstruction` with a type reference).*

```kotlin
import com.android.tools.smali.dexlib2.iface.instruction.TwoRegisterInstruction

// Example: Neutralizing a boolean field write (iput-boolean vx, vy, Field)
val putIndex = fingerprint.instructionMatches[1].index
val instruction = fingerprint.method.getInstruction<TwoRegisterInstruction>(putIndex)
val putReg = instruction.registerA      // Data value register (vx)
val objReg = instruction.registerB      // Object instance register (vy)

fingerprint.method.addInstructions(putIndex, "const/4 v$putReg, 0x0")
```

---

## 4. Multi-Branch & Label Management

Use `addInstructionsWithLabels` when introducing branching logic (`if-eqz`, `if-nez`, `goto`) to guarantee proper branch label target resolution and relative offset recalculation:

To branch back into the original body, bind an `ExternalLabel` to an existing instruction instead of declaring the label inside the injected smali (production use: `NokoPrintSkipWelcomeDialogPatch.kt`):

```kotlin
import app.morphe.patcher.util.smali.ExternalLabel

// Instance method: p0 = this, p1 = first argument. A null argument skips the original body.
method.addInstructionsWithLabels(
    0,
    """
    if-nez p1, :original
    return-void
    """.trimIndent(),
    ExternalLabel("original", method.getInstruction(0)),
)
```

### Branch Polarity Rule (blocking correctness invariant)
- `if-eqz vX, :label` jumps when the value is 0/null; `if-nez vX, :label` jumps when non-zero/non-null. Suppress-on-PRESENT means `if-nez → suppress`; skip-on-ABSENT means `if-eqz → continue`.
- Null receivers must never enter check blocks: restructure `if-eqz v1, :check` + `goto :continue` into `if-eqz v1, :continue` with fall-through into the checks (a `contains()`/`invoke` on null throws NPE at runtime).
- Prefer branchless designs (const-zeroing before `iput`, early `return` with verified return type); they are immune to this bug class.
- Evidence (X 12.33.0, 2026-10-10): a full filter layer shipped with systematically inverted branches; `runPatchTest` (assembly-only) and process-alive smoke both passed. Polarity must be verified by reading, never inferred from green gates.

---

## 5. Dynamic Reflection Bridges & Obfuscation Caveats

When accessing private fields or methods across DEX boundaries where direct invocation causes `IllegalAccessError`, use reflection bridges:

```smali
invoke-virtual {p0, p1}, Lorg/chromium/chrome/browser/settings/Preferences;->findPreference(Ljava/lang/CharSequence;)Landroidx/preference/Preference;
move-result-object v0
if-eqz v0, :done
move-object v3, p0
const-string v1, "mListener"
const-class v2, Landroidx/preference/Preference;
invoke-virtual {v2, v1}, Ljava/lang/Class;->getDeclaredField(Ljava/lang/String;)Ljava/lang/reflect/Field;
move-result-object v1
const/4 v2, 0x1
invoke-virtual {v1, v2}, Ljava/lang/reflect/Field;->setAccessible(Z)V
invoke-virtual {v1, v0, v3}, Ljava/lang/reflect/Field;->set(Ljava/lang/Object;Ljava/lang/Object;)V
:done
return-void
```

### Obfuscation Warning & Guidelines
- Obfuscated identifiers (such as `P4`, `y`, `O0`) are volatile and change between releases.
- Always prefer anchoring on **stable framework APIs** (e.g. `androidx.preference.Preference`) or string literals.
- When obfuscated symbols are strictly necessary, isolate them in centralized contracts or verify them via RE audit scripts (`harness/update.py --audit`) against newly updated APKs before building.

---

## 6. Mandatory In-Situ Patcher Verification Gate

Any modified Smali hook, register rewrite, or fingerprint must pass the `runPatchTest` gate in `AGENTS.md` (Section 3, Step 4), including its zero-smali-compile-error rule (non-range invokes only address `v0`-`v15`).

> **Runtime safety (device-proven):** a green `runPatchTest` proves assembly only. Two patterns pass the gate and still crash on device with `VerifyError`:
> - Removing and re-adding a single invoke inside a live body (`removeInstructions` + `addInstructions` at one index): branches that targeted the invoke are re-linked to the following `move-result`, which ART rejects (`invalid use of move-result`). Insert after the `move-result` instead, reusing existing registers.
> - Growing the register frame (`ensureRegisterCount`) while original instructions remain: already encoded parameter registers are not remapped, so `p` registers resolve to undefined slots. Growing the frame is safe only when the whole body is replaced (Section 1, Safe Return Overrides).
