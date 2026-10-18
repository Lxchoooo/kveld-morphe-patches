#!/usr/bin/env python3
"""Scheduled upstream app update checker for Morphe Patches.

Parses target versions from Constants.kt, queries upstream public sources
(APKMirror and APKPure), and reports whether updates are available.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

HTTP_TIMEOUT_SECONDS = 15

APP_SPECS: List[Dict[str, Any]] = [
    # ==============================================================================
    # ADD NEW APP HERE - TEMPLATE
    # ==============================================================================
    # To monitor a new app, copy-paste-fill this template into APP_SPECS below.
    # A maintainer adding an app touches ONLY this block and adds one fixture test
    # in TestUpdateChecker (see test_apkmirror_extraction_and_beta_filter).
    #
    # {
    #     "id": "my-app",                           # 1. Unique runner/issue identifier (matches PatchExecutionTest id)
    #     "name": "My App",                         # 2. Display name shown in logs, issue titles, and alerts
    #     "package_name": "com.example.app",        # 3. Android application package name
    #     "constant_key": "MY_APP_TARGET_VERSION",  # 4. Target version constant defined in Constants.kt
    #     "source_type": "apkmirror",               # 5. Upstream host type: "apkmirror" or "apkpure"
    #     "source_url": "https://www.apkmirror.com/apk/slug/app/",  # 6. Canonical listing URL (HTTP 200 verified live)
    #     "path_prefix": "/apk/slug/app/app-",      # URL path prefix for release links (apkmirror)
    #     "allow_beta": False,                      # Pre-release filter (typically False for stable patch releases)
    # },
    # ==============================================================================
    {
        "id": "brave",
        "name": "Brave",
        "package_name": "com.brave.browser",
        "constant_key": "BRAVE_TARGET_VERSION",
        "source_type": "apkmirror",
        "source_name": "APKMirror",
        "source_url": "https://www.apkmirror.com/apk/brave-software/brave-browser/",
        "path_prefix": "/apk/brave-software/brave-browser/",
        "allow_beta": False,
    },
    {
        "id": "gboard",
        "name": "Gboard",
        "package_name": "com.google.android.inputmethod.latin",
        "constant_key": "GBOARD_TARGET_VERSION",
        "source_type": "apkmirror",
        "source_name": "APKMirror",
        "source_url": "https://www.apkmirror.com/apk/google-inc/gboard/",
        "path_prefix": "/apk/google-inc/gboard/gboard-the-google-keyboard-",
        "allow_beta": True,
        "require_variant_marker": "lite_beta",
    },
    {
        "id": "tiktok",
        "name": "TikTok",
        "package_name": "com.zhiliaoapp.musically",
        "constant_key": "TIKTOK_TARGET_VERSION",
        "source_type": "apkmirror",
        "source_name": "APKMirror",
        "source_url": "https://www.apkmirror.com/apk/tiktok-pte-ltd/tik-tok-including-musical-ly/",
        "path_prefix": "/apk/tiktok-pte-ltd/tik-tok-including-musical-ly/tiktok-",
        "allow_beta": False,
    },
]


def resolve_default_constants_path() -> Path:
    """Resolve default path to Constants.kt relative to repository root."""
    repo_root = Path(__file__).resolve().parent.parent
    return repo_root / "patches" / "src" / "main" / "kotlin" / "app" / "morphe" / "patches" / "shared" / "Constants.kt"


def parse_constants(constants_path: Path) -> Dict[str, str]:
    """Parse target version constants from Constants.kt with regex.

    Matches constants such as:
        const val BRAVE_TARGET_VERSION = "1.97.57"
        const val GBOARD_TARGET_VERSION = "18.5.1.993608717-lite_beta-arm64-v8a"
    """
    if not constants_path.is_file():
        print(f"[WARN] Constants file not found: {constants_path}", file=sys.stderr)
        return {}

    content = constants_path.read_text(encoding="utf-8")
    pattern = r'const\s+val\s+([A-Z0-9_]+_TARGET_VERSION(?:_[A-Z0-9_]+)?)\s*=\s*"([^"]+)"'
    return dict(re.findall(pattern, content))


def parse_version(v_str: str) -> Tuple[Tuple[int, ...], str]:
    """Parse a version string into a numeric core tuple and suffix.

    Examples:
        '1.97.57' -> ((1, 97, 57), '')
        '18.5.1.993608717-lite_beta-arm64-v8a' -> ((18, 5, 1, 993608717), 'lite_beta-arm64-v8a')
        '18.5.1.993608717 beta' -> ((18, 5, 1, 993608717), 'beta')
        '1.38.0i' -> ((1, 38, 0), 'i')
        '9.0.278' -> ((9, 0, 278), '')
    """
    v = v_str.strip().lstrip("vV")
    m = re.match(r"^(\d+(?:\.\d+)*)(?:([a-zA-Z]+)|[-_\s]+(.*))?$", v)
    if not m:
        return (), v

    core_str = m.group(1)
    letter_suffix = m.group(2) or ""
    rest_suffix = m.group(3) or ""
    suffix = (letter_suffix + rest_suffix).strip()
    core = tuple(int(x) for x in core_str.split("."))
    return core, suffix


def compare_versions(local_ver: str, remote_ver: str) -> str:
    """Compare local vs remote version.

    Returns:
        'current', 'update-available', or 'unknown'
    """
    if not local_ver or not remote_ver:
        return "unknown"

    local_core, local_sfx = parse_version(local_ver)
    remote_core, remote_sfx = parse_version(remote_ver)

    if not local_core or not remote_core:
        return "unknown"

    max_len = max(len(local_core), len(remote_core))
    padded_local = local_core + (0,) * (max_len - len(local_core))
    padded_remote = remote_core + (0,) * (max_len - len(remote_core))

    if padded_remote > padded_local:
        return "update-available"
    if padded_remote < padded_local:
        return "current"

    # Numeric core parts are equal; check suffixes.
    clean_local_sfx = re.sub(r"-(arm64-v8a|armeabi-v7a|x86_64|x86)", "", local_sfx).strip()
    clean_remote_sfx = re.sub(r"-(arm64-v8a|armeabi-v7a|x86_64|x86)", "", remote_sfx).strip()

    if clean_local_sfx == clean_remote_sfx:
        return "current"

    # If both reference beta channel for the same numeric build:
    if "beta" in clean_local_sfx.lower() and "beta" in clean_remote_sfx.lower():
        return "current"

    if clean_remote_sfx > clean_local_sfx:
        return "update-available"

    return "current"


def fetch_html(url: str) -> Optional[str]:
    """Fetch HTML content from a public URL using standard urllib."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        print(f"[WARN] HTTP error fetching {url}: {exc}", file=sys.stderr)
        return None
    except Exception as exc:
        print(f"[WARN] Unexpected error fetching {url}: {exc}", file=sys.stderr)
        return None


