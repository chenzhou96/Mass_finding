import unittest
from unittest.mock import patch

from package.service.formula_search_service import (
    SearchStatus,
    FormulaSearchResult,
    SearchManager,
    _build_pubchem_compounds_from_cids,
)


class DummySearcher:
    def __init__(self, compounds=None, error=None):
        self._compounds = compounds
        self._error = error or {
            "category": "timeout",
            "message": "timeout:test",
        }

    def get_compounds(self, formula: str):
        return self._compounds

    def get_last_error(self):
        return self._error


class DummyExporter:
    def export(self, results):
        formula, compounds = results
        return {
            "metadata": {
                "molecular_formula": formula,
                "result_count": len(compounds),
            },
            "results": list(compounds),
        }


class PubChemBatchingTests(unittest.TestCase):
    def test_partial_batch_failure_preserves_successful_compounds(self):
        calls = {"count": 0}

        def fake_fetch(url, timeout=30, endpoint_label="unknown"):
            calls["count"] += 1
            cid_text = url.split('/cid/')[1].split('/property/')[0]
            cid_values = [int(item) for item in cid_text.split(',') if item]
            if any(cid in (3, 4) for cid in cid_values):
                raise RuntimeError("simulated batch failure")
            return {
                "PropertyTable": {
                    "Properties": [
                        {
                            "CID": cid,
                            "Title": f"Compound {cid}",
                            "MolecularWeight": float(cid),
                        }
                        for cid in cid_values
                    ]
                }
            }

        with patch("package.service.formula_search_service._fetch_pubchem_json", side_effect=fake_fetch):
            result = _build_pubchem_compounds_from_cids([1, 2, 3, 4], chunk_size=2, per_batch_retries=2)

        self.assertIsInstance(result, dict)
        self.assertEqual(len(result["compounds"]), 2)
        self.assertTrue(result["is_partial"])
        self.assertGreaterEqual(len(result["failed_batches"]), 1)

    def test_search_manager_treats_partial_result_as_partial_not_failed(self):
        partial_payload = {
            "compounds": [{"CID": 1, "Title": "A"}],
            "is_partial": True,
            "failed_batches": [{"batch_index": 2, "reason": "timeout"}],
            "batch_summary": {
                "total_batches": 2,
                "success_batches": 1,
                "failed_batches": 1,
            },
            "error": "partial_batch_failure",
        }

        with patch("package.service.formula_search_service.ExporterFactory.get_exporter", return_value=DummyExporter()), \
             patch("package.service.formula_search_service._save_pubchem_raw_data"), \
             patch("package.service.formula_search_service._load_latest_pubchem_raw_results", return_value=None):
            manager = SearchManager(DummySearcher(compounds=partial_payload), "json_formulaSearch_PubChem")
            results = manager.search_formula_list(["TEST_PARTIAL_FORMULA"])

        self.assertIn("TEST_PARTIAL_FORMULA", results["success"])
        self.assertIn("TEST_PARTIAL_FORMULA", results["partial"])
        self.assertEqual(results["failed"], [])
        self.assertEqual(results["partial_stats"]["partial"], 1)
        detail = results["failed_details"]["TEST_PARTIAL_FORMULA"]
        self.assertEqual(detail["category"], "partial")


if __name__ == "__main__":
    unittest.main()
