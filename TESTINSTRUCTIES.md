# Testinstructies v10.5.5

## Installatie via de bewezen automatische releaseketen
**Gebruik GEEN Home Assistant Terminal. Gebruik GEEN handmatige Git-commit of Git-push.** De normale automatische route is verplicht.

1. Plaats uitsluitend `EnergieProject_v10.5.5.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht tot QNAP de ZIP automatisch naar `processed` heeft verplaatst.
3. Controleer in de Energieproject-console dat `HA-publicatie` nog **Automatisch** is en dat laatste publicatie `10.5.5` wordt.
4. Installeer daarna v10.5.5 via de normale Home Assistant-knop **Bijwerken**.

## Functionele test v10.5.5
5. Open na de update de add-on **SlimmeMeterPortal Import** en daarna de console **Energieproject**.
6. Controleer bovenaan dat versie `10.5.5` draait en dat Workflow `idle`/normaal blijft.
7. Scroll naar **Diagnostiek en beheer**. Onderaan de kaart staat nu de link **Analysecontext**.
8. Klik **Analysecontext**. Er moet een JSON-pagina openen met bovenaan:
   - `schema: energie_analysis_context_v1`;
   - `version: 10.5.5`;
   - `scope`;
   - `history_span`;
   - `months`, `quarters` en `years`.
9. Controleer dat de bekende beschikbare maand(en) onder `months` voorkomen en dat dezelfde periode ook in `quarters` en `years` is geaggregeerd. Een onvolledig kwartaal/jaar moet `complete_quarter: false` of `complete_calendar_year: false` tonen.
10. Ga terug naar de console. Er hoeft voor deze versie **geen maandworkflow of automatische productietest** gestart te worden, omdat productiekern `9.4-core1` niet is gewijzigd.

Stuur daarna één screenshot van de bovenkant van de geopende `Analysecontext`-JSON en één screenshot waarop `months`/`quarters` zichtbaar zijn.
