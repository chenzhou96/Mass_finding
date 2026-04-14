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


SCORE_WEIGHT_BY_MODE: Dict[str, Dict[str, float]] = {
    'positive': {
        'ionization_likelihood': 0.55,
        'record_quality': 0.30,
        'prevalence': 0.15,
    },
    'negative': {
        'ionization_likelihood': 0.55,
        'record_quality': 0.30,
        'prevalence': 0.15,
    },
    'both': {
        'ionization_likelihood': 0.55,
        'record_quality': 0.30,
        'prevalence': 0.15,
    },
}


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


def _load_latest_pubchem_raw_results(formula: str) -> Optional[List[Any]]:
    try:
        normalized_formula = _normalize_formula(formula)
        if not normalized_formula:
            return None

        path_manager = PathManager()
        raw_dir = path_manager.get_pubchem_raw_cache_path()
        file_pattern = f"pubchem_raw_{_safe_formula_filename(normalized_formula)}_*.json"
        candidates = sorted(raw_dir.glob(file_pattern), key=lambda item: item.stat().st_mtime, reverse=True)

        for file_path in candidates:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    payload = json.load(f)
                raw_results = payload.get('raw_results') if isinstance(payload, dict) else None
                if isinstance(raw_results, list) and raw_results:
                    logging.info(f"命中 PubChem 原始缓存并准备重处理: {file_path}")
                    return raw_results
            except Exception as ex:
                logging.warning(f"读取 PubChem 原始缓存失败({file_path}): {ex}")
                continue
    except Exception as ex:
        logging.warning(f"检查 PubChem 原始缓存失败({formula}): {ex}")

    return None


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_synonyms(synonyms: Any) -> List[str]:
    if not isinstance(synonyms, list):
        return []
    output: List[str] = []
    for item in synonyms:
        if not isinstance(item, str):
            continue
        name = item.strip()
        if not name:
            continue
        output.append(name)
    return output


def _estimate_prevalence_from_synonyms(synonyms: List[str]) -> float:
    if not synonyms:
        return 0.0

    trusted_markers = ('CAS', 'UNII', 'CHEBI', 'CHEMBL', 'PUBCHEM')
    trusted_count = 0
    for name in synonyms:
        upper_name = name.upper()
        if any(marker in upper_name for marker in trusted_markers):
            trusted_count += 1

    raw_score = min(len(synonyms), 120) / 120.0
    trusted_bonus = min(trusted_count, 20) / 200.0
    return max(0.0, min(1.0, raw_score + trusted_bonus))


def _ionization_likelihood_score(compound: Dict[str, Any], ion_mode: str) -> float:
    xlogp = _safe_float(compound.get('xlogp'))
    tpsa = _safe_float(compound.get('tpsa'))
    hbd = _safe_int(compound.get('hbond_donor_count')) or 0
    hba = _safe_int(compound.get('hbond_acceptor_count')) or 0
    charge = _safe_int(compound.get('charge')) or 0

    base = 0.30
    if ion_mode == 'positive':
        base += min(hba, 8) * 0.05
        base += min(hbd, 6) * 0.02
        if charge > 0:
            base += 0.20
        elif charge < 0:
            base -= 0.05
        if xlogp is not None:
            if -1.0 <= xlogp <= 3.0:
                base += 0.12
            elif xlogp > 5.0:
                base -= 0.08
        if tpsa is not None:
            if 20.0 <= tpsa <= 150.0:
                base += 0.10
            elif tpsa > 220.0:
                base -= 0.06
    elif ion_mode == 'negative':
        base += min(hbd, 8) * 0.05
        base += min(hba, 6) * 0.02
        if charge < 0:
            base += 0.20
        elif charge > 0:
            base -= 0.05
        if xlogp is not None:
            if -2.0 <= xlogp <= 2.5:
                base += 0.12
            elif xlogp > 5.0:
                base -= 0.08
        if tpsa is not None:
            if 30.0 <= tpsa <= 180.0:
                base += 0.10
            elif tpsa > 240.0:
                base -= 0.06
    else:
        positive_score = _ionization_likelihood_score(compound, 'positive')
        negative_score = _ionization_likelihood_score(compound, 'negative')
        return max(positive_score, negative_score)

    return max(0.0, min(1.0, base))


def _record_quality_score(compound: Dict[str, Any]) -> float:
    required = [
        'canonical_smiles',
        'isomeric_smiles',
        'inchi',
        'inchikey',
        'iupac_name',
        'monoisotopic_mass',
        'molecular_weight',
    ]
    present = 0
    for key in required:
        value = compound.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        present += 1

    score = present / len(required)
    if compound.get('exact_mass') is not None:
        score += 0.05
    return max(0.0, min(1.0, score))


