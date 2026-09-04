def notification_route(severity: str, peter_decision_needed: bool = False) -> str:
    if peter_decision_needed or severity == 'RED':
        return 'DIRECT'
    if severity == 'ORANGE':
        return 'NEXT_PROJECT_STATUS'
    return 'LOG_ONLY'


def notification_payload(subject: str, detail: str, severity: str) -> dict:
    return {'title': f'Energie PM — {severity}', 'message': f'{subject}: {detail}', 'severity': severity}