def _release_has_marker(
    release_url: str,
    marker: str,
    fetcher: Callable[[str], Optional[str]],
) -> bool:
    """Check whether a candidate release page contains the variant marker."""
    page_html = fetcher(release_url)
    if not page_html:
        return False
    return marker.lower() in page_html.lower()


def _find_marked_release(
    candidates: List[Tuple[Tuple[int, ...], str, str, str]],
    source_url: str,
    marker: str,
    fetcher: Callable[[str], Optional[str]],
) -> Optional[str]:
    """Walk candidate releases newest-first and return the first matching release."""
    base_url = source_url if source_url.endswith("/") else f"{source_url}/"
    for _, _, raw_v, href in candidates:
        slug = href.strip("/").split("/")[-1]
        if not slug:
            continue
        release_url = f"{base_url}{slug}/"
        if _release_has_marker(release_url, marker, fetcher):
            return raw_v
    return None


def extract_apkmirror_version(
    html: str,
    path_prefix: str,
    allow_beta: bool = False,
    source_url: Optional[str] = None,
    require_variant_marker: Optional[str] = None,
    fetch_fn: Optional[Callable[[str], Optional[str]]] = None,
) -> Optional[str]:
    """Extract latest remote version from APKMirror listing HTML.

    Host: APKMirror (https://www.apkmirror.com/apk/...)
    Precedence: Release links matching path_prefix sorted descending by numeric
    core and suffix, filtering out beta/alpha/preview/rc when allow_beta=False.
    When require_variant_marker is specified, release candidate pages are inspected
    newest-first for the required marker token.
    Fixture test: test_apkmirror_extraction_and_beta_filter
    """
    candidates: List[Tuple[Tuple[int, ...], str, str, str]] = []

    link_pattern = r'<a[^>]*class="[^"]*fontBlack[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>'
    for m in re.finditer(link_pattern, html, re.DOTALL):
        href = m.group(1)
        title = m.group(2).strip()

        if not href.startswith(path_prefix):
            continue

        is_beta = bool(
            re.search(r"\b(beta|alpha|preview|rc)\b", title, re.I)
            or re.search(r"-(beta|alpha|rc)\d*", href, re.I)
        )
        if is_beta and not allow_beta:
            continue

        v_match = re.search(
            r"(\d+(?:\.\d+)+(?:[a-zA-Z]+)?(?:\s+(?:beta|alpha|rc\d*))?)",
            title,
            re.I,
        )
        if v_match:
            raw_v = v_match.group(1).strip()
            core, sfx = parse_version(raw_v)
            if core:
                candidates.append((core, sfx, raw_v, href))

    if not candidates:
        return None

    # Sort descending by numeric core then suffix
    candidates.sort(key=lambda c: (c[0], c[1]), reverse=True)

    if not require_variant_marker:
        return candidates[0][2]

    if not source_url:
        return None

    fetcher = fetch_fn if fetch_fn is not None else fetch_html
    return _find_marked_release(
        candidates, source_url, require_variant_marker, fetcher
    )


