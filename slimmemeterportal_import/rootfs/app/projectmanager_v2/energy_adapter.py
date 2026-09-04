ENERGY_DOMAINS = (
    'month_workflow', 'crash_recovery', 'reporting', 'nextenergy',
    'homewizard', 'enphase', 'slimmemeterportal', 'epex', 'quarter_hour_data'
)

PRIORITY = {
    'incident': 1,
    'data_loss': 1,
    'security': 1,
    'active_development': 2,
    'active_maintenance': 2,
    'month_workflow': 3,
    'roadmap': 4,
    'opportunity': 5,
}


def priority_for(kind: str) -> int:
    return PRIORITY.get(kind, 5)


def supports(domain: str) -> bool:
    return domain in ENERGY_DOMAINS
