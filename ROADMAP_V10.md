# Roadmap v10.x

## Afgerond
- v10.4.x: automatische QNAP ZIP-installatie.
- v10.5.0-v10.5.1: Home Assistant-ontwikkeling hervat en releasefasen zichtbaar.
- v10.5.2: GitHub Deploy Key en publisher toegevoegd.
- v10.5.3: publisherlogging, persistente status en automatische UI-status bewezen.
- v10.5.4: definitieve end-to-end productietest zonder Terminal.
- v10.5.5: eerste conversatie-/analysebasis met gestandaardiseerde maand-, kwartaal- en jaarcontext.
- v10.5.6: analysebasis bruikbaar gemaakt in de productieconsole met sneloverzicht, download en expliciete datakwaliteit.
- v10.5.7: bestaande EPEX-maandbestanden toegevoegd als historische prijscontext zonder ongefundeerde all-in kostenberekening.

## Vervolg v10.5
- Analysecontext stapsgewijs uitbreiden met alleen bewezen bruikbare historische financiële/prijscontext.
- Geen nieuwe architectuur of databron toevoegen zonder direct projectvoordeel.

## Daarna
- v11: proactieve energieassistent op basis van de gevalideerde analysecontext.

- v10.5.8: EPEX-analyse gekoppeld aan de echte productiebron `05_Maanddata/EPEX`, inclusief dekking en bronhiaten.

- v10.5.9: EPEX-padresolutie robuust gemaakt voor de Home Assistant-projectmount en zichtbaar gemaakt in analysedata.

- v10.5.10: EPEX gekoppeld aan de feitelijke Energie_NAS-root (`05_Maanddata/EPEX`).

- v10.5.11: release-watcher race condition opgelost met atomische singleton-lock en veilige processing-quarantaine.

- v10.5.12: EPEX-autodetectie over Home Assistant `/share` en `/media`.

- v10.5.13: SMB/Finder-safe ZIP-stabiliteitscontrole vóór release-installatie.

- v10.5.14: terminalvrije watcher-self-refresh en EPEX read-only MCP-brug.

- v10.5.15: pre-installer ZIP-integriteitsgate voor Finder/SMB uploads.