def _build_why_selected(
    compound: Dict[str, Any],
    ion_score: float,
    quality_score: float,
    prevalence_score: float,
) -> List[str]:
    reasons: List[str] = []
    if ion_score >= 0.7:
        reasons.append('离子化倾向较高')
    if quality_score >= 0.75:
        reasons.append('结构信息较完整')
    if prevalence_score >= 0.6:
        reasons.append('同义词较丰富，公共记录较多')
    if compound.get('exact_mass') is not None:
        reasons.append('包含精确质量字段，可用于后续精细比对')
    if not reasons:
        reasons.append('基础结构信息可用，但证据强度一般')
    return reasons


def _normalize_pubchem_compound(compound: Any) -> Dict[str, Any]:
    if isinstance(compound, dict):
        src = compound
    else:
        src = _compound_to_serializable(compound)

    normalized = {
        'cid': _safe_int(src.get('cid', src.get('CID'))),
        'iupac_name': src.get('iupac_name', src.get('IUPACName')),
        'isomeric_smiles': src.get('isomeric_smiles', src.get('IsomericSMILES')),
        'canonical_smiles': src.get('canonical_smiles', src.get('CanonicalSMILES')),
        'inchi': src.get('inchi', src.get('InChI')),
        'inchikey': src.get('inchikey', src.get('InChIKey')),
        'molecular_weight': _safe_float(src.get('molecular_weight', src.get('MolecularWeight'))),
        'monoisotopic_mass': _safe_float(src.get('monoisotopic_mass', src.get('MonoisotopicMass'))),
        'exact_mass': _safe_float(src.get('exact_mass', src.get('ExactMass'))),
        'xlogp': _safe_float(src.get('xlogp', src.get('XLogP'))),
        'tpsa': _safe_float(src.get('tpsa', src.get('TPSA'))),
        'hbond_donor_count': _safe_int(src.get('hbond_donor_count', src.get('HBondDonorCount'))),
        'hbond_acceptor_count': _safe_int(src.get('hbond_acceptor_count', src.get('HBondAcceptorCount'))),
        'rotatable_bond_count': _safe_int(src.get('rotatable_bond_count', src.get('RotatableBondCount'))),
        'heavy_atom_count': _safe_int(src.get('heavy_atom_count', src.get('HeavyAtomCount'))),
        'charge': _safe_int(src.get('charge', src.get('Charge'))),
        'title': src.get('title', src.get('Title')),
        'synonyms': _normalize_synonyms(src.get('synonyms', [])),
    }

    normalized['data_quality'] = {
        'has_structure_identifier': bool(normalized['canonical_smiles'] or normalized['inchi']),
        'has_inchikey': bool(normalized['inchikey']),
        'core_fields_present': sum(
            1
            for key in ('cid', 'iupac_name', 'canonical_smiles', 'inchi', 'inchikey', 'monoisotopic_mass')
            if normalized.get(key) not in (None, '')
        ),
    }

    return normalized


def _rank_compounds(compounds: List[Any], ion_mode: str = 'both') -> List[Dict[str, Any]]:
    mode = ion_mode.lower().strip()
    if mode not in SCORE_WEIGHT_BY_MODE:
        mode = 'both'
    weights = SCORE_WEIGHT_BY_MODE[mode]

    normalized_compounds = [_normalize_pubchem_compound(compound) for compound in compounds]
    for compound in normalized_compounds:
        ion_score = _ionization_likelihood_score(compound, mode)
        quality_score = _record_quality_score(compound)
        prevalence_score = _estimate_prevalence_from_synonyms(compound.get('synonyms', []))

        final_score = (
            ion_score * weights['ionization_likelihood'] +
            quality_score * weights['record_quality'] +
            prevalence_score * weights['prevalence']
        )

        compound['score_breakdown'] = {
            'ionization_likelihood': round(ion_score, 4),
            'record_quality': round(quality_score, 4),
            'prevalence': round(prevalence_score, 4),
        }
        compound['final_score'] = round(final_score * 100.0, 2)
        compound['why_selected'] = _build_why_selected(compound, ion_score, quality_score, prevalence_score)

    # InChIKey first block去重，保留同组中得分更高的记录
    dedup: Dict[str, Dict[str, Any]] = {}
    fallback_items: List[Dict[str, Any]] = []
    for compound in normalized_compounds:
        key = compound.get('inchikey')
        if isinstance(key, str) and '-' in key:
            block = key.split('-', 1)[0]
            exists = dedup.get(block)
            if exists is None or compound['final_score'] > exists['final_score']:
                dedup[block] = compound
        else:
            fallback_items.append(compound)

    ranked = list(dedup.values()) + fallback_items
    ranked.sort(
        key=lambda item: (
            item.get('final_score', 0),
            item.get('score_breakdown', {}).get('record_quality', 0),
            item.get('cid') or 0,
        ),
        reverse=True,
    )

    for idx, item in enumerate(ranked, start=1):
        item['rank'] = idx

    return ranked


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


