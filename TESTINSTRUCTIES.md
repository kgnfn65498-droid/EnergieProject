# Testinstructies v32.0.3 — NAS-layoutcorrectie

1. Plaats `EnergieProject_v32.0.3.zip` in `EnergieProject/Inbox/incoming` en wacht tot de release in `EnergieProject/Inbox/processed` staat.
2. Update SlimmeMeterPortal Import in Home Assistant en controleer dat versie `32.0.3` zichtbaar is.
3. Download **Analyse-export** en **release-diagnose**.
4. Controleer in de diagnose dat de NAS-layout `App`, `Data`, `Backups`, `Inbox` en `Infra` gebruikt.
5. Controleer dat release-inbox, watcherstatus en backupdoel geen oude losse EnergieProject-mappen meer noemen.
6. Controleer dat analyse-export `version = 32.0.3` meldt en dat bestaande financiële/rapportagegates ongewijzigd blijven.
7. Historische EPEX juli 2026 blijft gedeeltelijk beschikbaar t/m 2026-07-29; deze bekende brondekking mag niet als fout worden behandeld.
8. Er mag geen automatische aankoop, leverancierswissel of apparaatbesturing plaatsvinden.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
