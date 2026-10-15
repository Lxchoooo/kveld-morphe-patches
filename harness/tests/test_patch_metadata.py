"""
Guard rails for user-facing patch metadata.

Patch names and descriptions are shown in Morphe Manager and in the README
catalog, so they have to stay readable: one short sentence, plain ASCII, and
no APK class or method names. This test fails when they drift.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PATCH_ROOT = REPO_ROOT / "patches/src/main/kotlin/app/morphe/patches"

CTOR = re.compile(r"\b(bytecodePatch|resourcePatch|rawResourcePatch)\s*\(")
NAME = re.compile(r'^\s*name = "([^"]+)"')
DESC = re.compile(r'^\s*description = "([^"]*)"')
DECL = re.compile(r"^\s*(?:private\s+|internal\s+)?val\s+\w+")

MAX_DESCRIPTION = 150
# Obfuscated symbols and .so names leak into user-facing text constantly.
TECHNICAL = re.compile(r"\b(L[a-z]+/[a-zA-Z/$]+;|lib\w+\.so|\.apk\b|const-string|invoke-|DEX\b)", re.I)


def _visible_patches():
    for path in sorted(PATCH_ROOT.rglob("*.kt")):
        lines = path.read_text(encoding="utf-8").split("\n")
        for index, line in enumerate(lines):
            name_match = NAME.match(line)
            if not name_match:
                continue
            ctor = None
            for back in range(index, max(-1, index - 12), -1):
                if "Fingerprint(" in lines[back]:
                    ctor = None
                    break
                if CTOR.search(lines[back]):
                    ctor = back
                    break
            if ctor is None:
                continue
            decl = None
            for back in range(ctor, max(-1, ctor - 12), -1):
                if DECL.match(lines[back]) and "=" in lines[back]:
                    decl = lines[back]
                    break
            if decl and re.search(r"\b(private|internal)\b", decl):
                continue
            yield path, name_match.group(1)


class TestPatchMetadataReadability(unittest.TestCase):

    def test_the_scanner_finds_the_patches(self):
        found = list(_visible_patches())
        self.assertGreater(len(found), 100, "the parser stopped seeing patch declarations")

    def test_descriptions_are_short_enough_to_read(self):
        too_long = []
        for path, name in _visible_patches():
            src = path.read_text(encoding="utf-8")
            for match in DESC.finditer(src):
                if len(match.group(1)) > MAX_DESCRIPTION:
                    too_long.append(f"{path.name}: {name} ({len(match.group(1))} chars)")
        self.assertEqual(too_long, [], "descriptions over the readable limit: " + "; ".join(too_long))

    def test_descriptions_are_plain_ascii(self):
        offenders = []
        for path, name in _visible_patches():
            src = path.read_text(encoding="utf-8")
            for match in DESC.finditer(src):
                if not match.group(1).isascii():
                    offenders.append(f"{path.name}: {name}")
        self.assertEqual(offenders, [])

    def test_descriptions_do_not_leak_apk_internals(self):
        offenders = []
        for path, name in _visible_patches():
            src = path.read_text(encoding="utf-8")
            for match in DESC.finditer(src):
                if TECHNICAL.search(match.group(1)):
                    offenders.append(f"{path.name}: {name}")
        self.assertEqual(offenders, [])

    def test_names_are_not_blank_or_numbered(self):
        offenders = []
        for _, name in _visible_patches():
            if not name.strip() or re.fullmatch(r"[\d\s]+", name):
                offenders.append(repr(name))
        self.assertEqual(offenders, [])


class TestContractNamesMatchRealPatches(unittest.TestCase):
    """The audit report has to name patches a person can actually find.

    Most contracts name a patch directly. A few name a sub-feature of a patch
    ("Block Trackers: diagnostics"), which is fine as long as the patch name is
    part of it. Contracts for patches that do not give themselves a name in the
    UI are skipped: those are plain descriptions, not searchable names.
    """

    CONTRACTS = {
        app: REPO_ROOT / f"harness/{app}/contracts.py"
        for app in ("tiktok", "xiaomi", "gboard")
    }

    def test_contract_names_are_real_patch_names(self):
        by_file = {}
        known = set()
        for path, name in _visible_patches():
            by_file.setdefault(path, set()).add(name)
            known.add(name)
        self.assertGreater(len(known), 100)

        stale = []
        checked = 0
        for app, path in self.CONTRACTS.items():
            src = path.read_text(encoding="utf-8")
            for block in re.split(r"\w*PatchContract\(", src)[1:]:
                name = re.search(r'name="([^"]+)"', block)
                source = re.search(r'source_file="([^"]+)"', block)
                if not name:
                    continue
                name = name.group(1)
                if source:
                    declared = by_file.get(REPO_ROOT / source.group(1))
                    if not declared:
                        continue
                    if not any(real in name for real in declared):
                        stale.append(f"{app}: {name}")
                elif name not in known:
                    # No way to tell which file this is, so demand an exact hit.
                    stale.append(f"{app}: {name}")
                checked += 1
        self.assertGreater(checked, 40, "the contract scan stopped finding contracts")
        self.assertEqual(stale, [], "contract names with no matching patch: " + "; ".join(stale))


if __name__ == "__main__":
    unittest.main()
