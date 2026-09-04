from dataclasses import dataclass
from typing import Optional

@dataclass
class Opportunity:
    category: str
    subject: str
    evidence: str
    annual_saving_eur: Optional[float] = None
    payback_years: Optional[float] = None
    compatible: Optional[bool] = None


def should_promote(item: Opportunity) -> bool:
    if not item.evidence:
        return False
    if item.compatible is False:
        return False
    return (item.annual_saving_eur or 0) > 0 or item.category in {'security','regulation','end_of_life'}
