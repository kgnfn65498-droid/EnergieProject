## v32.3.3 — Assistant runtime mount-timing hotfix

- Herstelt uitsluitend de startup-timing van het v32.3.2 assistant acceptance-resultaat: het doelpad wordt niet meer bij module-import vastgezet.
- De self-probe wacht nu fail-closed op de werkelijk bestaande QNAP-projectmount via `wait_for_existing_nas_roots()` en bepaalt daarna pas `Data/03_Systeem/Projectmanager/State/assistant_runtime_acceptance.json`.
- Bij ontbrekende NAS-mount wordt geen fallbackprojectstructuur aangemaakt en blijft de Voice-gate gesloten.
- Assistant endpoints, energielogica, augustusstatus, NextEnergy-model, maandafsluiting, MCP-rechten en system-pad guard zijn inhoudelijk ongewijzigd.

## v32.3.2 — Assistant runtime observability

- Voegt één fixed-target, read-only assistant runtime self-probe toe die uitsluitend via loopback `127.0.0.1:8099` de bestaande `/api/assistant/health` en `/api/assistant/context` contracten controleert.
- Probe valideert release-identiteit, augustus 2026 als PARTIAL met Home Assistant-kwartierprovenance, sessie-follow-up naar juli 2026, NextEnergy contractmodel zonder factuuractual en Knowledge Base-bronvermelding voor apparatuur.
- Negatieve runtimechecks bevestigen dat een onbekende assistant-route 404 geeft en dat extra actie-/writevelden in assistant-context met 400 worden geweigerd.
- Assistant requestgrootte is begrensd op 32 KiB; probe-antwoorden op 256 KiB; timeout maximaal 5 seconden. De probe accepteert geen willekeurige host, URL, route of methode.
- Resultaat wordt na add-on-start atomisch vastgelegd in `Data/03_Systeem/Projectmanager/State/assistant_runtime_acceptance.json`; bij iedere fout blijft de Voice-gate gesloten.
- Geen wijziging aan energieactuals, maandafsluiting, `finalize_month`, NextEnergy-berekeningen, MCP-rechten of bestaande system-pad guard. Voice/Assist wordt door deze release niet automatisch geactiveerd.

## v32.3.1 — Kwartierdata, NextEnergy-contractmodel en gesprekspartner + MCP system-pad guard hotfix

- Herstelt de structurele foutklasse waarbij `write_system_text_file` en `create_system_directory` een relatief pad dat al met `Data/03_Systeem` begon opnieuw onder de system-root konden plaatsen.
- Nieuwe watcher-hotfix patcht `Infra/Docker/native-mcp/tools_filesystem.py` alleen wanneer de verwachte `_system_path`-bronvorm exact één keer aanwezig is, compileert de nieuwe bron vóór atomische vervanging en bewaart de pre-patchbron onder `Backups/MCPHotfix/v32.3.1/`.
- De runtime-guard weigert zowel `Data/03_Systeem/...`, `./Data/03_Systeem/...` als backslashvarianten; normale relatieve paden zoals `Projectmanager/Runs/...` blijven toegestaan.
- Dezelfde onderhoudsactie verwijdert uitsluitend de bekende 3.278-byte v32.3.0-acceptatiekopie wanneer pad, JSON-identiteit, release-SHA en grootte exact overeenkomen; daarna worden alleen de lege bekende dubbele parentmappen verwijderd.
- Onbekende inhoud, extra bestanden, symlinks of afwijkende broncode blokkeren de cleanup fail-closed.
- Na bronpatch is één herstart van `energie-filesystem-mcp` nodig zodat het Python-proces de nieuwe guard inlaadt.
- Geen wijziging aan energieactuals, NextEnergy-formules, gesprekspartnerlogica, automatische maandafsluiting of `finalize_month`.

## v32.3.0 — Kwartierdata, NextEnergy-contractmodel en gesprekspartner

- Gebouwd vanaf de door de gebruiker aangeleverde en manifest-identieke live v32.2.2-basis.
- Lopende maand gebruikt gevalideerde Home Assistant-kwartierdata primair; cumulatieve metergrenzen bepalen import, export en gas en de rapportage toont de werkelijke PARTIËLE dekking.
- Officiële NextEnergy-contractcomponenten per 16-07-2026 zijn gemodelleerd zonder factuuractuals te verzinnen; de live stroomprijs wordt niet dubbel belast met opslag/energiebelasting.
- Zonnebonus volgt de officiële 50%-regel, alleen 06:00–22:00, alleen bij positieve beursprijs, alleen bij bevestigde zonne-export en met 6.000-kWh-contractjaarcap.
- Nieuwe read-only gesprekspartnerbackend met sessiecontext, bronroutering, PARTIEEL/VOLLEDIG-kwaliteit en maximaal drie evidence-backed observaties.
- Nieuwe HTTP-contracten: `GET /api/assistant/health` en `POST /api/assistant/context`.
- Home Assistant Voice/Assist blijft een vervolgstap na echte liveacceptatie van deze backend.
- Geen structurele padwijziging, geen automatische maandafsluiting en geen `finalize_month` voor augustus.

## v32.2.2 — Knowledge Base cleanup/idempotentieherstel

- Herstelt de laatste live 32.2.1-naloopfout: QNAP kan de oude `.KnowledgeBase_v32.2_rehome` door eigenaarschap/ACL niet verwijderen.
- Cleanup na een al geverifieerde migratie is nu best-effort en kan de startup niet meer rood maken.
- Een volgende startup na een voltooide migratie valideert de canonieke doelen en raakt een achtergebleven onleesbare rehome-map niet meer aan.
- Bestaande pre-migratiebackup blijft herstelbewijs; geen data wordt opnieuw gegenereerd.
- Geen wijziging aan energieactuals, Excel-berekeningen, automatische maandafsluiting, `finalize_month`, watcherketen of rapportkern.

## v32.2.1 — Knowledge Base NAS-permissieherstel

- Herstelt de live v32.2.0-startupfout waarbij een reeds via de NAS/MCP aangemaakte `KnowledgeBase/` niet atomair beschrijfbaar was door de Home Assistant-runtime.
- Detecteert de schrijfbaarheid met een echte create/atomic-replace probe in plaats van alleen POSIX-modusbits.
- Rehomet een niet-schrijfbare bestaande KnowledgeBase veilig via de schrijfbare rapportroot, kopieert alle bestaande bestanden met SHA-256-verificatie terug en verwijdert de tijdelijke rehome-map pas na volledig geslaagde migratiestatus.
- Kan de exact half-uitgevoerde v32.2.0-toestand hervatten: reeds verhuisde history-bestanden blijven behouden; Roadmap, apparatuurindex, mobiele-socketlog en juli-archief worden daarna alsnog verplaatst.
- De bestaande `Backups/StructureMigration_v32.2/pre_migration/manifest.json` blijft herstelbewijs en wordt gevalideerd en hergebruikt.
- Geen wijziging aan energieactuals, Excel-berekeningen, automatische maandafsluiting, `finalize_month`, watcherketen of rapportkern.

## v32.2.0 — Knowledge Base

- Centraliseert actieve Knowledge Base, Roadmap, apparatuurindex en mobiele-socketlog onder `Data/02_Output/Rapportages/KnowledgeBase/`.
- Verplaatst de historische energie-master, bronindex, ontwerp, bootstrapstatus en maandarchieven naar `Data/02_Output/Rapportages/Verbruikshistorie/`.
- Gebruikt één centrale padmodule voor alle nieuwe historische write-paths.
- Voert de Data-migratie idempotent en fail-closed uit: vóór mutatie ontstaat een geverifieerde pre-migratiebackup; ieder bestand wordt na kopiëren met SHA-256 gecontroleerd; conflicterende oude/nieuwe inhoud wordt nooit overschreven.
- De bestaande `Energie_verbruik_historie.xlsx` wordt bij de verhuizing niet opnieuw berekend; byte-identieke inhoud blijft behouden.
- Startup en maandelijkse Excel-sidecar voeren de structuurcontrole uit vóór bootstrap/publicatie zodat geen oud pad opnieuw wordt aangemaakt.
- API-testbestanden en overige rapportroot-cleanup vallen bewust buiten deze release.
- Juli 2026-actuals, PARTIEEL-regels, automatische maandafsluiting UIT, `finalize_month`-verbod, production core en releaseketen blijven inhoudelijk ongewijzigd.

## v32.1.3 — SMP maandtotalen uit meterstandgrenzen

- Herstelt de historische Excel-bootstrap die op juli 2026 stopte met `Volledige historische actual wijkt af`.
- Berekent SMP-maandtotalen primair uit cumulatieve begin/eind-meterstanden in plaats van de op 0,01 afgeronde kwartier-/uurverbruiken op te tellen.
- Eerste intervalwaarde reconstrueert de exacte beginmeterstand wanneer de eerste registratie na 00:00 valt.
- Valt alleen terug op som van intervalwaarden wanneer bruikbare cumulatieve meterstanden ontbreken.
- Behoudt de bestaande conflictbeveiliging: echte afwijkingen tussen twee volledige historische actuals blijven geblokkeerd.
- Automatische maandafsluiting blijft UIT; `finalize_month` wordt niet gebruikt.

## v32.1.2 — live NAS-resolutie voor Energiehistorie Excel

- Oorzaak opgelost: de HA-app kon bij module-import een nog niet gemounte `/share` zien en daarna een lokale fallback blijven gebruiken, waardoor de Excel niet in het echte QNAP-project verscheen.
- Startup-bootstrap resolveert en wacht nu opnieuw op een aantoonbaar bestaand EnergieProject op de HA-netwerkshare; de fallback wordt nooit gebruikt voor Excel-schrijfacties.
- De maandelijkse Excel-sidecar resolveert eveneens de live NAS-root vlak vóór publicatie.
- Na startup wordt `Data/02_Output/Rapportages/Energie_verbruik_historie_bootstrap_status.json` op de NAS geschreven voor controleerbaar bewijs.
- Geen maandafsluiting; augustus blijft PARTIEEL; watcher-retenties blijven 999/999.

## v32.1.1 — maandelijkse Energiehistorie Excel startup-bootstrap

- Herstelt de ontbrekende eerste publicatie van `Energie_verbruik_historie.xlsx` na installatie van v32.1.0.
- Bij app-start wordt, alleen wanneer nodig, de nieuwste volledig gevalideerde maand gekozen en de master automatisch opgebouwd zonder een maandworkflow te starten.
- Als de master al geldig is maar het laatste maandarchief ontbreekt, wordt alleen dat archief opgebouwd; de bestaande master blijft intact.
- De bootstrap is idempotent en blijft een niet-destructieve sidecar: fouten blokkeren de app of maandworkflow niet.
- Automatische maandafsluiting blijft UIT; `finalize_month` wordt niet aangeroepen; watcher-retenties en normale Incoming → NAS → GitHub → HA-keten blijven ongewijzigd.

## v32.1.0 — maandelijkse Energiehistorie Excel

