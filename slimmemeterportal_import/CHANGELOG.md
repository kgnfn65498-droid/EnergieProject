# Changelog

## 32.1.2 - Live NAS-resolutie Energiehistorie Excel
- Startup en maand-sidecar gebruiken de werkelijk gemounte NAS-root op uitvoermoment in plaats van de import-time fallback.
- Wacht veilig op de netwerkshare zonder lokale projectmappen als fallback aan te maken.
- Schrijft een bootstrap-statusbestand naast de historische master voor directe runtimecontrole.
- Houdt automatische maandafsluiting uitgeschakeld en wijzigt de bestaande maanddata niet.
