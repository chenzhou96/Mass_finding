import json
import logging
import re
from typing import Dict, List

from ..config.path_config import PathManager


_FORMULA_SEARCH_CACHE_PATTERN = re.compile(r'^formula_search_results_(?P<formula>.+)\.json$')
_PUBCHEM_RAW_CACHE_PATTERN = re.compile(r'^pubchem_raw_(?P<formula>.+)_\d{8}_\d{6}\.json$')


def _write_formula_list(file_path, formula_list: List[str]) -> None:
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(formula_list, f, ensure_ascii=False, indent=2)


def _scan_existing_formulas(path_manager: PathManager) -> List[str]:
    cache_dir = path_manager.get_formula_search_cache_path()
    formulas = set()
    for file_path in cache_dir.glob('formula_search_results_*.json'):
        match = _FORMULA_SEARCH_CACHE_PATTERN.match(file_path.name)
        if not match:
            continue
        formula = match.group('formula').strip()
        if formula:
            formulas.add(formula)
    return sorted(formulas)


def _scan_raw_data_formulas(path_manager: PathManager) -> List[str]:
    cache_dir = path_manager.get_pubchem_raw_cache_path()
    formulas = set()
    for file_path in cache_dir.glob('pubchem_raw_*.json'):
        match = _PUBCHEM_RAW_CACHE_PATTERN.match(file_path.name)
        if not match:
            continue
        formula = match.group('formula').strip()
        if formula:
            formulas.add(formula)
    return sorted(formulas)


def sync_formula_index_cache(path_manager: PathManager = None) -> Dict[str, List[str]]:
    manager = path_manager or PathManager()
    init_dir = manager.get_initialization_cache_path()
    existing_file = manager.create_cache_file(init_dir, manager.existing_formula_filename)
    raw_file = manager.create_cache_file(init_dir, manager.raw_data_formula_filename)

    existing_formulas = _scan_existing_formulas(manager)
    raw_data_formulas = _scan_raw_data_formulas(manager)

    _write_formula_list(existing_file, existing_formulas)
    _write_formula_list(raw_file, raw_data_formulas)

    logging.info(
        "启动索引同步完成：existing=%d, raw_data=%d",
        len(existing_formulas),
        len(raw_data_formulas),
    )

    return {
        'existing_formulas': existing_formulas,
        'raw_data_formulas': raw_data_formulas,
    }
