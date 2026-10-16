"""Synthetic ranking contracts, not measured occurrence or identification truth."""
import copy
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from package.service import formula_search_service as service
from package.service.public import JSONExporter_formulaSearch_PubChem


def record(cid=1, synonyms=None, **extra):
    result = dict(cid=cid, title='Candidate', iupac_name='candidate', synonyms=synonyms or [])
    result.update(extra)
    return result


def ranked(item):
    return service._rank_compounds([item], strict_filter=False)[0]


class CandidateRankingTests(unittest.TestCase):
    def test_duplicate_aliases_cannot_inflate_score(self):
        one = ranked(record(synonyms=['Chemical name']))
        many = ranked(record(synonyms=['Chemical name', ' chemical NAME ', 'Chemical name'] * 50))
        self.assertEqual(one['final_score'], many['final_score'])
        self.assertEqual(many['public_record_count'], 1)

    def test_short_keyword_substrings_are_not_commercial_evidence(self):
        for name in ('Heptane', 'suspension', 'peptide', 'grade', 'solution', 'USP', 'EP', 'reagent'):
            with self.subTest(name=name):
                row = ranked(record(synonyms=[name]))
                self.assertEqual(row['score_breakdown']['commercial_availability'], 0)

    def test_explicit_negation_and_ambiguous_vendor_abbreviation_are_not_positive(self):
        for name in ('not for molecular biology', 'not reagent grade', 'non-reagent grade',
                     'not intended for molecular biology', 'TCI'):
            with self.subTest(name=name):
                self.assertEqual(ranked(record(synonyms=[name]))['score_breakdown']['commercial_availability'], 0)

    def test_explicit_commercial_clue_outweighs_alias_volume(self):
        rows = service._rank_compounds([
            record(1, [f'Unrelated alias {i}' for i in range(500)]),
            record(2, ['ACS reagent grade'])], strict_filter=False)
        self.assertEqual(rows[0]['cid'], 2)

    def test_commercial_clue_still_matters_for_alias_rich_records(self):
        aliases = [f'Alias {i}' for i in range(100)]
        self.assertGreater(ranked(record(synonyms=aliases + ['for molecular biology']))['final_score'],
                           ranked(record(synonyms=aliases))['final_score'])

    def test_title_clue_is_not_erased_by_one_synonym(self):
        first = ranked(record(title='ACS reagent grade', synonyms=[]))
        second = ranked(record(title='ACS reagent grade', synonyms=['one alias']))
        self.assertEqual(first['score_breakdown']['commercial_availability'],
                         second['score_breakdown']['commercial_availability'])
        self.assertGreater(first['score_breakdown']['commercial_availability'], 0)

    def test_generic_name_support_is_monotonic_and_preserves_stereo_punctuation(self):
        a = ranked(record(title='Common name', iupac_name='systematic long name'))
        b = ranked(record(title='Common name', iupac_name='systematic long name', synonyms=['one alias']))
        self.assertGreaterEqual(b['score_breakdown']['annotation_support'], a['score_breakdown']['annotation_support'])
        self.assertEqual(service._distinct_synonyms(['(R)-name', '(S)-name', 'NAME', ' name ']),
                         ['(R)-name', '(S)-name', 'NAME'])

    def test_repeating_or_stacking_same_commercial_family_is_bounded(self):
        base = ranked(record(synonyms=['reagent grade']))
        repeated = ranked(record(synonyms=['reagent grade', 'ACS reagent', 'analytical grade'] * 100))
        self.assertEqual(base['score_breakdown']['commercial_availability'],
                         repeated['score_breakdown']['commercial_availability'])

    def test_standard_clue_is_weaker_than_reagent_grade_clue(self):
        standard = ranked(record(synonyms=['reference standard']))
        reagent = ranked(record(synonyms=['reagent grade']))
        self.assertLess(standard['score_breakdown']['commercial_availability'],
                        reagent['score_breakdown']['commercial_availability'])

    def test_commercial_evidence_is_explainable_and_unverified(self):
        row = ranked(record(synonyms=['Sigma-Aldrich', 'ACS reagent grade']))
        evidence = row['ranking_evidence']
        self.assertEqual(evidence['market_availability'], 'unverified')
        self.assertEqual(evidence['commercial_matches'][0]['field'], 'synonyms')
        self.assertTrue(any('ACS reagent' in match['text'] for match in evidence['commercial_matches']))
        self.assertTrue(any('商品化文本线索' in reason for reason in row['why_selected']))

    def test_registry_markers_require_token_boundaries(self):
        for name in ('CAScade', 'unilateral', 'chebiology', 'pubchemical'):
            with self.subTest(name=name):
                self.assertEqual(ranked(record(synonyms=[name]))['reference_markers']['public_markers'], [])
        row = ranked(record(synonyms=['ChEBI:123', 'CHEBI:456', 'KEGG:C00001']))
        self.assertEqual(row['reference_markers']['public_markers'], ['CHEBI', 'KEGG'])

    def test_no_named_compound_whitelist_bonus(self):
        a = ranked(record(title='Ibuprofen', iupac_name='Ibuprofen'))
        b = ranked(record(title='Othername', iupac_name='Othername'))
        self.assertEqual(a['score_breakdown']['prevalence'], b['score_breakdown']['prevalence'])

    def test_partial_and_missing_metadata_stay_unknown_not_unavailable(self):
        for complete in (False, True, None):
            with self.subTest(complete=complete):
                row = ranked(record(synonyms_complete=complete, properties_complete=False))
                self.assertIs(row['synonyms_complete'], complete)
                self.assertFalse(row['properties_complete'])
                self.assertEqual(row['ranking_evidence']['market_availability'], 'unverified')
                if complete is False:
                    self.assertTrue(any('缺口' in reason for reason in row['why_selected']))

    def test_version_weights_and_score_are_reproducible(self):
        for mode in ('positive', 'negative', 'both'):
            with self.subTest(mode=mode):
                row = service._rank_compounds([record(synonyms=['reagent grade', 'ChEBI:123'])],
                                             ion_mode=mode, strict_filter=False)[0]
                self.assertEqual(row['ranking_model'], 'pubchem-reagent-prior-v1')
                weights = row['score_weights']
                self.assertAlmostEqual(sum(weights.values()), 1)
                total = sum(weights[key] * row['score_breakdown'][key] for key in weights)
                self.assertAlmostEqual(row['final_score'], total * 100, delta=0.015)

    def test_ranking_is_nonmutating_and_keeps_rare_candidates(self):
        source = [record(1), record(2, ['reagent grade'])]
        original = copy.deepcopy(source)
        rows = service._rank_compounds(source, strict_filter=False)
        self.assertEqual(source, original)
        self.assertEqual({row['cid'] for row in rows}, {1, 2})

    def test_prior_and_all_scores_stay_finite_and_bounded(self):
        row = ranked(record(synonyms=[f'Alias {i} ChEBI:1 KEGG:2 Sigma-Aldrich reagent grade reference standard' for i in range(200)]))
        self.assertLessEqual(row['score_breakdown']['commercial_availability'], .65)
        self.assertLessEqual(row['score_breakdown']['annotation_support'], .35)
        self.assertTrue(all(0 <= value <= 1 for value in row['score_breakdown'].values()))
        self.assertTrue(0 <= row['final_score'] <= 100)

    def test_ranking_requires_no_new_network_call(self):
        with patch.object(service, '_fetch_pubchem_json', side_effect=AssertionError('ranking is offline')):
            self.assertEqual(len(service._rank_compounds([record()], strict_filter=False)), 1)

    def test_lone_standard_does_not_overcome_strong_annotation(self):
        aliases = [f'Alias {i}' for i in range(60)] + ['ChEBI:1', 'KEGG:2', 'HMDB00001']
        rows = service._rank_compounds([record(1, ['reference standard']),
                                       record(2, aliases, title='Common name')], strict_filter=False)
        self.assertEqual(rows[0]['cid'], 2)

    def test_title_and_synonym_same_category_are_counted_once(self):
        a = ranked(record(synonyms=['reagent grade']))
        b = ranked(record(synonyms=['reagent grade'], title='ACS reagent grade'))
        self.assertEqual(a['score_breakdown']['commercial_availability'], b['score_breakdown']['commercial_availability'])
        self.assertEqual(len(b['ranking_evidence']['commercial_matches']), 1)

    def test_commercial_score_is_invariant_to_alias_order_and_whitespace(self):
        aliases = ['ACS  reagent', 'ACS reagent', 'ACS\treagent']
        a = ranked(record(synonyms=aliases))
        b = ranked(record(synonyms=list(reversed(aliases))))
        self.assertEqual(a['final_score'], b['final_score'])
        self.assertEqual(a['score_breakdown']['commercial_availability'], .45)
        self.assertEqual(a['ranking_evidence']['commercial_matches'][0]['text'], aliases[0])

    def test_export_reload_retains_version_evidence_weights_and_partial(self):
        row = ranked(record(synonyms=['reagent grade'], synonyms_complete=False))
        with TemporaryDirectory() as temp:
            class Paths:
                def get_mass_finding_cache_path(self): return Path(temp)
                def get_formula_search_cache_path(self): return Path(temp)
            with patch('package.service.public.PathManager', Paths):
                exported = JSONExporter_formulaSearch_PubChem().export_with_completeness(
                    ('CH4', [row]), {'status': 'partial', 'batch_summary': {'missing_synonym_cids': [1]}})
            disk = json.loads((Path(temp) / 'formula_search_results_CH4.json').read_text())
        self.assertEqual(disk, exported)
        for key in ('ranking_model', 'ranking_evidence', 'score_weights', 'score_breakdown', 'why_selected'):
            self.assertEqual(disk['results'][0][key], row[key])
        self.assertFalse(disk['results'][0]['synonyms_complete'])
        self.assertEqual(disk['metadata']['status'], 'partial')

    def test_desktop_detail_explains_current_and_legacy_scores(self):
        from types import SimpleNamespace
        from package.gui.pages.formula_search_page import FormulaSearchPage
        class Text:
            def config(self, **_kwargs): pass
            def delete(self, *_args): pass
            def insert(self, _position, text): self.text = text
        for row in (ranked(record(synonyms=['reagent grade'], synonyms_complete=False)), {'cid': 2}):
            with self.subTest(row=row):
                widget = Text()
                page = SimpleNamespace(compound_listbox=SimpleNamespace(curselection=lambda: [0]),
                    current_formula_results=[row], result_text=widget,
                    _extract_cas_numbers_for_display=lambda _item: [], _render_structure_image=lambda *_args: None)
                FormulaSearchPage._on_compound_select(page)
                self.assertIn('not probability', widget.text)
                self.assertIn('market availability and usage frequency unverified', widget.text)
                if row.get('ranking_model'):
                    self.assertIn('pubchem-reagent-prior-v1', widget.text)
                    self.assertIn('Text clue [synonyms]: reagent grade', widget.text)

    def test_current_and_legacy_smiles_keys_preserve_stereochemistry(self):
        for values in ({'SMILES': 'F[C@H](Cl)Br', 'ConnectivitySMILES': 'FC(Cl)Br'},
                       {'smiles': 'F[C@H](Cl)Br', 'connectivity_smiles': 'FC(Cl)Br'},
                       {'IsomericSMILES': 'F[C@H](Cl)Br', 'CanonicalSMILES': 'FC(Cl)Br'}):
            with self.subTest(values=values):
                row = service._normalize_pubchem_compound(values)
                self.assertEqual(row['isomeric_smiles'], 'F[C@H](Cl)Br')
                self.assertEqual(row['canonical_smiles'], 'FC(Cl)Br')
        row = service._normalize_pubchem_compound({'ConnectivitySMILES': 'FC(Cl)Br'})
        self.assertIsNone(row['isomeric_smiles'])
        row = service._normalize_pubchem_compound({'isomeric_smiles': 'legacy', 'SMILES': 'new'})
        self.assertEqual(row['isomeric_smiles'], 'legacy')

    def test_current_property_response_retains_both_smiles_fields(self):
        def fetch(url, **_kwargs):
            if '/synonyms/' in url:
                return {'InformationList': {'Information': [{'CID': 1, 'Synonym': []}]}}
            return {'PropertyTable': {'Properties': [{'CID': 1, 'SMILES': 'F[C@H](Cl)Br',
                                                       'ConnectivitySMILES': 'FC(Cl)Br'}]}}
        with patch.object(service, '_fetch_pubchem_json', side_effect=fetch):
            result = service._build_pubchem_compounds_from_cids([1], per_batch_retries=1)
        row = ranked(result['compounds'][0])
        self.assertEqual(row['isomeric_smiles'], 'F[C@H](Cl)Br')
        self.assertEqual(row['canonical_smiles'], 'FC(Cl)Br')


if __name__ == '__main__':
    unittest.main()
