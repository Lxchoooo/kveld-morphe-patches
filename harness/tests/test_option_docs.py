"""
Guard rail for documented patch options.

The tables in the docs list each option with its key, its type and its
default. Users read those before turning something off, so a doc that drifts
from the code means someone makes a decision based on a wrong default and
never finds out why the app behaves differently.

This test parses the real option declarations out of the Kotlin sources and
compares them with what the docs claim. It covers both documentation styles
in use: the option tables (`| **Name** | `key` | Boolean | `true` | ...`)
and the bullet lists (`- **`key`** ... Default: `true``).

A constant used as a default is resolved, so `default = DEFAULT_SINK_IP` is
compared as the literal it stands for rather than being reported as a
mismatch.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PATCH_ROOT = REPO_ROOT / "patches/src/main/kotlin/app/morphe/patches"
DOCS = sorted(DOCS_ALL) if (DOCS_ALL := sorted(REPO_ROOT.glob("docs/apps/*.md"))) else []
DOCS.append(REPO_ROOT / "docs/universal-patches.md")

# Anchored to the start of a line so that a `key = "..."` or `title = "..."`
# line inside a previously seen option block can never look like a new one.
DECL = re.compile(
    r"^[ \t]*val (\w+) (?:by[ \t]+|=[ \t]*)(booleanOption|stringOption|intOption|longOption)\(",
    re.M,
)
KEY = re.compile(r'key = "([^"]+)"')
DEFAULT = re.compile(r"default = (.+?),?\n")
CONST = re.compile(r'(?:const val|val) (\w+)\s*(?::\s*String\s*)?=\s*"([^"]*)"')
TYPE_MAP = {
    "Boolean": "booleanOption",
    "String": "stringOption",
    "Text": "stringOption",
    "Integer": "intOption",
    "Number": "intOption",
}


def _literal(text: str, constants: dict) -> str:
    """Resolve a default expression to the literal it stands for."""
    text = text.strip().strip('"')
    return constants.get(text, text)


def _options() -> dict:
    constants = {}
    for path in PATCH_ROOT.rglob("*.kt"):
        text = path.read_text(encoding="utf-8")
        for match in CONST.finditer(text):
            constants[match.group(1)] = match.group(2)

    found = {}
    for path in PATCH_ROOT.rglob("*.kt"):
        text = path.read_text(encoding="utf-8")
        pos = 0
        while True:
            match = DECL.search(text, pos)
            if not match:
                break
            # Consume the whole option block so key= / title= lines inside it
            # are not mistaken for the start of another declaration.
            close = text.find("\n    )", match.start())
            block = text[match.start():close if close != -1 else match.start() + 400]
            key_match = KEY.search(block)
            default_match = DEFAULT.search(block)
            key = key_match.group(1) if key_match else match.group(1)
            default = None
            if default_match:
                default = _literal(default_match.group(1), constants)
            found[key] = (match.group(2), default)
            pos = match.end()
    return found


class TestDocumentedOptionsMatchCode(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.options = _options()

    def test_the_scanner_finds_the_options(self):
        self.assertGreater(len(self.options), 150, "the parser stopped seeing option declarations")

    def test_documented_types_match_the_declaration(self):
        wrong = []
        for path in DOCS:
            for line in path.read_text(encoding="utf-8").split("\n"):
                if not line.startswith("|"):
                    continue
                cells = [c.strip() for c in line.strip("|").split("|")]
                if len(cells) < 5:
                    continue
                key_match = re.search(r"`(\w+)`", cells[1])
                if not key_match or self._is_patch_kind(key_match.group(1)):
                    continue
                if key_match.group(1) not in self.options:
                    continue
                key = key_match.group(1)
                declared, _ = self.options[key]
                if cells[2] in TYPE_MAP and TYPE_MAP[cells[2]] != declared:
                    wrong.append(f"{path.name}: `{key}` documented as {cells[2]}, declared as {declared}")
        self.assertEqual(wrong, [], "documented option types that do not match the code:\n" + "\n".join(wrong))

    def test_documented_defaults_match_the_declaration(self):
        wrong = []
        for path in DOCS:
            for line in path.read_text(encoding="utf-8").split("\n"):
                if not line.startswith("|"):
                    continue
                cells = [c.strip() for c in line.strip("|").split("|")]
                if len(cells) < 5:
                    continue
                key_match = re.search(r"`(\w+)`", cells[1])
                if not key_match or self._is_patch_kind(key_match.group(1)):
                    continue
                if key_match.group(1) not in self.options:
                    continue
                key = key_match.group(1)
                _, declared = self.options[key]
                if declared is None:
                    continue
                documented = cells[3].replace("`", "").strip()
                if documented in ("_(empty)_", "_(none)_", "-"):
                    documented = ""
                if documented.lower() != declared.lower():
                    wrong.append(f"{path.name}: `{key}` documented default {documented!r}, code has {declared!r}")
        self.assertEqual(wrong, [], "documented defaults that do not match the code:\n" + "\n".join(wrong))

    @staticmethod
    def _is_patch_kind(value: str) -> bool:
        return value in {"bytecodePatch", "resourcePatch", "rawResourcePatch", "Multiple"}

    def test_every_documented_key_exists_in_the_code(self):
        """A key shown in a table must be a real option, not a renamed leftover."""
        ghosts = set()
        for path in DOCS:
            text = path.read_text(encoding="utf-8")
            in_options_table = False
            for line in text.split("\n"):
                # An option table always has this header. Patch tables do not,
                # and listing their patch kinds here would flag every one of them.
                if line.startswith("|") and re.match(r"\|\s*Option\s*\|", line):
                    in_options_table = True
                    continue
                if in_options_table and re.match(r"\|\s*:?-{2,}", line):
                    continue
                if not line.startswith("|"):
                    in_options_table = False
                if not line.startswith("|"):
                    continue
                cells = [c.strip() for c in line.strip("|").split("|")]
                if len(cells) < 5:
                    continue
                key_match = re.search(r"`(\w+)`", cells[1])
                if not key_match or self._is_patch_kind(key_match.group(1)):
                    continue
                if key_match.group(1) not in self.options:
                    ghosts.add(f"{path.name}: `{key_match.group(1)}`")
        self.assertEqual(sorted(ghosts), [], "documented keys that no longer exist:\n" + "\n".join(sorted(ghosts)))


if __name__ == "__main__":
    unittest.main()