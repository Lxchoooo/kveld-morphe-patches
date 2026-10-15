"""
Unit Tests for Migrator, Symbols, and Validator.
Verifies version bump updates, no-op identical version handling, symbol mappings, and patch status.
"""

import re
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from harness.migration.patch_migrator import PatchMigrator, MigrationPlan
from harness.core.symbols import ResolvedSymbol, SymbolConfidence, BraveOriginSymbols
from harness.migration.validator import AdversarialValidator, PatchStatus, PatchAuditResult


class TestMigratorAndValidator(unittest.TestCase):

    def setUp(self):
        self.repo_root = Path(__file__).resolve().parent.parent.parent
        self.migrator = PatchMigrator(self.repo_root)

    # 10. new version -> metadata updated
    def test_version_new_metadata_updated(self):
        plan = self.migrator.plan_constants_update("1.95.100")
        self.assertTrue(plan.has_changes)
        self.assertIn('const val BRAVE_TARGET_VERSION = "1.95.100"', plan.modified_content)
        self.assertIn('Download com.brave.browser v$BRAVE_TARGET_VERSION (APK) arm64-v8a nodpi versionCode 429705704 (APK) from APKMirror', plan.modified_content)

    def test_version_description_no_match_warns_and_leaves_untouched(self):
        import io
        from unittest.mock import patch
        stale_desc = 'description = "Unrecognized custom upstream download description format"'
        orig_content = self.migrator.constants_file.read_text(encoding="utf-8")
        custom_content = re.sub(r'description\s*=\s*"Download [^"]+"', stale_desc, orig_content, count=1)

        with patch.object(Path, "read_text", return_value=custom_content):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                plan = self.migrator.plan_constants_update("1.95.100")
                self.assertIn("[WARN] AppTarget description pattern did not match; leaving description untouched.", mock_stdout.getvalue())
                self.assertIn(stale_desc, plan.modified_content)
                self.assertIn('const val BRAVE_TARGET_VERSION = "1.95.100"', plan.modified_content)
                self.assertNotIn("Updated AppTarget description for Brave", plan.changes)

    # 11. identical version -> NO-OP
    def test_version_identical_noop(self):
        # Read current version in Constants.kt
        constants_text = self.migrator.constants_file.read_text(encoding="utf-8")
        import re
        m = re.search(r'const val BRAVE_TARGET_VERSION = "([^"]+)"', constants_text)
        current_ver = m.group(1)
        plan = self.migrator.plan_constants_update(current_ver)
        self.assertFalse(plan.has_changes)
        self.assertEqual(len(plan.changes), 0)

    # 4. obfuscated symbol changed -> candidate detected
    def test_obfuscated_symbol_changed_detected(self):
        sym = ResolvedSymbol(
            symbol_id="origin_locked_field",
            target_class="Lorg/chromium/chrome/browser/settings/BraveOriginPreferences;",
            old_symbol="N0:Z",
            new_symbol="O0:Z",
            symbol_type="field",
            confidence=SymbolConfidence.VERIFIED,
            evidence=["Instance boolean field on class: O0"],
        )
        self.assertEqual(sym.confidence, SymbolConfidence.VERIFIED)
        self.assertEqual(sym.new_symbol, "O0:Z")

    # 5. incompatible symbol -> BLOCK
    def test_symbol_incompatible_block(self):
        sym = ResolvedSymbol(
            symbol_id="origin_locked_field",
            target_class="Lorg/chromium/chrome/browser/settings/BraveOriginPreferences;",
            old_symbol="N0:Z",
            new_symbol="UNKNOWN",
            symbol_type="field",
            confidence=SymbolConfidence.BLOCKED,
            evidence=["No matching boolean field found"],
        )
        self.assertEqual(sym.confidence, SymbolConfidence.BLOCKED)

    # 12. patch not affected -> NOT AFFECTED
    def test_patch_not_affected(self):
        audit_res = PatchAuditResult(
            patch_name="Universal Unrelated Patch",
            status=PatchStatus.NOT_AFFECTED,
            fingerprint_results=[],
            native_checks=[],
            blocking_reasons=[],
            evidence=["Patch is universal and has no package-specific targets."],
        )
    # 13. Gboard new version -> metadata updated
    def test_gboard_version_new_metadata_updated(self):
        plan = self.migrator.plan_gboard_constants_update("18.1.0.999999999-lite_beta-arm64-v8a")
        self.assertTrue(plan.has_changes)
        self.assertIn('const val GBOARD_TARGET_VERSION = "18.1.0.999999999-lite_beta-arm64-v8a"', plan.modified_content)
        self.assertIn('const val GBOARD_TARGET_VERSION_V7A = "18.1.0.999999999-lite_beta-armeabi-v7a"', plan.modified_content)

    # 13b. Gboard bump must only touch the two Gboard version constants
    def test_gboard_version_bump_leaves_other_lines_untouched(self):
        plan = self.migrator.plan_gboard_constants_update("18.1.0.999999999-lite_beta-armeabi-v7a")
        changed = [
            (old, new)
            for old, new in zip(plan.original_content.splitlines(), plan.modified_content.splitlines())
            if old != new
        ]
        self.assertEqual(len(changed), 2)
        for old, _ in changed:
            self.assertRegex(old, r'const val GBOARD_TARGET_VERSION(_V7A)? = ')

    # 13c. TikTok new version -> constant bumped, interpolated description untouched
    def test_tiktok_version_bump(self):
        plan = self.migrator.plan_tiktok_constants_update("99.9.9")
        self.assertIn('const val TIKTOK_TARGET_VERSION = "99.9.9"', plan.modified_content)
        self.assertEqual(plan.changes, ["Updated TIKTOK_TARGET_VERSION to '99.9.9'"])
        self.assertEqual(len(plan.original_content.splitlines()), len(plan.modified_content.splitlines()))

    # 16. Origin pref key migration -> updated
    def test_origin_pref_key_migration(self):
        symbols = BraveOriginSymbols(
            locked_field=ResolvedSymbol("origin_locked_field", "", "N0:Z", "O0:Z", "field", SymbolConfidence.VERIFIED),
            key_mapping_method=ResolvedSymbol("origin_key_mapping", "", "b5", "j5(Ljava/lang/String;)Ljava/lang/String;", "method", SymbolConfidence.VERIFIED),
            context_getter_method=ResolvedSymbol("origin_context_getter", "", "B4", "S3()Landroid/content/Context;", "method", SymbolConfidence.VERIFIED),
            update_prefs_method=ResolvedSymbol("origin_update_prefs", "", "e5", "i5()V", "method", SymbolConfidence.VERIFIED),
            find_pref_method=ResolvedSymbol("origin_find_pref", "", "P4", "W4(Ljava/lang/CharSequence;)Landroidx/preference/Preference;", "method", SymbolConfidence.VERIFIED),
            pref_listener_field=ResolvedSymbol("origin_pref_listener", "", "y", "y", "field", SymbolConfidence.VERIFIED),
            pref_key_field=ResolvedSymbol("origin_pref_key_field", "", "G:Ljava/lang/String;", "H:Ljava/lang/String;", "field", SymbolConfidence.VERIFIED),
        )
        plan = self.migrator.plan_origin_symbols_update(symbols)
        self.assertTrue(plan.has_changes)
        self.assertIn("Updated Preference key field to 'H'", plan.changes)

    # 17. Scheduler onStartTask rename -> fingerprint name migrated, identical name -> NO-OP
    def test_scheduler_on_start_task_rename(self):
        from harness.core.symbols import BraveNotificationSchedulerSymbols

        def plan_for(name):
            sym = ResolvedSymbol("scheduler_on_start_task", "", "c", name, "method", SymbolConfidence.VERIFIED)
            return self.migrator.plan_scheduler_symbols_update(BraveNotificationSchedulerSymbols(sym))

        renamed = plan_for("zq")
        self.assertTrue(renamed.has_changes)
        self.assertIn('name = "zq",\n            returnType = "I",', renamed.modified_content)
        self.assertEqual(len(renamed.original_content.splitlines()), len(renamed.modified_content.splitlines()))

    # 18. Scheduler resolver must not index missing parameters
    def test_scheduler_resolver_single_param_method(self):
        from harness.core.symbols import SymbolResolver

        method = MagicMock(return_type="I", parameters=["Landroid/content/Context;"], full_name="X->c(Landroid/content/Context;)I")
        method.name = "c"
        index = MagicMock()
        index.find_class.return_value = MagicMock(methods=[method])
        resolved = SymbolResolver(index).resolve_notification_scheduler_symbols()
        self.assertEqual(resolved.on_start_task_method.new_symbol, "c")

    # 19. Current telemetry offsets are read per ABI from the patch source
    def test_current_telemetry_offsets(self):
        arm64 = self.migrator.current_telemetry_offsets(is_arm32=False)
        arm32 = self.migrator.current_telemetry_offsets(is_arm32=True)
        self.assertEqual(len(arm64["crashpad.chromium.org"]), 2)
        self.assertEqual(set(arm64), set(arm32))
        self.assertNotEqual(arm64["cr.brave.com"], arm32["cr.brave.com"])

    # 20. Raw-resource patches must not claim a verified check that never ran
    def test_unverified_raw_resource_patches_are_not_marked_verified(self):
        validator = AdversarialValidator(self.repo_root, MagicMock())
        for result in (validator._audit_locale_slimmer_patch(), validator._audit_native_bloat_slimmer_patch()):
            self.assertEqual(result.status, PatchStatus.STATICALLY_VERIFIED)
            self.assertEqual(result.blocking_reasons, [])
            self.assertTrue(
                any("not verified against APK entries" in e for e in result.evidence),
                f"{result.patch_name} evidence must disclose the missing verification",
            )

    # 20b. Downgrading to STATICALLY_VERIFIED must not block the pipeline
    def test_statically_verified_still_counts_as_passing(self):
        from harness.core.pipeline import BaseTargetPipeline

        class _Stub(BaseTargetPipeline):
            app_name = "stub"

            def __init__(self):  # bypass the APK-dependent constructor
                pass

            def matches_package(self, package_name): return True
            def validate_apk_sanity(self): pass
            def extract_and_index(self): pass
            def get_old_target_version(self): return "0"
            def run_gradle_verification(self, validator): return True, "ok"
            def execute_audit_and_validation(self): return {}, None
            def create_migration_plans(self, extra_data): return []

        results = {
            "locale": PatchAuditResult("Locale PAK Slimmer", PatchStatus.STATICALLY_VERIFIED),
            "bloat": PatchAuditResult("Native Bloat Slimmer", PatchStatus.STATICALLY_VERIFIED),
        }
        self.assertTrue(_Stub().is_all_verified(results, None))
        results["bloat"] = PatchAuditResult("Native Bloat Slimmer", PatchStatus.BLOCKED, blocking_reasons=["nope"])
        self.assertFalse(_Stub().is_all_verified(results, None))


