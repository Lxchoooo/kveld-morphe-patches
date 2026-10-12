"""
Guard rails for user-facing patch metadata.

Patch names and descriptions are shown in Morphe Manager and in the README
catalog, so they have to stay readable: one short sentence, plain ASCII, and
no APK class or method names. This test fails when they drift.
"""

import re
import unittest
from pathlib import Path

PATCH_ROOT = Path(__file__).resolve().parents[2] / "patches/src/main/kotlin/app/morphe/patches"

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


if __name__ == "__main__":
    unittest.main()