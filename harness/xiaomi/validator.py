"""
Adversarial validator for Xiaomi Earbuds patches against target APK bytecode and assets.
"""

from __future__ import annotations
from typing import Any, Dict
from pathlib import Path

from harness.core.dex import DexIndex, find_contract_target
from harness.reporting.reporter import PatchAuditResult, PatchStatus
from harness.xiaomi.contracts import XIAOMI_EARBUDS_PATCH_CONTRACTS


class XiaomiEarbudsValidator:
    def __init__(self, repo_root: Path, dex_index: DexIndex, apk_ctx: Any):
        self.repo_root = repo_root
        self.dex_index = dex_index
        self.apk_ctx = apk_ctx

    def audit_all_patches(self) -> Dict[str, PatchAuditResult]:
        results: Dict[str, PatchAuditResult] = {}

        for contract in XIAOMI_EARBUDS_PATCH_CONTRACTS:
            status = PatchStatus.VERIFIED
            details = []
            blocking_reasons = []
            evidence = []
            fp_results = []

            found_classes = []
            for cls_desc in contract.required_classes:
                matched = self.dex_index.find_class(cls_desc)
                if matched:
                    evidence.append(f"Found class `{cls_desc}` in `{matched.dex_name}`")
                    fp_results.append((cls_desc, PatchStatus.VERIFIED.value, matched.dex_name))
                    found_classes.append(matched)
                else:
                    # Report this class with its own outcome: copying the contract-level
                    # status here marked resolved classes as BLOCKED and vice versa.
                    fp_results.append((cls_desc, "NOT FOUND", "NONE"))
                    status = PatchStatus.BLOCKED if contract.criticality in ("CRITICAL", "HIGH") else PatchStatus.STATICALLY_VERIFIED
                    blocking_reasons.append(f"Missing required class `{cls_desc}`")

            for req_str in contract.required_strings:
                matched_methods = find_contract_target(self.dex_index, found_classes, req_str)

                if matched_methods:
                    evidence.append(f"Target `{req_str}` found ({len(matched_methods)} occurrence(s))")
                else:
                    if contract.criticality in ("CRITICAL", "HIGH"):
                        status = PatchStatus.BLOCKED
                        blocking_reasons.append(f"Target `{req_str}` not found")
                    else:
                        details.append(f"Target `{req_str}` not found")

            results[contract.patch_id] = PatchAuditResult(
                patch_name=contract.name,
                status=status,
                fingerprint_results=fp_results,
                blocking_reasons=blocking_reasons,
                evidence=evidence,
            )

        return results
