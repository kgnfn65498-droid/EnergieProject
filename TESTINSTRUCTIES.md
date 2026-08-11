# Testinstructies v32.0.6 — NAS-layoutcorrectie

1. Plaats `EnergieProject_v32.0.6.zip` in `EnergieProject/Inbox/incoming` en wacht tot de release in `EnergieProject/Inbox/processed` staat.
2. Update SlimmeMeterPortal Import in Home Assistant en controleer dat versie `32.0.6` zichtbaar is.
3. Download **Analyse-export** en **release-diagnose**.
4. Controleer in de diagnose dat de NAS-layout `App`, `Data`, `Backups`, `Inbox` en `Infra` gebruikt.
5. Controleer dat release-inbox, watcherstatus en backupdoel geen oude losse EnergieProject-mappen meer noemen.
6. Controleer dat analyse-export `version = 32.0.6` meldt en dat bestaande financiële/rapportagegates ongewijzigd blijven.
7. Historische EPEX juli 2026 blijft gedeeltelijk beschikbaar t/m 2026-07-29; deze bekende brondekking mag niet als fout worden behandeld.
8. Er mag geen automatische aankoop, leverancierswissel of apparaatbesturing plaatsvinden.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.

9. Controleer in de release-diagnose dat de automatische HA→GitHub-publicatie `published=true` meldt, `local_head == remote_head` en `worktree=/config/github_publisher/worktree`.
10. Controleer dat `publisher_state.last_publication` niet opnieuw recursief een volgende `last_publication` bevat.
11. Controleer dat analyse-export `validation_marker = v32_0_6_runtime_identity` meldt.
