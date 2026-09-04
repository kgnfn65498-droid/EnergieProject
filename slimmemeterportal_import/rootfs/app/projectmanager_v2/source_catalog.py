OFFICIAL_SOURCES = (
    {
        'id': 'home_assistant_security',
        'category': 'security',
        'url': 'https://www.home-assistant.io/security',
        'keywords': ['security', 'advisory', 'critical', 'high', 'cve'],
        'cadence_hours': 24,
        'priority': 1,
    },
    {
        'id': 'home_assistant_alerts',
        'category': 'software',
        'url': 'https://alerts.home-assistant.io/',
        'keywords': ['home assistant', 'integration', 'disabled', 'shutdown', 'blocked'],
        'cadence_hours': 24,
        'priority': 2,
    },
    {
        'id': 'qnap_security',
        'category': 'security',
        'url': 'https://www.qnap.com/nl-nl/security-advisories',
        'keywords': ['critical', 'important', 'qts', 'container', 'cve'],
        'cadence_hours': 24,
        'priority': 1,
    },
    {
        'id': 'acm_energy_news',
        'category': 'regulation',
        'url': 'https://www.acm.nl/nl/nieuws',
        'keywords': ['energie', 'gas', 'elektriciteit', 'netbeheer', 'tarief', 'teruglever'],
        'cadence_hours': 24,
        'priority': 2,
    },
    {
        'id': 'rijksoverheid_saldering',
        'category': 'regulation',
        'url': 'https://www.rijksoverheid.nl/themas/klimaat-milieu-en-natuur/energie-thuis/salderingsregeling',
        'keywords': ['saldering', '2027', 'teruglever', 'vergoeding'],
        'cadence_hours': 24,
        'priority': 2,
    },
)


def sources_by_priority():
    return sorted(OFFICIAL_SOURCES, key=lambda item: (item['priority'], item['id']))