- Maakt `Energie_verbruik_historie.xlsx` een niet-destructieve sidecar na een geslaagde maandworkflow; een Excel-fout maakt de maandworkflow zelf niet ongeldig.
- Bouwt iedere run vanuit een schoon workbook; geen patch/re-export-keten, macro’s, PowerQuery of werkbladformules.
- Kalenderjaar is primair voor dashboards en jaar-op-jaarvergelijkingen; contract-/afrekenjaren blijven apart.
- Herbouwt uit de historische seed plus alle volledig gevalideerde projectmaanden t/m de doelmaand, zodat eerdere nieuwe maanden bij volgende runs behouden blijven.
- Volledige maand: atomische masterpublicatie plus byte-identiek maandarchief `Archief/Energie_verbruik_historie_YYYY_MM.xlsx`.
- Lopende/onvolledige maand blijft PARTIEEL en krijgt geen bevroren maandarchief.
- Regressiebeveiliging tegen 2008-datumverschuiving, corrupte Excel-reparatiemelding, overlap/dubbeltelling en overschrijven van een geldige master bij buildfout.
- Automatische maandafsluiting blijft UIT; `finalize_month` wordt niet gebruikt. Watcher-retenties blijven 999/999 en de bewezen NAS -> GitHub -> Home Assistant-keten blijft behouden.

## v32.0.38 — automatische publicatieketen end-to-end validatie

- Onderhoudsrelease zonder functionele wijziging aan energie-, import-, rapport- of financiële logica.
- Valideert de standaardketen Incoming -> watcher -> NAS -> publication-contract -> GitHub -> Home Assistant.
- Behoudt dedicated Git-worktree, remote-baselinecontrole en verbod op force-push.
- Behoudt watcher-retenties 999/999.
- Automatische maandafsluiting blijft UIT; augustus 2026 blijft open.

## v32.0.37 — veilige standaard GitHub-publicatie

- Herstelt de latente v32.0.36-installerfout waarbij `LOGDIR` werd gebruikt zonder definitie; toekomstige releases definiëren `LOGDIR="$INBOX/logs"` expliciet.
- Home Assistant resolveert de actuele projectshare dynamisch; `Project Energie` en `Project_Energie` zijn primair, `Energie_NAS` blijft compatibiliteitsfallback.
- De bestaande dedicated Git-worktree onder `/config/github_publisher/worktree` blijft de enige Git-publicatieworktree; live `App` krijgt geen `.git`.
- Iedere ZIP-only QNAP-release schrijft pas na canonieke `processed`-archivering een publicatiecontract met vorige/nieuwe manifesthash en processed-ZIP SHA256.
- GitHub-publicatie blokkeert bij een onverwachte versie of manifest op `main`; force-push, automatische rebase en conflictoverschrijving zijn niet toegestaan.
- Na push moet lokale HEAD exact gelijk zijn aan remote HEAD; alleen dan wordt het publicatiecontract opgeruimd.
- GitHub-publicatie staat voor nieuwe/herstelde HA-installaties standaard aan.
- Geen wijziging aan energie-, rapport-, import- of financiële logica.
- Automatische maandafsluiting blijft UIT; augustus 2026 wordt niet afgesloten.

## v32.0.36 — Crash-recovery backuprechten en watcher-retentie

- QNAP `Backups` wordt bij normale release-installatie blijvend als gedeelde beheermap (`2775`) ingesteld.
- Nieuwe pre-release backups krijgen groep `everyone` en modus `660`, zodat ze via Finder/SMB verwijderbaar blijven.
- De watcher-bootstrap legt `ENERGIE_BACKUP_RETENTION=999` en `ENERGIE_PROCESSED_RETENTION=999` expliciet vast.
- NAS-container crash-recovery blijft Finder/SMB-beheerbaar met ZIP/SHA/VERIFY op `660`.
- Home Assistant app-identiteit is gesynchroniseerd op v32.0.36.
- Geen wijziging aan energie-, rapport-, import- of financiële logica.
- Automatische maandafsluiting blijft UIT; augustus 2026 wordt niet afgesloten.

## v32.0.35 — Pagina 2 onbekende terugleververgoeding

- Herstelt de historische pagina-2-generator wanneer `feed_in_compensation` niet gevalideerd beschikbaar is en daarom `None` is.
- De generator probeert niet langer `-None` te berekenen; onbekende terugleververgoeding blijft expliciet niet beschikbaar in plaats van als €0 te worden ingevuld.
- Numerieke terugleververgoeding behoudt de bestaande negatieve presentatie in het kostenoverzicht.
- Geen wijziging aan SlimmeMeterPortal-fallback, juli-brondata, automatische maandafsluiting, Crash Recovery, NextEnergy of `finalize_month`.

## v32.0.34 — SMP analyse/rapport-fallback

- Gebruikt volledige SlimmeMeterPortal-maanddekking als expliciete fallback voor netafname, teruglevering en gas wanneer historische P1/P1g-detaildata ontbreekt of ongeldig is.
- P1/P1g blijft per metriek leidend wanneer die bron geldig is; SMP wordt nooit bij P1 opgeteld, zodat dubbeltelling is uitgesloten.
- Analyse en officiële rapportadapter gebruiken dezelfde bronselectie en leggen de gekozen bron per metriek vast.
- Historische rapport-readiness accepteert complete SMP-kernmetriek zonder oude HomeWizard/socket/Enphase-detailbestanden verplicht te maken.
- Succesvolle rapportage publiceert atomair naar `Data/02_Output/Rapportages/YYYY_MM`; voor de huidige reparatie is het doel `Rapportages/2026_07`.
- Nieuwe gerichte actie `Herbouw historisch rapport` herstelt alleen analyse/rapport-output voor een bestaande maand en start geen 11-stappen-maandworkflow.
- Geen wijziging aan augustus 2026, automatische maandafsluiting, Crash Recovery, NextEnergy-contractlogica of `finalize_month`.

## v32.0.33 — Juli ingress/fallback

- Maakt de vaste `Data/01_Input/YYYY_MM/HomeAssistant`-ingress veilig zelf aan wanneer die bij een historische maand nog ontbreekt.
- SlimmeMeterPortal kan daardoor de volledige meterdata publiceren voor juli 2026, ook wanneer lokale P1/HomeWizard-historie pas halverwege juli beschikbaar kwam.
- De bestaande `HomeAssistant/SlimmeMeterPortal`-structuur, staging/checksum/swap-publicatie en idempotency/completion-marker blijven intact.
- Onbruikbare of onbeschrijfbare NAS-ingress blijft fail-closed.
- Geen wijziging aan augustus 2026, Crash Recovery, watcher-cleanup, GitHub-publicatie of `finalize_month`.

## v32.0.32 — Crash Recovery watcher-cleanup

- Verplaatst NAS-cleanup na een volledige Crash-Recovery-download van de Home Assistant-container naar de bestaande QNAP/Docker-watcher.
- Home Assistant verwijdert alleen de lokale browserexport en schrijft daarna één strikt cleanup-verzoek met de exacte complete-backupnaam, het daarvan afgeleide manifest en één concrete RestoreStaging-run.
- Nieuwe `tools/crash_recovery_cleanup.py` valideert alle paden opnieuw in de watchercontext; maandbackups, `FULL_RECOVERY*.tar.gz`, release-ZIP's en willekeurige paden zijn verboden.
- Cleanup is idempotent: reeds verdwenen exacte runartefacten gelden als veilig afgehandeld.
- Een gedownloade v32.0.31 Crash Recovery met cleanup-warning wordt zonder nieuwe backup/export automatisch opnieuw aan de watcher aangeboden.
- De backend blijft GUI-onafhankelijk zodat dezelfde Crash-Recovery-keten later via een spraakopdracht kan worden gestart.
- Geen wijziging aan maandafsluiting, juli-status, `finalize_month`, backupretentie of automatische iCloud-upload.

## v32.0.31 — Crash Recovery live-snapshot

- Vervangt pad-specifieke heartbeat-uitzonderingen door een structurele live-snapshot per projectbestand.
- Scheduler- en watcher-heartbeats mogen na hun stabiele snapshot normaal doorlopen; de export faalt niet meer op hun latere mtime-wijziging.
- Een bestand dat tijdens het daadwerkelijke lezen verandert blijft hard afgekeurd; de volledige ZIP-build wordt maximaal drie keer veilig herstart.
- Bestandsset wordt voor en na de snapshot vergeleken; nieuwe/verwijderde projectpaden tijdens de build veroorzaken een veilige retry.
- Browserdownloadnaam blijft `YYYY-MM-DD HH.MM CrashRecovery EnergieProject.zip`.
- Add-on changelog is bijgewerkt en ontbrekende Crash Recovery-releases 32.0.29/32.0.30 zijn teruggevuld.
- Geen wijziging aan maandafsluiting, juli-status, `finalize_month`, RestoreStaging of backupretentie.

## v32.0.30 — Crash Recovery heartbeat-snapshot

- Crash Recovery legt `Data/01_Input/_scheduler/quarter_hour_heartbeat.json` als één stabiele byte-snapshot vast, zodat normale scheduler-heartbeats de export niet meer onterecht afbreken.
- Alle andere projectbestanden blijven onder de bestaande strenge size/mtime-wijzigingscontrole; symlink- en backup-in-backup-regels blijven ongewijzigd.
- Browserdownload krijgt de filesystem-veilige naam `YYYY-MM-DD HH.MM CrashRecovery EnergieProject.zip`.
- Geen wijziging aan maandafsluiting, juli-status, `finalize_month`, RestoreStaging of normale backupretentie.

## v32.0.29 — Crash Recovery browser/iCloud export

- Complete Crash Recovery levert na create/deep verify en veilige `RestoreStaging` één herstelvriendelijke browser-ZIP met exact top-level `EnergieProject/`.
- De export bevat de volledige actuele projectinhoud, inclusief normale maandbackups, manifests, logs en herstelhandleidingen. Alleen `Energie_Complete_Backup_*.zip`, `FULL_RECOVERY*.tar.gz` en `.DS_Store` worden niet opnieuw ingepakt.
- Na een volledig succesvolle browserdownload worden uitsluitend run-specifieke tijdelijke Crash-Recovery-artefacten op de NAS opgeruimd; een afgebroken download blijft retrybaar en verwijdert niets.
- Geen `finalize_month`, geen live restore en geen wijziging van de normale NAS-backupretentie.

## v32.0.27 — HA Ingress GUI render fail-safe

- Root cause opgelost waarbij de GUI tijdens renderen een schrijvende productiecertificaatcontrole kon starten voordat `/config/output` bestond.
- `write_atomic_json()` maakt voortaan de doelmap atomisch gereed vóór het tijdelijke JSON-bestand wordt geschreven.
- Nieuwe runtime-regressietest bewijst dat de SlimmeMeterPortal-GUI rendert wanneer de outputmap nog niet bestaat.
- Geen wijziging aan maandworkflow, SMP-import, GitHub-publicatiearchitectuur of gecertificeerde productiekern.

## v32.0.26 — fail-safe HA GUI + harde releasevalidatie

- GUI blijft bereikbaar wanneer de API-key/configuratie tijdelijk ontbreekt of nog niet geladen is.
- Startupmonitoring degradeert naar waarschuwing in plaats van een exception die Ingress breekt.
- Processed-retentie blijft semantisch en maximaal 3.
- Statische release-identiteitstests zijn opnieuw gesynchroniseerd met de actuele release.
- Standalone release-tests mogen alleen full-project Infra-tests overslaan wanneer Infra fysiek niet aanwezig is; in de installatieketentest wordt Infra wel meegenomen.
- Geen maandfinalisatie en geen wijziging aan de gecertificeerde productiekern.

## v32.0.25 — GUI startup recovery + processed-retentie

- Herstelt het volledige bewezen Home Assistant app-startpad dat in v32.0.24 onbedoeld was afgekapt.
- Herstelt signal handlers, state update, scheduler, HTTP/Ingress server en startup-selftest.
- Behoudt de semantische processed-retentie met harde eindcontrole op maximaal 3 release-ZIP's.
- Geen maandfinalisatie en geen wijziging aan de gecertificeerde productiekern.

