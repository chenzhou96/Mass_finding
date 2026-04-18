import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from package.service.formula_search_service import (
    SearchStatus,
    FormulaSearchResult,
    FormulaSearchPubChem,
    SearchManager,
    _build_pubchem_compounds_from_cids,
    _load_latest_pubchem_raw_results,
    _rank_compounds,
    _save_pubchem_raw_data,
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
    def test_property_fetch_enriches_synonyms_from_pubchem_endpoint(self):
        def fake_fetch(url, timeout=30, endpoint_label="unknown"):
            if "/property/" in url:
                cid_text = url.split('/cid/')[1].split('/property/')[0]
                cid_values = [int(item) for item in cid_text.split(',') if item]
                return {
                    "PropertyTable": {
                        "Properties": [
                            {
                                "CID": cid,
                                "Title": "Ibuprofen, (+-)-" if cid == 3672 else f"Compound {cid}",
                                "IUPACName": "2-[4-(2-methylpropyl)phenyl]propanoic acid" if cid == 3672 else f"Compound {cid}",
                                "MolecularWeight": 206.28,
                                "MonoisotopicMass": 206.130679813,
                            }
                            for cid in cid_values
                        ]
                    }
                }
            if "/synonyms/" in url:
                cid_text = url.split('/cid/')[1].split('/synonyms/')[0]
                cid_values = [int(item) for item in cid_text.split(',') if item]
                return {
                    "InformationList": {
                        "Information": [
                            {
                                "CID": cid,
                                "Synonym": ["Ibuprofen", "Advil", "DrugBank: DB01050"] if cid == 3672 else [f"Compound {cid}"]
                            }
                            for cid in cid_values
                        ]
                    }
                }
            raise AssertionError(f"unexpected url: {url}")

        with patch("package.service.formula_search_service._fetch_pubchem_json", side_effect=fake_fetch):
            result = _build_pubchem_compounds_from_cids([3672], chunk_size=10, per_batch_retries=1)

        self.assertEqual(result["compounds"][0]["synonyms"], ["Ibuprofen", "Advil", "DrugBank: DB01050"])

    def test_ranking_uses_title_fallback_when_synonyms_are_missing(self):
        compounds = [
            {
                "cid": 3672,
                "title": "Ibuprofen, (+-)-",
                "iupac_name": "2-[4-(2-methylpropyl)phenyl]propanoic acid",
                "inchi": "InChI=1S/C13H18O2/test",
                "inchikey": "HEFNNWSXXWATRW-UHFFFAOYSA-N",
                "monoisotopic_mass": 206.130679813,
                "molecular_weight": 206.28,
                "xlogp": 3.5,
                "tpsa": 37.3,
                "hbond_donor_count": 1,
                "hbond_acceptor_count": 2,
                "charge": 0,
                "synonyms": [],
            },
            {
                "cid": 23235,
                "title": "Hexyl benzoate",
                "iupac_name": "hexyl benzoate",
                "inchi": "InChI=1S/C13H18O2/other",
                "inchikey": "UUGLJVMIFJNVFH-UHFFFAOYSA-N",
                "monoisotopic_mass": 206.130679813,
                "molecular_weight": 206.28,
                "xlogp": 3.5,
                "tpsa": 37.3,
                "hbond_donor_count": 1,
                "hbond_acceptor_count": 2,
                "charge": 0,
                "synonyms": [],
            },
        ]

        ranked = _rank_compounds(compounds, ion_mode="both", strict_filter=True)

        self.assertEqual(ranked[0]["cid"], 3672)
        self.assertGreater(ranked[0]["score_breakdown"]["prevalence"], 0.0)

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

    def test_pubchem_raw_cache_is_saved_under_formula_folder(self):
        with TemporaryDirectory() as temp_dir:
            raw_cache_root = Path(temp_dir)
            fake_path_manager = type("FakePathManager", (), {
                "get_pubchem_raw_cache_path": lambda self: raw_cache_root,
                "get_pubchem_formula_cache_dir": lambda self, formula: raw_cache_root / str(formula),
                "ensure_pubchem_formula_cache_dir": lambda self, formula: ((raw_cache_root / str(formula)).mkdir(parents=True, exist_ok=True) or (raw_cache_root / str(formula))),
            })()

            with patch("package.service.formula_search_service.PathManager", return_value=fake_path_manager):
                _save_pubchem_raw_data("C13H18O2", [{"cid": 3672, "iupac_name": "ibuprofen"}])

            formula_dir = raw_cache_root / "C13H18O2"
            saved_files = list(formula_dir.glob("pubchem_raw_C13H18O2_*.json"))
            self.assertTrue(formula_dir.exists())
            self.assertEqual(len(saved_files), 1)

    def test_pubchem_raw_cache_loader_supports_formula_folder_and_legacy_flat_files(self):
        with TemporaryDirectory() as temp_dir:
            raw_cache_root = Path(temp_dir)
            fake_path_manager = type("FakePathManager", (), {
                "get_pubchem_raw_cache_path": lambda self: raw_cache_root,
                "get_pubchem_formula_cache_dir": lambda self, formula: raw_cache_root / str(formula),
                "ensure_pubchem_formula_cache_dir": lambda self, formula: ((raw_cache_root / str(formula)).mkdir(parents=True, exist_ok=True) or (raw_cache_root / str(formula))),
            })()

            legacy_file = raw_cache_root / "pubchem_raw_C2H7NO2_20260416_010101.json"
            legacy_file.write_text(
                '{"metadata":{"formula":"C2H7NO2"},"raw_results":[{"cid":1}]}',
                encoding="utf-8",
            )

            formula_dir = raw_cache_root / "C13H18O2"
            formula_dir.mkdir(parents=True, exist_ok=True)
            nested_file = formula_dir / "pubchem_raw_C13H18O2_20260416_020202.json"
            nested_file.write_text(
                '{"metadata":{"formula":"C13H18O2"},"raw_results":[{"cid":3672}]}',
                encoding="utf-8",
            )

            with patch("package.service.formula_search_service.PathManager", return_value=fake_path_manager):
                nested_payload = _load_latest_pubchem_raw_results("C13H18O2")
                legacy_payload = _load_latest_pubchem_raw_results("C2H7NO2")

            self.assertEqual(nested_payload["metadata"]["formula"], "C13H18O2")
            self.assertEqual(legacy_payload["metadata"]["formula"], "C2H7NO2")

    def test_pubchem_no_compounds_stops_retries_early(self):
        searcher = FormulaSearchPubChem(max_retries=3, retry_delay=2)
        calls = []

        def fake_try(formula, fast=False, timeout=30, poll_interval=2, poll_max_attempts=6):
            calls.append((formula, fast))
            return {
                "cids": None,
                "error": "no_compounds:formula_http_400",
                "endpoint": "fastformula" if fast else "formula",
            }

        with patch("package.service.formula_search_service._try_pubchem_formula_search_rest", side_effect=fake_try), \
             patch("package.service.formula_search_service.time.sleep") as sleep_mock:
            result = searcher.get_compounds("C5HNO")

        self.assertIsNone(result)
        self.assertEqual(searcher.get_last_error()["category"], "no_compounds")
        self.assertEqual(len(calls), 2)
        sleep_mock.assert_not_called()

    def test_search_manager_emits_progress_callback_for_each_formula(self):
        payloads = {
            "A": {"compounds": [{"cid": 1, "title": "A"}], "is_partial": False},
            "B": {"compounds": [], "is_partial": False},
        }
        progress_calls = []

        class CallbackSearcher:
            def get_compounds(self, formula: str):
                return payloads[formula]

            def get_last_error(self):
                return {"category": "no_compounds", "message": "empty"}

        with patch("package.service.formula_search_service.ExporterFactory.get_exporter", return_value=DummyExporter()), \
             patch("package.service.formula_search_service._save_pubchem_raw_data"), \
             patch("package.service.formula_search_service._load_latest_pubchem_raw_results", return_value=None):
            manager = SearchManager(
                CallbackSearcher(),
                "json_formulaSearch_PubChem",
                progress_callback=lambda payload: progress_calls.append(payload),
            )
            results = manager.search_formula_list(["A", "B"])

        self.assertEqual([item["formula"] for item in progress_calls], ["A", "B"])
        self.assertEqual(progress_calls[0]["status"], "success")
        self.assertEqual(progress_calls[1]["status"], "failed")
        self.assertIn("A", results["success"])
        self.assertIn("B", results["failed"])

    def test_min_split_size_never_recurses_below_floor(self):
        chunk_sizes = []

        def fake_fetch(url, timeout=30, endpoint_label="unknown"):
            cid_text = url.split('/cid/')[1].split('/')[0]
            cid_values = [int(item) for item in cid_text.split(',') if item]
            chunk_sizes.append(len(cid_values))
            raise RuntimeError("simulated batch failure")

        with patch("package.service.formula_search_service._fetch_pubchem_json", side_effect=fake_fetch):
            result = _build_pubchem_compounds_from_cids(
                list(range(1, 13)),
                chunk_size=100,
                per_batch_retries=1,
                min_split_size=10,
            )

        self.assertEqual(result["compounds"], [])
        self.assertTrue(chunk_sizes)
        self.assertTrue(all(size >= 10 for size in chunk_sizes), chunk_sizes)


if __name__ == "__main__":
    unittest.main()
