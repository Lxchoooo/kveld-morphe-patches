"""
Unit Tests for the Xiaomi Earbuds adversarial validator.

Focus: per-class fingerprint reporting must reflect each class' own outcome
instead of copying the contract-level status.
"""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import harness.xiaomi.validator as xiaomi_validator
from harness.migration.validator import PatchStatus
from harness.xiaomi.contracts import PatchContract


FOUND_CLASS = "Lcom/xiaomi/found;"
MISSING_CLASS = "Lcom/xiaomi/missing;"


class _FakeIndexedClass:
    def __init__(self, dex_name: str):
        self.dex_name = dex_name
        self.methods = []


class TestXiaomiValidator(unittest.TestCase):

    def setUp(self):
        self.dex_index = MagicMock()
        self.dex_index.find_class.side_effect = (
            lambda desc: _FakeIndexedClass("classes.dex") if desc == FOUND_CLASS else None
        )
        self.validator = xiaomi_validator.XiaomiEarbudsValidator(
            Path("/tmp"), self.dex_index, MagicMock()
        )

    def _run_single_contract(self):
        contract = PatchContract(
            patch_id="mixed_contract",
            name="Mixed Contract",
            target_type="bytecode",
            description="Synthetic contract for unit tests",
            required_classes=[FOUND_CLASS, MISSING_CLASS],
            required_strings=["someTarget"],
            criticality="HIGH",
        )
        with patch.object(xiaomi_validator, "XIAOMI_EARBUDS_PATCH_CONTRACTS", [contract]), \
             patch.object(xiaomi_validator, "find_contract_target", return_value=[object()]):
            return self.validator.audit_all_patches()["mixed_contract"]

    def test_found_class_is_not_reported_as_blocked(self):
        result = self._run_single_contract()
        by_class = {fp[0]: fp[1] for fp in result.fingerprint_results}
        self.assertEqual(by_class[FOUND_CLASS], PatchStatus.VERIFIED.value)
        self.assertEqual(by_class[MISSING_CLASS], "NOT FOUND")

    def test_contract_status_still_reflects_the_missing_class(self):
        result = self._run_single_contract()
        self.assertEqual(result.status, PatchStatus.BLOCKED)
        self.assertIn(f"Missing required class `{MISSING_CLASS}`", result.blocking_reasons)

    def test_fully_resolved_contract_is_verified(self):
        contract = PatchContract(
            patch_id="clean_contract",
            name="Clean Contract",
            target_type="bytecode",
            description="Synthetic contract for unit tests",
            required_classes=[FOUND_CLASS],
            required_strings=["someTarget"],
            criticality="HIGH",
        )
        self.dex_index.find_class.side_effect = lambda desc: _FakeIndexedClass("classes.dex")
        with patch.object(xiaomi_validator, "XIAOMI_EARBUDS_PATCH_CONTRACTS", [contract]), \
             patch.object(xiaomi_validator, "find_contract_target", return_value=[object()]):
            result = self.validator.audit_all_patches()["clean_contract"]
        self.assertEqual(result.status, PatchStatus.VERIFIED)
        self.assertEqual([fp[1] for fp in result.fingerprint_results], [PatchStatus.VERIFIED.value])
        self.assertEqual(result.blocking_reasons, [])


if __name__ == "__main__":
    unittest.main()