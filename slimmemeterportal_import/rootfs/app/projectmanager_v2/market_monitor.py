import hashlib
import html
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from persistence import atomic_write_json, load_json

TAG_RE = re.compile(r'<[^>]+>')
SPACE_RE = re.compile(r'\s+')


def normalize_content(text: str) -> str:
    cleaned = TAG_RE.sub(' ', html.unescape(text or ''))
    return SPACE_RE.sub(' ', cleaned).strip().lower()


def default_fetcher(url: str) -> str:
    request = urllib.request.Request(url, headers={'User-Agent': 'EnergieProjectManager/2.0'})
    with urllib.request.urlopen(request, timeout=12) as response:
        return response.read(2_000_000).decode('utf-8', errors='replace')


def _valid_state(data):
    return isinstance(data, dict) and isinstance(data.get('sources', {}), dict)


class SourceMonitor:
    def __init__(self, state_path, *, fetcher=None):
        self.state_path = Path(state_path)
        self.fetcher = fetcher or default_fetcher

    def _load(self):
        return load_json(
            self.state_path,
            default={'schema': 1, 'sources': {}},
            recover_corrupt=True,
            validator=_valid_state,
        )

    def check(self, source: dict) -> dict:
        source_id = source['id']
        url = source['url']
        raw = self.fetcher(url)
        normalized = normalize_content(raw)
        digest = hashlib.sha256(normalized.encode('utf-8')).hexdigest()
        data = self._load()
        previous = data.setdefault('sources', {}).get(source_id)
        now = datetime.now(timezone.utc).isoformat()
        record = {
            'url': url,
            'sha256': digest,
            'checked_at': now,
            'keywords': list(source.get('keywords') or []),
        }
        data['sources'][source_id] = record
        atomic_write_json(self.state_path, data)
        if previous is None:
            return {
                'source_id': source_id,
                'state': 'BASELINED',
                'changed': False,
                'relevant': False,
                'sha256': digest,
                'evidence_ref': url,
            }
        changed = previous.get('sha256') != digest
        keywords = [str(word).lower() for word in source.get('keywords') or []]
        relevant = changed and (not keywords or any(word in normalized for word in keywords))
        return {
            'source_id': source_id,
            'state': 'CHANGED' if changed else 'UNCHANGED',
            'changed': changed,
            'relevant': relevant,
            'sha256': digest,
            'previous_sha256': previous.get('sha256'),
            'evidence_ref': url,
        }
