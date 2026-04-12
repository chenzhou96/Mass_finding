import json
import logging
import time
import datetime
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from ..config.path_config import PathManager
from ..service.public import ExporterFactory


class SearchStatus(Enum):
    SUCCESS = "success"
    NO_COMPOUNDS_FOUND = "no_compounds"
    ERROR = "error"


@dataclass
class FormulaSearchResult:
    formula: str
    status: SearchStatus
    compounds: Optional[List[Any]] = None
    error_message: Optional[str] = None

    def to_export_tuple(self):
        return (self.formula, self.compounds or [])


class FormulaSearch:
    def __init__(self, max_retries: int = 1, retry_delay: int = 10):
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def get_compounds(self, formula: str):
        raise NotImplementedError


def _normalize_formula(formula: str) -> str:
    if not isinstance(formula, str):
        return ''
    return formula.strip().replace(' ', '')


def _safe_formula_filename(formula: str) -> str:
    keep = []
    for ch in formula:
        if ch.isalnum() or ch in ('_', '-', '.'):
            keep.append(ch)
    return ''.join(keep) or 'unknown_formula'


def _compound_to_serializable(compound: Any) -> Dict[str, Any]:
    if isinstance(compound, dict):
        return compound

    fields = [
        'cid', 'iupac_name', 'isomeric_smiles', 'canonical_smiles',
        'inchi', 'inchikey', 'molecular_weight', 'monoisotopic_mass',
        'synonyms', 'record'
    ]
    data: Dict[str, Any] = {}
    for field in fields:
        try:
            value = getattr(compound, field)
            if value is not None:
                data[field] = value
        except Exception:
            continue

    if hasattr(compound, 'to_dict'):
        try:
            data['raw_dict'] = compound.to_dict()
        except Exception:
            pass

    return data


def _save_pubchem_raw_data(formula: str, compounds: List[Any]):
    try:
        path_manager = PathManager()
        raw_dir = path_manager.get_pubchem_raw_cache_path()
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        file_name = f"pubchem_raw_{_safe_formula_filename(formula)}_{timestamp}.json"
        output_path = raw_dir / file_name

        payload = {
            'metadata': {
                'formula': formula,
                'export_time': datetime.datetime.now().isoformat(),
                'source': 'pubchem_raw',
                'record_count': len(compounds),
            },
            'raw_results': [_compound_to_serializable(item) for item in compounds],
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        logging.info(f"PubChem 原始数据已保存: {output_path}")
    except Exception as ex:
        logging.warning(f"保存 PubChem 原始数据失败({formula}): {ex}")


def _fetch_pubchem_json(url: str, timeout: int = 30) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode('utf-8'))


def _parse_listkey_response(response: dict) -> Optional[List[int]]:
    if not isinstance(response, dict):
        return None
    if 'IdentifierList' in response and isinstance(response['IdentifierList'], dict):
        cid_list = response['IdentifierList'].get('CID')
        if isinstance(cid_list, list):
            return [int(cid) for cid in cid_list if isinstance(cid, int)]
    return None


def _build_pubchem_compounds_from_cids(cids: List[int], max_records: int = 100) -> List[Dict[str, Any]]:
    if not cids:
        return []
    cids = cids[:max_records]
    properties = [
        'CID',
        'IUPACName',
        'IsomericSMILES',
        'CanonicalSMILES',
        'InChI',
        'InChIKey',
        'MolecularWeight',
        'MonoisotopicMass'
    ]
    url = (
        'https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/' +
        ','.join(str(cid) for cid in cids) +
        '/property/' + ','.join(properties) +
        '/JSON'
    )
    try:
        data = _fetch_pubchem_json(url)
        properties_list = data.get('PropertyTable', {}).get('Properties', [])
        compounds = []
        for item in properties_list:
            compounds.append({
                'CID': item.get('CID'),
                'IUPACName': item.get('IUPACName'),
                'IsomericSMILES': item.get('IsomericSMILES'),
                'CanonicalSMILES': item.get('CanonicalSMILES'),
                'InChI': item.get('InChI'),
                'InChIKey': item.get('InChIKey'),
                'MolecularWeight': item.get('MolecularWeight'),
                'MonoisotopicMass': item.get('MonoisotopicMass'),
                'synonyms': []
            })
        return compounds
    except Exception as ex:
        logging.warning(f"PubChem REST 通过 CID 获取属性失败: {ex}")
        return []