def _build_pubchem_compounds_from_cids(
    cids: List[int],
    max_records: int = 100,
    source_compounds: Optional[List[Any]] = None,
) -> List[Dict[str, Any]]:
    if not cids:
        return []
    cids = cids[:max_records]
    properties = [
        'CID',
        'Title',
        'IUPACName',
        'IsomericSMILES',
        'CanonicalSMILES',
        'InChI',
        'InChIKey',
        'MolecularWeight',
        'MonoisotopicMass',
        'ExactMass',
        'XLogP',
        'TPSA',
        'HBondDonorCount',
        'HBondAcceptorCount',
        'RotatableBondCount',
        'HeavyAtomCount',
        'Charge',
    ]
    url = (
        'https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/' +
        ','.join(str(cid) for cid in cids) +
        '/property/' + ','.join(properties) +
        '/JSON'
    )
    try:
        synonym_map: Dict[int, List[str]] = {}
        for raw in source_compounds or []:
            normalized = _normalize_pubchem_compound(raw)
            cid = normalized.get('cid')
            if cid is None:
                continue
            if normalized.get('synonyms'):
                synonym_map[cid] = normalized['synonyms']

        data = _fetch_pubchem_json(url)
        properties_list = data.get('PropertyTable', {}).get('Properties', [])
        compounds = []
        for item in properties_list:
            cid = item.get('CID')
            compounds.append({
                'CID': cid,
                'Title': item.get('Title'),
                'IUPACName': item.get('IUPACName'),
                'IsomericSMILES': item.get('IsomericSMILES'),
                'CanonicalSMILES': item.get('CanonicalSMILES'),
                'InChI': item.get('InChI'),
                'InChIKey': item.get('InChIKey'),
                'MolecularWeight': item.get('MolecularWeight'),
                'MonoisotopicMass': item.get('MonoisotopicMass'),
                'ExactMass': item.get('ExactMass'),
                'XLogP': item.get('XLogP'),
                'TPSA': item.get('TPSA'),
                'HBondDonorCount': item.get('HBondDonorCount'),
                'HBondAcceptorCount': item.get('HBondAcceptorCount'),
                'RotatableBondCount': item.get('RotatableBondCount'),
                'HeavyAtomCount': item.get('HeavyAtomCount'),
                'Charge': item.get('Charge'),
                'synonyms': synonym_map.get(cid, []),
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
                    enriched_compounds = _build_pubchem_compounds_from_cids(cids, source_compounds=compounds)
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
    def __init__(self, searcher: FormulaSearch, exporter_name: str, ion_mode: str = 'both', raw_only: bool = False):
        self.searcher = searcher
        self.exporter_name = exporter_name
        self.ion_mode = ion_mode
        self.raw_only = raw_only

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
                if self.exporter_name == 'json_formulaSearch_PubChem':
                    raw_cached_compounds = _load_latest_pubchem_raw_results(formula)
                    if raw_cached_compounds:
                        ranked_compounds = _rank_compounds(raw_cached_compounds, ion_mode=self.ion_mode)
                        export_data = exporter.export((formula, ranked_compounds))
                        results["success"][formula] = export_data
                        logging.info(f"分子式 {formula} 使用 PubChem 原始缓存重处理完成")
                        continue
                    if self.raw_only:
                        logging.warning(f"分子式 {formula} 未命中 PubChem 原始缓存，raw_only 模式下跳过")
                        results["failed"].append(formula)
                        continue

                compounds = self.searcher.get_compounds(formula)
                if compounds:
                    _save_pubchem_raw_data(formula, compounds)
                    ranked_compounds = _rank_compounds(compounds, ion_mode=self.ion_mode)
                    export_data = exporter.export((formula, ranked_compounds))
                    results["success"][formula] = export_data
                else:
                    results["failed"].append(formula)
            except Exception as ex:
                logging.error(f"处理化学式 {formula} 失败: {ex}", exc_info=True)
                results["failed"].append(formula)

        return results


def start_search(
    formula_list: List[str],
    web_name: str,
    ion_mode: str = 'both',
    raw_only: bool = False,
) -> Dict[str, Any]:
    web_name_lower = web_name.lower()
    if 'pubchem' in web_name_lower:
        searcher = FormulaSearchPubChem()
        exporter_name = 'json_formulaSearch_PubChem'
    else:
        raise ValueError(f"未知的 web_name: {web_name}")

    manager = SearchManager(searcher, exporter_name, ion_mode=ion_mode, raw_only=raw_only)
    return manager.search_formula_list(formula_list)
