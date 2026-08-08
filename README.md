# EnergieProject v10.4.2 – Automatic Watcher Proof

v10.4.2 is de eerste release die bedoeld is om **zonder enig Terminal-commando** door de reeds draaiende v10.4.1 release-watcher te worden verwerkt.

## Doel van deze release
- ZIP uitsluitend plaatsen in `AI Projecten/EnergieProject_Inbox/incoming`.
- De watcher moet hem binnen circa 30 seconden zelf detecteren.
- Daarna moeten ZIP-validatie, SHA256-controle, repositorycontrole, herstelbackup, installatie, Git commit/push, GitHub-eindcontrole en verplaatsing naar `processed` automatisch verlopen.
- Geen functionele wijziging aan de release-installer of watcher zelf; hierdoor is v10.4.2 een zuivere end-to-end praktijktest van de in v10.4.1 geïnstalleerde automatisering.
- Home Assistant app-versie is 10.4.2, zodat na succesvolle verwerking ook de normale Home Assistant-updateknop kan worden gecontroleerd.
- Gecertificeerde productiekern blijft `9.4-core1`.

## Succescriterium
Zonder Terminalinvoer verschijnt v10.4.2 op GitHub `main`, verdwijnt de ZIP uit `incoming` en staat deze in `processed`.

Als dit stabiel is, wordt de verdere v10.x-roadmap in een nieuwe chat voortgezet met de actuele NAS/GitHub-basis en de afspraken uit `NEXT_CHAT_V7.md`.
