# Changelog

## 32.2.1 - Knowledge Base NAS-permissieherstel
- Herstelt de v32.2.0-startupmigratie wanneer de bestaande KnowledgeBase-map door een andere NAS/MCP-identiteit is aangemaakt.
- Rehomet die map fail-closed via de schrijfbare rapportroot en verifieert bestaande inhoud vóór en na kopie.
- Hervat veilig een gedeeltelijk uitgevoerde v32.2.0-migratie zonder de reeds verhuisde historische master opnieuw te genereren.
- Behoudt juli-actuals, PARTIEEL-regels en automatische maandafsluiting UIT.
