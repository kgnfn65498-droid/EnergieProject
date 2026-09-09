from __future__ import annotations

import hmac
from typing import Any, Mapping

CLIENT_SOURCE_CHANNELS = {
    'chatgpt': 'chatgpt',
    'voice': 'voice',
    'nomad': 'nomad',
}


def _header(headers: Mapping[str, Any], name: str) -> str:
    value = headers.get(name, '') if hasattr(headers, 'get') else ''
    return str(value or '').strip()


def authenticate_external_pm_request(headers: Mapping[str, Any], environ: Mapping[str, Any]) -> dict[str, str]:
    """Authenticate only the dedicated edge-protected external PM route.

    The edge must strip inbound identity headers and inject these values only
    after its own OAuth/OIDC/JWT policy succeeds. The shared edge secret is an
    additional server-side trust binding and is never accepted from payload data.
    """
    configured_secret = str(environ.get('PM_EXTERNAL_INGRESS_SECRET') or '')
    if len(configured_secret) < 32:
        raise PermissionError('external PM ingress is not configured')

    supplied_secret = _header(headers, 'X-Energie-Edge-Secret')
    if not supplied_secret or not hmac.compare_digest(supplied_secret, configured_secret):
        raise PermissionError('external PM ingress credentials rejected')

    allowed_principal = str(environ.get('PM_EXTERNAL_ALLOWED_PRINCIPAL') or 'Peter').strip()
    principal = _header(headers, 'X-Energie-Principal')
    if not principal or not hmac.compare_digest(principal, allowed_principal):
        raise PermissionError('external PM ingress principal rejected')

    client = _header(headers, 'X-Energie-Client').lower()
    source_channel = CLIENT_SOURCE_CHANNELS.get(client)
    if source_channel is None:
        raise PermissionError('external PM ingress client rejected')

    return {
        'principal': principal,
        'client': client,
        'source_channel': source_channel,
    }


def parse_external_pm_payload(payload: Any, authenticated: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError('JSON body must be an object')
    allowed = {'query', 'text', 'session_id', 'turn_id', 'transcript_id', 'transcript_confidence'}
    unsupported = sorted(set(payload) - allowed)
    if unsupported:
        raise ValueError('unsupported external projectmanager payload fields: ' + ', '.join(unsupported))

    query = payload.get('query') if payload.get('query') is not None else payload.get('text')
    if not isinstance(query, str) or not query.strip():
        raise ValueError('query is required')

    result: dict[str, Any] = {
        'query': query.strip(),
        'source_channel': str(authenticated.get('source_channel') or ''),
        'principal': str(authenticated.get('principal') or ''),
        'client': str(authenticated.get('client') or ''),
    }
    if result['source_channel'] not in CLIENT_SOURCE_CHANNELS.values() or not result['principal']:
        raise PermissionError('authenticated external PM identity is incomplete')

    for field_name in ('session_id', 'turn_id', 'transcript_id'):
        value = payload.get(field_name)
        if value is not None and not isinstance(value, str):
            raise ValueError(f'{field_name} must be a string')
        result[field_name] = value

    confidence = payload.get('transcript_confidence')
    if confidence not in (None, ''):
        try:
            confidence = float(confidence)
        except (TypeError, ValueError) as exc:
            raise ValueError('transcript_confidence must be a number') from exc
        if not 0.0 <= confidence <= 1.0:
            raise ValueError('transcript_confidence must be between 0 and 1')
    else:
        confidence = None
    result['transcript_confidence'] = confidence
    return result
