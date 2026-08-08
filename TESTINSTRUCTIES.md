# Testinstructies v10.5.7

1. Plaats `EnergieProject_v10.5.7.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht tot de automatische releaseketen hem verwerkt en Home Assistant v10.5.7 aanbiedt.
3. Installeer via **Bijwerken**. Gebruik GEEN Home Assistant Terminal. Gebruik GEEN handmatige Git-commit of Git-push.
4. Open **Energieproject** en controleer bovenaan: versie 10.5.7, workflow `idle`, releaseketen en HA-publicatie `Automatisch`.
5. Klik **Download analysedata**.
6. Stuur het gedownloade JSON-bestand terug. Ik controleer daarin `price_context` en of ontbrekende prijsdata correct als niet beschikbaar wordt behandeld.

Geen maandworkflow starten; productiekern, scheduler en maandworkflow zijn niet gewijzigd.
