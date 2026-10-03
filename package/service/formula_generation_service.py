"""Shared monoisotopic candidate engine; no structural identification is implied."""
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any

from ..config.path_config import PathManager
from .public import ExporterFactory, ReadChemElementConfig

ENGINE_VERSION = '2.0.0'
MAX_NODES = 2_000_000
MAX_RESULTS = 25_000


class SearchLimitError(ValueError):
    pass


class SearchCancelled(ValueError):
    pass


@dataclass
class FormulaCandidate:
    formula: Dict[str, int] = field(default_factory=dict)
    atomic_weights: Dict[str, float] = field(default_factory=dict)
    element_categories: Dict[str, List[str]] = field(default_factory=dict)
    dbr: float = 0.0
    predicted_mw: float = 0.0

    def validate_valency(self) -> bool:
        v1 = sum(self.formula.get(e, 0) for e in self.element_categories['valency_1'])
        v3 = sum(self.formula.get(e, 0) for e in self.element_categories['valency_3'])
        v4 = sum(self.formula.get(e, 0) for e in self.element_categories['valency_4'])
        self.dbr = (2 * v4 + 2 + v3 - v1) / 2
        self.predicted_mw = self.calculate_molecular_weight()
        return self.dbr >= 0 and self.dbr.is_integer()

    def calculate_molecular_weight(self) -> float:
        return math.fsum(self.atomic_weights[e] * n for e, n in self.formula.items())

    def to_dict(self):
        return {'formula': {e: n for e, n in self.formula.items() if n},
                'dbr': self.dbr, 'predicted_mw': self.predicted_mw}

    def to_formula_string(self):
        keys = ['C', 'H'] + sorted(e for e in self.formula if e not in ('C', 'H')) if self.formula.get('C') else sorted(self.formula)
        return ''.join(e + (str(self.formula[e]) if self.formula[e] > 1 else '')
                       for e in keys if self.formula.get(e, 0) > 0)


def normalize_elements(elements, atomic_weights):
    for e, count in elements.items():
        if e not in atomic_weights or isinstance(count, bool) or not isinstance(count, int) or count < -1:
            raise ValueError('元素上限必须是支持的元素及非负整数或 -1（不限）')
    items = [(e, atomic_weights[e], math.inf if n == -1 else n) for e, n in elements.items() if e != 'H' and n != 0]
    items.sort(key=lambda item: item[1], reverse=True)
    if elements.get('H', 0) != 0:
        items.append(('H', atomic_weights['H'], math.inf if elements['H'] == -1 else elements['H']))
    return items


def backtrack_search(target_mw, tolerance_mw, elements_order, atomic_weights, element_categories,
                     dbe_filter=True, cancel_event=None, max_nodes=MAX_NODES, max_results=MAX_RESULTS):
    if not math.isfinite(target_mw) or target_mw <= 0 or not math.isfinite(tolerance_mw) or tolerance_mw < 0:
        raise ValueError('质量与误差必须是有限有效数值')
    low, high = target_mw - tolerance_mw, target_mw + tolerance_mw
    # Several summation orders meet here. An ulp-scale guard retains mathematical
    # closed endpoints without widening an instrument tolerance by a fixed Da.
    guard = 16 * math.ulp(max(abs(low), abs(high), 1.0))
    h_weight = atomic_weights['H']
    h_max = next((n for e, _, n in elements_order if e == 'H'), 0)
    non_h = [(e, w, n) for e, w, n in elements_order if e != 'H']
    results, nodes = [], 0

    def dfs(index, current_mw, current):
        nonlocal nodes
        nodes += 1
        if cancel_event is not None and cancel_event.is_set():
            raise SearchCancelled('分析已取消')
        if nodes > max_nodes:
            raise SearchLimitError('搜索空间超限；请收紧元素上限或误差窗口。未返回不完整候选。')
        if index == len(non_h):
            min_h = max(0, math.ceil((low - current_mw - guard) / h_weight))
            max_h = min(math.floor((high - current_mw + guard) / h_weight), h_max)
            for count in range(min_h, int(max_h) + 1):
                candidate = FormulaCandidate({**current, 'H': count}, atomic_weights, element_categories)
                passes = candidate.validate_valency()
                if not any(candidate.formula.values()):
                    continue
                if (passes or not dbe_filter) and low - guard <= candidate.predicted_mw <= high + guard:
                    results.append(candidate)
                    if len(results) > max_results:
                        raise SearchLimitError('候选数量超限；请收紧元素上限或误差窗口。未返回截断结果。')
            return
        e, weight, limit = non_h[index]
        maximum = min(math.floor((high - current_mw + guard) / weight), limit)
        for count in range(int(maximum), -1, -1):
            dfs(index + 1, current_mw + count * weight, {**current, e: count})

    dfs(0, 0.0, {})
    return results


