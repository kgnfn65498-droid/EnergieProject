import hashlib
import json

SCORE_KEYS = ('relevance', 'impact', 'urgency', 'actionability', 'confidence')
HARD_CATEGORIES = {'security', 'data_quality', 'contract_risk', 'deadline_risk'}


def _normalized_text(value):
    return ' '.join(str(value or '').strip().lower().split())


def _normalized_evidence(values):
    return sorted(set(str(item).strip() for item in (values or []) if str(item).strip()))


def _assessment(item):
    raw = item.get('assessment')
    if raw is None:
        return None, None
    if not isinstance(raw, dict):
        return None, 'assessment_not_dict'
    if set(raw.keys()) != set(SCORE_KEYS):
        return None, 'assessment_keys_invalid'
    normalized = {}
    for key in SCORE_KEYS:
        value = raw.get(key)
        if type(value) is not int or value < 0 or value > 2:
            return None, f'assessment_{key}_invalid'
        normalized[key] = value
    return normalized, None


def material_fingerprint(item: dict) -> str:
    assessment, _ = _assessment(item or {})
    raw_assessment = assessment if assessment is not None else (item or {}).get('assessment')
    payload = {
        'category': _normalized_text((item or {}).get('category')),
        'subject': _normalized_text((item or {}).get('subject')),
        'evidence': _normalized_evidence((item or {}).get('evidence')),
        'annual_saving_eur': (item or {}).get('annual_saving_eur'),
        'payback_years': (item or {}).get('payback_years'),
        'compatible': (item or {}).get('compatible'),
        'assessment': raw_assessment,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def evaluate_signal(item: dict) -> dict:
    item = item or {}
    fingerprint = material_fingerprint(item)
    assessment, error = _assessment(item)
    if error:
        return {
            'decision': 'REVIEW_REQUIRED',
            'total_score': None,
            'hard_gate': False,
            'reason': error,
            'material_fingerprint': fingerprint,
        }
    if assessment is None:
        return {
            'decision': 'WATCH',
            'total_score': None,
            'hard_gate': False,
            'reason': 'assessment_missing',
            'material_fingerprint': fingerprint,
        }

    total = sum(assessment.values())
    evidence = _normalized_evidence(item.get('evidence'))
    if not evidence:
        return {
            'decision': 'WATCH',
            'total_score': total,
            'hard_gate': False,
            'reason': 'evidence_missing',
            'material_fingerprint': fingerprint,
        }

    category = _normalized_text(item.get('category'))
    if category in HARD_CATEGORIES:
        hard_ok = assessment['urgency'] >= 1 and assessment['confidence'] >= 1
        return {
            'decision': 'PROMOTE' if hard_ok else 'WATCH',
            'total_score': total,
            'hard_gate': hard_ok,
            'reason': 'hard_gate_satisfied' if hard_ok else 'hard_gate_insufficient_urgency_or_confidence',
            'material_fingerprint': fingerprint,
        }

    if assessment['actionability'] <= 0:
        return {
            'decision': 'WATCH',
            'total_score': total,
            'hard_gate': False,
            'reason': 'not_actionable',
            'material_fingerprint': fingerprint,
        }
    if total >= 7:
        return {
            'decision': 'PROMOTE',
            'total_score': total,
            'hard_gate': False,
            'reason': 'score_threshold_met',
            'material_fingerprint': fingerprint,
        }
    return {
        'decision': 'WATCH',
        'total_score': total,
        'hard_gate': False,
        'reason': 'score_below_threshold',
        'material_fingerprint': fingerprint,
    }