def extract_apkpure_version(html: str, package_name: str) -> Optional[str]:
    """Extract latest remote version from APKPure page HTML.

    Priority order:
    1. Version from download-URL pattern for the package (/<package>/download/<version>).
       Ground truth for fetchable artifact; wins over JSON-LD when they disagree.
    2. Version from data-dt-version attributes for the package.
    3. Version from schema.org JSON-LD as last resort.
    4. Version from meta description tag fallback.
    """
    # 1. Version from download-URL pattern for this package
    dl_matches = re.findall(
        rf'/{re.escape(package_name)}/download/([a-zA-Z0-9._-]+)', html
    )
    dl_version = dl_matches[0].strip() if dl_matches else None

    # 2. Version from data-dt-version attributes
    attr_match = re.search(
        rf'data-dt-package_name="{re.escape(package_name)}"[^>]*data-dt-version="([^"]+)"',
        html,
    )
    if not attr_match:
        attr_match = re.search(
            rf'data-dt-version="([^"]+)"[^>]*data-dt-package_name="{re.escape(package_name)}"',
            html,
        )
    dt_version = attr_match.group(1).strip() if attr_match else None

    # 3. Version from schema.org JSON-LD
    json_ld_version: Optional[str] = None
    for m in re.finditer(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    ):
        try:
            data = json.loads(m.group(1))
            items = data if isinstance(data, list) else [data]
            for item in items:
                v = item.get("version") or item.get("softwareVersion")
                if v and isinstance(v, str):
                    core, _ = parse_version(v)
                    if core:
                        json_ld_version = v.strip()
                        break
            if json_ld_version:
                break
        except Exception:
            pass

    # Resolution:
    # If download-URL version is present, it takes precedence over JSON-LD.
    # When data-dt-version reports a higher numeric version than dl_version,
    # the higher version from the primary download button is preferred.
    if dl_version:
        core_dl, _ = parse_version(dl_version)
        if dt_version:
            core_dt, _ = parse_version(dt_version)
            if core_dt and core_dl and core_dt > core_dl:
                return dt_version
        return dl_version

    if dt_version:
        core, _ = parse_version(dt_version)
        if core:
            return dt_version

    if json_ld_version:
        core, _ = parse_version(json_ld_version)
        if core:
            return json_ld_version

    # 4. Fallback: meta description tag
    meta_match = re.search(
        r'<meta[^>]*name="description"[^>]*content="[^"]*?\s+v?(\d+(?:\.\d+)+[a-zA-Z]?)\s+APK',
        html,
        re.I,
    )
    if meta_match:
        v = meta_match.group(1).strip()
        core, _ = parse_version(v)
        if core:
            return v

    return None


def run_update_checks(
    constants_path: Path,
    fetch_fn: Optional[Callable[[str], Optional[str]]] = None,
) -> List[Dict[str, Any]]:
    """Run update checks for all configured apps."""
    constants = parse_constants(constants_path)
    results: List[Dict[str, Any]] = []
    fetcher = fetch_fn if fetch_fn is not None else fetch_html

    for spec in APP_SPECS:
        app_id = spec["id"]
        app_name = spec["name"]
        package_name = spec["package_name"]
        constant_key = spec["constant_key"]
        source_type = spec["source_type"]
        source_name = spec["source_name"]
        source_url = spec["source_url"]
        allow_beta = spec["allow_beta"]
        require_variant_marker = spec.get("require_variant_marker")

        local_version = constants.get(constant_key)
        if not local_version:
            print(
                f"[WARN] Constant {constant_key} not found in {constants_path}",
                file=sys.stderr,
            )
            local_version = "unknown"

        remote_version: Optional[str] = None
        html = fetcher(source_url)
        if html:
            if source_type == "apkmirror":
                remote_version = extract_apkmirror_version(
                    html,
                    spec["path_prefix"],
                    allow_beta,
                    source_url=source_url,
                    require_variant_marker=require_variant_marker,
                    fetch_fn=fetcher,
                )
            elif source_type == "apkpure":
                remote_version = extract_apkpure_version(html, package_name)

        if not remote_version:
            status = "unknown"
        else:
            status = compare_versions(local_version, remote_version)

        display_remote = remote_version if remote_version else "unknown"
        print(
            f"[UPDATE-CHECK] {app_name}: local={local_version} remote={display_remote} status={status}"
        )

        results.append(
            {
                "id": app_id,
                "name": app_name,
                "package_name": package_name,
                "local_version": local_version,
                "remote_version": display_remote,
                "status": status,
                "source_name": source_name,
                "source_url": source_url,
            }
        )

    return results


