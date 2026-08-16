# Testinstructies v32.3.5 — assistant fast-context runtime hotfix

1. Valideer `VERSIE.txt`, add-on `config.yaml` en `APP_VERSION` exact als 32.3.5.
2. Verifieer dat `ASSISTANT_ENGINE` `build_assistant_analysis_context` gebruikt en de beheerendpoint `build_analysis_context` behoudt.
3. Verifieer met de gerichte test dat één kwartier-snapshotpass meerdere kernentiteiten tegelijk uitleest.
4. Draai gesprekspartner-, probe-, mount-timing-, writable-handoff- en fast-context regressies.
5. Draai daarna de volledige pytest-suite, Python compile, shellsyntax, manifestcontrole en ZIP-integriteit.
6. Live acceptance blijft: health + augustus PARTIAL/kwartier + sessie juli + finance zonder invoice-actual + apparatuur/KB + negatieve route + negatieve payload, elk binnen de bestaande 5-secondenlimiet.
7. Automatische maandafsluiting blijft UIT; `finalize_month` niet gebruiken.

# Testinstructies v32.3.4 — assistant acceptance writable handoff

1. Valideer ZIP-integriteit, `MANIFEST.sha256` en `SHA256SUMS.json`.
2. Valideer `VERSIE.txt`, add-on `config.yaml` en `APP_VERSION` exact als 32.3.4.
3. Draai volledige pytest-regressie plus `tests/test_v3234_assistant_acceptance_handoff.py`.
4. Na live-installatie moet `Inbox/logs/assistant_runtime_acceptance.json` verschijnen; directe runtime-write naar `Data/03_Systeem/Projectmanager/State` is niet toegestaan/vereist.
5. Projectmanager leest en valideert dit handoff-bestand en promoveert het daarna via het bestaande smalle system-writecontract naar `Data/03_Systeem/Projectmanager/State/assistant_runtime_acceptance.json`.
6. Alleen `status=PASS` met alle zeven checks groen opent de volgende Voice-acceptatiestap; deze release activeert Voice niet.
7. Bevestig augustus 2026 als PARTIAL met Home Assistant-kwartierbron, dezelfde sessie naar juli, NextEnergy zonder factuuractual en apparaatantwoord met Knowledge Base-bron.
8. Bevestig negatieve checks: onbekende assistant-route 404 en extra write/action-veld 400.
9. Automatische maandafsluiting blijft UIT; `finalize_month` niet gebruiken.

---

# Testinstructies v32.3.3 — assistant runtime mount-timing hotfix

1. Valideer ZIP-integriteit en `MANIFEST.sha256`.
2. Valideer `VERSIE.txt`, add-on `config.yaml` en `APP_VERSION` exact als 32.3.3.
3. Draai volledige pytest-regressie plus `tests/test_v3232_assistant_runtime_self_probe.py`.
4. Na live-installatie moet `Data/03_Systeem/Projectmanager/State/assistant_runtime_acceptance.json` verschijnen.
5. Alleen `status=PASS` met alle checks groen opent de volgende Voice-acceptatiestap; deze release activeert Voice niet.
6. Bevestig augustus 2026 als PARTIAL met Home Assistant-kwartierbron, dezelfde sessie naar juli, NextEnergy zonder factuuractual en apparaatantwoord met Knowledge Base-bron.
7. Bevestig negatieve checks: onbekende assistant-route 404 en extra write/action-veld 400.
8. Automatische maandafsluiting blijft UIT; `finalize_month` niet gebruiken.

## Regressiebasis v32.3.1

## Automatisch vóór release
1. `pytest -q tests/test_v3230_phase1.py tests/test_v3230_conversation.py`.
2. Volledige `pytest -q`.
3. Compile alle Pythonbestanden.
4. `sh -n` op alle shellscripts.
5. Valideer `VERSIE.txt`, add-on `config.yaml` en `APP_VERSION` exact als 32.3.1.
6. Rebuild en controleer `MANIFEST.sha256` en `SHA256SUMS.json` op hash én grootte.
7. Bouw de uiteindelijke ZIP zonder bovenliggende map, test CRC/path-safety, pak opnieuw schoon uit en herhaal manifest-, compile- en regressiecontroles vanuit de ZIP zelf.

