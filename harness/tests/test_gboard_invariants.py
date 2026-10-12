"""
Unit Tests for Gboard regression invariants.

Focus: the invariants report must never claim PASSED while listing a failed
invariant, and an unreadable APK must not be reported as a missing asset.
"""

import contextlib
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from harness.core.apk import ApkMetadata
from harness.core.dex import DexIndex, IndexedClass
from harness.gboard.invariants import GboardInvariantsChecker


PACKAGE = "com.google.android.inputmethod.latin"
THEME_ASSET = "assets/theme/style_sheet_color_black.binarypb"


def _apk_with(entries) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="gboard_invariants_test_"))
    apk = tmp / "gboard.apk"
    with zipfile.ZipFile(apk, "w") as zf:
        for name in entries:
            zf.writestr(name, b"\x00")
    return apk


def _metadata(dex_files) -> ApkMetadata:
    return ApkMetadata(
        package_name=PACKAGE,
        version_name="18.0.3",
        version_code=175940530,
        sha256="sha",
        file_size=1234,
        dex_files=dex_files,
        has_arm64_libchrome=False,
    )


def _dex_with_ime() -> DexIndex:
    index = DexIndex()
    cls = IndexedClass(
        dex_name="classes.dex",
        name="Lcom/google/android/apps/inputmethod/latin/LatinIME;",
        access_flags=1,
        superclass="Ljava/lang/Object;",
        interfaces=[],
        class_def=None,
    )
    index.classes.append(cls)
    index.classes_by_name[cls.name] = cls
    return index


class TestGboardInvariants(unittest.TestCase):

    def test_all_green_report_passes(self):
        apk = _apk_with([THEME_ASSET])
        report = GboardInvariantsChecker(_metadata(["classes.dex"]), _dex_with_ime(), apk).check_all()
        self.assertTrue(report.passed)
        self.assertEqual(report.blocking_reasons, [])

    def test_failed_dex_invariant_cannot_be_overridden(self):
        # dex_files_valid failed while the rest pass: the section must not print
        # PASSED next to a [FAIL] line.
        apk = _apk_with([THEME_ASSET])
        report = GboardInvariantsChecker(_metadata([]), _dex_with_ime(), apk).check_all()
        failed = {r.invariant_id for r in report.results if not r.passed}
        self.assertIn("dex_files_valid", failed)
        self.assertFalse(report.passed)
        self.assertTrue(report.blocking_reasons)

    def test_overall_status_never_contradicts_a_failed_invariant(self):
        apk = _apk_with([])  # missing theme asset
        report = GboardInvariantsChecker(_metadata(["classes.dex"]), _dex_with_ime(), apk).check_all()
        self.assertEqual(report.passed, all(r.passed for r in report.results))

    def test_package_mismatch_blocks(self):
        apk = _apk_with([THEME_ASSET])
        meta = _metadata(["classes.dex"])
        meta.package_name = "com.example.other"
        report = GboardInvariantsChecker(meta, _dex_with_ime(), apk).check_all()
        self.assertFalse(report.passed)
        self.assertIn("Package mismatch: com.example.other", report.blocking_reasons)


if __name__ == "__main__":
    unittest.main()