def validate_input(data, config=None):
    if not isinstance(data, dict):
        raise ValueError('输入须为参数对象')
    config = config or ReadChemElementConfig(PathManager().chem_element_config_path).config
    normalized = dict(data)
    for key in ('m2z', 'error_pct', 'error_da'):
        value = data.get(key, 0.0 if key == 'error_da' else None)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f'{key} 必须是有限数值')
        normalized[key] = float(value)
    if not 0 < normalized['m2z'] <= 3000:
        raise ValueError('m/z 范围为 (0, 3000] Th')
    if not 0 <= normalized['error_pct'] <= 1 or not 0 <= normalized['error_da'] <= 10:
        raise ValueError('误差须非负：百分比最多 1%，绝对窗口最多 10 Th')
    charge = data.get('charge')
    if isinstance(charge, bool) or not isinstance(charge, int) or not 1 <= charge <= 10:
        raise ValueError('电荷绝对值须为 1–10 的整数')
    mode, adducts = data.get('ms_mode'), data.get('adduct_model')
    if mode not in config['adducts'] or not isinstance(adducts, list) or not adducts:
        raise ValueError('请选择有效离子模式与至少一个加合类型')
    if any(not isinstance(a, str) or a not in config['adducts'][mode] for a in adducts):
        raise ValueError('加合类型与离子模式不匹配')
    if charge > 1 and (not mode.startswith('ESI') or any(a not in ('H+', 'H-') for a in adducts)):
        raise ValueError('多电荷仅支持 [M+zH]z+ 或 [M−zH]z−；其余模型请选择单电荷')
    elements = data.get('elements')
    if not isinstance(elements, dict) or not elements:
        raise ValueError('请选择至少一种元素')
    normalize_elements(elements, config['atomic_weights'])
    if not any(n != 0 for n in elements.values()):
        raise ValueError('元素上限不能全为零')
    if any(n > 1000 for n in elements.values()):
        raise ValueError('元素上限最多 1000；-1 表示不限（受质量预算约束）')
    if not isinstance(data.get('dbe_filter', True), bool):
        raise ValueError('DBE筛选须为布尔值')
    normalized['elements'] = dict(elements)
    normalized['adduct_model'] = list(dict.fromkeys(adducts))
    normalized['dbe_filter'] = data.get('dbe_filter', True)
    return normalized


