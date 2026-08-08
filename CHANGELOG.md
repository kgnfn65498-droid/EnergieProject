# Changelog EnergieProject

## 10.5.3
- GitHub-publisher in Home Assistant hardened en volledig observeerbaar gemaakt.
- Startup logt nu expliciet of `github_publication_enabled` werkelijk is ingelezen.
- Publisherthread logt start, iedere controle, ontbrekende `processed`-release, publicatiepoging en resultaat.
- Fouten worden niet meer stil ingeslikt maar met traceback in het add-onlog geschreven.
- Laatste publisherresultaat wordt persistent opgeslagen in `github_publication_state.json`.
- HA-console ververst de GitHub-publicatiestatus automatisch bij openen en iedere 15 seconden.
- De statuskaart kan nu onderscheid maken tussen `Configureren`, `Wacht op GitHub` en `Automatisch`.
- Geen wijzigingen aan productiekern `9.4-core1`, maandworkflow of rapportgeneratoren.
