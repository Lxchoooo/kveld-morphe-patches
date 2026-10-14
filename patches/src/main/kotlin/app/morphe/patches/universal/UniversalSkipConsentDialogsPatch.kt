package app.morphe.patches.universal

import app.morphe.patcher.extensions.InstructionExtensions.addInstruction
import app.morphe.patcher.patch.bytecodePatch
import app.morphe.patches.shared.clearTryBlocks

private const val TAG = "[Skip Consent Dialogs]"

private const val PLATFORM_CONSENT_FORM_INTERFACE = "Lcom/google/android/ump/ConsentForm;"
private const val EMBEDDED_CONSENT_SDK_CLASS = "Lcom/applovin/sdk/AppLovinSdk;"

@Suppress("unused")
val universalSkipConsentDialogsPatch = bytecodePatch(
    name = "Skip Consent Dialogs",
    description = "Suppresses platform consent prompts and dialogs on launch.",
    default = false,
) {
    execute {
        var patched = 0
        var touchedClasses = 0
        val matchedShapes = mutableSetOf<String>()

        classDefForEach { classDef ->
            val implementsPlatformConsent = classDef.interfaces.contains(PLATFORM_CONSENT_FORM_INTERFACE) ||
                classDef.type == PLATFORM_CONSENT_FORM_INTERFACE ||
                classDef.superclass == PLATFORM_CONSENT_FORM_INTERFACE
            val isEmbeddedConsent = classDef.type == EMBEDDED_CONSENT_SDK_CLASS ||
                classDef.superclass == EMBEDDED_CONSENT_SDK_CLASS

            if (!implementsPlatformConsent && !isEmbeddedConsent) return@classDefForEach

            val mutableClass = mutableClassDefBy(classDef)
            var classModified = false

            mutableClass.methods.forEach { method ->
                if (method.implementation == null) return@forEach

                if (implementsPlatformConsent) {
                    if (method.name == "show" &&
                        method.returnType == "V" &&
                        method.parameters.size == 2 &&
                        method.parameters[0] == "Landroid/app/Activity;"
                    ) {
                        method.clearTryBlocks()
                        method.addInstruction(0, "return-void")
                        matchedShapes.add("platform consent form")
                        patched++
                        classModified = true
                    }
                }

                if (isEmbeddedConsent) {
                    if (method.name == "showConsentFlow" && method.returnType == "V") {
                        method.clearTryBlocks()
                        method.addInstruction(0, "return-void")
                        matchedShapes.add("embedded consent flow")
                        patched++
                        classModified = true
                    }
                }
            }

            if (classModified) {
                touchedClasses++
            }
        }

        if (patched == 0) {
            println("$TAG Target APK does not contain recognized consent dialog entrypoints (0 components found).")
            return@execute
        }

        println(
            "$TAG Stubbed $patched consent entrypoint(s) across $touchedClasses class(es) " +
                "(${matchedShapes.sorted().joinToString(", ")})."
        )
    }
}
