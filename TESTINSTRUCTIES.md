# Testinstructies v10.3.1

1. Download `EnergieProject_v10.3.1.zip` en zet de ZIP ongewijzigd in `AI Projecten/EnergieProject_Inbox/incoming`.
2. Start eenmalig de bestaande v10.3-installer vanuit Home Assistant Terminal & SSH met:

```bash
unzip -p /share/Energie_NAS/EnergieProject_Inbox/incoming/EnergieProject_v10.3.1.zip tools/release_installer.sh > /tmp/energie_release_installer.sh && chmod 700 /tmp/energie_release_installer.sh && sh /tmp/energie_release_installer.sh
```

3. Verwacht onderaan `SUCCES: 10.3.0 -> 10.3.1`, een GitHub-commit-hash en archivering naar `processed`.
4. Bij `FOUT:` niets handmatig herstellen; stuur alleen de volledige foutuitvoer. De installer hoort zelf de vorige worktree uit de tar-backup terug te zetten.
5. Controleer daarna:

```bash
cd /share/Energie_NAS/EnergieProject && git --no-pager status --short --branch && git --no-pager log -1 --oneline && git ls-remote origin refs/heads/main
```

De lokale HEAD en GitHub `main` moeten dezelfde hash hebben en `git status` mag geen wijzigingen tonen.
6. Update daarna de Home Assistant-app normaal naar 10.3.1, laat alleen de app herstarten en ververs de GUI. Geen rebuild tenzij Home Assistant aantoonbaar de oude image gebruikt.
7. Controleer bovenaan versie `10.3.1`. Geen automatische maandafsluitingstest nodig voor deze release.
