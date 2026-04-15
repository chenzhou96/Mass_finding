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

from ..config.base_config import BaseConfig
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
    def __init__(self, max_retries: int = 3, retry_delay: int = 2):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.last_error_category = 'other'
        self.last_error_message = 'unknown'

    def _set_last_error(self, category: str, message: str):
        self.last_error_category = category
        self.last_error_message = message

    def get_last_error(self) -> Dict[str, str]:
        return {
            'category': self.last_error_category,
            'message': self.last_error_message,
        }

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


COMMERCIAL_KEYWORD_WEIGHTS: Dict[str, float] = {
    'for mass spectrometry': 0.08,
    'reference standard': 0.10,
    'certified reference material': 0.10,
    'usp': 0.08,
    'ep': 0.08,
    'grade': 0.05,
    'solution': 0.04,
    'buffer': 0.04,
}

COMMERCIAL_BOOST_CAP = 0.20


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


def _commercial_availability_boost(synonyms: List[str]) -> float:
    if not synonyms:
        return 0.0

    lowered = [name.lower() for name in synonyms if isinstance(name, str)]
    if not lowered:
        return 0.0

    boost = 0.0
    for keyword, weight in COMMERCIAL_KEYWORD_WEIGHTS.items():
        if any(keyword in name for name in lowered):
            boost += weight

    return max(0.0, min(COMMERCIAL_BOOST_CAP, boost))


def _contains_isotope_marker(inchi: Any) -> bool:
    return isinstance(inchi, str) and '/i' in inchi.lower()


def _extract_record_count_value(src: Dict[str, Any], key: str) -> Optional[int]:
    record = src.get('record')
    if not isinstance(record, dict):
        return None
    count = record.get('count')
    if not isinstance(count, dict):
        return None
    return _safe_int(count.get(key))


def _strict_filter_reasons(compound: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []

    covalent_unit = _safe_int(compound.get('covalent_unit')) or 0
    if covalent_unit > 1:
        reasons.append('多组分结构(covalent_unit>1)')

    iupac_name = compound.get('iupac_name')
    if isinstance(iupac_name, str) and ';' in iupac_name:
        reasons.append('IUPAC 名称包含分号')

    isotope_atom_count = _safe_int(compound.get('isotope_atom_count')) or 0
    if isotope_atom_count > 0 or bool(compound.get('isotopic_flag')):
        reasons.append('同位素标记化合物')

    return reasons


def _is_strict_filtered_compound(compound: Dict[str, Any]) -> bool:
    return bool(_strict_filter_reasons(compound))


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
    commercial_boost: float = 0.0,
) -> List[str]:
    reasons: List[str] = []
    if ion_score >= 0.7:
        reasons.append('离子化倾向较高')
    if quality_score >= 0.75:
        reasons.append('结构信息较完整')
    if prevalence_score >= 0.6:
        reasons.append('同义词较丰富，公共记录较多')
    if commercial_boost >= 0.08:
        reasons.append('命中可购试剂关键词，商业可获得性较高')
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

    isotope_atom_count = _safe_int(src.get('isotope_atom_count', src.get('isotope_atom')))
    if isotope_atom_count is None:
        isotope_atom_count = _extract_record_count_value(src, 'isotope_atom')

    covalent_unit = _safe_int(src.get('covalent_unit', src.get('covalent_unit_count')))
    if covalent_unit is None:
        covalent_unit = _extract_record_count_value(src, 'covalent_unit')

    inchi_value = src.get('inchi', src.get('InChI'))

    normalized = {
        'cid': _safe_int(src.get('cid', src.get('CID'))),
        'iupac_name': src.get('iupac_name', src.get('IUPACName')),
        'isomeric_smiles': src.get('isomeric_smiles', src.get('IsomericSMILES')),
        'canonical_smiles': src.get('canonical_smiles', src.get('CanonicalSMILES')),
        'inchi': inchi_value,
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
        'isotope_atom_count': isotope_atom_count,
        'covalent_unit': covalent_unit,
    }

    normalized['isotopic_flag'] = bool((isotope_atom_count or 0) > 0 or _contains_isotope_marker(inchi_value))

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

