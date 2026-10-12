"""
Static cost analysis for patch fingerprint scanning.

AGENTS.md section 5 ("Fingerprint Scan Cost") is a measured performance contract:
a fingerprint without `strings` or an exact `definingClass` walks every method of
the APK, and `matchAll()` always walks every class even when a `definingClass` is
declared, because `matchAll()` ignores that index.

On the TikTok baseline (about 475k classes / 2M methods) a single walk costs
seconds, so the number of full walks per patch is the main lever on patch time.
This module counts them from the Kotlin sources so the cost is visible without an
APK, a device or a Gradle build.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


PATCHES_REL = Path("patches/src/main/kotlin/app/morphe/patches")

_FINGERPRINT_OPEN = re.compile(r"\bFingerprint\s*\(")
_DEFINING_CLASS = re.compile(r"\bdefiningClass\s*=")
_STRINGS = re.compile(r"\bstrings\s*=")
_MATCH_ALL = re.compile(r"\.matchAll\(\s*\)")


@dataclass(frozen=True)
class FingerprintCost:
    file: str
    line: int
    app: str
    kind: str  # "matchAll" or "single"
    predicate_chars: int


def _iter_fingerprint_blocks(src: str) -> List[Tuple[int, str, str]]:
    """Yields (line, block, tail) for every balanced Fingerprint(...) expression.

    `tail` is the source right after the closing parenthesis: `matchAll()` is chained
    onto the result, so it lives outside the block and has to be inspected separately.
    """
    for match in _FINGERPRINT_OPEN.finditer(src):
        start = src.index("(", match.start())
        depth = 0
        index = start
        while index < len(src):
            char = src[index]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    break
            index += 1
        if depth != 0:
            continue
        line = src[: match.start()].count("\n") + 1
        yield line, src[match.start() : index + 1], src[index + 1 : index + 201]


def scan_patch_sources(repo_root: str | Path) -> List[FingerprintCost]:
    """Returns every fingerprint that forces a full scan of the APK."""
    root = Path(repo_root)
    patches_dir = root / PATCHES_REL
    costs: List[FingerprintCost] = []
    for path in sorted(patches_dir.rglob("*.kt")):
        src = path.read_text(encoding="utf-8")
        rel_parts = path.relative_to(patches_dir).parts
        app = rel_parts[0] if len(rel_parts) > 1 else "."
        for line, block, tail in _iter_fingerprint_blocks(src):
            if _DEFINING_CLASS.search(block) or _STRINGS.search(block):
                continue  # indexed lookup, no walk
            costs.append(
                FingerprintCost(
                    file=str(path.relative_to(root)),
                    line=line,
                    app=app,
                    kind="matchAll" if _MATCH_ALL.search(tail) else "single",
                    predicate_chars=len(block),
                )
            )
    return costs


def group_by_patch(costs: List[FingerprintCost]) -> Dict[str, List[FingerprintCost]]:
    grouped: Dict[str, List[FingerprintCost]] = {}
    for cost in costs:
        grouped.setdefault(cost.file, []).append(cost)
    return grouped


def render_cost_report(repo_root: str | Path) -> str:
    costs = scan_patch_sources(repo_root)
    if not costs:
        return "No fingerprint forces a full APK scan."

    grouped = group_by_patch(costs)
    by_app: Dict[str, int] = {}
    for cost in costs:
        by_app[cost.app] = by_app.get(cost.app, 0) + 1

    lines = [
        f"{len(costs)} fingerprint(s) force a full APK scan across {len(grouped)} patch file(s).",
        "Full scans are the dominant patch-time cost on large APKs (AGENTS.md section 5).",
        "",
        "By app: " + ", ".join(f"{app}={n}" for app, n in sorted(by_app.items(), key=lambda x: -x[1])),
        "",
        "| Patch file | Full scans | Locations |",
        "| :--- | ---: | :--- |",
    ]
    for path, items in sorted(grouped.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        locations = ", ".join(f"L{item.line}" for item in sorted(items, key=lambda i: i.line))
        lines.append(f"| `{path}` | {len(items)} | {locations} |")
    lines.extend([
        "",
        "Remediation (AGENTS.md section 5):",
        "  - Merge independent scans of the same patch into ONE union predicate, then partition",
        "    the candidates afterwards. Keep each section's own unchanged predicate and its",
        "    exactly-1 guard.",
        "  - Add `strings` or an exact `definingClass` so the lookup uses the patcher index.",
        "  - Scope `matchAll()` with `classDefBy(TYPE)`; it ignores `definingClass` as an index.",
        "  - A performance-only change must produce byte-identical DEX: verify with",
        "    runPatchTest -PdexDigest before and after and diff the two files.",
    ])
    return "\n".join(lines)