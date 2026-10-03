"""Synthetic PubChem payloads; no network or native desktop is required."""
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from package.service import formula_search_service as service
from package.service.public import JSONExporter_formulaSearch_PubChem


def property_record(cid, synonyms=None, complete=None):
    result = {'CID': cid, 'Title': f'Candidate {cid}', 'MonoisotopicMass': 46.041864812,
              'MolecularWeight': 46.07, 'synonyms': synonyms or []}
    if complete is not None:
        result['synonyms_complete'] = complete
    return result


def failure(cid=2):
    return {'cids': [cid], 'cid_count': 1, 'reason': 'synonym_fetch_failed:timeout'}


class DummyExporter:
    def export(self, payload):
        formula, compounds = payload
        return {'metadata': {'molecular_formula': formula}, 'results': compounds}


class PubChemCompletenessTests(unittest.TestCase):
    def builder(self, response, callbacks=None):
        def fetch(url, **kwargs):
            if '/synonyms/' in url:
                if isinstance(response, Exception):
                    raise response
                return response
            return {'PropertyTable': {'Properties': [property_record(1), property_record(2)]}}
        with patch.object(service, '_fetch_pubchem_json', side_effect=fetch), patch.object(service.time, 'sleep'):
            return service._build_pubchem_compounds_from_cids([1, 2], chunk_size=2,
                per_batch_retries=1, min_split_size=2, progress_callback=(callbacks.append if callbacks is not None else None))

    def test_property_complete_synonym_failure_is_partial_in_every_checkpoint(self):
        checkpoints = []
        result = self.builder(TimeoutError('synthetic timeout'), checkpoints)
        self.assertEqual(result['batch_summary']['missing_cids'], [])
        self.assertEqual(result['batch_summary']['missing_synonym_cids'], [1, 2])
        self.assertEqual(result['batch_summary']['success_batches'], 1)
        self.assertEqual(result['batch_summary']['property_failed_batches'], 0)
        self.assertEqual(result['batch_summary']['synonym_failed_batches'], 1)
        self.assertTrue(result['is_partial'])
        self.assertEqual(result['error'], 'partial_synonym_enrichment')
        self.assertTrue(all(p['is_partial'] for p in checkpoints))

    def test_successful_empty_synonyms_are_complete(self):
        result = self.builder({'InformationList': {'Information': [
            {'CID': 1, 'Synonym': []}, {'CID': 2, 'Synonym': []}]}})
        self.assertFalse(result['is_partial'])
        self.assertTrue(all(row['synonyms_complete'] for row in result['compounds']))
        self.assertEqual(result['batch_summary']['missing_synonym_cids'], [])

    def test_successful_http_response_with_omitted_cid_is_partial(self):
        result = self.builder({'InformationList': {'Information': [{'CID': 1, 'Synonym': ['record one']}]}})
        self.assertTrue(result['is_partial'])
        self.assertEqual(result['batch_summary']['missing_synonym_cids'], [2])
        self.assertEqual(result['failed_batches'][0]['cids'], [2])

    def test_explicit_incomplete_flag_is_authoritative(self):
        self.assertEqual(service._missing_synonym_cids([1], [property_record(1, ['old subset'], False)]), [1])

    def search_with_cache(self, cache, repair):
        searcher = service.FormulaSearchPubChem(max_retries=1, property_batch_retries=1)
        patches = [patch.object(service, '_load_latest_pubchem_raw_results', return_value=cache),
                   patch.object(service, '_try_pubchem_formula_search_rest', return_value={'cids': [1, 2]}),
                   patch.object(service, '_fetch_pubchem_synonym_map', return_value=repair),
                   patch.object(service, '_build_pubchem_compounds_from_cids'),
                   patch.object(service, '_save_pubchem_raw_data')]
        with patches[0], patches[1], patches[2] as synonyms, patches[3] as properties, patches[4] as save:
            result = searcher.get_compounds('C2H6O')
        return result, synonyms, properties, save

    def cache(self, status='partial'):
        return {'status': status, 'raw_results': [property_record(1, ['known'], True), property_record(2, complete=False)],
                'failed_batches': [failure()], 'batch_summary': {'missing_cids': [], 'missing_synonym_cids': [2]}}

    def test_resume_only_failed_synonyms_retains_properties(self):
        result, synonyms, properties, save = self.search_with_cache(self.cache(), {'synonym_map': {2: ['repaired']}, 'failed_batches': []})
        synonyms.assert_called_once()
        self.assertEqual(synonyms.call_args.args[0], [2])
        properties.assert_not_called()
        self.assertFalse(result['is_partial'])
        self.assertEqual(result['compounds'][1]['MonoisotopicMass'], 46.041864812)
        self.assertEqual(result['compounds'][1]['synonyms'], ['repaired'])
        self.assertEqual(save.call_args.kwargs['status'], 'success')

    def test_resume_to_empty_synonyms_is_complete(self):
        result, _, properties, _ = self.search_with_cache(self.cache(), {'synonym_map': {2: []}, 'failed_batches': []})
        self.assertFalse(result['is_partial'])
        self.assertTrue(result['compounds'][1]['synonyms_complete'])
        properties.assert_not_called()

    def test_failed_resume_preserves_partial_and_existing_properties(self):
        result, _, properties, save = self.search_with_cache(self.cache(), {'synonym_map': {}, 'failed_batches': [failure()]})
        self.assertTrue(result['is_partial'])
        self.assertEqual(len(result['compounds']), 2)
        self.assertEqual(result['batch_summary']['missing_synonym_cids'], [2])
        self.assertEqual(save.call_args.kwargs['status'], 'partial')
        properties.assert_not_called()

    def test_new_search_does_not_discard_enrichment_partial_flag(self):
        payload = {'compounds': [property_record(1, complete=False), property_record(2, complete=False)],
                   'failed_batches': [failure(1), failure(2)], 'is_partial': True,
                   'error': 'partial_synonym_enrichment'}
        def build(*args, **kwargs):
            kwargs['progress_callback'](payload)
            return payload
        with patch.object(service, '_load_latest_pubchem_raw_results', return_value=None), \
             patch.object(service, '_try_pubchem_formula_search_rest', return_value={'cids': [1, 2]}), \
             patch.object(service, '_build_pubchem_compounds_from_cids', side_effect=build), \
             patch.object(service, '_save_pubchem_raw_data') as save:
            result = service.FormulaSearchPubChem(max_retries=1).get_compounds('C2H6O')
        self.assertTrue(result['is_partial'])
        self.assertEqual(save.call_args.kwargs['status'], 'partial')

    def test_recovered_properties_clear_stale_failure_batches(self):
        cache = {'status': 'partial', 'raw_results': [property_record(1, ['known'], True)],
                 'failed_batches': [{'cids': [2], 'reason': 'property_timeout'}, failure(2)]}
        payload = {'compounds': [property_record(2, ['repaired'], True)], 'failed_batches': [], 'is_partial': False}
        with patch.object(service, '_load_latest_pubchem_raw_results', return_value=cache), \
             patch.object(service, '_try_pubchem_formula_search_rest', return_value={'cids': [1, 2]}), \
             patch.object(service, '_fetch_pubchem_synonym_map') as synonyms, \
             patch.object(service, '_build_pubchem_compounds_from_cids', return_value=payload) as properties:
            result = service.FormulaSearchPubChem(max_retries=1).get_compounds('C2H6O')
        synonyms.assert_not_called()
        self.assertEqual(properties.call_args.args[0], [2])
        self.assertFalse(result['is_partial'])
        self.assertEqual(result['failed_batches'], [])
        self.assertEqual(result['batch_summary']['failed_batches'], 0)

    def test_export_and_progress_include_enrichment_partial_status(self):
        payload = {'compounds': [property_record(1, complete=False)], 'is_partial': True,
                   'failed_batches': [failure(1)], 'batch_summary': {'missing_cids': [], 'missing_synonym_cids': [1]}}
        class Searcher:
            def get_compounds(self, formula):
                return payload
        progress = []
        with patch.object(service, '_load_latest_pubchem_raw_results', return_value=None), \
             patch.object(service, '_save_pubchem_raw_data'), \
             patch.object(service.ExporterFactory, 'get_exporter', return_value=DummyExporter()):
            result = service.SearchManager(Searcher(), 'json_formulaSearch_PubChem', strict_filter=False,
                progress_callback=progress.append).search_formula_list(['C2H6O'])
        self.assertIn('C2H6O', result['partial'])
        self.assertEqual(result['success']['C2H6O']['metadata']['status'], 'partial')
        self.assertEqual(progress[0]['status'], 'partial')

    def test_inconsistent_success_cache_is_retried(self):
        class Searcher:
            def __init__(self): self.calls = []
            def get_compounds(self, formula):
                self.calls.append(formula)
                return {'compounds': [property_record(1, complete=True)], 'is_partial': False}
        searcher = Searcher()
        with patch.object(service, '_load_latest_pubchem_raw_results', return_value=self.cache(status='success')), \
             patch.object(service, '_save_pubchem_raw_data'), \
             patch.object(service.ExporterFactory, 'get_exporter', return_value=DummyExporter()):
            service.SearchManager(searcher, 'json_formulaSearch_PubChem', strict_filter=False).search_formula_list(['C2H6O'])
        self.assertEqual(searcher.calls, ['C2H6O'])

    def test_raw_only_partial_cache_preserves_gaps_without_network(self):
        class Searcher:
            def get_compounds(self, formula): raise AssertionError('raw-only must be offline')
        with patch.object(service, '_load_latest_pubchem_raw_results', return_value=self.cache()), \
             patch.object(service.ExporterFactory, 'get_exporter', return_value=DummyExporter()):
            result = service.SearchManager(Searcher(), 'json_formulaSearch_PubChem', raw_only=True,
                strict_filter=False).search_formula_list(['C2H6O'])
        exported = result['success']['C2H6O']
        self.assertEqual(exported['metadata']['status'], 'partial')
        self.assertEqual(exported['metadata']['batch_summary']['missing_synonym_cids'], [2])
        self.assertFalse(exported['results'][1]['synonyms_complete'])

    def fallback(self, enriched, allow_partial=True):
        from types import SimpleNamespace
        source = [property_record(1)]
        fake = SimpleNamespace(get_compounds=lambda *_args: source)
        with patch.dict(sys.modules, {'pubchempy': fake}), \
             patch.object(service, '_load_latest_pubchem_raw_results', return_value=None), \
             patch.object(service, '_try_pubchem_formula_search_rest', return_value={'cids': None, 'error': 'timeout:synthetic'}), \
             patch.object(service, '_build_pubchem_compounds_from_cids', return_value=enriched):
            return service.FormulaSearchPubChem(max_retries=1, allow_partial_results=allow_partial).get_compounds('C2H6O')

    def test_pubchempy_failed_enrichment_preserves_partial_checkpoint(self):
        failures = [{'cids': [1], 'reason': 'property_timeout'}]
        result = self.fallback({'compounds': [], 'failed_batches': failures, 'error': 'property_timeout'})
        self.assertTrue(result['is_partial'])
        self.assertEqual(result['failed_batches'], failures)
        self.assertEqual(result['batch_summary']['missing_cids'], [1])
        self.assertEqual(result['batch_summary']['missing_synonym_cids'], [1])
        self.assertFalse(result['compounds'][0]['properties_complete'])
        self.assertEqual(result['compounds'][0]['MonoisotopicMass'], 46.041864812)

    def test_pubchempy_failed_enrichment_never_returns_partial_when_disabled(self):
        result = self.fallback({'compounds': [], 'failed_batches': [failure(1)], 'error': 'synthetic'}, False)
        self.assertIsNone(result)

    def test_pubchempy_partial_enrichment_never_returns_partial_when_disabled(self):
        result = self.fallback({'compounds': [property_record(1)], 'is_partial': True,
                                'failed_batches': [failure(1)], 'error': 'partial_synonyms'}, False)
        self.assertIsNone(result)

    def test_fallback_checkpoint_refetches_properties_and_replaces_old_record(self):
        old = property_record(1, ['old synonyms'], True)
        old['properties_complete'] = False
        old['MonoisotopicMass'] = 45.0
        new = property_record(1, ['old synonyms'], True)
        new['properties_complete'] = True
        with patch.object(service, '_load_latest_pubchem_raw_results', return_value={'status': 'partial', 'raw_results': [old], 'failed_batches': []}), \
             patch.object(service, '_try_pubchem_formula_search_rest', return_value={'cids': [1]}), \
             patch.object(service, '_build_pubchem_compounds_from_cids', return_value={'compounds': [new], 'failed_batches': [], 'is_partial': False}) as properties:
            result = service.FormulaSearchPubChem(max_retries=1).get_compounds('C2H6O')
        self.assertEqual(properties.call_args.args[0], [1])
        self.assertFalse(result['is_partial'])
        self.assertEqual(len(result['compounds']), 1)
        self.assertEqual(result['compounds'][0]['MonoisotopicMass'], 46.041864812)

    def test_property_retry_preserves_previously_retrieved_synonyms(self):
        old = property_record(1, ['retrieved earlier'], True)
        old['properties_complete'] = False
        def fetch(url, **_kwargs):
            if '/synonyms/' in url:
                raise AssertionError('completed synonyms must not be fetched again')
            return {'PropertyTable': {'Properties': [property_record(1)]}}
        with patch.object(service, '_fetch_pubchem_json', side_effect=fetch):
            result = service._build_pubchem_compounds_from_cids([1], source_compounds=[old], per_batch_retries=1)
        self.assertFalse(result['is_partial'])
        self.assertEqual(result['compounds'][0]['synonyms'], ['retrieved earlier'])
        self.assertTrue(result['compounds'][0]['properties_complete'])

    def test_missing_and_unrequested_response_cids_are_not_guessed_or_exported(self):
        def fetch(url, **_kwargs):
            if '/synonyms/' in url:
                return {'InformationList': {'Information': [{'CID': 1, 'Synonym': []}, {'CID': 2, 'Synonym': []}]}}
            missing_identity = property_record(1)
            missing_identity.pop('CID')
            return {'PropertyTable': {'Properties': [missing_identity, property_record(999), property_record(True), property_record(1.5), property_record(2)]}}
        with patch.object(service, '_fetch_pubchem_json', side_effect=fetch):
            result = service._build_pubchem_compounds_from_cids([1, 2], per_batch_retries=1)
        self.assertEqual([row['CID'] for row in result['compounds']], [2])
        self.assertTrue(result['is_partial'])
        self.assertEqual(result['batch_summary']['missing_cids'], [1])
        self.assertEqual(result['failed_batches'][0]['cids'], [1])

    def test_only_malformed_response_records_are_explicit_property_failure(self):
        def fetch(url, **_kwargs):
            if '/synonyms/' in url:
                return {'InformationList': {'Information': [{'CID': 1, 'Synonym': []}]}}
            return {'PropertyTable': {'Properties': [{'Title': 'unattributed mass', 'MonoisotopicMass': 46.0}]}}
        with patch.object(service, '_fetch_pubchem_json', side_effect=fetch):
            result = service._build_pubchem_compounds_from_cids([1], per_batch_retries=1)
        self.assertEqual(result['compounds'], [])
        self.assertEqual(result['error'], 'property_response_missing_cids')
        self.assertEqual(result['batch_summary']['missing_cids'], [1])

    def test_json_export_persists_completeness_and_precise_mass(self):
        with TemporaryDirectory() as temp:
            class Paths:
                def get_mass_finding_cache_path(self): return Path(temp)
                def get_formula_search_cache_path(self): return Path(temp)
            completeness = {'status': 'partial', 'batch_summary': {'missing_synonym_cids': [1]}, 'failed_batches': [failure(1)]}
            with patch('package.service.public.PathManager', Paths):
                data = JSONExporter_formulaSearch_PubChem().export_with_completeness(
                    ('C2H6O', [service._normalize_pubchem_compound(property_record(1, complete=False))]), completeness)
            disk = json.loads((Path(temp) / 'formula_search_results_C2H6O.json').read_text())
            self.assertEqual(disk['metadata']['status'], 'partial')
            self.assertEqual(disk['metadata']['batch_summary']['missing_synonym_cids'], [1])
            self.assertFalse(disk['results'][0]['synonyms_complete'])
            self.assertEqual(disk['results'][0]['monoisotopic_mass'], 46.041864812)
            self.assertEqual(disk, data)


if __name__ == '__main__':
    unittest.main()
