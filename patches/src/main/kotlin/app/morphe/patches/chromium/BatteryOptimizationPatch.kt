package app.morphe.patches.chromium

import app.morphe.patcher.Fingerprint
import app.morphe.patcher.extensions.InstructionExtensions.addInstructions
import app.morphe.patcher.patch.bytecodePatch
import app.morphe.patches.shared.Constants

@Suppress("unused")
val batteryOptimizationPatch = bytecodePatch(
    name = "Hide Battery Status",
    description = "Stops sites from reading your battery level to track you.",
    default = true,
) {
    compatibleWith(Constants.COMPATIBILITY_BRAVE)

    execute {
        val fp = Fingerprint(
            returnType = "V",
            parameters = listOf("Landroid/content/Context;", "Landroid/content/Intent;"),
            strings = listOf("android.intent.action.BATTERY_CHANGED", "cr_BatteryStatusManager"),
        )
        fp.method.addInstructions(
            0,
            """
                return-void
            """.trimIndent(),
        )

        val targetClass = fp.originalClassDef.type.substringAfterLast('/').removeSuffix(";")
        println("[Disable Battery API] Hooked onReceive in $targetClass to drop BATTERY_CHANGED broadcast events")
    }
}