if __name__ == "__main__":
    unittest.main()


class TestOriginSymbolAmbiguity(unittest.TestCase):
    """The migrator writes resolved symbol names straight into BraveOriginPatch.kt.

    A settings class usually exposes several instance booleans and several static
    String->String helpers, so a "first match wins" guess must not be reported as
    verified: it would silently patch an unrelated member.
    """

    @staticmethod
    def _prefs_class(booleans, statics):
        from harness.core.dex import IndexedClass, IndexedMethod

        return IndexedClass(
            dex_name="classes.dex",
            name="Lorg/chromium/chrome/browser/settings/BraveOriginPreferences;",
            access_flags=1,
            superclass="Ljava/lang/Object;",
            interfaces=[],
            class_def=None,
            methods=[
                IndexedMethod(
                    dex_name="classes.dex",
                    class_name="Lorg/chromium/chrome/browser/settings/BraveOriginPreferences;",
                    name=name,
                    parameters=["Ljava/lang/String;"],
                    return_type="Ljava/lang/String;",
                    access_flags=0x9,  # public static
                    encoded_method=MagicMock(),
                )
                for name in statics
            ],
            fields=[(n, "Z", 0x2) for n in booleans],
        )

    def test_single_boolean_is_verified(self):
        from harness.core.symbols import SymbolResolver, SymbolConfidence

        cls = self._prefs_class(["N0"], [])
        sym = SymbolResolver._resolve_origin_locked_field(cls, cls.name)
        self.assertEqual(sym.confidence, SymbolConfidence.VERIFIED)
        self.assertEqual(sym.new_symbol, "N0:Z")

    def test_multiple_booleans_block_instead_of_guessing(self):
        from harness.core.symbols import SymbolResolver, SymbolConfidence

        cls = self._prefs_class(["N0", "O0", "P0"], [])
        sym = SymbolResolver._resolve_origin_locked_field(cls, cls.name)
        self.assertEqual(sym.confidence, SymbolConfidence.BLOCKED)
        self.assertIn("ambiguous", " ".join(sym.evidence))

    def test_single_static_string_method_is_verified(self):
        from harness.core.symbols import SymbolResolver, SymbolConfidence

        cls = self._prefs_class(["N0"], ["b5"])
        sym = SymbolResolver._resolve_origin_key_mapping(cls, cls.name)
        self.assertEqual(sym.confidence, SymbolConfidence.VERIFIED)

    def test_multiple_static_string_methods_block(self):
        from harness.core.symbols import SymbolResolver, SymbolConfidence

        cls = self._prefs_class(["N0"], ["b5", "c5"])
        sym = SymbolResolver._resolve_origin_key_mapping(cls, cls.name)
        self.assertEqual(sym.confidence, SymbolConfidence.BLOCKED)
        self.assertIn("ambiguous", " ".join(sym.evidence))
