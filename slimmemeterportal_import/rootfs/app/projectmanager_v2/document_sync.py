from pathlib import Path

from knowledge_sync import upsert_managed_section
from persistence import atomic_write_text
from secret_guard import contains_secret_text


class ManagedDocumentSync:
    def update(self, path, section_id: str, content: str, *, placement='end') -> dict:
        if contains_secret_text(content):
            raise ValueError('refusing to sync secret-like content')
        target = Path(path)
        existing = target.read_text(encoding='utf-8') if target.exists() else ''
        updated = upsert_managed_section(existing, section_id, content, placement=placement)
        changed = updated != existing
        if changed:
            atomic_write_text(target, updated)
        return {'path': str(target), 'changed': changed, 'section_id': section_id, 'placement': placement}