## v32.0.24 — correcte NAS/HA-publicatiestatus

- ZIP-only QNAP-installatie markeert expliciet dat GitHub/HA-publicatie nog vereist is.
- NAS-success wordt niet langer gelijkgesteld aan een beschikbare Home Assistant update.
- De nieuwe HA add-on probeert niet meer zijn eigen nog-niet-geïnstalleerde release te publiceren.
- `Inbox/ha_publication_required.json` vormt het overdrachtspunt voor een externe GitHub publisher.
- Geen credentials of runtime-data worden aan de release toegevoegd.

## v32.0.23 — HA-app-owned processed-retentie

- Structurele fix: processed-retentie draait nu ook rechtstreeks bij startup van de HA add-on.
- Daardoor is de cleanup niet afhankelijk van de watcher/installer die de release installeerde.
- Bewaren gebeurt op semantisch versienummer; de hoogste 3 releases blijven staan.
- Startup logt before/after, behouden en verwijderde release-ZIP's.
- Fout in retentie blokkeert de energie-app niet, maar wordt expliciet als ERROR gelogd.

## v32.0.22 — watcher-owned processed-retentie

- Structurele fix: processed-retentie is niet langer afhankelijk van de installer die de huidige release installeert.
- De nieuw geïnstalleerde watcher voert bij zijn eigen startup direct retentie uit.
- Daardoor wordt de retentie ook actief bij de overgang van een oudere installer naar deze release.
- Bewaren gebeurt op semantisch versienummer, niet op bestandstijd.
- Doel na watcher-overname: uitsluitend de hoogste 3 `EnergieProject_v*.zip` releases in `Inbox/processed`.
- Een cleanup-fout stopt de watcher niet, maar publiceert status `MAINTENANCE_FAILED`.
- Installer-retentie gebruikt dezelfde semantische versielogica voor toekomstige releases.

## v32.0.21 — processed-retentie activeren via normale releaseketen

- Geen nieuwe functionele wijziging buiten de releaseketen.
- De reeds aanwezige fail-closed processed-retentie uit v32.0.20 wordt nu door de actieve v32.0.20-installer uitgevoerd.
- Installatie telt processed vóór en na cleanup en faalt wanneer meer dan 3 release-ZIP's overblijven.
- Crash Recovery blijft onafhankelijk van maandafsluiting.

## v32.0.20 — Processed-retentie fail-closed

- Retentie telt voor en na opschonen expliciet de release-ZIP’s.
- Oude releases worden deterministisch verwijderd tot maximaal 3.
- Installatie faalt als de eindcontrole meer dan 3 release-ZIP’s aantreft.

## v32.0.20 — Crash Recovery + processed-retentie

- Inbox/processed bewaart automatisch de laatste 3 release-ZIP's.
- Crash Recovery staat los van finalize_month en kan op ieder moment worden gemaakt.
- Crash Recovery bevat App, Data, Infra, Inbox en bestaande Backups.
- Alleen Backups/CrashRecovery wordt uitgesloten om recursieve backupgroei te voorkomen.
- Manifest, SHA-256, ZIP-integriteit en deep verification zijn verplicht.

## v32.0.18 — HA-ingress zonder schrijven in NAS-maandroot

- Home Assistant maakt geen stagingmap meer rechtstreeks in `Data/01_Input/YYYY_MM`.
- SMP-overdracht gebruikt `Data/01_Input/YYYY_MM/HomeAssistant` als vaste HA-ingress.
- Alleen `HomeAssistant/SlimmeMeterPortal` wordt atomisch bijgewerkt; snapshots en QuarterHour blijven onaangeroerd.
- Platform-v5 scant de maandmap recursief en herkent deze SlimmeMeterPortal-evidence zonder NAS-API-fallback.
- IPv4-only SMP, `userapi/v1`, `partial_current_month`, month_key-fix en gescheiden diagnose blijven behouden.

## v32.0.17 — automatische HA → NAS SMP-overdracht

- Een geslaagde `Importeer SMP` publiceert de gevalideerde SlimmeMeterPortal-maanddata automatisch naar `Data/01_Input/YYYY_MM/SlimmeMeterPortal`.
- Alleen de submap `SlimmeMeterPortal` wordt atomisch vervangen; bestaande Home Assistant-snapshots, analyses en andere maandbronnen blijven onaangeroerd.
- Publicatie gebruikt staging, SHA-256-verificatie en rollback van uitsluitend de SMP-submap.
- `ha_smp_transfer_manifest.json` bewijst maand, doelpad, bestandenaantal, omvang en publicatiestatus.
- Een mislukte vereiste NAS-publicatie maakt de SMP-import zichtbaar fout; stille half-geslaagde overdrachten zijn niet toegestaan.
- De GUI en SMP-importdiagnose tonen de laatste HA→NAS overdracht.
- IPv4-only SMP, `userapi/v1`, `partial_current_month`, month_key-fix en gescheiden SMP/workflowdiagnose blijven behouden.

## v32.0.16 — complete SMP-importfix en juiste diagnose

- Definieert `month_key` vroeg in `run_import()`, zodat een kale month_key-referentie nooit meer ongedefinieerd kan zijn.
- Behoudt de v32.0.15 content-coveragefix via `workflow_month_key`.
- De losse GUI-actie `Importeer SMP` krijgt een eigen zichtbaar blok `Laatste SMP-import`.
- Fouttype en volledige Python-traceback van de losse SMP-import worden bewaard.
- `Download SMP-importdiagnose` levert exact de status en traceback van de laatste losse SMP-import.
- `Laatste workflowfout` en `Download workflowlog` blijven uitsluitend gekoppeld aan de volledige maandworkflow.
- IPv4-only SlimmeMeterPortal transport, `userapi/v1`, `partial_current_month` en de bestaande releaseketen blijven behouden.
- De release wordt als volledige ZIP uit v32.0.15 opgebouwd; de live App-map wordt tijdens het bouwen niet gewijzigd.

## v32.0.15 — SlimmeMeterPortal maandimport month_key fix

- Herstelt RuntimeError `name 'month_key' is not defined` in de SMP-inhoudscontrole.
- De inhoudscontrole gebruikt nu de reeds gedefinieerde `workflow_month_key`.
- De werkende IPv4-only SMP-transportfix uit v32.0.14 blijft behouden.
- `partial_current_month` en de moderne `/userapi/v1` route blijven behouden.
- Regression-test voorkomt gebruik van de ongedefinieerde `month_key` op deze plek.

## v32.0.14 — HA SlimmeMeterPortal IPv4 transportfix

- SlimmeMeterPortal-aanroepen vanuit de HA-app gebruiken geforceerd IPv4.
- Moderne userapi/v1 endpoints en bestaande API-key blijven ongewijzigd.
- API-test krijgt veilige DNS/transportdiagnose.
- partial_current_month blijft behouden.
- Actuele analyse release_version en engine_version volgen APP_VERSION.

## v32.0.13 — release-identiteit gesynchroniseerd

- VERSIE.txt, add-on config en APP_VERSION zijn gelijkgetrokken.
- De release-watcher kan de actuele release nu correct herkennen en archiveren.
- v32.0.12 HA-current-month en transferfix blijft inhoudelijk ongewijzigd.

## v32.0.12 — lopende maand via Home Assistant

- De handmatige/full workflow verwerkt standaard de lopende kalendermaand.
- De aparte maandelijkse scheduler blijft de vorige kalendermaand verwerken.
- Bestaande opgeslagen HA-opties kunnen de full workflow niet terugzetten op vorige maand.
- SMP-maanddata wordt via Home Assistant naar Data/01_Input overgedragen.
- De verouderde analysezin 'SlimmeMeterPortal wordt bewust overgeslagen' is verwijderd.

## v32.0.11 — Home Assistant centrale API-importlaag

- Externe/API-importen lopen productioneel via Home Assistant.
- `full_month_workflow` wordt ook voor bestaande opgeslagen opties afgedwongen.
- De NAS-workflow voert geen directe SlimmeMeterPortal-API-fallback meer uit.
- De NAS valideert en verwerkt uitsluitend HA-aangeleverde maanddata.
- De v32.0.10-logica voor `partial_current_month` blijft behouden.

## v32.0.10 — SMP bronvertraging lopende maand

- Lopende maand: recente lege SMP-dagen worden expliciet als `partial_current_month` gemeld.
- Afgesloten maand blijft volledig verplicht.
- Gaten vóór het beschikbaarheidsfront blijven hard fout.
- `available_through` en `calendar_expected_through` maken dekking controleerbaar.

## v32.0.9 — GitHub publisher status-state cleanup

- Voorkomt recursieve `last_publication`-nesting in `/config/output/github_publication_state.json`.
- Houdt de dedicated Home Assistant Git-worktree en automatische HA→GitHub-publicatie ongewijzigd actief.
- Corrigeert de v32 release-identiteitsmarker naar v32.0.9.
- Geen wijzigingen aan energiegegevens, rapportlogica, financiële gates, NAS-layout of Home Assistant-mounts.

## 32.0.3 - Home Assistant GitHub publisher worktree fix
- Herstelt automatische HA→GitHub-publicatie na de NAS-layoutmigratie.
- Publicatie gebruikt een dedicated persistente Git-worktree onder `/config/github_publisher/worktree`; `EnergieProject/App` blijft bewust zonder `.git`.
- Synchroniseert uitsluitend App-inhoud en verifieert na push dat lokale en remote HEAD gelijk zijn.
- Voorkomt CIFS executable-bit vervuiling bij nieuwe bestanden.

## v32.0.3 — definitieve NAS-layoutcorrectie en regressiecontrole
- Release-installatie is aangepast aan de definitieve NAS-structuur `EnergieProject/{App,Data,Backups,Inbox,Infra}`.
- De installer vervangt uitsluitend `App`, zodat `Data`, `Backups`, `Inbox` en `Infra` nooit door een software-update worden gewist.
- Watcher, bootstrap, Home Assistant infrastructuurdiagnose, GitHub-publicatiepad, EPEX-lokalisatie en noodherstel gebruiken dezelfde layout.
- Oude losse inbox/backuppaden zijn uit actieve broncode, scripts, tests en documentatie verwijderd.
- Pytest-importisolatie toegevoegd zodat de volledige testsuite ook met gelijknamige generatortests betrouwbaar kan worden verzameld.

## v32.0.1 — automatische crash-recoveryretentie
- Maximaal 3 pre-release herstelbackups.
- Retentie pas na succesvolle installatie/eindcontrole.
- BusyBox/QNAP-compatibel; `ENERGIE_BACKUP_RETENTION` kan het aantal overschrijven.

## v32.0.0 — final integration, backup/recovery and final validation
- Bundelt de volledige v32-afronding in één release.
- Eén consistente guarded integratieketen voor release-identiteit, financiële gates, officiële rapportage, chat/voice en savings-runtime.
- Backup/recovery wordt expliciet onderdeel van releasevalidatie.
- Na succesvolle HA-validatie is de huidige roadmap compleet.

## v31.2.0 — chat/voice completion + report/print handoff
- v31 stap 4/4 voltooid.
- Chat/voice gebruikt uitsluitend bestaande gevalideerde rapportcontext en publiceerbare financiële waarden.
- Rapport/print-handoff bewaart officiële templates en staand formaat.
- Volgende major release: v32.0.0 eindintegratie, backup/recovery en eindvalidatie.

