"""
Unit tests for the static fingerprint cost analyser.

Focus: the analyser must count exactly the fingerprints that force a full APK
scan (no `strings`, no exact `definingClass`) and must not flag indexed lookups.
"""

import tempfile
import unittest
from pathlib import Path

from harness.core.fingerprint_cost import scan_patch_sources, render_cost_report


KT_HEADER = 'package app.morphe.patches.universal\n'


def _write(root: Path, relative: str, body: str) -> None:
    target = root / "patches/src/main/kotlin/app/morphe/patches" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(KT_HEADER + body, encoding="utf-8")


class TestFingerprintCost(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_counts_only_full_walks(self):
        _write(self.root, "universal/Probe.kt", """
val indexed = Fingerprint(
    returnType = "V",
    strings = listOf("marker"),
)
val scoped = Fingerprint(
    definingClass = "Lcom/example/Thing;",
    returnType = "V",
)
val walkOne = Fingerprint(
    returnType = "V",
    custom = { method, _ -> false },
)
val walkTwo = Fingerprint(
    returnType = "Z",
    parameters = listOf("Ljava/lang/String;"),
)
""")
        costs = scan_patch_sources(self.root)
        self.assertEqual(len(costs), 2)
        self.assertTrue(all(c.app == "universal" for c in costs))

    def test_indexed_filters_are_not_counted_as_walks(self):
        # `filters = listOf(string(...))` is the newer spelling of `strings`; both are
        # resolved through the patcher index and cost nothing.
        _write(self.root, "gboard/Probe.kt", """
val indexed = Fingerprint(
    name = "<clinit>",
    returnType = "V",
    filters = listOf(string("config_max_access_points")),
)
""")
        self.assertEqual(scan_patch_sources(self.root), [])

    def test_reports_location_and_file(self):
        _write(self.root, "tiktok/Probe.kt", """
val walk = Fingerprint(
    custom = { method, _ -> true },
).matchAll()
""")
        costs = scan_patch_sources(self.root)
        self.assertEqual(len(costs), 1)
        self.assertEqual(costs[0].app, "tiktok")
        self.assertEqual(costs[0].kind, "matchAll")
        self.assertTrue(costs[0].file.endswith("Probe.kt"))

    def test_balanced_parsing_handles_nested_parens(self):
        _write(self.root, "tiktok/Nested.kt", """
val walk = Fingerprint(
    parameters = listOf(
        "Ljava/lang/String;",
        "Ljava/util/List;",
    ),
    custom = { method, _ -> method.parameterTypes.size == 2 },
)
val after = Fingerprint(
    returnType = "V",
    strings = listOf("not_a_walk"),
)
""")
        costs = scan_patch_sources(self.root)
        self.assertEqual(len(costs), 1)
        self.assertNotIn("not_a_walk", costs[0].file)

    def test_report_mentions_the_remediation_contract(self):
        _write(self.root, "universal/Probe.kt", """
val walk = Fingerprint(
    returnType = "V",
    custom = { method, _ -> true },
)
""")
        report = render_cost_report(self.root)
        self.assertIn("1 fingerprint", report)
        self.assertIn("union predicate", report)
        self.assertIn("byte-identical", report)

    def test_empty_tree_reports_cleanly(self):
        report = render_cost_report(self.root)
        self.assertIn("No fingerprint", report)


if __name__ == "__main__":
    unittest.main()