import re

KNOWLEDGE_EVENTS = {
    'release_installed', 'release_validated', 'workflow_completed', 'workflow_failed',
    'recovery_result_changed', 'mode_changed', 'validated_energy_source',
    'validated_financial_source', 'operational_fact',
}
ROADMAP_EVENTS = {'roadmap_task', 'approved_architecture_roadmap_item'}
BOTH_EVENTS = {'roadmap_decision', 'approved_design_principle'}


def classify_event(event: dict) -> str:
    event_type = event.get('type')
    if event_type in BOTH_EVENTS and event.get('approved', True):
        return 'both'
    if event_type in ROADMAP_EVENTS:
        return 'roadmap'
    if event_type in KNOWLEDGE_EVENTS:
        return 'knowledge_base'
    return 'none'


def _block(section_id: str, content: str):
    safe_id = re.sub(r'[^A-Z0-9_\-]', '_', section_id.upper())
    begin = f'<!-- PMV2:{safe_id}:BEGIN -->'
    end = f'<!-- PMV2:{safe_id}:END -->'
    return begin, end, f'{begin}\n{content.rstrip()}\n{end}'


def upsert_managed_section(existing: str, section_id: str, content: str, *, placement='end') -> str:
    begin, end, block = _block(section_id, content)
    pattern = re.compile(re.escape(begin) + r'.*?' + re.escape(end), flags=re.DOTALL)
    without = pattern.sub('', existing or '').strip()
    if placement == 'top':
        lines = without.splitlines()
        if lines and lines[0].startswith('# '):
            head = lines[0].rstrip()
            rest = '\n'.join(lines[1:]).strip()
            return f'{head}\n\n{block}\n\n{rest}\n' if rest else f'{head}\n\n{block}\n'
        return f'{block}\n\n{without}\n' if without else f'{block}\n'
    if placement != 'end':
        raise ValueError(f'unsupported managed-section placement: {placement}')
    return f'{without}\n\n{block}\n' if without else f'{block}\n'


def sync_plan(event: dict, *, kb_path: str, roadmap_path: str) -> list:
    classification = classify_event(event)
    targets = []
    if classification in {'knowledge_base', 'both'}:
        targets.append({'target': kb_path, 'kind': 'knowledge_base'})
    if classification in {'roadmap', 'both'}:
        targets.append({'target': roadmap_path, 'kind': 'roadmap'})
    return targets