## Inhoudelijke acceptatie
- Lopende augustusmaand gebruikt Home Assistant `QuarterHour` primair zodra een geldige cumulatieve reeks bestaat.
- Import/export/gas komen uit cumulatieve begin/eindgrenzen; tellerreset of ongeldige reeks mag niet stil worden opgeteld.
- Rapport toont de werkelijk gedekte periode en blijft PARTIEEL.
- Afgesloten juli blijft exact 156,32 kWh afname, 603,97 kWh teruglevering en 33,89 m³ gas volgens de bestaande gevalideerde bronregels.
- Officieel NextEnergy-contract start 16-07-2026; stroomopslag 0,0219 €/kWh, gasopslag 0,0799 €/m³, vaste levering 5,99 €/maand per product.
- De €628,96 energiebelastingvermindering wordt één keer toegepast, nooit dubbel voor stroom en gas.
- Live NextEnergy-stroomprijs krijgt geen tweede opslag of energiebelasting bovenop de al inbegrepen componenten.
- Zonnebonus: 50%, uitsluitend 06:00–22:00, beursprijs > 0, bevestigde zonne-export, 6.000 kWh contractjaarcap.
- Factuuractual blijft onbekend/null zolang geen officiële nota als bron aanwezig is.
- Projecttermijn €150 en oorspronkelijk contracttermijn €118 blijven afzonderlijk gelabeld.

## Gesprekspartner
- `/api/assistant/health` is read-only en meldt release-identiteit 32.3.1.
- `/api/assistant/context` accepteert `query` en optioneel `session_id`.
- `deze maand` blijft PARTIEEL; `en vorige maand?` erft domein binnen dezelfde sessie.
- Apparatuurvragen gebruiken alleen read-only canonieke Knowledge Base-bronnen.
- Financiële antwoorden noemen geen factuuractual als die bron ontbreekt.
- Geen schrijf-, apparaatbesturings-, contractwijzigings- of externe actieprimitieven in de gesprekspartnermodule.

## Home Assistant na installatie
- Alleen via de normale `Inbox/incoming` → watcher → NAS → GitHub → Home Assistant-keten.
- Geen Terminal en geen handmatige Git-push voor de normale release.
- Controleer GUI/startup, projectstructuur en bestaande maandworkflow op regressies.
- Test `/api/assistant/health`, daarna minimaal: huidige maand gas, vorige maand vervolg, NextEnergy-kostenstatus en airco/Knowledge Base.
- Voice/Assist pas koppelen nadat deze liveacceptatie volledig groen is.
- Automatische maandafsluiting blijft UIT; augustus niet finaliseren.

## Bewezen veiligheids- en bronregels
- Gebruik GEEN Home Assistant Terminal.
- Historische EPEX-referentiedekking voor juli kon eerder gedeeltelijk zijn; dit wijzigt de gevalideerde juli-energieactuals niet.
- Gebruik GEEN handmatige Git-commit of Git-push.
- De historische gedeeltelijke EPEX-referentiedekking voor juli liep eerder t/m 2026-07-29; dit blijft alleen historische referentiecontext.

## Hotfix-aanvulling v32.3.1 — MCP system-pad guard

- Na installatie moet `Inbox/logs/mcp_system_path_guard_hotfix_v3231.json` `status=ok` melden.
- Guardstatus is `patched` of `already_guarded`; cleanupstatus is `removed_exact_duplicate_tree` of `already_absent`.
- `Data/03_Systeem/Data` moet daarna afwezig zijn; canoniek `Data/03_Systeem/Projectmanager` blijft intact.
- Herstart daarna uitsluitend `energie-filesystem-mcp` in Container Station zodat de actieve Python-runtime de nieuwe guard inlaadt.
- Negatieve acceptatietest: een system-write met `Data/03_Systeem/...` als argument moet vóór enige write een `ValueError` geven; `Projectmanager/...` blijft het geldige relatieve formaat.
- Onbekende inhoud, extra entries of afwijkende MCP-broncode moeten de hotfix fail-closed blokkeren.