## v31.1.0 — guarded conversation response runtime
- v31 stap 3/4.
- Antwoordcontract, taalbeleid, recommendation policy en failure policy.
- Geen externe uitvoering vanuit chat/voice.

## v31.0.0 — chat/voice context + intent routing
- Bundelt v31 stap 1/4 en 2/4.
- Gewone-taalvragen worden gebonden aan bestaande gevalideerde Energieproject-context.
- Intent-routing ondersteunt status, uitleg, vergelijking, diagnose, advies, rapport, meting en historie.
- Alle bestaande financiële en autorisatiegates blijven hard.

## v30.3.1 — release identity validation
- Correctieve build nadat de HA-analyse nog 30.2.0 rapporteerde.
- Expliciete runtime release-identiteit toegevoegd zodat updateherkenning direct controleerbaar is.
- Geen nieuwe roadmapfunctionaliteit; v30 blijft op completion stap 4/4.

## v30.3.0 — v30 guarded completion gate
- v30 stap 4/4: completion gate voor de volledige optimalisatieketen.
- Controleert kandidaat → selectie → uitvoeringsplan als één traceerbare keten.
- Externe acties blijven expliciet door de gebruiker geautoriseerd; geen verzonnen financiële waarden.

## v30.2.0 — guarded optimization execution plan
- v30 stap 3/4: traceerbaar uitvoeringsplan voor één gevalideerde optimalisatie.
- Meetbaseline, succesmetric en rollback-gate verplicht.
- Geen automatische aankoop, leverancierswissel, contractacceptatie, voorschotwijziging of apparaatbesturing.

## v30.1.0 — guarded optimization selection
- v30 stap 2/4: maximaal één financieel voorkeursadvies uit gevalideerde optimalisatiekandidaten.
- Externe financiële/meetgates en gebruikersautorisatie blijven hard.
- Geen automatische aankoop, leverancierswissel, contractacceptatie, voorschotwijziging of apparaatbesturing.

## v30.0.0 — adaptive optimization candidates
- Start v30 met een guarded optimalisatielaag bovenop de afgeronde forecastketen.
- Kandidaten worden financieel gerangschikt op gevalideerde eurowaarde, confidence en implementatie-inspanning.
- Externe financiële en meetgates blijven hard; geen autonome externe uitvoering.

## v29.2.0 — forecast publication + v29 completion
- Bundelt v29 stap 3/4 en 4/4.
- Publiceert alleen gevalideerde gekalibreerde besparingsprognoses.
- Actuals, businesscase en forecast blijven gescheiden; onzekerheid en confidence zijn verplicht.
- Volgende major release: v30.0.0.

## v29.1.0 — calibrated savings forecast
- v29 stap 2/4: gevalideerde kalibratie wordt vertaald naar toekomstige besparingsprognoses.
- Actuals, businesscase en forecast blijven afzonderlijke financiële lagen.
- Onzekerheid blijft zichtbaar; negatieve forecastaanpassingen worden behouden.

## v29.0.0 — guarded forecast calibration
- Start v29 met gecontroleerde kalibratie van toekomstige energie- en financiële prognoses.
- Historische actuals blijven immutable; forecast-aanpassingen worden afzonderlijk opgeslagen en gepubliceerd.
- Kalibratie vereist herhaald gevalideerd bewijs en relevante context.

## v28.2.0 — outcome learning + v28 completion
- Bundelt v28 stap 3/4 en 4/4.
- Leert uitsluitend uit herhaalde, gevalideerde uitvoering- en meetuitkomsten.
- Geen modelrewrite vanuit één gebeurtenis, kandidaatwaarde of kort meetvenster.
- Volgende major release: v29.0.0.

## v28.1.0 — verified outcome portfolio
- v28 stap 2/4: traceerbare portfolio van uitsluitend gevalideerde gerealiseerde uitkomsten.
- Geen estimate-promotie, dubbeltelling, automatische overlapverdeling of annualisatie.
- Negatieve uitkomsten worden niet weggefilterd.

## v28.0.0 — guarded execution outcome verification
- Start v28 met gesloten-lus verificatie van uitgevoerde energieacties.
- Accepteert gerealiseerde besparing alleen na valide uitvoeringsbewijs en vergelijkbare voor/na-meting.
- Bewaart negatieve financiële uitkomsten en verbiedt dubbeltelling en short-window annualisatie.

## v27.2.0 — execution plan publication + v27 completion
- Bundelt v27 stap 3/4 en 4/4.
- Publiceert maximaal drie guarded uitvoeringsplannen naar officiële rapportsurfaces.
- Sluit v27 af zonder externe observatie-, contract-, meet- of gebruikersactiegates kunstmatig te openen.
- Volgende major release: v28.0.0.

## v27.1.0 — guarded execution plans
- v27 stap 2/4: concrete uitvoeringsplannen voor maximaal drie gevalideerde energieacties.
- Meetplan, succescriterium, stopconditie en rollback worden expliciet onderdeel van ieder toepasbaar plan.
- Geen financiële transacties of apparaatwijzigingen zonder gebruikersactie.

## v27.0.0 — guarded execution readiness
- Start v27 met uitvoeringsgereedheid voor maximaal drie financieel geprioriteerde energieacties.
- Acties worden alleen uitvoeringsgereed wanneer bewijs, financiële case en vereiste externe gates valide zijn.
- Meetplan en stopconditie worden onderdeel van de uitvoeringscontext.
- Geen autonome financiële transacties of apparaatwijzigingen.

## v26.2.0 — action queue publication + v26 completion
- Bundelt v26 stap 3/4 en 4/4.
- Publiceert maximaal drie guarded energieacties naar officiële rapportsurfaces.
- Sluit v26 af zonder externe observatie-, contract- of meetgates kunstmatig te openen.
- Volgende major release: v27.0.0.

## v26.1.1 — GUI runtime hotfix
- Herstelt de Action Queue runtime waardoor de GUI-context in v26.1.0 kon crashen.
- Voegt een runtime-safe regressiecontrole toe zodat JSON-literals niet opnieuw in Python-dictionaries terechtkomen.

## v26.1.0 — guarded action queue
- v26 stap 2/4: maximaal drie traceerbare energieacties vanuit gevalideerde financiële prioritering.
- Expliciete act_now / measure_first / wait_for_data / do_not_pursue toestanden.
- Geen bypass van observatie-, leveranciercontract-, all-in- of meetgates.

## v26.0.0 — decision value prioritization
- Start v26 met guarded financiële prioritering van maximaal drie concrete energieacties.
- Combineert euro-impact, confidence, meetgereedheid, data quality en uitvoeringsinspanning.
- Supplier-, batterij- en apparaatbeslissingen behouden hun bestaande harde gates.
- Geen estimate-promotie, partial-period extrapolatie of dubbeltelling.

## v25.3.0 — report publication + v25 completion
- Bundelt v25 stap 4/5 Report Publication en stap 5/5 Completion in één grotere release.
- Publiceert alleen gevalideerde gerealiseerde Savings Ledger-, portfolio- en maandbudgetwaarden naar officiële rapportsurfaces.
- Externe meet-, contract- en period-normalization gates mogen bij technische v25-afronding nog gesloten zijn.
- Blokkeert kandidaatwaarden, business-case estimates, partial-period extrapolatie, dubbeltelling en ongevalideerde voorschotwijzigingen.
- Volgende major release: v26.0.0.

## v25.2.0 — guarded monthly budget impact
- v25 stap 3/5: vertaalt uitsluitend gevalideerde gerealiseerde portfolio-impact naar maandbudgetcontext.
- Referentie maandvoorschot blijft €150; ledgerbesparing alleen mag het leveranciervoorschot niet wijzigen.
- Gedeeltelijke meetvensters worden niet automatisch naar maandwaarden geëxtrapoleerd.
- Voorkomt dubbeltelling tussen gerealiseerde besparing en leverancier-kostenprognoses.
- Volgende stap: guarded report publication runtime.

## v25.0.0 — guarded validated savings ledger
- Start v25 vanaf de in Home Assistant gevalideerde v24.4.0 completion-baseline.
- Voegt één traceerbaar Savings Ledger-contract toe voor uitsluitend gevalideerde gerealiseerde besparingen uit de v24-keten.
- Voorkomt dubbeltelling via stabiele action-id + evidence-reference; estimates, candidates en self-report mogen niet als gerealiseerde eurobesparing worden geboekt.
- Negatieve gerealiseerde impact blijft zichtbaar en mag niet naar nul worden afgevlakt.
- v25-roadmap stap 1/5; hierna cumulatieve portfolio-impact, budget/voorschot-impact, rapportpublicatie en completion.
- Behoudt ongewijzigd de v24.3.1 suffix-tolerante NAS→GitHub→Home Assistant publicatieketen.

## v24.4.0 — v24 completion gate
- Sluit v24 af na de in Home Assistant gevalideerde Variance/Learning Runtime van v24.3.1.
- Consolideert Action Handoff, Action Tracking, Realized Savings en Variance/Learning tot één guarded end-to-end keten.
- Externe meet- en contractgates mogen bij release-afronding nog geblokkeerd zijn; zij openen later automatisch zonder handmatige override.
- Kandidaatwaarden, korte meetvensters en business-case schattingen mogen nooit als gerealiseerde besparing of learning-input worden gepromoveerd.
- v24-roadmap stap 5/5 voltooid; volgende hoofdontwikkelrelease is v25.0.0.
- Behoudt de v24.3.1 suffix-tolerante NAS→GitHub→Home Assistant publicatiefix.

## v24.3.1
- Herstelt NAS→GitHub→Home Assistant publicatie wanneer browser/QNAP een releasebestand als `(1)`/`(2)` archiveert.
- Publisher accepteert voortaan alle verifieerbare `EnergieProject_v<versie>*.zip` bestanden in `processed`.
- Installer archiveert toekomstige releases canoniek als `EnergieProject_v<versie>.zip`.

# Changelog

## v24.2.0 — guarded realized savings

- Bouwt voort op de in Home Assistant gevalideerde v24.1.0 Action Tracking Runtime.
- Voegt meetbare gerealiseerde besparing toe met verplichte baseline, post-actiemeting en vergelijkbare meetvensters.
- Voorkomt dat business-case schattingen, zelfrapportage of kandidaatwaarden als werkelijke besparing worden gepubliceerd.
- Annualisering blijft geblokkeerd tot een representatieve gevalideerde periode beschikbaar is; relevante seizoens- en gebruikseffecten moeten zijn verwerkt.
- v24-roadmap stap 3/5: Realized Savings; hierna Variance/Learning en Completion.

## v24.1.0 — guarded action tracking

- Bouwt voort op de in Home Assistant gevalideerde v24.0.0 Action Handoff Runtime.
- Voegt traceerbare actiestatus, uitvoeringsbewijs en audittrail toe zonder externe acties automatisch uit te voeren.
- Zelfrapportage mag een actie registreren, maar nooit zelfstandig gerealiseerde financiële besparing bewijzen.
- Gerealiseerde besparing blijft `null` tot gevalideerde meetdata beschikbaar is.
- v24-roadmap stap 2/5: Action Tracking; hierna Realized Savings.

## v24.0.0 — guarded action handoff

- Start v24 vanaf de gevalideerde v23.5.0 productie-baseline.
- Voegt een traceerbare handoff toe van publiceerbaar besparingsadvies naar een concrete gebruikersactie, zonder automatische externe uitvoering.
- Behoudt alle observatie-, contract-, kandidaat-, null- en EPEX-publicatiegates.
- Legt actievoorwaarden, financiële basis, blockers, bewijsreferentie en datakwaliteit vast in één outputcontract.
- v24-roadmap stap 1/5: Action Handoff; hierna Action Tracking, Realized Savings, Variance/Learning en Completion.

