package app.morphe.patches.universal

import app.morphe.patcher.extensions.InstructionExtensions.addInstructions
import app.morphe.patcher.extensions.InstructionExtensions.removeInstructions
import app.morphe.patcher.patch.bytecodePatch
import app.morphe.patcher.util.proxy.mutableTypes.MutableMethod
import app.morphe.patches.shared.clearTryBlocks
import app.morphe.patches.shared.ensureRegisterCount

private const val TAG = "[Skip Rating Prompts]"

private val RATING_GATE_NAMES = setOf(
    "shouldshowratedialog",
    "shouldshowratingdialog",
    "shouldshowrate",
    "shouldshowreview",
    "shouldshowreviewdialog",
    "shouldpromptforrating",
    "iseligibleforrating",
    "canshowratedialog",
    "canshowreviewdialog",
)

private val REVIEW_SHOW_NAMES = setOf(
    "showratedialog",
    "showratingdialog",
    "showreviewdialog",
    "showrateappdialog",
    "showrateprompt",
    "showrateusprompt",
    "showrateme",
    "showapprating",
    "showappratedialog",
    "launchreviewdialog",
)

@Suppress("unused")
val universalSkipRatingPromptsPatch = bytecodePatch(
    name = "Skip Rating Prompts",
    description = "Stops apps from showing unsolicited in-app review and rating prompts.",
    default = false,
) {
    execute {
        var patched = 0
        var gatesPatched = 0
        var dialogsPatched = 0
        var touchedClasses = 0

        classDefForEach { classDef ->
            if (classDef.type.startsWith("Lcom/kveld9/morphe/extension") ||
                classDef.type.startsWith("Lapp/morphe/extension")
            ) {
                return@classDefForEach
            }

            var classHasTarget = false
            for (method in classDef.methods) {
                if (method.implementation == null) continue
                val normalized = method.name.lowercase().replace("_", "")
                if ((method.returnType == "Z" && normalized in RATING_GATE_NAMES) ||
                    (method.returnType == "V" && normalized in REVIEW_SHOW_NAMES)
                ) {
                    classHasTarget = true
                    break
                }
            }

            if (!classHasTarget) return@classDefForEach

            val mutableClass = mutableClassDefBy(classDef)
            var classModified = false

            mutableClass.methods.forEach { method ->
                if (method.implementation == null) return@forEach
                val normalized = method.name.lowercase().replace("_", "")

                if (method.returnType == "Z" && normalized in RATING_GATE_NAMES) {
                    method.replaceWithReturnFalse()
                    gatesPatched++
                    patched++
                    classModified = true
                } else if (method.returnType == "V" && normalized in REVIEW_SHOW_NAMES) {
                    method.replaceWithReturnVoidBody()
                    dialogsPatched++
                    patched++
                    classModified = true
                }
            }

            if (classModified) {
                touchedClasses++
            }
        }

        if (patched == 0) {
            println("$TAG Target APK does not contain recognized rating or review prompts (0 components found).")
            return@execute
        }

        println(
            "$TAG Suppressed $patched rating prompt entrypoint(s) across $touchedClasses class(es) " +
                "($gatesPatched eligibility gate(s) forced to false, $dialogsPatched review dialog(s) stubbed)."
        )
    }
}

private fun MutableMethod.replaceWithReturnFalse() {
    val impl = implementation ?: return
    clearTryBlocks()
    ensureRegisterCount(1)
    removeInstructions(0, impl.instructions.count())
    addInstructions(
        0,
        """
            const/4 v0, 0x0
            return v0
        """.trimIndent(),
    )
}

private fun MutableMethod.replaceWithReturnVoidBody() {
    val impl = implementation ?: return
    clearTryBlocks()
    removeInstructions(0, impl.instructions.count())
    addInstructions(0, "return-void")
}
