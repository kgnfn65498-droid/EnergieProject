# Changelog v8.16.1

- Correctieversie op v8.16.0 na de Home Assistant-productietest.
- Audittrailblok in de operationele console wordt nu tijdens de bestaande 2,5-seconden statuspoll live bijgewerkt.
- Auditintegriteit, recordaantal en recente auditrecords lopen daardoor direct gelijk met `/config/output/audit_trail.jsonl` zonder handmatige paginavernieuwing.
- **Controleer / herstel productiecertificaat** gebruikt na een geslaagde controle nu Post/Redirect/Get en keert direct terug naar de sectie Productiecertificaten in de console.
- De ruwe JSON-resultaatpagina verschijnt alleen nog bij een echte fout/afwijzing.
- De console toont na certificaatbeheer expliciet `Certificaat gecontroleerd — geldig` of `Certificaat hersteld — geldig`.
- Productiecertificaatbeheer blijft uitsluitend herstel toestaan uit aantoonbaar geslaagd testbewijs van exact de actieve versie.
- Geen wijzigingen aan auditbestandformaat, hashketen, maandworkflow, scheduler, retry-state, rapportgeneratoren of Recovery Update-contract.