def _extract_cids_from_compounds(compounds: List[Any]) -> List[int]:
    cids: List[int] = []
    for item in compounds:
        raw_cid = None
        if isinstance(item, dict):
            raw_cid = item.get('CID', item.get('cid'))
        else:
            raw_cid = getattr(item, 'cid', None)

        try:
            cid = int(raw_cid)
        except (TypeError, ValueError):
            continue

        if cid not in cids:
            cids.append(cid)
    return cids


def _try_pubchem_formula_search_rest(formula: str, fast: bool = False) -> Optional[List[int]]:
    encoded = urllib.parse.quote(formula)
    endpoint = 'fastformula' if fast else 'formula'
    url = f'https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/{endpoint}/{encoded}/cids/JSON'
    try:
        response = _fetch_pubchem_json(url)
        cids = _parse_listkey_response(response)
        if cids:
            return cids
        # If the service returns Waiting, treat as not ready and fallback gracefully
        if 'Waiting' in response:
            logging.warning(f"PubChem {endpoint} 查询进入异步队列: {formula}")
            return None
        return None
    except urllib.error.HTTPError as ex:
        if ex.code == 404:
            return None
        logging.warning(f"PubChem REST {endpoint} 查询失败 {formula}: {ex}")
        return None
    except Exception as ex:
        logging.warning(f"PubChem REST {endpoint} 查询异常 {formula}: {ex}")
        return None


class FormulaSearchPubChem(FormulaSearch):
    def get_compounds(self, formula: str):
        formula = _normalize_formula(formula)
        if not formula:
            logging.warning("PubChem 查询时遇到空化学式。")
            return None

        try:
            import pubchempy as pcp
        except ModuleNotFoundError as ex:
            raise ImportError(
                "PubChem 查询需要安装 pubchempy 库。请运行：pip install pubchempy"
            ) from ex

        for attempt in range(self.max_retries):
            try:
                compounds = pcp.get_compounds(formula, 'formula')
                if compounds:
                    cids = _extract_cids_from_compounds(compounds)
                    enriched_compounds = _build_pubchem_compounds_from_cids(cids)
                    if enriched_compounds:
                        return enriched_compounds
                    return compounds
                logging.warning(f"{formula} 未匹配到任何化合物")
                return None
            except Exception as ex:
                message = str(ex)
                logging.warning(f"PubChem 请求失败({attempt + 1}/{self.max_retries}) for {formula}: {message}")
                if attempt + 1 < self.max_retries:
                    time.sleep(self.retry_delay)
                if 'PUGREST.BadRequest' in message or 'BadRequest' in message:
                    cids = _try_pubchem_formula_search_rest(formula, fast=True)
                    if cids:
                        compounds = _build_pubchem_compounds_from_cids(cids)
                        if compounds:
                            return compounds
                    cids = _try_pubchem_formula_search_rest(formula, fast=False)
                    if cids:
                        return _build_pubchem_compounds_from_cids(cids)

        logging.error(f"PubChem 查询最终失败: {formula}")
        return None


class SearchManager:
    def __init__(self, searcher: FormulaSearch, exporter_name: str):
        self.searcher = searcher
        self.exporter_name = exporter_name

    def search_formula_list(self, formula_list: List[str]) -> Dict[str, Any]:
        if not formula_list:
            logging.warning("未识别到任何化学式")
            return {"success": {}, "failed": []}

        results = {"success": {}, "failed": []}
        exporter = ExporterFactory.get_exporter(self.exporter_name)
        if exporter is None:
            raise ValueError(f"找不到导出器: {self.exporter_name}")

        for formula in formula_list:
            try:
                compounds = self.searcher.get_compounds(formula)
                if compounds:
                    _save_pubchem_raw_data(formula, compounds)
                    export_data = exporter.export((formula, compounds))
                    results["success"][formula] = export_data
                else:
                    results["failed"].append(formula)
            except Exception as ex:
                logging.error(f"处理化学式 {formula} 失败: {ex}", exc_info=True)
                results["failed"].append(formula)

        return results


def start_search(formula_list: List[str], web_name: str) -> Dict[str, Any]:
    web_name_lower = web_name.lower()
    if 'pubchem' in web_name_lower:
        searcher = FormulaSearchPubChem()
        exporter_name = 'json_formulaSearch_PubChem'
    else:
        raise ValueError(f"未知的 web_name: {web_name}")

    manager = SearchManager(searcher, exporter_name)
    return manager.search_formula_list(formula_list)