## v23.5.0 — financiële beslissing naar rapportklare actie

- Start nieuwe hoofdversie na afronding van de v18 explainabilityketen.
- Zet de bestaande financiële beslissing en uitleg om in een eenduidig presentatiecontract voor de officiële rapporten.
- Houdt alle kwaliteits-, contract- en publicatiegates ongewijzigd actief.
- Bouwt voort op bestaande functionaliteit; geen financiële bouwblokken opnieuw geïmplementeerd.

## v23.5.0 — afronding financiële explainability

- Sluit v18 af op basis van de in Home Assistant gevalideerde v18.2.0 rapport-handoff.
- Consolideert financiële explainability, runtime-redenen en officiële rapportuitleg.
- Houdt alle bestaande kwaliteits-, contract- en publicatiegates strikt actief.
- Bereidt de overgang naar v19 voor zonder bestaande financiële of rapportfunctionaliteit opnieuw te bouwen.

## v23.5.0 — financiële uitleg naar officiële rapporten

- Bouwt voort op de in Home Assistant gevalideerde v18.1.0 runtime-uitleglaag.
- Verbindt financiële explainability met de officiële rapportgeneratorcontext.
- Zorgt dat financiële waarden en blokkades in rapporten dezelfde herleidbare redenstructuur gebruiken.
- Behoudt alle bestaande publicatie-, kwaliteits- en contractgates.

## v23.5.0 — financiële explainability en auditbaarheid

- Start nieuwe hoofdversie na succesvolle afronding van de guarded v17-kostenbesparingsketen.
- Legt een formeel contract vast voor uitlegbare financiële adviezen en geblokkeerde adviezen.
- Maakt zichtbaar welke data, kwaliteitsgates en contractcomponenten een toekomstig advies dragen of blokkeren.
- Behoudt alle bestaande financiële veiligheidsregels en rapportgeneratorintegratie.

## v23.5.0 — afronding financiële kostenbesparingsketen

- Sluit v17 af op basis van de in Home Assistant gevalideerde v17.2.0 runtime-publicatiegate.
- Consolideert financiële beslissing, concrete besparingsaanbeveling en veilige publicatie tot één productie-baseline.
- Houdt alle externe kwaliteits- en contractgates ongewijzigd strikt actief.
- Bereidt de overgang naar v18 voor zonder bestaande financiële functionaliteit opnieuw te bouwen.

## v23.5.0 — publicatiegate kostenbesparingsadvies

- Bouwt voort op de gevalideerde v17.1.0 aanbevelingscontractlaag.
- Voegt de laatste runtime-publicatiecontrole toe vóór een concreet financieel advies zichtbaar mag worden.
- Voorkomt halve of intern inconsistente aanbevelingen.
- Laat de aanbeveling automatisch verschijnen zodra alle bestaande financiële gates en verplichte adviesvelden geldig zijn.

## v23.5.0 — concrete kostenbesparingsaanbevelingen

- Bouwt voort op de in Home Assistant gevalideerde v17.0.0.
- Verbindt de guarded financiële beslissing met concrete actie-uitvoer voor maandvoorschot en besparingsadvies.
- Acties, bedragen en adviessterkte worden uitsluitend gepubliceerd wanneer alle bestaande financiële gates geldig zijn.
- Geblokkeerde toestand blijft expliciet `Niet beschikbaar`.

## v23.5.0 — financiële beslisuitvoer

- Start v17 vanaf de gevalideerde v16.3.0 productie-baseline.
- Legt de guarded beslisuitvoer vast voor daadwerkelijke kostenbesparing en maandvoorschotadvies.
- Een aanbeveling wordt uitsluitend gepubliceerd wanneer zowel de prognosekwaliteit als leverancier-all-in contractvalidatie volledig slagen.
- Onvolledige data blijft zichtbaar als niet beschikbaar en wordt nooit door aannames vervangen.

## v23.5.0 — v16 productieconsolidatie

- Rondt de v16 financiële rapportuitvoer af.
- Consolideert outputcontract, live runtime-gates en auditeerbare publicatievalidatie.
- Houdt alle externe datagates strikt intact en bereidt de productie-baseline voor op v17.

## v23.5.0 — auditeerbare runtime-validatie

- Maakt de feitelijke activatiestatus van financiële rapportvelden expliciet controleerbaar.
- Legt per financiële gate vast welke runtimebron de publicatie vrijgeeft en waar de blokkeerreden vandaan komt.
- Bereidt de laatste v16-consolidatiestap voor zonder de bestaande financiële logica opnieuw te bouwen.

## v23.5.0 — runtime activatie financiële rapportuitvoer

- Bindt de officiële rapportuitvoer aan de feitelijke runtime-gates in plaats van alleen aan statische beleidsregels.
- Prognose, leverancier-all-in en voorschotadvies krijgen elk hun eigen expliciete activatiebron.
- Overgang van geblokkeerd naar publiceerbaar gebeurt automatisch zodra de bronstatus geldig wordt.

## v23.5.0 — officiële financiële rapportuitvoer

- Start v16 vanaf de gevalideerde v15.3.0 guarded productie-baseline.
- Legt het outputcontract vast waarmee de officiële rapportgeneratoren automatisch echte financiële waarden mogen tonen zodra hun externe gates slagen.
- Prognosewaarden activeren na de bestaande 7-dagen observatiegate.
- Leverancier-all-in waarden activeren pas na volledige officiële NextEnergy-contractvalidatie.
- Handmatige bypass, nul-fallback en publicatie van validatie-candidates blijven verboden.

## v23.5.0 — v15 productieconsolidatie

- Rondt de v15 integratie van de financiële engine met de officiële rapportgeneratoren af.
- Bevestigt één guarded productiecontext, expliciete veldcontracten en laatste renderbeveiliging.
- Externe datagates blijven bewust actief: 7 waargenomen dagen en officiële NextEnergy-contractcomponenten.
- Bereidt de productie-baseline voor op v16 zonder bestaande functies opnieuw te bouwen.

## v23.5.0 — veilige financiële rapportweergave

- Voegt een expliciete laatste renderbeveiliging toe vóór financiële waarden de officiële rapporten bereiken.
- Scheidt validatie-candidates strikt van publiceerbare prognoses.
- Voorschotvergelijking wordt pas financieel publiceerbaar wanneer leverancier-all-in gereed is.
- Ontbrekende/geblokkeerde waarden blijven `Niet beschikbaar` en worden nooit 0.

## v23.5.0 — officiële rapportgenerator veldcontracten

- Legt de bron en publicatiegate per financieel rapportveld expliciet vast.
- Behoudt de 7-dagen observatiegate en officiële NextEnergy-contractgate.
- Voorkomt dat rapportgeneratoren eigen financiële aannames of nulwaarden introduceren.

## v23.5.0 — officiële rapportgenerator productiecontext

- Eén guarded financiële productiecontext voor alle officiële rapportgeneratoren.
- Pagina 1 managementsamenvatting/KPI's en pagina 2 financiële simulatie/prognose/maandtermijncontrole gebruiken de gevalideerde financiële bronlaag.
- Pagina's 3–13 kunnen dezelfde context gebruiken zonder eigen financiële aannames.
- 7-dagengate, officiële NextEnergy-contractgate en EPEX-referentiebeleid blijven intact.

## v23.5.0 — v14 eindconsolidatie en opgeschoonde HA-releaseweergave

- Laatste geplande v14-productiestap.
- Home Assistant add-on changelog bevat voortaan uitsluitend de actuele release.
- Financiële rapportpublicatie, bronmapping en datagates geconsolideerd.
- Ontbrekende financiële waarden blijven `Niet beschikbaar`; nul-fallback blijft verboden.
- EPEX blijft uitsluitend markt-/referentieprijs.
- Bestaande GUI, Ingress, watcher, GitHub-publicatie, maandworkflow, diagnoses en herstelvoorzieningen blijven behouden.

## v23.5.0 — financiële rapportpublicatie-gates

- Voegt expliciete publicatie-gates toe tussen de gevalideerde financiële context en de officiële rapportvelden.
- Prognosevelden worden alleen publiceerbaar na de 7-dagen kwaliteitsgate.
- Leverancier-all-in velden worden alleen publiceerbaar na officiële contractvalidatie.
- Maandtermijnadvies wordt alleen publiceerbaar wanneer de recommendation-gate geldig is.
- Geblokkeerde waarden worden als `Niet beschikbaar` weergegeven en nooit als numerieke nul.
- EPEX kan niet als leverancier-all-in worden gepubliceerd.
- Bestaande GUI, Ingress, watcher, publicatie, maandworkflow, diagnoses en herstelvoorzieningen blijven behouden.

## v23.5.0 — financiële rapportvelden gekoppeld aan gevalideerde bronnen

- Koppelt management-financiële KPI's expliciet aan de guarded decision-supportlaag.
- Koppelt pagina 2 prognosevelden aan `financial_projection` en `projection_detail`.
- Koppelt maandtermijnadvies aan de bestaande guarded decision-supportlaag.
- Leverancier-all-in velden mogen uitsluitend uit gevalideerde officiële contractwaarden komen.
- Ontbrekende waarden blijven `Niet beschikbaar`; nul-fallback blijft verboden.
- 7-dagen kwaliteitsgate blijft verplicht.
- EPEX blijft uitsluitend markt-/referentieprijs.
- Bestaande GUI, Ingress, watcher, publicatie, maandworkflow, diagnoses en herstelvoorzieningen blijven behouden.

## v23.5.0 — officiële rapportgeneratoren geactiveerd op guarded financiële context

- Start v14 vanaf de volledig gevalideerde v13.3.0 productie-baseline.
- Activeert de officiële rapportgenerator-koppeling voor management-KPI's, financiële simulatie, jaarprognose en maandtermijncontrole.
- Pagina's 3–13 ontvangen dezelfde guarded financiële context.
- De 7-dagen kwaliteitsgate blijft verplicht voor prognosevelden.
- Leverancier-all-in blijft geblokkeerd totdat officiële NextEnergy-contractcomponenten geldig beschikbaar zijn.
- Ontbrekende financiële waarden worden als `Niet beschikbaar` gerenderd en nooit als nul aangenomen.
- EPEX blijft uitsluitend markt-/referentieprijs.
- Bestaande GUI, Ingress, watcher, GitHub-publicatie, maandworkflow, diagnoses en herstelvoorzieningen blijven behouden.

## v23.5.0 — v13 eindconsolidatie

- Consolideert de guarded financiële rapportageketen als productie-baseline.
- Home Assistant releaseweergave is voortaan bedoeld voor uitsluitend de nieuwste release.
- Financiële simulatie, jaarprognose en maandtermijncontrole blijven achter hun bestaande datagates.
- Ontbrekende financiële waarden blijven `Niet beschikbaar` en worden nooit als nul aangenomen.
- EPEX blijft uitsluitend markt-/referentieprijs.

## v23.5.0 — officiële financiële rapport-rendercontracten