def _rank_compounds(compounds: List[Any], ion_mode: str = 'both', strict_filter: bool = True) -> List[Dict[str, Any]]:
    mode = ion_mode.lower().strip()
    if mode not in SCORE_WEIGHT_BY_MODE:
        mode = 'both'
    weights = SCORE_WEIGHT_BY_MODE[mode]

    normalized_compounds = [_normalize_pubchem_compound(compound) for compound in compounds]
    if strict_filter:
        filtered_count = 0
        kept_compounds: List[Dict[str, Any]] = []
        for compound in normalized_compounds:
            if _is_strict_filtered_compound(compound):
                filtered_count += 1
                continue
            kept_compounds.append(compound)
        if filtered_count > 0:
            logging.info(f"严格过滤命中 {filtered_count} 条记录")
        normalized_compounds = kept_compounds

    for compound in normalized_compounds:
        ion_score = _ionization_likelihood_score(compound, mode)
        quality_score = _record_quality_score(compound)
        base_prevalence_score = _estimate_prevalence_from_synonyms(compound.get('synonyms', []))
        commercial_boost = _commercial_availability_boost(compound.get('synonyms', []))
        prevalence_score = max(0.0, min(1.0, base_prevalence_score + commercial_boost))

        final_score = (
            ion_score * weights['ionization_likelihood'] +
            quality_score * weights['record_quality'] +
            prevalence_score * weights['prevalence']
        )

        compound['score_breakdown'] = {
            'ionization_likelihood': round(ion_score, 4),
            'record_quality': round(quality_score, 4),
            'prevalence': round(prevalence_score, 4),
            'commercial_availability': round(commercial_boost, 4),
        }
        compound['final_score'] = round(final_score * 100.0, 2)
        compound['why_selected'] = _build_why_selected(compound, ion_score, quality_score, prevalence_score, commercial_boost)

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


def _fetch_pubchem_json(url: str, timeout: int = 30, endpoint_label: str = 'unknown') -> dict:
    started_at = time.perf_counter()
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode('utf-8'))
    elapsed = time.perf_counter() - started_at
    logging.info(f"PubChem {endpoint_label} 请求完成，耗时 {elapsed:.2f}s")
    return payload


def _parse_listkey_response(response: dict) -> Dict[str, Any]:
    result: Dict[str, Any] = {'cids': None, 'listkey': None}
    if not isinstance(response, dict):
        return result
    if 'IdentifierList' in response and isinstance(response['IdentifierList'], dict):
        cid_list = response['IdentifierList'].get('CID')
        if isinstance(cid_list, list):
            result['cids'] = [int(cid) for cid in cid_list if isinstance(cid, int)]

    waiting = response.get('Waiting')
    if isinstance(waiting, dict):
        listkey = waiting.get('ListKey')
        if isinstance(listkey, str) and listkey.strip():
            result['listkey'] = listkey.strip()
    return result


def _categorize_failure(message: str) -> str:
    text = (message or '').lower()
    if 'poll_limit' in text:
        return 'poll_limit'
    if 'timeout' in text or 'timed out' in text or 'pugrest.timeout' in text:
        return 'timeout'
    if 'no_compounds' in text or '未返回 cid' in text or '未匹配到任何化合物' in text:
        return 'no_compounds'
    return 'other'


def _poll_pubchem_listkey(
    listkey: str,
    timeout: int = 30,
    poll_interval: int = 2,
    poll_max_attempts: int = 6,
) -> Dict[str, Any]:
    if not listkey:
        return {'cids': None, 'error': 'poll_limit:empty_listkey'}

    url = f'https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/listkey/{listkey}/cids/JSON'
    for attempt in range(poll_max_attempts):
        try:
            response = _fetch_pubchem_json(url, timeout=timeout, endpoint_label='listkey')
            parsed = _parse_listkey_response(response)
            cids = parsed.get('cids')
            if cids:
                return {'cids': cids, 'error': None}

            still_waiting = isinstance(response.get('Waiting'), dict)
            if not still_waiting:
                return {'cids': None, 'error': 'no_compounds:listkey_finished_without_cids'}

            if attempt + 1 < poll_max_attempts:
                logging.info(
                    f"PubChem listkey 仍在处理中({attempt + 1}/{poll_max_attempts})，将在 {poll_interval}s 后继续轮询"
                )
                time.sleep(poll_interval)
        except Exception as ex:
            logging.warning(f"PubChem listkey 轮询失败({attempt + 1}/{poll_max_attempts}): {ex}")
            if attempt + 1 < poll_max_attempts:
                time.sleep(poll_interval)
    return {'cids': None, 'error': f'poll_limit:listkey_exceeded_{poll_max_attempts}'}


