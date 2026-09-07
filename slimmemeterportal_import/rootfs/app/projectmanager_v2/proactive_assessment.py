from __future__ import annotations

SCORE_KEYS = ('relevance', 'impact', 'urgency', 'actionability', 'confidence')

_DEFAULT = {
    'security': (2, 2, 1, 1, 2),
    'data_quality': (2, 2, 1, 1, 2),
    'contract_risk': (2, 2, 1, 1, 2),
    'deadline_risk': (2, 2, 1, 1, 2),
    'regulation': (2, 2, 1, 1, 1),
    'end_of_life': (2, 2, 1, 1, 1),
    'software': (1, 1, 0, 0, 1),
    'market': (1, 1, 0, 0, 1),
    'conversation_opportunity': (1, 1, 0, 0, 1),
    'follow_up': (1, 1, 0, 0, 1),
}


def derive_assessment(category, *, evidence, annual_saving_eur=None, compatible=None, details=None) -> dict:
    normalized = str(category or '').strip().lower()
    has_evidence = bool([item for item in (evidence or []) if str(item).strip()])
    if normalized == 'saving':
        values = (2, 2, 1, 2, 2) if has_evidence and (annual_saving_eur or 0) > 0 else (1, 1, 0, 0, 1)
    else:
        values = _DEFAULT.get(normalized, (1, 1, 0, 0, 1))

    scores = dict(zip(SCORE_KEYS, values))
    if not has_evidence:
        scores['confidence'] = 0
        scores['actionability'] = 0
    if compatible is False:
        scores['actionability'] = 0
    return scores