- Bouwt voort op de in Home Assistant gevalideerde v13.1.1 hotfix.
- Legt voor de officiële rapportgeneratoren expliciet vast hoe financiële velden worden gerenderd.
- Financiële simulatie, jaarprognose en maandtermijncontrole blijven guarded totdat hun datagates geldig zijn.
- Ontbrekende financiële waarden worden weergegeven als `Niet beschikbaar`; numerieke nul-fallback is verboden.
- Leverancier-all-in labels vereisen gevalideerde officiële contractwaarden.
- Prognoselabels vereisen de 7-dagen kwaliteitsgate.
- Voorschotadvies vereist een publiceerbare financiële beslissing.
- EPEX mag nooit als leverancier-all-in worden gelabeld.
- GUI, watcher, GitHub-publicatie, maandworkflow, diagnoses en herstelvoorzieningen blijven behouden.

## v23.5.0 — GUI runtime hotfix

- Herstelt de Home Assistant GUI/Ingress-crash uit v13.1.0.
- Oorzaak: twee Python dictionaries gebruikten JSON `false` in plaats van Python `False`.
- Corrigeert `zero_substitution_for_missing_financial_data` en `epex_supplier_all_in_allowed`.
- Financiële logica en rapportagebeleid blijven verder ongewijzigd.

## v23.5.0 — guarded financiële rapportveld-policy

- Bouwt voort op de in Home Assistant gevalideerde v13.0.0.
- Legt per financieel rapportveld expliciet vast welke gate vereist is.
- Prognoses vereisen de observatiekwaliteitsgate.
- Leverancier-all-in vereist officiële contractvalidatie.
- Voorschotadvies en adviessterkte vereisen `recommendation_publishable`.
- Ontbrekende financiële waarden worden expliciet als niet-beschikbaar behandeld; nooit als nul.
- EPEX mag niet als leverancier-all-in bron worden gebruikt.
- Alle bestaande productievoorzieningen blijven behouden.

## v23.5.0 — officiële rapportage financiële handoff

- Start v13 vanaf de volledig gevalideerde v12.3.0.
- Verbindt de guarded financiële beslislaag expliciet met de officiële rapportageketen.
- Prognosevelden mogen alleen worden gepubliceerd nadat de 7-dagen kwaliteitsgate is gehaald.
- Leverancier-all-in velden mogen alleen worden gepubliceerd na officiële contractvalidatie.
- Voorschotadvies mag alleen in rapportage verschijnen wanneer `recommendation_publishable` waar is.
- Ontbrekende financiële waarden blijven niet-beschikbaar en worden nooit aangenomen.
- EPEX blijft uitsluitend markt-/referentieprijs en nooit leverancier-all-in.
- Bestaande GUI, watcher, GitHub-publicatie, maandworkflow, diagnose- en herstelvoorzieningen blijven behouden.

## v23.5.0 — v12 eindconsolidatie

- Laatste geplande v12-productiestap, voortbouwend op de in Home Assistant gevalideerde v12.2.0.
- Voegt een machine-leesbare `v12_completion_gate` toe.
- Kostenbesparingsbeslislogica, voorschotadvies, recommendation strength en 5% veiligheidsmarge worden als `ready_guarded` geconsolideerd.
- De 7-dagen kwaliteitsgrens blijft verplicht.
- Leverancier-all-in blijft afhankelijk van officiële NextEnergy-contractwaarden.
- Officiële rapportgeneratoren krijgen een expliciete guarded handoff vanuit de v12-beslislaag.
- Geen ontbrekende contractwaarden worden aangenomen; EPEX blijft uitsluitend referentie.
- GUI, watcher, GitHub-publicatie, maandworkflow, diagnoses en herstelketen blijven behouden.

## v23.5.0 — adviessterkte en financiële veiligheidsmarge

- Bouwt voort op de in Home Assistant gevalideerde v12.1.0.
- Voegt `recommendation_strength` toe: hold, moderate of strong.
- Adviessterkte ontstaat uitsluitend na geldige kwaliteits- én contractgates.
- Geblokkeerde analyses houden recommendation_strength op null.
- De bestaande 5% veiligheidsmarge is expliciet machine-leesbaar.
- Geen contractwaarden worden verzonnen; EPEX blijft referentie.
- Bestaande GUI, watcher, rapportgeneratoren, maandworkflow en herstelketen blijven behouden.

## v23.5.0 — financiële beslislogica en voorschotadvies

- Voegt echte kostenbesparingsbeslislogica toe bovenop de gevalideerde v12.0.0 productiebasis.
- Advies wordt uitsluitend gepubliceerd wanneer de 7-dagen kwaliteitsgate is gehaald, alle officiële contractcomponenten geldig zijn en leverancier-all-in beschikbaar is.
- Vergelijkt daarna de gevalideerde all-in maandprognose met het huidige voorschot van €150.
- Mogelijke uitkomst: voorschot mogelijk verlagen, voorschot verhogen of huidig voorschot behouden.
- Voorgesteld voorschot gebruikt een 5% veiligheidsmarge boven de gevalideerde all-in prognose.
- Geen ontbrekende contractwaarden worden afgeleid of verzonnen.
- EPEX blijft uitsluitend referentieprijs.
- Bestaande GUI, watcher, rapportgeneratoren, maandworkflow en herstelketen blijven behouden.

## v23.5.0 — financiële beslisondersteuning productie-baseline

- Start v12 vanaf de volledig gevalideerde v11.3.0.
- Voegt een expliciete beslisondersteuningslaag toe bovenop analyse, prognose en officiële rapportgeneratoren.
- Primaire doelstelling: aantoonbare energiekostenbesparing.
- Maandvoorschot €150 wordt als bekende context meegenomen, maar nog niet als kostenprognose geïnterpreteerd.
- Financiële aanbevelingen blijven geblokkeerd totdat zowel de 7-dagen prognosegate als de vereiste leverancier-all-in contractdata beschikbaar zijn.
- Geen ontbrekende contractwaarden worden aangenomen; EPEX blijft uitsluitend referentie.
- Bestaande GUI, watcher, maandworkflow, diagnose- en herstelketen blijven behouden.

## v23.5.0 — v11 eindconsolidatie

- Laatste geplande v11-productiestap.
- Voegt een expliciete machine-leesbare v11 completion gate toe.
- Analyseketen, prognose-engine, automatische activatie en officiële rapportgeneratoren worden als gereed/guarded vastgelegd.
- Externe datagates blijven zichtbaar: 7 waargenomen dagen en officiële NextEnergy-contractwaarden.
- Geen contractwaarden worden ingevuld of afgeleid.
- Geen wijziging aan bewezen GUI, watcher, maandworkflow, GitHub-publicatie of herstelketen.

## v23.5.0 — guarded report-readiness

- Bouwt voort op de gevalideerde v11.1.0.
- Maakt de productiestatus van de officiële rapportgeneratoren expliciet in de analyse-audit.
- Prognosevelden worden alleen gevuld wanneer de bestaande prognosekwaliteitsgate is gehaald.
- Leverancier-all-in velden blijven afhankelijk van volledig gevalideerde contractcomponenten.
- Ontbrekende financiële waarden blijven zichtbaar als niet beschikbaar en worden niet verzonnen.
- Geen wijziging aan watcher, GUI/Ingress, automatische maandworkflow of herstelketen.

## v23.5.0 — automatische prognose-activatie

- Bouwt voort op de gevalideerde v11.0.0 productie-baseline.
- Legt expliciet vast dat de 30-daagse prognose automatisch activeert zodra de bestaande 7-dagen kwaliteitsgrens wordt gehaald.
- Geen handmatige override van de kwaliteitsgrens.
- Leverancier-all-in blijft afzonderlijk geblokkeerd tot officiële contractcomponenten geldig zijn.
- Verouderde interne target-release 10.6 bijgewerkt naar 11.1.
- Geen wijziging aan watcher, GUI/Ingress, maandworkflow of herstelketen.

## v23.5.0 — financiële & rapportage productie-baseline

- Start hoofdversie 11 vanaf de volledig gevalideerde v10.9.1 op Home Assistant 2026.8.2.
- Consolideert de financiële analyse, prognose-engine en officiële rapportkoppeling als productie-baseline.
- GUI-bouwstatus bijgewerkt van de historische 10.6-aanduiding naar de actuele productiestatus.
- Strikte contractgating blijft verplicht: geen leverancier-all-in zonder officiële gevalideerde contractwaarden.
- EPEX blijft uitsluitend markt-/referentieprijs.
- Geen wijziging aan de bewezen watcher-, GitHub-, maandworkflow-, diagnose- of herstelketen.

## v23.5.0 — GUI runtime hotfix

- Herstelt de Home Assistant GUI/Ingress-crash uit v10.9.0.
- Oorzaak: `production_consolidation` verwees naar een niet-bestaande constante `MINIMUM_PROJECTION_OBSERVED_DAYS`.
- Gebruikt nu de bestaande gevalideerde kwaliteitsgrens van 7.0 dagen zonder nieuwe afhankelijkheid.
- Financiële logica en rapportintegratie blijven ongewijzigd.

## v23.5.0 — productieconsolidatie financiële keten

- Consolideert de gevalideerde financiële analyse-, prognose- en rapportketen.
- Voegt expliciete productie-readiness/auditstatus toe aan de analyse-export.
- Bevestigt strikte contractgating: geen leverancier-all-in zonder gevalideerde officiële contractwaarden.
- Behoudt de 7-dagen kwaliteitsgrens en EPEX als uitsluitend markt-/referentieprijs.
- Behoudt officiële rapportintegratie uit 10.8.x, GUI, watcher, maandworkflow, diagnoses en herstelvoorzieningen.
- Voorbereid als laatste 10.x productiestap vóór v11.0.

## v23.5.0 — watcher checksum-manifest hotfix

- Herstelt verplicht `SHA256SUMS.json` dat in v10.8.1 ontbrak.
- Release-identiteit overal 23.5.0.
- Functionele inhoud van de financiële rapportintegratie ongewijzigd.

## v23.5.0 — release-identiteit hotfix

- Corrigeert de fout waardoor het v10.8.0-pakket intern nog als v10.7.0 werd gepubliceerd.
- Add-on/config-versie, APP_VERSION en financiële engine-identiteit zijn nu consistent v23.5.0.
- Functionaliteit van v10.8.0 blijft ongewijzigd: officiële financiële rapportintegratie en strikte contractgating.
- Geen wijzigingen aan watcher, GUI, maandworkflow of herstelvoorzieningen.

## v23.5.0 — officiële financiële rapportintegratie

- Verbindt de gevalideerde financiële analyse met de bestaande officiële rapportgeneratoren.
- Pagina 2 gebruikt geen financiële voorbeeldwaarden meer als productiedata.
- Alleen waargenomen/verifieerbare NextEnergy-kosten worden doorgegeven.
- Leverancier-all-in, gas, terugleververgoeding en termijnadvies blijven expliciet niet beschikbaar zolang officiële contractcomponenten ontbreken.
- EPEX blijft uitsluitend markt-/referentieprijs.
- De bestaande 7-dagen kwaliteitsgrens blijft ongewijzigd.
- Adapterresultaat bevat een auditblok `financial_report_integration`.
- Alle bestaande GUI-, watcher-, workflow-, diagnose- en herstelvoorzieningen blijven behouden.

## v10.7.0
- Prognose-engine verdiept met kalendermaand-run-rate na de bestaande 7-dagen kwaliteitsgate.
- 30-dagen variabele elektriciteitsprognose krijgt een expliciete ±15% bandbreedte voor scenarioanalyse.
- Nieuwe projection_detail-output blijft strikt elektriciteit-only en nooit leverancier-all-in zonder officiële contractcomponenten.
- EPEX blijft uitsluitend markt-/referentieprijs.
- Bestaande GUI, watcher, GitHub-publicatie, diagnoses, maandworkflow, herstel en rapportgeneratoren behouden.


