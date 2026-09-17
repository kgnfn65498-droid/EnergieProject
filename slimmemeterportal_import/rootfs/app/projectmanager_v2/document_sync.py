from pathlib import Path
import stat

from knowledge_sync import upsert_managed_section
from persistence import atomic_write_text
from secret_guard import contains_secret_text


class ManagedDocumentSync:
    def update(self, path, section_id: str, content: str, *, placement='end') -> dict:
        if contains_secret_text(content):
            raise ValueError('refusing to sync secret-like content')
        target = Path(path)
        try:
            st = target.lstat()
        except FileNotFoundError:
            st = None
        if st is not None and stat.S_ISLNK(st.st_mode):
            raise RuntimeError(f'document sync target is symlink: {target}')
        existing_mode = stat.S_IMODE(st.st_mode) if st is not None else None
        existing = target.read_text(encoding='utf-8') if st is not None else ''
        updated = upsert_managed_section(existing, section_id, content, placement=placement)
        changed = updated != existing
        if changed:
            atomic_write_text(target, updated, mode=existing_mode)
        return {'path': str(target), 'changed': changed, 'section_id': section_id, 'placement': placement}
