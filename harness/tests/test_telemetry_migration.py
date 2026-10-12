"""
Unit Tests for telemetry offset migration.

Focus: each newly discovered match must inherit the offsets of ITS OWN previous
HostEntry. Pairing by position attached one host's offsets to another host and
mangled multi-literal hosts such as crashpad.chromium.org.
"""

import tempfile
import unittest
from pathlib import Path

from harness.core.elf import NativeStringMatch
from harness.core.telemetry import HostAuditResult
from harness.migration.patch_migrator import PatchMigrator


HOST_A = "star-randsrv.bsg.brave.com"
HOST_B = "collector.bsg.brave.com"
HOST_MULTI = "crashpad.chromium.org"

PATCH_TEMPLATE = """package app.morphe.patches.brave

val blockTelemetryPatch = bytecodePatch(
    name = "Block Brave Telemetry",
) {{
    execute {{
        data class HostEntry(
            val arm64Offset: Long,
            val arm32Offset: Long,
            val hostName: String,
        )

        val hostEntries = listOf(
            HostEntry(0x0020d657L, 0x005a14b4L, "{host_a}"),
            HostEntry(0x0020d6bfL, 0x005a151cL, "{host_b}"),
            HostEntry(0x0008ca50L, 0x00426dfbL, "{host_multi}"),
            HostEntry(0x004d92bcL, 0x00861123L, "{host_multi}"),
        )

        val targets = listOf(
            "lib/arm64-v8a/libchrome.so" to {{ entry: HostEntry -> entry.arm64Offset }},
        )
    }}
}}
"""


def _match(host: str, offset: int) -> NativeStringMatch:
    return NativeStringMatch(
        offset=offset,
        matched_string=host,
        section_name=".rodata",
        original_bytes=host.encode("ascii"),
        replacement_bytes=b"0.0.0.0" + b"\x00" * (len(host) - 7),
        is_null_terminated=True,
    )


def _result(host: str, offsets) -> HostAuditResult:
    return HostAuditResult(
        hostname=host,
        expected_count=len(offsets),
        found_count=len(offsets),
        matches=[_match(host, o) for o in offsets],
        status="VERIFIED",
    )


class TestTelemetryOffsetMigration(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        target = root / "patches/src/main/kotlin/app/morphe/patches/brave"
        target.mkdir(parents=True)
        (target / "BraveBlockTelemetryPatch.kt").write_text(
            PATCH_TEMPLATE.format(host_a=HOST_A, host_b=HOST_B, host_multi=HOST_MULTI),
            encoding="utf-8",
        )
        self.migrator = PatchMigrator(root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_sibling_offsets_stay_with_their_own_host(self):
        # Report order deliberately differs from the source order.
        plan = self.migrator.plan_telemetry_hosts_update(
            [_result(HOST_B, [0x3000]), _result(HOST_A, [0x1000])]
        )
        lines = [l.strip() for l in plan.modified_content.splitlines() if "HostEntry(0x" in l]
        self.assertIn(f'HostEntry(0x00001000L, 0x005a14b4L, "{HOST_A}"),', lines)
        self.assertIn(f'HostEntry(0x00003000L, 0x005a151cL, "{HOST_B}"),', lines)

    def test_multi_literal_host_keeps_each_own_offsets(self):
        plan = self.migrator.plan_telemetry_hosts_update(
            [_result(HOST_MULTI, [0x1111, 0x2222])]
        )
        lines = [l.strip() for l in plan.modified_content.splitlines() if "HostEntry(0x" in l]
        self.assertIn(f'HostEntry(0x00001111L, 0x00426dfbL, "{HOST_MULTI}"),', lines)
        self.assertIn(f'HostEntry(0x00002222L, 0x00861123L, "{HOST_MULTI}"),', lines)

    def test_new_host_without_previous_entry_is_reported(self):
        brand_new = "brand-new.bsg.brave.com"
        plan = self.migrator.plan_telemetry_hosts_update([_result(brand_new, [0x4000])])
        self.assertTrue(any(brand_new in c for c in plan.changes), plan.changes)
        lines = [l.strip() for l in plan.modified_content.splitlines() if "HostEntry(0x" in l]
        self.assertIn(f'HostEntry(0x00004000L, 0x00000000L, "{brand_new}"),', lines)

    def test_arm32_pass_uses_new_arm32_offsets_and_keeps_arm64(self):
        plan = self.migrator.plan_telemetry_hosts_update([_result(HOST_A, [0x9999])], is_arm32=True)
        lines = [l.strip() for l in plan.modified_content.splitlines() if "HostEntry(0x" in l]
        self.assertIn(f'HostEntry(0x0020d657L, 0x00009999L, "{HOST_A}"),', lines)
        self.assertTrue(any("armeabi-v7a" in c for c in plan.changes), plan.changes)

    def test_no_match_report_leaves_source_untouched(self):
        plan = self.migrator.plan_telemetry_hosts_update([])
        self.assertFalse(plan.has_changes)


if __name__ == "__main__":
    unittest.main()