/*
 * Copyright 2026 Morphe.
 * https://github.com/MorpheApp/morphe-patches/pull/2470
 *
 * Original code hard forked from:
 * https://github.com/ReVanced/revanced-patches/blob/724e6d61b2ecd868c1a9a37d465a688e83a74799/patches/src/main/kotlin/app/revanced/patches/all/misc/versioncode/ChangeVersionCodePatch.kt
 *
 * File-Specific License Notice (GPLv3 Section 7 Terms)
 *
 * This file is part of the Morphe project and is licensed under
 * the GNU General Public License version 3 (GPLv3), with the Additional
 * Terms under Section 7 described in the LICENSE file.
 *
 * https://www.gnu.org/licenses/gpl-3.0.html
 *
 * Section 7b: Notice Preservation
 * -------------------------------
 * This entire comment block must be preserved in all copies,
 * distributions, and derivative works of this file, in both
 * original and modified source forms.
 *
 * Portions of this software are provided "AS IS" by the Morphe software project.
 * Any express or implied warranties, including the implied warranties of
 * merchantability and fitness for a particular purpose, are disclaimed.
 */

package app.morphe.patches.universal

import app.morphe.patcher.extensions.InstructionExtensions.addInstruction
import app.morphe.patcher.extensions.InstructionExtensions.addInstructions
import app.morphe.patcher.extensions.InstructionExtensions.instructionsOrNull
import app.morphe.patcher.extensions.InstructionExtensions.removeInstructions
import app.morphe.patcher.extensions.InstructionExtensions.replaceInstruction
import app.morphe.patcher.patch.bytecodePatch
import app.morphe.patcher.patch.resourcePatch
import app.morphe.patcher.util.proxy.mutableTypes.MutableMethod
import app.morphe.patches.shared.ANDROID_XML_NAMESPACE
import app.morphe.patches.shared.clearTryBlocks
import app.morphe.patches.shared.ensureRegisterCount
import app.morphe.patches.shared.sharedExtensionPatch
import com.android.tools.smali.dexlib2.Opcode
import com.android.tools.smali.dexlib2.iface.ClassDef
import com.android.tools.smali.dexlib2.iface.Method
import com.android.tools.smali.dexlib2.iface.instruction.FiveRegisterInstruction
import com.android.tools.smali.dexlib2.iface.instruction.Instruction
import com.android.tools.smali.dexlib2.iface.instruction.ReferenceInstruction
import com.android.tools.smali.dexlib2.iface.instruction.RegisterRangeInstruction
import com.android.tools.smali.dexlib2.iface.instruction.TwoRegisterInstruction
import com.android.tools.smali.dexlib2.iface.reference.FieldReference
import com.android.tools.smali.dexlib2.iface.reference.MethodReference

private const val EXTENSION_CLASS = "Lcom/kveld9/morphe/extension/DisablePlayStoreUpdatesPatch;"

private var originalVersionCode: Int = 0

@Suppress("unused")
private val disablePlayStoreUpdatesResourcePatch = resourcePatch {
    execute {
        val manifestFile = get("AndroidManifest.xml")
        if (!manifestFile.exists()) {
            println("[Disable Play Store updates] Skipped: AndroidManifest.xml not found.")
            return@execute
        }

        document(manifestFile.absolutePath).use { doc ->
            val manifest = doc.documentElement
            val raw = manifest.getAttribute("android:versionCode").takeIf { it.isNotBlank() }
                ?: manifest.getAttributeNS(ANDROID_XML_NAMESPACE, "versionCode").takeIf { it.isNotBlank() }
                ?: manifest.getAttribute("versionCode").takeIf { it.isNotBlank() }
                ?: "0"

            originalVersionCode = raw.toIntOrNull() ?: 0
            if (originalVersionCode == 0) {
                println("[Disable Play Store updates] Warning: manifest versionCode missing or unparsable, using 0.")
            }
        }
    }

    finalize {
        val manifestFile = get("AndroidManifest.xml")
        if (!manifestFile.exists()) {
            return@finalize
        }

        document(manifestFile.absolutePath).use { doc ->
            val manifest = doc.documentElement
            manifest.setAttribute("android:versionCode", Int.MAX_VALUE.toString())
        }
    }
}

@Suppress("unused")
val universalDisablePlayStoreUpdatesPatch = bytecodePatch(
    name = "Disable Play Store updates",
    description = "Disables Play Store updates by setting the version code to the maximum allowed.",
    default = false,
) {
    dependsOn(disablePlayStoreUpdatesResourcePatch)
    dependsOn(sharedExtensionPatch)

    finalize {
        val extClass = mutableClassDefByOrNull(EXTENSION_CLASS)
        val originalVersionMethod = extClass?.methods?.firstOrNull { it.name == "originalVersionCode" }
        if (originalVersionMethod != null) {
            val impl = originalVersionMethod.implementation
            if (impl != null) {
                originalVersionMethod.clearTryBlocks()
                originalVersionMethod.ensureRegisterCount(1)
                originalVersionMethod.removeInstructions(0, impl.instructions.count())
                originalVersionMethod.addInstructions(0, "const v0, $originalVersionCode\nreturn v0")
            }
        }

        var patched = 0
        var versionCodeFieldHooks = 0
        var longVersionCodeHooks = 0
        var touchedClasses = 0

        classDefForEach { classDef ->
            if (classDef.type.startsWith("Lcom/kveld9/morphe/extension") ||
                classDef.type.startsWith("Lapp/morphe/extension")
            ) {
                return@classDefForEach
            }
            if (!hasAnyTargetInstruction(classDef)) return@classDefForEach

            val mutableClass = mutableClassDefBy(classDef)
            var classModified = false

            mutableClass.methods.forEach { method ->
                val mutations = scanMethodMutations(method)
                if (mutations.isNotEmpty()) {
                    classModified = true
                    applyMutations(method, mutations) { type ->
                        when (type) {
                            MutationType.FIELD_ACCESS -> versionCodeFieldHooks++
                            MutationType.LONG_METHOD_CALL -> longVersionCodeHooks++
                        }
                        patched++
                    }
                }
            }

            if (classModified) {
                touchedClasses++
            }
        }

        if (patched == 0) {
            println(
                "[Disable Play Store updates] Set manifest versionCode to $originalVersionCode -> ${Int.MAX_VALUE} " +
                    "(0 bytecode version check calls found)."
            )
            return@finalize
        }

        println(
            "[Disable Play Store updates] Set manifest versionCode to $originalVersionCode -> ${Int.MAX_VALUE} " +
                "and applied $patched version check hook(s) across $touchedClasses class(es) " +
                "($versionCodeFieldHooks versionCode field reads, $longVersionCodeHooks getLongVersionCode calls)."
        )
    }
}