class FormulaGenerator:
    def __init__(self, config_path: Optional[Path] = None):
        self.config = ReadChemElementConfig(config_path or PathManager().chem_element_config_path).config
        self.atomic_weights = self.config['atomic_weights']
        self.element_categories = self.config['element_categories']
        self.ion_weights = self.config['ion_weights']
        self.adducts = self.config['adducts']

    def build_formula_results(self, m2z, error_pct, error_da, charge, ms_mode, selected_adducts, elements,
                              dbe_filter=True, cancel_event=None):
        params = validate_input(dict(m2z=m2z, error_pct=error_pct, error_da=error_da, charge=charge,
                                     ms_mode=ms_mode, adduct_model=selected_adducts, elements=elements,
                                     dbe_filter=dbe_filter), self.config)
        order = normalize_elements(elements, self.atomic_weights)
        tolerance = max(m2z * error_pct / 100, error_da) * charge
        results = {}
        for adduct in params['adduct_model']:
            shift = self.ion_weights[self.adducts[ms_mode][adduct]]
            target = (m2z - shift) * charge
            if target <= 0 or target > 5000:
                raise ValueError('换算中性质量须为 (0, 5000] Da；请核对模式、电荷和 m/z')
            candidates = backtrack_search(target, tolerance, order, self.atomic_weights, self.element_categories,
                                          dbe_filter, cancel_event)
            rows = []
            for candidate in candidates:
                predicted = candidate.predicted_mw / charge + shift
                rows.append({**candidate.to_dict(), 'adduct_type': adduct,
                             'ion_model': ion_model(adduct, charge, ms_mode),
                             'calculated_properties': {'dbr': candidate.dbr, 'predicted_mz': predicted,
                                 'molecular_weight': candidate.predicted_mw,
                                 'error_th': predicted - m2z, 'error_ppm': (predicted - m2z) / m2z * 1e6}})
            rows.sort(key=lambda r: (abs(r['calculated_properties']['error_th']), str(r['formula'])))
            results[adduct] = rows
            if sum(len(group) for group in results.values()) > MAX_RESULTS:
                raise SearchLimitError('所有加合模型合计候选超限；请收紧约束。未返回截断结果。')
        return results


def ion_model(adduct, charge, mode):
    if adduct in ('e+', 'e-'):
        return '[M]+' if mode == 'EI+' else '[M]−'
    if adduct == 'H-':
        return '[M−H]−' if charge == 1 else f'[M−{charge}H]{charge}−'
    label = adduct[:-1]
    suffix = '+' if mode.endswith('+') else '−'
    return f'[M+{label}]{suffix}' if charge == 1 else f'[M+{charge}{label}]{charge}{suffix}'


def analyze(input_data, cancel_event=None):
    start = time.monotonic()
    generator = FormulaGenerator()
    params = validate_input(input_data, generator.config)
    groups = generator.build_formula_results(params['m2z'], params['error_pct'], params['error_da'], params['charge'],
                                            params['ms_mode'], params['adduct_model'], params['elements'],
                                            params['dbe_filter'], cancel_event)
    rows = [row for group in groups.values() for row in group]
    rows.sort(key=lambda r: abs(r['calculated_properties']['error_th']))
    return {'status': 'success', 'input_params': params, 'results': rows,
            'metadata': {'engine_version': ENGINE_VERSION, 'mass_table': generator.config.get('mass_table'),
                         'mass_basis': 'monoisotopic', 'mz_unit': 'Th', 'neutral_mass_unit': 'Da',
                         'tolerance_rule': 'max(percent, absolute); inclusive endpoints',
                         'tolerance_th': max(params['m2z'] * params['error_pct'] / 100, params['error_da']),
                         'elapsed_seconds': time.monotonic() - start, 'result_count': len(rows),
                         'dbe_filter': params['dbe_filter'], 'identification': 'candidate_only'}}


def start_analysis(input_data: Dict[str, Any], cancel_event=None):
    """Legacy desktop adapter; explicit errors remain distinct from no matches."""
    try:
        result = analyze(input_data, cancel_event)
        if cancel_event is not None and cancel_event.is_set():
            raise SearchCancelled('分析已取消')
        if result['results']:
            # Keep the existing cache schema and preserve all audit fields.
            result['formulas'] = {}
            for row in result['results']:
                result['formulas'].setdefault(row['adduct_type'], []).append(row)
            ExporterFactory.get_exporter('json_formulaGeneration').export(result)
            result.pop('formulas')
        return result
    except Exception as exc:
        return {'status': 'error', 'error': str(exc), 'input_params': input_data, 'results': []}
