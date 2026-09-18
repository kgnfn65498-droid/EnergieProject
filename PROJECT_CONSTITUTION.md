# PROJECT_CONSTITUTION — EnergieProject

Status: bindend, permanent.

## Harde ontwikkelcontracten
- ChatGPT/Projectmanager houdt technische regie; Work is uitvoer/orchestratie; Codex alleen bij aantoonbare technische meerwaarde met exacte vraag, scope en stopcriterium.
- Peter is geen menselijke transportlaag tussen ChatGPT, Work, Codex, NAS en Projectmanager.
- TDD: RED → GREEN. Bestaande regressietests worden niet verwijderd of versoepeld om een build groen te krijgen.
- Een release is niet geaccepteerd op basis van unittests alleen. De autonome live end-to-end releaseketen moet GREEN sluiten.
- Geen productie-installatie, restart/recreate of andere beschermde productieactie zonder expliciete autorisatie.
- Terminalgebruik door Peter is uitzondering. Als het echt nodig is: vooraf waarom, stap X/Y, verwachte duur, maximale duur, exact terug te sturen resultaat en resterend werk.
- Canonieke releaseweg blijft ZIP → Incoming → watcher/installer → hold → atomic acceptance → CR → CLEARUP/HYGIENE → LIVE_PROVEN → DEVELOPMENT restore → COMPLETE.
- Geen GitHub-reconstructie of productieboom als vervangende buildbasis.
- Geen state fabriceren of handmatig hold/atomic/transition op GREEN zetten.
- CR-retentie EnergieProject=1 en NAS Containers=1; oude geldige sets alleen reversibel/quarantaine, niet als shortcut verwijderen.
- Nieuwe chats beginnen niet opnieuw met reeds bewezen onderzoek.

## Persistente informatielagen
Een nieuwe chat leest in deze volgorde:
1. PROJECT_CONSTITUTION.md
2. CURRENT_HANDOVER.md
3. WORK_LEDGER.md

Daarna uitsluitend aanvullende runtime-evidence die voor de eerstvolgende stap nodig is.
