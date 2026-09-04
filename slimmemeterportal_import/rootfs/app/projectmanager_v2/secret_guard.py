import re

SENSITIVE_KEYS = {
    'password', 'passwd', 'token', 'access_token', 'refresh_token',
    'api_key', 'apikey', 'authorization', 'secret', 'client_secret',
}
SENSITIVE_TEXT_PATTERN = re.compile(
    r'(?i)\b(password|passwd|token|access_token|refresh_token|api[_-]?key|authorization|client_secret|secret)\b\s*[:=]\s*\S+'
)


def _sensitive(key) -> bool:
    return str(key).strip().lower() in SENSITIVE_KEYS


def contains_secret(value) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if _sensitive(key) and item not in (None, '', '[REDACTED]'):
                return True
            if contains_secret(item):
                return True
    elif isinstance(value, (list, tuple)):
        return any(contains_secret(item) for item in value)
    return False


def contains_secret_text(text: str) -> bool:
    return bool(SENSITIVE_TEXT_PATTERN.search(text or ''))


def redact(value):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            result[key] = '[REDACTED]' if _sensitive(key) else redact(item)
        return result
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    return value