## 10.6.0
- Financiële prognose-engine geactiveerd als productiefunctionaliteit bovenop de bewezen v10.5.39-bouwblokken.
- Na minimaal 7 waargenomen dagen publiceert `financial_projection` een echte 30-dagenprognose voor import en verbruiksgewogen variabele NextEnergy-stroomkosten.
- Indien officiële vaste leverancierskosten en opslag beschikbaar zijn, worden deze afzonderlijk toegevoegd aan de 30-dagen leverancier-stroomprognose.
- Leverancier-all-in blijft bewust `null` zolang vaste kosten, opslag, terugleververgoeding of gasformule niet volledig gevalideerd zijn; ontbrekende contractwaarden worden nooit verzonnen.
- EPEX blijft expliciet markt-/referentieprijs en wordt niet als leverancier-all-in gepresenteerd.
- `projection_engine.stage` staat nu op `production_active`; resterende all-in afhankelijkheden worden dynamisch gerapporteerd.
- Bestaande GUI, Ingress, release-watcher, GitHub-publicatie, diagnose-downloads, maandworkflow, rapportgeneratoren en herstelvoorzieningen zijn behouden.

## 10.5.39
- Kritieke GUI-regressie opgelost in `build_analysis_context()`: de maandlus gebruikt nu de geldige `month`-context in plaats van de niet-bestaande variabele `item`.
- Hierdoor crasht de Home Assistant Ingress/Web UI niet meer met `NameError: name 'item' is not defined`.
- Regressiontest toegevoegd die voorkomt dat deze ongeldige variabele opnieuw in het gewogen maandblok terechtkomt.
- `/health`, achtergrondtaken, releaseketen en rapportfunctionaliteit blijven ongewijzigd.


## 10.5.37
- Ontbrekende zichtbare rapportpagina in de Home Assistant Web UI opgelost.
- Nieuwe route `reports` toegevoegd met een echte HTML-rapportpagina.
- Hoofdscherm bevat nu een duidelijke knop **Open rapportpagina**.
- Rapportstatus, maand, start/eindtijd, overdracht, generatorstatus, outputmap en laatste rapportbestanden zijn zichtbaar.
- Bestaande rapportacties zijn rechtstreeks vanaf de rapportpagina beschikbaar.
- De bestaande productie-routes en rapportgeneratorlogica zijn niet vervangen; alleen de GUI-ontsluiting is hersteld.

## 10.5.36
- Contractformulemotor toegevoegd voor terugleververgoeding en gas.
- Teruglevering ondersteunt een expliciet vast contracttarief of `market_price_minus_markup`.
- Gas ondersteunt expliciet `fixed` of `market_price_plus_markup`.
- Formules rekenen uitsluitend met gevalideerde contractwaarden; ontbrekende of onbekende waarden leveren `null` plus reden op.
- Per maand is `contract_formula_preview` toegevoegd zodat analyse/diagnose direct laat zien waarom export- of gaskosten wel/niet berekenbaar zijn.
- Formule-uitkomsten worden nog niet stilzwijgend in leverancier-all-in opgenomen; activatie blijft gated richting v10.6.

## 10.5.35
- Contractkostenlaag uitgebreid met echte berekeningslogica voor leveranciercomponenten.
- Bij geldige vaste leveringskosten + opslag wordt een waargenomen leverancier-stroomkost berekend over exact dezelfde meetperiode.
- 30-dagen kandidaatprojectie bevat afzonderlijk marktprijs, opslag, vaste leveringskosten en leverancier-stroomtotaal.
- Alle leverancierberekeningen blijven expliciet `electricity_only_not_all_in`: gas, teruglevering en netbeheerkosten worden niet stilzwijgend meegerekend.
- Dynamische teruglevering wordt ondersteund via `export_compensation_formula` met type `market_price_minus_markup`; een vast bedrag blijft ondersteund.
- `financial_status` schakelt contractkosten/export/readiness voortaan dynamisch op basis van gevalideerde contractconfiguratie en de 7-dagenkwaliteitsgate.

## 10.5.34
- Veilige NextEnergy-contractkostenlaag toegevoegd richting v10.6.
- Nieuwe optionele bron: `00_Config/nextenergy_contract_costs.json`.
- Vaste leverancierskosten, opslag per kWh, terugleververgoeding en gasformule worden alleen geactiveerd wanneer geldige officiële waarden aanwezig zijn.
- Onbekende waarden blijven `null`; er worden geen tarieven of aannames verzonnen.
- `supplier_context.contract_costs` toont bron, geldigheid en validatiefouten.
- Voorbeeldbestand `00_Config/nextenergy_contract_costs.example.json` toegevoegd.
- Bestaande gewogen prijs-, prognose- en diagnoseketen blijft werken wanneer het contractkostenbestand ontbreekt.

## 10.5.33
- Financiële gereedheidsmatrix toegevoegd richting v10.6.
- Technische/contractuele bouwblokken worden expliciet als gereed/niet-gereed gerapporteerd.
- `financial_readiness.progress_pct` en `next_required_components` maken zichtbaar wat nog ontbreekt.
- Kandidaat-30-dagen variabele stroomkosten worden nu naast het maandvoorschot van €150 gezet, uitsluitend als context.
- De vergelijking met het voorschot is expliciet gemarkeerd als `variable_electricity_only_not_all_in`; er wordt dus geen onterechte all-in conclusie getrokken.
- All-in blijft geblokkeerd tot vaste leverancierskosten, opslag, terugleververgoeding en gasformule zijn gekoppeld.

## 10.5.32
- Nieuwe knop **Download release-diagnose** in de Web UI.
- Release-diagnose werkt ook wanneer een release niet geslaagd is en bevat alleen relevante watcher-, publicatie- en runtimestatus.
- Historische release-locaties uit `incoming`, `processing`, `processed` en `failed` worden meegenomen; via `?version=X.Y.Z` kan ook een oudere release gericht worden onderzocht.
- `runtime_diagnostics` toont uptime, PID, actieve threads en backend-health zodat 0% CPU niet meer met 'app staat stil' wordt verward.
- Stale `.git/index.lock` wordt alleen gerapporteerd, niet automatisch verwijderd.
- Geen P1-, Enphase-, EPEX-, rapport-, token- of wachtwoorddata in de release-diagnose.

## 10.5.31
- v10.6-prognose-engine kan vóór het openen van de 7-dagengate intern worden gevalideerd.
- `projection_candidate_validation` berekent kandidaat-30-dagenwaarden, maar markeert ze als niet-publiceerbaar zolang de kwaliteitsgate niet is gehaald.
- Officiële `projection_preview` blijft onder zeven dagen geblokkeerd en `null`.
- De vier resterende leverancier-all-in afhankelijkheden worden expliciet gerapporteerd.

## 10.5.30
- Voorbereiding op v10.6: de 30-dagen variabele-stroomprojectielogica is ingebouwd achter de bestaande 7-dagen kwaliteitsdrempel.
- `projection_preview` blijft leeg zolang de observatiedrempel niet is gehaald.
- Zodra de drempel gehaald is, kan de engine 30-dagen import en variabele stroomkosten berekenen uit de echte dag-run-rate.
- Leverancier-all-in projectie blijft apart geblokkeerd totdat opslag, vaste kosten, terugleververgoeding en gasformule gekoppeld zijn.
- `projection_engine` rapporteert expliciet de v10.6-gereedheid.

## 10.5.29
- Prognosekwaliteitsdrempel uit 10.5.28 uitgebreid met voortgangsmeting.
- Per maand worden `coverage_progress_pct` en `remaining_observation_days` gerapporteerd.
- Supplier cost model bevat een compacte `projection_observation_status`.
- Nog steeds geen voortijdige extrapolatie: pas na minimaal 7 waargenomen dagen wordt de maand prognosegeschikt.

## 10.5.28
- De herstelde verbruikgewogen NextEnergy-keten uit 10.5.27 is nu voorzien van een expliciete prognosekwaliteitsdrempel.
- `observed_coverage_days` en `projection_eligibility` toegevoegd per financiële maand.
- Minimaal 7 dagen echte kwartierwaarnemingen vereist voordat een maand überhaupt prognosegeschikt wordt gemarkeerd.
- Nog steeds geen automatische maand- of contractjaarextrapolatie; leverancier-all-in componenten ontbreken nog.
- Supplier cost model toont voortaan `projection_ready_months` en de gehanteerde projection policy.

## 10.5.27
- Runtimefout uit 10.5.26 hersteld: `timezone` wordt nu correct uit `datetime` geïmporteerd.
- De 10.5.26-diagnostiek bewees dat zowel 307 prijs- als 307 P1-importsnapshots correct worden geladen; de MCP-reader zelf is dus goed.
- Verbruikgewogen berekening en run-rate kunnen nu na `series_loaded` daadwerkelijk worden afgerond.

## 10.5.26
- Oorzaak van de lege verbruikgewogen reeks vastgesteld en hersteld.
- Werkelijke Energie MCP-toolnamen gebruikt: `search_files` en `read_text_file`.
- `search_files`-response wordt correct uit `matches` gelezen.
- Verbruikgewogen diagnostiek wordt altijd geëxporteerd, ook als de berekening niet beschikbaar is.
- Reader-status en aantallen prijs/importsnapshots maken regressies direct zichtbaar.

## 10.5.25
- Regressie uit 10.5.24 hersteld: verbruikgewogen NextEnergy-reader leest snapshots nu primair als volledig JSON-bestand via MCP.
- `search_content` blijft alleen compatibiliteitsfallback; contextregels worden niet meer blind als entiteitsstate geïnterpreteerd.
- Diagnostiek toegevoegd: aantallen gevonden prijs- en importsnapshots.
- Run-rate uit 10.5.24 blijft behouden zodra de robuuste reader geldige gekoppelde intervallen levert.

## 10.5.24
- Verbruikgewogen financiële waarneming uitgebreid met exacte geobserveerde tijdsduur.
- Veilige dag-run-rate toegevoegd voor import-kWh en variabele stroomkosten.
- Run-rate blijft expliciet een observatie van de beschikbare periode en wordt niet als volledige maandprognose gepresenteerd.
- Basis gelegd voor latere contractjaarprognose zodra voldoende representatieve dekking beschikbaar is.

## 10.5.23
- Verbruikgewogen NextEnergy-resultaten geïntegreerd in de financiële maandcontext.
- Maanden met echte geobserveerde kwartierkosten krijgen `partial_observed`.
- `months_partially_costable` bevat nu ook deze maanden.
- Geobserveerde import-kWh, verbruikgewogen stroomprijs en variabele stroomkosten worden direct financieel beschikbaar.
- Geen extrapolatie naar volledige maand en nog geen leverancier-all-in kosten.

## 10.5.22
- Eerste echte verbruikgewogen financiële analyse toegevoegd.
- NextEnergy-kwartierprijs wordt gekoppeld aan de delta van `sensor.p1_meter_energie_import` uit dezelfde NAS-snapshot.
- Levert geobserveerde import-kWh, verbruikgewogen EUR/kWh en geobserveerde importkosten.
- Dekking blijft expliciet `partial_observed_window`; nog geen volledig leverancier-all-in maandbedrag.

