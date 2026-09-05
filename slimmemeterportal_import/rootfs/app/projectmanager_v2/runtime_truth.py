import re
from pathlib import Path

from reconciler import find_drift, reconciliation_action
from truth_engine import resolve_truth

PM_BEGIN = '<!-- PMV2:PROJECTMANAGER_V2:BEGIN -->'
PM_END = '<!-- PMV2:PROJECTMANAGER_V2:END -->'
CURRENT_WORDS = re.compile(r'(?i)\b(actueel|actuele|huidige|productie|runtime|statusoverride|basis/effectieve mode)\b')
VERSION_RE = re.compile(r'\bv?(\d+\.\d+\.\d+)\b')
MODE_RE = re.compile(r'\b(USER|DEVELOPMENT|MAINTENANCE)\b')


def _outside_managed(text: str) -> str:
    return re.sub(re.escape(PM_BEGIN) + r'.*?' + re.escape(PM_END), '', text or '', flags=re.S)


def _managed_block(text: str) -> str:
    match = re.search(re.escape(PM_BEGIN) + r'(.*?)' + re.escape(PM_END), text or '', flags=re.S)
    return match.group(1) if match else ''


def _managed_is_top(text: str) -> bool:
    value = text or ''
    start = value.find(PM_BEGIN)
    if start < 0:
        return False
    prefix = value[:start].strip().splitlines()
    # Allow only the document H1 before the authoritative PM block.
    return len(prefix) <= 1 and (not prefix or prefix[0].startswith('# '))


def extract_current_claims(text: str) -> dict:
    claims = {'release': None, 'mode': None, 'stale_lines': []}
    for line in _outside_managed(text).splitlines():
        if not CURRENT_WORDS.search(line):
            continue
        versions = VERSION_RE.findall(line)
        modes = MODE_RE.findall(line)
        if claims['release'] is None and versions:
            claims['release'] = versions[0]
        if claims['mode'] is None and modes:
            claims['mode'] = modes[0]
        if versions or modes:
            claims['stale_lines'].append(line[:300])
    return claims


def evaluate_runtime_first(paths, *, release: str, mode: str, health: str) -> dict:
    runtime = {'release': release, 'mode': mode, 'health': health}
    document_claims = []
    stale = []
    superseded = []
    unresolved = []
    for raw_path in paths:
        path = Path(raw_path)
        try:
            text = path.read_text(encoding='utf-8')
        except OSError:
            continue
        extracted = extract_current_claims(text)
        data = {key: extracted.get(key) for key in ('release', 'mode') if extracted.get(key) is not None}
        document_claims.append({'path': str(path), 'data': data})
        managed = _managed_block(text)
        authoritative = (
            _managed_is_top(text)
            and release in managed
            and mode in managed
            and 'runtime' in managed.lower()
        )
        for line in extracted.get('stale_lines', []):
            versions = VERSION_RE.findall(line)
            modes = MODE_RE.findall(line)
            mismatch = (
                (versions and release and any(value != release for value in versions))
                or (modes and mode and any(value != mode for value in modes))
            )
            if mismatch:
                finding = {'path': str(path), 'line': line}
                stale.append(finding)
                if authoritative:
                    superseded.append(finding)
                else:
                    unresolved.append(finding)

    sources = [{'name': 'runtime', 'priority': 1, 'data': runtime}]
    for index, item in enumerate(document_claims):
        sources.append({'name': f'document:{index}', 'priority': 100 + index, 'data': item['data']})
    truth = resolve_truth(sources)
    documented = {}
    for item in document_claims:
        for key, value in item['data'].items():
            documented.setdefault(key, value)
    drift = [item.__dict__ for item in find_drift(runtime, documented)]
    action = reconciliation_action(certain=True, safe=True)
    return {
        'runtime': runtime,
        'truth': truth.get('truth', {}),
        'provenance': truth.get('provenance', {}),
        'conflicts': truth.get('conflicts', []),
        'drift': drift,
        'stale_current_claims': stale,
        'superseded_stale_current_claims': superseded,
        'unresolved_stale_current_claims': unresolved,
        'action': action,
        'strategy': 'runtime_first_managed_block_at_document_top_preserve_historical_text',
    }
