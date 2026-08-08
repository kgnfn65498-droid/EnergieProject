# Testinstructies v10.5.6

## Installatie
1. Plaats uitsluitend `EnergieProject_v10.5.6.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht tot de ZIP automatisch naar `processed` is verplaatst.
3. Controleer in de Energieproject-console dat `HA-publicatie` **Automatisch** blijft en laatste publicatie `10.5.6` wordt.
4. Installeer v10.5.6 via de normale Home Assistant-knop **Bijwerken**.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.

## Functionele test v10.5.6
5. Open **SlimmeMeterPortal Import -> Energieproject**.
6. Controleer direct bovenaan:
   - versie `10.5.6`;
   - Workflow `idle`;
   - Releaseketen `Automatisch`;
   - HA-publicatie `Automatisch`;
   - nieuw blok **Sneloverzicht analyse** zichtbaar zonder naar onderen te scrollen.
7. Controleer in **Sneloverzicht analyse** dat Historie, Laatste analysemaand en Datakwaliteit gevuld zijn.
8. Klik **Download analysedata**. Er moet direct een JSON-bestand met naam `Energie_analyse_YYYYMMDD_HHMMSS.json` worden gedownload.
9. Klik optioneel **Bekijk technische analysecontext**. Controleer dat ontbrekende brondata als `null` wordt weergegeven en niet als een fictieve `0.0`.
10. Als Enphase-opwek lager is dan P1-teruglevering voor hetzelfde maandrecord, moeten afgeleide zonne-KPI's `null` zijn en moet `solar_balance_status` gelijk zijn aan `inconsistent_period_coverage`.

Geen maandworkflow of productietest starten; de productiekern is niet gewijzigd.
