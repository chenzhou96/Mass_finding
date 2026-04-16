import json
import logging
import time
import datetime
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ..config.base_config import BaseConfig
from ..config.path_config import PathManager
from ..service.public import ExporterFactory


class SearchStatus(Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
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
        'ionization_likelihood': 0.10,
        'record_quality': 0.20,
        'prevalence': 0.70,
    },
    'negative': {
        'ionization_likelihood': 0.10,
        'record_quality': 0.20,
        'prevalence': 0.70,
    },
    'both': {
        'ionization_likelihood': 0.10,
        'record_quality': 0.20,
        'prevalence': 0.70,
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

PUBLIC_RECORD_MARKERS = (
    'CAS', 'UNII', 'CHEBI', 'CHEMBL', 'PUBCHEM', 'HMDB', 'KEGG', 'DRUGBANK', 'LIPIDMAPS', 'METLIN'
)

BIOLOGICAL_RECORD_MARKERS = (
    'HMDB', 'KEGG', 'LIPIDMAPS', 'DRUGBANK', 'METLIN', 'BIOCYC'
)

KNOWN_BIOACTIVE_NAME_MARKERS = (
    'IBUPROFEN', 'DEXIBUPROFEN', 'NAPROXEN', 'DICLOFENAC', 'KETOPROFEN',
    'FLURBIPROFEN', 'FENOPROFEN', 'ASPIRIN', 'PARACETAMOL', 'ACETAMINOPHEN',
    'LIDOCAINE', 'CAFFEINE', 'CHOLESTEROL', 'GLUCOSE'
)


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


def _dedupe_compounds_by_cid(compounds: List[Any]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen_keys = set()

    for item in compounds or []:
        serialized = _compound_to_serializable(item)
        normalized = _normalize_pubchem_compound(serialized)
        key = (
            normalized.get('cid'),
            normalized.get('inchikey') or '',
            normalized.get('isomeric_smiles') or normalized.get('canonical_smiles') or '',
            normalized.get('iupac_name') or '',
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(serialized)

    return deduped


def _build_batch_summary(
    requested_cids: Optional[List[int]],
    compounds: List[Any],
    failed_batches: Optional[List[Dict[str, Any]]] = None,
    total_batches: int = 0,
) -> Dict[str, Any]:
    completed_cids = _extract_cids_from_compounds(compounds)
    completed_cid_set = set(completed_cids)

    requested_unique: List[int] = []
    for raw_cid in requested_cids or []:
        cid = _safe_int(raw_cid)
        if cid is None or cid in requested_unique:
            continue
        requested_unique.append(cid)

    missing_cids = [cid for cid in requested_unique if cid not in completed_cid_set]
    failure_count = len(failed_batches or [])
    success_batches = max(0, total_batches - failure_count) if total_batches else 0

    return {
        'total_batches': total_batches,
        'success_batches': success_batches,
        'failed_batches': failure_count,
        'completed_records': len(compounds or []),
        'completed_cids': completed_cids,
        'missing_cids': missing_cids,
    }


def _save_pubchem_raw_data(
    formula: str,
    compounds: Any,
    status: str = 'success',
    batch_summary: Optional[Dict[str, Any]] = None,
    failed_batches: Optional[List[Dict[str, Any]]] = None,
    error_message: Optional[str] = None,
):
    try:
        raw_items = compounds.get('compounds', []) if isinstance(compounds, dict) else compounds
        save_status = status
        save_error = error_message
        save_batch_summary = batch_summary
        save_failed_batches = failed_batches

        if isinstance(compounds, dict):
            if compounds.get('is_partial') and save_status == 'success':
                save_status = 'partial'
            if save_batch_summary is None:
                save_batch_summary = compounds.get('batch_summary')
            if save_failed_batches is None:
                save_failed_batches = compounds.get('failed_batches')
            if save_error is None:
                save_error = compounds.get('error')

        serialized_results = _dedupe_compounds_by_cid(raw_items if isinstance(raw_items, list) else [])

        path_manager = PathManager()
        safe_formula = _safe_formula_filename(formula)
        raw_dir = path_manager.ensure_pubchem_formula_cache_dir(safe_formula)
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        file_name = f"pubchem_raw_{safe_formula}_{timestamp}.json"
        output_path = raw_dir / file_name

        payload = {
            'metadata': {
                'formula': formula,
                'export_time': datetime.datetime.now().isoformat(),
                'source': 'pubchem_raw',
                'record_count': len(serialized_results),
                'status': save_status,
                'error_message': save_error,
            },
            'raw_results': serialized_results,
            'batch_summary': save_batch_summary or {},
            'failed_batches': save_failed_batches or [],
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        logging.info(f"PubChem 原始数据已保存: {output_path}")
    except Exception as ex:
        logging.warning(f"保存 PubChem 原始数据失败({formula}): {ex}")


def _load_latest_pubchem_raw_results(formula: str) -> Optional[Dict[str, Any]]:
    try:
        normalized_formula = _normalize_formula(formula)
        if not normalized_formula:
            return None

        path_manager = PathManager()
        raw_dir = path_manager.get_pubchem_raw_cache_path()
        safe_formula = _safe_formula_filename(normalized_formula)
        file_pattern = f"pubchem_raw_{safe_formula}_*.json"

        candidate_paths = []
        formula_dir = path_manager.get_pubchem_formula_cache_dir(safe_formula)
        if formula_dir.exists():
            candidate_paths.extend(formula_dir.glob(file_pattern))
        candidate_paths.extend(raw_dir.glob(file_pattern))

        unique_candidates = {str(item): item for item in candidate_paths}
        candidates = sorted(unique_candidates.values(), key=lambda item: item.stat().st_mtime, reverse=True)

        for file_path in candidates:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    payload = json.load(f)
                if not isinstance(payload, dict):
                    continue

                raw_results = payload.get('raw_results', [])
                if not isinstance(raw_results, list):
                    raw_results = []

                metadata = payload.get('metadata', {}) if isinstance(payload.get('metadata', {}), dict) else {}
                status = metadata.get('status', 'success')
                if raw_results or status in ('partial', 'failed'):
                    logging.info(f"命中 PubChem 原始缓存并准备重处理: {file_path} | status={status}")
                    return {
                        'metadata': metadata,
                        'raw_results': raw_results,
                        'batch_summary': payload.get('batch_summary', {}),
                        'failed_batches': payload.get('failed_batches', []),
                        'status': status,
                        'file_path': str(file_path),
                    }
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

    trusted_count = 0
    for name in synonyms:
        upper_name = name.upper()
        if any(marker in upper_name for marker in PUBLIC_RECORD_MARKERS):
            trusted_count += 1

    raw_score = min(len(synonyms), 60) / 60.0
    trusted_bonus = min(trusted_count, 12) / 48.0
    return max(0.0, min(1.0, raw_score + trusted_bonus))


def _normalize_text_key(text: Any) -> str:
    if not isinstance(text, str):
        return ''
    return ''.join(ch.lower() for ch in text.strip() if ch.isalnum())


def _estimate_prevalence_from_compound(compound: Dict[str, Any]) -> float:
    synonyms = compound.get('synonyms', []) if isinstance(compound.get('synonyms', []), list) else []
    synonym_score = _estimate_prevalence_from_synonyms(synonyms)
    if synonym_score > 0.0:
        return synonym_score

    marker_info = _collect_reference_markers(compound)
    public_markers = marker_info.get('public_markers', [])
    bio_markers = marker_info.get('bio_markers', [])

    title = compound.get('title')
    iupac_name = compound.get('iupac_name')
    title_key = _normalize_text_key(title)
    iupac_key = _normalize_text_key(iupac_name)
    combined_text = ' | '.join(
        value.strip().upper()
        for value in (title, iupac_name)
        if isinstance(value, str) and value.strip()
    )

    fallback_score = 0.0
    if public_markers:
        fallback_score += min(len(public_markers), 3) * 0.08
    if bio_markers:
        fallback_score += min(len(bio_markers), 3) * 0.05

    if title_key and iupac_key and title_key != iupac_key:
        fallback_score += 0.12
        if len(title_key) + 8 < len(iupac_key):
            fallback_score += 0.08

    if any(marker in combined_text for marker in KNOWN_BIOACTIVE_NAME_MARKERS):
        fallback_score += 0.15

    return max(0.0, min(0.35, fallback_score))


def _collect_reference_markers(compound: Dict[str, Any]) -> Dict[str, List[str]]:
    text_pool: List[str] = []

    synonyms = compound.get('synonyms', [])
    if isinstance(synonyms, list):
        text_pool.extend(item for item in synonyms if isinstance(item, str) and item.strip())

    for key in ('title', 'iupac_name'):
        value = compound.get(key)
        if isinstance(value, str) and value.strip():
            text_pool.append(value.strip())

    combined = ' | '.join(text_pool).upper()
    public_markers = [marker for marker in PUBLIC_RECORD_MARKERS if marker in combined]
    bio_markers = [marker for marker in BIOLOGICAL_RECORD_MARKERS if marker in combined]

    return {
        'public_markers': list(dict.fromkeys(public_markers)),
        'bio_markers': list(dict.fromkeys(bio_markers)),
    }


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
    synonyms = compound.get('synonyms', []) if isinstance(compound.get('synonyms', []), list) else []
    synonym_count = len(synonyms)
    marker_info = _collect_reference_markers(compound)
    public_markers = marker_info.get('public_markers', [])
    bio_markers = marker_info.get('bio_markers', [])

    if synonym_count >= 15 or prevalence_score >= 0.70:
        if public_markers:
            reasons.append(f"公共记录丰富（{'/'.join(public_markers[:3])}）")
        else:
            reasons.append(f'公共记录丰富（同义词 {synonym_count} 条）')
    elif synonym_count >= 6:
        reasons.append(f'有一定公共记录支持（同义词 {synonym_count} 条）')

    if bio_markers:
        reasons.append(f"命中生物相关词条：{'/'.join(bio_markers[:3])}")

    if commercial_boost >= 0.08:
        reasons.append('含标准品/试剂关键词')

    if quality_score >= 0.80:
        reasons.append('结构字段较完整')
    elif compound.get('inchikey') or compound.get('inchi') or compound.get('canonical_smiles'):
        reasons.append('具备基础结构标识')

    if ion_score >= 0.80 and len(reasons) < 4:
        reasons.append('离子化可见性较好')

    if not reasons:
        reasons.append('公共记录较少，但可作候选参考')

    return reasons[:4]


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
        base_prevalence_score = _estimate_prevalence_from_compound(compound)
        commercial_boost = _commercial_availability_boost(compound.get('synonyms', []))
        prevalence_score = max(0.0, min(1.0, base_prevalence_score + commercial_boost))
        marker_info = _collect_reference_markers(compound)

        final_score = (
            ion_score * weights['ionization_likelihood'] +
            quality_score * weights['record_quality'] +
            prevalence_score * weights['prevalence']
        )

        compound['public_record_count'] = len(compound.get('synonyms', [])) if isinstance(compound.get('synonyms', []), list) else 0
        compound['reference_markers'] = marker_info
        compound['score_breakdown'] = {
            'ionization_likelihood': round(ion_score, 4),
            'record_quality': round(quality_score, 4),
            'prevalence': round(prevalence_score, 4),
            'commercial_availability': round(commercial_boost, 4),
        }
        compound['final_score'] = round(final_score * 100.0, 2)
        compound['why_selected'] = _build_why_selected(compound, ion_score, quality_score, prevalence_score, commercial_boost)

    # 仅移除完全重复的条目；保留立体异构体并行展示
    seen_keys = set()
    ranked: List[Dict[str, Any]] = []
    for compound in normalized_compounds:
        dedup_key = (
            compound.get('cid') or 0,
            compound.get('inchikey') or '',
            compound.get('isomeric_smiles') or compound.get('canonical_smiles') or '',
            compound.get('iupac_name') or '',
        )
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)
        ranked.append(compound)

    ranked.sort(
        key=lambda item: (
            item.get('final_score', 0),
            item.get('score_breakdown', {}).get('prevalence', 0),
            item.get('score_breakdown', {}).get('record_quality', 0),
            item.get('cid') or 0,
        ),
        reverse=True,
    )

    for idx, item in enumerate(ranked, start=1):
        item['rank'] = idx

    return ranked


def rerank_cached_compounds(compounds: Any, ion_mode: str = 'both', strict_filter: bool = True) -> List[Dict[str, Any]]:
    if not isinstance(compounds, list):
        return []
    return _rank_compounds(compounds, ion_mode=ion_mode, strict_filter=strict_filter)


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
    if 'partial' in text:
        return 'partial'
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


def _fetch_pubchem_synonym_map(
    cids: List[int],
    timeout: int = 30,
    chunk_size: int = 100,
    per_batch_retries: int = 2,
    min_split_size: int = 1,
) -> Dict[str, Any]:
    ordered_cids: List[int] = []
    seen_cids = set()
    for raw_cid in cids or []:
        cid = _safe_int(raw_cid)
        if cid is None or cid in seen_cids:
            continue
        seen_cids.add(cid)
        ordered_cids.append(cid)

    if not ordered_cids:
        return {'synonym_map': {}, 'failed_batches': []}

    batch_size = max(1, int(chunk_size or 100))
    retries = max(1, int(per_batch_retries or 2))
    smallest_chunk = max(1, int(min_split_size or 1))
    total_batches = (len(ordered_cids) + batch_size - 1) // batch_size

    def _request_chunk(cid_chunk: List[int], batch_index: int, split_depth: int = 0) -> Dict[str, Any]:
        last_error = 'unknown'
        for attempt in range(1, retries + 1):
            try:
                url = (
                    'https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/' +
                    ','.join(str(cid) for cid in cid_chunk) +
                    '/synonyms/JSON'
                )
                logging.info(
                    f"PubChem 正在拉取同义词批次 {batch_index}/{total_batches}，本批 CID 数: {len(cid_chunk)}，尝试 {attempt}/{retries}"
                )
                data = _fetch_pubchem_json(url, timeout=timeout, endpoint_label='cid-synonyms')
                info_list = data.get('InformationList', {}).get('Information', [])
                chunk_map: Dict[int, List[str]] = {}
                for item in info_list:
                    cid = _safe_int(item.get('CID'))
                    synonyms = _normalize_synonyms(item.get('Synonym', []))
                    if cid is not None and synonyms:
                        chunk_map[cid] = synonyms
                return {
                    'synonym_map': chunk_map,
                    'failed_batches': [],
                }
            except Exception as ex:
                last_error = str(ex)
                logging.warning(
                    f"PubChem 同义词批次 {batch_index}/{total_batches} 拉取失败，CID 数 {len(cid_chunk)}，尝试 {attempt}/{retries}: {ex}"
                )
                if attempt < retries:
                    time.sleep(min(6, attempt))

        if len(cid_chunk) > smallest_chunk:
            split_point = max(1, len(cid_chunk) // 2)
            left_result = _request_chunk(cid_chunk[:split_point], batch_index, split_depth + 1)
            right_result = _request_chunk(cid_chunk[split_point:], batch_index, split_depth + 1)
            merged_map = dict(left_result.get('synonym_map', {}))
            merged_map.update(right_result.get('synonym_map', {}))
            return {
                'synonym_map': merged_map,
                'failed_batches': left_result.get('failed_batches', []) + right_result.get('failed_batches', []),
            }

        return {
            'synonym_map': {},
            'failed_batches': [{
                'batch_index': batch_index,
                'split_depth': split_depth,
                'cid_count': len(cid_chunk),
                'cids': list(cid_chunk),
                'reason': f'synonym_fetch_failed:{last_error}',
            }],
        }

    synonym_map: Dict[int, List[str]] = {}
    failed_batches: List[Dict[str, Any]] = []
    for batch_index, start_idx in enumerate(range(0, len(ordered_cids), batch_size), start=1):
        cid_chunk = ordered_cids[start_idx:start_idx + batch_size]
        chunk_result = _request_chunk(cid_chunk, batch_index)
        synonym_map.update(chunk_result.get('synonym_map', {}))
        failed_batches.extend(chunk_result.get('failed_batches', []))

    return {'synonym_map': synonym_map, 'failed_batches': failed_batches}


def _build_pubchem_compounds_from_cids(
    cids: List[int],
    max_records: Optional[int] = None,
    source_compounds: Optional[List[Any]] = None,
    timeout: int = 30,
    chunk_size: int = 100,
    per_batch_retries: Optional[int] = None,
    min_split_size: Optional[int] = None,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    if not cids:
        empty_summary = _build_batch_summary([], [], [], 0)
        return {
            'compounds': [],
            'failed_batches': [],
            'batch_summary': empty_summary,
            'is_partial': False,
            'error': 'no_cids',
        }

    ordered_cids: List[int] = []
    seen_cids = set()
    for raw_cid in cids:
        cid = _safe_int(raw_cid)
        if cid is None or cid in seen_cids:
            continue
        seen_cids.add(cid)
        ordered_cids.append(cid)

    if max_records is not None:
        limit = _safe_int(max_records)
        if limit is not None and limit > 0:
            ordered_cids = ordered_cids[:limit]

    if not ordered_cids:
        empty_summary = _build_batch_summary([], [], [], 0)
        return {
            'compounds': [],
            'failed_batches': [],
            'batch_summary': empty_summary,
            'is_partial': False,
            'error': 'no_cids',
        }

    try:
        batch_size = max(1, int(chunk_size))
    except (TypeError, ValueError):
        batch_size = 100

    try:
        retries = max(1, int(per_batch_retries if per_batch_retries is not None else BaseConfig.PUBCHEM_PROPERTY_BATCH_RETRIES))
    except (TypeError, ValueError):
        retries = 2

    try:
        smallest_chunk = max(1, int(min_split_size if min_split_size is not None else BaseConfig.PUBCHEM_PROPERTY_MIN_CHUNK_SIZE))
    except (TypeError, ValueError):
        smallest_chunk = 1

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

    synonym_map: Dict[int, List[str]] = {}
    for raw in source_compounds or []:
        normalized = _normalize_pubchem_compound(raw)
        cid = normalized.get('cid')
        if cid is None:
            continue
        if normalized.get('synonyms'):
            synonym_map[cid] = normalized['synonyms']

    missing_synonym_cids = [cid for cid in ordered_cids if cid not in synonym_map]
    synonym_fetch_failures: List[Dict[str, Any]] = []
    if missing_synonym_cids:
        synonym_fetch_result = _fetch_pubchem_synonym_map(
            missing_synonym_cids,
            timeout=timeout,
            chunk_size=batch_size,
            per_batch_retries=retries,
            min_split_size=smallest_chunk,
        )
        synonym_map.update(synonym_fetch_result.get('synonym_map', {}))
        synonym_fetch_failures = synonym_fetch_result.get('failed_batches', [])
        if synonym_fetch_failures:
            logging.warning(f"PubChem 同义词补全存在失败批次: {len(synonym_fetch_failures)}")

    def _request_chunk(cid_chunk: List[int], batch_index: int, split_depth: int = 0) -> Dict[str, Any]:
        last_error = 'unknown'
        for attempt in range(1, retries + 1):
            try:
                url = (
                    'https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/' +
                    ','.join(str(cid) for cid in cid_chunk) +
                    '/property/' + ','.join(properties) +
                    '/JSON'
                )
                logging.info(
                    f"PubChem 正在拉取属性批次 {batch_index}/{total_batches}，本批 CID 数: {len(cid_chunk)}，尝试 {attempt}/{retries}"
                )
                data = _fetch_pubchem_json(url, timeout=timeout, endpoint_label='cid-property')
                properties_list = data.get('PropertyTable', {}).get('Properties', [])
                chunk_compounds: List[Dict[str, Any]] = []
                for idx, item in enumerate(properties_list):
                    cid = item.get('CID')
                    if cid is None and idx < len(cid_chunk):
                        cid = cid_chunk[idx]
                    chunk_compounds.append({
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
                return {
                    'compounds': chunk_compounds,
                    'failed_batches': [],
                }
            except Exception as ex:
                last_error = str(ex)
                logging.warning(
                    f"PubChem 属性批次 {batch_index}/{total_batches} 拉取失败，CID 数 {len(cid_chunk)}，尝试 {attempt}/{retries}: {ex}"
                )
                if attempt < retries:
                    time.sleep(min(6, attempt))

        if len(cid_chunk) > smallest_chunk:
            split_point = max(1, len(cid_chunk) // 2)
            logging.warning(
                f"PubChem 属性批次 {batch_index}/{total_batches} 将拆分重试，原始大小 {len(cid_chunk)} -> {split_point}+{len(cid_chunk) - split_point}"
            )
            left_result = _request_chunk(cid_chunk[:split_point], batch_index, split_depth + 1)
            right_result = _request_chunk(cid_chunk[split_point:], batch_index, split_depth + 1)
            return {
                'compounds': left_result.get('compounds', []) + right_result.get('compounds', []),
                'failed_batches': left_result.get('failed_batches', []) + right_result.get('failed_batches', []),
            }

        return {
            'compounds': [],
            'failed_batches': [{
                'batch_index': batch_index,
                'split_depth': split_depth,
                'cid_count': len(cid_chunk),
                'cids': list(cid_chunk),
                'reason': last_error,
            }],
        }

    compounds: List[Dict[str, Any]] = []
    failed_batches: List[Dict[str, Any]] = list(synonym_fetch_failures)
    total_batches = (len(ordered_cids) + batch_size - 1) // batch_size

    for batch_index, start_idx in enumerate(range(0, len(ordered_cids), batch_size), start=1):
        cid_chunk = ordered_cids[start_idx:start_idx + batch_size]
        chunk_result = _request_chunk(cid_chunk, batch_index)
        compounds.extend(chunk_result.get('compounds', []))
        failed_batches.extend(chunk_result.get('failed_batches', []))

        current_compounds = _dedupe_compounds_by_cid(compounds)
        current_summary = _build_batch_summary(ordered_cids, current_compounds, failed_batches, total_batches)
        current_missing = current_summary.get('missing_cids', [])
        current_payload = {
            'compounds': current_compounds,
            'failed_batches': list(failed_batches),
            'batch_summary': current_summary,
            'is_partial': bool(current_compounds) and bool(current_missing),
            'error': 'partial_batch_failure' if current_missing else None,
        }
        if callable(progress_callback):
            try:
                progress_callback(current_payload)
            except Exception as callback_ex:
                logging.warning(f"PubChem 增量缓存回调失败: {callback_ex}")

    compounds = _dedupe_compounds_by_cid(compounds)
    batch_summary = _build_batch_summary(ordered_cids, compounds, failed_batches, total_batches)
    missing_cids = batch_summary.get('missing_cids', [])
    synonym_gap = bool(synonym_fetch_failures) and any(cid not in synonym_map for cid in ordered_cids)
    is_partial = (bool(compounds) and bool(missing_cids)) or (bool(compounds) and synonym_gap)
    error_message = None
    if failed_batches and not compounds:
        error_message = failed_batches[0].get('reason', 'cid_property_fetch_failed')
    elif bool(compounds) and synonym_gap:
        error_message = 'partial_synonym_enrichment'
    elif bool(compounds) and bool(missing_cids):
        error_message = 'partial_batch_failure'

    logging.info(
        f"PubChem CID 属性拉取完成，目标 CID 数: {len(ordered_cids)}，返回记录数: {len(compounds)}，失败批次: {len(failed_batches)}"
    )
    return {
        'compounds': compounds,
        'failed_batches': failed_batches,
        'batch_summary': batch_summary,
        'is_partial': is_partial,
        'error': error_message,
    }


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
        property_batch_size: int = 100,
        property_batch_retries: int = 2,
        property_min_split_size: int = 1,
        allow_partial_results: bool = True,
    ):
        super().__init__(max_retries=max_retries, retry_delay=retry_delay)
        self.http_timeout = max(5, int(http_timeout))
        self.poll_interval = max(1, int(poll_interval))
        self.poll_max_attempts = max(1, int(poll_max_attempts))
        self.prefer_fastformula = bool(prefer_fastformula)
        self.property_batch_size = max(1, int(property_batch_size))
        self.property_batch_retries = max(1, int(property_batch_retries))
        self.property_min_split_size = max(1, int(property_min_split_size))
        self.allow_partial_results = bool(allow_partial_results)

    def get_compounds(self, formula: str):
        formula = _normalize_formula(formula)
        if not formula:
            logging.warning("PubChem 查询时遇到空化学式。")
            self._set_last_error('no_compounds', 'empty_formula')
            return None

        self._set_last_error('other', 'unknown')

        cached_payload = _load_latest_pubchem_raw_results(formula) or {}
        cached_compounds = cached_payload.get('raw_results', []) if isinstance(cached_payload, dict) else []
        cached_failed_batches = cached_payload.get('failed_batches', []) if isinstance(cached_payload, dict) else []
        cached_status = cached_payload.get('status', 'success') if isinstance(cached_payload, dict) else 'success'

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

                    cached_cid_set = set(_extract_cids_from_compounds(cached_compounds))
                    missing_cids = [cid for cid in cids if cid not in cached_cid_set]
                    total_batches = (len(cids) + self.property_batch_size - 1) // self.property_batch_size

                    if not missing_cids and cached_compounds:
                        summary = _build_batch_summary(cids, cached_compounds, cached_failed_batches, total_batches)
                        is_partial = bool(summary.get('missing_cids', [])) or cached_status == 'partial'
                        result_payload = {
                            'compounds': _dedupe_compounds_by_cid(cached_compounds),
                            'failed_batches': cached_failed_batches,
                            'batch_summary': summary,
                            'is_partial': is_partial,
                            'error': 'partial_cache_resume_pending' if is_partial else None,
                        }
                        if is_partial:
                            self._set_last_error('partial', result_payload['error'] or 'partial_cache_resume_pending')
                        else:
                            self._set_last_error('other', '')
                        return result_payload

                    def _progress_callback(fetch_payload: Dict[str, Any]):
                        if not BaseConfig.PUBCHEM_INCREMENTAL_CACHE_ENABLED:
                            return
                        merged_compounds = _dedupe_compounds_by_cid(cached_compounds + fetch_payload.get('compounds', []))
                        merged_summary = _build_batch_summary(
                            cids,
                            merged_compounds,
                            fetch_payload.get('failed_batches', []),
                            total_batches,
                        )
                        save_status = 'partial' if merged_summary.get('missing_cids', []) else 'success'
                        incremental_payload = {
                            'compounds': merged_compounds,
                            'failed_batches': fetch_payload.get('failed_batches', []),
                            'batch_summary': merged_summary,
                            'is_partial': save_status == 'partial',
                            'error': fetch_payload.get('error'),
                        }
                        _save_pubchem_raw_data(formula, incremental_payload, status=save_status)

                    fetch_result = _build_pubchem_compounds_from_cids(
                        missing_cids,
                        timeout=self.http_timeout,
                        chunk_size=self.property_batch_size,
                        per_batch_retries=self.property_batch_retries,
                        min_split_size=self.property_min_split_size,
                        progress_callback=_progress_callback,
                    )
                    merged_compounds = _dedupe_compounds_by_cid(cached_compounds + fetch_result.get('compounds', []))
                    merged_summary = _build_batch_summary(cids, merged_compounds, fetch_result.get('failed_batches', []), total_batches)
                    merged_missing = merged_summary.get('missing_cids', [])
                    result_payload = {
                        'compounds': merged_compounds,
                        'failed_batches': fetch_result.get('failed_batches', []),
                        'batch_summary': merged_summary,
                        'is_partial': bool(merged_compounds) and bool(merged_missing),
                        'error': fetch_result.get('error') or ('partial_batch_failure' if merged_missing else None),
                    }

                    if merged_compounds:
                        if result_payload['is_partial']:
                            self._set_last_error('partial', result_payload['error'] or 'partial_batch_failure')
                            if self.allow_partial_results:
                                return result_payload
                        else:
                            self._set_last_error('other', '')
                            return result_payload

                        last_rest_error = result_payload.get('error') or last_rest_error

                if pcp is not None:
                    compounds = pcp.get_compounds(formula, 'formula')
                    if compounds:
                        cids = _extract_cids_from_compounds(compounds)
                        enriched_payload = _build_pubchem_compounds_from_cids(
                            cids,
                            source_compounds=compounds,
                            timeout=self.http_timeout,
                            chunk_size=self.property_batch_size,
                            per_batch_retries=self.property_batch_retries,
                            min_split_size=self.property_min_split_size,
                        )
                        if enriched_payload.get('compounds'):
                            if enriched_payload.get('is_partial'):
                                self._set_last_error('partial', enriched_payload.get('error') or 'partial_batch_failure')
                            else:
                                self._set_last_error('other', '')
                            return enriched_payload
                        fallback_payload = {
                            'compounds': _dedupe_compounds_by_cid(compounds),
                            'failed_batches': [],
                            'batch_summary': _build_batch_summary(cids, compounds, [], len(cids)),
                            'is_partial': False,
                            'error': None,
                        }
                        self._set_last_error('other', '')
                        return fallback_payload

                if cached_compounds and self.allow_partial_results:
                    partial_summary = cached_payload.get('batch_summary') if isinstance(cached_payload.get('batch_summary'), dict) else {}
                    if not partial_summary:
                        partial_summary = _build_batch_summary(None, cached_compounds, cached_failed_batches, 0)
                    result_payload = {
                        'compounds': _dedupe_compounds_by_cid(cached_compounds),
                        'failed_batches': cached_failed_batches,
                        'batch_summary': partial_summary,
                        'is_partial': True,
                        'error': last_rest_error,
                    }
                    self._set_last_error('partial', last_rest_error)
                    return result_payload

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
            "partial": {},
            "failed": [],
            "failed_details": {},
            "failed_stats": {
                "timeout": 0,
                "no_compounds": 0,
                "poll_limit": 0,
                "other": 0,
            },
            "partial_stats": {
                "partial": 0,
            },
        }
        exporter = ExporterFactory.get_exporter(self.exporter_name)
        if exporter is None:
            raise ValueError(f"找不到导出器: {self.exporter_name}")

        for formula in formula_list:
            try:
                raw_cached_payload = None
                raw_cached_compounds: List[Any] = []
                raw_cache_status = 'success'
                raw_failed_batches: List[Dict[str, Any]] = []
                raw_batch_summary: Dict[str, Any] = {}

                if self.exporter_name == 'json_formulaSearch_PubChem':
                    raw_cached_payload = _load_latest_pubchem_raw_results(formula)
                    if raw_cached_payload:
                        raw_cached_compounds = raw_cached_payload.get('raw_results', []) if isinstance(raw_cached_payload, dict) else []
                        raw_cache_status = raw_cached_payload.get('status', 'success') if isinstance(raw_cached_payload, dict) else 'success'
                        raw_failed_batches = raw_cached_payload.get('failed_batches', []) if isinstance(raw_cached_payload, dict) else []
                        raw_batch_summary = raw_cached_payload.get('batch_summary', {}) if isinstance(raw_cached_payload, dict) else {}

                    if raw_cached_compounds and raw_cache_status == 'success' and not self.raw_only:
                        ranked_compounds = _rank_compounds(raw_cached_compounds, ion_mode=self.ion_mode, strict_filter=self.strict_filter)
                        export_data = exporter.export((formula, ranked_compounds))
                        results["success"][formula] = export_data
                        logging.info(f"分子式 {formula} 使用 PubChem 原始缓存重处理完成")
                        continue

                    if self.raw_only:
                        if raw_cached_compounds:
                            ranked_compounds = _rank_compounds(raw_cached_compounds, ion_mode=self.ion_mode, strict_filter=self.strict_filter)
                            export_data = exporter.export((formula, ranked_compounds))
                            results["success"][formula] = export_data
                            if raw_cache_status == 'partial':
                                results["partial"][formula] = {
                                    "category": "partial",
                                    "message": "partial_cache_rebuild",
                                    "batch_summary": raw_batch_summary,
                                    "failed_batches": raw_failed_batches,
                                }
                                results["failed_details"][formula] = results["partial"][formula]
                                results["partial_stats"]["partial"] += 1
                            logging.info(f"分子式 {formula} 在 raw_only 模式下重建完成，status={raw_cache_status}")
                            continue

                        logging.warning(f"分子式 {formula} 未命中 PubChem 原始缓存，raw_only 模式下跳过")
                        results["failed"].append(formula)
                        results["failed_details"][formula] = {
                            "category": "no_compounds",
                            "message": "raw_only_no_cache",
                        }
                        results["failed_stats"]["no_compounds"] += 1
                        continue

                search_payload = self.searcher.get_compounds(formula)
                payload_compounds = search_payload.get('compounds', []) if isinstance(search_payload, dict) else search_payload
                payload_is_partial = bool(search_payload.get('is_partial')) if isinstance(search_payload, dict) else False
                payload_failed_batches = search_payload.get('failed_batches', []) if isinstance(search_payload, dict) else []
                payload_batch_summary = search_payload.get('batch_summary', {}) if isinstance(search_payload, dict) else {}
                payload_error = search_payload.get('error') if isinstance(search_payload, dict) else None

                if payload_compounds:
                    save_status = 'partial' if payload_is_partial else 'success'
                    _save_pubchem_raw_data(
                        formula,
                        search_payload,
                        status=save_status,
                        batch_summary=payload_batch_summary,
                        failed_batches=payload_failed_batches,
                        error_message=payload_error,
                    )
                    ranked_compounds = _rank_compounds(payload_compounds, ion_mode=self.ion_mode, strict_filter=self.strict_filter)
                    export_data = exporter.export((formula, ranked_compounds))
                    results["success"][formula] = export_data

                    if payload_is_partial:
                        partial_detail = {
                            "category": "partial",
                            "message": payload_error or 'partial_batch_failure',
                            "batch_summary": payload_batch_summary,
                            "failed_batches": payload_failed_batches,
                        }
                        results["partial"][formula] = partial_detail
                        results["failed_details"][formula] = partial_detail
                        results["partial_stats"]["partial"] += 1
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
            property_batch_size=BaseConfig.PUBCHEM_PROPERTY_BATCH_SIZE,
            property_batch_retries=BaseConfig.PUBCHEM_PROPERTY_BATCH_RETRIES,
            property_min_split_size=BaseConfig.PUBCHEM_PROPERTY_MIN_CHUNK_SIZE,
            allow_partial_results=BaseConfig.PUBCHEM_ALLOW_PARTIAL_RESULTS,
        )
        exporter_name = 'json_formulaSearch_PubChem'
    else:
        raise ValueError(f"未知的 web_name: {web_name}")

    manager = SearchManager(searcher, exporter_name, ion_mode=ion_mode, raw_only=raw_only, strict_filter=strict_filter)
    return manager.search_formula_list(formula_list)
