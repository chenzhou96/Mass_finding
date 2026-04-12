import concurrent.futures
import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from ..config.path_config import PathManager
from ..service.public import ExporterFactory, ReadChemElementConfig


@dataclass
class FormulaCandidate:
    formula: Dict[str, int] = field(default_factory=dict)
    atomic_weights: Dict[str, float] = field(default_factory=dict)
    element_categories: Dict[str, List[str]] = field(default_factory=dict)
    dbr: float = 0.0
    predicted_mw: float = 0.0

    def validate_valency(self) -> bool:
        valency_1 = sum(self.formula.get(e, 0) for e in self.element_categories['valency_1'])
        valency_3 = sum(self.formula.get(e, 0) for e in self.element_categories['valency_3'])
        valency_4 = sum(self.formula.get(e, 0) for e in self.element_categories['valency_4'])

        self.dbr = (2 * valency_4 + 2 + valency_3 - valency_1) / 2
        if self.dbr < 0:
            return False

        self.predicted_mw = self.calculate_molecular_weight()
        return ((self.dbr * 2) % 2) == 0

    def calculate_molecular_weight(self) -> float:
        return sum(self.atomic_weights.get(element, 0.0) * count for element, count in self.formula.items())

    def to_dict(self) -> Dict[str, object]:
        return {
            'formula': {k: v for k, v in self.formula.items() if v != 0},
            'dbr': self.dbr,
            'predicted_mw': self.predicted_mw,
        }

    def to_formula_string(self) -> str:
        parts = []
        ordered = ['C', 'H', 'N', 'O', 'S', 'P', 'Si', 'F', 'Cl', 'Br', 'I', 'B', 'Se']
        for atom in ordered:
            count = self.formula.get(atom, 0)
            if count == 1:
                parts.append(atom)
            elif count > 1:
                parts.append(f'{atom}{count}')
        return ''.join(parts)


def normalize_elements(elements: Dict[str, int], atomic_weights: Dict[str, float]) -> List[tuple]:
    processed = {}
    for element, count in elements.items():
        if element not in atomic_weights:
            logging.warning(f'元素 {element} 不在原子量表中，已忽略。')
            continue
        if count == 0:
            continue
        processed[element] = float('inf') if count == -1 else count

    items = [(elem, atomic_weights[elem], max_count) for elem, max_count in processed.items() if elem != 'H']
    items.sort(key=lambda x: x[1], reverse=True)
    if 'H' in processed:
        items.append(('H', atomic_weights['H'], processed['H']))
    return items


def backtrack_search(target_mw: float, tolerance: float, elements_order: List[tuple], atomic_weights: Dict[str, float], element_categories: Dict[str, List[str]]) -> List[FormulaCandidate]:
    mw_min = target_mw - target_mw * tolerance
    mw_max = target_mw + target_mw * tolerance
    h_weight = atomic_weights.get('H', 1.0)
    results: List[FormulaCandidate] = []
    h_max = next((count for elem, _, count in elements_order if elem == 'H'), float('inf'))

    def dfs(index: int, remaining_mw: float, current: Dict[str, int]):
        if index >= len(elements_order):
            h_count = round(remaining_mw / h_weight)
            if h_count < 0 or h_count > h_max:
                return

            candidate = FormulaCandidate(
                formula={**current, 'H': h_count},
                atomic_weights=atomic_weights,
                element_categories=element_categories
            )
            if candidate.validate_valency() and mw_min <= candidate.predicted_mw <= mw_max:
                results.append(candidate)
            return

        elem, weight, max_count = elements_order[index]
        max_possible = int(min(remaining_mw / weight, max_count)) if weight > 0 else 0
        for count in range(max_possible, -1, -1):
            next_remaining = remaining_mw - count * weight
            if next_remaining < 0:
                continue
            dfs(index + 1, next_remaining, {**current, elem: count})

    dfs(0, target_mw, {})
    return results


class FormulaGenerator:
    def __init__(self, config_path: Optional[str] = None):
        config_path = config_path or str(PathManager().chem_element_config_path)
        self.config = ReadChemElementConfig(config_path).config
        self.atomic_weights = self.config['atomic_weights']
        self.element_categories = self.config['element_categories']
        self.ion_weights = self.config['ion_weights']
        self.adducts = self.config['adducts']

    def build_formula_results(self, m2z: float, error_pct: float, charge: int, ms_mode: str, selected_adducts: List[str], elements: Dict[str, int]) -> Dict[str, List[dict]]:
        order = normalize_elements(elements, self.atomic_weights)
        mw_tolerance = error_pct / 100
        results: Dict[str, List[dict]] = {}

        tasks = []
        for adduct, ion_key in self.adducts.get(ms_mode, {}).items():
            if adduct not in selected_adducts:
                continue
            ion_weight = self.ion_weights.get(ion_key, 0.0)
            base_mw = (m2z - ion_weight) * charge
            if base_mw <= 0:
                continue
            tasks.append((adduct, base_mw, ion_weight))

        if not tasks:
            return results

        max_workers = max(1, os.cpu_count() // 2)
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(backtrack_search, base_mw, mw_tolerance, order, self.atomic_weights, self.element_categories): (adduct, ion_weight)
                for adduct, base_mw, ion_weight in tasks
            }
            for future in concurrent.futures.as_completed(futures):
                adduct, ion_weight = futures[future]
                try:
                    candidates = future.result()
                    if not candidates:
                        continue
                    results[adduct] = [
                        {
                            **candidate.to_dict(),
                            'adduct_type': adduct,
                            'calculated_properties': {
                                'dbr': candidate.dbr,
                                'predicted_mz': (candidate.predicted_mw + charge * ion_weight) / charge,
                                'molecular_weight': candidate.predicted_mw,
                            }
                        }
                        for candidate in candidates
                    ]
                except Exception as ex:
                    logging.error(f'adduct {adduct} 计算失败: {ex}', exc_info=True)
        return results


def start_analysis(input_data: Dict[str, Any]) -> Dict[str, Any]:
    start_time = time.time()
    try:
        generator = FormulaGenerator()
        ms_mode = input_data['ms_mode']
        selected_adducts = input_data.get('adduct_model', [])
        m2z = float(input_data['m2z'])
        error_pct = float(input_data['error_pct'])
        charge = int(input_data['charge'])
        elements = input_data['elements']

        if not selected_adducts:
            logging.warning('未选择任何离子类型。')
            return {
                'input_params': {
                    **input_data,
                    'adduct_model': []
                },
                'results': []
            }

        result = {
            'input_params': {
                **input_data,
                'adduct_model': selected_adducts
            },
            'formulas': generator.build_formula_results(m2z, error_pct, charge, ms_mode, selected_adducts, elements)
        }

        if result['formulas']:
            csv_exporter = ExporterFactory.get_exporter('csv_formulaGeneration')
            json_exporter = ExporterFactory.get_exporter('json_formulaGeneration')
            if csv_exporter is None or json_exporter is None:
                raise ValueError('未找到生成结果导出器')
            csv_exporter.export(result)
            data_to_save = json_exporter.export(result)
            logging.info(f'分析完成，结果已保存。耗时 {time.time() - start_time:.2f} 秒')
            return data_to_save

        logging.warning('未找到符合条件的分子式')
        return {
            'input_params': result['input_params'],
            'results': []
        }
    except Exception as ex:
        logging.exception(f'分析失败: {ex}')
        return {
            'input_params': input_data,
            'results': []
        }
