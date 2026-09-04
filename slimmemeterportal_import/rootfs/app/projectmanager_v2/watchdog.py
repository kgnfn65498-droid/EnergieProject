from energy_adapter import priority_for
from manager_core import classify_severity
from notification_router import notification_route


def evaluate(events):
    evaluated = []
    for event in events:
        severity, _ = classify_severity(event['type'])
        evaluated.append({**event, 'severity': severity, 'priority': priority_for(event['type']), 'route': notification_route(severity, event.get('peter_decision_needed', False))})
    return sorted(evaluated, key=lambda x: x['priority'])