# Built-in fixture test suite
class TestUpdateChecker(unittest.TestCase):
    """Fixture tests covering version comparison, variant markers, and extraction."""

    def test_version_schemes(self) -> None:
        """Verify non-plain version schemes and channel matching."""
        # Standard semver
        self.assertEqual(compare_versions("1.97.57", "1.97.57"), "current")
        self.assertEqual(compare_versions("1.97.57", "1.97.58"), "update-available")
        self.assertEqual(compare_versions("1.97.58", "1.97.57"), "current")

        # Non-plain schemes from reference (twitter prod suffix, microsoft 4-part, instagram 5-part, lightroom)
        self.assertEqual(compare_versions("12.34.0-prod.01", "12.34.0-prod.01"), "current")
        self.assertEqual(compare_versions("12.34.0-prod.01", "12.35.0-prod.01"), "update-available")
        self.assertEqual(compare_versions("12.34.0-prod.01", "12.34.0-prod.02"), "update-available")
        self.assertEqual(compare_versions("12.34.0-prod.02", "12.34.0-prod.01"), "current")

        # Microsoft 4-part builds
        self.assertEqual(compare_versions("16.0.20527.20034", "16.0.20527.20034"), "current")
        self.assertEqual(compare_versions("16.0.20527.20034", "16.0.20527.20035"), "update-available")
        self.assertEqual(compare_versions("16.0.20527.20035", "16.0.20527.20034"), "current")

        # Instagram 5-part builds
        self.assertEqual(compare_versions("447.0.0.55.81", "447.0.0.55.81"), "current")
        self.assertEqual(compare_versions("447.0.0.55.81", "448.0.0.1.1"), "update-available")

        # Trailing point groups (Lightroom)
        self.assertEqual(compare_versions("11.6.01", "11.6.01"), "current")
        self.assertEqual(compare_versions("11.6.01", "11.6.10"), "update-available")

        # Beta channel matching
        self.assertEqual(
            compare_versions(
                "18.5.1.993608717-lite_beta-arm64-v8a",
                "18.5.1.993608717 beta",
            ),
            "current",
        )
        self.assertEqual(
            compare_versions(
                "18.5.1.993608717-lite_beta-arm64-v8a",
                "18.5.2.100000000 beta",
            ),
            "update-available",
        )

    def test_apkmirror_extraction_and_beta_filter(self) -> None:
        """Verify APKMirror listing extraction filters out betas when allow_beta=False."""
        fixture_html = """
        <div>
          <a class="fontBlack" href="/apk/moovit/moovit-bus-train-live-info/moovit-5-201-6-1811-release/">
            Moovit: Your Transit Tracker 5.201.6.1811 beta
          </a>
          <a class="fontBlack" href="/apk/moovit/moovit-bus-train-live-info/moovit-5-201-1-1809-release/">
            Moovit: Your Transit Tracker 5.201.1.1809
          </a>
          <a class="fontBlack" href="/apk/other-dev/other-app/other-release/">
            Other App 1.0.0
          </a>
        </div>
        """
        ver = extract_apkmirror_version(
            fixture_html,
            path_prefix="/apk/moovit/moovit-bus-train-live-info/moovit-",
            allow_beta=False,
        )
        self.assertEqual(ver, "5.201.1.1809")


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Check upstream app versions against Morphe target constants."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        default=True,
        help="Report update check status (default: True)",
    )
    parser.add_argument(
        "--json",
        dest="json_path",
        type=str,
        default=None,
        help="Path to write machine-readable JSON report",
    )
    parser.add_argument(
        "--constants",
        dest="constants_path",
        type=str,
        default=None,
        help="Path to Constants.kt (default: auto-detected)",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        default=False,
        help="Run built-in unit and fixture tests",
    )

    args = parser.parse_args()

    if args.test:
        suite = unittest.TestLoader().loadTestsFromTestCase(TestUpdateChecker)
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        return 0 if result.wasSuccessful() else 1

    constants_path = (
        Path(args.constants_path)
        if args.constants_path
        else resolve_default_constants_path()
    )

    results = run_update_checks(constants_path)

    if args.json_path:
        out_path = Path(args.json_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        report_data = {"apps": results}
        out_path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
        print(f"[INFO] Saved JSON report to {args.json_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
