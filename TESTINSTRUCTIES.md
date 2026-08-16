# Testinstructies v32.3.1 — kwartierdata, NextEnergy en gesprekspartner

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

