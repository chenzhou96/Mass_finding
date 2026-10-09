"""Independent reference masses and exhaustive truth, synthetic data only."""
import csv
import io
import itertools
import json
import math
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from package.service.formula_generation_service import (FormulaGenerator, analyze, validate_input,
    normalize_elements, backtrack_search, SearchCancelled, SearchLimitError, start_analysis)
from package.service.public import CSVExporter_formulaGeneration, JSONExporter_formulaGeneration
from package.utils.data_validator import DataValidator

REF = {'C':12.0,'H':1.00782503223,'N':14.00307400443,'O':15.99491461957}
PROTON = 1.007276466621
ELECTRON = 0.000548579909065
ETHANOL = 46.04186481295


def params(**changes):
    data = dict(m2z=ETHANOL+PROTON,error_pct=0,error_da=1e-8,charge=1,
                ms_mode='ESI+',adduct_model=['H+'],elements={'C':2,'H':6,'O':1},dbe_filter=True)
    data.update(changes)
    return data


class ScientificEngineTests(unittest.TestCase):
    def test_known_ethanol_monoisotopic_mass_and_proton(self):
        result = analyze(params())
        row = result['results'][0]
        self.assertEqual(row['formula'], {'C':2,'H':6,'O':1})
        self.assertAlmostEqual(row['calculated_properties']['molecular_weight'], ETHANOL, places=10)
        self.assertAlmostEqual(row['calculated_properties']['predicted_mz'], ETHANOL+PROTON, places=10)
        self.assertEqual(result['metadata']['mass_basis'], 'monoisotopic')

    def test_all_single_charge_adducts_with_independent_shifts(self):
        shifts = {'ESI+':{'H+':PROTON,'Na+':22.9897692820-ELECTRON,'K+':38.9637064864-ELECTRON,
                 'NH4+':REF['N']+3*REF['H']+PROTON,'H3O+':REF['O']+2*REF['H']+PROTON},
                  'ESI-':{'H-':-PROTON,'Cl-':34.968852682+ELECTRON,
                           'HCOO-':REF['H']+12+2*REF['O']+ELECTRON,
                           'CH3COO-':3*REF['H']+24+2*REF['O']+ELECTRON},
                  'EI+':{'e+':-ELECTRON},'EI-':{'e-':ELECTRON}}
        for mode, adducts in shifts.items():
            for adduct, shift in adducts.items():
                with self.subTest(mode=mode,adduct=adduct):
                    rows=analyze(params(m2z=ETHANOL+shift,ms_mode=mode,adduct_model=[adduct]))['results']
                    self.assertEqual(len(rows),1)
                    self.assertAlmostEqual(rows[0]['calculated_properties']['molecular_weight'],ETHANOL,places=10)

    def test_multiple_protons_and_deprotonation_charge_scaling(self):
        for charge in (2,3,10):
            for mode,a,shift in [('ESI+','H+',PROTON),('ESI-','H-',-PROTON)]:
                with self.subTest(charge=charge,mode=mode):
                    r=analyze(params(m2z=ETHANOL/charge+shift,charge=charge,ms_mode=mode,adduct_model=[a]))['results'][0]
                    self.assertEqual(r['formula'],{'C':2,'H':6,'O':1})
                    self.assertIn(str(charge),r['ion_model'])

    def test_unsupported_multicharge_model_is_error(self):
        for mode,a in [('ESI+','Na+'),('ESI-','Cl-'),('EI+','e+')]:
            with self.subTest(mode=mode):
                with self.assertRaises(ValueError):analyze(params(charge=2,ms_mode=mode,adduct_model=[a]))

    def test_percent_absolute_max_and_mass_window_scaling(self):
        r=analyze(params(error_pct=.001,error_da=.0001,charge=2,m2z=ETHANOL/2+PROTON))
        self.assertAlmostEqual(r['metadata']['tolerance_th'], r['input_params']['m2z']*.001/100)
        self.assertEqual(len(r['results']),1)

    def test_zero_tolerance_exact_formula_is_supported(self):
        self.assertEqual(len(analyze(params(error_da=0))['results']),1)

    def test_no_hydrogen_unless_selected_and_zero_really_excludes(self):
        for elements in ({'C':2,'O':1},{'C':2,'O':1,'H':0}):
            self.assertEqual(analyze(params(elements=elements))['results'],[])
        self.assertEqual(len(analyze(params(elements={'C':2,'O':1,'H':-1}))['results']),1)

    def test_unknown_or_illegal_element_counts_rejected(self):
        for elements in ({'Xx':1},{'C':-2},{'C':2.1},{'H':True},{'C':1001},{'C':0}):
            with self.subTest(elements=elements):
                with self.assertRaises(ValueError):validate_input(params(elements=elements))

    def test_nonfinite_boolean_and_invalid_inputs_rejected(self):
        bad = [('m2z',math.nan),('m2z',math.inf),('m2z',0),('m2z',3001),('m2z',True),
               ('error_pct',math.nan),('error_pct',-.1),('error_da',math.inf),('error_da',-1),
               ('charge',True),('charge',1.5),('charge',0),('charge',11),('ms_mode','other'),
               ('adduct_model',['Na+','unknown']),('adduct_model',[]),('dbe_filter','true')]
        for key,value in bad:
            with self.subTest(key=key,value=value):
                with self.assertRaises(ValueError):analyze(params(**{key:value}))

    def test_negative_and_out_of_scope_neutral_mass_errors(self):
        with self.assertRaises(ValueError):analyze(params(m2z=.1))
        with self.assertRaises(ValueError):analyze(params(m2z=1000,charge=10))

    def test_dbe_is_optional_heuristic_for_sulfur_hexafluoride(self):
        mass=31.9720711744+6*18.99840316273
        p=params(m2z=mass+PROTON,elements={'S':1,'F':6},dbe_filter=True)
        self.assertEqual(analyze(p)['results'],[])
        p['dbe_filter']=False
        row=analyze(p)['results'][0]
        self.assertEqual(row['formula'],{'S':1,'F':6})
        self.assertLess(row['dbr'],0)

    def test_exhaustive_independent_chno_centers_and_closed_endpoints(self):
        g=FormulaGenerator();order=normalize_elements({'C':5,'H':12,'N':3,'O':3},g.atomic_weights)
        checked=0
        for c,h,n,o in itertools.product(range(6),range(13),range(4),range(4)):
            dbe=(2*c+2+n-h)/2
            if not any((c,h,n,o)) or dbe<0 or not dbe.is_integer():continue
            expected={e:v for e,v in zip(('C','H','N','O'),(c,h,n,o)) if v}
            mass=math.fsum([c*REF['C'],h*REF['H'],n*REF['N'],o*REF['O']])
            for offset in (0,-.01,.01):
                found=backtrack_search(mass+offset,.01,order,g.atomic_weights,g.element_categories)
                self.assertIn(expected,[r.to_dict()['formula'] for r in found])
                checked+=1
        self.assertEqual(checked,1377)

    def test_bounded_truth_set_no_missing_or_extra_candidates(self):
        g=FormulaGenerator();elements={'C':3,'H':8,'N':2,'O':2};order=normalize_elements(elements,g.atomic_weights)
        for target in (18.01056468403,30,46,60,80,100):
            expected=set()
            for c,h,n,o in itertools.product(range(4),range(9),range(3),range(3)):
                mass=math.fsum([c*REF['C'],h*REF['H'],n*REF['N'],o*REF['O']]);dbe=(2*c+2+n-h)/2
                if any((c,h,n,o)) and dbe>=0 and dbe.is_integer() and abs(mass-target)<=.05:
                    expected.add((c,h,n,o))
            found=backtrack_search(target,.05,order,g.atomic_weights,g.element_categories)
            self.assertEqual({tuple(r.formula.get(e,0) for e in ('C','H','N','O')) for r in found},expected)

    def test_limits_and_cancellation_do_not_return_truncated_results(self):
        g=FormulaGenerator();order=normalize_elements({'C':10,'H':50,'O':10},g.atomic_weights)
        event=threading.Event();event.set()
        with self.assertRaises(SearchCancelled):backtrack_search(100,1,order,g.atomic_weights,g.element_categories,cancel_event=event)
        with self.assertRaises(SearchLimitError):backtrack_search(100,1,order,g.atomic_weights,g.element_categories,max_nodes=1)
        with self.assertRaises(SearchLimitError):backtrack_search(100,100,order,g.atomic_weights,g.element_categories,max_results=1)

    def test_errors_are_distinct_from_no_candidates_in_desktop_adapter(self):
        r=start_analysis(params(m2z=math.nan))
        self.assertEqual(r['status'],'error');self.assertTrue(r['error'])
        r=start_analysis(params(elements={'C':1,'H':0}))
        self.assertEqual(r['status'],'success');self.assertEqual(r['results'],[])

    def test_legacy_string_validator_uses_same_rules(self):
        p=params(elements={'C':'2','H':'不限','O':'1'})
        self.assertTrue(DataValidator().validate(p))
        for change in ({'m2z':math.nan},{'charge':True},{'elements':{'C':'-2'}}):
            self.assertFalse(DataValidator().validate({**p,**change}))

    def test_exports_preserve_input_mass_precision_metadata_and_ion_model(self):
        r=analyze(params());r['formulas']={'H+':r['results']}
        with TemporaryDirectory() as folder,patch('package.service.public.PathManager') as manager:
            manager.return_value.get_formula_generation_cache_path.return_value=Path(folder)
            out=JSONExporter_formulaGeneration().export(r)
            CSVExporter_formulaGeneration().export(r)
            self.assertEqual(out['input_params'],r['input_params'])
            self.assertEqual(out['metadata']['engine_version'],'2.0.0')
            self.assertEqual(out['results'][0]['ion_model'],'[M+H]+')
            self.assertEqual(out['results'][0]['calculated_properties'],r['results'][0]['calculated_properties'])
            raw=next(Path(folder).glob('*.csv')).read_text()
            self.assertIn(repr(ETHANOL),raw)
            self.assertIn(repr(ETHANOL+PROTON),raw)


if __name__ == '__main__':unittest.main()
