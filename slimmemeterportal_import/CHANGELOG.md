# Changelog

## 32.2.2 - Knowledge Base cleanup/idempotentieherstel
- Maakt een QNAP PermissionError bij het verwijderen van een reeds geverifieerde tijdelijke KnowledgeBase-rehome niet-fataal.
- Een reeds volledig voltooide 32.2.1-migratie raakt een achtergebleven onleesbare rehome-map bij volgende startups niet meer aan.
- Upgrade de structuurstatus idempotent naar 32.2.2 en markeert cleanup als uitgesteld wanneer QNAP-eigenaarschap verwijdering blokkeert.
- Geen wijziging aan energieactuals, Excel-berekeningen, automatische maandafsluiting, finalize_month of releaseketen.