## 10.5.21
- Historische NextEnergy-reader gecorrigeerd voor de werkelijke NAS-opslaglocatie.
- Home Assistant leest kwartier-snapshots nu read-only via Energie MCP `search_content` uit `01_Input/YYYY_MM/HomeAssistant/QuarterHour`.
- Lokale filesystem-reader blijft uitsluitend als fallback bestaan.
- `supplier_price_history_transport` maakt zichtbaar via welke route de historische prijsdata is gevonden.
- Geen wijzigingen aan de stabiele release-watcherketen.

## 10.5.20
- Historische NextEnergy-prijstelemetrie toegevoegd vanuit Home Assistant kwartier-snapshots.
- Per beschikbare maand worden observatieaantal, gemiddelde, minimum, maximum en eerste/laatste timestamp berekend.
- `supplier_price_history_connected` maakt zichtbaar of historische leverancier-prijsdata daadwerkelijk beschikbaar is.
- Historische prijsstatistiek wordt expliciet als ongewogen prijstrend gemarkeerd; nog niet als verbruikgewogen energiekost.
- Bestaande NextEnergy live-koppeling en conservatieve all-in blokkering blijven intact.

## 10.5.19
- NextEnergy-contractcontext toegevoegd aan de analysecontext.
- Bekende contractgegevens vastgelegd: start 15-07-2026, dynamische stroom, variabel gas, voorschot €150, opzegtermijn 5 werkdagen.
- Live NextEnergy-stroomprijs wordt via de bestaande Home Assistant-entiteit uitgelezen en als prijstelemetrie gerapporteerd.
- `financial_status` toont nu of live leverancier-prijstelemetrie verbonden is.
- Leveranciersopslag, vaste kosten, terugleververgoeding en gasformule blijven bewust onbekend totdat officiële contractwaarden zijn gekoppeld.
- Sneloverzicht toont NextEnergy direct bovenaan.

## 10.5.18
- Eerste echte financiële analyse-laag toegevoegd.
- Marktvariabele stroom- en gaskosten worden alleen berekend wanneer meetdata en EPEX-prijsdata voor dezelfde maand beschikbaar zijn.
- Terugleververgoeding, leveranciersopslag, vaste kosten en all-in kosten blijven expliciet leeg totdat contractdata officieel is gekoppeld.
- `financial_status` toont direct welke maanden financieel berekenbaar zijn.
- Release-watchercontainer uit v10.5.17 blijft ongewijzigd.

## 10.5.17
- Release-watcher kan nu als aparte Container Station-container `energie-release-watcher` draaien met `restart=unless-stopped`.
- Nieuwe gedeelde heartbeat maakt singleton-detectie betrouwbaar tussen QNAP-hostprocessen en Docker PID-namespaces.
- Stale `.watcher.lock` wordt na 30 seconden zonder heartbeat automatisch hersteld.
- ZIP-validatie heeft een Python fallback (`tools/release_zip.py`), zodat de watcher-container geen extra `unzip`-pakket hoeft te installeren.
- Eenmalige bootstrap `tools/bootstrap_release_watcher_container.sh` maakt/stopt/herstart de container zonder de vier bestaande Energie-containers te wijzigen.
- EPEX-MCP en analyseverbeteringen uit v10.5.16 blijven behouden.

## 10.5.16
- EPEX-bronstatus onderscheidt nu een bereikbare bron van een nog ontbrekend maandbestand.
- Huidige maand zonder EPEX-bestand geeft `source_found=true` en `coverage.status=month_not_available`.
- Analysedownload toont bovenaan `price_status` met bronbereikbaarheid en beschikbare prijsmaanden.
- Releaseketen v10.5.15 blijft ongewijzigd; ZIP rechtstreeks naar `incoming`.
- Geen wijziging aan productiekern `9.4-core1`, maandworkflow of scheduler.

## 10.5.15
- Finder/SMB release-inname verder gehard: watcher controleert nu bestandsgrootte én wijzigingstijd over meerdere polls.
- De watcher voert vóór de installer zelf `unzip -tqq` uit; een nog onvolledige ZIP blijft in `incoming` en wordt niet meer naar `failed` verplaatst.
- Terminalvrije self-refresh en stale-lock herstel uit v10.5.14 blijven behouden.
- EPEX read-only MCP-brug uit v10.5.14 blijft behouden.
- Geen wijziging aan productiekern `9.4-core1`, maandworkflow of scheduler.

## 10.5.14
- Release-watcher herstart zichzelf na een succesvolle installatie rechtstreeks vanuit de nieuw geïnstalleerde release; QNAP cron/Terminal is niet meer nodig.
- Achtergebleven `.watcher.lock` en `.watcher.pid` worden automatisch hersteld wanneer de PID niet meer leeft.
- Finder/SMB ZIP-stabiliteitscontrole uit v10.5.13 blijft behouden.
- EPEX-analyse krijgt een tweede, werkelijke gegevensroute: read-only via de bestaande Energie MCP op de QNAP (`192.168.1.200:8000/mcp`) wanneer geen lokale HA-mount beschikbaar is.
- Geen wijziging aan productiekern `9.4-core1`, maandworkflow of scheduler.

## 10.5.13
- Release-watcher wacht nu op een volledig gekopieerde en stabiele ZIP voordat de installer start.
- Voorkomt Finder/QNAP-race waarbij een ZIP tijdens SMB-kopiëren al werd verplaatst en als corrupt werd afgekeurd.
- EPEX-autodetectie uit v10.5.12 blijft behouden.
- Race-safe singleton-lock uit v10.5.11 blijft behouden.

## 10.5.12
- EPEX-brondetectie uitgebreid met begrensde autodetectie onder Home Assistant `/share` en `/media`.
- Alleen een werkelijk bestaand `EPEX_index.csv` geldt nog als gevonden bron; `resolved_path` is anders null.
- Race-safe releaseketen uit v10.5.11 blijft behouden.
- Geen wijziging aan productiekern, maandworkflow of scheduler.

## 10.5.11
- Verhelpt de race condition waardoor meerdere QNAP release-watchers tegelijk dezelfde ZIP konden detecteren.
- De watcher gebruikt nu een atomische directory-lock (`.watcher.lock`) in plaats van alleen een niet-atomische PID-controle.
- Een ZIP in `processing` wordt niet meer direct als verweesd naar `failed` verplaatst; alleen processing-ZIP's ouder dan 10 minuten worden automatisch in quarantaine gezet.
- Hiermee wordt voorkomen dat een tweede watcher een ZIP wegneemt terwijl de eerste installer hem nog valideert of uitpakt.
- De EPEX-correctie uit v10.5.10 blijft volledig behouden.
- Geen wijziging aan productiekern `9.4-core1`, maandworkflow of scheduler.

## 10.5.10
- Corrigeert de EPEX-bronlocatie op basis van de feitelijke Home Assistant netwerkshare: `/share/Energie_NAS/05_Maanddata/EPEX`.
- De reader controleert `EPEX_index.csv` voordat een kandidaatpad als geldig wordt gebruikt.
- Legacy locaties onder `EnergieProject` blijven als fallback ondersteund.
- `resolved_path` blijft in analysedata zichtbaar voor productiecontrole.
- Geen wijziging aan productiekern, maandworkflow, scheduler of automatische releaseketen.

## 10.5.9
- Corrigeert de EPEX-padresolutie voor Home Assistant: ondersteunt zowel een mount die direct op `05_Maanddata` staat als een mount op de volledige projectroot.
- `price_context.resolved_path` toegevoegd zodat de werkelijk gebruikte productiebron direct controleerbaar is.
- EPEX-formaat, dekkingscontrole en prijsdefinities uit v10.5.8 blijven ongewijzigd.
- Geen wijziging aan productiekern, maandworkflow, scheduler of automatische releaseketen.

## 10.5.8
- Corrigeert de EPEX-analysebron: leest de bestaande productiegegevens uit `05_Maanddata/EPEX/YYYY` in plaats van uit `01_Input/YYYY_MM`.
- Ondersteunt het werkelijke EPEX-v6 formaat: UTF-8 BOM, puntkomma en de kolommen `prijs_excl_btw`, `prijs_incl_btw` en `prijs_incl_btw_en_eb`.
- Neemt dekking uit `EPEX_index.csv` mee zodat gedeeltelijke maanden en bronhiaten expliciet zichtbaar blijven.
- Hoofdstatistiek gebruikt `prijs_incl_btw_en_eb`; dit wordt nadrukkelijk niet als leverancier-all-in prijs gepresenteerd.
- Geen wijziging aan productiekern, maandworkflow, scheduler of automatische releaseketen.

## 10.5.7
- Analysecontext uitgebreid met historische EPEX-prijscontext uit reeds aanwezige maandbestanden.
- Per maand worden voor elektriciteit en gas aantal observaties, gemiddelde, minimum en maximum beschikbaar gemaakt.
- Geen nieuwe databron en geen wijziging aan de maandworkflow of releaseketen.
- Geen all-in kostenberekening zolang leverancierstarief, belasting en volledige periode-dekking niet bewezen zijn.

## 10.5.6
- Nieuw **Sneloverzicht analyse** direct bovenaan de operationele console; historie, laatste analysemaand en datakwaliteit zijn zichtbaar zonder naar beneden te scrollen.
- Nieuwe knop **Download analysedata** levert de actuele analysecontext als JSON-download.
- Ontbrekende bronmetingen worden in de analysecontext voortaan `null` in plaats van misleidend `0.0`.
- Afgeleide zonne-KPI's worden niet berekend wanneer Enphase-opwek en P1-teruglevering aantoonbaar geen gelijk meetvenster vormen; dit wordt gemarkeerd als `inconsistent_period_coverage`.
- Kwartaal- en jaaraggregaties bevatten `metric_month_coverage` zodat zichtbaar is hoeveel maanden werkelijk aan iedere KPI bijdragen.
- Maandworkflow, scheduler, rapportagekern en automatische QNAP -> GitHub -> Home Assistant releaseketen zijn niet gewijzigd.

# Changelog EnergieProject

## 10.5.5
- Eerste productieverbetering van de v10.5 conversatie-/analysebasis.
- Nieuw read-only endpoint `analysis-context` bouwt een gestandaardiseerde context uit bestaande `01_Input/YYYY_MM`-maanddata.
- De context bevat maand-, kwartaal- en kalenderjaaraggregaties voor netafname, teruglevering, netto netbalans, gas, zonne-opwek, direct zonnegebruik, huishoudelijk gebruik, eigen-verbruikpercentage en zelfvoorzieningspercentage.
- Onvolledige kwartalen/jaren worden expliciet gemarkeerd; bronbeschikbaarheid en Enphase-fallback worden als kwaliteitsmetadata opgenomen.
- De operationele console bevat een directe link `Analysecontext`.
- Geen wijziging aan maandworkflow, scheduler, retry/finalization, rapportgeneratoren of automatische releaseketen.
- Productiekern blijft `9.4-core1`.

## 10.5.4
- End-to-end productietest van de volledige releaseketen.
- Geen functionele wijzigingen aan maandworkflow, scheduler, importlogica of rapportgeneratoren.
- Geen wijziging aan productiekern `9.4-core1`.
- Doel van deze release:
  `incoming -> QNAP processed -> automatische HA GitHub-publicatie -> Home Assistant update`.
- v10.5.4 mag niet handmatig via Terminal of GitHub worden gepubliceerd; daarmee wordt de automatische keten daadwerkelijk bewezen.

## v10.5.39
- Kritieke Home Assistant ingress-fix: interne proxy-IP wordt niet langer door een hardcoded allowlist geblokkeerd.
- Lost de melding “app lijkt nog niet klaar te zijn” op terwijl de app wel draait.
- Rapportpagina uit v10.5.37 blijft aanwezig.
