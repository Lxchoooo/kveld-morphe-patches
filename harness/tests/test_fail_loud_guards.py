"""
Guard rail for fail-loud patches.

A patch that resolves nothing normally throws, because a fingerprint that
silently matched nothing means the feature is not working and the app is
about to behave as if it were.

There is one exception. When every option of a patch is turned off there is
nothing for the patch to do, so reaching zero hooks is the expected result
and not a failure. Those throws have to test the options as well, otherwise
turning everything off makes the patch fail the whole patching run.

This test fails when a patch with toggleable options throws on zero hooks
without checking whether any option was actually enabled.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PATCH_ROOT = REPO_ROOT / "patches/src/main/kotlin/app/morphe/patches"

BOOLEAN_OPTION = re.compile(r"val (\w+) by booleanOption")
FAIL_LOUD = re.compile(r"^\s*if \(patched == 0\)(.*?)throw PatchException")


def _toggleable(path):
    return set(BOOLEAN_OPTION.findall(path.read_text(encoding="utf-8")))


class TestFailLoudRespectsDisabledOptions(unittest.TestCase):

    def test_throws_on_zero_hooks_check_the_options_first(self):
        offenders = []
        for path in sorted(PATCH_ROOT.rglob("*.kt")):
            toggles = _toggleable(path)
            if not toggles:
                # No way to turn the patch off, so zero hooks is always a fault.
                continue
            for line in path.read_text(encoding="utf-8").split("\n"):
                if not FAIL_LOUD.match(line):
                    continue
                rest = line[line.index("patched == 0"):]
                # "patched == 0 && (... != false ...)" is the guarded form.
                if "&&" not in rest:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {line.strip()[:90]}")
        self.assertEqual(
            offenders,
            [],
            "fail-loud throws that fire even when every option is off:\n"
            + "\n".join(offenders),
        )

    def test_guarded_throws_only_mention_real_options(self):
        """A guard must reference options the patch actually declares."""
        offenders = []
        for path in sorted(PATCH_ROOT.rglob("*.kt")):
            toggles = _toggleable(path)
            for line in path.read_text(encoding="utf-8").split("\n"):
                if "patched == 0 &&" not in line:
                    continue
                named = set(re.findall(r"\b(\w+)\b != false", line))
                unknown = named - toggles
                if unknown:
                    offenders.append(
                        f"{path.relative_to(REPO_ROOT)}: {sorted(unknown)}"
                    )
        self.assertEqual(offenders, [], "guards naming options that do not exist:\n" + "\n".join(offenders))

    def test_the_checker_actually_finds_these_patches(self):
        found = 0
        for path in sorted(PATCH_ROOT.rglob("*.kt")):
            for line in path.read_text(encoding="utf-8").split("\n"):
                if FAIL_LOUD.match(line):
                    found += 1
        # The consolidation work folded many patches together and moved the
        # rest behind their guards, so the count is much lower than it used to
        # be. Keep this as a floor to catch a broken parser, not a target.
        self.assertGreater(found, 3, "the scanner stopped seeing fail-loud throws")


if __name__ == "__main__":
    unittest.main()