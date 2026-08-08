# Testinstructies v10.3.0

1. Zet `EnergieProject_v10.3.0.zip` in `AI Projecten/EnergieProject_Inbox/incoming`.
2. Voer in Home Assistant Terminal & SSH vanaf de NAS-master één keer uit: `sh /share/Energie_NAS/EnergieProject/tools/release_installer.sh`. Voor deze eerste v10.3-overgang staat het script pas na handmatige plaatsing van de v10.3-worktree in de master; daarom mag v10.3 zelf nog via de bestaande Home Assistant update worden geïnstalleerd.
3. Update de Home Assistant-app normaal naar 10.3.0; alleen app-herstart + GUI verversen is nodig. Geen rebuild tenzij HA aantoonbaar de oude image gebruikt.
4. Controleer bovenaan versie 10.3.0 en download het diagnosepakket.
5. Geen automatische maandafsluitingstest nodig; productiekern blijft 9.4-core1.
6. Voor v10.4 testen we de echte inboxroute: ZIP in `incoming` -> validator -> backup -> Git commit/push -> `processed`.