private enum class MutationType {
    FIELD_ACCESS,
    LONG_METHOD_CALL,
}

private sealed class VersionCodeMutation(val instructionIndex: Int) {
    class FieldAccess(
        index: Int,
        val packageInfoRegister: Int,
        val moveResultRegister: Int,
    ) : VersionCodeMutation(index)

    class LongMethodCall(
        index: Int,
        val register: Int,
    ) : VersionCodeMutation(index)
}

private fun hasAnyTargetInstruction(classDef: ClassDef): Boolean {
    for (method in classDef.methods) {
        val instructions = method.instructionsOrNull ?: continue
        for (inst in instructions) {
            if (isTargetInstruction(inst)) return true
        }
    }
    return false
}

private fun isTargetInstruction(inst: Instruction): Boolean {
    return isVersionCodeFieldAccess(inst) || isGetLongVersionCodeCall(inst)
}

private fun isVersionCodeFieldAccess(inst: Instruction): Boolean {
    if (inst.opcode != Opcode.IGET) return false
    val fieldRef = (inst as? ReferenceInstruction)?.reference as? FieldReference ?: return false
    if (fieldRef.name != "versionCode") return false
    if (fieldRef.type != "I") return false
    return fieldRef.definingClass == "Landroid/content/pm/PackageInfo;"
}

private fun isGetLongVersionCodeCall(inst: Instruction): Boolean {
    val opcode = inst.opcode
    if (opcode != Opcode.INVOKE_VIRTUAL && opcode != Opcode.INVOKE_VIRTUAL_RANGE) return false
    val methodRef = (inst as? ReferenceInstruction)?.reference as? MethodReference ?: return false
    if (methodRef.name != "getLongVersionCode") return false
    if (methodRef.returnType != "J") return false
    if (methodRef.parameterTypes.isNotEmpty()) return false
    return methodRef.definingClass == "Landroid/content/pm/PackageInfo;"
}

private fun scanMethodMutations(method: Method): List<VersionCodeMutation> {
    val instructions = method.instructionsOrNull?.toList() ?: return emptyList()
    val mutations = mutableListOf<VersionCodeMutation>()

    for ((index, inst) in instructions.withIndex()) {
        if (isVersionCodeFieldAccess(inst)) {
            val twoReg = inst as? TwoRegisterInstruction ?: continue
            mutations.add(
                VersionCodeMutation.FieldAccess(
                    index = index,
                    packageInfoRegister = twoReg.registerB,
                    moveResultRegister = twoReg.registerA,
                )
            )
        } else if (isGetLongVersionCodeCall(inst)) {
            if (index + 1 >= instructions.size) continue
            if (instructions[index + 1].opcode != Opcode.MOVE_RESULT_WIDE) continue

            val register = when (inst) {
                is FiveRegisterInstruction -> inst.registerC
                is RegisterRangeInstruction -> inst.startRegister
                else -> null
            } ?: continue

            mutations.add(
                VersionCodeMutation.LongMethodCall(
                    index = index,
                    register = register,
                )
            )
        }
    }

    return mutations
}

private fun applyMutations(
    method: MutableMethod,
    mutations: List<VersionCodeMutation>,
    onApplied: (MutationType) -> Unit,
) {
    val sortedMutations = mutations.sortedByDescending { it.instructionIndex }

    for (mutation in sortedMutations) {
        when (mutation) {
            is VersionCodeMutation.FieldAccess -> {
                method.replaceInstruction(
                    mutation.instructionIndex,
                    "invoke-static/range { v${mutation.packageInfoRegister} .. v${mutation.packageInfoRegister} }, " +
                        "$EXTENSION_CLASS->getVersionCode(Landroid/content/pm/PackageInfo;)I"
                )
                if (mutation.moveResultRegister >= 16) {
                    method.addInstructions(
                        mutation.instructionIndex + 1,
                        """
                            move-result v0
                            move/from16 v${mutation.moveResultRegister}, v0
                        """.trimIndent()
                    )
                } else {
                    method.addInstruction(
                        mutation.instructionIndex + 1,
                        "move-result v${mutation.moveResultRegister}"
                    )
                }
                onApplied(MutationType.FIELD_ACCESS)
            }
            is VersionCodeMutation.LongMethodCall -> {
                method.replaceInstruction(
                    mutation.instructionIndex,
                    "invoke-static/range { v${mutation.register} .. v${mutation.register} }, " +
                        "$EXTENSION_CLASS->getVersionCodeLong(Landroid/content/pm/PackageInfo;)J"
                )
                onApplied(MutationType.LONG_METHOD_CALL)
            }
        }
    }
}
