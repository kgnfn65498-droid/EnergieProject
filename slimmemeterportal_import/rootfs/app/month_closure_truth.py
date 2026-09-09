"""Compatibility import for the canonical Projectmanager month-closure predicate."""
from projectmanager_v2.month_closure_truth import (  # noqa: F401
    CLOSED_VALID,
    OPEN,
    UNKNOWN,
    classify_month_closure,
    closure_status_is_deep_verified,
)

__all__ = [
    'CLOSED_VALID',
    'OPEN',
    'UNKNOWN',
    'classify_month_closure',
    'closure_status_is_deep_verified',
]
