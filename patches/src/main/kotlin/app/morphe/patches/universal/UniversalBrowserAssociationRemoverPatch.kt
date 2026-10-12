package app.morphe.patches.universal

import app.morphe.patcher.patch.resourcePatch
import app.morphe.patches.shared.childrenNamed
import org.w3c.dom.Element

private const val ANDROID_NAME = "android:name"
private const val VIEW_ACTION = "android.intent.action.VIEW"
private const val BROWSABLE_CATEGORY = "android.intent.category.BROWSABLE"

/**
 * An `<intent-filter>` only puts an app in the browser's "open with" chooser when
 * it declares the VIEW action *and* the BROWSABLE category. Filters that open
 * local content (content://, file:// handed over by another app) do not carry
 * BROWSABLE, so they are left alone and local files keep working.
 */
private fun isBrowserFileFilter(element: Element): Boolean {
    val hasView = element.getAttribute(ANDROID_NAME) == VIEW_ACTION
    val hasBrowsable = element.childrenNamed("category")
        .any { it.getAttribute(ANDROID_NAME) == BROWSABLE_CATEGORY }
    return hasView && hasBrowsable
}

private val COMPONENT_TAGS = setOf("activity", "activity-alias", "service", "receiver")

@Suppress("unused")
val universalBrowserAssociationRemoverPatch = resourcePatch(
    name = "Stop Browser File Association",
    description = "Stops the app from appearing when a link is opened in the browser. Local files still open normally.",
    default = false,
) {
    // Universal patch: applies to any target APK in Morphe Manager / CLI (no compatibleWith)

    execute {
        val manifestFile = get("AndroidManifest.xml")
        if (!manifestFile.exists()) {
            println("[Universal Browser Association Remover] Skipped: AndroidManifest.xml not found.")
            return@execute
        }

        var removedTotal = 0
        val touchedComponents = mutableListOf<String>()

        document(manifestFile.absolutePath).use { doc ->
            val filters = doc.getElementsByTagName("intent-filter")
            // Collect first, remove after, so we never mutate the live NodeList.
            val toRemove = mutableListOf<Pair<Element, Element>>()
            for (i in 0 until filters.length) {
                val filter = filters.item(i) as? Element ?: continue
                if (!isBrowserFileFilter(filter)) continue
                val parent = filter.parentNode as? Element ?: continue
                toRemove += parent to filter
            }

            for ((parent, filter) in toRemove) {
                // Remember the component name (activity/service/etc.) for the report.
                val component = generateSequence(parent.parentNode) { it.parentNode }
                    .filterIsInstance<Element>()
                    .firstOrNull { it.tagName in COMPONENT_TAGS }
                    ?.getAttribute(ANDROID_NAME)
                    ?.substringAfterLast('.')
                    ?.ifBlank { null }

                parent.removeChild(filter)
                removedTotal++
                if (component != null) touchedComponents += component
            }
        }

        if (removedTotal == 0) {
            println("[Universal Browser Association Remover] No browser file association found in AndroidManifest.xml.")
            return@execute
        }

        val componentList = touchedComponents.distinct()
        val componentNote = if (componentList.isEmpty()) {
            ""
        } else {
            " Affected component(s): ${componentList.joinToString(", ")}."
        }
        println(
            "[Universal Browser Association Remover] Removed $removedTotal browser file intent-filter(s) from AndroidManifest.xml.$componentNote"
        )
    }
}