def _build_pubchem_compounds_from_cids(
    cids: List[int],
    max_records: int = 100,
    source_compounds: Optional[List[Any]] = None,
    timeout: int = 30,
) -> List[Dict[str, Any]]:
    if not cids:
        return []
    cids = cids[:max_records]
    properties = [
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

        data = _fetch_pubchem_json(url, timeout=timeout, endpoint_label='cid-property')
        properties_list = data.get('PropertyTable', {}).get('Properties', [])
        compounds = []
        for idx, item in enumerate(properties_list):
            cid = item.get('CID')
            if cid is None and idx < len(cids):
                cid = cids[idx]
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


def _try_pubchem_formula_search_rest(
    formula: str,
    fast: bool = False,
    timeout: int = 30,
    poll_interval: int = 2,
    poll_max_attempts: int = 6,
) -> Dict[str, Any]:
    encoded = urllib.parse.quote(formula)
    endpoint = 'fastformula' if fast else 'formula'
    url = f'https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/{endpoint}/{encoded}/cids/JSON'
    try:
        response = _fetch_pubchem_json(url, timeout=timeout, endpoint_label=endpoint)
        parsed = _parse_listkey_response(response)
        cids = parsed.get('cids')
        if cids:
            return {'cids': cids, 'error': None, 'endpoint': endpoint}

        listkey = parsed.get('listkey')
        if listkey:
            logging.info(f"PubChem {endpoint} 查询进入异步队列，listkey={listkey}")
            poll_result = _poll_pubchem_listkey(
                listkey,
                timeout=timeout,
                poll_interval=poll_interval,
                poll_max_attempts=poll_max_attempts,
            )
            poll_result['endpoint'] = endpoint
            return poll_result

        return {'cids': None, 'error': f'no_compounds:{endpoint}_no_cids', 'endpoint': endpoint}
    except urllib.error.HTTPError as ex:
        if ex.code == 404:
            return {'cids': None, 'error': f'no_compounds:{endpoint}_404', 'endpoint': endpoint}
        logging.warning(f"PubChem REST {endpoint} 查询失败 {formula}: {ex}")
        return {'cids': None, 'error': f'other:{endpoint}_http_{ex.code}', 'endpoint': endpoint}
    except Exception as ex:
        logging.warning(f"PubChem REST {endpoint} 查询异常 {formula}: {ex}")
        return {'cids': None, 'error': f'timeout:{endpoint}:{ex}', 'endpoint': endpoint}


class FormulaSearchPubChem(FormulaSearch):
    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: int = 2,
        http_timeout: int = 30,
        poll_interval: int = 2,
        poll_max_attempts: int = 6,
        prefer_fastformula: bool = True,
    ):
        super().__init__(max_retries=max_retries, retry_delay=retry_delay)
        self.http_timeout = max(5, int(http_timeout))
        self.poll_interval = max(1, int(poll_interval))
        self.poll_max_attempts = max(1, int(poll_max_attempts))
        self.prefer_fastformula = bool(prefer_fastformula)

    def get_compounds(self, formula: str):
        formula = _normalize_formula(formula)
        if not formula:
            logging.warning("PubChem 查询时遇到空化学式。")
            self._set_last_error('no_compounds', 'empty_formula')
            return None

        self._set_last_error('other', 'unknown')

        pcp = None
        try:
            import pubchempy as pcp
        except ModuleNotFoundError:
            logging.warning("未安装 pubchempy，将仅使用 PubChem REST 路径检索")

        endpoint_priority: List[bool]
        if self.prefer_fastformula:
            endpoint_priority = [True, False]
        else:
            endpoint_priority = [False, True]

        for attempt in range(self.max_retries):
            current_attempt = attempt + 1
            try:
                last_rest_error = 'no_compounds:no_cids_from_all_endpoints'
                for use_fast in endpoint_priority:
                    endpoint_name = 'fastformula' if use_fast else 'formula'
                    rest_result = _try_pubchem_formula_search_rest(
                        formula,
                        fast=use_fast,
                        timeout=self.http_timeout,
                        poll_interval=self.poll_interval,
                        poll_max_attempts=self.poll_max_attempts,
                    )
                    cids = rest_result.get('cids')
                    endpoint_error = rest_result.get('error')
                    if not cids:
                        if endpoint_error:
                            last_rest_error = endpoint_error
                        logging.info(
                            f"PubChem {endpoint_name} 未返回 CID({current_attempt}/{self.max_retries}) for {formula}"
                        )
                        continue

                    compounds = _build_pubchem_compounds_from_cids(cids, timeout=self.http_timeout)
                    if compounds:
                        self._set_last_error('other', '')
                        return compounds

                if pcp is not None:
                    compounds = pcp.get_compounds(formula, 'formula')
                    if compounds:
                        cids = _extract_cids_from_compounds(compounds)
                        enriched_compounds = _build_pubchem_compounds_from_cids(
                            cids,
                            source_compounds=compounds,
                            timeout=self.http_timeout,
                        )
                        if enriched_compounds:
                            self._set_last_error('other', '')
                            return enriched_compounds
                        self._set_last_error('other', '')
                        return compounds

                self._set_last_error(_categorize_failure(last_rest_error), last_rest_error)
            except Exception as ex:
                message = str(ex)
                self._set_last_error(_categorize_failure(message), message)
                logging.warning(
                    f"PubChem 请求失败({current_attempt}/{self.max_retries}) for {formula}: {message}"
                )

            if current_attempt < self.max_retries:
                delay = self.retry_delay * (2 ** attempt)
                logging.info(f"PubChem 即将重试 {formula}，等待 {delay}s")
                time.sleep(delay)

        logging.error(f"PubChem 查询最终失败: {formula}")
        if self.last_error_message in ('unknown', ''):
            self._set_last_error('no_compounds', 'no_compounds:final_empty_result')
        return None


