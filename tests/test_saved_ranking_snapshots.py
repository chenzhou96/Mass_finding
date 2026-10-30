"""Synthetic saved-score snapshots; not calibrated identification evidence."""
import copy
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from package.gui.pages.formula_search_page import FormulaSearchPage
from package.gui.pages.score_statistics_page import ScoreStatisticsPage
from package.service.formula_search_service import _rank_compounds, rerank_cached_compounds


class SavedRankingSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.path = self.directory / 'formula_search_results_CH4.json'
        paths = SimpleNamespace(get_formula_search_cache_path=lambda: self.directory)
        self.search = FormulaSearchPage.__new__(FormulaSearchPage)
        self.search.path_manager = paths
        self.stats = ScoreStatisticsPage.__new__(ScoreStatisticsPage)
        self.stats.path_manager = paths

    def save(self, rows):
        payload = {'metadata': {'status': 'partial', 'top_final_score': 91.25,
                    'batch_summary': {'missing_synonym_cids': [1]}}, 'results': rows}
        self.path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        return payload

    def test_legacy_snapshot_readers_preserve_saved_scores_order_and_explanations(self):
        payload = self.save([
            {'cid': 2, 'title': '历史候选', 'final_score': 91.25, 'rank': 1,
             'why_selected': ['Saved legacy reason'], 'score_breakdown': {'prevalence': .9}},
            {'cid': 1, 'final_score': 80, 'rank': 2, 'synonyms': ['ACS reagent grade'],
             'synonyms_complete': False, 'properties_complete': True}])
        before = self.path.read_bytes()
        self.assertEqual(self.search._load_cached_result_for_formula('CH4'), payload)
        self.assertEqual(self.stats._load_compounds('CH4'), payload['results'])
        self.assertEqual(self.path.read_bytes(), before)

    def test_current_positive_negative_snapshots_are_not_forced_to_both_mode(self):
        for mode in ('positive', 'negative'):
            with self.subTest(mode=mode):
                rows = _rank_compounds([{'cid': 1, 'title': 'Synthetic', 'hbond_donor_count': 8,
                    'hbond_acceptor_count': 0, 'charge': -1, 'synonyms': ['ACS reagent grade']}], ion_mode=mode)
                payload = self.save(rows)
                self.assertEqual(self.search._load_cached_result_for_formula('CH4'), payload)
                self.assertEqual(self.stats._load_compounds('CH4'), rows)

    def test_loading_does_not_apply_new_strict_filters_to_saved_snapshot(self):
        rows = [{'cid': 1, 'final_score': 50, 'covalent_unit': 2,
                 'ranking_model': 'saved-model', 'ranking_evidence': {'source': 'saved'}}]
        payload = self.save(rows)
        self.assertEqual(self.search._load_cached_result_for_formula('CH4'), payload)
        self.assertEqual(self.stats._load_compounds('CH4'), rows)

    def test_unscored_or_invalid_scores_are_unavailable_not_silently_recomputed(self):
        for invalid in (None, '91.25', True, float('nan'), float('inf'), -1, 101):
            with self.subTest(score=invalid):
                self.save([{'cid': 1, 'final_score': invalid}])
                self.assertIsNone(self.stats._load_compounds('CH4'))
        self.save([{'cid': 1}])
        self.assertIsNone(self.stats._load_compounds('CH4'))
        self.save([{'cid': 1, 'final_score': 90}, {'cid': 2, 'final_score': None}])
        self.assertIsNone(self.stats._load_compounds('CH4'))
        self.save([])
        self.assertEqual(self.stats._load_compounds('CH4'), [])

    def test_statistics_threshold_uses_saved_scores(self):
        self.save([{'cid': 1, 'final_score': 91.25}, {'cid': 2, 'final_score': 20}])
        page = self.stats
        page.threshold_spinbox = SimpleNamespace(get=lambda: '85')
        page.formula_list = ['CH4']
        page.statistics_data = {}
        page._current_compounds = []
        page.compound_listbox = SimpleNamespace(delete=lambda *_args: None)
        page._clear_structure = lambda: None
        page._refresh_tree = lambda: None
        page.summary_var = SimpleNamespace(set=lambda _text: None)
        page._run_statistics()
        self.assertEqual(page.statistics_data['CH4']['above'], 1)
        self.assertEqual(page.statistics_data['CH4']['top_score'], 91.25)
        self.assertEqual(page.statistics_data['CH4']['pct'], 50)

    def test_statistics_reports_unavailable_snapshots_without_fabricating_scores(self):
        self.save([{'cid': 1, 'final_score': 0}])
        page = self.stats
        page.threshold_spinbox = SimpleNamespace(get=lambda: '0')
        page.formula_list = ['CH4', 'MISSING']
        page.statistics_data = {}
        page._current_compounds = []
        page.compound_listbox = SimpleNamespace(delete=lambda *_args: None)
        page._clear_structure = lambda: None
        page._refresh_tree = lambda: None
        page.summary_var = SimpleNamespace(set=lambda _text: None)
        with patch('package.gui.pages.score_statistics_page.messagebox.showwarning') as warning:
            page._run_statistics()
        self.assertEqual(page.statistics_data['CH4']['above'], 1)
        self.assertNotIn('MISSING', page.statistics_data)
        warning.assert_called_once()
        self.assertIn('MISSING', warning.call_args.args[1])
        self.assertIn('未自动重算或补零', warning.call_args.args[1])

    def test_malformed_snapshots_do_not_masquerade_as_empty_valid_results(self):
        for payload in ([], {}, {'results': {}}, {'results': [None]}, {'results': ['bad']}):
            with self.subTest(payload=payload):
                self.path.write_text(json.dumps(payload), encoding='utf-8')
                self.assertIsNone(self.search._load_cached_result_for_formula('CH4'))
                self.assertIsNone(self.stats._load_compounds('CH4'))

    def test_explicit_reranking_remains_available_and_does_not_mutate_input(self):
        rows = [{'cid': 1, 'final_score': 91.25, 'synonyms': ['ACS reagent grade']}]
        original = copy.deepcopy(rows)
        with patch('package.service.formula_search_service._fetch_pubchem_json',
                   side_effect=AssertionError('offline rebuild must not retrieve')):
            rebuilt = rerank_cached_compounds(rows)
        self.assertEqual(rows, original)
        self.assertNotEqual(rebuilt[0]['final_score'], 91.25)
        self.assertEqual(rebuilt[0]['ranking_model'], 'pubchem-reagent-prior-v1')


if __name__ == '__main__':
    unittest.main()
