# AGENT_TASK — EnergieProject 32.5.26 complete release closure + originele Type-3 / finale Inbox-opruiming

- mode: DEVELOPMENT
- reasoning: HIGH
- stap: 1/10
- owner: ChatGPT/Spock
- buildbasis: exact verified EnergieProject_v32.5.25.zip SHA256 bc667f11d6a22ef4588add6c213baff21c5b7ebd6591e5b4820732d5a9bbaf4a
- PM target: 2.0.0-rc61
- productieautoriteit: NEE

## Doel
Bouw één 32.5.26 die in dezelfde release alle bekende 32.5.25 closure-defecten en Peters finale Inbox-opruimscope oplost. Geen doorschuiven naar 32.5.27.

## Scope
1. Releasecontroller sluit autonoom processing -> processed na exact GitHub/NAS/HA-bewijs, zonder handmatige publication-state reconciliatie of ZIP-move.
2. Oorspronkelijke vijfdelige ClearUp-rubricering blijft leidend; Type-3 = twijfel/dependency-runtimecheck, niet generieke hygiene-debt.
3. Resterend oorspronkelijk Type-3 legacy pad crash_recovery_cleanup_result wordt canoniek omgebonden; legacy request/result writer/readers verdwijnen uit Inbox en reappearance wordt getest.
4. Inbox/failed wordt plat; bestaande en toekomstige corrupt/rejected/rolled_back/withdrawn/duplicates komen zonder submappen rechtstreeks onder failed met collision-safe herkenbare namen.
5. release_hold_tmp en historische losse publication/HA JSON-restanten verdwijnen veilig uit Inbox.
6. Inbox/processing bestaat alleen transactioneel tijdens actieve release, wordt na closure als lege directory verwijderd en idle componenten maken hem niet opnieuw aan.
7. .github_publisher.lock verhuist naar canonieke systeemlocklocatie; legacy hidden Inbox-lock verschijnt niet terug.
8. Inbox/projectmanager_v2 wordt ALS LAATSTE gesloten: RuntimeV2 blijft canoniek; ApprovalIngress gebruikt alleen Data/03_Systeem/Projectmanager/ApprovalIngress; historische legacy approvals zijn al verwerkt en legacy map + 32.4.11 resten verdwijnen.
9. New-chat bare `verder` bootstrap krijgt verplichte canonieke resume-context/readback zodat 32.5.25 checkpoint/handover vóór inhoudelijk antwoord wordt geladen.
10. Retained-release artifact export/download capability maakt NAS-retentie 3 daadwerkelijk zelfstandig bruikbaar in nieuwe chat.

## Niet wijzigen
- Type-2 002-012 niet opnieuw uitvoeren of heropenen.
- Geen nieuwe lifecycle-owner/watcherarchitectuur.
- Geen gebruikers-Terminal als route.
- Geen productieactie/restart/recreate/installatie.
- Geen testversoepeling of historische fixture-rewrite om GREEN te fabriceren.

## Bekende bewezen feiten
- Live 32.5.25 COMPLETE; Type-2 002-012 11/11 definitief GREEN.
- 32.5.25 incident: GitHub/HA exact maar processing bleef staan door publication-state split; handmatige evidence-bound reconcile was nodig.
- Nieuwe-chat E2E faalde omdat chat canonieke NAS-handover niet automatisch las vóór inhoudelijk antwoord.
- Huidige Inbox heeft failed-subdirs, lege release_hold_tmp, lege processing, historische publication/HA JSONs en legacy projectmanager_v2.
- Oorspronkelijke Type-3-lijst is teruggevonden; vrijwel alles is door Type-2 canoniek gemigreerd, behalve actief crash_recovery_cleanup_result legacy protocol.

## Acceptance
- Nieuwe tests RED op exact 32.5.25-baseline voor iedere gewijzigde foutklasse; daarna GREEN.
- Targeted regressies + alle direct gewijzigde release/Inbox/PM foutklassen + relevante historische regressies GREEN; CLOSED Type-2 002-012 wordt niet opnieuw als live/sequence-suite uitgevoerd.
- Python compile/shell syntax GREEN.
- Finale exacte ZIP: unique/safe entries, CRC, MANIFEST.sha256/SHA256SUMS exact.
- Exact fresh extract herhaalt volledige acceptance GREEN.
- Geen productieactie tijdens build; live-only gates expliciet LIVE_REQUIRED.

## Stopcriteria
Alleen stoppen bij echte safety/artifact/model blocker of wanneer finale exact geverifieerde ZIP klaar is. Gewone RED/testfout wordt autonoom onderzocht en gerepareerd.

## Platformgrens
- Release acceptance en host-capability Platform Qualification zijn afzonderlijke contracten.
- Een GREEN release-artifact mag host-capability Platform Qualification niet impliciet als bewezen markeren; host/live-only bewijs blijft apart LIVE_REQUIRED wanneer het niet in de ontwikkelomgeving kan worden uitgevoerd.