class SearchManager:
    def __init__(self, searcher: FormulaSearch, exporter_name: str, ion_mode: str = 'both', raw_only: bool = False, strict_filter: bool = True):
        self.searcher = searcher
        self.exporter_name = exporter_name
        self.ion_mode = ion_mode
        self.raw_only = raw_only
        self.strict_filter = strict_filter

    def search_formula_list(self, formula_list: List[str]) -> Dict[str, Any]:
        if not formula_list:
            logging.warning("未识别到任何化学式")
            return {"success": {}, "failed": []}

        results = {
            "success": {},
            "failed": [],
            "failed_details": {},
            "failed_stats": {
                "timeout": 0,
                "no_compounds": 0,
                "poll_limit": 0,
                "other": 0,
            },
        }
        exporter = ExporterFactory.get_exporter(self.exporter_name)
        if exporter is None:
            raise ValueError(f"找不到导出器: {self.exporter_name}")

        for formula in formula_list:
            try:
                if self.exporter_name == 'json_formulaSearch_PubChem':
                    raw_cached_compounds = _load_latest_pubchem_raw_results(formula)
                    if raw_cached_compounds:
                        ranked_compounds = _rank_compounds(raw_cached_compounds, ion_mode=self.ion_mode, strict_filter=self.strict_filter)
                        export_data = exporter.export((formula, ranked_compounds))
                        results["success"][formula] = export_data
                        logging.info(f"分子式 {formula} 使用 PubChem 原始缓存重处理完成")
                        continue
                    if self.raw_only:
                        logging.warning(f"分子式 {formula} 未命中 PubChem 原始缓存，raw_only 模式下跳过")
                        results["failed"].append(formula)
                        results["failed_details"][formula] = {
                            "category": "no_compounds",
                            "message": "raw_only_no_cache",
                        }
                        results["failed_stats"]["no_compounds"] += 1
                        continue

                compounds = self.searcher.get_compounds(formula)
                if compounds:
                    _save_pubchem_raw_data(formula, compounds)
                    ranked_compounds = _rank_compounds(compounds, ion_mode=self.ion_mode, strict_filter=self.strict_filter)
                    export_data = exporter.export((formula, ranked_compounds))
                    results["success"][formula] = export_data
                else:
                    results["failed"].append(formula)
                    error_info = self.searcher.get_last_error() if hasattr(self.searcher, 'get_last_error') else {
                        'category': 'other',
                        'message': 'unknown',
                    }
                    category = error_info.get('category', 'other')
                    if category not in results["failed_stats"]:
                        category = 'other'
                    results["failed_details"][formula] = {
                        "category": category,
                        "message": error_info.get('message', 'unknown'),
                    }
                    results["failed_stats"][category] += 1
            except Exception as ex:
                logging.error(f"处理化学式 {formula} 失败: {ex}", exc_info=True)
                results["failed"].append(formula)
                results["failed_details"][formula] = {
                    "category": "other",
                    "message": str(ex),
                }
                results["failed_stats"]["other"] += 1

        return results


def start_search(
    formula_list: List[str],
    web_name: str,
    ion_mode: str = 'both',
    raw_only: bool = False,
    strict_filter: bool = True,
) -> Dict[str, Any]:
    web_name_lower = web_name.lower()
    if 'pubchem' in web_name_lower:
        searcher = FormulaSearchPubChem(
            max_retries=BaseConfig.PUBCHEM_MAX_RETRIES,
            retry_delay=BaseConfig.PUBCHEM_RETRY_BASE_DELAY_SEC,
            http_timeout=BaseConfig.PUBCHEM_HTTP_TIMEOUT_SEC,
            poll_interval=BaseConfig.PUBCHEM_POLL_INTERVAL_SEC,
            poll_max_attempts=BaseConfig.PUBCHEM_POLL_MAX_ATTEMPTS,
            prefer_fastformula=BaseConfig.PUBCHEM_PREFER_FASTFORMULA,
        )
        exporter_name = 'json_formulaSearch_PubChem'
    else:
        raise ValueError(f"未知的 web_name: {web_name}")

    manager = SearchManager(searcher, exporter_name, ion_mode=ion_mode, raw_only=raw_only, strict_filter=strict_filter)
    return manager.search_formula_list(formula_list)
