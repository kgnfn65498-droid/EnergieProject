from copy import deepcopy


def _flatten(data, prefix=''):
    result = {}
    for key, value in (data or {}).items():
        path = f'{prefix}.{key}' if prefix else str(key)
        if isinstance(value, dict):
            result.update(_flatten(value, path))
        else:
            result[path] = value
    return result


def _assign(target, path, value):
    parts = path.split('.')
    node = target
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = deepcopy(value)


def resolve_truth(sources: list) -> dict:
    ordered = sorted(sources, key=lambda s: (s.get('priority', 999), s.get('name', '')))
    truth = {}
    provenance = {}
    chosen = {}
    conflicts = []

    flattened = [(source, _flatten(source.get('data', {}))) for source in ordered]
    all_paths = []
    seen = set()
    for _, values in flattened:
        for path in values:
            if path not in seen:
                seen.add(path)
                all_paths.append(path)

    for path in all_paths:
        candidates = []
        for source, values in flattened:
            if path in values and values[path] is not None:
                candidates.append((source, values[path]))
        if not candidates:
            continue
        winner_source, winner_value = candidates[0]
        _assign(truth, path, winner_value)
        provenance[path] = winner_source.get('name')
        chosen[path] = winner_value
        for source, value in candidates[1:]:
            if value != winner_value:
                conflicts.append({
                    'path': path,
                    'authoritative_source': winner_source.get('name'),
                    'authoritative_value': winner_value,
                    'conflicting_source': source.get('name'),
                    'conflicting_value': value,
                    'classification': 'LOWER_PRIORITY_STALE_OR_DRIFT',
                })
    return {'truth': truth, 'provenance': provenance, 'conflicts': conflicts}
