from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class IncomingItem:
    name: str
    size: int
    mtime_ns: int
    sha256: str | None = None
    integral: bool | None = None

@dataclass(frozen=True)
class IngressDecision:
    status: str
    reason: str
    selected: str | None = None

def decide_incoming(items: list[IncomingItem], previous_sample: dict[str, tuple[int,int]], *, stable_polls: int = 2) -> IngressDecision:
    if not items:
        return IngressDecision('WAITING','empty')
    if len(items) > 1:
        hashes=[x.sha256 for x in items if x.sha256]
        if len(hashes) == len(items) and len(set(hashes)) == 1 and all(x.integral is True for x in items):
            return IngressDecision('DEDUPLICATE','identical_duplicates',selected=sorted(x.name for x in items)[0])
        return IngressDecision('BLOCKED','multiple_distinct_incoming')
    item=items[0]
    sample=previous_sample.get(item.name)
    if sample != (item.size,item.mtime_ns):
        return IngressDecision('WAITING','copy_not_stable')
    if item.integral is not True:
        return IngressDecision('WAITING','zip_not_integral')
    return IngressDecision('READY','single_stable_integral',selected=item.name)
