import json
import urllib.error
import urllib.request


class HomeAssistantNotifier:
    def __init__(self, base_url: str, token: str, *, service: str = None, opener=None, timeout: float = 10.0):
        self.base_url = (base_url or '').rstrip('/')
        self.token = token or ''
        self.service = service
        self.opener = opener or urllib.request.urlopen
        self.timeout = timeout

    def _request(self, path: str, *, payload=None):
        data = None if payload is None else json.dumps(payload).encode('utf-8')
        headers = {'Accept': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        if data is not None:
            headers['Content-Type'] = 'application/json'
        request = urllib.request.Request(self.base_url + path, data=data, headers=headers, method='POST' if data is not None else 'GET')
        with self.opener(request, timeout=self.timeout) as response:
            raw = response.read()
            return json.loads(raw.decode('utf-8')) if raw else None

    def discover_mobile_service(self):
        if self.service:
            return self.service.removeprefix('notify.')
        if not self.base_url or not self.token:
            return None
        try:
            services = self._request('/api/services') or []
        except Exception:
            return None
        candidates = []
        for domain in services:
            if domain.get('domain') != 'notify':
                continue
            for name in (domain.get('services') or {}):
                if name.startswith('mobile_app_'):
                    candidates.append(name)
        return candidates[0] if len(candidates) == 1 else None

    def send(self, title: str, message: str, *, severity: str, notification_id: str = 'energie_projectmanager') -> dict:
        if not self.base_url or not self.token:
            return {'ok': False, 'reason': 'missing_credentials'}
        mobile = self.discover_mobile_service()
        if mobile:
            path = f'/api/services/notify/{mobile}'
            payload = {'title': title, 'message': message, 'data': {'tag': notification_id, 'severity': severity}}
            transport = f'notify.{mobile}'
        else:
            path = '/api/services/persistent_notification/create'
            payload = {'title': title, 'message': message, 'notification_id': notification_id}
            transport = 'persistent_notification'
        try:
            response = self._request(path, payload=payload)
            return {'ok': True, 'transport': transport, 'response': response}
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            return {'ok': False, 'transport': transport, 'reason': 'request_failed', 'error': str(exc)}
