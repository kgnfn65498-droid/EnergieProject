# Energieproject — noodherstel

Deze handleiding is uitsluitend voor een echte crash of vervanging van Home Assistant. Normaal dagelijks beheer verloopt automatisch.

1. Herstel Home Assistant met de normale Home Assistant back-up vanaf de externe QNAP-back-uplocatie.
2. Voeg de GitHub-repository `https://github.com/kgnfn65498-droid/EnergieProject` toe en installeer SlimmeMeterPortal Import.
3. Controleer bij **Instellingen > Systeem > Opslag** dat de QNAP-share met naam `Energie_NAS` gekoppeld is als type **Share**.
4. Start de app en download het diagnosepakket. GO + health 100% betekent dat de operationele keten hersteld is.
5. Ontbreken maand-/runtimegegevens, gebruik dan de nieuwste `EnergieProject_maandbackup_*.zip` uit `EnergieProject_Backups`.

API-sleutels staan bewust niet in projectback-ups. Die horen via de normale Home Assistant back-up/appconfiguratie terug te komen.

## v32 herstelvalidatie
Na herstel controleren: release-identiteit, MANIFEST.sha256, SHA256SUMS.json, Python compile, runtime-smoke en daarna een nieuwe Home Assistant Energieanalyse. Een herstel zonder deze controles geldt niet als gevalideerd herstel.
